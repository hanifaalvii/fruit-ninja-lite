"""Visual effects with hard caps. Cheap by design: small lists, cached sprites, no per-pixel work."""
import colorsys
import math
import random
from collections import deque

import pygame

from . import settings

GRAVITY = 900.0


class Quality:
    """Sheds effects (never adds them back) when frames get slow."""

    def __init__(self, window=90, limit_ms=24.0):
        self.level = 2
        self.window, self.limit = window, limit_ms
        self.acc, self.n = 0.0, 0

    def record(self, frame_ms):
        if frame_ms > 250:  # tab switch / debugger pause, not real slowness
            return
        self.acc += frame_ms
        self.n += 1
        if self.n >= self.window:
            if self.acc / self.n > self.limit and self.level > 0:
                self.level -= 1
            self.acc, self.n = 0.0, 0

    @property
    def particle_cap(self):
        base = 60 if settings.WEB else 120
        return (base // 4, base // 2, base)[self.level]

    @property
    def splat_cap(self):
        return (8, 20, 36)[self.level]

    @property
    def parallax(self):
        return self.level >= 1


class Particles:
    def __init__(self, cap=120):
        self.cap = cap
        self.p = []

    @property
    def count(self):
        return len(self.p)

    def burst(self, x, y, color, n, speed, life=(0.4, 0.9), size=(2, 5), up=0.0):
        n = min(n, self.cap)
        for _ in range(n):
            a = random.uniform(0, 6.2832)
            sp = random.uniform(speed * 0.25, speed)
            life_ = random.uniform(*life)
            self.p.append([x, y, math.cos(a) * sp, math.sin(a) * sp - up, life_, life_,
                           random.uniform(*size), color])
        if len(self.p) > self.cap:
            del self.p[: len(self.p) - self.cap]

    def update(self, dt):
        alive = []
        for q in self.p:
            q[4] -= dt
            if q[4] > 0:
                q[3] += GRAVITY * dt
                q[0] += q[2] * dt
                q[1] += q[3] * dt
                alive.append(q)
        self.p = alive

    def draw(self, surf):
        circle = pygame.draw.circle
        for q in self.p:
            r = max(1, int(q[6] * (q[4] / q[5]) ** 0.5))
            circle(surf, q[7], (int(q[0]), int(q[1])), r)


class Shake:
    def __init__(self):
        self.amp = 0.0

    def kick(self, amount):
        self.amp = max(self.amp, amount)

    def update(self, dt):
        self.amp = max(0.0, self.amp - dt * 40)

    def offset(self):
        if self.amp < 0.5:
            return 0, 0
        a = self.amp
        return int(random.uniform(-a, a)), int(random.uniform(-a, a))


class TimeScale:
    def __init__(self):
        self.t = 0.0
        self.target = 1.0
        self.cur = 1.0

    def slowmo(self, duration, scale):
        self.t, self.target = duration, scale

    def update(self, dt):
        if self.t > 0:
            self.t -= dt
            want = self.target
        else:
            want = 1.0
        self.cur += (want - self.cur) * min(1.0, dt * 10)
        return self.cur


class SplatLayer:
    """Juice stains that stay on the backdrop and fade out slowly."""

    def __init__(self, art):
        self.art = art
        self.items = []

    def add(self, x, y, color, size, cap):
        if not self.art.splats:
            return
        src = random.choice(self.art.splats)
        size = int(size)
        s = pygame.transform.smoothscale(src, (size, size))
        s.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
        s = pygame.transform.rotate(s, random.uniform(0, 360)) if size < 140 else s
        self.items.append([s, x, y, 7.0])
        if len(self.items) > cap:
            del self.items[: len(self.items) - cap]

    def update(self, dt):
        for it in self.items:
            it[3] -= dt
        self.items = [i for i in self.items if i[3] > 0]

    def draw(self, surf):
        for s, x, y, life in self.items:
            s.set_alpha(int(190 * min(1.0, life / 2.5)))
            surf.blit(s, s.get_rect(center=(x, y)))

    def clear(self):
        self.items = []


class BladeTrail:
    LIFE = 0.22

    def __init__(self):
        self.pts = deque()

    def add(self, x, y, now):
        self.pts.append((x, y, now))

    def clear(self):
        self.pts.clear()

    def update(self, now):
        while self.pts and now - self.pts[0][2] > self.LIFE:
            self.pts.popleft()

    def colors(self, style, now):
        if style == "rainbow":
            c = colorsys.hsv_to_rgb((now * 0.8) % 1.0, 0.7, 1.0)
            core = tuple(int(v * 255) for v in c)
            return (255, 255, 255), core
        return settings.BLADE_COLORS.get(style) or settings.BLADE_COLORS["classic"]

    def draw(self, surf, style, now):
        pts = self.pts
        if len(pts) < 2:
            return
        core, glow = self.colors(style, now)
        line, circle = pygame.draw.line, pygame.draw.circle
        for i in range(1, len(pts)):
            a, b = pts[i - 1], pts[i]
            age = (now - b[2]) / self.LIFE
            w = max(1, int(11 * (1 - age)))
            line(surf, glow, a[:2], b[:2], w + 7)
            circle(surf, glow, b[:2], (w + 7) // 2)
        for i in range(1, len(pts)):
            a, b = pts[i - 1], pts[i]
            age = (now - b[2]) / self.LIFE
            w = max(1, int(11 * (1 - age)))
            line(surf, core, a[:2], b[:2], w)
            circle(surf, core, b[:2], max(1, w // 2))


class Shadows:
    """Soft drop shadows cached per radius; they drift and fade with height so fruit feel airborne."""

    def __init__(self):
        self.cache = {}

    def get(self, r):
        r = int(r) // 4 * 4 + 4
        s = self.cache.get(r)
        if s is None:
            w, h = r * 2 + 16, int(r * 1.3) + 12
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(6, 0, -1):
                k = i / 6
                pygame.draw.ellipse(s, (0, 0, 0, int(34 * (1 - k) + 10)),
                                    (int(w * (0.5 - 0.5 * k * 0.92 - 0.04)), int(h * (0.5 - 0.5 * k * 0.9)),
                                     int(w * k * 0.92), int(h * k * 0.9)))
            self.cache[r] = s
        return s

    def draw(self, surf, x, y, r):
        lift = max(0.0, min(1.0, (settings.H - y) / settings.H))
        sh = self.get(r * (1.0 - 0.25 * lift))
        sh.set_alpha(int(255 * (1.0 - 0.55 * lift)))
        surf.blit(sh, sh.get_rect(center=(x + 10 + 34 * lift, y + r * 0.78 + 16 + 40 * lift)))


class Flashes:
    """Bright cut lines and expanding shockwave rings."""

    def __init__(self):
        self.cuts = []
        self.rings = []

    def cut(self, x, y, dx, dy, length):
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        self.cuts.append([x - ux * length, y - uy * length, x + ux * length, y + uy * length, 0.16])

    def ring(self, x, y, color, size=1.0):
        self.rings.append([x, y, 0.0, color, size])

    def update(self, dt):
        for c in self.cuts:
            c[4] -= dt
        self.cuts = [c for c in self.cuts if c[4] > 0]
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.55]

    def draw(self, surf):
        for x0, y0, x1, y1, life in self.cuts:
            k = life / 0.16
            pygame.draw.line(surf, (255, 255, 255), (x0, y0), (x1, y1), max(1, int(7 * k)))
            pygame.draw.line(surf, (255, 240, 200), (x0, y0), (x1, y1), max(1, int(2 * k)))
        for x, y, t, col, size in self.rings:
            k = t / 0.55
            pygame.draw.circle(surf, col, (int(x), int(y)), int((30 + 330 * k) * size), max(1, int(14 * (1 - k))))

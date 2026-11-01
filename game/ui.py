"""Cyberpunk UI kit: an original angular stroke font, neon chamfered panels, glowing buttons and sliders.

Everything is drawn once and cached; frames only blit.
"""
import math

import pygame

from . import settings

CYAN = (0, 240, 255)
MAGENTA = (255, 42, 109)
YELLOW = (252, 238, 10)
VIOLET = (155, 92, 255)
GREEN = (57, 255, 120)
ORANGE = (255, 150, 30)
INK = (7, 3, 15)

_fonts = {}
_text_cache = {}
_shape_cache = {}


def font(size):
    f = _fonts.get(size)
    if f is None:
        if not settings.WEB:
            try:
                f = pygame.font.SysFont("rajdhani,bankgothic,eurostile,avenirnextcondensed,arialnarrow,arial", size,
                                        bold=True)
            except Exception:
                f = None
        if f is None:
            f = pygame.font.Font(None, int(size * 1.3))
        _fonts[size] = f
    return f


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out_back(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


# ------------------------------------------------------------- stroke font
# Glyphs live on a 4 x 6 grid (y down). Straight, chamfered strokes give the angular techno look.
_O = [(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]
_P = [(0, 6), (0, 0), (3, 0), (4, 1), (4, 2.2), (3, 3.2), (0, 3.2)]
GLYPHS = {
    "A": [[(0, 6), (0, 1.5), (1.5, 0), (2.5, 0), (4, 1.5), (4, 6)], [(0, 3.6), (4, 3.6)]],
    "B": [[(0, 0), (2.8, 0), (4, 1), (4, 2), (2.8, 3), (0, 3)], [(0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6), (0, 0)]],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "D": [[(0, 0), (0, 6), (2.8, 6), (4, 4.8), (4, 1.2), (2.8, 0), (0, 0)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "F": [[(4, 0), (0, 0), (0, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (4, 6), (4, 3.5), (2.2, 3.5)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(0.5, 0), (3.5, 0)], [(2, 0), (2, 6)], [(0.5, 6), (3.5, 6)]],
    "J": [[(4, 0), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "K": [[(0, 0), (0, 6)], [(4, 0), (0, 3), (4, 6)]],
    "L": [[(0, 0), (0, 6), (4, 6)]],
    "M": [[(0, 6), (0, 0), (2, 2.5), (4, 0), (4, 6)]],
    "N": [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    "O": [_O],
    "P": [_P],
    "Q": [_O, [(2.5, 4.5), (4, 6.4)]],
    "R": [_P, [(2, 3.2), (4, 6)]],
    "S": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 2.2), (1, 3), (3, 3), (4, 3.8), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    "U": [[(0, 0), (0, 5), (1, 6), (3, 6), (4, 5), (4, 0)]],
    "V": [[(0, 0), (2, 6), (4, 0)]],
    "W": [[(0, 0), (1, 6), (2, 3.5), (3, 6), (4, 0)]],
    "X": [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    "Y": [[(0, 0), (2, 3), (4, 0)], [(2, 3), (2, 6)]],
    "Z": [[(0, 0), (4, 0), (0, 6), (4, 6)]],
    "0": [_O, [(1, 4.8), (3, 1.2)]],
    "1": [[(0.8, 1.2), (2.2, 0), (2.2, 6)], [(0.8, 6), (3.6, 6)]],
    "2": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2.2), (0, 6), (4, 6)]],
    "3": [[(0, 0), (4, 0), (2, 2.6), (3, 2.8), (4, 3.8), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "4": [[(3, 6), (3, 0), (0, 4), (4, 4)]],
    "5": [[(4, 0), (0, 0), (0, 3), (3, 2.8), (4, 3.8), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "6": [[(4, 0.8), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 3.8), (3, 3), (0, 3.2)]],
    "7": [[(0, 0), (4, 0), (1.6, 6)]],
    "8": [[(1, 3), (0, 2), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3), (0, 4), (0, 5), (1, 6), (3, 6),
           (4, 5), (4, 4), (3, 3)]],
    "9": [[(4, 2.8), (1, 3), (0, 2), (0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5.2)]],
    "-": [[(0.4, 3), (3.6, 3)]],
    "+": [[(0.4, 3), (3.6, 3)], [(2, 1.4), (2, 4.6)]],
    "=": [[(0.4, 2.2), (3.6, 2.2)], [(0.4, 3.8), (3.6, 3.8)]],
    "/": [[(0, 6), (4, 0)]],
    ">": [[(0.4, 0.6), (3.6, 3), (0.4, 5.4)]],
    "<": [[(3.6, 0.6), (0.4, 3), (3.6, 5.4)]],
    "%": [[(0, 6), (4, 0)], [(0, 0.2), (1.3, 0.2), (1.3, 1.6), (0, 1.6), (0, 0.2)],
          [(2.7, 4.4), (4, 4.4), (4, 5.8), (2.7, 5.8), (2.7, 4.4)]],
    "?": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (2, 3.2), (2, 4)], [(2, 5.4), (2, 6)]],
    "(": [[(2.6, 0), (1.2, 1), (1.2, 5), (2.6, 6)]],
    ")": [[(1.4, 0), (2.8, 1), (2.8, 5), (1.4, 6)]],
    "[": [[(2.6, 0), (1.2, 0), (1.2, 6), (2.6, 6)]],
    "]": [[(1.4, 0), (2.8, 0), (2.8, 6), (1.4, 6)]],
    ".": [[(0, 5.4), (0, 6)]],
    ":": [[(0, 1.6), (0, 2.2)], [(0, 4.4), (0, 5)]],
    "!": [[(0, 0), (0, 3.9)], [(0, 5.4), (0, 6)]],
    ",": [[(0, 5.4), (-0.4, 6.4)]],
    "'": [[(0, 0), (0, 1.6)]],
    "*": [[(0.4, 1.6), (3.6, 4.4)], [(3.6, 1.6), (0.4, 4.4)], [(2, 1), (2, 5)]],
    "#": [[(1.2, 0), (0.8, 6)], [(3.2, 0), (2.8, 6)], [(0, 2), (4, 2)], [(0, 4), (4, 4)]],
}
NARROW = {".": 0.0, ":": 0.0, "!": 0.0, ",": 0.0, "'": 0.0, "(": 2.0, ")": 2.0, "[": 2.0, "]": 2.0}
SPACE = 2.4


def tech_ok(s):
    return all(c.upper() in GLYPHS or c == " " for c in s)


def tech(s, size, color, bold=1.0):
    """Angular techno lettering. `size` is roughly the font size in px (cap height = 0.74 x size)."""
    s = s.upper()
    cap = size * 0.74
    u = cap / 6.0
    th = max(1.6, cap / 6.2) * bold
    slant = 0.16
    SS = 2
    xs, x = [], th * 2
    for ch in s:
        xs.append(x)
        if ch == " ":
            x += SPACE * u
        else:
            w = NARROW.get(ch, 4.0)
            x += (w + 1.35) * u if w else 1.9 * u
    width = int(x + th * 2 + slant * 6 * u) + 2
    height = int(cap + th * 3 + 4)
    surf = pygame.Surface((width * SS, height * SS), pygame.SRCALPHA)
    col = (*color, 255)
    r = max(1, int(th * SS / 2))
    top = th * 1.5
    for ch, x0 in zip(s, xs):
        for poly in GLYPHS.get(ch, ()):
            pts = [((x0 + gx * u + (6 - gy) * slant * u) * SS, (top + gy * u) * SS) for gx, gy in poly]
            pygame.draw.lines(surf, col, False, pts, int(th * SS))
            for p in pts:
                pygame.draw.circle(surf, col, (int(p[0]), int(p[1])), r)
    return pygame.transform.smoothscale(surf, (width, height))


def render(s, size, color, use_tech):
    if use_tech:
        return tech(s, size, color)
    return font(size).render(s, True, color)


def text(s, size, color=(255, 255, 255), outline=INK, ow=2, use_tech=None):
    """Cached text with a dark outline so it stays readable on any board."""
    if use_tech is None:
        use_tech = size >= 30 and tech_ok(s)
    key = (s, size, color, outline, ow, use_tech)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 700:
            _text_cache.clear()
        base = render(s, size, color, use_tech)
        if outline and ow:
            ow = 1 if use_tech and size < 30 else ow
            w, h = base.get_size()
            surf = pygame.Surface((w + ow * 2, h + ow * 2 + 2), pygame.SRCALPHA)
            dark = render(s, size, outline, use_tech)
            for dx in (-ow, 0, ow):
                for dy in (-ow, 0, ow, ow + 2):
                    if dx or dy:
                        surf.blit(dark, (ow + dx, ow + dy))
            surf.blit(base, (ow, ow))
        else:
            surf = base
        _text_cache[key] = surf
    return surf


def blit_text(dst, s, size, pos, color=(255, 255, 255), anchor="center", outline=INK, ow=2, alpha=None,
              scale=1.0, use_tech=None):
    t = text(s, size, color, outline, ow, use_tech)
    if scale != 1.0:
        t = pygame.transform.smoothscale(t, (max(1, int(t.get_width() * scale)), max(1, int(t.get_height() * scale))))
    if alpha is not None:
        t = t.copy()
        t.set_alpha(max(0, min(255, int(alpha))))
    r = t.get_rect(**{anchor: pos})
    dst.blit(t, r)
    return r


# ------------------------------------------------------------------ neon boxes
def _chamfer(x, y, w, h, c):
    return [(x + c, y), (x + w, y), (x + w, y + h - c), (x + w - c, y + h), (x, y + h), (x, y + c)]


def neon_box(w, h, color, fill=INK, alpha=214, cut=12, glow=1.0, solid=False):
    """Chamfered glass panel with a glowing rim, accent ticks and faint scanlines."""
    key = ("neon", w, h, color, fill, alpha, cut, round(glow, 2), solid)
    s = _shape_cache.get(key)
    if s is not None:
        return s
    pad = 12
    s = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    pts = _chamfer(pad, pad, w, h, cut)
    if glow > 0:
        for i in range(6, 0, -1):
            pygame.draw.polygon(s, (*color, int(14 * glow)), pts, i * 2)
    body = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    if solid:
        pygame.draw.polygon(body, (*color, 255), pts)
    else:
        pygame.draw.polygon(body, (*lerp_col(fill, color, 0.10), alpha), pts)
        sheen = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            k = 1.0 - y / max(1, h - 1)
            sheen.fill((*color, int(26 * k * k)), (0, y, w, 1))
        mask = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
        full = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
        full.blit(sheen, (pad, pad))
        full.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        body.blit(full, (0, 0))
    s.blit(body, (0, 0))
    pygame.draw.polygon(s, (*color, 255), pts, 2)
    hi = lerp_col(color, (255, 255, 255), 0.6)
    pygame.draw.line(s, (*hi, 200), (pad + cut + 2, pad + 3), (pad + min(w - 6, cut + 46), pad + 3), 2)
    pygame.draw.line(s, (*color, 255), (pad + w - cut - 38, pad + h - 3), (pad + w - cut - 3, pad + h - 3), 3)
    pygame.draw.line(s, (*color, 255), (pad, pad + cut + 6), (pad, pad + cut + 22), 4)
    _shape_cache[key] = s
    return s


def pill(w, h, col, radius=None):
    """Kept for the scenes that call it: now a neon chamfered panel."""
    return neon_box(w, h, col, cut=max(8, min(20, h // 5)))


def panel(w, h, fill=(10, 6, 24, 214), border=CYAN, radius=22):
    return neon_box(w, h, border, fill=fill[:3], alpha=fill[3] if len(fill) > 3 else 214, cut=16)


class Button:
    def __init__(self, label, cx, cy, cb, w=200, h=48, col=CYAN, size=24, primary=False):
        self.label, self.cb, self.col, self.size, self.primary = label, cb, col, size, primary
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (cx, cy)
        self.hover = 0.0
        self.press = 0.0
        self.enabled = True

    def update(self, dt, mouse):
        target = 1.0 if self.rect.collidepoint(mouse) and self.enabled else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14)
        self.press = max(0.0, self.press - dt * 5)

    def hit(self, pos):
        if self.enabled and self.rect.collidepoint(pos):
            self.press = 1.0
            self.cb()
            return True
        return False

    def draw(self, surf):
        w, h = self.rect.size
        col = self.col if self.enabled else (90, 84, 104)
        if self.primary:
            base = neon_box(w, h, col, solid=True, cut=12, glow=1.4)
            txt = (12, 6, 20)
        else:
            base = neon_box(w, h, col, cut=12)
            txt = (255, 255, 255)
        c = self.rect.center
        k = 1.0 - 0.05 * self.press
        spr = base
        if k != 1.0:
            spr = pygame.transform.smoothscale(base, (int(base.get_width() * k), int(base.get_height() * k)))
        surf.blit(spr, spr.get_rect(center=c))
        if self.hover > 0.02:
            hc = lerp_col(col, (255, 255, 255), 0.25)
            hot = neon_box(w, h, hc, solid=True, cut=12, glow=2.2) if self.primary else \
                neon_box(w, h, hc, fill=lerp_col(INK, col, 0.35), alpha=235, cut=12, glow=2.0)
            hot = hot.copy()
            hot.set_alpha(int(255 * self.hover))
            surf.blit(hot, hot.get_rect(center=c))
        blit_text(surf, self.label, self.size, (c[0], c[1] + 1), txt, outline=None if self.primary else INK)


class Slider:
    def __init__(self, label, x, y, w, value):
        self.label, self.rect, self.value, self.drag = label, pygame.Rect(x, y, w, 12), value, False

    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.inflate(30, 44).collidepoint(e.pos):
            self.drag = True
        if e.type == pygame.MOUSEBUTTONUP:
            self.drag = False
        if self.drag and e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            self.value = min(1.0, max(0.0, (e.pos[0] - self.rect.x) / self.rect.w))
            return True
        return False

    def draw(self, surf):
        blit_text(surf, self.label, 26, (self.rect.x - 22, self.rect.centery), anchor="midright", color=CYAN)
        pygame.draw.rect(surf, (4, 2, 10), self.rect.inflate(6, 8))
        pygame.draw.rect(surf, (60, 40, 110), self.rect.inflate(6, 8), 1)
        n = 28
        gap = self.rect.w / n
        for i in range(n):
            on = (i + 0.5) / n <= self.value
            col = lerp_col(CYAN, MAGENTA, i / n) if on else (36, 26, 64)
            pygame.draw.rect(surf, col, (self.rect.x + i * gap + 1, self.rect.y + 1, gap - 3, self.rect.h - 2))
        x = self.rect.x + int(self.rect.w * self.value)
        cy = self.rect.centery
        diamond = [(x, cy - 16), (x + 9, cy), (x, cy + 16), (x - 9, cy)]
        pygame.draw.polygon(surf, YELLOW, diamond)
        pygame.draw.polygon(surf, (255, 255, 255), diamond, 2)


def heart(size, filled=True):
    """Neon heart: lit magenta when alive, dim when lost."""
    key = ("heart", size, filled)
    s = _shape_cache.get(key)
    if s is None:
        s = pygame.Surface((size + 12, size + 12), pygame.SRCALPHA)
        o = 6
        r = size // 4
        cy = o + size // 2 - r // 2
        cx = o + size // 2
        pts = [(cx - 2 * r + 1, cy + 2), (cx + 2 * r - 1, cy + 2), (cx, o + size - 2)]
        if filled:
            for i in range(4, 0, -1):
                pygame.draw.polygon(s, (*MAGENTA, 22), pts, i * 3)
                pygame.draw.circle(s, (*MAGENTA, 22), (cx - r, cy), r + i * 2)
                pygame.draw.circle(s, (*MAGENTA, 22), (cx + r, cy), r + i * 2)
        col = MAGENTA if filled else (80, 40, 70)
        pygame.draw.circle(s, col, (cx - r, cy), r + 1)
        pygame.draw.circle(s, col, (cx + r, cy), r + 1)
        pygame.draw.polygon(s, col, pts)
        if filled:
            pygame.draw.circle(s, (255, 200, 220), (cx - r, cy - r // 3), max(2, r // 3))
        _shape_cache[key] = s
    return s


def make_logo():
    """FRUIT SLASH in glitchy neon techno lettering (built once at load)."""
    parts = (("FRUIT", YELLOW, ORANGE), ("SLASH", (255, 90, 160), MAGENTA))
    gap = 46
    rendered = []
    for word, c0, c1 in parts:
        m = tech(word, 150, (255, 255, 255), bold=1.35)
        grad = pygame.Surface(m.get_size(), pygame.SRCALPHA)
        for y in range(m.get_height()):
            grad.fill((*lerp_col(c0, c1, y / m.get_height()), 255), (0, y, m.get_width(), 1))
        grad.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        rendered.append((m, grad))
    W = sum(m.get_width() for m, _ in rendered) + gap + 80
    H = rendered[0][0].get_height() + 70
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    x = 40
    for (m, grad), (_, _c0, c1) in zip(rendered, parts):
        for ang in range(0, 360, 30):
            ox, oy = math.cos(math.radians(ang)) * 9, math.sin(math.radians(ang)) * 9
            g = m.copy()
            g.fill((*c1, 255), special_flags=pygame.BLEND_RGBA_MULT)
            g.set_alpha(26)
            glow.blit(g, (x + ox, 35 + oy))
        ghost_c = m.copy()
        ghost_c.fill((*CYAN, 255), special_flags=pygame.BLEND_RGBA_MULT)
        ghost_c.set_alpha(190)
        out.blit(ghost_c, (x - 6, 35 + 2))
        ghost_m = m.copy()
        ghost_m.fill((*MAGENTA, 255), special_flags=pygame.BLEND_RGBA_MULT)
        ghost_m.set_alpha(150)
        out.blit(ghost_m, (x + 6, 35 - 2))
        dark = m.copy()
        dark.fill((*INK, 255), special_flags=pygame.BLEND_RGBA_MULT)
        for dx, dy in ((-3, 0), (3, 0), (0, 3), (0, -3), (3, 5)):
            out.blit(dark, (x + dx, 35 + dy))
        out.blit(grad, (x, 35))
        x += m.get_width() + gap
    cut = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.line(cut, (*CYAN, 255), (W // 2 - 70, H - 12), (W // 2 + 70, 10), 5)
    pygame.draw.line(cut, (255, 255, 255, 255), (W // 2 - 70, H - 12), (W // 2 + 70, 10), 2)
    final = pygame.Surface((W, H), pygame.SRCALPHA)
    final.blit(glow, (0, 0))
    final.blit(out, (0, 0))
    final.blit(cut, (0, 0))
    return final

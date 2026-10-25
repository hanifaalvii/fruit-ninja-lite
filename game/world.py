"""Animated parallax backdrop: sky, drifting clouds, scrolling hills and ambient motes."""
import math
import random

import pygame

from . import settings

W, H = settings.W, settings.H


def additive_glow(glow, size, color):
    """Pre-multiplied glow that can be added with BLEND_RGB_ADD (cheap sparkle)."""
    s = pygame.Surface((size, size))
    s.fill((0, 0, 0))
    g = pygame.transform.smoothscale(glow, (size, size))
    g.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(g, (0, 0))
    return s


class Backdrop:
    def __init__(self, app):
        self.app = app
        self.t = 0.0
        self.name = None
        self.clouds = []
        self.motes = []
        self.cloud_sprites = []
        self.petals = []
        self.leaves = []
        self.glows = []
        self.ready = False

    def setup(self):
        art = self.app.art
        if art.cloud is None or art.glow is None or art.petal is None or self.ready:
            return
        rng = random.Random(4)
        for sc, a in ((0.8, 140), (1.1, 110), (1.5, 80)):
            c = pygame.transform.smoothscale(art.cloud, (int(260 * sc), int(110 * sc)))
            c.set_alpha(a)
            self.cloud_sprites.append(c)
        for i in range(5):
            self.clouds.append([rng.uniform(0, W), rng.uniform(30, 230), rng.uniform(5, 16), i % 3])
        self.glows = [additive_glow(art.glow, 26, (255, 230, 150)), additive_glow(art.glow, 18, (255, 240, 200)),
                      additive_glow(art.glow, 34, (255, 200, 120))]
        self.petals = [pygame.transform.rotate(art.petal, a) for a in range(0, 360, 30)]
        self.leaves = [pygame.transform.rotate(art.leaf, a) for a in range(0, 360, 30)]
        for _ in range(16):
            self.motes.append([rng.uniform(0, W), rng.uniform(0, H), rng.uniform(-18, 18), rng.uniform(14, 40),
                               rng.uniform(0, 6.28)])
        self.ready = True

    def set_theme(self, name):
        self.name = name

    def update(self, dt):
        self.t += dt
        if not self.ready:
            self.setup()
            return
        for c in self.clouds:
            c[0] += c[2] * dt
            if c[0] > W + 40:
                c[0] = -300
        if self.app.quality.level >= 1:
            slow = 0.4 if self.name in ("night", "dusk") else 1.0
            for m in self.motes:
                m[0] += (m[2] + math.sin(self.t + m[4]) * 20) * dt
                m[1] += m[3] * dt * slow
                if m[1] > H + 20:
                    m[1], m[0] = -20, random.uniform(0, W)
                if m[0] > W + 20:
                    m[0] = -20
                elif m[0] < -20:
                    m[0] = W + 20

    def draw(self, surf):
        th = self.app.art.theme(self.name or self.app.save["bg"])
        q = self.app.quality
        if not (q.parallax and self.ready):
            surf.blit(th.static, (0, 0))
            return
        surf.blit(th.sky, (0, 0))
        for x, y, _s, k in self.clouds:
            surf.blit(self.cloud_sprites[k], (x, y))
        for layer, speed in ((th.far, 6.0), (th.near, 14.0)):
            off = int((self.t * speed) % W)
            surf.blit(layer, (-off, th.top))
            surf.blit(layer, (W - off, th.top))
        n = len(self.motes) if q.level >= 2 else len(self.motes) // 2
        name = th.name
        for i in range(n):
            x, y, _vx, _vy, ph = self.motes[i]
            if name == "sakura":
                surf.blit(self.petals[int((self.t * 3 + ph * 2) % 12)], (x, y))
            elif name == "orchard":
                surf.blit(self.leaves[int((self.t * 2 + ph * 2) % 12)], (x, y))
            else:
                g = self.glows[int((self.t * 2 + ph) % 3)]
                surf.blit(g, (x, y), special_flags=pygame.BLEND_RGB_ADD)

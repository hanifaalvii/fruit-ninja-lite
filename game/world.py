"""Animated cutting-board backdrop: the board itself, drifting light, floating specks, and knife scars."""
import math
import random

import pygame

from . import settings

W, H = settings.W, settings.H


def additive_glow(glow, size, color):
    """Pre-multiplied glow that can be added with BLEND_RGB_ADD (cheap light)."""
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
        self.canvas = None
        self.canvas_name = None
        self.scar_cols = ((20, 10, 4), (255, 250, 240))
        self.motes = []
        self.glows = []
        self.sweep = None
        self.ready = False

    def setup(self):
        art = self.app.art
        if art.glow is None or self.ready:
            return
        rng = random.Random(4)
        self.glows = [additive_glow(art.glow, 22, (255, 240, 200)), additive_glow(art.glow, 14, (255, 250, 230)),
                      additive_glow(art.glow, 30, (255, 220, 160))]
        self.sweep = additive_glow(art.glow, 520, (44, 36, 24))
        for _ in range(18):
            self.motes.append([rng.uniform(0, W), rng.uniform(0, H), rng.uniform(-10, 10), rng.uniform(-14, -4),
                               rng.uniform(0, 6.28)])
        self.ready = True

    def board(self):
        name = self.name or self.app.save["bg"]
        if name not in settings.BOARDS:
            name = settings.DEFAULT_BOARD
        return name

    def set_theme(self, name):
        self.name = name
        self.reset()

    def reset(self):
        """Fresh board: wipes the knife scars from the previous run."""
        name = self.board()
        th = self.app.art.theme(name)
        self.canvas = th.static.copy()
        self.canvas_name = name
        avg = pygame.transform.average_color(th.static)[:3]
        self.scar_cols = (tuple(int(v * 0.5) for v in avg), tuple(min(255, int(v * 1.22) + 14) for v in avg))

    def scar(self, a, b):
        """Knife marks that stay on the board for the rest of the run (painted into the cached board)."""
        if self.canvas is None or self.canvas_name != self.board():
            self.reset()
        dark, light = self.scar_cols
        pygame.draw.line(self.canvas, dark, a, b, 2)
        pygame.draw.line(self.canvas, light, (a[0] + 1, a[1] + 2), (b[0] + 1, b[1] + 2), 1)

    def update(self, dt):
        self.t += dt
        if not self.ready:
            self.setup()
            return
        if self.app.quality.level >= 1:
            for m in self.motes:
                m[0] += (m[2] + math.sin(self.t * 0.7 + m[4]) * 12) * dt
                m[1] += m[3] * dt
                if m[1] < -20:
                    m[1], m[0] = H + 20, random.uniform(0, W)
                if m[0] > W + 20:
                    m[0] = -20
                elif m[0] < -20:
                    m[0] = W + 20

    def draw(self, surf):
        if self.canvas is None or self.canvas_name != self.board():
            self.reset()
        surf.blit(self.canvas, (0, 0))
        q = self.app.quality
        if not (q.parallax and self.ready):
            return
        if q.level >= 2 and self.sweep is not None:
            x = (self.t * 38) % (W + 900) - 700
            y = 120 + 90 * math.sin(self.t * 0.31)
            surf.blit(self.sweep, (x, y), special_flags=pygame.BLEND_RGB_ADD)
        n = len(self.motes) if q.level >= 2 else len(self.motes) // 2
        for i in range(n):
            x, y, _vx, _vy, ph = self.motes[i]
            g = self.glows[int((self.t * 1.5 + ph) % 3)]
            surf.blit(g, (x, y), special_flags=pygame.BLEND_RGB_ADD)

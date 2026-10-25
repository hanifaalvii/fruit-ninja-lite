"""Shared scene plumbing: Scene base, fruit splitting, the sliding Top-3 leaderboard tab."""
import math
import random

import pygame

from . import settings, ui
from .entities import Piece
from .net import SHORT

W, H = settings.W, settings.H


class Scene:
    def __init__(self, app):
        self.app = app

    def enter(self, **kw):
        pass

    def handle(self, e):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


def split_fruit(art, x, y, vx, vy, dx, dy, pieces):
    n = math.hypot(dx, dy) or 1.0
    ang = math.degrees(math.atan2(-dy, dx))
    nx, ny = -dy / n, dx / n
    for side, sgn in ((-1, 1), (1, -1)):
        pieces.append(Piece(art, side, x, y, vx + nx * 130 * sgn, vy * 0.4 + ny * 130 * sgn, ang - 90,
                            random.uniform(40, 160) * sgn))


class BoardPanel:
    PW, PH, PY, PEEK = 340, 190, 200, 64

    def __init__(self, app):
        self.app = app
        self.t = 0.0
        self.open = False

    def rect(self):
        return pygame.Rect(int(W - self.PEEK - (self.PW - self.PEEK) * self.t), self.PY, self.PW, self.PH)

    def update(self, dt):
        over = self.rect().collidepoint(self.app.mouse)
        target = 1.0 if (self.open or over) else 0.0
        self.t += (target - self.t) * min(1.0, dt * 12)
        self.app.board.refresh(pygame.time.get_ticks())

    def click(self, pos):
        if self.rect().collidepoint(pos):
            self.open = not self.open
            return True
        self.open = False
        return False

    def draw(self, surf):
        r = self.rect()
        b = self.app.board
        surf.blit(ui.panel(self.PW, self.PH, radius=22), r.topleft)
        gold = (255, 210, 74)
        ui.blit_text(surf, "TOP 3", 20, (r.x + 14, r.y + 12), gold, "topleft")
        medals = [(255, 210, 74), (200, 205, 215), (205, 127, 50)]
        for i, row in enumerate(b.rows):
            cy = r.y + 72 + i * 46
            pygame.draw.circle(surf, medals[i], (r.x + 30, cy), 14)
            ui.blit_text(surf, str(i + 1), 18, (r.x + 30, cy), (40, 20, 5), outline=None)
            ui.blit_text(surf, row["name"], 18, (r.x + 54, cy), anchor="midleft")
            ui.blit_text(surf, str(row["score"]), 18, (r.x + 262, cy), gold, "midright")
            ui.blit_text(surf, SHORT[row["mode"]], 14, (r.x + 270, cy), (230, 210, 180), "midleft", outline=None)
        if not b.rows:
            ui.blit_text(surf, b.status, 18, (r.x + 54, r.y + 100), (230, 210, 180), "midleft")

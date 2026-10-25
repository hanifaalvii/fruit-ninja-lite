"""Things that fly through the air."""
import math

import pygame

from . import settings

MAX_DT = 1 / 30


def clamp_dt(dt):
    return min(dt, MAX_DT)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Item:
    __slots__ = ("kind", "art", "name", "r", "x", "y", "vx", "vy", "rot", "vrot", "hp", "alive",
                 "hit_t", "bonus", "gscale", "age")

    def __init__(self, kind, art, name, r, x, y, vx, vy, vrot, hp=1, bonus=False, gscale=1.0):
        self.kind, self.art, self.name, self.r = kind, art, name, r
        self.x, self.y, self.vx, self.vy, self.vrot = x, y, vx, vy, vrot
        self.rot = (x * 7) % 360
        self.hp, self.alive, self.hit_t, self.bonus, self.gscale, self.age = hp, True, 0.0, bonus, gscale, 0.0

    def update(self, dt, g):
        self.vy += g * self.gscale * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.vrot * dt
        self.age += dt
        if self.hit_t > 0:
            self.hit_t -= dt

    def draw(self, surf):
        img = self.art.frame(self.rot)
        if self.hit_t > 0:
            img = img.copy()
            img.fill((int(120 * self.hit_t / 0.12),) * 3 + (0,), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(img, img.get_rect(center=(self.x, self.y)))


class Piece:
    __slots__ = ("art", "side", "x", "y", "vx", "vy", "rot", "vrot")

    def __init__(self, art, side, x, y, vx, vy, rot, vrot):
        self.art, self.side, self.x, self.y, self.vx, self.vy, self.rot, self.vrot = art, side, x, y, vx, vy, rot, vrot

    def update(self, dt, g=settings.H * 1.3):
        self.vy += g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.vrot * dt

    def draw(self, surf):
        img = self.art.half(self.side, self.rot)
        surf.blit(img, img.get_rect(center=(self.x, self.y)))

"""Staged asset loading + cached image helpers."""
import asyncio
import os
import time

import pygame

from . import settings

ANGLE_STEP = 6
N_ANGLES = 360 // ANGLE_STEP


class Loader:
    """Runs small steps in slices so the loading screen keeps animating at full frame rate."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.i = 0
        self.errors = []
        self.label = "Starting"

    @property
    def done(self):
        return self.i >= len(self.steps)

    @property
    def progress(self):
        return 1.0 if not self.steps else min(1.0, self.i / len(self.steps))

    def _one(self):
        label, fn = self.steps[self.i]
        self.label = label
        try:
            fn()
        except Exception as exc:  # a missing/corrupt asset must never stop the game booting
            self.errors.append((label, repr(exc)))
        self.i += 1

    def step(self, budget=0.006):
        t0 = time.perf_counter()
        while not self.done:
            self._one()
            if time.perf_counter() - t0 >= budget:
                break
        return self.done

    async def run(self, progress_cb=None):
        while not self.done:
            self._one()
            if progress_cb:
                progress_cb(self.progress, self.label)
            await asyncio.sleep(0)


def load_image(rel, alpha=True):
    path = os.path.join(settings.ASSETS, "img", rel)
    try:
        img = pygame.image.load(path)
        return img.convert_alpha() if alpha else img.convert()
    except Exception:
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 0, 255), (32, 32), 30)
        return s


class SphereArt:
    """A body that tumbles + a light overlay that stays put = 3D look from cached frames."""

    def __init__(self, body, light, left=None, right=None, radius=36):
        self.body, self.light, self.left, self.right, self.r = body, light, left, right, radius
        self._frames, self._halves = {}, {}

    def frame(self, angle):
        k = int(round(angle / ANGLE_STEP)) % N_ANGLES
        f = self._frames.get(k)
        if f is None:
            f = pygame.transform.rotate(self.body, k * ANGLE_STEP)
            f.blit(self.light, self.light.get_rect(center=f.get_rect().center))
            self._frames[k] = f
        return f

    def half(self, side, angle):
        k = (side, int(round(angle / ANGLE_STEP)) % N_ANGLES)
        f = self._halves.get(k)
        if f is None:
            f = pygame.transform.rotate(self.left if side < 0 else self.right, k[1] * ANGLE_STEP)
            self._halves[k] = f
        return f

    def prewarm(self, n=12):
        for k in range(0, N_ANGLES, max(1, N_ANGLES // n)):
            self.frame(k * ANGLE_STEP)


class Theme:
    def __init__(self, name):
        self.name = name
        self.sky = load_image(f"bg_{name}_sky.jpg", alpha=False)
        far = load_image(f"bg_{name}_far.png")
        near = load_image(f"bg_{name}_near.png")
        top = 300
        self.far = far.subsurface((0, top, settings.W, settings.H - top)).copy()
        self.near = near.subsurface((0, top, settings.W, settings.H - top)).copy()
        self.top = top
        self.static = self.sky.copy()
        self.static.blit(self.far, (0, top))
        self.static.blit(self.near, (0, top))
        self.static = self.static.convert()


class Art:
    def __init__(self):
        self.fruit = {}
        self.bomb = self.boss = None
        self.orbs = {}
        self.splats = []
        self.glow = self.cloud = self.petal = self.leaf = self.logo = None
        self.themes = {}
        self._tint = {}

    def sphere(self, name, radius, halves=True):
        return SphereArt(load_image(f"{name}_body.png"), load_image(f"{name}_light.png"),
                         load_image(f"{name}_L.png") if halves else None,
                         load_image(f"{name}_R.png") if halves else None, radius)

    def theme(self, name):
        if name not in self.themes:
            self.themes[name] = Theme(name)
        return self.themes[name]

    def tinted(self, key, surf, color):
        k = (key, color)
        t = self._tint.get(k)
        if t is None:
            t = surf.copy()
            t.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._tint[k] = t
        return t

    def steps(self):
        def fruits():
            for n in settings.FRUITS:
                self.fruit[n] = self.sphere(f"fruit_{n}", settings.FRUIT_RADIUS[n])
                self.fruit[n].prewarm(6)

        def orbs():
            for n in ("pu_slowmo", "pu_double", "pu_rain", "freeze", "frenzy"):
                self.orbs[n] = self.sphere(n, 36, halves=False)

        def misc():
            self.glow = load_image("glow.png")
            self.cloud = load_image("cloud.png")
            self.petal = load_image("petal.png")
            self.leaf = load_image("leaf.png")
            self.splats = [load_image(f"splat_{i}.png") for i in range(4)]

        def sphere_step(attr, name, r, halves):
            return lambda: setattr(self, attr, self.sphere(name, r, halves))

        return [
            ("Printing the logo", lambda: setattr(self, "logo", load_image("logo.png"))),
            ("Polishing fruit", fruits),
            ("Arming bombs", sphere_step("bomb", "bomb", 36, False)),
            ("Growing a giant melon", sphere_step("boss", "boss", 112, True)),
            ("Charging power-ups", orbs),
            ("Mixing juice", misc),
        ]

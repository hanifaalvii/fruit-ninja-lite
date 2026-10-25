"""Sound effects and music. Files from assets/, with a tiny synthesized fallback for effects."""
import array
import math
import os
import random

import pygame

from . import settings

SFX = ["swoosh", "splat", "bomb", "miss", "over", "click", "freeze", "frenzy", "powerup", "boss_hit",
       "boss_down", "achievement", "tick"] + [f"combo_{i}" for i in range(1, 6)] + \
      [f"slice_{f}_{v}" for f in settings.FRUITS for v in range(2)]
MUSIC = ["menu", "play", "tense"]


def _fallback(freq=600, dur=0.1):
    sr = 22050
    n = int(sr * dur)
    data = array.array("h", (int(9000 * math.sin(2 * math.pi * freq * i / sr) * (1 - i / n) ** 2)
                             for i in range(n)))
    return pygame.mixer.Sound(buffer=data.tobytes())


class Audio:
    def __init__(self, save):
        self.save = save
        self.sounds, self.music_snd = {}, {}
        self.cur = None
        self.duck_t = 0.0
        self.duck_v = 1.0
        self.ok = pygame.mixer.get_init() is not None
        self.chs = []
        if self.ok:
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(2)
            self.chs = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
        self.flip = 0

    # --------------------------------------------------------------- loading
    def load_sfx(self, name):
        if not self.ok:
            return
        path = os.path.join(settings.ASSETS, "sfx", name + ".ogg")
        try:
            self.sounds[name] = pygame.mixer.Sound(path)
        except Exception:
            try:
                self.sounds[name] = _fallback(300 + (hash(name) % 700))
            except Exception:
                pass

    def load_music(self, name):
        if not self.ok:
            return
        try:
            self.music_snd[name] = pygame.mixer.Sound(os.path.join(settings.ASSETS, "music", name + ".ogg"))
        except Exception:
            pass

    def steps(self):
        out = [("Sharpening sounds", lambda: [self.load_sfx(n) for n in SFX if n not in self.sounds]),
               ("Tuning the menu theme", lambda: self.load_music("menu")),
               ("Tuning the battle theme", lambda: self.load_music("play")),
               ("Tuning the tense theme", lambda: self.load_music("tense"))]
        return out

    # --------------------------------------------------------------- playback
    def sfx(self, name, vol=1.0):
        if not self.ok or self.save["mute"]:
            return
        s = self.sounds.get(name)
        if s:
            s.set_volume(min(1.0, self.save["sfx"] * vol))
            s.play()

    def slice_fruit(self, fruit):
        self.sfx(f"slice_{fruit}_{random.randint(0, 1)}", 0.9)

    def combo(self, level):
        self.sfx(f"combo_{max(1, min(5, level))}", 0.8)

    def music(self, name):
        if not self.ok or name == self.cur:
            return
        self.cur = name
        for c in self.chs:
            c.fadeout(450)
        snd = self.music_snd.get(name)
        if snd:
            self.flip ^= 1
            self.chs[self.flip].play(snd, loops=-1, fade_ms=500)
            self.apply_volume()

    def stop_music(self, fade=500):
        self.cur = None
        for c in self.chs:
            c.fadeout(fade)

    def apply_volume(self):
        if not self.ok:
            return
        v = 0.0 if self.save["mute"] else self.save["music"] * 0.8 * self.duck_v
        for c in self.chs:
            c.set_volume(v)

    def duck(self, seconds=1.2):
        self.duck_t = max(self.duck_t, seconds)

    def update(self, dt):
        want = 0.35 if self.duck_t > 0 else 1.0
        self.duck_t = max(0.0, self.duck_t - dt)
        if abs(self.duck_v - want) > 0.01:
            self.duck_v += (want - self.duck_v) * min(1.0, dt * 6)
            self.apply_volume()

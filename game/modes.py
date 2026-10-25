"""Wave director: decides what gets thrown and when. Pure logic, no pygame."""
from collections import namedtuple

from . import settings

SpawnSpec = namedtuple("SpawnSpec", "kind offset")
BOSS_EVERY = 8


class WaveDirector:
    def __init__(self, mode, difficulty, rng):
        self.mode = mode
        self.diff = settings.DIFFICULTY[difficulty]
        self.rng = rng

    def ramp(self, t):
        return min(1.0, t / (40.0 if self.mode == "sudden" else 90.0))

    def is_boss_wave(self, wave_no):
        return self.mode == "classic" and wave_no > 0 and wave_no % BOSS_EVERY == 0

    def interval(self, t, frenzy=False):
        if frenzy:
            return 0.45
        d = self.ramp(t)
        lo, hi = (1.6, 0.8) if self.mode != "sudden" else (1.2, 0.5)
        return (lo + (hi - lo) * d + self.rng.uniform(0, 0.3)) * self.diff["gap"]

    def next_wave(self, t, wave_no, frenzy=False):
        rng, d = self.rng, self.ramp(t)
        if self.is_boss_wave(wave_no):
            return [SpawnSpec("boss", 0.0)]
        if frenzy:
            return [SpawnSpec("fruit", i * 25.0) for i in range(rng.randint(3, 5))]
        base = 1 + int(rng.random() * (1 + d * 3))
        n = max(1, round(base * self.diff["count"] + 0.001))
        bomb_p = {"classic": 0.10 + 0.12 * d, "arcade": 0.12, "zen": 0.0,
                  "sudden": 0.18 + 0.15 * d}[self.mode] * self.diff["bomb"]
        out = []
        for i in range(n):
            bomb = rng.random() < bomb_p * (0.5 if i == 0 else 1.0)
            out.append(SpawnSpec("bomb" if bomb else "fruit", i * 30.0))
        if self.mode == "arcade" and rng.random() < 0.10:
            out.append(SpawnSpec(rng.choice(("freeze", "frenzy")), 60.0))
        elif self.mode != "sudden" and rng.random() < 0.07:
            out.append(SpawnSpec("pu_" + rng.choice(("slowmo", "double", "rain")), 60.0))
        return out

"""Combo, swipe bonus and power-up timers. Pure logic, no pygame."""
COMBO_MAX = 5
POWERUPS = {
    # kind: (duration seconds, label)
    "slowmo": (6.0, "Slow-Mo"),
    "double": (8.0, "Double Score"),
    "rain": (5.0, "Fruit Rain"),
}


class Combo:
    def __init__(self, window=0.9):
        self.window = window
        self.count = 0
        self.last = -1e9
        self.best = 0

    def hit(self, now):
        self.count = self.count + 1 if now - self.last <= self.window else 1
        self.last = now
        self.best = max(self.best, min(self.count, COMBO_MAX))
        return min(self.count, COMBO_MAX)

    def reset(self):
        self.count = 0
        self.last = -1e9

    def alive(self, now):
        return self.count > 1 and now - self.last <= self.window


def swipe_bonus(n):
    return 0 if n < 3 else 5 * (n - 2)


class PowerUps:
    def __init__(self):
        self.until = {}
        self.used = 0

    def activate(self, kind, now):
        self.until[kind] = now + POWERUPS[kind][0]
        self.used += 1

    def active(self, kind, now):
        return self.until.get(kind, 0) > now

    def remaining(self, kind, now):
        return max(0.0, self.until.get(kind, 0) - now)

    def score_mult(self, now):
        return 2 if self.active("double", now) else 1

    def time_scale(self, now):
        return 0.45 if self.active("slowmo", now) else 1.0

"""Bakes the cutting-board backdrops into assets/img/board_<name>.jpg. Run: python3 tools/boards.py [name ...]

Original procedural art (CC0). To use AI-generated boards instead, drop a 1000x650 JPG with the same
file name into assets/img/ - the game loads whatever file is there.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx  # noqa: E402  (sets up headless pygame and the shared noise helpers)
import pygame  # noqa: E402
from gfx import clamp, mix, smooth, vnoise  # noqa: E402

W, H = 1000, 650
GW, GH = 500, 325


def fbm(x, y, s=0, octaves=3):
    v, amp, f, tot = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        v += vnoise(x * f, y * f, s + o * 7) * amp
        tot += amp
        amp *= 0.5
        f *= 2.1
    return v / tot


def strips(u, v, n, seed, tones, grain, ring, warp, glue=0.55, knots=0):
    """Edge-grain board: n strips, each with its own tone and grain phase."""
    y = v * n
    k = min(n - 1, int(y))
    f = y - k
    rng_t = tones[(k * 7 + seed) % len(tones)]
    dark, light = rng_t
    ph = ((k * 131 + seed * 17) % 97) / 9.0
    x = u * 12.0
    w = fbm(x * 0.5, k * 3.1 + f * 1.2, seed + k) * warp
    g = (f * ring + w + ph)
    band = abs(math.sin(g * math.pi))
    fine = vnoise(x * 2.5, (k + f) * 70.0, seed + 5)
    t = clamp(band * 0.55 + fine * grain + fbm(x * 0.2, k * 2.0, seed) * 0.25)
    col = mix(dark, light, t)
    edge = min(f, 1 - f)
    if edge < 0.045:
        col = mix(col, (28, 14, 6), glue * (1 - edge / 0.045))
    elif edge < 0.09:
        col = mix(col, (255, 245, 225), 0.06 * (1 - (edge - 0.045) / 0.045))
    return col


def pine(u, v):
    tones = [((196, 148, 84), (238, 196, 128)), ((206, 160, 96), (244, 206, 140)), ((188, 140, 78), (232, 188, 120))]
    c = strips(u, v, 5, 1, tones, 0.22, 3.0, 1.8)
    knot = max(0.0, 1 - math.hypot((u - 0.68) * 10, (v - 0.31) * 10 * 0.65) / 0.55)
    knot2 = max(0.0, 1 - math.hypot((u - 0.22) * 10, (v - 0.76) * 10 * 0.65) / 0.45)
    return mix(c, (122, 78, 36), smooth(max(knot, knot2)) * 0.8)


def bamboo(u, v):
    tones = [((196, 170, 96), (236, 214, 142)), ((184, 160, 88), (226, 204, 132)), ((206, 180, 104), (244, 224, 154))]
    c = strips(u, v, 15, 3, tones, 0.12, 1.4, 0.7, glue=0.4)
    k = min(14, int(v * 15))
    for nx in (0.17 + (k * 37 % 11) / 40.0, 0.58 + (k * 53 % 13) / 45.0, 0.86):
        d = abs(u - nx)
        if d < 0.006:
            c = mix(c, (120, 90, 40), 0.55 * (1 - d / 0.006))
    return c


def walnut(u, v):
    tones = [((60, 34, 20), (112, 66, 38)), ((78, 44, 24), (138, 84, 48)), ((48, 26, 16), (96, 56, 32)),
             ((92, 56, 32), (160, 104, 62))]
    return strips(u, v, 9, 5, tones, 0.3, 4.2, 2.6, glue=0.7)


def marble(u, v):
    x, y = u * 10, v * 6.5
    w = fbm(x * 0.7, y * 0.7, 21, 4)
    base = mix((236, 236, 240), (206, 208, 218), fbm(x * 0.5, y * 0.5, 22))
    vein = abs(math.sin((x * 0.9 + y * 1.4 + w * 5.0) * math.pi * 0.5))
    vein = (1 - smooth(vein * 7)) * 0.85
    vein2 = abs(math.sin((x * -1.2 + y * 0.6 + w * 7.0 + 2) * math.pi * 0.5))
    vein2 = (1 - smooth(vein2 * 12)) * 0.5
    c = mix(base, (92, 98, 118), clamp(vein))
    c = mix(c, (150, 156, 176), clamp(vein2))
    return mix(c, (255, 255, 255), vnoise(x * 40, y * 40, 4) * 0.06)


def slate(u, v):
    x, y = u * 10, v * 6.5
    n = fbm(x * 1.4, y * 1.4, 31, 4)
    c = mix((38, 42, 50), (70, 76, 88), n)
    c = mix(c, (24, 26, 32), smooth(vnoise(x * 6, y * 0.8, 33) - 0.55) * 0.7)
    flake = vnoise(x * 70, y * 70, 35)
    if flake > 0.93:
        c = mix(c, (210, 216, 230), 0.5)
    w = fbm(x * 0.6, y * 0.6, 37, 3)
    gv = abs(math.sin((x * 0.5 - y * 1.1 + w * 4.0) * math.pi * 0.5))
    gold = (1 - smooth(gv * 14)) * 0.9
    return mix(c, (232, 188, 84), clamp(gold) * 0.85)


def gold(u, v):
    x, y = u * 10, v * 6.5
    diag = smooth(0.5 + 0.5 * math.sin((u * 1.1 + v * 0.8) * 6.0))
    base = mix((150, 98, 20), (255, 226, 130), diag * 0.8)
    streak = vnoise(x * 1.2, y * 90.0, 41)
    c = mix(base, (255, 240, 170), streak * 0.28)
    c = mix(c, (96, 58, 10), (1 - streak) * 0.18)
    lat = abs(math.sin(x * 6.0 + y * 6.0)) * abs(math.sin(x * 6.0 - y * 6.0))
    c = mix(c, (110, 70, 14), (1 - smooth(lat * 9)) * 0.3)
    glint = max(0.0, 1 - math.hypot(u - 0.3, (v - 0.25) * 0.9) / 0.35)
    return mix(c, (255, 255, 235), glint * glint * 0.45)


BOARDS = {
    "pine": (pine, (128, 82, 38)),
    "bamboo": (bamboo, (126, 98, 40)),
    "walnut": (walnut, (30, 16, 8)),
    "marble": (marble, (88, 92, 110)),
    "slate": (slate, (214, 170, 70)),
    "gold": (gold, (84, 50, 8)),
}


def vignette(strength):
    s = pygame.Surface((125, 82))
    for y in range(82):
        for x in range(125):
            d = math.hypot((x / 124 - 0.5) * 1.15, (y / 81 - 0.5) * 1.0) / 0.72
            k = 1 - strength * smooth((d - 0.45) / 0.75)
            c = int(255 * clamp(k))
            s.set_at((x, y), (c, c, c))
    return pygame.transform.smoothscale(s, (W, H))


def finish(img, groove, seed):
    """Light falloff, bevelled rim, juice groove, old knife scratches, vignette."""
    rng = random.Random(seed)
    img = img.convert()
    lit = pygame.Surface((125, 82))
    for y in range(82):
        for x in range(125):
            k = 1.1 - 0.28 * math.hypot(x / 124 - 0.3, y / 81 - 0.22)
            c = int(255 * clamp(k))
            lit.set_at((x, y), (c, c, c))
    img.blit(pygame.transform.smoothscale(lit, (W, H)), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(46):
        a = rng.uniform(-0.45, 0.45) if rng.random() < 0.7 else rng.uniform(1.0, 2.2)
        x0, y0 = rng.uniform(40, W - 40), rng.uniform(40, H - 40)
        ln = rng.uniform(40, 220)
        x1, y1 = x0 + math.cos(a) * ln, y0 + math.sin(a) * ln
        light = rng.random() < 0.55
        pygame.draw.line(ov, (255, 250, 240, 34) if light else (20, 10, 4, 40), (x0, y0), (x1, y1), 1)
    img.blit(ov, (0, 0))
    rim = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(rim, (0, 0, 0, 0), (0, 0, W, H))
    m = 34
    for i, (a, col) in enumerate(((120, (0, 0, 0)), (70, (0, 0, 0)), (40, (0, 0, 0)))):
        pygame.draw.rect(rim, (*col, a), (i, i, W - 2 * i, H - 2 * i), 2)
    pygame.draw.rect(rim, (255, 255, 255, 70), (m - 10, m - 10, W - 2 * (m - 10), H - 2 * (m - 10)), 2,
                     border_radius=26)
    pygame.draw.rect(rim, (*groove, 120), (m + 8, m + 8, W - 2 * (m + 8), H - 2 * (m + 8)), 7, border_radius=34)
    pygame.draw.rect(rim, (*groove, 200), (m + 11, m + 11, W - 2 * (m + 11), H - 2 * (m + 11)), 3, border_radius=31)
    pygame.draw.rect(rim, (255, 255, 255, 55), (m + 15, m + 15, W - 2 * (m + 15), H - 2 * (m + 15)), 1,
                     border_radius=28)
    img.blit(rim, (0, 0))
    img.blit(vignette(0.42), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return img


def bake(name):
    fn, groove = BOARDS[name]
    g = pygame.Surface((GW, GH))
    for y in range(GH):
        v = (y + 0.5) / GH
        for x in range(GW):
            c = fn((x + 0.5) / GW, v)
            g.set_at((x, y), (int(clamp(c[0], 0, 255)), int(clamp(c[1], 0, 255)), int(clamp(c[2], 0, 255))))
    img = pygame.transform.smoothscale(g, (W, H))
    img = finish(img, groove, hash(name) & 0xFFFF)
    out = os.path.join(gfx.OUT, f"board_{name}.jpg")
    pygame.image.save(img, out)
    print(name, os.path.getsize(out) // 1024, "KB", flush=True)


if __name__ == "__main__":
    for n in (sys.argv[1:] or BOARDS):
        bake(n)

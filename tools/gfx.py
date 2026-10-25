"""Generates every image in assets/img (original art, CC0). Run: python3 tools/gfx.py

Fruit are split into an albedo `body` (rotates in game) and a `light` overlay
(shadow + specular, stays fixed) so highlights stay put while fruit tumble: this is
what gives the 3D look at zero per-frame cost.
"""
import math
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "img")
os.makedirs(OUT, exist_ok=True)
LIGHT = (-0.45, -0.6, 0.66)
_ln = math.sqrt(sum(v * v for v in LIGHT))
LIGHT = tuple(v / _ln for v in LIGHT)
HALF = (LIGHT[0], LIGHT[1], LIGHT[2] + 1)
_hn = math.sqrt(sum(v * v for v in HALF))
HALF = tuple(v / _hn for v in HALF)


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def h2(x, y, s=0):
    return (math.sin(x * 127.1 + y * 311.7 + s * 74.7) * 43758.5453) % 1.0


def vnoise(x, y, s=0):
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = smooth(x - xi), smooth(y - yi)
    a, b = h2(xi, yi, s), h2(xi + 1, yi, s)
    c, d = h2(xi, yi + 1, s), h2(xi + 1, yi + 1, s)
    top = a + (b - a) * fx
    bot = c + (d - c) * fx
    return top + (bot - top) * fy


def save(surf, name):
    pygame.image.save(surf, os.path.join(OUT, name))


# ------------------------------------------------------------------ spheres
def sphere(r, albedo, ambient=0.34, spec=0.8, shin=34, rim=(255, 255, 255), rim_k=0.22,
           bounce=(255, 170, 90)):
    """Returns (body, light). body = albedo only; light = shade + highlight overlay."""
    S = 2 * r + 8
    c = S / 2
    body = pygame.Surface((S, S), pygame.SRCALPHA)
    light = pygame.Surface((S, S), pygame.SRCALPHA)
    for y in range(S):
        for x in range(S):
            dx, dy = (x + 0.5 - c) / r, (y + 0.5 - c) / r
            d2 = dx * dx + dy * dy
            dist = math.sqrt(d2)
            a = clamp((1.0 - dist) * r + 0.5)
            if a <= 0:
                continue
            nz = math.sqrt(max(0.0, 1 - d2))
            if dist > 1:
                dx, dy, dist = dx / dist, dy / dist, 1.0
            base = albedo(dx, dy, nz)
            diff = max(0.0, dx * LIGHT[0] + dy * LIGHT[1] + nz * LIGHT[2])
            bn = max(0.0, dx * 0.55 + dy * 0.65 + nz * 0.15)
            shade = ambient + (1 - ambient) * diff
            rimf = (1 - nz) ** 3
            col = [base[i] * (1.0 + 0.10 * bn * bounce[i] / 255) + rim[i] * rimf * rim_k * 0.6 for i in range(3)]
            body.set_at((x, y), (int(clamp(col[0], 0, 255)), int(clamp(col[1], 0, 255)),
                                 int(clamp(col[2], 0, 255)), int(a * 255)))
            s_alpha = clamp((1 - shade) * 0.92)
            sp = (max(0.0, dx * HALF[0] + dy * HALF[1] + nz * HALF[2]) ** shin) * spec
            sp += max(0.0, diff - 0.7) * 0.25 * spec
            sp = clamp(sp)
            A = 1 - (1 - s_alpha) * (1 - sp)
            if A <= 0.004:
                continue
            k = sp / A
            lc = int(255 * k)
            light.set_at((x, y), (lc, lc, lc, int(A * a * 255)))
    return body, light


def finish(name, body, light):
    save(body, f"{name}_body.png")
    save(light, f"{name}_light.png")


def fruit_albedos():
    def watermelon(dx, dy, nz):
        lon = math.atan2(dx, nz + 0.0001)
        s = math.sin(lon * 7.5 + 2.4 * vnoise(dx * 3, dy * 3) + dy * 0.9)
        t = smooth((s + 0.25) * 2.2)
        base = mix((118, 205, 88), (24, 104, 44), t)
        n = vnoise(dx * 14, dy * 14, 3) * 0.14
        return tuple(v * (0.92 + n) for v in base)

    def orange(dx, dy, nz):
        n = vnoise(dx * 38, dy * 38, 1)
        base = mix((255, 150, 24), (240, 112, 8), vnoise(dx * 4, dy * 4))
        return tuple(v * (0.9 + 0.16 * n) for v in base)

    def apple(dx, dy, nz):
        streak = vnoise(dx * 7, dy * 1.5, 5)
        base = mix((205, 22, 34), (240, 90, 40), smooth(streak * 1.6 - 0.5))
        base = mix(base, (130, 8, 20), smooth(-dy * 1.6 - 0.9) * 0.9)
        base = mix(base, (240, 200, 70), smooth(dy * 1.3 - 0.35) * 0.35)
        return base

    def kiwi(dx, dy, nz):
        n = vnoise(dx * 55, dy * 55, 2)
        base = mix((150, 108, 58), (112, 76, 38), n)
        return tuple(v * (0.92 + 0.12 * vnoise(dx * 9, dy * 9)) for v in base)

    def lemon(dx, dy, nz):
        n = vnoise(dx * 40, dy * 40, 4)
        base = mix((252, 232, 52), (240, 205, 28), vnoise(dx * 3, dy * 3))
        return tuple(v * (0.92 + 0.14 * n) for v in base)

    def plum(dx, dy, nz):
        base = mix((92, 32, 138), (60, 18, 98), smooth(dy + 0.2))
        bloom = vnoise(dx * 6, dy * 6, 8)
        base = mix(base, (170, 160, 210), 0.22 * smooth(bloom * 1.5 - 0.5))
        crease = math.exp(-((dx - 0.1) ** 2) * 120) * (1 if dy > -0.8 else 0)
        return mix(base, (40, 10, 70), crease * 0.55)

    return {"watermelon": watermelon, "orange": orange, "apple": apple, "kiwi": kiwi,
            "lemon": lemon, "plum": plum}


FRUITS = {"watermelon": 50, "orange": 40, "apple": 38, "kiwi": 36, "lemon": 36, "plum": 34}


def decorate(name, body, r):
    c = body.get_width() // 2
    if name == "apple":
        pygame.draw.line(body, (96, 58, 22), (c, c - r + 6), (c + 5, c - r - 5), 4)
        leaf = pygame.Surface((26, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(leaf, (70, 180, 60), (0, 0, 26, 14))
        pygame.draw.line(leaf, (40, 120, 40), (2, 7), (24, 7), 1)
        body.blit(pygame.transform.rotate(leaf, 25), (c + 3, c - r - 12))
    if name == "orange":
        pygame.draw.circle(body, (60, 130, 40), (c, c - r + 7), 4)
        pygame.draw.circle(body, (90, 170, 60), (c, c - r + 7), 2)
    if name == "plum":
        pygame.draw.line(body, (90, 60, 30), (c, c - r + 5), (c - 2, c - r - 4), 3)
    if name == "lemon":
        pygame.draw.circle(body, (225, 190, 20), (c + r - 5, c - 3), 5)
        pygame.draw.circle(body, (225, 190, 20), (c - r + 5, c + 3), 5)


# -------------------------------------------------------------- cross sections
SECTION = {
    # skin, rim(pith), flesh centre, flesh edge, seed
    "watermelon": ((40, 140, 50), (200, 238, 160), (255, 120, 135), (226, 40, 70), (25, 25, 25)),
    "orange": ((255, 140, 20), (255, 232, 170), (255, 200, 80), (255, 150, 30), None),
    "apple": ((205, 25, 36), (252, 250, 215), (255, 252, 226), (246, 238, 190), (90, 50, 20)),
    "kiwi": ((140, 100, 50), (214, 238, 150), (200, 240, 140), (92, 180, 40), (20, 20, 20)),
    "lemon": ((250, 226, 50), (255, 250, 200), (255, 250, 170), (252, 232, 80), None),
    "plum": ((100, 34, 140), (250, 220, 130), (255, 206, 90), (232, 140, 30), None),
}


def section(name, r):
    skin, rim, f0, f1, seed = SECTION[name]
    S = 2 * r + 8
    c = S / 2
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    for y in range(S):
        for x in range(S):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            d = math.hypot(dx, dy)
            a = clamp(r - d + 0.5)
            if a <= 0:
                continue
            t = d / r
            if t > 0.955:
                col = skin
            elif t > 0.9:
                col = mix(skin, rim, smooth((0.955 - t) / 0.05))
            elif t > 0.83:
                col = rim
            else:
                u = t / 0.83
                col = mix(f0, f1, smooth(u) ** 1.2)
                ang = math.atan2(dy, dx)
                if name in ("watermelon", "kiwi"):
                    col = mix(col, (255, 255, 255), 0.10 * abs(math.sin(ang * 14 + vnoise(ang * 3, u * 4) * 6)))
                if name == "kiwi":
                    col = mix(col, (245, 252, 215), smooth(0.28 - u))
                if name in ("orange", "lemon"):
                    seg = abs(math.sin(ang * 4.0))
                    col = mix(col, rim, (1 - smooth(seg * 8)) * 0.75)
                    col = mix(col, (255, 255, 235), 0.14 * vnoise(ang * 5, u * 9))
                if name == "apple":
                    col = mix(col, (230, 215, 150), smooth(u - 0.7) * 0.3)
            sh = 1 - 0.18 * clamp((dx * 0.5 + dy * 0.6) / r + 0.4)
            s.set_at((x, y), (int(col[0] * sh), int(col[1] * sh), int(col[2] * sh), int(a * 255)))
    ci = int(c)
    if seed:
        n = 4 if name == "apple" else 10
        rad = r * (0.18 if name == "apple" else 0.5)
        for k in range(n):
            ang = k * 2 * math.pi / n + (0.4 if name == "watermelon" else 0)
            ring = rad * (1 if k % 2 == 0 or name != "watermelon" else 0.68)
            x, y = ci + math.cos(ang) * ring, ci + math.sin(ang) * ring
            e = pygame.Surface((8, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(e, seed, (0, 0, 7, 12))
            pygame.draw.ellipse(e, (255, 255, 255, 90), (1, 1, 2, 4))
            e = pygame.transform.rotate(e, -math.degrees(ang) + 90)
            s.blit(e, e.get_rect(center=(x, y)))
    if name == "plum":
        pit = pygame.Surface((20, 28), pygame.SRCALPHA)
        pygame.draw.ellipse(pit, (150, 92, 44), (0, 0, 20, 28))
        pygame.draw.ellipse(pit, (190, 130, 80), (4, 4, 7, 10))
        s.blit(pit, pit.get_rect(center=(ci, ci)))
    gl = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.ellipse(gl, (255, 255, 255, 70), (c - r * 0.62, c - r * 0.68, r * 0.7, r * 0.3))
    s.blit(gl, (0, 0))
    left = s.copy()
    left.fill((0, 0, 0, 0), (ci, 0, S, S))
    right = s.copy()
    right.fill((0, 0, 0, 0), (0, 0, ci, S))
    return left, right


# --------------------------------------------------------------------- others
def bomb():
    r = 36

    def alb(dx, dy, nz):
        v = 34 + 16 * vnoise(dx * 8, dy * 8)
        return (v, v, v + 8)

    body, light = sphere(r, alb, ambient=0.3, spec=0.95, shin=40, rim=(120, 150, 255), rim_k=0.5)
    S = body.get_width()
    out = pygame.Surface((S, S + 30), pygame.SRCALPHA)
    out.blit(body, (0, 30))
    lo = pygame.Surface((S, S + 30), pygame.SRCALPHA)
    lo.blit(light, (0, 30))
    c = S // 2
    pygame.draw.rect(out, (80, 82, 96), (c - 10, 30 + c - r - 7, 20, 11), border_radius=3)
    pygame.draw.line(out, (210, 160, 80), (c, 30 + c - r - 6), (c + 10, 30 + c - r - 22), 4)
    for w, col in ((6, (255, 120, 40)), (3, (255, 240, 160))):
        pygame.draw.circle(out, col, (c + 10, 30 + c - r - 24), w)
    cy = 30 + c + 6
    for a in ((-13, -10, 13, 12), (13, -10, -13, 12)):
        pygame.draw.line(out, (225, 40, 44), (c + a[0], cy + a[1]), (c + a[2], cy + a[3]), 6)
    finish("bomb", out, lo)


def orb(name, col_a, col_b, glyph):
    r = 36

    def alb(dx, dy, nz):
        return mix(col_b, col_a, smooth(1 - math.hypot(dx + 0.2, dy + 0.2)))

    body, light = sphere(r, alb, ambient=0.5, spec=1.0, shin=30, rim=(255, 255, 255), rim_k=0.9)
    glyph(body, body.get_width() // 2)
    pygame.draw.circle(body, (255, 255, 255), (body.get_width() // 2,) * 2, r, 3)
    finish(name, body, light)


def glyph_clock(s, c):
    pygame.draw.circle(s, (255, 255, 255), (c, c), 17, 3)
    pygame.draw.line(s, (255, 255, 255), (c, c), (c, c - 12), 3)
    pygame.draw.line(s, (255, 255, 255), (c, c), (c + 9, c + 4), 3)


def glyph_double(s, c):
    f = pygame.font.SysFont("arialrounded,arialblack,arial", 30, bold=True)
    t = f.render("x2", True, (255, 255, 255))
    s.blit(t, t.get_rect(center=(c, c)))


def glyph_rain(s, c):
    for dx in (-12, 0, 12):
        pygame.draw.polygon(s, (255, 255, 255), [(c + dx, c + 12), (c + dx - 5, c + 2), (c + dx + 5, c + 2)])
        pygame.draw.line(s, (255, 255, 255), (c + dx, c - 12 + abs(dx) // 3), (c + dx, c + 2), 3)


def glyph_ice(s, c):
    for k in range(3):
        a = k * math.pi / 3
        dx, dy = math.cos(a) * 18, math.sin(a) * 18
        pygame.draw.line(s, (255, 255, 255), (c - dx, c - dy), (c + dx, c + dy), 3)


def glyph_bolt(s, c):
    pts = [(c + 4, c - 18), (c - 10, c + 2), (c - 1, c + 2), (c - 5, c + 18), (c + 11, c - 4), (c + 2, c - 4)]
    pygame.draw.polygon(s, (255, 255, 255), pts)


def glow(size, col, name):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    for y in range(size):
        for x in range(size):
            d = math.hypot(x + 0.5 - c, y + 0.5 - c) / c
            if d < 1:
                s.set_at((x, y), (*col, int(255 * (1 - d) ** 2.2)))
    save(s, name)


def splats():
    rng = random.Random(7)
    for i in range(4):
        S = 120
        s = pygame.Surface((S, S), pygame.SRCALPHA)
        c = S // 2
        pygame.draw.circle(s, (255, 255, 255, 235), (c, c), rng.randint(16, 24))
        for _ in range(11):
            a = rng.uniform(0, 6.283)
            d = rng.uniform(14, 40)
            pygame.draw.circle(s, (255, 255, 255, 220), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)),
                               rng.randint(4, 12))
        for _ in range(7):
            a = rng.uniform(0, 6.283)
            ln = rng.uniform(34, 54)
            pygame.draw.line(s, (255, 255, 255, 220), (c, c), (c + math.cos(a) * ln, c + math.sin(a) * ln),
                             rng.randint(3, 6))
        for _ in range(8):
            a = rng.uniform(0, 6.283)
            d = rng.uniform(44, 58)
            pygame.draw.circle(s, (255, 255, 255, 200), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)),
                               rng.randint(1, 3))
        save(s, f"splat_{i}.png")


def cloud():
    s = pygame.Surface((260, 110), pygame.SRCALPHA)
    for cx, cy, rr in ((60, 70, 34), (110, 52, 42), (165, 60, 38), (205, 76, 28), (130, 78, 36)):
        for k in range(rr, 0, -2):
            pygame.draw.circle(s, (255, 255, 255, int(16 + 20 * (1 - k / rr))), (cx, cy), k)
    save(s, "cloud.png")


def petal(name, col):
    s = pygame.Surface((22, 22), pygame.SRCALPHA)
    pygame.draw.ellipse(s, col, (2, 6, 18, 10))
    pygame.draw.ellipse(s, (255, 255, 255, 90), (5, 8, 8, 3))
    save(s, name)


THEMES = {
    # sky top, sky bottom, far hills, near hills, sun/moon colour, sun pos
    "orchard": ((70, 170, 255), (255, 240, 190), (90, 170, 120), (46, 120, 70), (255, 245, 170), (780, 150)),
    "dusk": ((70, 40, 120), (255, 150, 90), (150, 70, 110), (78, 34, 80), (255, 210, 120), (240, 330)),
    "night": ((8, 12, 40), (44, 60, 120), (30, 44, 90), (14, 22, 56), (235, 240, 255), (800, 120)),
    "sakura": ((255, 170, 200), (255, 232, 238), (230, 140, 170), (176, 88, 130), (255, 250, 235), (200, 140)),
}


def background(name):
    top, bot, far, near, sun, (sx, sy) = THEMES[name]
    W, H = 1000, 650
    sky = pygame.Surface((W, H))
    for y in range(H):
        sky.fill(mix(top, bot, smooth(y / H * 1.1)), (0, y, W, 1))
    glow_s = pygame.Surface((W, H), pygame.SRCALPHA)
    for rr in range(220, 0, -4):
        pygame.draw.circle(glow_s, (*sun, int(70 * (1 - rr / 220) ** 2)), (sx, sy), rr)
    pygame.draw.circle(glow_s, (*sun, 255), (sx, sy), 46 if name != "night" else 36)
    sky.blit(glow_s, (0, 0))
    if name == "night":
        rng = random.Random(5)
        for _ in range(110):
            x, y = rng.randint(0, W), rng.randint(0, 330)
            v = rng.randint(130, 255)
            pygame.draw.circle(sky, (v, v, 255), (x, y), rng.choice((1, 1, 2)))
    pygame.image.save(sky, os.path.join(OUT, f"bg_{name}_sky.jpg"))
    # periodic hill layers so they scroll seamlessly (two tiles side by side at runtime)
    for lname, col, base, amp, k in (("far", far, 400, 55, 2), ("near", near, 500, 40, 3)):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for x in range(W):
            ph = x / W * 2 * math.pi
            y = base + amp * math.sin(ph * k + 1.0) + amp * 0.45 * math.sin(ph * (k * 2 + 1) + 2.0)
            pygame.draw.line(s, (*col, 255), (x, int(y)), (x, H))
        save(s, f"bg_{name}_{lname}.png")


def logo():
    font = pygame.font.SysFont("arialrounded,arialroundedmtbold,trebuchetms,verdana", 120, bold=True)
    parts = (("Fruit", (255, 226, 80), (255, 140, 20)), ("Slash", (255, 110, 90), (214, 28, 70)))
    pieces = []
    for text, c0, c1 in parts:
        m = font.render(text, True, (255, 255, 255))
        grad = pygame.Surface(m.get_size(), pygame.SRCALPHA)
        for y in range(m.get_height()):
            grad.fill((*mix(c0, c1, y / m.get_height()), 255), (0, y, m.get_width(), 1))
        grad.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        pieces.append((m, grad))
    gap = 18
    W = sum(p[0].get_width() for p in pieces) + gap + 40
    H = pieces[0][0].get_height() + 40
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    x = 20
    for m, grad in pieces:
        dark = m.copy()
        dark.fill((70, 20, 10, 255), special_flags=pygame.BLEND_RGBA_MULT)
        for ang in range(0, 360, 20):
            ox, oy = math.cos(math.radians(ang)) * 6, math.sin(math.radians(ang)) * 6
            out.blit(dark, (x + ox, 20 + oy))
        out.blit(dark, (x + 2, 28))
        out.blit(grad, (x, 20))
        x += m.get_width() + gap
    save(out, "logo.png")


def main():
    albs = fruit_albedos()
    for name, r in FRUITS.items():
        soft = name in ("kiwi", "orange", "lemon")
        body, light = sphere(r, albs[name], spec=0.55 if soft else 0.85, shin=26 if soft else 36)
        decorate(name, body, r)
        finish(f"fruit_{name}", body, light)
        left, right = section(name, r)
        save(left, f"fruit_{name}_L.png")
        save(right, f"fruit_{name}_R.png")
        print("fruit", name, flush=True)
    body, light = sphere(112, albs["watermelon"], spec=0.9, shin=34)
    finish("boss", body, light)
    bl, br = section("watermelon", 112)
    save(bl, "boss_L.png")
    save(br, "boss_R.png")
    bomb()
    orb("pu_slowmo", (150, 220, 255), (30, 110, 220), glyph_clock)
    orb("pu_double", (255, 235, 120), (230, 130, 10), glyph_double)
    orb("pu_rain", (170, 255, 150), (20, 160, 80), glyph_rain)
    orb("freeze", (200, 245, 255), (60, 150, 240), glyph_ice)
    orb("frenzy", (255, 220, 100), (240, 60, 40), glyph_bolt)
    glow(96, (255, 255, 255), "glow.png")
    splats()
    cloud()
    petal("petal.png", (255, 170, 200, 255))
    petal("leaf.png", (120, 200, 80, 255))
    for t in THEMES:
        background(t)
    logo()
    print("done")


if __name__ == "__main__":
    main()

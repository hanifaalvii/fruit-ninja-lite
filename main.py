"""Fruit Slash - a Fruit Ninja style game in Python (pygame).

Desktop:  pip install pygame-ce  &&  python main.py
Web/phone: built with pygbag (see README.md).
Swipe with mouse or finger to slice fruit.  ESC = pause, M = mute, F = fullscreen.
All sounds are synthesised at start-up, so no asset files are needed.
"""
import array
import asyncio
import json
import math
import os
import random
import sys
from collections import deque

import pygame

import leaderboard

WEB = sys.platform == "emscripten"
if WEB:
    import platform

W, H = 1000, 650
PANEL_W, PANEL_H, PANEL_Y, PEEK = 340, 190, 200, 64
SHORT = {"classic": "Classic", "arcade": "Arcade", "zen": "Zen", "sudden": "Sudden"}
FPS = 60
SR = 16000
SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")

MODES = {
    "classic": ("Classic", ["3 lives", "avoid bombs"]),
    "arcade": ("Arcade", ["60 seconds", "Freeze & Frenzy"]),
    "zen": ("Zen", ["90 seconds", "no bombs"]),
    "sudden": ("Sudden Death", ["1 life", "speed keeps rising"]),
}


def mkfont(size):
    if not WEB:
        try:
            return pygame.font.SysFont("arialrounded,trebuchetms,verdana,arial", size, bold=True)
        except Exception:
            pass
    return pygame.font.Font(None, int(size * 1.3))


def store_load():
    try:
        if WEB:
            raw = platform.window.localStorage.getItem("fruitslash")
            return json.loads(raw) if raw else {}
        with open(SAVE) as f:
            return json.load(f)
    except Exception:
        return {}


def store_save(data):
    try:
        if WEB:
            platform.window.localStorage.setItem("fruitslash", json.dumps(data))
        else:
            with open(SAVE, "w") as f:
                json.dump(data, f)
    except Exception:
        pass

# name: (skin, flesh, rim, radius, seed colour)
FRUITS = {
    "watermelon": ((40, 140, 50), (235, 60, 80), (190, 235, 150), 50, (20, 20, 20)),
    "orange": ((255, 150, 20), (255, 190, 60), (255, 225, 150), 40, None),
    "apple": ((210, 30, 40), (250, 245, 200), (255, 255, 235), 38, (90, 50, 20)),
    "kiwi": ((140, 100, 50), (140, 210, 60), (210, 240, 140), 36, (20, 20, 20)),
    "lemon": ((250, 230, 50), (255, 245, 140), (255, 250, 200), 36, None),
    "plum": ((110, 40, 150), (230, 170, 60), (250, 215, 130), 34, None),
}


# ----------------------------------------------------------------- synthesis
def buf(dur):
    return [0.0] * int(dur * SR)


def tone(b, start, dur, f0, vol, wave="sine", f1=None, attack=0.005, curve=3.0):
    s0 = int(start * SR)
    n = int(dur * SR)
    ph = 0.0
    for i in range(n):
        if s0 + i >= len(b):
            break
        t = i / n
        f = f0 if f1 is None else f0 + (f1 - f0) * t
        ph += f / SR
        p = ph % 1.0
        if wave == "sine":
            v = math.sin(2 * math.pi * p)
        elif wave == "tri":
            v = 4 * abs(p - 0.5) - 1
        elif wave == "square":
            v = 1.0 if p < 0.5 else -1.0
        else:
            v = 2 * p - 1
        a = min(1.0, i / max(1, attack * SR))
        b[s0 + i] += v * vol * a * (1 - t) ** curve


def noise(b, start, dur, vol, lp=0.3, curve=2.0, sweep=None, rng=random):
    s0 = int(start * SR)
    n = int(dur * SR)
    y = 0.0
    for i in range(n):
        if s0 + i >= len(b):
            break
        t = i / n
        k = lp if sweep is None else lp + (sweep - lp) * t
        y += k * (rng.uniform(-1, 1) - y)
        b[s0 + i] += y * vol * min(1.0, i / 80) * (1 - t) ** curve


def to_sound(b):
    out = array.array("h", (int(max(-1.0, min(1.0, v)) * 30000) for v in b))
    return pygame.mixer.Sound(buffer=out.tobytes())


def make_swoosh():
    b = buf(0.28)
    noise(b, 0, 0.28, 0.5, lp=0.05, sweep=0.5, curve=1.2)
    return to_sound(b)


def make_slice():
    b = buf(0.3)
    noise(b, 0, 0.12, 0.8, lp=0.7, curve=2)
    tone(b, 0, 0.18, 900, 0.3, "tri", f1=300)
    noise(b, 0.02, 0.28, 0.5, lp=0.15, curve=3)
    return to_sound(b)


def make_splat():
    b = buf(0.25)
    noise(b, 0, 0.25, 0.7, lp=0.12, curve=3)
    tone(b, 0, 0.15, 220, 0.5, "sine", f1=70)
    return to_sound(b)


def make_bomb():
    b = buf(1.0)
    noise(b, 0, 1.0, 1.0, lp=0.25, sweep=0.02, curve=1.6)
    tone(b, 0, 0.8, 110, 0.9, "sine", f1=30, curve=1.5)
    return to_sound(b)


def make_combo():
    b = buf(0.5)
    for i, f in enumerate((660, 880, 1320)):
        tone(b, i * 0.07, 0.3, f, 0.3, "tri")
    return to_sound(b)


def make_miss():
    b = buf(0.4)
    tone(b, 0, 0.4, 330, 0.5, "square", f1=110)
    return to_sound(b)


def make_over():
    b = buf(1.2)
    for i, f in enumerate((392, 330, 262, 196)):
        tone(b, i * 0.25, 0.4, f, 0.45, "tri")
    return to_sound(b)


def make_click():
    b = buf(0.1)
    tone(b, 0, 0.08, 700, 0.4, "square", f1=500)
    return to_sound(b)


def make_freeze():
    b = buf(0.8)
    for i in range(6):
        tone(b, i * 0.05, 0.4, 2000 - i * 200, 0.15, "sine")
    noise(b, 0, 0.5, 0.3, lp=0.8, curve=3)
    return to_sound(b)


def make_frenzy():
    b = buf(0.7)
    for i, f in enumerate((523, 659, 784, 1046, 1318)):
        tone(b, i * 0.07, 0.3, f, 0.3, "square", curve=2)
    return to_sound(b)


def make_music(bpm, lead_wave, lead_vol, drums, seed):
    rng = random.Random(seed)
    step = 60.0 / bpm / 2
    bars = 8
    total = bars * 8 * step
    b = buf(total)
    # Am F C G, two bars each
    roots = [220.0, 174.61, 261.63, 196.0]
    scale = [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3]
    for bar in range(bars):
        root = roots[(bar // 2) % 4]
        for s in range(8):
            t = (bar * 8 + s) * step
            if s % 4 == 0:
                tone(b, t, step * 3.5, root / 2, 0.22, "tri", curve=1.2)
            if rng.random() < 0.75:
                f = root * 2 * rng.choice(scale)
                tone(b, t, step * rng.choice((1, 1.5, 2)), f, lead_vol, lead_wave, curve=2)
            if drums:
                if s % 4 == 0:
                    tone(b, t, 0.14, 140, 0.5, "sine", f1=45)
                if s % 2 == 1:
                    noise(b, t, 0.05, 0.14, lp=0.9, curve=2, rng=rng)
                if s % 4 == 2:
                    noise(b, t, 0.1, 0.18, lp=0.5, curve=2, rng=rng)
    return to_sound(b)


# ------------------------------------------------------------------- sprites
def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build_fruit(name):
    skin, flesh, rim, r, seed = FRUITS[name]
    S = r * 2 + 4
    c = S // 2
    whole = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(r, 0, -2):
        pygame.draw.circle(whole, lerp_col(skin, (255, 255, 255), 0.25 * (1 - i / r)) if False
                           else lerp_col(tuple(int(v * 0.65) for v in skin), skin, 1 - i / r * 0.6),
                           (c - (r - i) // 4, c - (r - i) // 4), i)
    pygame.draw.circle(whole, tuple(int(v * 0.5) for v in skin), (c, c), r, 2)
    hl = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.ellipse(hl, (255, 255, 255, 110), (c - r * 0.6, c - r * 0.7, r * 0.55, r * 0.35))
    whole.blit(hl, (0, 0))
    if name == "apple":
        pygame.draw.line(whole, (90, 55, 20), (c, c - r + 4), (c + 4, c - r - 2), 3)
        pygame.draw.ellipse(whole, (60, 170, 60), (c + 3, c - r - 3, 12, 6))
    if name == "watermelon":
        for k in range(-3, 4):
            pygame.draw.line(whole, (20, 90, 30), (c + k * r // 4, c - r + abs(k) * 5),
                             (c + k * r // 4, c + r - abs(k) * 5), 3)
    if name == "orange":
        for _ in range(20):
            a = random.random() * 6.28
            d = random.random() * r * 0.8
            pygame.draw.circle(whole, (230, 120, 10), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), 1)

    # flesh disc used for the two halves
    cut = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(cut, skin, (c, c), r)
    pygame.draw.circle(cut, rim, (c, c), r - 4)
    pygame.draw.circle(cut, flesh, (c, c), r - 8)
    if name in ("watermelon", "kiwi", "apple"):
        n = 8 if name != "apple" else 4
        for k in range(n):
            a = k * 6.283 / n
            d = r * (0.45 if name != "apple" else 0.2)
            x, y = c + math.cos(a) * d, c + math.sin(a) * d
            pygame.draw.ellipse(cut, seed, (x - 2, y - 3, 4, 6))
    if name in ("orange", "lemon"):
        for k in range(8):
            a = k * 6.283 / 8
            pygame.draw.line(cut, rim, (c, c), (c + math.cos(a) * (r - 9), c + math.sin(a) * (r - 9)), 2)
    if name == "kiwi":
        pygame.draw.circle(cut, (240, 250, 200), (c, c), r // 4)
    if name == "plum":
        pygame.draw.ellipse(cut, (150, 90, 40), (c - 7, c - 10, 14, 20))
    left = cut.copy()
    left.fill((0, 0, 0, 0), (c, 0, S, S))
    right = cut.copy()
    right.fill((0, 0, 0, 0), (0, 0, c, S))
    return whole, left, right, r


def build_bomb():
    r = 34
    S = r * 2 + 30
    c = S // 2
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(r, 0, -2):
        v = int(15 + (1 - i / r) * 50)
        pygame.draw.circle(s, (v, v, v + 6), (c - (r - i) // 3, c + 6 - (r - i) // 3), i)
    pygame.draw.circle(s, (200, 200, 200), (c, c + 6), r, 2)
    pygame.draw.rect(s, (70, 70, 80), (c - 8, c + 6 - r - 8, 16, 10))
    pygame.draw.line(s, (200, 150, 70), (c, c + 6 - r - 8), (c + 12, c - r - 16), 3)
    pygame.draw.circle(s, (255, 90, 60), (c + 12, c - r - 16), 5)
    pygame.draw.line(s, (230, 40, 40), (c - 12, c - 2), (c + 12, c + 22), 5)
    pygame.draw.line(s, (230, 40, 40), (c + 12, c - 2), (c - 12, c + 22), 5)
    return s, r


def build_special(kind, font):
    r = 38
    S = r * 2 + 4
    c = S // 2
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    cols = {"freeze": ((90, 190, 255), (210, 245, 255)), "frenzy": ((255, 190, 20), (255, 245, 150))}[kind]
    for i in range(r, 0, -2):
        pygame.draw.circle(s, lerp_col(cols[0], cols[1], 1 - i / r), (c, c), i)
    pygame.draw.circle(s, (255, 255, 255), (c, c), r, 3)
    t = font.render("ICE" if kind == "freeze" else "x2", True, (20, 60, 110) if kind == "freeze" else (130, 60, 0))
    s.blit(t, t.get_rect(center=(c, c)))
    return s, r


def build_background():
    bg = pygame.Surface((W, H))
    for y in range(H):
        bg.fill(lerp_col((92, 58, 30), (46, 26, 12), y / H), (0, y, W, 1))
    rng = random.Random(3)
    for x in range(0, W, 125):
        pygame.draw.line(bg, (30, 16, 6), (x, 0), (x, H), 3)
        for _ in range(14):
            y = rng.randrange(H)
            pygame.draw.line(bg, (110, 72, 40), (x + rng.randrange(8, 118), y), (x + rng.randrange(8, 118), y + 40), 1)
    vig = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(60):
        pygame.draw.rect(vig, (0, 0, 0, 3), (i, i, W - 2 * i, H - 2 * i), 1)
    bg.blit(vig, (0, 0))
    return bg


# ----------------------------------------------------------------- game bits
class Item:
    def __init__(self, kind, spr, r, x, y, vx, vy, rot_speed, name=None):
        self.kind, self.spr, self.r, self.name = kind, spr, r, name
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.rot, self.vrot = random.uniform(0, 360), rot_speed
        self.alive = True
        self.fade = None

    def update(self, dt, g):
        self.vy += g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.vrot * dt

    def draw(self, surf):
        img = pygame.transform.rotate(self.spr, self.rot)
        if self.fade is not None:
            img.set_alpha(max(0, int(255 * self.fade)))
        surf.blit(img, img.get_rect(center=(self.x, self.y)))


class Slider:
    def __init__(self, label, x, y, w, value):
        self.label, self.rect, self.value, self.drag = label, pygame.Rect(x, y, w, 10), value, False

    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.inflate(30, 40).collidepoint(e.pos):
            self.drag = True
        if e.type == pygame.MOUSEBUTTONUP:
            self.drag = False
        if self.drag and e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            self.value = min(1.0, max(0.0, (e.pos[0] - self.rect.x) / self.rect.w))
            return True
        return False

    def draw(self, surf, font):
        t = font.render(self.label, True, (255, 255, 255))
        surf.blit(t, (self.rect.x - t.get_width() - 20, self.rect.centery - t.get_height() // 2))
        pygame.draw.rect(surf, (40, 20, 8), self.rect, border_radius=5)
        pygame.draw.rect(surf, (155, 227, 74), (self.rect.x, self.rect.y, self.rect.w * self.value, 10), border_radius=5)
        pygame.draw.circle(surf, (255, 210, 74), (int(self.rect.x + self.rect.w * self.value), self.rect.centery), 13)


class Button:
    def __init__(self, text, cx, cy, cb, w=240, h=52, col=(200, 50, 26)):
        self.text, self.cb, self.col = text, cb, col
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (cx, cy)

    def draw(self, surf, font, mouse):
        r = self.rect.copy()
        hov = r.collidepoint(mouse)
        pygame.draw.rect(surf, (90, 20, 8), r.move(0, 4), border_radius=26)
        pygame.draw.rect(surf, lerp_col(self.col, (255, 255, 255), 0.2 if hov else 0), r, border_radius=26)
        pygame.draw.rect(surf, (255, 210, 74), r, 3, border_radius=26)
        t = font.render(self.text, True, (255, 255, 255))
        surf.blit(t, t.get_rect(center=r.center))


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


NAME_JS = """
(function(){
var old=document.getElementById('nm_ov'); if(old) old.remove();
window.__nm=undefined;
var first=__FIRST__==1, cur=__CUR__;
var ov=document.createElement('div'); ov.id='nm_ov';
ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.65);display:flex;align-items:center;justify-content:center;z-index:99999;font-family:sans-serif';
ov.innerHTML='<div style="background:#2b1d12;border:3px solid #ffb347;border-radius:18px;padding:22px 26px;width:min(86vw,360px);text-align:center;color:#fff">'
+'<div style="font-size:22px;font-weight:bold;color:#ffb347">Enter your nickname</div>'
+'<div style="font-size:14px;margin:8px 0 14px;opacity:.85">Do NOT use your real name.<br>It shows on the public leaderboard.</div>'
+'<input id="nm_in" maxlength="12" autocomplete="off" placeholder="Nickname" style="width:100%;box-sizing:border-box;font-size:20px;padding:10px;border-radius:10px;border:2px solid #ffb347;text-align:center">'
+'<button id="nm_ok" style="margin-top:14px;font-size:20px;padding:10px 28px;border:0;border-radius:12px;background:#ff7a1a;color:#fff;font-weight:bold">Play!</button>'
+(first?'':'<button id="nm_x" style="margin:14px 0 0 10px;font-size:16px;padding:10px 16px;border:0;border-radius:12px;background:#555;color:#fff">Cancel</button>')
+'</div>';
document.body.appendChild(ov);
var inp=document.getElementById('nm_in'); inp.value=cur;
['keydown','keyup','keypress'].forEach(function(e){inp.addEventListener(e,function(ev){ev.stopPropagation();if(e=='keydown'&&ev.key=='Enter')ok();});});
function done(v){ov.remove();window.__nm=v;}
function ok(){var v=inp.value.trim(); if(!v){inp.style.borderColor='red';return;} done(v);}
document.getElementById('nm_ok').onclick=ok;
var x=document.getElementById('nm_x'); if(x) x.onclick=function(){done('\\x00');};
setTimeout(function(){inp.focus();},50);
})();
"""

class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Fruit Slash")
        flags = 0 if WEB else pygame.SCALED | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((W, H), flags)
        self.clock = pygame.time.Clock()
        pygame.mixer.set_num_channels(20)
        pygame.mixer.set_reserved(1)
        self.music_ch = pygame.mixer.Channel(0)
        self.f_big = mkfont(96)
        self.f_title = mkfont(56)
        self.f_med = mkfont(30)
        self.f_row = mkfont(24)
        self.f_small = mkfont(18)
        self.f_score = mkfont(64)
        self.save = {"music": 0.6, "sfx": 0.8, "mute": False, "best": {}, "name": ""}
        self.save.update(store_load())
        self.name_buf = ""
        self.name_cb = None
        self.lb = {"rows": [], "status": "Loading...", "req": None, "next": 0}
        self.panel_t = 0.0
        self.panel_open = False
        self.submit_req = None
        self.submit_msg = ""
        self.state = "loading"
        self.mouse_down = False
        self.mouse = (0, 0)
        self.blade = deque()
        self.items, self.pieces, self.particles, self.texts = [], [], [], []
        self.splat = pygame.Surface((W, H), pygame.SRCALPHA)
        self.splat_t = 0
        self.shake = 0
        self.flash = 0
        self.settings_from = "menu"
        self.sounds, self.fruit_sprites = {}, {}
        self.swoosh_cd = 0

    # ---------------------------------------------------------------- loading
    async def load(self):
        steps = [
            ("Polishing fruit", lambda: self.fruit_sprites.update({n: build_fruit(n) for n in FRUITS})),
            ("Arming bombs", lambda: (setattr(self, "bomb", build_bomb()),
                                      setattr(self, "freeze", build_special("freeze", self.f_med)),
                                      setattr(self, "frenzy", build_special("frenzy", self.f_med)))),
            ("Varnishing table", lambda: setattr(self, "bg", build_background())),
        ]
        for n, fn in [("swoosh", make_swoosh), ("slice", make_slice), ("splat", make_splat),
                      ("bomb", make_bomb), ("combo", make_combo), ("miss", make_miss),
                      ("over", make_over), ("click", make_click), ("freeze", make_freeze),
                      ("frenzy", make_frenzy)]:
            steps.append(("Sharpening sounds", lambda n=n, fn=fn: self.sounds.__setitem__(n, fn())))
        self.ld = {"items": [], "pieces": [], "parts": [], "trail": [], "spawn": 0.2, "sliced": 0,
                   "last": None, "down": False, "clock": pygame.time.Clock(), "p": 0.0, "label": ""}
        for i, (label, fn) in enumerate(steps):
            self.ld["label"], self.ld["p"] = label, i / len(steps)
            self.loading_frame()
            fn()
            await asyncio.sleep(0)
        self.ld["label"], self.ld["p"] = "Ready!", 1.0
        end = pygame.time.get_ticks() + 3500
        while pygame.time.get_ticks() < end:
            self.loading_frame()
            await asyncio.sleep(0)
        self.build_menu()
        self.build_ui()

    def loading_frame(self):
        L = self.ld
        dt = min(0.05, L["clock"].tick(60) / 1000)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                L["down"], L["last"] = True, e.pos
            elif e.type == pygame.MOUSEBUTTONUP:
                L["down"], L["last"] = False, None
            elif e.type == pygame.MOUSEMOTION and L["down"]:
                self.ld_slice(L["last"] or e.pos, e.pos)
                L["last"] = e.pos
                L["trail"].append([e.pos[0], e.pos[1], 0.25])
        L["spawn"] -= dt
        if L["spawn"] <= 0 and self.fruit_sprites:
            name = random.choice(list(self.fruit_sprites))
            x = random.uniform(160, W - 160)
            spr = self.fruit_sprites[name][0]
            L["items"].append(Item("fruit", spr, self.fruit_sprites[name][3], x, H + 40,
                                   (W / 2 - x) * random.uniform(0.1, 0.35), -random.uniform(780, 960),
                                   random.uniform(-200, 200), name))
            L["spawn"] = random.uniform(0.35, 0.8)
        for it in L["items"]:
            it.update(dt, 900)
        L["items"] = [i for i in L["items"] if i.alive and i.y < H + 120]
        for p in L["pieces"]:
            p.update(dt, 900)
        L["pieces"] = [p for p in L["pieces"] if p.y < H + 150]
        for p in L["parts"]:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 700 * dt
            p[4] -= dt
        L["parts"] = [p for p in L["parts"] if p[4] > 0]
        for t in L["trail"]:
            t[2] -= dt
        L["trail"] = [t for t in L["trail"] if t[2] > 0]
        self.draw_loading(L["label"], L["p"])

    def ld_slice(self, a, b):
        L = self.ld
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy)
        if ln < 1:
            return
        for it in L["items"]:
            t = max(0, min(1, ((it.x - ax) * dx + (it.y - ay) * dy) / (ln * ln)))
            if math.hypot(ax + dx * t - it.x, ay + dy * t - it.y) < it.r + 8:
                it.alive = False
                L["sliced"] += 1
                whole, left, right, r = self.fruit_sprites[it.name]
                ang = math.degrees(math.atan2(-dy, dx))
                nx, ny = -dy / ln, dx / ln
                for spr, sgn in ((left, 1), (right, -1)):
                    p = Item("piece", spr, r, it.x, it.y, it.vx + nx * 130 * sgn, it.vy * 0.4 + ny * 130 * sgn, 0)
                    p.rot, p.vrot = ang - 90, random.uniform(40, 160) * sgn
                    L["pieces"].append(p)
                for _ in range(14):
                    a2 = random.uniform(0, 6.283)
                    sp = random.uniform(80, 340)
                    L["parts"].append([it.x, it.y, math.cos(a2) * sp, math.sin(a2) * sp,
                                       random.uniform(0.3, 0.7), FRUITS[it.name][1]])
                if "slice" in self.sounds:
                    self.sfx("slice", 0.6)

    def draw_loading(self, label, p):
        s = self.screen
        s.fill((30, 16, 6))
        pygame.draw.circle(s, (60, 36, 16), (W // 2, H // 2 - 40), 300)
        L = self.ld
        for it in L["items"]:
            it.draw(s)
        for it in L["pieces"]:
            it.draw(s)
        for q in L["parts"]:
            pygame.draw.circle(s, q[5], (int(q[0]), int(q[1])), max(1, int(q[4] * 8)))
        pts = [(t[0], t[1]) for t in L["trail"]]
        if len(pts) > 1:
            pygame.draw.lines(s, (255, 255, 255), False, pts, 5)
        self.draw_logo(W // 2, H // 2 - 110)
        bar = pygame.Rect(0, 0, 420, 22)
        bar.center = (W // 2, H // 2 + 60)
        pygame.draw.rect(s, (20, 10, 4), bar, border_radius=11)
        pygame.draw.rect(s, (255, 210, 74), bar, 3, border_radius=11)
        fill = bar.inflate(-8, -8)
        fill.w = int(fill.w * p)
        if fill.w > 0:
            pygame.draw.rect(s, (110, 200, 50), fill, border_radius=7)
        t = self.f_small.render(f"{label}...", True, (255, 240, 200))
        s.blit(t, t.get_rect(center=(W // 2, H // 2 + 100)))
        t = self.f_small.render("Swipe to slice the fruit while you wait!", True, (255, 210, 74))
        s.blit(t, t.get_rect(center=(W // 2, H - 40)))
        if L["sliced"]:
            t = self.f_med.render(f"Sliced: {L['sliced']}", True, (255, 255, 255))
            s.blit(t, t.get_rect(center=(W // 2, 40)))
        pygame.display.flip()

    def draw_logo(self, cx, cy):
        a = self.f_big.render("Fruit", True, (255, 210, 74))
        b = self.f_big.render("Slash", True, (255, 77, 61))
        sh_a = self.f_big.render("Fruit", True, (120, 50, 20))
        sh_b = self.f_big.render("Slash", True, (90, 20, 10))
        w = a.get_width() + b.get_width() + 20
        x = cx - w // 2
        for img, sh, xx in ((a, sh_a, x), (b, sh_b, x + a.get_width() + 20)):
            self.screen.blit(sh, (xx + 4, cy - img.get_height() // 2 + 6))
            self.screen.blit(img, (xx, cy - img.get_height() // 2))

    # ---------------------------------------------------------------- helpers
    def persist(self):
        store_save(self.save)

    def apply_volume(self):
        m = self.save["mute"]
        self.music_ch.set_volume(0 if m else self.save["music"])

    def sfx(self, name, vol=1.0):
        if self.save["mute"]:
            return
        snd = self.sounds[name]
        snd.set_volume(self.save["sfx"] * vol)
        snd.play()

    def play_music(self, name):
        pass

    def quit(self):
        self.persist()
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------- menu
    def build_menu(self):
        self.menu_items = []
        names = ["watermelon", "orange", "kiwi", "plum"]
        for i, mode in enumerate(MODES):
            whole, left, right, r = self.fruit_sprites[names[i]]
            k = 150 / (2 * r)
            spr = pygame.transform.smoothscale(whole, (int(whole.get_width() * k), int(whole.get_height() * k)))
            self.menu_items.append({"mode": mode, "x": 180 + i * 213, "y": 330, "spr": spr, "k": k,
                                    "name": names[i], "r": 75, "ph": i * 1.3, "hit": False})
        self.menu_pending = None

    def build_ui(self):
        grey = (90, 60, 40)
        self.btn_name = Button("", 0, 0, lambda: self.ask_name(None), 180, 44, grey)
        self.menu_btns = [
            Button("Sound", 0, 0, lambda: self.open_settings("menu"), 180, 44, grey),
            self.btn_name,
            Button("Fullscreen", 0, 0, self.toggle_fullscreen, 180, 44, grey),
        ]
        if not WEB:
            self.menu_btns.append(Button("Quit", 0, 0, self.quit, 180, 44, grey))
        n = len(self.menu_btns)
        for i, b in enumerate(self.menu_btns):
            b.rect.center = (W // 2 + int((i - (n - 1) / 2) * 195), H - 40)
        self.btn_pause = Button("II", W - 45, 38, self.pause, 60, 50, grey)
        self.btn_full_hud = None
        self.settings_btns = [Button("Back", W // 2, 470, self.close_settings)]
        self.btn_mute = Button("", W // 2, 380, self.toggle_mute, 300, 48, (90, 60, 40))
        self.sl_sfx = Slider("Effects", 400, 260, 320, self.save["sfx"])
        self.pause_btns = [Button("Resume", W // 2, 300, self.resume),
                           Button("Sound", W // 2, 370, lambda: self.open_settings("pause")),
                           Button("Menu", W // 2, 440, self.to_menu)]
        self.over_btns = [Button("Play Again", W // 2, 420, lambda: self.start(self.mode)),
                          Button("Menu", W // 2, 490, self.to_menu)]
        self.show_menu()

    def pause(self):
        if self.state == "play":
            self.sfx("click")
            self.state = "pause"

    def toggle_fullscreen(self):
        self.sfx("click")
        try:
            if WEB:
                platform.window.eval(
                    "var c=document.getElementById('canvas')||document.documentElement;"
                    "if(document.fullscreenElement){document.exitFullscreen()}else{c.requestFullscreen()}")
            else:
                pygame.display.toggle_fullscreen()
        except Exception:
            pass

    # ------------------------------------------------------- name & scores
    def clean_name(self, s):
        s = "".join(ch for ch in (s or "") if ch.isprintable()).strip()[:12]
        return s or "Player"

    def ask_name(self, cb):
        self.sfx("click")
        if WEB:
            self.name_buf = self.save.get("name", "")
            self.name_cb = cb
            self.name_from = self.state
            self.state = "name"
            self.name_web = True
            first = "0" if self.save.get("name") else "1"
            platform.window.eval(NAME_JS.replace("__FIRST__", first).replace("__CUR__", json.dumps(self.name_buf)))
        else:
            self.name_buf = self.save.get("name", "")
            self.name_cb = cb
            self.name_from = self.state
            self.state = "name"

    def finish_name(self):
        self.save["name"] = self.clean_name(self.name_buf)
        self.persist()
        self.state = self.name_from
        cb, self.name_cb = self.name_cb, None
        if cb:
            cb()

    def refresh_scores(self):
        self.lb["next"] = pygame.time.get_ticks() + 30000
        if not leaderboard.enabled():
            self.lb["status"] = "Not set up yet"
            return
        self.lb["req"] = leaderboard.fetch(None)

    def poll_net(self):
        if getattr(self, "name_web", False):
            try:
                v = platform.window.eval("window.__nm===undefined?null:window.__nm")
            except Exception:
                v = None
            if v is not None:
                v = str(v)
                self.name_web = False
                platform.window.eval("window.__nm=undefined")
                if v == "\x00" and self.save.get("name"):
                    self.name_buf = self.save["name"]
                else:
                    self.name_buf = "" if v == "\x00" else v
                self.finish_name()
        if self.lb["req"] is not None:
            res = leaderboard.result(self.lb["req"])
            if res is not None:
                self.lb["req"] = None
                rows = leaderboard.parse_scores(res)
                if rows is None:
                    self.lb["status"] = "Offline"
                else:
                    self.lb["rows"] = rows[:3]
                    self.lb["status"] = "" if rows else "Be the first!"
        if self.submit_req is not None:
            res = leaderboard.result(self.submit_req)
            if res is not None:
                self.submit_req = None
                ok = res != "ERR" and not res.startswith("{")
                self.submit_msg = "Score saved to leaderboard!" if ok else "Couldn't save score"
                if ok:
                    self.lb["next"] = 0

    def show_menu(self):
        self.state = "menu"
        self.items.clear()
        self.pieces.clear()
        for it in self.menu_items:
            it["hit"] = False
        self.menu_pending = None
        self.play_music("m_menu")
        self.lb["next"] = 0

    def to_menu(self):
        self.sfx("click")
        self.show_menu()

    def open_settings(self, frm):
        self.sfx("click")
        self.settings_from = frm
        self.state = "settings"

    def close_settings(self):
        self.sfx("click")
        self.persist()
        self.state = self.settings_from

    def toggle_mute(self):
        self.save["mute"] = not self.save["mute"]
        self.apply_volume()
        self.sfx("click")

    # ------------------------------------------------------------------- play
    def start(self, mode):
        if not self.save.get("name"):
            self.ask_name(lambda: self.start(mode))
            return
        self.mode = mode
        self.submit_msg = ""
        self.submit_req = None
        self.items.clear()
        self.pieces.clear()
        self.particles.clear()
        self.texts.clear()
        self.splat.fill((0, 0, 0, 0))
        self.score = 0
        self.lives = {"classic": 3, "sudden": 1}.get(mode, 0)
        self.max_lives = self.lives
        self.time_left = {"arcade": 60, "zen": 90}.get(mode)
        self.elapsed = 0.0
        self.spawn_t = 0.8
        self.freeze_t = 0
        self.frenzy_t = 0
        self.combo_n = 0
        self.combo_t = 0
        self.combo_pos = (0, 0)
        self.banner = ("", 0)
        self.state = "play"
        self.play_music("m_game")
        self.sfx("click")

    def resume(self):
        self.sfx("click")
        self.state = "play"

    def difficulty(self):
        return min(1.0, self.elapsed / (40 if self.mode == "sudden" else 90))

    def throw(self, kind, offset=0.0):
        d = self.difficulty()
        if kind == "bomb":
            spr, r = self.bomb
            name = None
        elif kind == "freeze":
            spr, r = self.freeze
            name = None
        elif kind == "frenzy":
            spr, r = self.frenzy
            name = None
        else:
            name = random.choice(list(FRUITS))
            spr, r = self.fruit_sprites[name][0], self.fruit_sprites[name][3]
        g = H * 1.15 * (1 + (0.25 * d if self.mode == "sudden" else 0))
        height = H * random.uniform(0.55, 0.85)
        vy = -math.sqrt(2 * g * height)
        x = random.uniform(W * 0.15, W * 0.85)
        vx = (W / 2 - x) * random.uniform(0.1, 0.5) + random.uniform(-90, 90)
        it = Item(kind, spr, r, x, H + r + offset, vx, vy, random.uniform(-220, 220), name)
        self.items.append(it)

    def spawn_wave(self):
        d = self.difficulty()
        mode = self.mode
        if self.frenzy_t > 0:
            for i in range(random.randint(3, 5)):
                self.throw("fruit", i * 25)
            self.spawn_t = 0.45
            return
        n = 1 + int(random.random() * (1 + d * 3))
        bomb_p = {"classic": 0.10 + 0.12 * d, "arcade": 0.12, "zen": 0.0, "sudden": 0.18 + 0.15 * d}[mode]
        for i in range(n):
            kind = "bomb" if i > 0 and random.random() < bomb_p else "fruit"
            if i == 0 and mode != "zen" and random.random() < bomb_p * 0.5:
                kind = "bomb"
            self.throw(kind, i * 30)
        if mode == "arcade" and self.freeze_t <= 0 and self.frenzy_t <= 0 and random.random() < 0.1:
            self.throw(random.choice(("freeze", "frenzy")), 60)
        lo, hi = (1.6, 0.8) if mode != "sudden" else (1.2, 0.5)
        self.spawn_t = lo + (hi - lo) * d + random.uniform(0, 0.3)
        self.sfx("swoosh", 0.4)

    def add_text(self, text, x, y, col=(255, 255, 255), size=None, life=0.9):
        self.texts.append([text, x, y, life, life, col, size or self.f_med])

    def juice(self, x, y, flesh, big=1.0):
        for _ in range(int(5 * big) + 2):
            a = random.uniform(0, 6.283)
            d = random.uniform(0, 40) * big
            pygame.draw.circle(self.splat, (*flesh, 150), (int(x + math.cos(a) * d), int(y + math.sin(a) * d)),
                               random.randint(4, int(18 * big) + 4))
        for _ in range(int(14 * big)):
            a = random.uniform(0, 6.283)
            sp = random.uniform(80, 360)
            self.particles.append([x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.4, 0.9), flesh])

    def slice_item(self, it, dx, dy):
        it.alive = False
        ang = math.degrees(math.atan2(-dy, dx))
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        if it.kind == "fruit":
            whole, left, right, r = self.fruit_sprites[it.name]
            flesh = FRUITS[it.name][1]
            for spr, sgn in ((left, 1), (right, -1)):
                p = Item("piece", pygame.transform.rotate(spr, ang - 90), r, it.x, it.y,
                         it.vx + nx * 130 * sgn, it.vy * 0.4 + ny * 130 * sgn, 0)
                p.rot, p.vrot = 0, 0
                p.spr = spr
                p.rot = ang - 90
                p.vrot = random.uniform(40, 160) * sgn
                self.pieces.append(p)
            self.juice(it.x, it.y, flesh)
            self.sfx("slice")
            self.sfx("splat", 0.6)
            pts = 2 if self.frenzy_t > 0 else 1
            self.score += pts
            self.add_text(f"+{pts}", it.x, it.y - 20, (255, 240, 120))
            self.combo_n += 1
            self.combo_t = 0.3
            self.combo_pos = (it.x, it.y)
        elif it.kind == "bomb":
            self.sfx("bomb")
            self.flash = 1.0
            self.shake = 0.6
            self.juice(it.x, it.y, (255, 160, 40), 2.0)
            if self.mode == "arcade":
                self.score = max(0, self.score - 10)
                self.add_text("-10", it.x, it.y, (255, 80, 60))
            else:
                self.end_game()
        elif it.kind == "freeze":
            self.freeze_t = 4.0
            self.sfx("freeze")
            self.juice(it.x, it.y, (170, 225, 255), 1.5)
            self.set_banner("FREEZE!", (150, 230, 255))
        elif it.kind == "frenzy":
            self.frenzy_t = 5.0
            self.sfx("frenzy")
            self.juice(it.x, it.y, (255, 210, 60), 1.5)
            self.set_banner("BANANA FRENZY x2!", (255, 220, 70))

    def set_banner(self, text, col):
        self.banner = (text, 1.6, col)

    def lose_life(self):
        self.sfx("miss")
        self.lives -= 1
        self.flash = 0.35
        if self.lives <= 0:
            self.end_game()

    def end_game(self):
        if self.state != "play":
            return
        self.state = "over"
        best = self.save["best"].get(self.mode, 0)
        self.new_best = self.score > best
        if self.new_best:
            self.save["best"][self.mode] = self.score
            if self.score > 0 and leaderboard.enabled():
                self.submit_msg = "Saving score..."
                self.submit_req = leaderboard.submit(self.save["name"], self.score, self.mode)
        self.persist()
        self.music_ch.fadeout(500)
        self.cur_music = None
        self.sfx("over")

    # ----------------------------------------------------------------- update
    def blade_segment(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if math.hypot(dx, dy) < 6:
            return
        if self.swoosh_cd <= 0 and math.hypot(dx, dy) > 25:
            self.sfx("swoosh", 0.6)
            self.swoosh_cd = 0.18
        if self.state == "play":
            for it in self.items:
                if it.alive and seg_dist(it.x, it.y, a[0], a[1], b[0], b[1]) <= it.r:
                    self.slice_item(it, dx, dy)
                    if self.state != "play":
                        return
        elif self.state == "menu" and not self.menu_pending:
            for m in self.menu_items:
                if not m["hit"] and seg_dist(m["x"], m["y"] + math.sin(pygame.time.get_ticks() / 500 + m["ph"]) * 8,
                                             a[0], a[1], b[0], b[1]) <= m["r"]:
                    m["hit"] = True
                    whole, left, right, r = self.fruit_sprites[m["name"]]
                    ang = math.degrees(math.atan2(-dy, dx))
                    n = math.hypot(dx, dy)
                    nx, ny = -dy / n, dx / n
                    for spr, sgn in ((left, 1), (right, -1)):
                        big = pygame.transform.smoothscale(spr, (int(spr.get_width() * m["k"]), int(spr.get_height() * m["k"])))
                        p = Item("piece", big, r, m["x"], m["y"], nx * 160 * sgn, -150 + ny * 160 * sgn, 0)
                        p.rot, p.vrot = ang - 90, random.uniform(40, 120) * sgn
                        self.pieces.append(p)
                    self.juice(m["x"], m["y"], FRUITS[m["name"]][1], 2.0)
                    self.sfx("slice")
                    self.sfx("splat", 0.6)
                    self.menu_pending = [m["mode"], 0.7]

    def update(self, dt):
        self.poll_net()
        self.update_panel(dt)
        self.swoosh_cd -= dt
        self.shake = max(0, self.shake - dt)
        self.flash = max(0, self.flash - dt * 2)
        self.splat_t += dt
        if self.splat_t > 0.2:
            self.splat_t = 0
            self.splat.fill((0, 0, 0, 5), special_flags=pygame.BLEND_RGBA_SUB)
        cutoff = pygame.time.get_ticks() / 1000 - 0.18
        while self.blade and self.blade[0][2] < cutoff:
            self.blade.popleft()
        for p in self.particles:
            p[4] -= dt
            p[3] += 900 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for t in self.texts:
            t[3] -= dt
            t[2] -= 40 * dt
        self.texts = [t for t in self.texts if t[3] > 0]
        for p in self.pieces:
            p.update(dt, H * 1.4)
        self.pieces = [p for p in self.pieces if p.y < H + 150]

        if self.state == "menu":
            if self.menu_pending:
                self.menu_pending[1] -= dt
                if self.menu_pending[1] <= 0:
                    self.start(self.menu_pending[0])
            return
        if self.state != "play":
            return

        ts = 0.35 if self.freeze_t > 0 else 1.0
        sdt = dt * ts
        self.elapsed += dt
        self.freeze_t = max(0, self.freeze_t - dt)
        self.frenzy_t = max(0, self.frenzy_t - dt)
        if self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - dt, self.banner[2])
        if self.time_left is not None:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.end_game()
                return
        self.spawn_t -= sdt
        if self.spawn_t <= 0:
            self.spawn_wave()
        g = H * 1.15 * (1 + (0.25 * self.difficulty() if self.mode == "sudden" else 0))
        for it in self.items:
            it.update(sdt, g)
            if it.y > H + it.r + 40 and it.vy > 0 and it.alive:
                it.alive = False
                if it.kind == "fruit" and self.mode in ("classic", "sudden"):
                    self.lose_life()
                    if self.state != "play":
                        return
        self.items = [i for i in self.items if i.alive]
        self.combo_t -= dt
        if self.combo_t <= 0 and self.combo_n:
            if self.combo_n >= 3:
                self.score += self.combo_n
                self.sfx("combo")
                self.add_text(f"{self.combo_n} COMBO!  +{self.combo_n}", self.combo_pos[0], self.combo_pos[1] - 50,
                              (255, 120, 60), self.f_title, 1.3)
            self.combo_n = 0

    # ------------------------------------------------------------------- draw
    def draw_blade(self):
        pts = list(self.blade)
        if len(pts) < 2:
            return
        now = pygame.time.get_ticks() / 1000
        for i in range(1, len(pts)):
            age = (now - pts[i][2]) / 0.18
            w = max(1, int(10 * (1 - age)))
            pygame.draw.line(self.screen, (200, 240, 255), pts[i - 1][:2], pts[i][:2], w + 4)
            pygame.draw.line(self.screen, (255, 255, 255), pts[i - 1][:2], pts[i][:2], w)

    def draw_world(self):
        s = self.screen
        ox = random.randint(-8, 8) * self.shake if self.shake else 0
        oy = random.randint(-8, 8) * self.shake if self.shake else 0
        s.blit(self.bg, (ox, oy))
        s.blit(self.splat, (ox, oy))
        for p in self.pieces:
            p.draw(s)
        for it in self.items:
            it.draw(s)
        for p in self.particles:
            pygame.draw.circle(s, p[5], (int(p[0]), int(p[1])), 3)
        if self.state == "play" and self.freeze_t > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((120, 200, 255, 55))
            s.blit(ov, (0, 0))

    def draw_text(self, font, text, pos, col=(255, 255, 255), center=True, shadow=(40, 15, 5)):
        t = font.render(text, True, col)
        sh = font.render(text, True, shadow)
        r = t.get_rect(center=pos) if center else t.get_rect(topleft=pos)
        self.screen.blit(sh, r.move(3, 3))
        self.screen.blit(t, r)

    def draw_hud(self):
        s = self.screen
        self.draw_text(self.f_score, str(self.score), (20, 10), (255, 210, 74), center=False)
        best = self.save["best"].get(self.mode, 0)
        self.draw_text(self.f_small, f"Best {best}", (24, 90), center=False)
        if self.time_left is not None:
            self.draw_text(self.f_score, str(int(math.ceil(self.time_left))), (W // 2, 40),
                           (255, 90, 70) if self.time_left < 10 else (255, 255, 255))
        for i in range(self.max_lives):
            col = (230, 50, 50) if i < self.lives else (90, 50, 40)
            x = W - 125 - i * 46
            pygame.draw.line(s, col, (x - 14, 20), (x + 14, 48), 8)
            pygame.draw.line(s, col, (x + 14, 20), (x - 14, 48), 8)
        if self.frenzy_t > 0:
            self.draw_text(self.f_med, f"x2 {self.frenzy_t:.1f}s", (W // 2, 120), (255, 220, 70))
        if self.freeze_t > 0:
            self.draw_text(self.f_med, f"FROZEN {self.freeze_t:.1f}s", (W // 2, 120), (150, 230, 255))
        if self.banner[1] > 0:
            self.draw_text(self.f_title, self.banner[0], (W // 2, 220), self.banner[2])
        self.btn_pause.draw(s, self.f_med, self.mouse)
        for t in self.texts:
            a = max(0, min(1, t[3] / t[4] * 2))
            img = t[6].render(t[0], True, t[5])
            img.set_alpha(int(255 * a))
            self.screen.blit(img, img.get_rect(center=(t[1], t[2])))

    def overlay(self, alpha=150):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((15, 7, 2, alpha))
        self.screen.blit(ov, (0, 0))

    def draw(self):
        s = self.screen
        mouse = self.mouse
        self.draw_world()
        if self.state == "menu":
            self.draw_logo(W // 2, 95)
            self.draw_text(self.f_med, "Slice a fruit to begin", (W // 2, 185), (255, 240, 200))
            tick = pygame.time.get_ticks() / 500
            for m in self.menu_items:
                label, lines = MODES[m["mode"]]
                y = m["y"] + math.sin(tick + m["ph"]) * 8
                if not m["hit"]:
                    img = pygame.transform.rotate(m["spr"], math.sin(tick * 0.6 + m["ph"]) * 12)
                    s.blit(img, img.get_rect(center=(m["x"], y)))
                self.draw_text(self.f_row, label, (m["x"], m["y"] + 110))
                best = self.save["best"].get(m["mode"], 0)
                self.draw_text(self.f_small, f"Best: {best}", (m["x"], m["y"] + 140), (255, 230, 140))
                for j, ln in enumerate(lines):
                    self.draw_text(self.f_small, ln, (m["x"], m["y"] + 168 + j * 22), (230, 210, 180))
            self.btn_name.text = "Name: " + (self.save.get("name") or "?")
            for b in self.menu_btns:
                b.draw(s, self.f_small, mouse)
            if WEB and self.portrait():
                self.draw_text(self.f_small, "Tip: rotate your phone sideways & tap Fullscreen", (W // 2, 15), (255, 230, 140))
        elif self.state in ("play", "pause", "over"):
            self.draw_hud()
        if self.state == "name":
            self.overlay(200)
            self.draw_text(self.f_title, "Choose a nickname", (W // 2, 190))
            box = pygame.Rect(0, 0, 420, 60)
            box.center = (W // 2, 300)
            pygame.draw.rect(s, (40, 20, 8), box, border_radius=12)
            pygame.draw.rect(s, (255, 210, 74), box, 3, border_radius=12)
            cursor = "_" if (pygame.time.get_ticks() // 400) % 2 == 0 else ""
            self.draw_text(self.f_med, self.name_buf + cursor, box.center)
            self.draw_text(self.f_small, "Please don't use your real name - it shows on the public leaderboard", (W // 2, 360), (230, 210, 180))
            self.draw_text(self.f_small, "Type it and press Enter", (W // 2, 390), (230, 210, 180))
        if self.state == "pause":
            self.overlay()
            self.draw_text(self.f_title, "Paused", (W // 2, 200))
            for b in self.pause_btns:
                b.draw(s, self.f_med, mouse)
        elif self.state == "over":
            self.overlay(170)
            self.draw_text(self.f_title, "Game Over", (W // 2, 200))
            self.draw_text(self.f_med, f"Score: {self.score}", (W // 2, 275))
            if self.new_best:
                self.draw_text(self.f_med, "New best!", (W // 2, 320), (255, 210, 74))
            else:
                self.draw_text(self.f_small, f"Best: {self.save['best'].get(self.mode, 0)}", (W // 2, 320))
            self.draw_text(self.f_small, self.submit_msg, (W // 2, 360), (230, 210, 180))
            for b in self.over_btns:
                b.draw(s, self.f_med, mouse)
        elif self.state == "settings":
            self.overlay(200)
            self.draw_text(self.f_title, "Sound", (W // 2, 130))
            self.sl_sfx.draw(s, self.f_med)
            self.btn_mute.text = "Sound: OFF" if self.save["mute"] else "Sound: ON"
            self.btn_mute.draw(s, self.f_med, mouse)
            for b in self.settings_btns:
                b.draw(s, self.f_med, mouse)
        if self.state in ("menu", "over"):
            self.draw_panel()
        if self.flash > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((255, 255, 255, int(200 * self.flash)))
            s.blit(ov, (0, 0))
        if self.state in ("play", "menu"):
            self.draw_blade()
        pygame.display.flip()

    # ----------------------------------------------------------------- events
    def buttons(self):
        return {"menu": self.menu_btns, "play": [self.btn_pause], "pause": self.pause_btns, "over": self.over_btns,
                "settings": self.settings_btns + [self.btn_mute]}.get(self.state, [])

    def portrait(self):
        try:
            return platform.window.innerHeight > platform.window.innerWidth
        except Exception:
            return False

    def panel_rect(self):
        t = self.panel_t
        return pygame.Rect(int(W - PEEK - (PANEL_W - PEEK) * t), PANEL_Y, PANEL_W, PANEL_H)

    def update_panel(self, dt):
        if self.state not in ("menu", "over"):
            self.panel_t = 0.0
            return
        over = self.panel_rect().collidepoint(self.mouse)
        target = 1.0 if (self.panel_open or over) else 0.0
        self.panel_t += (target - self.panel_t) * min(1.0, dt * 12)
        if self.lb["req"] is None and pygame.time.get_ticks() >= self.lb["next"]:
            self.refresh_scores()

    def draw_panel(self):
        r = self.panel_rect()
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        rad = dict(border_top_left_radius=22, border_bottom_left_radius=22)
        pygame.draw.rect(box, (25, 12, 4, 230), box.get_rect(), **rad)
        pygame.draw.rect(box, (255, 210, 74), box.get_rect(), 3, **rad)
        self.screen.blit(box, r.topleft)
        gold = (255, 210, 74)
        self.draw_text(self.f_small, "TOP 3", (r.x + 12, r.y + 10), gold, center=False)
        medals = [(255, 210, 74), (200, 205, 215), (205, 127, 50)]
        for i, row in enumerate(self.lb["rows"]):
            cy = r.y + 70 + i * 46
            pygame.draw.circle(self.screen, medals[i], (r.x + 28, cy), 14)
            num = self.f_small.render(str(i + 1), True, (40, 20, 5))
            self.screen.blit(num, num.get_rect(center=(r.x + 28, cy)))
            self.draw_text(self.f_small, row["name"], (r.x + 52, cy - 10), center=False)
            sc = self.f_small.render(str(row["score"]), True, gold)
            self.screen.blit(sc, sc.get_rect(midright=(r.x + 255, cy)))
            self.draw_text(self.f_small, SHORT[row["mode"]], (r.x + 265, cy - 10), (230, 210, 180), center=False)
        if not self.lb["rows"]:
            self.draw_text(self.f_small, self.lb["status"], (r.x + 52, r.y + 100), (230, 210, 180), center=False)

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type == pygame.KEYDOWN and self.state == "name":
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.finish_name()
            elif e.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif e.unicode and e.unicode.isprintable() and len(self.name_buf) < 12:
                self.name_buf += e.unicode
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_f:
                self.toggle_fullscreen()
            if e.key == pygame.K_ESCAPE:
                if self.state == "play":
                    self.state = "pause"
                    self.sfx("click")
                elif self.state == "pause":
                    self.resume()
                elif self.state == "settings":
                    self.close_settings()
            elif e.key == pygame.K_m:
                self.toggle_mute()
        if self.state == "settings":
            changed = self.sl_sfx.event(e)
            if changed:
                self.save["sfx"] = self.sl_sfx.value
                self.apply_volume()
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.mouse = e.pos
            if self.state in ("menu", "over"):
                if self.panel_rect().collidepoint(e.pos):
                    self.panel_open = not self.panel_open
                    return
                self.panel_open = False
            self.mouse_down = True
            self.blade.clear()
            self.blade.append((*e.pos, pygame.time.get_ticks() / 1000))
            for b in self.buttons():
                if b.rect.collidepoint(e.pos):
                    b.cb()
                    self.mouse_down = False
                    break
            if self.state == "play":
                pass
        elif e.type == pygame.MOUSEMOTION:
            prev = self.mouse
            self.mouse = e.pos
            if self.mouse_down and self.state in ("play", "menu"):
                self.blade.append((*e.pos, pygame.time.get_ticks() / 1000))
                self.blade_segment(prev, e.pos)
        elif e.type == pygame.MOUSEBUTTONUP:
            self.mouse_down = False

    async def run(self):
        await self.load()
        self.apply_volume()
        if not self.save.get("name"):
            self.ask_name(None)
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(Game().run())

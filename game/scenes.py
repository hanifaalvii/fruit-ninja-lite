"""Menu-side scenes: loading, menu, settings, awards, unlocks, nickname entry."""
import math
import random

import pygame

from . import progress, settings, ui
from .common import BoardPanel, Scene, split_fruit
from .effects import BladeTrail, Particles
from .entities import Item, seg_dist
from .net import clean_name
from .world import additive_glow

W, H = settings.W, settings.H
TIPS = [
    "CHAIN FRUIT FAST FOR A BIGGER COMBO MULTIPLIER",
    "SLICE 3 OR MORE FRUIT IN ONE SWIPE FOR A BONUS",
    "BOMBS HURT. LET THEM FALL",
    "GRAB GLOWING ORBS: SLOW-MO, DOUBLE SCORE, FRUIT RAIN",
    "EVERY 8TH CLASSIC WAVE BRINGS A GIANT WATERMELON",
    "HIGH SCORES UNLOCK BETTER CUTTING BOARDS AND BLADES",
    "FINISH THE DAILY CONTRACT FOR A BONUS ACHIEVEMENT",
]
MODE_COLORS = {"classic": ui.MAGENTA, "arcade": ui.YELLOW, "zen": ui.CYAN, "sudden": ui.VIOLET}
MODE_TAGS = {"classic": "MODE 01", "arcade": "MODE 02", "zen": "MODE 03", "sudden": "MODE 04"}


def glitch_blit(dst, img, center, t, strength=1.0):
    """Blit an image; during glitch bursts it tears into horizontally shifted strips."""
    r = img.get_rect(center=center)
    phase = t % 3.4
    if phase < 0.16:
        rng = random.Random(int(t * 40))
        sh = img.get_height() // 7
        for k in range(7):
            off = int(rng.uniform(-26, 26) * strength) if rng.random() < 0.6 else 0
            strip = img.subsurface((0, k * sh, img.get_width(), sh if k < 6 else img.get_height() - 6 * sh))
            dst.blit(strip, (r.x + off, r.y + k * sh))
    else:
        dst.blit(img, r)


def segment_bar(s, rect, frac, t, segs=36):
    """Chamfered neon bar made of segments; the leading segment pulses yellow."""
    s.blit(ui.neon_box(rect.w, rect.h, ui.CYAN, cut=10, glow=1.0), ui.neon_box(rect.w, rect.h, ui.CYAN).get_rect(
        center=rect.center))
    inner = rect.inflate(-18, -14)
    gap = inner.w / segs
    lit = frac * segs
    for i in range(segs):
        x = inner.x + i * gap
        if i + 1 <= lit:
            col = ui.lerp_col(ui.CYAN, ui.MAGENTA, i / segs)
        elif i < lit:
            col = ui.lerp_col((40, 28, 70), ui.YELLOW, 0.5 + 0.5 * math.sin(t * 14))
        else:
            col = (34, 24, 60)
        pygame.draw.rect(s, col, (x + 1, inner.y, max(2, gap - 3), inner.h))


# ------------------------------------------------------------------- loading
class Loading(Scene):
    def enter(self, loader=None):
        a = self.app
        self.loader = loader
        self.items, self.pieces = [], []
        self.parts = Particles(60 if settings.WEB else 120)
        self.trail = BladeTrail()
        self.sliced = 0
        self.t = 0.0
        self.spawn = 0.1
        self.down = False
        self.last = None
        self.p = 0.0
        self.ready = False
        self.ready_t = 0.0
        self.tip = random.randrange(len(TIPS))
        self.tip_t = 0.0
        self.pulse = 0.0
        self.board = a.art.theme("walnut").static
        self.glow = None
        self.rest = []
        self.rest_pos = [(150, 470), (300, 520), (700, 515), (850, 465), (500, 560)]
        self.hit_glow = None
        self.shadow = None

    def spawn_rest(self):
        a = self.app
        if not a.art.fruit or self.rest:
            return
        names = list(a.art.fruit)
        for i, (x, y) in enumerate(self.rest_pos):
            n = names[(i * 2 + 1) % len(names)]
            self.rest.append({"name": n, "x": x, "y": y, "rot": random.uniform(0, 360), "alive": True, "back": 0.0,
                              "ph": random.uniform(0, 6.28)})

    def update(self, dt):
        a = self.app
        self.t += dt
        if self.glow is None and a.art.glow is not None:
            self.glow = additive_glow(a.art.glow, 640, (30, 70, 110))
            self.hit_glow = additive_glow(a.art.glow, 150, (255, 210, 230))
        if self.loader and not self.loader.done:
            self.loader.step(0.006)
        elif not self.ready:
            self.ready = True
        self.spawn_rest()
        target = self.loader.progress if self.loader else 1.0
        self.p += (target - self.p) * min(1.0, dt * 8)
        self.pulse = max(0.0, self.pulse - dt * 3)
        self.tip_t += dt
        if self.tip_t > 3.2:
            self.tip_t, self.tip = 0.0, (self.tip + 1) % len(TIPS)
        self.spawn -= dt
        if self.spawn <= 0 and a.art.fruit:
            name = random.choice(list(a.art.fruit))
            art = a.art.fruit[name]
            x = random.uniform(120, W - 120)
            self.items.append(Item("fruit", art, name, art.r, x, H + 60, (W / 2 - x) * random.uniform(0.1, 0.35),
                                   -random.uniform(780, 980), random.uniform(-200, 200)))
            self.spawn = random.uniform(0.35, 0.8)
        for it in self.items:
            it.update(dt, 900)
        self.items = [i for i in self.items if i.alive and i.y < H + 140]
        for r in self.rest:
            if not r["alive"]:
                r["back"] -= dt
                if r["back"] <= 0:
                    r["alive"] = True
        for p in self.pieces:
            p.update(dt, 900)
        self.pieces = [p for p in self.pieces if p.y < H + 160]
        self.parts.update(dt)
        self.trail.update(a.now)
        if self.ready:
            self.ready_t += dt
            if self.ready_t > 1.1:
                self.finish()

    def finish(self):
        a = self.app
        a.audio.music("menu")
        a.go("menu")

    def _cut(self, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        if math.hypot(dx, dy) < 3:
            return
        for it in self.items:
            if it.alive and seg_dist(it.x, it.y, ax, ay, bx, by) < it.r + 8:
                it.alive = False
                self.hit(it.art, it.name, it.x, it.y, it.vx, it.vy, dx, dy)
        for r in self.rest:
            if r["alive"]:
                art = self.app.art.fruit[r["name"]]
                if seg_dist(r["x"], r["y"], ax, ay, bx, by) < art.r + 8:
                    r["alive"], r["back"] = False, 2.2
                    self.hit(art, r["name"], r["x"], r["y"], 0, -120, dx, dy)

    def hit(self, art, name, x, y, vx, vy, dx, dy):
        self.sliced += 1
        self.pulse = 1.0
        split_fruit(art, x, y, vx, vy, dx, dy, self.pieces)
        self.parts.burst(x, y, settings.FRUIT_JUICE[name], 18, 360, up=120)
        self.app.audio.slice_fruit(name)

    def handle(self, e):
        a = self.app
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.down, self.last = True, e.pos
            self.trail.clear()
        elif e.type == pygame.MOUSEBUTTONUP:
            self.down = False
        elif e.type == pygame.MOUSEMOTION and self.down:
            self.trail.add(*e.pos, a.now)
            self._cut(self.last or e.pos, e.pos)
            self.last = e.pos
        elif e.type == pygame.KEYDOWN and self.ready and e.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.finish()

    def draw(self, s):
        a = self.app
        s.blit(self.board, (0, 0))
        if self.glow is not None:
            s.blit(self.glow, self.glow.get_rect(center=(W // 2, 250)), special_flags=pygame.BLEND_RGB_ADD)
        sh = a.backdrop.shadows if hasattr(a.backdrop, "shadows") else None
        for r in self.rest:
            if r["alive"] and a.art.fruit:
                art = a.art.fruit[r["name"]]
                bob = math.sin(self.t * 1.6 + r["ph"]) * 3
                img = art.frame(r["rot"] + math.sin(self.t * 0.8 + r["ph"]) * 6)
                shd = pygame.Surface((art.r * 2, art.r), pygame.SRCALPHA) if sh is None else None
                if shd is not None:
                    pygame.draw.ellipse(shd, (0, 0, 0, 90), shd.get_rect())
                    s.blit(shd, shd.get_rect(center=(r["x"] + 8, r["y"] + art.r * 0.8)))
                s.blit(img, img.get_rect(center=(r["x"], r["y"] + bob)))
        for p in self.pieces:
            p.draw(s)
        for it in self.items:
            it.draw(s)
        self.parts.draw(s)
        self.trail.draw(s, a.save["blade"], a.now)
        logo = a.art.logo
        if logo is not None:
            k = 0.66 + 0.012 * math.sin(self.t * 2.4)
            if self.logo_img is None or abs(k - self.logo_k) > 0.004:
                self.logo_img = pygame.transform.smoothscale(logo, (int(logo.get_width() * k), int(logo.get_height() * k)))
                self.logo_k = k
            glitch_blit(s, self.logo_img, (W // 2, 140 + 6 * math.sin(self.t * 1.9)), self.t)
        bar = pygame.Rect(0, 0, 560, 34)
        bar.center = (W // 2, 300)
        segment_bar(s, bar, self.p, self.t)
        label = (self.loader.label if self.loader else "").upper()
        if self.ready:
            ui.blit_text(s, "SYSTEM ONLINE", 30, (W // 2, 352), ui.GREEN)
        else:
            ui.blit_text(s, f"> {label}...", 20, (bar.x, 352), ui.CYAN, "midleft")
            ui.blit_text(s, f"{int(self.p * 100)}%", 26, (bar.right, 352), ui.YELLOW, "midright")
        ui.blit_text(s, "FRUIT-OS // BOOT SEQUENCE v2.077", 18, (28, 26), (170, 190, 210), "topleft", outline=ui.INK)
        ui.blit_text(s, f"SLICED {self.sliced:03d}", 24, (W - 30, 26), ui.MAGENTA, "topright")
        ui.blit_text(s, "[ SWIPE TO SLICE WHILE THE SYSTEM LOADS ]", 20, (W // 2, H - 84), ui.YELLOW)
        ui.blit_text(s, "TIP // " + TIPS[self.tip], 18, (W // 2, H - 52), (210, 225, 240))
    logo_img = None
    logo_k = 0.0


# ---------------------------------------------------------------------- menu
class Menu(Scene):
    CX = 20
    CW, CH, GAP, CY = 206, 250, 16, 168

    def enter(self, **kw):
        a = self.app
        a.backdrop.set_theme(a.save["bg"])
        a.audio.music("menu")
        self.t = 0.0
        self.trail = BladeTrail()
        self.pieces = []
        self.parts = Particles(a.quality.particle_cap)
        self.pending = None
        self.down = False
        self.last = None
        self.hover = {m: 0.0 for m in settings.MODE_ORDER}
        self.panel = BoardPanel(a)
        self.btns = []
        x0, y = 40, 604
        for i, (label, cb) in enumerate([("AWARDS", lambda: a.go("achievements")),
                                         ("UNLOCKS", lambda: a.go("unlocks")),
                                         ("SOUND", lambda: a.go("settings", back="menu")),
                                         ("NAME", lambda: a.ask_name(None)),
                                         ("FULLSCREEN", a.toggle_fullscreen)]):
            self.btns.append(ui.Button(label, x0 + 80 + i * 164, y, cb, 150, 40, ui.CYAN, 20))
        self.diff_rects = {}
        for i, d in enumerate(settings.DIFFICULTY_ORDER):
            self.diff_rects[d] = pygame.Rect(self.CX + 20 + i * 138, 466, 130, 38)
        a.board.refresh(pygame.time.get_ticks(), force=True)
        logo = a.art.logo
        self.logo_img = pygame.transform.smoothscale(logo, (int(logo.get_width() * 0.5), int(logo.get_height() * 0.5)))
        self.card_glow = {m: additive_glow(a.art.glow, 190, ui.lerp_col(MODE_COLORS[m], (0, 0, 0), 0.55))
                          for m in settings.MODE_ORDER}

    def card_rect(self, i):
        return pygame.Rect(self.CX + i * (self.CW + self.GAP), self.CY, self.CW, self.CH)

    def update(self, dt):
        a = self.app
        self.t += dt
        a.backdrop.update(dt)
        for b in self.btns:
            b.update(dt, a.mouse)
        for i, m in enumerate(settings.MODE_ORDER):
            tgt = 1.0 if self.card_rect(i).collidepoint(a.mouse) and not self.pending else 0.0
            self.hover[m] += (tgt - self.hover[m]) * min(1.0, dt * 12)
        for p in self.pieces:
            p.update(dt, 1100)
        self.pieces = [p for p in self.pieces if p.y < H + 150]
        self.parts.cap = a.quality.particle_cap
        self.parts.update(dt)
        self.trail.update(a.now)
        self.panel.update(dt)
        if self.pending:
            self.pending[1] -= dt
            if self.pending[1] <= 0:
                mode = self.pending[0]
                self.pending = None
                a.start_game(mode)

    def choose(self, i):
        if self.pending:
            return
        a = self.app
        mode = settings.MODE_ORDER[i]
        r = self.card_rect(i)
        art = a.art.fruit[settings.MODE_FRUIT[mode]]
        cx, cy = r.centerx, r.y + 104
        split_fruit(art, cx, cy, 0, -150, 1, -0.4, self.pieces)
        self.parts.burst(cx, cy, settings.FRUIT_JUICE[settings.MODE_FRUIT[mode]], 30, 380)
        a.audio.slice_fruit(settings.MODE_FRUIT[mode])
        self.pending = [mode, 0.55]

    def handle(self, e):
        a = self.app
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.down, self.last = True, e.pos
            self.trail.clear()
            if self.panel.click(e.pos):
                return
            for b in self.btns:
                if b.hit(e.pos):
                    a.audio.sfx("click")
                    return
            for d, r in self.diff_rects.items():
                if r.collidepoint(e.pos):
                    a.save["difficulty"] = d
                    a.persist()
                    a.audio.sfx("click")
                    return
            for i in range(4):
                if self.card_rect(i).collidepoint(e.pos):
                    self.choose(i)
                    return
        elif e.type == pygame.MOUSEBUTTONUP:
            self.down = False
        elif e.type == pygame.MOUSEMOTION and self.down:
            self.trail.add(*e.pos, a.now)
            if self.last:
                for i in range(4):
                    r = self.card_rect(i)
                    if seg_dist(r.centerx, r.y + 104, *self.last, *e.pos) < 55:
                        self.choose(i)
            self.last = e.pos

    def draw(self, s):
        a = self.app
        a.backdrop.draw(s)
        glitch_blit(s, self.logo_img, (470, 84 + 5 * math.sin(self.t * 1.8)), self.t, 0.6)
        mx, my = a.mouse
        for i, mode in enumerate(settings.MODE_ORDER):
            r = self.card_rect(i)
            h = self.hover[mode]
            r = r.move(0, int(-10 * h))
            col = MODE_COLORS[mode]
            box = ui.neon_box(r.w, r.h, col, cut=22)
            s.blit(box, box.get_rect(center=r.center))
            if h > 0.02:
                hot = ui.neon_box(r.w, r.h, ui.lerp_col(col, (255, 255, 255), 0.3), fill=ui.lerp_col(ui.INK, col, 0.3),
                                  alpha=225, cut=22, glow=2.2).copy()
                hot.set_alpha(int(255 * h))
                s.blit(hot, hot.get_rect(center=r.center))
            fname = settings.MODE_FRUIT[mode]
            art = a.art.fruit[fname]
            ox = (mx - r.centerx) / r.w * 16 * h
            oy = (my - (r.y + 104)) / r.h * 16 * h
            g = self.card_glow[mode]
            s.blit(g, g.get_rect(center=(r.centerx + ox * 0.5, r.y + 104 + oy * 0.5)), special_flags=pygame.BLEND_RGB_ADD)
            ui.blit_text(s, MODE_TAGS[mode], 14, (r.x + 16, r.y + 14), col, "topleft", outline=ui.INK, ow=1)
            if not (self.pending and self.pending[0] == mode):
                spin = self.t * (30 + 70 * h) + i * 70
                img = art.frame(spin)
                s.blit(img, img.get_rect(center=(r.centerx + ox, r.y + 104 + oy + 5 * math.sin(self.t * 2 + i))))
            title, sub = settings.MODES[mode]
            ui.blit_text(s, title.upper(), 24 if len(title) < 10 else 19, (r.centerx, r.y + 176), (255, 255, 255))
            for j, line in enumerate(sub.split(" - ")[:2]):
                ui.blit_text(s, line.upper(), 14, (r.centerx, r.y + 202 + j * 16), (190, 215, 235), outline=ui.INK, ow=1)
            ui.blit_text(s, f"HI-SCORE {a.save['best'].get(mode, 0)}", 15, (r.centerx, r.bottom - 14), ui.YELLOW,
                         outline=ui.INK, ow=1)
        for p in self.pieces:
            p.draw(s)
        self.parts.draw(s)
        ui.blit_text(s, "DIFFICULTY", 18, (self.CX + 20, 450), ui.CYAN, "midleft")
        for d, r in self.diff_rects.items():
            on = a.save["difficulty"] == d
            col = {"easy": ui.GREEN, "normal": ui.YELLOW, "hard": ui.MAGENTA}[d]
            if on:
                s.blit(ui.neon_box(r.w, r.h, col, solid=True, cut=10, glow=1.6), ui.neon_box(r.w, r.h, col, solid=True,
                       cut=10, glow=1.6).get_rect(center=r.center))
            else:
                box = ui.neon_box(r.w, r.h, ui.lerp_col(col, (40, 30, 70), 0.55), cut=10, glow=0.4)
                s.blit(box, box.get_rect(center=r.center))
            ui.blit_text(s, settings.DIFFICULTY[d]["label"].upper(), 20, r.center, (12, 6, 20) if on else (220, 225, 240),
                         outline=None if on else ui.INK)
        ch, st = progress.daily_state(a.save)
        done = st["done"]
        dr = pygame.Rect(self.CX + 440, 452, 436, 62)
        dcol = ui.GREEN if done else ui.YELLOW
        box = ui.neon_box(dr.w, dr.h, dcol, cut=14)
        s.blit(box, box.get_rect(center=dr.center))
        ui.blit_text(s, "DAILY CONTRACT" + ("  // COMPLETE" if done else ""), 15, (dr.x + 18, dr.y + 11), dcol, "topleft",
                     outline=None)
        ui.blit_text(s, ch["text"].upper(), 21, (dr.x + 18, dr.y + 38), (255, 255, 255), "midleft")
        nb = progress.next_board(a.save)
        pr = pygame.Rect(self.CX + 20, 524, 856, 38)
        box = ui.neon_box(pr.w, pr.h, ui.VIOLET, cut=12, glow=0.6)
        s.blit(box, box.get_rect(center=pr.center))
        if nb:
            frac = min(1.0, nb[2] / nb[1])
            bar = pygame.Rect(pr.x + 380, pr.y + 11, 440, 16)
            pygame.draw.rect(s, (14, 8, 30), bar)
            n = 30
            for k in range(n):
                if (k + 1) / n <= frac:
                    pygame.draw.rect(s, ui.lerp_col(ui.VIOLET, ui.MAGENTA, k / n), (bar.x + k * bar.w / n + 1, bar.y, bar.w / n - 3, bar.h))
                else:
                    pygame.draw.rect(s, (38, 26, 66), (bar.x + k * bar.w / n + 1, bar.y, bar.w / n - 3, bar.h))
            ui.blit_text(s, f"NEXT BOARD: {settings.BOARD_NAMES[nb[0]].upper()}", 19, (pr.x + 20, pr.centery), (255, 230, 150),
                         "midleft")
            ui.blit_text(s, f"{nb[2]} / {nb[1]}", 16, (bar.right + 10, bar.centery), (255, 255, 255), "midleft", ow=1)
        else:
            ui.blit_text(s, "ALL BOARDS UNLOCKED // MASTER CHEF", 19, pr.center, ui.GREEN)
        for b in self.btns:
            b.draw(s)
        name = (a.save.get("name") or "?").upper()
        ui.blit_text(s, f"RUNNER // {name}", 18, (18, 12), (190, 215, 235), "topleft", outline=ui.INK)
        self.panel.draw(s)
        self.trail.draw(s, a.save["blade"], a.now)


# ------------------------------------------------------------------ settings
class Settings(Scene):
    def enter(self, back="menu"):
        a = self.app
        self.back = back
        self.sl_music = ui.Slider("Music", 400, 250, 340, a.save["music"])
        self.sl_sfx = ui.Slider("Effects", 400, 330, 340, a.save["sfx"])
        self.btn_mute = ui.Button("", W // 2, 410, self.toggle_mute, 300, 48, ui.CYAN)
        self.btn_back = ui.Button("BACK", W // 2, 500, self.close, 220, 52, ui.YELLOW, 26, True)
        self.btns = [self.btn_mute, self.btn_back]
        self.sync()

    def sync(self):
        self.btn_mute.label = "SOUND: OFF" if self.app.save["mute"] else "SOUND: ON"

    def toggle_mute(self):
        self.app.toggle_mute()
        self.sync()

    def close(self):
        a = self.app
        a.audio.sfx("click")
        a.persist()
        if self.back == "play":
            a.resume_scene("play")
        else:
            a.go(self.back)

    def update(self, dt):
        self.app.backdrop.update(dt)
        for b in self.btns:
            b.update(dt, self.app.mouse)

    def handle(self, e):
        a = self.app
        if self.sl_music.event(e):
            a.save["music"] = self.sl_music.value
            a.audio.apply_volume()
        if self.sl_sfx.event(e):
            a.save["sfx"] = self.sl_sfx.value
        if e.type == pygame.MOUSEBUTTONUP and a.save["sfx"] > 0:
            a.audio.sfx("slice_apple_0", 0.8)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for b in self.btns:
                if b.hit(e.pos):
                    return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.close()

    def draw(self, s):
        a = self.app
        a.backdrop.draw(s)
        s.blit(ui.panel(560, 420, (30, 16, 40, 225)), (220, 130))
        ui.blit_text(s, "Sound", 48, (W // 2, 190), (252, 238, 10))
        self.sl_music.draw(s)
        self.sl_sfx.draw(s)
        for b in self.btns:
            b.draw(s)


# -------------------------------------------------------------------- awards
class Awards(Scene):
    def enter(self, **kw):
        self.btn = ui.Button("BACK", W // 2, 604, self.close, 200, 46, ui.YELLOW, 24, True)
        self.t = 0.0

    def close(self):
        self.app.audio.sfx("click")
        self.app.go("menu")

    def update(self, dt):
        self.t += dt
        self.app.backdrop.update(dt)
        self.btn.update(dt, self.app.mouse)

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.btn.hit(e.pos)
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.close()

    def draw(self, s):
        a = self.app
        a.backdrop.draw(s)
        s.blit(ui.panel(920, 560, (30, 16, 40, 225)), (40, 40))
        got = a.save["ach"]
        ui.blit_text(s, f"Achievements  {len(got)}/{len(progress.ACHIEVEMENTS)}", 40, (W // 2, 84), (252, 238, 10))
        for i, (aid, title, desc, _t) in enumerate(progress.ACHIEVEMENTS):
            col, row = i % 2, i // 2
            r = pygame.Rect(70 + col * 440, 130 + row * 74, 420, 64)
            have = aid in got
            s.blit(ui.pill(r.w, r.h, (60, 150, 80) if have else (70, 60, 90), 20), r.topleft)
            pygame.draw.circle(s, (252, 238, 10) if have else (110, 100, 120), (r.x + 34, r.centery + 2), 20)
            ui.blit_text(s, "OK" if have else "?", 18, (r.x + 34, r.centery + 2), (60, 30, 10), outline=None)
            ui.blit_text(s, title, 22, (r.x + 70, r.y + 8), (255, 255, 255), "topleft")
            ui.blit_text(s, desc, 14, (r.x + 70, r.y + 38), (235, 225, 210), "topleft", outline=None)
        self.btn.draw(s)


# ------------------------------------------------------------------- unlocks
class Unlocks(Scene):
    def enter(self, **kw):
        self.btn = ui.Button("BACK", W // 2, 604, self.close, 200, 46, ui.YELLOW, 24, True)
        self.t = 0.0
        self.blade_rects = {b: pygame.Rect(70 + i * 178, 160, 160, 130) for i, b in enumerate(settings.BLADES)}
        self.bg_rects = {b: pygame.Rect(48 + i * 150, 370, 140, 91) for i, b in enumerate(settings.BOARDS)}
        self.thumbs = {}

    def close(self):
        self.app.audio.sfx("click")
        self.app.go("menu")

    def thumb(self, name):
        if name not in self.thumbs:
            t = pygame.transform.smoothscale(self.app.art.theme(name).static, (140, 91))
            if name not in self.app.save["unlocks"]["bg"]:
                t.fill((70, 70, 80), special_flags=pygame.BLEND_RGB_MULT)
            self.thumbs[name] = t
        return self.thumbs[name]

    def update(self, dt):
        self.t += dt
        self.app.backdrop.update(dt)
        self.btn.update(dt, self.app.mouse)

    def handle(self, e):
        a = self.app
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn.hit(e.pos):
                return
            for group, rects, key in (("blade", self.blade_rects, "blade"), ("bg", self.bg_rects, "bg")):
                for item, r in rects.items():
                    if r.collidepoint(e.pos) and item in a.save["unlocks"][group]:
                        a.save[key] = item
                        a.persist()
                        a.audio.sfx("click")
                        if key == "bg":
                            a.backdrop.set_theme(item)
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.close()

    def draw(self, s):
        a = self.app
        a.backdrop.draw(s)
        s.blit(ui.panel(920, 560, (30, 16, 40, 225)), (40, 40))
        ui.blit_text(s, "Blades & Boards", 40, (W // 2, 84), (252, 238, 10))
        ui.blit_text(s, "Blades", 22, (70, 130), (255, 255, 255), "midleft")
        for b, r in self.blade_rects.items():
            own = b in a.save["unlocks"]["blade"]
            sel = a.save["blade"] == b
            s.blit(ui.panel(r.w, r.h, (50, 34, 70, 240), (120, 240, 100) if sel else (252, 238, 10) if own else (90, 80, 100), 16), r.topleft)
            if own:
                self.draw_blade_preview(s, b, r)
            ui.blit_text(s, b.title(), 20, (r.centerx, r.y + 12))
            req = progress.unlock_text(progress.UNLOCKS["blade"][b])
            ui.blit_text(s, "Equipped" if sel else req, 14, (r.centerx, r.bottom - 14),
                         (140, 240, 100) if sel else (230, 220, 210), outline=None)
        ui.blit_text(s, "Cutting boards - score high to unlock better ones", 22, (70, 340), (255, 255, 255), "midleft")
        for b, r in self.bg_rects.items():
            own = b in a.save["unlocks"]["bg"]
            sel = a.save["bg"] == b
            s.blit(self.thumb(b), r.topleft)
            if not own:
                ui.blit_text(s, "LOCKED", 18, r.center, (230, 225, 235))
            pygame.draw.rect(s, (120, 240, 100) if sel else (252, 238, 10) if own else (90, 80, 100), r, 4, border_radius=8)
            ui.blit_text(s, settings.BOARD_NAMES[b], 14, (r.centerx, r.bottom + 16), outline=(40, 15, 5), ow=1)
            req = progress.unlock_text(progress.UNLOCKS["bg"][b])
            ui.blit_text(s, "On the table" if sel else req, 14, (r.centerx, r.bottom + 34),
                         (140, 240, 100) if sel else (230, 220, 210), outline=None)
        self.btn.draw(s)

    def draw_blade_preview(self, s, style, r):
        from .effects import BladeTrail
        bt = BladeTrail()
        now = self.t
        for i in range(12):
            x = r.x + 20 + i * 10
            y = r.centery + 12 + math.sin(i * 0.5 + self.t * 4) * 14
            bt.add(x, y, now - (11 - i) * 0.012)
        bt.draw(s, style, now)


# ---------------------------------------------------------------------- name
class NameEntry(Scene):
    def enter(self, cb=None):
        self.cb = cb
        self.buf = self.app.save.get("name", "")
        self.t = 0.0

    def finish(self):
        a = self.app
        a.save["name"] = clean_name(self.buf)
        a.persist()
        a.audio.sfx("click")
        cb, self.cb = self.cb, None
        a.go("menu")
        if cb:
            cb()

    def update(self, dt):
        self.t += dt
        self.app.backdrop.update(dt)

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.finish()
            elif e.key == pygame.K_ESCAPE and self.app.save.get("name"):
                self.app.go("menu")
            elif e.key == pygame.K_BACKSPACE:
                self.buf = self.buf[:-1]
            elif e.unicode and e.unicode.isprintable() and len(self.buf) < 12:
                self.buf += e.unicode

    def draw(self, s):
        self.app.backdrop.draw(s)
        s.blit(ui.panel(560, 300, (30, 16, 40, 230)), (220, 170))
        ui.blit_text(s, "Choose a nickname", 42, (W // 2, 225), (252, 238, 10))
        ui.blit_text(s, "Do NOT use your real name - it shows on the public leaderboard.", 18, (W // 2, 270))
        box = pygame.Rect(0, 0, 360, 60)
        box.center = (W // 2, 340)
        pygame.draw.rect(s, (255, 255, 255), box, border_radius=14)
        txt = self.buf + ("|" if int(self.t * 2) % 2 == 0 else "")
        ui.blit_text(s, txt, 34, box.center, (40, 20, 10), outline=None)
        ui.blit_text(s, "Press Enter to play", 22, (W // 2, 425), (255, 240, 170))

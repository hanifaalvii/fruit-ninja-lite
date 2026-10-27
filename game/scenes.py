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
    "Slice fruit in quick chains for a bigger combo multiplier!",
    "Cut 3 or more fruit in a single swipe for a bonus.",
    "Bombs hurt. Let them fall!",
    "Grab the glowing orbs: slow-mo, double score and fruit rain.",
    "Every 8th wave in Classic brings a giant watermelon. Keep slicing!",
    "Score big to unlock new blades and backgrounds.",
    "Finish today's daily challenge for an achievement.",
]
CARD_COLORS = {"classic": (214, 70, 40), "arcade": (232, 140, 20), "zen": (50, 160, 90), "sudden": (130, 70, 190)}


# ------------------------------------------------------------------- loading
class Loading(Scene):
    def enter(self, loader=None):
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
        self.tip = random.randrange(len(TIPS))
        self.tip_t = 0.0
        self.pulse = 0.0
        self.grad = pygame.Surface((W, H))
        for y in range(H):
            self.grad.fill(ui.lerp_col((255, 140, 60), (96, 30, 120), y / H), (0, y, W, 1))
        self.rays = None
        self.logo_img = None

    def update(self, dt):
        a = self.app
        self.t += dt
        if self.loader and not self.loader.done:
            self.loader.step(0.006)
        elif not self.ready:
            self.ready = True
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
            self.spawn = random.uniform(0.3, 0.7)
        for it in self.items:
            it.update(dt, 900)
        self.items = [i for i in self.items if i.alive and i.y < H + 140]
        for p in self.pieces:
            p.update(dt, 900)
        self.pieces = [p for p in self.pieces if p.y < H + 160]
        self.parts.update(dt)
        self.trail.update(a.now)
        if self.ready and a.audio.cur is None and a.audio.music_snd:
            a.audio.music("menu")

    def _cut(self, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        if math.hypot(dx, dy) < 3:
            return
        for it in self.items:
            if it.alive and seg_dist(it.x, it.y, ax, ay, bx, by) < it.r + 8:
                it.alive = False
                self.sliced += 1
                self.pulse = 1.0
                split_fruit(it.art, it.x, it.y, it.vx, it.vy, dx, dy, self.pieces)
                self.parts.burst(it.x, it.y, settings.FRUIT_JUICE[it.name], 16, 340)
                self.app.audio.slice_fruit(it.name)

    def handle(self, e):
        a = self.app
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.ready:
                a.audio.sfx("click")
                a.audio.music("menu")
                a.go("menu")
                return
            self.down, self.last = True, e.pos
            self.trail.clear()
        elif e.type == pygame.MOUSEBUTTONUP:
            self.down = False
        elif e.type == pygame.MOUSEMOTION and self.down:
            self.trail.add(*e.pos, a.now)
            self._cut(self.last or e.pos, e.pos)
            self.last = e.pos
        elif e.type == pygame.KEYDOWN and self.ready and e.key in (pygame.K_RETURN, pygame.K_SPACE):
            a.audio.music("menu")
            a.go("menu")

    def draw(self, s):
        a = self.app
        s.blit(self.grad, (0, 0))
        if a.art.glow is not None:
            if self.rays is None:
                self.rays = additive_glow(a.art.glow, 700, (255, 170, 90))
            s.blit(self.rays, self.rays.get_rect(center=(W // 2, H // 2 - 30)), special_flags=pygame.BLEND_RGB_ADD)
        for p in self.pieces:
            p.draw(s)
        for it in self.items:
            it.draw(s)
        self.parts.draw(s)
        self.trail.draw(s, a.save["blade"], a.now)
        logo = a.art.logo
        if logo is not None:
            if self.logo_img is None:
                self.logo_img = pygame.transform.smoothscale(logo, (int(logo.get_width() * 0.64), int(logo.get_height() * 0.64)))
            s.blit(self.logo_img, self.logo_img.get_rect(center=(W // 2, 150 + 8 * math.sin(self.t * 2.4))))
        bar = pygame.Rect(0, 0, 460, 26)
        bar.center = (W // 2, H // 2 + 70)
        pygame.draw.rect(s, (30, 12, 30), bar.inflate(8, 8), border_radius=18)
        fill = bar.copy()
        fill.w = max(0, int(bar.w * self.p))
        if fill.w > 6:
            pygame.draw.rect(s, ui.lerp_col((120, 220, 60), (255, 220, 60), self.pulse), fill, border_radius=13)
            pygame.draw.rect(s, (255, 255, 255, 90), fill.inflate(-8, -16).move(0, -5), border_radius=6)
        pygame.draw.rect(s, (255, 210, 74), bar.inflate(8, 8), 3, border_radius=18)
        if self.ready:
            pulse = 1.0 + 0.06 * math.sin(self.t * 6)
            ui.blit_text(s, "TAP TO START", 40, (W // 2, H // 2 + 125), (255, 240, 120), scale=pulse)
        else:
            label = self.loader.label if self.loader else ""
            ui.blit_text(s, f"{label}...  {int(self.p * 100)}%", 20, (W // 2, H // 2 + 118), (255, 240, 220))
        ui.blit_text(s, TIPS[self.tip], 20, (W // 2, H - 62), (255, 230, 170))
        ui.blit_text(s, "Swipe to slice the fruit while you wait!", 18, (W // 2, H - 30), (255, 255, 255))
        if self.sliced:
            ui.blit_text(s, f"Sliced: {self.sliced}", 30, (W // 2, 36))


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
        grey = (96, 70, 130)
        self.btns = []
        x0, y = 40, 600
        for i, (label, cb) in enumerate([("Awards", lambda: a.go("achievements")),
                                         ("Unlocks", lambda: a.go("unlocks")),
                                         ("Sound", lambda: a.go("settings", back="menu")),
                                         ("Name", lambda: a.ask_name(None)),
                                         ("Fullscreen", a.toggle_fullscreen)]):
            self.btns.append(ui.Button(label, x0 + 80 + i * 164, y, cb, 150, 42, grey, 20))
        self.diff_rects = {}
        for i, d in enumerate(settings.DIFFICULTY_ORDER):
            self.diff_rects[d] = pygame.Rect(self.CX + 20 + i * 138, 466, 130, 38)
        a.board.refresh(pygame.time.get_ticks(), force=True)
        logo = a.art.logo
        self.logo_img = pygame.transform.smoothscale(logo, (int(logo.get_width() * 0.5), int(logo.get_height() * 0.5)))
        self.card_glow = pygame.transform.smoothscale(a.art.glow, (150, 150))

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
        cx, cy = r.centerx, r.y + 100
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
                    if seg_dist(r.centerx, r.y + 100, *self.last, *e.pos) < 55:
                        self.choose(i)
            self.last = e.pos

    def draw(self, s):
        a = self.app
        a.backdrop.draw(s)
        s.blit(self.logo_img, self.logo_img.get_rect(center=(470, 80 + 5 * math.sin(self.t * 1.8))))
        mx, my = a.mouse
        for i, mode in enumerate(settings.MODE_ORDER):
            r = self.card_rect(i)
            h = self.hover[mode]
            r = r.move(0, int(-10 * h))
            col = CARD_COLORS[mode]
            s.blit(ui.pill(r.w, r.h, col, 28), r.topleft)
            fname = settings.MODE_FRUIT[mode]
            art = a.art.fruit[fname]
            ox = (mx - r.centerx) / r.w * 16 * h
            oy = (my - (r.y + 100)) / r.h * 16 * h
            g = self.card_glow
            s.blit(g, g.get_rect(center=(r.centerx + ox * 0.5, r.y + 100 + oy * 0.5)))
            if not (self.pending and self.pending[0] == mode):
                spin = self.t * (30 + 70 * h) + i * 70
                img = art.frame(spin)
                s.blit(img, img.get_rect(center=(r.centerx + ox, r.y + 100 + oy + 5 * math.sin(self.t * 2 + i))))
            title, sub = settings.MODES[mode]
            ui.blit_text(s, title, 28 if len(title) < 10 else 23, (r.centerx, r.y + 178))
            for j, line in enumerate(sub.split(" - ")[:2]):
                ui.blit_text(s, line, 14, (r.centerx, r.y + 202 + j * 17), (255, 240, 210), outline=(60, 20, 10), ow=1)
            ui.blit_text(s, f"Best {a.save['best'].get(mode, 0)}", 15, (r.centerx, r.bottom - 12), (255, 230, 120))
        for p in self.pieces:
            p.draw(s)
        self.parts.draw(s)
        # difficulty selector
        ui.blit_text(s, "Difficulty", 18, (self.CX + 20, 452), (255, 255, 255), "midleft")
        for d, r in self.diff_rects.items():
            on = a.save["difficulty"] == d
            col = {"easy": (60, 170, 90), "normal": (232, 160, 30), "hard": (210, 60, 60)}[d]
            s.blit(ui.pill(r.w, r.h, col if on else (90, 80, 100), 18), r.topleft)
            ui.blit_text(s, settings.DIFFICULTY[d]["label"], 20, r.center, (255, 255, 255) if on else (210, 200, 215))
        ch, st = progress.daily_state(a.save)
        done = st["done"]
        dr = pygame.Rect(self.CX + 440, 452, 436, 62)
        s.blit(ui.panel(dr.w, dr.h, (30, 16, 40, 200), (255, 210, 74) if not done else (120, 220, 90), 16), dr.topleft)
        ui.blit_text(s, "DAILY CHALLENGE" + ("  - DONE!" if done else ""), 15, (dr.x + 14, dr.y + 8),
                     (255, 210, 74) if not done else (140, 240, 100), "topleft", outline=None)
        ui.blit_text(s, ch["text"], 22, (dr.x + 14, dr.y + 36), (255, 255, 255), "midleft")
        nb = progress.next_board(a.save)
        pr = pygame.Rect(self.CX + 20, 530, 856, 30)
        s.blit(ui.panel(pr.w, pr.h, (30, 16, 40, 200), (255, 210, 74), 14), pr.topleft)
        if nb:
            frac = min(1.0, nb[2] / nb[1])
            bar = pygame.Rect(pr.x + 372, pr.y + 8, 460, 14)
            pygame.draw.rect(s, (20, 10, 24), bar, border_radius=7)
            if frac > 0:
                pygame.draw.rect(s, (255, 190, 60), (bar.x, bar.y, max(8, int(bar.w * frac)), bar.h), border_radius=7)
            ui.blit_text(s, f"Next board: {settings.BOARD_NAMES[nb[0]]}", 17, (pr.x + 14, pr.centery), (255, 230, 150),
                         "midleft")
            ui.blit_text(s, f"{nb[2]} / {nb[1]}", 14, (bar.centerx, bar.centery), outline=(20, 10, 24), ow=1)
        else:
            ui.blit_text(s, "Every board unlocked - you are a master chef!", 17, pr.center, (140, 240, 100))
        for b in self.btns:
            b.draw(s)
        name = a.save.get("name") or "?"
        ui.blit_text(s, f"Player: {name}", 16, (14, 14), (255, 255, 255), "topleft")
        self.panel.draw(s)
        self.trail.draw(s, a.save["blade"], a.now)


# ------------------------------------------------------------------ settings
class Settings(Scene):
    def enter(self, back="menu"):
        a = self.app
        self.back = back
        self.sl_music = ui.Slider("Music", 400, 250, 340, a.save["music"])
        self.sl_sfx = ui.Slider("Effects", 400, 330, 340, a.save["sfx"])
        self.btn_mute = ui.Button("", W // 2, 410, self.toggle_mute, 300, 48, (96, 70, 130))
        self.btn_back = ui.Button("Back", W // 2, 500, self.close, 220, 52)
        self.btns = [self.btn_mute, self.btn_back]
        self.sync()

    def sync(self):
        self.btn_mute.label = "Sound: OFF" if self.app.save["mute"] else "Sound: ON"

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
        ui.blit_text(s, "Sound", 48, (W // 2, 190), (255, 210, 74))
        self.sl_music.draw(s)
        self.sl_sfx.draw(s)
        for b in self.btns:
            b.draw(s)


# -------------------------------------------------------------------- awards
class Awards(Scene):
    def enter(self, **kw):
        self.btn = ui.Button("Back", W // 2, 604, self.close, 200, 46)
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
        ui.blit_text(s, f"Achievements  {len(got)}/{len(progress.ACHIEVEMENTS)}", 40, (W // 2, 84), (255, 210, 74))
        for i, (aid, title, desc, _t) in enumerate(progress.ACHIEVEMENTS):
            col, row = i % 2, i // 2
            r = pygame.Rect(70 + col * 440, 130 + row * 74, 420, 64)
            have = aid in got
            s.blit(ui.pill(r.w, r.h, (60, 150, 80) if have else (70, 60, 90), 20), r.topleft)
            pygame.draw.circle(s, (255, 210, 74) if have else (110, 100, 120), (r.x + 34, r.centery + 2), 20)
            ui.blit_text(s, "OK" if have else "?", 18, (r.x + 34, r.centery + 2), (60, 30, 10), outline=None)
            ui.blit_text(s, title, 22, (r.x + 70, r.y + 8), (255, 255, 255), "topleft")
            ui.blit_text(s, desc, 14, (r.x + 70, r.y + 38), (235, 225, 210), "topleft", outline=None)
        self.btn.draw(s)


# ------------------------------------------------------------------- unlocks
class Unlocks(Scene):
    def enter(self, **kw):
        self.btn = ui.Button("Back", W // 2, 604, self.close, 200, 46)
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
        ui.blit_text(s, "Blades & Boards", 40, (W // 2, 84), (255, 210, 74))
        ui.blit_text(s, "Blades", 22, (70, 130), (255, 255, 255), "midleft")
        for b, r in self.blade_rects.items():
            own = b in a.save["unlocks"]["blade"]
            sel = a.save["blade"] == b
            s.blit(ui.panel(r.w, r.h, (50, 34, 70, 240), (120, 240, 100) if sel else (255, 210, 74) if own else (90, 80, 100), 16), r.topleft)
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
            pygame.draw.rect(s, (120, 240, 100) if sel else (255, 210, 74) if own else (90, 80, 100), r, 4, border_radius=8)
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
        ui.blit_text(s, "Choose a nickname", 42, (W // 2, 225), (255, 210, 74))
        ui.blit_text(s, "Do NOT use your real name - it shows on the public leaderboard.", 18, (W // 2, 270))
        box = pygame.Rect(0, 0, 360, 60)
        box.center = (W // 2, 340)
        pygame.draw.rect(s, (255, 255, 255), box, border_radius=14)
        txt = self.buf + ("|" if int(self.t * 2) % 2 == 0 else "")
        ui.blit_text(s, txt, 34, box.center, (40, 20, 10), outline=None)
        ui.blit_text(s, "Press Enter to play", 22, (W // 2, 425), (255, 240, 170))

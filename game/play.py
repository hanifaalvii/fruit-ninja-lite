"""The gameplay scene: all four modes, combos, power-ups, boss, pause and game over."""
import math
import random

import pygame

from . import progress, settings, ui
from .common import BoardPanel, Scene, split_fruit
from .effects import BladeTrail, Flashes, Particles, Shadows, Shake, SplatLayer, TimeScale
from .entities import Item, seg_dist
from .modes import WaveDirector
from .world import additive_glow
from .scoring import Combo, POWERUPS, PowerUps, swipe_bonus

W, H = settings.W, settings.H
COMBO_COLORS = {2: (255, 240, 120), 3: (255, 190, 70), 4: (255, 120, 60), 5: (255, 70, 110)}
PU_COLORS = {"slowmo": (90, 170, 255), "double": (255, 190, 40), "rain": (110, 220, 120)}


class Play(Scene):
    def enter(self, mode="classic", difficulty=None):
        a = self.app
        self.mode = mode
        self.dkey = difficulty or a.save["difficulty"]
        self.diff = settings.DIFFICULTY[self.dkey]
        self.rng = random.Random()
        self.dir = WaveDirector(mode, self.dkey, self.rng)
        self.items, self.pieces, self.texts, self.hits = [], [], [], []
        self.parts = Particles(a.quality.particle_cap)
        self.splats = SplatLayer(a.art)
        self.trail = BladeTrail()
        self.shadows = Shadows()
        self.fx = Flashes()
        self.hit_glow = additive_glow(a.art.glow, 170, (255, 235, 190))
        self.shake = Shake()
        self.tscale = TimeScale()
        self.combo = Combo()
        self.pw = PowerUps()
        self.score = 0
        self.t = 0.0
        self.spawn_t = 0.8
        self.wave = 0
        self.lives = 1 if mode == "sudden" else (self.diff["lives"] if mode == "classic" else 0)
        self.max_lives = self.lives
        self.time_left = {"arcade": 60.0, "zen": 90.0}.get(mode)
        self.freeze_t = self.frenzy_t = 0.0
        self.rain_acc = 0.0
        self.stats = {"sliced": 0, "best_combo": 0, "max_swipe": 0, "boss_down": 0, "bombs": 0}
        self.swipe_n = 0
        self.swipe_t = 0.0
        self.swipe_pos = (0, 0)
        self.state = "play"
        self.banner = None
        self.flash = 0.0
        self.flash_col = (255, 40, 30)
        self.flash_surf = pygame.Surface((W, H))
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self.dim.fill((15, 5, 30, 150))
        self.down = False
        self.last = None
        self.boss = None
        self.over_t = 0.0
        self.result = None
        self.tense = False
        self.panel = BoardPanel(a)
        self.btn_pause = ui.Button("II", W - 44, 40, self.pause, 58, 46, (96, 70, 130), 22)
        self.pause_btns = [ui.Button("Resume", W // 2, 270, self.resume, 260, 52),
                           ui.Button("Sound", W // 2, 340, self.open_sound, 260, 52, (96, 70, 130)),
                           ui.Button("Menu", W // 2, 410, self.to_menu, 260, 52, (96, 70, 130))]
        self.over_btns = [ui.Button("Play Again", W // 2 - 140, 560, self.again, 250, 52, (60, 170, 90)),
                          ui.Button("Menu", W // 2 + 140, 560, self.to_menu, 250, 52, (96, 70, 130))]
        a.backdrop.set_theme(a.save["bg"])
        a.audio.music("play")
        a.audio.sfx("click")

    # ------------------------------------------------------------- buttons
    def pause(self):
        if self.state == "play":
            self.app.audio.sfx("click")
            self.state = "pause"
            self.down = False

    def resume(self):
        self.app.audio.sfx("click")
        self.state = "play"

    def open_sound(self):
        self.app.audio.sfx("click")
        self.app.go("settings", back="play")

    def to_menu(self):
        self.app.audio.sfx("click")
        self.app.go("menu")

    def again(self):
        self.app.audio.sfx("click")
        self.app.go("play", mode=self.mode, difficulty=self.dkey)

    # ------------------------------------------------------------- spawning
    def gravity(self):
        d = self.dir.ramp(self.t)
        return H * 1.15 * self.diff["speed"] * (1 + (0.25 * d if self.mode == "sudden" else 0))

    def throw(self, kind, offset=0.0):
        a = self.app
        g = self.gravity()
        name, gscale, hp, r = None, 1.0, 1, 36
        if kind == "boss":
            if self.boss is not None:
                return
            art, r, gscale = a.art.boss, 110, 0.4
            hp = max(6, round(10 * self.diff["count"]))
            height = H * 0.5
        elif kind == "bomb":
            art, r = a.art.bomb, 34
            height = H * random.uniform(0.55, 0.85)
        elif kind in a.art.orbs:
            art, r = a.art.orbs[kind], 38
            height = H * random.uniform(0.55, 0.8)
        else:
            name = random.choice(settings.FRUITS)
            art = a.art.fruit[name]
            r = art.r
            height = H * random.uniform(0.55, 0.85)
        vy = -math.sqrt(2 * g * gscale * height)
        x = random.uniform(W * 0.15, W * 0.85) if kind != "boss" else random.uniform(W * 0.38, W * 0.62)
        vx = (W / 2 - x) * random.uniform(0.1, 0.5) + random.uniform(-90, 90)
        if kind == "boss":
            vx *= 0.3
        it = Item(kind, art, name, r, x, H + r + offset, vx, vy, random.uniform(-220, 220) if kind != "boss" else 25,
                  hp, gscale=gscale)
        if kind == "boss":
            self.boss = it
            self.banner = ["GIANT WATERMELON!", 1.8, (255, 120, 90)]
            a.audio.sfx("powerup", 0.7)
        self.items.append(it)

    def rain_fruit(self):
        a = self.app
        name = random.choice(settings.FRUITS)
        art = a.art.fruit[name]
        self.items.append(Item("fruit", art, name, art.r, random.uniform(60, W - 60), -50, random.uniform(-40, 40),
                               random.uniform(40, 120), random.uniform(-200, 200), bonus=True, gscale=0.45))

    def spawn_wave(self):
        self.wave += 1
        frenzy = self.frenzy_t > 0
        for s in self.dir.next_wave(self.t, self.wave, frenzy):
            self.throw(s.kind, s.offset)
        self.spawn_t = self.dir.interval(self.t, frenzy)
        self.app.audio.sfx("swoosh", 0.4)

    # -------------------------------------------------------------- scoring
    def add_text(self, s, x, y, col=(255, 255, 255), size=30, life=0.9):
        self.texts.append([s, x, min(max(x, 40), W - 40), y, life, life, col, size])

    def juice(self, x, y, color, big=1.0, n=14):
        self.parts.burst(x, y, color, int(n * big), 360 * min(1.5, big), up=120)
        self.splats.add(x, y, color, random.uniform(70, 110) * big, self.app.quality.splat_cap)

    def finish_swipe(self):
        n = self.swipe_n
        self.stats["max_swipe"] = max(self.stats["max_swipe"], n)
        if n >= 3:
            bonus = swipe_bonus(n) * self.pw.score_mult(self.t)
            self.score += bonus
            label = {3: "TRIPLE!", 4: "QUAD!"}.get(n, f"{n}x SLICE!")
            self.add_text(f"{label} +{bonus}", self.swipe_pos[0], self.swipe_pos[1] - 40, (120, 255, 200), 40, 1.2)
            self.app.audio.sfx("powerup", 0.6)
        self.swipe_n = 0

    def slice_item(self, it, dx, dy):
        a = self.app
        k = it.kind
        if k == "boss":
            self.hit_boss(it)
            return
        it.alive = False
        if k == "fruit":
            split_fruit(it.art, it.x, it.y, it.vx, it.vy, dx, dy, self.pieces)
            self.juice(it.x, it.y, settings.FRUIT_JUICE[it.name])
            self.fx.cut(it.x, it.y, dx, dy, it.r * 1.6)
            self.hits.append([it.x, it.y, 0.18])
            n = math.hypot(dx, dy) or 1.0
            a.backdrop.scar((int(it.x - dx / n * it.r), int(it.y - dy / n * it.r)),
                            (int(it.x + dx / n * it.r), int(it.y + dy / n * it.r)))
            a.audio.slice_fruit(it.name)
            mult = self.combo.hit(self.t)
            pts = 2 * mult * self.pw.score_mult(self.t) * (2 if self.frenzy_t > 0 else 1)
            self.score += pts
            self.stats["sliced"] += 1
            self.stats["best_combo"] = max(self.stats["best_combo"], mult)
            self.swipe_n += 1
            self.swipe_t = a.now
            self.swipe_pos = (it.x, it.y)
            self.add_text(f"+{pts}", it.x, it.y - 24, (255, 240, 120), 28)
            if mult >= 2:
                a.audio.combo(mult)
                self.add_text(f"COMBO x{mult}", it.x, it.y - 62, COMBO_COLORS[mult], 34, 1.0)
        elif k == "bomb":
            self.stats["bombs"] += 1
            a.audio.sfx("bomb")
            a.audio.duck(1.4)
            self.shake.kick(22)
            self.fx.ring(it.x, it.y, (255, 170, 60))
            self.fx.ring(it.x, it.y, (255, 240, 200), 0.6)
            self.tscale.slowmo(0.9, 0.3)
            self.flash, self.flash_col = 1.0, (255, 60, 30)
            self.parts.burst(it.x, it.y, (255, 170, 50), 40, 520, up=100)
            self.parts.burst(it.x, it.y, (90, 90, 100), 16, 260, size=(4, 8))
            self.splats.add(it.x, it.y, (40, 30, 30), 150, self.app.quality.splat_cap)
            self.combo.reset()
            if self.mode == "arcade":
                self.score = max(0, self.score - 10)
                self.add_text("-10", it.x, it.y, (255, 90, 70), 40)
            elif self.mode == "classic" and self.dkey == "easy" and self.lives > 1:
                self.lives -= 1
            else:
                self.end_game()
        elif k == "freeze":
            self.freeze_t = 4.0
            a.audio.sfx("freeze")
            self.juice(it.x, it.y, (170, 225, 255), 1.5)
            self.banner = ["FREEZE!", 1.6, (150, 230, 255)]
        elif k == "frenzy":
            self.frenzy_t = 5.0
            a.audio.sfx("frenzy")
            self.juice(it.x, it.y, (255, 210, 60), 1.5)
            self.banner = ["FRENZY x2!", 1.6, (255, 220, 70)]
        elif k.startswith("pu_"):
            kind = k[3:]
            self.pw.activate(kind, self.t)
            a.audio.sfx("powerup")
            self.juice(it.x, it.y, PU_COLORS[kind], 1.4)
            self.banner = [POWERUPS[kind][1].upper() + "!", 1.4, PU_COLORS[kind]]

    def hit_boss(self, it):
        a = self.app
        if it.hit_t > 0:
            return
        it.hp -= 1
        it.hit_t = 0.12
        self.score += 3
        self.shake.kick(7)
        a.audio.sfx("boss_hit", 0.8)
        self.parts.burst(it.x, it.y, (235, 60, 80), 14, 420, up=100)
        self.splats.add(it.x + random.uniform(-40, 40), it.y + random.uniform(-40, 40), (235, 60, 80), 90,
                        a.quality.splat_cap)
        if it.hp <= 0:
            it.alive = False
            self.boss = None
            self.stats["boss_down"] += 1
            self.score += 50
            self.shake.kick(20)
            self.fx.ring(it.x, it.y, (255, 120, 140))
            self.tscale.slowmo(0.6, 0.4)
            a.audio.sfx("boss_down")
            split_fruit(it.art, it.x, it.y, it.vx, -80, 1, -0.3, self.pieces)
            self.parts.burst(it.x, it.y, (235, 60, 80), 60, 600, up=150)
            self.banner = ["BOSS DOWN! +50", 1.8, (255, 220, 90)]
            for _ in range(6):
                self.rain_fruit()

    def lose_life(self):
        self.app.audio.sfx("miss")
        self.lives -= 1
        self.flash, self.flash_col = 0.5, (255, 60, 30)
        self.combo.reset()
        if self.lives <= 0:
            self.end_game()

    def end_game(self):
        if self.state != "play":
            return
        a = self.app
        self.finish_swipe()
        self.state = "over"
        self.over_t = 0.0
        sv = a.save
        best = sv["best"].get(self.mode, 0)
        new_best = self.score > best
        if new_best:
            sv["best"][self.mode] = self.score
            a.board.submit(self.score, self.mode)
        stats = dict(self.stats, mode=self.mode, score=self.score, difficulty=self.dkey, powerups=self.pw.used)
        stats["daily_done"] = progress.daily_update(sv, stats)
        new_ach = progress.check_achievements(sv, stats)
        sv["totals"]["sliced"] += self.stats["sliced"]
        sv["totals"]["games"] += 1
        if self.mode not in sv["totals"]["modes"]:
            sv["totals"]["modes"].append(self.mode)
        new_unlocks = progress.unlock_new(sv)
        for u in new_unlocks:
            if u.startswith("bg:"):
                sv["bg"] = u[3:]
        a.persist()
        self.result = {"new_best": new_best, "ach": new_ach, "unlocks": new_unlocks,
                       "daily": stats["daily_done"], "title": "Time's up!" if self.time_left == 0 else "Game Over"}
        a.audio.stop_music(400)
        a.audio.sfx("over")
        if new_ach or new_unlocks:
            a.audio.sfx("achievement")

    # --------------------------------------------------------------- update
    def update(self, dt):
        a = self.app
        a.backdrop.update(dt)
        self.parts.cap = a.quality.particle_cap
        self.parts.update(dt)
        self.splats.update(dt)
        self.fx.update(dt)
        for h in self.hits:
            h[2] -= dt
        self.hits = [h for h in self.hits if h[2] > 0]
        self.trail.update(a.now)
        self.flash = max(0.0, self.flash - dt * 2.2)
        self.shake.update(dt)
        for t in self.texts:
            t[4] -= dt
            t[3] -= 45 * dt
        self.texts = [t for t in self.texts if t[4] > 0]
        for b in self.btns_active():
            b.update(dt, a.mouse)
        if self.state == "play":
            self.update_play(dt)
        elif self.state == "over":
            self.over_t += dt
            self.panel.update(dt)
            for p in self.pieces:
                p.update(dt)

    def btns_active(self):
        return {"play": [self.btn_pause], "pause": self.pause_btns, "over": self.over_btns}[self.state]

    def update_play(self, dt):
        a = self.app
        ts = min(self.tscale.update(dt), 0.4 if self.freeze_t > 0 else 1.0, self.pw.time_scale(self.t))
        sdt = dt * ts
        self.t += dt
        self.freeze_t = max(0.0, self.freeze_t - dt)
        self.frenzy_t = max(0.0, self.frenzy_t - dt)
        if self.banner:
            self.banner[1] -= dt
            if self.banner[1] <= 0:
                self.banner = None
        if self.time_left is not None:
            self.time_left = max(0.0, self.time_left - dt)
            if self.time_left <= 0:
                self.end_game()
                return
        tense = (self.mode in ("classic",) and self.lives == 1 and self.max_lives > 1) or \
                (self.time_left is not None and self.time_left < 12) or self.mode == "sudden"
        if tense != self.tense:
            self.tense = tense
            a.audio.music("tense" if tense else "play")
        self.spawn_t -= sdt
        if self.spawn_t <= 0:
            self.spawn_wave()
        if self.pw.active("rain", self.t):
            self.rain_acc += dt
            while self.rain_acc > 0.14:
                self.rain_acc -= 0.14
                self.rain_fruit()
        g = self.gravity()
        for it in self.items:
            it.update(sdt, g)
            if it.y > H + it.r + 40 and it.vy > 0:
                it.alive = False
                if it is self.boss:
                    self.boss = None
                elif it.kind == "fruit" and not it.bonus and self.mode in ("classic", "sudden"):
                    self.lose_life()
                    if self.state != "play":
                        return
        self.items = [i for i in self.items if i.alive]
        for p in self.pieces:
            p.update(sdt)
        self.pieces = [p for p in self.pieces if p.y < H + 200]
        if self.swipe_n and a.now - self.swipe_t > 0.25:
            self.finish_swipe()
        self.stats["best_combo"] = max(self.stats["best_combo"], self.combo.best)

    # ---------------------------------------------------------------- input
    def blade(self, p0, p1):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        d = math.hypot(dx, dy)
        if d < 5:
            return
        if d > 30 and self.app.now - getattr(self, "_swoosh", 0) > 0.2:
            self._swoosh = self.app.now
            self.app.audio.sfx("swoosh", 0.5)
        for it in list(self.items):
            if it.alive and seg_dist(it.x, it.y, p0[0], p0[1], p1[0], p1[1]) <= it.r + 6:
                self.slice_item(it, dx, dy)
                if self.state != "play":
                    return

    def handle(self, e):
        a = self.app
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.state == "play":
                self.pause()
            elif self.state == "pause":
                self.resume()
            return
        if e.type == getattr(pygame, "WINDOWFOCUSLOST", -1) and self.state == "play":
            self.pause()
            return
        if self.state == "over" and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.panel.click(e.pos):
                return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for b in self.btns_active():
                if b.hit(e.pos):
                    return
            if self.state == "play":
                self.down, self.last = True, e.pos
                self.trail.clear()
                self.trail.add(*e.pos, a.now)
        elif e.type == pygame.MOUSEMOTION and self.down and self.state == "play":
            self.trail.add(*e.pos, a.now)
            self.blade(self.last or e.pos, e.pos)
            self.last = e.pos
        elif e.type == pygame.MOUSEBUTTONUP:
            self.down = False
            if self.state == "play":
                self.finish_swipe()

    # ----------------------------------------------------------------- draw
    def draw(self, s):
        a = self.app
        a.backdrop.draw(s)
        self.splats.draw(s)
        sh = self.shadows
        for p in self.pieces:
            sh.draw(s, p.x, p.y, 30)
        for it in self.items:
            sh.draw(s, it.x, it.y, it.r)
        for p in self.pieces:
            p.draw(s)
        for it in self.items:
            it.draw(s)
        self.parts.draw(s)
        self.fx.draw(s)
        for x, y, life in self.hits:
            s.blit(self.hit_glow, self.hit_glow.get_rect(center=(x, y)), special_flags=pygame.BLEND_RGB_ADD)
        self.trail.draw(s, a.save["blade"], a.now)
        if self.shake.amp > 0.5:
            ox, oy = self.shake.offset()
            s.scroll(ox, oy)
        if self.flash > 0:
            self.flash_surf.fill(self.flash_col)
            self.flash_surf.set_alpha(int(120 * self.flash))
            s.blit(self.flash_surf, (0, 0))
        if self.freeze_t > 0:
            self.flash_surf.fill((150, 210, 255))
            self.flash_surf.set_alpha(int(40 * min(1.0, self.freeze_t)))
            s.blit(self.flash_surf, (0, 0))
        if self.state != "over":
            self.draw_hud(s)
        if self.state == "pause":
            s.blit(self.dim, (0, 0))
            s.blit(ui.panel(380, 330, (30, 16, 40, 235)), (310, 170))
            ui.blit_text(s, "Paused", 52, (W // 2, 215), (255, 210, 74))
            for b in self.pause_btns:
                b.draw(s)
        elif self.state == "over":
            self.draw_over(s)

    def draw_hud(self, s):
        a = self.app
        ui.blit_text(s, str(self.score), 64, (22, 8), (255, 255, 255), "topleft", ow=3)
        ui.blit_text(s, f"Best {a.save['best'].get(self.mode, 0)}", 18, (26, 78), (255, 230, 150), "topleft")
        x = 24
        if self.combo.alive(self.t):
            c = min(5, self.combo.count)
            k = 1.0 + 0.25 * max(0.0, 1.0 - (self.t - self.combo.last) * 5)
            ui.blit_text(s, f"COMBO x{c}", 30, (26, 112), COMBO_COLORS.get(c, (255, 255, 255)), "topleft", scale=k)
        y = 150
        for kind, (dur, label) in POWERUPS.items():
            rem = self.pw.remaining(kind, self.t)
            if rem > 0:
                col = PU_COLORS[kind]
                ui.blit_text(s, label, 16, (x, y), col, "topleft")
                pygame.draw.rect(s, (30, 15, 30), (x, y + 22, 130, 10), border_radius=5)
                pygame.draw.rect(s, col, (x, y + 22, int(130 * rem / dur), 10), border_radius=5)
                y += 40
        if self.frenzy_t > 0:
            ui.blit_text(s, f"FRENZY x2  {self.frenzy_t:.1f}s", 16, (x, y), (255, 220, 70), "topleft")
        if self.time_left is not None:
            frac = self.time_left / ({"arcade": 60.0, "zen": 90.0}[self.mode])
            bar = pygame.Rect(0, 0, 300, 22)
            bar.center = (W // 2, 30)
            pygame.draw.rect(s, (30, 15, 30), bar.inflate(6, 6), border_radius=14)
            col = ui.lerp_col((255, 70, 60), (120, 220, 80), min(1.0, frac * 1.5))
            f = bar.copy()
            f.w = max(0, int(bar.w * frac))
            if f.w:
                pygame.draw.rect(s, col, f, border_radius=11)
            ui.blit_text(s, f"{int(math.ceil(self.time_left))}", 20, bar.center)
        if self.max_lives:
            for i in range(self.max_lives):
                s.blit(ui.heart(36, i < self.lives), (W - 100 - (self.max_lives - 1 - i) * 38 - 40, 20))
        if self.boss and self.boss.alive:
            total = max(6, round(10 * self.diff["count"]))
            bar = pygame.Rect(0, 0, 360, 20)
            bar.center = (W // 2, 74)
            pygame.draw.rect(s, (30, 15, 30), bar.inflate(6, 6), border_radius=12)
            f = bar.copy()
            f.w = max(0, int(bar.w * self.boss.hp / total))
            pygame.draw.rect(s, (235, 60, 80), f, border_radius=10)
            ui.blit_text(s, "GIANT WATERMELON", 14, bar.center)
        if self.banner:
            t = 1.0 - self.banner[1] / (1.8 if len(self.banner[0]) > 14 else 1.6)
            k = ui.ease_out_back(min(1.0, t * 4))
            al = 255 * min(1.0, self.banner[1] * 3)
            ui.blit_text(s, self.banner[0], 60, (W // 2, 190), self.banner[2], ow=3, alpha=al, scale=max(0.1, k))
        for txt, x0, x1, y0, life, maxlife, col, size in self.texts:
            ui.blit_text(s, txt, size, (x1, y0), col, alpha=255 * min(1.0, life / maxlife * 2))
        if self.state == "play":
            self.btn_pause.draw(s)

    def draw_over(self, s):
        a = self.app
        r = self.result
        s.blit(self.dim, (0, 0))
        k = ui.ease_out_back(self.over_t * 2.5)
        ui.blit_text(s, r["title"], 64, (W // 2, 90), (255, 210, 74), ow=3, scale=max(0.1, k))
        shown = int(self.score * min(1.0, self.over_t / 0.9))
        ui.blit_text(s, str(shown), 96, (W // 2, 190), (255, 255, 255), ow=4)
        if r["new_best"]:
            pulse = 1.0 + 0.08 * math.sin(self.over_t * 8)
            ui.blit_text(s, "NEW BEST!", 40, (W // 2, 262), (255, 120, 150), scale=pulse)
        else:
            ui.blit_text(s, f"Best: {a.save['best'].get(self.mode, 0)}", 28, (W // 2, 262), (255, 230, 150))
        ui.blit_text(s, f"Fruit sliced {self.stats['sliced']}    Best combo x{self.stats['best_combo']}"
                     f"    Biggest swipe {self.stats['max_swipe']}", 20, (W // 2, 308), (255, 240, 220))
        y = 350
        if r["daily"]:
            ui.blit_text(s, "Daily challenge complete!", 24, (W // 2, y), (140, 240, 100))
            y += 36
        for aid in r["ach"]:
            ui.blit_text(s, "Achievement: " + progress.ACH_BY_ID[aid][1], 24, (W // 2, y), (255, 210, 74))
            y += 34
        for u in r["unlocks"][:3]:
            group, item = u.split(":")
            label = settings.BOARD_NAMES.get(item, item.title()) if group == "bg" else item.title() + " blade"
            what = "NEW BOARD unlocked" if group == "bg" else "Unlocked"
            ui.blit_text(s, f"{what}: {label}", 24 if group == "bg" else 22, (W // 2, y),
                         (255, 215, 100) if group == "bg" else (170, 220, 255))
            y += 32
        if a.board.submit_msg:
            ui.blit_text(s, a.board.submit_msg, 18, (W // 2, 520), (255, 255, 255))
        for b in self.over_btns:
            b.draw(s)
        self.panel.draw(s)

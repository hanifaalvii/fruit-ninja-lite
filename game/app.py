"""App: owns the window, shared services and the active scene."""
import asyncio
import sys
import time

import pygame

from . import progress, settings
from .assets import Art, Loader
from .audio import Audio
from .effects import Quality
from .entities import clamp_dt
from .net import Board, clean_name
from .play import Play
from .scenes import Awards, Loading, Menu, NameEntry, Settings, Unlocks
from .world import Backdrop

W, H = settings.W, settings.H


class App:
    def __init__(self):
        try:
            pygame.mixer.pre_init(22050, -16, 1, 512)
        except Exception:
            pass
        pygame.init()
        pygame.display.set_caption("Fruit Slash")
        flags = 0 if settings.WEB else pygame.SCALED | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((W, H), flags)
        self.clock = pygame.time.Clock()
        self.save = progress.load()
        self.quality = Quality()
        self.art = Art()
        self.audio = Audio(self.save)
        self.board = Board(self.save)
        self.backdrop = Backdrop(self)
        self.now = time.perf_counter()
        self.mouse = (0, 0)
        self.name_cb = None
        self.scenes = {"loading": Loading(self), "menu": Menu(self), "play": Play(self), "settings": Settings(self),
                       "achievements": Awards(self), "unlocks": Unlocks(self), "name": NameEntry(self)}
        self.scene = None
        self.audio.apply_volume()

    # -------------------------------------------------------------- scenes
    def go(self, name, **kw):
        self.scene = self.scenes[name]
        self.scene.enter(**kw)

    def resume_scene(self, name):
        self.scene = self.scenes[name]

    def persist(self):
        progress.save(self.save)

    def make_loader(self):
        steps = [("Sanding the cutting board", lambda: self.art.theme(self.save["bg"]))]
        steps += self.art.steps()
        steps += self.audio.steps()
        steps.append(("Sharpening the knives", self.backdrop.setup))
        return Loader(steps)

    async def boot(self):
        loader = self.make_loader()
        await loader.run()
        self.go("menu")
        return loader

    # --------------------------------------------------------------- actions
    def toggle_mute(self):
        self.save["mute"] = not self.save["mute"]
        self.audio.apply_volume()
        self.persist()
        self.audio.sfx("click")

    def toggle_fullscreen(self):
        self.audio.sfx("click")
        try:
            if settings.WEB:
                import platform
                platform.window.eval(
                    "var c=document.getElementById('canvas')||document.documentElement;"
                    "if(document.fullscreenElement){document.exitFullscreen()}else{c.requestFullscreen()}")
            else:
                pygame.display.toggle_fullscreen()
        except Exception:
            pass

    def ask_name(self, cb):
        self.audio.sfx("click")
        self.name_cb = cb
        if settings.WEB:
            self.board.open_web_name(first=not self.save.get("name"))
        else:
            self.go("name", cb=cb)

    def start_game(self, mode):
        if not self.save.get("name"):
            self.ask_name(lambda: self.go("play", mode=mode))
        else:
            self.go("play", mode=mode)

    def quit(self):
        self.persist()
        pygame.quit()
        sys.exit()

    # ----------------------------------------------------------------- loop
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.mouse = e.pos
        typing = self.scene is self.scenes["name"]
        if e.type == pygame.KEYDOWN and not typing:
            if e.key == pygame.K_f:
                self.toggle_fullscreen()
            elif e.key == pygame.K_m:
                self.toggle_mute()
        self.scene.handle(e)

    def frame(self, dt):
        self.now = time.perf_counter()
        for e in pygame.event.get():
            self.handle(e)
        picked = self.board.poll()
        if picked is not None:
            if picked == "\x00" and self.save.get("name"):
                self.name_cb = None
            else:
                self.save["name"] = clean_name("" if picked == "\x00" else picked)
                self.persist()
                cb, self.name_cb = self.name_cb, None
                if cb:
                    cb()
        self.audio.update(dt)
        self.scene.update(clamp_dt(dt))
        self.scene.draw(self.screen)
        pygame.display.flip()

    async def run(self):
        self.go("loading", loader=self.make_loader())
        last = time.perf_counter()
        while True:
            now = time.perf_counter()
            dt = now - last
            last = now
            self.quality.record(dt * 1000)
            self.frame(dt)
            self.clock.tick(settings.FPS)
            await asyncio.sleep(0)

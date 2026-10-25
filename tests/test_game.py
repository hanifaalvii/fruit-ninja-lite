import asyncio
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402
import pytest  # noqa: E402

from game import progress  # noqa: E402
from game.app import App  # noqa: E402


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    progress.SAVE = str(tmp_path_factory.mktemp("sv") / "save.json")
    a = App()
    a.save["name"] = "Tester"
    loader = asyncio.run(a.boot())
    assert not loader.errors, loader.errors
    return a


def run_scene(a, frames, dt=1 / 60):
    for _ in range(frames):
        a.now = time.perf_counter()
        a.scene.update(dt)
        a.scene.draw(a.screen)


def test_menu_scenes_draw(app):
    for name, kw in [("menu", {}), ("settings", {"back": "menu"}), ("achievements", {}), ("unlocks", {})]:
        app.go(name, **kw)
        run_scene(app, 20)


@pytest.mark.parametrize("mode", ["classic", "arcade", "zen", "sudden"])
@pytest.mark.parametrize("diff", ["easy", "hard"])
def test_every_mode_plays_to_the_end(app, mode, diff):
    app.go("play", mode=mode, difficulty=diff)
    sc = app.scene
    # sweep the blade across the screen every few frames so slicing paths are exercised
    for i in range(900):
        if i % 20 == 0 and sc.state == "play":
            sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100 + (i % 7) * 60)))
            for k in range(1, 12):
                sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(100 + k * 70, 100 + (i % 7) * 60 + k * 15),
                                             rel=(70, 15), buttons=(1, 0, 0)))
            sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(900, 300)))
        run_scene(app, 1)
    if sc.state == "play":
        sc.end_game()
    assert sc.state == "over" and sc.result is not None
    run_scene(app, 30)


def test_boss_spawns_and_can_be_defeated(app):
    app.go("play", mode="classic", difficulty="normal")
    sc = app.scene
    sc.throw("boss")
    assert sc.boss is not None
    boss = sc.boss
    for _ in range(boss.hp):
        boss.hit_t = 0
        sc.slice_item(boss, 10, 0)
    assert sc.boss is None and sc.stats["boss_down"] == 1
    run_scene(app, 10)


def test_powerups_work(app):
    app.go("play", mode="arcade", difficulty="normal")
    sc = app.scene
    for kind in ("pu_slowmo", "pu_double", "pu_rain", "freeze", "frenzy"):
        sc.throw(kind)
    for it in list(sc.items):
        sc.slice_item(it, 5, 5)
    assert sc.pw.active("double", sc.t) and sc.frenzy_t > 0
    run_scene(app, 120)


def test_pause_and_settings_roundtrip(app):
    app.go("play", mode="zen", difficulty="normal")
    sc = app.scene
    sc.pause()
    assert sc.state == "pause"
    run_scene(app, 5)
    sc.open_sound()
    app.scene.close()
    assert app.scene is sc
    sc.resume()
    assert sc.state == "play"


def test_touch_events_and_resize_ignored(app):
    app.go("play", mode="classic", difficulty="easy")
    for e in [pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=.2, y=.2),
              pygame.event.Event(pygame.FINGERDOWN, finger_id=2, x=.8, y=.8),
              pygame.event.Event(pygame.VIDEORESIZE, w=500, h=300, size=(500, 300))]:
        app.scene.handle(e)
    run_scene(app, 5)


def test_huge_dt_does_not_explode(app):
    app.go("play", mode="classic", difficulty="normal")
    for _ in range(5):
        app.frame(5.0)
    assert len(app.scene.items) < 40


def test_loading_scene_and_missing_assets():
    from game.assets import Loader
    seen = []

    def boom():
        raise RuntimeError("x")
    L = Loader([("a", lambda: seen.append("a")), ("b", boom), ("c", lambda: seen.append("c"))])
    asyncio.run(L.run())
    assert seen == ["a", "c"] and len(L.errors) == 1 and L.progress == 1.0


def test_gameplay_frame_time(app):
    app.go("play", mode="arcade", difficulty="hard")
    sc = app.scene
    ts = []
    for i in range(600):
        if i % 12 == 0:
            sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 300)))
            for k in range(1, 10):
                sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(50 + k * 100, 300 + (k % 3) * 70), rel=(100, 0),
                                             buttons=(1, 0, 0)))
            sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(950, 300)))
        t = time.perf_counter()
        sc.update(1 / 60)
        sc.draw(app.screen)
        ts.append((time.perf_counter() - t) * 1000)
        if sc.state != "play":
            break
    ts.sort()
    p95 = ts[int(len(ts) * 0.95)]
    print(f"frame ms: median {ts[len(ts) // 2]:.2f}  p95 {p95:.2f}  max {ts[-1]:.2f}")
    assert p95 < 16.7

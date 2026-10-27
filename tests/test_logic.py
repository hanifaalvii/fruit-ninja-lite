import datetime
import os
import sys
from random import Random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import progress  # noqa: E402
from game.modes import WaveDirector  # noqa: E402
from game.scoring import Combo, PowerUps, swipe_bonus  # noqa: E402


def test_combo_builds_caps_and_resets():
    c = Combo(window=0.9)
    assert [c.hit(t) for t in (0.0, 0.3, 0.6, 0.9, 1.2)] == [1, 2, 3, 4, 5]
    assert c.hit(1.3) == 5
    assert c.hit(3.0) == 1


def test_swipe_bonus():
    assert [swipe_bonus(n) for n in (1, 2, 3, 4)] == [0, 0, 5, 10]


def test_powerups_expire():
    p = PowerUps()
    p.activate("double", 10.0)
    p.activate("slowmo", 10.0)
    assert p.score_mult(12.0) == 2 and p.time_scale(12.0) == 0.45
    assert p.score_mult(19.0) == 1 and p.time_scale(17.0) == 1.0


def test_boss_only_classic_every_8th():
    d = WaveDirector("classic", "normal", Random(1))
    assert [w for w in range(1, 17) if d.is_boss_wave(w)] == [8, 16]
    assert not WaveDirector("zen", "normal", Random(1)).is_boss_wave(8)


def test_zen_has_no_bombs_and_hard_spawns_more():
    z = WaveDirector("zen", "normal", Random(2))
    assert all(s.kind != "bomb" for w in range(1, 40) for s in z.next_wave(w * 2.0, w))

    def count(diff):
        d = WaveDirector("classic", diff, Random(3))
        return sum(len(d.next_wave(40.0, w)) for w in range(1, 8))
    assert count("hard") > count("easy")


def test_old_save_gets_defaults(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    p.write_text('{"music": 0.3, "best": {"classic": 12}}')
    monkeypatch.setattr(progress, "SAVE", str(p))
    d = progress.load()
    assert d["music"] == 0.3 and d["best"]["classic"] == 12
    assert d["unlocks"] == {"blade": ["classic"], "bg": ["pine"]}
    assert d["difficulty"] == "normal" and d["ach"] == []


def test_corrupt_save_falls_back(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    monkeypatch.setattr(progress, "SAVE", str(p))
    assert progress.load()["sfx"] == 0.8


def test_daily_deterministic_and_varied():
    a = progress.daily_challenge(datetime.date(2026, 10, 25))
    assert a == progress.daily_challenge(datetime.date(2026, 10, 25))
    days = {progress.daily_challenge(datetime.date(2026, 10, d))["text"] for d in range(1, 20)}
    assert len(days) > 3


def test_achievement_awarded_once():
    s = progress.load_defaults()
    assert "first_slice" in progress.check_achievements(s, {"sliced": 1})
    assert progress.check_achievements(s, {"sliced": 1}) == []


def test_unlock_by_score_and_ach():
    s = progress.load_defaults()
    s["best"] = {"classic": 500}
    assert "blade:flame" in progress.unlock_new(s)
    s["ach"].append("boss_down")
    assert "blade:neon" in progress.unlock_new(s)


def test_daily_completes_once():
    s = progress.load_defaults()
    day = datetime.date(2026, 10, 25)
    ch = progress.daily_challenge(day)
    stats = {"mode": ch["mode"] or "classic", "sliced": 999, "best_combo": 9, "score": 9999, "max_swipe": 9,
             "boss_down": 1, "powerups": 9}
    assert progress.daily_update(s, stats, day) is True
    assert progress.daily_update(s, stats, day) is False


def test_old_sky_theme_save_maps_to_a_board(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    p.write_text('{"bg": "dusk", "unlocks": {"bg": ["orchard", "dusk"], "blade": ["classic"]}}')
    monkeypatch.setattr(progress, "SAVE", str(p))
    d = progress.load()
    assert d["bg"] == "pine" and d["unlocks"]["bg"] == ["pine"]


def test_boards_unlock_by_score_in_order():
    s = progress.load_defaults()
    assert progress.next_board(s)[:2] == ("bamboo", 100)
    s["best"] = {"arcade": 650}
    new = progress.unlock_new(s)
    assert "bg:bamboo" in new and "bg:walnut" in new and "bg:marble" in new and "bg:slate" not in new
    assert progress.next_board(s)[:2] == ("slate", 1000)
    s["best"] = {"arcade": 5000}
    progress.unlock_new(s)
    assert progress.next_board(s) is None

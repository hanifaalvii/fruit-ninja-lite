"""Saved data, achievements, unlocks and the daily challenge. Pure logic, no pygame."""
import copy
import datetime
import json
import random

from . import settings

SAVE = settings.SAVE_PATH

DEFAULTS = {
    "music": 0.6, "sfx": 0.8, "mute": False, "best": {}, "name": "",
    "unlocks": {"blade": ["classic"], "bg": ["orchard"]},
    "blade": "classic", "bg": "orchard", "difficulty": "normal",
    "ach": [], "daily": {}, "totals": {"sliced": 0, "games": 0, "modes": []},
}


def load_defaults():
    return copy.deepcopy(DEFAULTS)


def _merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load():
    data = load_defaults()
    try:
        if settings.WEB:
            import platform
            raw = platform.window.localStorage.getItem(settings.STORE_KEY)
            stored = json.loads(raw) if raw else {}
        else:
            with open(SAVE) as f:
                stored = json.load(f)
        if isinstance(stored, dict):
            _merge(data, stored)
    except Exception:
        pass
    return data


def save(data):
    try:
        if settings.WEB:
            import platform
            platform.window.localStorage.setItem(settings.STORE_KEY, json.dumps(data))
        else:
            with open(SAVE, "w") as f:
                json.dump(data, f)
    except Exception:
        pass


# ------------------------------------------------------------------ achievements
ACHIEVEMENTS = [
    ("first_slice", "First Cut", "Slice your first fruit", lambda s, st: st.get("sliced", 0) >= 1),
    ("fruit_100", "Fruit Ninja", "Slice 100 fruit in total",
     lambda s, st: s["totals"]["sliced"] + st.get("sliced", 0) >= 100),
    ("combo_x5", "Combo King", "Reach a x5 combo", lambda s, st: st.get("best_combo", 0) >= 5),
    ("triple", "Triple Threat", "Slice 3 fruit in one swipe", lambda s, st: st.get("max_swipe", 0) >= 3),
    ("boss_down", "Giant Slayer", "Defeat the giant watermelon", lambda s, st: st.get("boss_down", 0) >= 1),
    ("clean_500", "Clean Hands", "Score 500 in Classic without hitting a bomb",
     lambda s, st: st.get("mode") == "classic" and st.get("score", 0) >= 500 and st.get("bombs", 0) == 0),
    ("zen_300", "Inner Peace", "Score 300 in Zen",
     lambda s, st: st.get("mode") == "zen" and st.get("score", 0) >= 300),
    ("sudden_100", "Sudden Master", "Score 100 in Sudden Death",
     lambda s, st: st.get("mode") == "sudden" and st.get("score", 0) >= 100),
    ("hard_200", "Brave Heart", "Score 200 on Hard",
     lambda s, st: st.get("difficulty") == "hard" and st.get("score", 0) >= 200),
    ("daily_done", "Daily Hero", "Finish a daily challenge", lambda s, st: bool(st.get("daily_done"))),
    ("all_modes", "Explorer", "Play all four modes",
     lambda s, st: len(set(s["totals"]["modes"]) | {st.get("mode")}) >= 4),
    ("powerup_master", "Power Surge", "Use 3 power-ups in one game", lambda s, st: st.get("powerups", 0) >= 3),
]
ACH_BY_ID = {a[0]: a for a in ACHIEVEMENTS}


def check_achievements(save_data, stats):
    new = []
    for aid, _title, _desc, test in ACHIEVEMENTS:
        if aid not in save_data["ach"] and test(save_data, stats):
            save_data["ach"].append(aid)
            new.append(aid)
    return new


# ---------------------------------------------------------------------- unlocks
UNLOCKS = {
    "blade": {"classic": None, "flame": ("score", 150), "ice": ("score", 400), "neon": ("ach", "boss_down"),
              "rainbow": ("score", 1500)},
    "bg": {"orchard": None, "dusk": ("score", 250), "night": ("ach", "fruit_100"), "sakura": ("score", 600)},
}


def unlock_text(req):
    if req is None:
        return "Unlocked"
    kind, val = req
    return f"Best score {val}" if kind == "score" else "Achievement: " + ACH_BY_ID[val][1]


def best_score(save_data):
    return max(save_data["best"].values(), default=0)


def unlock_new(save_data):
    top = best_score(save_data)
    new = []
    for group, items in UNLOCKS.items():
        owned = save_data["unlocks"].setdefault(group, [])
        for item, req in items.items():
            if item in owned:
                continue
            ok = req is None or (req[0] == "score" and top >= req[1]) or (req[0] == "ach" and req[1] in save_data["ach"])
            if ok:
                owned.append(item)
                new.append(f"{group}:{item}")
    return new


# ------------------------------------------------------------------ daily challenge
DAILY_GOALS = [
    ("sliced", 60, "classic", "Slice 60 fruit in Classic"),
    ("sliced", 40, "arcade", "Slice 40 fruit in Arcade"),
    ("combo", 4, None, "Reach a x4 combo"),
    ("score", 250, "arcade", "Score 250 in Arcade"),
    ("score", 200, "zen", "Score 200 in Zen"),
    ("swipe", 3, None, "Slice 3 fruit in one swipe"),
    ("boss", 1, "classic", "Defeat the giant watermelon"),
    ("powerups", 2, None, "Collect 2 power-ups in one game"),
]


def daily_challenge(date):
    rng = random.Random(date.toordinal() * 7919)
    kind, target, mode, text = rng.choice(DAILY_GOALS)
    return {"goal": kind, "target": target, "mode": mode, "text": text, "date": date.isoformat()}


def today():
    return datetime.date.today()


def daily_state(save_data, date=None):
    ch = daily_challenge(date or today())
    d = save_data["daily"]
    if d.get("date") != ch["date"]:
        save_data["daily"] = d = {"date": ch["date"], "done": False}
    return ch, d


def daily_update(save_data, stats, date=None):
    """True the first time today's challenge is completed by a finished run."""
    ch, d = daily_state(save_data, date)
    if d["done"] or (ch["mode"] and ch["mode"] != stats.get("mode")):
        return False
    key = {"sliced": "sliced", "combo": "best_combo", "score": "score", "swipe": "max_swipe",
           "boss": "boss_down", "powerups": "powerups"}[ch["goal"]]
    if stats.get(key, 0) >= ch["target"]:
        d["done"] = True
        return True
    return False

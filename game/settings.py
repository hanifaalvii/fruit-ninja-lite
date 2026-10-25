"""Constants shared across the game."""
import os
import sys

WEB = sys.platform == "emscripten"
W, H = 1000, 650
FPS = 60
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SAVE_PATH = os.path.join(ROOT, "save.json")
STORE_KEY = "fruitslash"

MODE_ORDER = ("classic", "arcade", "zen", "sudden")
MODES = {
    "classic": ("Classic", "3 lives - dodge bombs - boss every 8 waves"),
    "arcade": ("Arcade", "60 seconds - power-ups - Freeze & Frenzy"),
    "zen": ("Zen", "90 seconds - no bombs - pure flow"),
    "sudden": ("Sudden Death", "1 life - speed keeps rising"),
}
MODE_FRUIT = {"classic": "watermelon", "arcade": "orange", "zen": "kiwi", "sudden": "plum"}
FRUITS = ("watermelon", "orange", "apple", "kiwi", "lemon", "plum")
FRUIT_RADIUS = {"watermelon": 50, "orange": 40, "apple": 38, "kiwi": 36, "lemon": 36, "plum": 34}
FRUIT_JUICE = {
    "watermelon": (235, 60, 80), "orange": (255, 170, 40), "apple": (250, 240, 190),
    "kiwi": (130, 200, 50), "lemon": (255, 240, 90), "plum": (240, 160, 40),
}

DIFFICULTY_ORDER = ("easy", "normal", "hard")
DIFFICULTY = {
    "easy": {"label": "Easy", "lives": 4, "count": 0.8, "bomb": 0.6, "speed": 0.92, "gap": 1.25},
    "normal": {"label": "Normal", "lives": 3, "count": 1.0, "bomb": 1.0, "speed": 1.0, "gap": 1.0},
    "hard": {"label": "Hard", "lives": 2, "count": 1.3, "bomb": 1.4, "speed": 1.08, "gap": 0.8},
}

THEMES = ("orchard", "dusk", "night", "sakura")
BLADES = ("classic", "flame", "ice", "neon", "rainbow")
BLADE_COLORS = {
    "classic": ((255, 255, 255), (170, 220, 255)),
    "flame": ((255, 240, 120), (255, 90, 20)),
    "ice": ((230, 252, 255), (60, 170, 255)),
    "neon": ((255, 255, 255), (255, 40, 220)),
    "rainbow": None,
}

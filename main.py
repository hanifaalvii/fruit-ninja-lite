"""Fruit Slash - a Fruit Ninja style game in Python (pygame-ce).

Desktop:   pip install pygame-ce && python3 main.py
Web/phone: built with pygbag (see README.md).
Swipe with mouse or finger to slice fruit.  ESC = pause, M = mute, F = fullscreen.
"""
import asyncio

import pygame  # noqa: F401  (pygbag scans main.py imports to decide which packages to ship)

from game.app import App


async def main():
    await App().run()


if __name__ == "__main__":
    asyncio.run(main())

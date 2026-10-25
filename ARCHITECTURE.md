# Architecture

`main.py` is a thin entry point (pygbag needs it). Everything else lives in `game/`.

| Module | Responsibility |
|---|---|
| `app.py` | Window, shared services (art, audio, save, board, quality), scene switching, main loop |
| `scenes.py` | Loading, Menu, Settings, Awards, Unlocks, NameEntry |
| `play.py` | Gameplay: all modes, slicing, combos, power-ups, boss, pause, game over |
| `common.py` | Scene base class, fruit splitting, sliding Top-3 leaderboard tab |
| `world.py` | Animated parallax backdrop |
| `effects.py` | Quality governor, capped particles, shake, slow-mo, juice splats, blade trail |
| `entities.py` | Flying items and sliced halves, safe physics step |
| `assets.py` | Time-sliced `Loader`, `Art` (cached sprites: tumbling body + fixed light overlay) |
| `audio.py` | OGG effects/music with fallback, music crossfade, ducking |
| `ui.py` | Cached outlined text, buttons, sliders, panels |
| `net.py` | Leaderboard + nickname glue (non-blocking) |
| `progress.py` | Save data, achievements, unlocks, daily challenge (pure logic) |
| `scoring.py` | Combo, swipe bonus, power-up timers (pure logic) |
| `modes.py` | Wave director, boss schedule (pure logic) |
| `settings.py` | Constants, difficulty table |

Performance rules: heavy drawing happens once (`tools/gfx.py` bakes the art; frames are cached lazily per 6 degrees),
frames only blit; particles and splats are capped; `effects.Quality` drops effects when frames average over 24 ms.
Assets load in 6 ms slices so the loading screen stays at full frame rate.

Tests (`tests/`) run headless with SDL dummy drivers: pure logic, every scene and mode, and a frame-time budget.

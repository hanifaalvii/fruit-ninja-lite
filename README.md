# Fruit Slash

A Fruit Ninja style game in Python (pygame). Runs on desktop and in the browser (phone + desktop) via pygbag.

- 4 modes: Classic, Arcade, Zen, Sudden Death
- Players pick a nickname on first open (change it with the Name button)
- Live online **Top 3** leaderboard: a tab on the right edge that slides out on hover (desktop) or tap (phone)
- Fullscreen button (or press F), pause button, mute (M), music/effects sliders

## Run on your computer

    pip3 install pygame-ce
    python3 main.py

## Test the web version locally

    pip3 install pygbag
    python3 -m pygbag .

Open http://localhost:8000

## Put it live on the internet (step by step)

### 1. Create the leaderboard database (free, ~3 minutes)
1. Go to https://supabase.com, sign up, click **New project** (any name/password, pick a nearby region).
2. When it finishes, open **SQL Editor -> New query**, paste everything from [supabase.sql](supabase.sql), click **Run**.
3. Open **Project Settings -> API**. Copy the **Project URL** and the **anon public** key.
4. Paste them into [config.py](config.py). (The anon key is designed to be public; the table rules only allow reading and adding scores.)

### 2. Build the web version
    pip3 install pygbag
    sh deploy.sh

This creates a `docs/` folder with the playable web game.

### 3. Publish with GitHub Pages (free)
1. Push the code:

       git add -A
       git commit -m "Fruit Slash web version"
       git push

2. On GitHub open the repo -> **Settings -> Pages**.
3. Under **Build and deployment**: Source = **Deploy from a branch**, Branch = **main**, folder = **/docs**, then **Save**.
4. After about a minute your game is live at
   `https://<your-github-username>.github.io/<repo-name>/`
   (for this repo: https://hanifaalvii.github.io/fruit-ninja-lite2/). Share that link; it works on phones.

### Updating later
Edit the code, run `sh deploy.sh`, then `git add -A && git commit -m "update" && git push`.

## Notes
- Scores are submitted from the player's browser, so a determined player could fake a score. For a casual game this is fine; stricter protection needs a server that verifies gameplay.
- Only a player's new personal best (per mode) is submitted; the leaderboard shows each player's best per mode.
- On iPhone, "Fullscreen" isn't supported by Safari - use Share -> **Add to Home Screen** for a fullscreen app-like feel.
- Phones: play in landscape.

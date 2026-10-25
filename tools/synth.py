"""Synthesises every sound in assets/sfx and assets/music as OGG (original, CC0).

Run: python3 tools/synth.py   (needs `imageio-ffmpeg` only for the WAV -> OGG step)
Pure Python on purpose: no numpy dependency, runs anywhere.
"""
import array
import math
import os
import random
import subprocess
import wave

SR = 22050
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
TMP = "/tmp/fs_synth"
os.makedirs(TMP, exist_ok=True)
TAU = 2 * math.pi


def buf(dur):
    return [0.0] * int(dur * SR)


def add(b, start, samples, loop=False):
    s0 = int(start * SR)
    n = len(b)
    for i, v in enumerate(samples):
        j = s0 + i
        if j >= n:
            if not loop:
                break
            j %= n
        b[j] += v


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_exp(i, n, attack, curve):
    t = i / n
    return min(1.0, i / max(1, attack * SR)) * (1 - t) ** curve


def tone(dur, f0, vol, f1=None, wave_="sine", attack=0.004, curve=2.5, harm=()):
    n = int(dur * SR)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / n
        f = f0 if f1 is None else f0 + (f1 - f0) * t
        ph += f / SR
        if wave_ == "sine":
            v = math.sin(TAU * ph)
        elif wave_ == "tri":
            p = ph % 1.0
            v = 4 * abs(p - 0.5) - 1
        elif wave_ == "square":
            v = 0.6 if (ph % 1.0) < 0.5 else -0.6
        else:
            v = 0.6 * (2 * (ph % 1.0) - 1)
        for k, hv in harm:
            v += hv * math.sin(TAU * ph * k)
        out[i] = v * vol * env_exp(i, n, attack, curve)
    return out


def pluck(f, dur, vol, bright=1.0):
    n = int(dur * SR)
    out = [0.0] * n
    w = TAU * f / SR
    for i in range(n):
        t = i / n
        e = min(1.0, i / (0.003 * SR)) * math.exp(-5.5 * t)
        v = (math.sin(w * i) + 0.45 * bright * math.sin(2 * w * i) * math.exp(-8 * t)
             + 0.2 * math.sin(3 * w * i) * math.exp(-10 * t))
        out[i] = v * vol * e
    return out


def pad(f, dur, vol):
    n = int(dur * SR)
    out = [0.0] * n
    w = TAU * f / SR
    for i in range(n):
        t = i / n
        e = min(1.0, t * 8) * min(1.0, (1 - t) * 6)
        out[i] = (math.sin(w * i) + math.sin(w * 1.004 * i + 1) * 0.7 + 0.25 * math.sin(2 * w * i)) * vol * e * 0.5
    return out


def noise(dur, vol, lp=0.3, hp=0.0, curve=2.0, sweep=None, rng=random, attack=0.002):
    n = int(dur * SR)
    out = [0.0] * n
    y = z = 0.0
    for i in range(n):
        t = i / n
        k = lp if sweep is None else lp + (sweep - lp) * t
        y += k * (rng.uniform(-1, 1) - y)
        v = y
        if hp:
            z += hp * (v - z)
            v -= z
        out[i] = v * vol * env_exp(i, n, attack, curve)
    return out


def finish(b, peak=0.9):
    m = max(1e-9, max(abs(v) for v in b))
    k = min(peak / m, 4.0)
    return [math.tanh(v * k * 1.1) * 0.95 for v in b]


def write(name, b, folder, music=False):
    pcm = array.array("h", (int(max(-1, min(1, v)) * 30000) for v in b))
    wav = os.path.join(TMP, name + ".wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    out = os.path.join(ROOT, folder, name + ".ogg")
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis",
                    "-q:a", "3" if music else "4", out], check=True)
    print(name, os.path.getsize(out) // 1024, "KB", flush=True)


def sfx(name, b, peak=0.9):
    write(name, finish(b, peak), "sfx")


def sfx_swoosh():
    b = buf(0.3)
    add(b, 0, noise(0.3, 0.7, lp=0.04, sweep=0.55, curve=1.0, attack=0.06))
    sfx("swoosh", b, 0.55)


FRUIT_SLICE = {
    # wet, crunch, pitch
    "watermelon": (0.9, 0.5, 150), "orange": (1.0, 0.2, 320), "apple": (0.5, 1.0, 420),
    "kiwi": (0.8, 0.2, 260), "lemon": (1.0, 0.1, 520), "plum": (0.8, 0.3, 230),
}


def sfx_slice():
    for fname, (wet, crunch, p) in FRUIT_SLICE.items():
        for v in range(2):
            rng = random.Random(len(fname) * 10 + v)
            b = buf(0.36)
            add(b, 0, noise(0.07, 0.9, lp=0.85, hp=0.2, curve=2, rng=rng))
            add(b, 0, noise(0.05 + 0.1 * crunch, crunch, lp=0.5, curve=1.5, rng=rng))
            add(b, 0.01, noise(0.25, 0.55 * wet, lp=0.12, sweep=0.04, curve=2.5, rng=rng))
            add(b, 0, tone(0.2, p * (1 + 0.15 * v) * 2.4, 0.3 * wet, f1=p * 0.7, wave_="tri", curve=3))
            add(b, 0.03, tone(0.12, p * 0.8, 0.35, f1=p * 0.3, curve=3))
            sfx(f"slice_{fname}_{v}", b, 0.85)


def sfx_splat():
    b = buf(0.3)
    add(b, 0, noise(0.3, 0.8, lp=0.1, sweep=0.03, curve=2.6))
    add(b, 0, tone(0.2, 240, 0.6, f1=60, curve=2))
    sfx("splat", b)


def sfx_bomb():
    b = buf(1.4)
    add(b, 0, noise(1.4, 1.0, lp=0.3, sweep=0.015, curve=1.5))
    add(b, 0, tone(1.0, 90, 1.0, f1=24, curve=1.4))
    add(b, 0, tone(0.1, 1500, 0.4, f1=200, wave_="saw", curve=4))
    sfx("bomb", b, 0.98)


def sfx_combo():
    for lvl in range(1, 6):
        b = buf(0.6)
        base = 60 + lvl * 2
        notes = [0, 4, 7, 12, 16][: 2 + lvl]
        for i, nn in enumerate(notes):
            add(b, i * 0.055, pluck(midi(base + nn), 0.35, 0.5, 1.4))
        add(b, 0, noise(0.12, 0.2, lp=0.9, hp=0.3, curve=2))
        sfx(f"combo_{lvl}", b, 0.8)


def sfx_miss():
    b = buf(0.5)
    add(b, 0, tone(0.45, 330, 0.6, f1=100, wave_="square", curve=1.6))
    add(b, 0, tone(0.45, 165, 0.4, f1=50, curve=1.5))
    sfx("miss", b, 0.8)


def sfx_over():
    b = buf(1.6)
    for i, m in enumerate((67, 64, 60, 55)):
        add(b, i * 0.28, pluck(midi(m), 0.7, 0.6, 0.6))
        add(b, i * 0.28, pad(midi(m - 12), 0.7, 0.35))
    sfx("over", b, 0.8)


def sfx_click():
    b = buf(0.12)
    add(b, 0, tone(0.09, 900, 0.6, f1=600, wave_="tri", curve=3))
    add(b, 0, noise(0.02, 0.4, lp=0.9, hp=0.3, curve=1))
    sfx("click", b, 0.6)


def sfx_freeze():
    b = buf(1.0)
    for i in range(8):
        add(b, i * 0.05, tone(0.5, 2600 - i * 220, 0.18, curve=2.5, harm=((2.7, 0.3),)))
    add(b, 0, noise(0.6, 0.35, lp=0.9, hp=0.4, curve=2.5))
    add(b, 0, pad(midi(84), 0.9, 0.3))
    sfx("freeze", b, 0.85)


def sfx_frenzy():
    b = buf(0.9)
    for i, m in enumerate((72, 76, 79, 84, 88, 91)):
        add(b, i * 0.06, tone(0.3, midi(m), 0.4, wave_="square", curve=2))
    add(b, 0, noise(0.2, 0.2, lp=0.9, hp=0.3))
    sfx("frenzy", b, 0.8)


def sfx_powerup():
    b = buf(0.9)
    for i, m in enumerate((72, 79, 84, 88)):
        add(b, i * 0.07, pluck(midi(m), 0.6, 0.55, 1.5))
        add(b, i * 0.07, tone(0.3, midi(m + 12), 0.15, curve=3))
    add(b, 0, noise(0.5, 0.15, lp=0.95, hp=0.5, curve=2))
    sfx("powerup", b, 0.85)


def sfx_boss_hit():
    b = buf(0.5)
    add(b, 0, tone(0.4, 120, 1.0, f1=40, curve=2))
    add(b, 0, noise(0.15, 0.8, lp=0.7, curve=2))
    add(b, 0.0, tone(0.3, 700, 0.3, f1=300, wave_="saw", curve=4))
    sfx("boss_hit", b, 0.95)


def sfx_boss_down():
    b = buf(2.0)
    add(b, 0, noise(1.6, 0.9, lp=0.25, sweep=0.02, curve=1.4))
    add(b, 0, tone(1.4, 80, 1.0, f1=22, curve=1.2))
    for i, m in enumerate((60, 64, 67, 72, 76)):
        add(b, 0.5 + i * 0.12, pluck(midi(m), 0.9, 0.5, 1.2))
    sfx("boss_down", b, 0.95)


def sfx_ach():
    b = buf(1.3)
    for i, m in enumerate((72, 76, 79, 84)):
        add(b, i * 0.1, pluck(midi(m), 0.9, 0.5, 1.3))
    add(b, 0.4, pad(midi(72), 0.8, 0.4))
    add(b, 0.4, pad(midi(79), 0.8, 0.3))
    sfx("achievement", b, 0.85)


def sfx_tick():
    b = buf(0.1)
    add(b, 0, tone(0.08, 1200, 0.5, curve=4))
    sfx("tick", b, 0.5)


def kick(b, t):
    add(b, t, tone(0.18, 150, 0.9, f1=45, curve=2.5), loop=True)


def hat(b, t, v=0.12, rng=random):
    add(b, t, noise(0.04, v, lp=0.9, hp=0.5, curve=2, rng=rng), loop=True)


def clap(b, t, rng=random):
    add(b, t, noise(0.12, 0.3, lp=0.6, hp=0.3, curve=2.2, rng=rng), loop=True)


def track(name, bpm, bars, chords, melody_scale, lead_vol, bass_style, drum_style, seed, bright=1.0):
    """chords: list of (root_midi, [intervals]) one per bar (cycled). Loops seamlessly."""
    rng = random.Random(seed)
    beat = 60.0 / bpm
    b = buf(bars * 4 * beat)
    for bar in range(bars):
        root, ivs = chords[bar % len(chords)]
        t0 = bar * 4 * beat
        add(b, t0, pad(midi(root + 12), 4 * beat * 1.02, 0.30), loop=True)
        add(b, t0, pad(midi(root + 12 + ivs[1]), 4 * beat * 1.02, 0.22), loop=True)
        for step in range(8):
            t = t0 + step * beat / 2
            if bass_style == "pulse":
                add(b, t, pluck(midi(root - 12), beat * 0.45, 0.55, 0.7), loop=True)
            elif bass_style == "soft" and step % 4 == 0:
                add(b, t, pluck(midi(root - 12), beat * 1.8, 0.5, 0.5), loop=True)
            arp = root + 12 + ivs[step % len(ivs)] + (12 if step % 4 == 3 else 0)
            add(b, t, pluck(midi(arp), beat * 0.6, 0.22 * bright, 1.0), loop=True)
            if rng.random() < 0.62:
                nn = root + 24 + rng.choice(melody_scale)
                ln = rng.choice((0.5, 0.5, 1.0, 1.5)) * beat
                add(b, t, pluck(midi(nn), ln, lead_vol, 1.3), loop=True)
            if drum_style == "four":
                if step % 2 == 0:
                    kick(b, t)
                if step % 4 == 2:
                    clap(b, t, rng)
                hat(b, t + (beat / 4 if step % 2 == 0 else 0), 0.1, rng)
            elif drum_style == "soft":
                if step in (0, 5):
                    kick(b, t)
                if step % 2 == 1:
                    hat(b, t, 0.07, rng)
            elif drum_style == "drive":
                if step % 2 == 0:
                    kick(b, t)
                if step in (2, 6):
                    clap(b, t, rng)
                hat(b, t, 0.12, rng)
                hat(b, t + beat / 4, 0.07, rng)
    write(name, finish(b, 0.8), "music", music=True)


def main():
    os.makedirs(os.path.join(ROOT, "sfx"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "music"), exist_ok=True)
    for fn in (sfx_swoosh, sfx_slice, sfx_splat, sfx_bomb, sfx_combo, sfx_miss, sfx_over, sfx_click,
               sfx_freeze, sfx_frenzy, sfx_powerup, sfx_boss_hit, sfx_boss_down, sfx_ach, sfx_tick):
        fn()
    major = [0, 2, 4, 7, 9, 12]
    minor = [0, 3, 5, 7, 10, 12]
    track("menu", 96, 8, [(60, [0, 4, 7, 11]), (57, [0, 3, 7, 10]), (53, [0, 4, 7, 11]), (55, [0, 4, 7, 10])],
          major, 0.2, "soft", "soft", 11, 0.8)
    track("play", 128, 12, [(60, [0, 4, 7]), (55, [0, 4, 7]), (57, [0, 3, 7]), (53, [0, 4, 7])],
          major, 0.28, "pulse", "four", 22)
    track("tense", 152, 12, [(57, [0, 3, 7]), (53, [0, 4, 7]), (50, [0, 3, 7]), (52, [0, 4, 7])],
          minor, 0.26, "pulse", "drive", 33, 1.1)


if __name__ == "__main__":
    main()

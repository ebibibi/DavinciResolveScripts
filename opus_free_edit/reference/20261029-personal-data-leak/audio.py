"""timeline.json -> work/audio_mix.wav (48 kHz stereo). Presenter mic mixed to mono and put on both channels."""
import json
import os
import subprocess
import wave

import numpy as np

os.chdir("/home/ebi/video-jobs/20261029-personal-data-leak")
SR, FPS = 48000, 30
SPF = SR // FPS
TL = json.load(open("work/timeline.json"))


def read_wav(path):
    with wave.open(path) as w:
        ch, n = w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    return x.reshape(-1, ch)


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def active_rms(x):
    hop = SR // 50
    m = x[: len(x) // hop * hop].reshape(-1, hop)
    r = np.sqrt((m ** 2).mean(1))
    return float(np.sqrt((r[r > np.percentile(r, 60)] ** 2).mean()))


def fade(seg, n=288):
    n = min(n, len(seg) // 2)
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    seg[:n] *= ramp
    seg[-n:] *= ramp[::-1]
    return seg


rng = np.random.default_rng(7)


def whoosh(d=0.5):
    n = int(SR * d)
    noise = rng.standard_normal(n).astype(np.float32)
    t = np.linspace(0, 1, n)
    out = np.zeros(n, np.float32)
    y = 0.0
    for i in range(n):  # one-pole low-pass with a cutoff sweeping up then down
        a = 0.02 + 0.25 * np.sin(np.pi * t[i]) ** 2
        y += a * (noise[i] - y)
        out[i] = y
    out *= np.sin(np.pi * t) ** 2
    return out / np.abs(out).max()


def pop(d=0.12):
    t = np.arange(int(SR * d)) / SR
    f = 900 * np.exp(-t * 12) + 300
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)
    return (s / np.abs(s).max()).astype(np.float32)


def ding(d=0.5):
    t = np.arange(int(SR * d)) / SR
    s = (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 9)
    s[: 96] *= np.linspace(0, 1, 96)
    return (s / np.abs(s).max()).astype(np.float32)


def main():
    total = TL["total"]
    out = np.zeros((total * SPF, 2), np.float32)
    src = read_wav("work/src_audio.wav").mean(1)
    speech = active_rms(src[: SR * 600])
    for p in TL["pieces"]:
        a = p["o0"] * SPF
        if p["kind"] == "talk":
            seg = fade(src[p["f0"] * SPF: p["f1"] * SPF].copy())
            out[a: a + len(seg)] += seg[:, None]
        elif p["kind"] == "ebifry":
            v = read_wav(f"work/ebifry/{p['id']}.wav").mean(1)
            v = v * (speech / active_rms(v))
            st = a + int(0.25 * SR)
            v = v[: max(0, p["o1"] * SPF - st)]
            out[st: st + len(v)] += v[:, None]
        else:
            clip = decode(p["file"])[: p["n"] * SPF]
            out[a: a + len(clip)] += clip * 0.8
    lib = {"whoosh": (whoosh(), 0.10), "pop": (pop(), 0.16), "ding": (ding(), 0.11)}
    for fx in TL["sfx"]:
        s, g = lib[fx["kind"]]
        a = fx["o"] * SPF
        seg = s[: max(0, len(out) - a)] * g * speech / 0.1
        out[a: a + len(seg)] += seg[:, None]
    peak = np.abs(out).max()
    if peak > 0.98:
        out *= 0.98 / peak
    with wave.open("work/audio_mix.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    print("audio", len(out) / SR, "s; speech rms", speech)


if __name__ == "__main__":
    main()

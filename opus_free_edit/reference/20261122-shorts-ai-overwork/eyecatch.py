"""Closing eyecatch (2026-11-22 review: 「唐突に終わるので、最後にはアイキャッチが欲しい」).

Appends a 1.5 s branded close to an already-rendered short, without re-rendering the short itself:
  work/build/<sid>_video.mp4 + <sid>.wav  ->  work/build/<sid>_ec_video.mp4 + <sid>_ec.wav
then finalize.py <sid> --ec loudness-normalises and muxes to out/<sid>.mp4.

Look (same for all shorts): gold slash lines (the channel stinger's lines) cut across the last frame and wipe
it to the short's warm-charcoal background; えびフライ pops in silently (mouth closed); the short's theme in one
phrase, his own words, sits in a gold pill under him. No logo, no text that invites anyone anywhere.
Audio: a soft synthesized two-note bell over a faint swish, well under his voice, never over his words.
usage: eyecatch.py s1 [--png]   (--png: also write a few still frames to work/eyecatch/ for review)
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

ROOT = '/home/ebi/video-jobs/20261121-ai-overwork-shorts/'
os.chdir(ROOT)
sys.path.insert(0, ROOT + 'work/scripts')
sys.path.insert(0, os.path.expanduser('~/work/ebi-explainer-video'))
import render  # noqa: E402  (background(), over(), constants)
from text import text_block  # noqa: E402
from explainer import char  # noqa: E402

FPS, W, H, SR = 30, 1080, 1920, 48000
N = 45                       # 1.5 s
GOLD = (246, 190, 60)
PHRASE = {                   # his own words, the punchline of each short
    's1': 'AIは疲れず、人間は疲れる',
    's2': 'もっと任せる仕組みを',
    's3': '自分の数字を、ちゃんと見る',
}
CX = render.CX               # 515: keeps clear of the right-hand button column
EBI_FOOT = 1050              # えびフライ feet; head ends well below the 270 px top safe line
PILL_CY = 1150               # pill bottom ~1205 < 1248 (= 1920 - 672, the strictest bottom safe line)
LINES = [                    # slash lines: (angle deg, offset from centre along normal, width, delay frames)
    (-28, -150, 10, 0), (-28, 40, 16, 2), (-28, 230, 6, 4),
]


def ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def last_frame(sid):
    vid = f'work/build/{sid}_video.mp4'
    out = subprocess.run(['ffmpeg', '-loglevel', 'error', '-sseof', '-0.2', '-i', vid, '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    fr = np.frombuffer(out, np.uint8).reshape(-1, H, W, 3)
    return fr[-1].copy()


def slash_layer(f, persist):
    """gold lines sweeping across; afterwards they stay as faint decoration"""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for ang, off, wid, dl in LINES:
        p = ease((f - dl) / 7)
        if p <= 0:
            continue
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)          # direction of the line
        nx, ny = -uy, ux                            # normal
        cx, cy = W / 2 + nx * off, 820 + ny * off
        L = 1400
        x0, y0 = cx - ux * L, cy - uy * L
        x1, y1 = x0 + ux * 2 * L * p, y0 + uy * 2 * L * p
        alpha = 255 if not persist else int(255 * (0.35 + 0.65 * max(0, 1 - (f - 10) / 10)))
        d.line([(x0, y0), (x1, y1)], fill=GOLD + (alpha,), width=wid)
    return im


def wipe_mask(f):
    """diagonal wipe from the last frame to the card, led by the slash lines"""
    x = min(1.0, max(0.0, (f - 1) / 10))
    p = x * x * (3 - 2 * x)                        # ease-in-out: the last frame leaves with the lines, not before
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    s = (xx * 0.47 + yy * 0.88)                    # along the lines' normal
    edge = -200 + p * (s.max() + 400)
    return np.clip((edge - s) / 120, 0, 1)[..., None]


def ebifry_layer(f):
    t = f / FPS
    age = t - 0.27
    if age < 0:
        return None
    char.CENTER_X, char.FOOT_Y, char.HEIGHT = 330, 690, 560
    fr = Image.new('RGBA', (660, 720), (0, 0, 0, 0))
    char.draw(fr, t, 'standing', 0.0, age, 5.0)
    k = ease(age / 0.18)
    return fr, k


def pill(sid):
    tb = text_block([PHRASE[sid]], 72, fill=(30, 22, 18))
    pw, ph = tb.width + 70, tb.height + 18
    im = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, pw - 1, ph - 1), ph // 2, fill=GOLD + (255,))
    im.alpha_composite(tb, (35, 9))
    return im


def frames(sid):
    last = last_frame(sid).astype(np.float32)
    bg = render.background().astype(np.float32)
    pl = pill(sid)
    for f in range(N):
        m = wipe_mask(f)
        img = (last * (1 - m) + bg * m).astype(np.uint8)
        render.over(img, slash_layer(f, persist=f > 10), 0, 0)   # lines stay behind えびフライ
        e = ebifry_layer(f)
        if e:
            fr, k = e
            render.over(img, fr, CX - 330, EBI_FOOT - 690 + (1 - k) * 60, alpha=k)
        kp = ease((f - 10) / 7)
        if kp > 0:
            render.over(img, pl, CX - pl.width / 2, PILL_CY - pl.height / 2 + (1 - kp) * 30, alpha=kp)
        yield f, img


def sting():
    """soft two-note bell + faint swish; returns mono float32 of N frames"""
    n = N * SR // FPS
    t = np.arange(n) / SR
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n).astype(np.float32)
    # swish: noise, smoothed (cheap low-pass), shaped 0-0.3 s
    k = 40
    noise = np.convolve(noise, np.ones(k) / k, mode='same')
    sw = noise * np.clip(t / 0.12, 0, 1) * np.clip((0.32 - t) / 0.2, 0, 1) * 0.5
    bell = np.zeros(n, np.float32)
    for t0, fq in ((0.20, 783.99), (0.38, 1174.66)):  # G5 then D6
        tt = np.clip(t - t0, 0, None)
        on = (t >= t0).astype(np.float32)
        env = on * np.exp(-tt / 0.55) * np.clip(tt / 0.008, 0, 1)
        bell += env * (np.sin(2 * np.pi * fq * tt) + 0.35 * np.sin(2 * np.pi * 2 * fq * tt)
                       + 0.12 * np.sin(2 * np.pi * 3.01 * fq * tt))
    # soft pad underneath so the tail never drops to silence before the loop
    pad = 0.18 * (np.sin(2 * np.pi * 392 * t) + 0.5 * np.sin(2 * np.pi * 587.33 * t)) * np.clip((t - 0.15) / 0.3, 0, 1)
    y = sw + bell + pad
    y *= np.clip((t[-1] - t) / 0.08, 0, 1)          # 80 ms fade at the very end
    return (y / np.abs(y).max()).astype(np.float32)


def read_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels())
    return x.astype(np.float32) / 32768


def main():
    sid = sys.argv[1]
    os.makedirs('work/eyecatch', exist_ok=True)
    card = f'work/eyecatch/{sid}_card.mp4'
    enc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                            '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
                            '-profile:v', 'high', '-pix_fmt', 'yuv420p', card], stdin=subprocess.PIPE)
    for f, img in frames(sid):
        enc.stdin.write(img.tobytes())
        if '--png' in sys.argv and f in (0, 4, 8, 12, 20, 44):
            Image.fromarray(img).save(f'work/eyecatch/{sid}_ec{f:02d}.png')
    enc.stdin.close()
    enc.wait()
    # video: re-encode short + card in one pass (same settings) so the join is frame-exact
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', f'work/build/{sid}_video.mp4', '-i', card,
                    '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-r', str(FPS),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                    f'work/build/{sid}_ec_video.mp4'], check=True)
    # audio: short + sting at a soft level relative to his voice
    a = read_wav(f'work/build/{sid}.wav')
    nv = int(round(len(a) / (SR / FPS)))
    vid_frames = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                     '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0',
                                     f'work/build/{sid}_video.mp4'], capture_output=True, text=True).stdout.strip())
    a = a[:vid_frames * SR // FPS]
    if len(a) < vid_frames * SR // FPS:
        a = np.concatenate([a, np.zeros((vid_frames * SR // FPS - len(a), 2), np.float32)])
    mono = a.mean(1)
    hop = SR // 20
    rms = np.sqrt((mono[:len(mono) // hop * hop].reshape(-1, hop) ** 2).mean(1))
    voice = float(np.median(rms[rms > rms.max() * 0.05]))
    s = sting()
    s_rms = float(np.sqrt(np.mean(s[: int(0.9 * SR)] ** 2)))
    s *= voice * 0.32 / s_rms                        # soft: bell peaks stay a few dB under his voice
    out = np.concatenate([a, np.stack([s, s], 1)])
    st = np.clip(out * 32767, -32768, 32767).astype(np.int16)
    with wave.open(f'work/build/{sid}_ec.wav', 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
    print(sid, 'video frames', vid_frames, '+', N, 'audio s', len(out) / SR, '(wav had', nv, 'frames)')


if __name__ == '__main__':
    main()

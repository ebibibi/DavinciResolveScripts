"""Audio helpers: 10 ms dB envelope of the raw recording, snap cut points to quiet, split a range into voiced islands."""
import numpy as np, wave
ROOT = '/home/ebi/video-jobs/20261121-ai-overwork-shorts/'
_w = wave.open(ROOT + 'work/raw48.wav'); SR = _w.getframerate()
X = np.frombuffer(_w.readframes(_w.getnframes()), np.int16).astype(np.float32) / 32768
HOP = SR // 100
_n = len(X) // HOP
DB = 20 * np.log10(np.sqrt((X[:_n * HOP].reshape(_n, HOP) ** 2).mean(1)) + 1e-9)
FLOOR = np.percentile(DB, 10)

def db(t):
    i = int(t * 100); return DB[max(0, min(i, _n - 1))]

def islands(a, b, thr=None, min_gap=0.22, pad=0.06):
    """voiced sub-ranges of [a,b]; gaps shorter than min_gap are kept"""
    thr = FLOOR + 9 if thr is None else thr
    i0, i1 = int(a * 100), int(b * 100)
    v = DB[i0:i1] > thr
    segs, s = [], None
    for k, on in enumerate(v):
        if on and s is None: s = k
        if not on and s is not None: segs.append([s, k]); s = None
    if s is not None: segs.append([s, len(v)])
    merged = []
    for s, e in segs:
        if merged and (s - merged[-1][1]) / 100 < min_gap: merged[-1][1] = e
        else: merged.append([s, e])
    merged = [m for m in merged if (m[1] - m[0]) >= 4]
    return [[max(a, (i0 + s) / 100 - pad), min(b, (i0 + e) / 100 + pad)] for s, e in merged]

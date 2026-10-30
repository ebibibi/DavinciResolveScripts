"""QA on a rendered video: flash frames (1-3 frame anomalies) and frozen presenter stretches (>= 3 s).
usage: qa.py VIDEO   (ignores CLIP shots: stingers and end card)"""
import json, subprocess, sys, os
import numpy as np
os.chdir("/home/ebi/video-jobs/20261029-personal-data-leak")
TL = json.load(open("work/timeline.json"))
clip = [(s["o0"], s["o1"]) for s in TL["shots"] if s["layout"] == "CLIP"]
w, h = 480, 270
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-vf", f"fps=30,scale={w}:{h}", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], capture_output=True).stdout
F = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
print("frames", len(F), "timeline", TL["total"])
d = np.abs(np.diff(F, axis=0)).mean((1, 2))           # d[i] = |F[i+1]-F[i]|
inclip = lambda i: any(a - 2 <= i < b + 2 for a, b in clip)
cuts = {s["o0"] for s in TL["shots"]} | {p["o0"] for p in TL["pieces"]}
flash = []
for i in range(1, len(F) - 3):
    for k in (1, 2, 3):   # frames i..i+k-1 differ from both i-1 and i+k, which agree with each other
        if i + k >= len(F):
            continue
        edge = np.abs(F[i + k] - F[i - 1]).mean()
        if d[i - 1] > 12 and d[i + k - 1] > 12 and edge < 4 and d[i - 1] > 3 * max(edge, 1) and not inclip(i):
            flash.append((i, k))
print("flash candidates:", [(i, round(i / 30, 2), k) for i, k in flash][:40])
# frozen: the presenter's own area (depends on the layout) unchanged for >= 90 frames
REG = {"FULL": (12, 90, 392, 472), "SPLIT": (62, 200, 325, 475), "RECAP": (152, 212, 345, 405)}
def region(L):
    return REG.get(L, (12, 150, 100, 300))
lay = np.empty(len(F), dtype=object)
for sh in TL["shots"]:
    lay[sh["o0"]:sh["o1"]] = sh["layout"]
run = 0; frozen = []
for i in range(1, len(F)):
    L = lay[i]
    if L == "CLIP" or lay[i - 1] != L:
        run = 0
        continue
    y0, y1, x0, x1 = region(L)
    v = (np.abs(F[i, y0:y1, x0:x1] - F[i - 1, y0:y1, x0:x1]) >= 3).mean()   # live camera always has some change
    run = run + 1 if v < 0.002 else 0
    if run == 90:
        frozen.append((round(i / 30, 1), L))
print("frozen presenter >= 3 s at:", frozen)

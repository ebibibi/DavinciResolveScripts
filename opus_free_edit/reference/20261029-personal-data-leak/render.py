"""Render work/timeline.json to video (no audio) in parallel chunks.

usage: render.py preview|final [--frames a:b] [--stills o1,o2,...] [--jobs N]
  preview: reads input/proxy.mp4 (upscaled), writes work/preview_video.mp4 at 960x540
  final:   reads input/source.mkv, writes work/final_video.mp4 at 1920x1080
  --stills: write PNGs of single output frames to work/stills/ (uses the source)
"""
import argparse
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

os.environ.setdefault("OMP_NUM_THREADS", "1")
import cv2
import numpy as np

cv2.setNumThreads(1)

sys.path.insert(0, os.path.dirname(__file__))
import gfx  # noqa: E402

JOB = gfx.JOB
os.chdir(JOB)
FPS, W, H = 30, 1920, 1080
GX0, GX1 = 150, 1490
TL = json.load(open("work/timeline.json"))
CUES = json.load(open("work/cues.json"))
PIECES, SHOTS, EVENTS = TL["pieces"], TL["shots"], TL["events"]
EBI_BASE = "work/ebifry"
DX_TRACK = -160
HEAD_Y = 300


# ---------------------------------------------------------------- readers
def read_frames(path, start_s, n, size=None, pix="rgb24", ch=3):
    vf = f"fps={FPS}"
    if size:
        vf += f",scale={size[0]}:{size[1]}:flags=bicubic"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "2", "-ss", f"{start_s:.4f}", "-i", path, "-an", "-vf", vf,
           "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", pix, "-"]
    cmd[cmd.index("-an"):cmd.index("-an")] = ["-filter_threads", "1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10 ** 8)
    w, h = size if size else (W, H)
    last = None
    for _ in range(n):
        buf = p.stdout.read(w * h * ch)
        if len(buf) < w * h * ch:
            if last is None:
                raise RuntimeError(f"no frames from {path} at {start_s}")
            yield last
            continue
        last = np.frombuffer(buf, np.uint8).reshape(h, w, ch)
        yield last
    p.stdout.close()
    p.wait()


# ---------------------------------------------------------------- keyer
def key(frame):
    """Chroma key on the garbage-matted camera crop. Alpha is computed at half resolution (it is soft anyway)."""
    crop = np.ascontiguousarray(frame[:, GX0:GX1])
    small = cv2.resize(crop, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA).astype(np.float32)
    r, g, b = small[..., 0], small[..., 1], small[..., 2]
    rel = (g - np.maximum(r, b)) / (g + 8.0)
    a = 1.0 - np.clip((rel - 0.12) / 0.18, 0, 1)
    a = cv2.erode(a, np.ones((2, 2), np.uint8))
    a = cv2.GaussianBlur(a, (3, 3), 0.7)
    a = cv2.resize(a, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_LINEAR)
    R, G, B = cv2.split(crop)
    G = cv2.min(G, cv2.add(cv2.max(R, B), 2))
    return cv2.merge((R, G, B)), a


def head_x(alpha):
    band = alpha[140:420]
    cols = band.sum(0)
    if cols.sum() < 1000:
        return 920
    return float((cols * np.arange(len(cols))).sum() / cols.sum()) + GX0


def place(fg, a, s, tx, ty, box):
    """Warp camera-crop layer (crop x0 = GX0) with out = cam*s + t into box (x0,y0,x1,y1). Returns fg,a in box."""
    x0, y0, x1, y1 = box
    M = np.float32([[s, 0, GX0 * s + tx - x0], [0, s, ty - y0]])
    size = (x1 - x0, y1 - y0)
    interp = cv2.INTER_LINEAR if s != 1 else cv2.INTER_NEAREST
    f2 = cv2.warpAffine(fg, M, size, flags=interp, borderMode=cv2.BORDER_CONSTANT)
    a2 = cv2.warpAffine(a, M, size, flags=interp, borderMode=cv2.BORDER_CONSTANT)
    return f2, a2


def blend_layer(out, fg, a, box):
    x0, y0, x1, y1 = box
    cols = np.nonzero(a.max(0) > 0.003)[0]
    rows = np.nonzero(a.max(1) > 0.003)[0]
    if len(cols) == 0:
        return
    c0, c1, r0, r1 = cols[0], cols[-1] + 1, rows[0], rows[-1] + 1
    fg = np.ascontiguousarray(fg[r0:r1, c0:c1])
    a = np.ascontiguousarray(a[r0:r1, c0:c1])
    x0, y0, x1, y1 = x0 + c0, y0 + r0, x0 + c1, y0 + r1
    reg = np.ascontiguousarray(out[y0:y1, x0:x1])
    if fg.dtype != np.uint8:
        fg = fg.clip(0, 255).astype(np.uint8)
    out[y0:y1, x0:x1] = cv2.blendLinear(fg, reg, a, 1.0 - a)


def overlay_rgba(out, img, x, y, alpha=1.0):
    h, w = img.shape[:2]
    X0, Y0 = max(0, x), max(0, y)
    X1, Y1 = min(W, x + w), min(H, y + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    sub = img[Y0 - y:Y1 - y, X0 - x:X1 - x]
    a = sub[..., 3].astype(np.float32) * (alpha / 255)
    blend_layer(out, np.ascontiguousarray(sub[..., :3]), a, (X0, Y0, X1, Y1))


# ---------------------------------------------------------------- cached graphics
class Assets:
    def __init__(self):
        self.bg = gfx.background()
        self.split = {}
        self.full = {}
        self.track = {}
        self.lt = {}
        self.cap = {}
        self.bub = {}
        self.recap = {}
        self.circle = {}
        self.ring = {}

    def get(self, cache, k, fn):
        if k not in cache:
            cache[k] = fn()
        return cache[k]


A = None


def pip(out, fg, a, hx, center, d):
    """Round face PiP: circle centred around the mouth/chin so the whole head and the neck show."""
    rad_cam = 330
    s = d / (2 * rad_cam)
    cx, cy = center
    box = (cx - d // 2, cy - d // 2, cx - d // 2 + d, cy - d // 2 + d)
    # camera point (hx, HEAD_Y + 100) -> circle centre
    tx = cx - hx * s
    ty = cy - (HEAD_Y + 100) * s
    f2, a2 = place(fg, a, s, tx, ty, box)
    m = A.get(A.circle, d, lambda: gfx.circle_mask(d))
    tint = np.empty_like(f2)
    tint[:] = gfx.TEAL_L
    comp = cv2.blendLinear(f2, tint, a2, 1.0 - a2)
    blend_layer(out, comp, m, box)
    rg = A.get(A.ring, d, lambda: gfx.ring(d))
    overlay_rgba(out, rg, box[0] - 8, box[1] - 8)


def shot_at(o):
    for s in SHOTS:
        if s["o0"] <= o < s["o1"]:
            return s
    return SHOTS[-1]


def event_at(o):
    for e in EVENTS:
        if e["o0"] <= o < e["o1"]:
            return e
    return None


def cue_at(o):
    t = (o + 0.5) / FPS
    for c in CUES:
        if c["s"] <= t < c["e"]:
            return c
    return None


SLIDE_FIRST = {}
for s in SHOTS:
    if s.get("layout") in ("FULL", "SPLIT") and s.get("slide") and s["slide"] not in SLIDE_FIRST:
        SLIDE_FIRST[s["slide"]] = s["o0"]
STEP_FIRST = {}
for s in SHOTS:
    if s.get("layout") in ("FACE", "PUNCH") and s["step"] and s["step"] not in STEP_FIRST:
        STEP_FIRST[s["step"]] = s["o0"]


def compose(o, piece, cam, ebi_rgba):
    sh = shot_at(o)
    L = sh["layout"]
    step = piece.get("step", 0)
    if L == "CLIP":
        return cam.copy()
    if L == "RECAP":
        k = o - sh["o0"] if sh["o0"] == min(x["o0"] for x in SHOTS if x["layout"] == "RECAP") else 999
        vis = min(gfx.RECAP_N, 1 + k // 12)
        out = A.get(A.recap, vis, lambda: gfx.recap_card(vis)).copy()
        fg, a = key(cam)
        pip(out, fg, a, piece["_hx"], (1500, 730), 240)
    elif L in ("FULL", "SPLIT"):
        n = sh["slide"]
        fg, a = key(cam)
        if L == "FULL":
            out = A.get(A.full, n, lambda: gfx.slide_full(n)).copy()
            pip(out, fg, a, piece["_hx"], (1730, 205), 320)
        else:
            out = A.bg.copy()
            out[:, :1280] = A.get(A.split, n, lambda: gfx.slide_split(n))
            out[:, 1280:] = (np.array(gfx.TEAL_L) * 0.6 + np.array(gfx.CREAM) * 0.4).astype(np.uint8)
            out[:, 1278:1282] = (200, 214, 211)
            s = 0.85
            tx = 1600 - piece["_hx"] * s
            ty = H - H * s
            f2, a2 = place(fg, a, s, tx, ty, (1282, 0, W, H))
            blend_layer(out, f2, a2, (1282, 0, W, H))
        k = o - SLIDE_FIRST.get(n, -100)
        if 0 <= k < 8:  # first appearance of a slide: soft fade in from the background
            al = (k + 1) / 9
            out = (A.bg * (1 - al) + out * al).astype(np.uint8)
    else:  # FACE / PUNCH / FACEC / PUNCHC / EBI
        fg, a = key(cam)
        out = A.bg.copy()
        track = L in ("FACE", "PUNCH") and step > 0
        dx = DX_TRACK if (track or L == "EBI") else 960 - piece["_hx"]
        if L.startswith("PUNCH"):
            s = 1.12
            ax, ay = piece["_hx"], HEAD_Y
            tx = ax * (1 - s) + dx
            ty = ay * (1 - s)
        else:
            s, tx, ty = 1.0, dx, 0
        f2, a2 = place(fg, a, s, tx, ty, (0, 0, W, H))
        blend_layer(out, f2, a2, (0, 0, W, H))
        if track:
            k = o - STEP_FIRST.get(step, -999)
            glow = round(max(0.0, math.sin(k / 90 * math.pi * 3)) * 4) / 4 if 0 <= k < 90 else 0.0
            tr = A.get(A.track, (step, glow), lambda: gfx.tracker(step, glow))
            overlay_rgba(out, tr, W - tr.shape[1] - 30, 36)
        if L != "EBI":
            e = event_at(o)
            if e:
                img = A.get(A.lt, (e["kind"], e["text"]), lambda: gfx.lower_third(e["kind"], e["text"]))
                k, r = o - e["o0"], e["o1"] - o
                al = min(1.0, (k + 1) / 7, r / 6)
                x = 70 - int(max(0, 7 - k) * 9)
                overlay_rgba(out, img, x, gfx.LT_BOTTOM - img.shape[0] + 12, al)
    if L == "EBI":
        b = A.get(A.bub, piece["id"], lambda: gfx.bubble(piece["bubble"]))
        k = o - piece["o0"]
        al = min(1.0, max(0.0, (k - 6) / 5))
        if ebi_rgba is not None:
            overlay_rgba(out, ebi_rgba, W - 560 - 30, H - 520)
        overlay_rgba(out, b, W - b.shape[1] - 230, H - 520 - b.shape[0] + 70, al)
    elif piece["kind"] == "talk":
        c = cue_at(o)
        if c:
            img = A.get(A.cap, tuple(c["lines"]), lambda: gfx.caption(c["lines"]))
            overlay_rgba(out, img, 0, gfx.CAP_BOTTOM - img.shape[0] + 30)
    return out


def piece_frames(p, k0, n, proxy):
    """Frames k0..k0+n of piece p (camera or clip) + optional えびフライ RGBA frames."""
    if p["kind"] in ("stinger", "outro"):
        for f in read_frames(p["file"], k0 / FPS, n):
            yield f, None
        return
    start = p["f0"] if p["kind"] == "talk" else p["src_f0"]
    path = "input/proxy.mp4" if proxy else "input/source.mkv"
    size = (W, H) if proxy else None
    cams = read_frames(path, (start + k0) / FPS, n, size=size)
    if p["kind"] == "ebifry":
        ebis = read_frames(f"{EBI_BASE}/{p['id']}.mov", k0 / FPS, n, size=(560, 520), pix="rgba", ch=4)
        for c, e in zip(cams, ebis):
            yield c, e
    else:
        for c in cams:
            yield c, None


def hx_for(p, proxy):
    if p["kind"] in ("stinger", "outro"):
        return 920
    start = p["f0"] if p["kind"] == "talk" else p["src_f0"]
    path = "input/proxy.mp4" if proxy else "input/source.mkv"
    fr = next(read_frames(path, (start + min(p["n"] // 2, 15)) / FPS, 1, size=(W, H) if proxy else None))
    return head_x(key(fr)[1])


def render_range(args):
    a, b, outpath, mode = args
    global A
    A = Assets()
    proxy = mode == "preview"
    enc = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if proxy:
        enc += ["-vf", "scale=960:540", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-threads", "2"]
    else:
        enc += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
                "-threads", "3", "-x264-params", "keyint=60:min-keyint=30"]
    enc += [outpath]
    pe = subprocess.Popen(enc, stdin=subprocess.PIPE)
    for p in PIECES:
        lo, hi = max(a, p["o0"]), min(b, p["o1"])
        if lo >= hi:
            continue
        p = dict(p)
        p["_hx"] = hx_for(p, proxy)
        for i, (cam, ebi) in enumerate(piece_frames(p, lo - p["o0"], hi - lo, proxy)):
            pe.stdin.write(compose(lo + i, p, cam, ebi).tobytes())
    pe.stdin.close()
    pe.wait()
    return outpath


def stills(frames):
    global A
    A = Assets()
    os.makedirs("work/stills", exist_ok=True)
    for o in frames:
        p = next(p for p in PIECES if p["o0"] <= o < p["o1"])
        p = dict(p)
        p["_hx"] = hx_for(p, False)
        cam, ebi = next(piece_frames(p, o - p["o0"], 1, False))
        cv2.imwrite(f"work/stills/o{o:06d}.jpg", cv2.cvtColor(compose(o, p, cam, ebi), cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["preview", "final", "stills"])
    ap.add_argument("--frames", default=None)
    ap.add_argument("--stills", default="")
    ap.add_argument("--jobs", type=int, default=12)
    args = ap.parse_args()
    if args.mode == "stills":
        stills([int(x) for x in args.stills.split(",") if x])
        return
    total = TL["total"]
    a, b = (0, total) if not args.frames else map(int, args.frames.split(":"))
    # chunk boundaries at shot starts, about equal size
    n = args.jobs * 2
    cuts = [a]
    starts = sorted({s["o0"] for s in SHOTS if a < s["o0"] < b})
    for i in range(1, n):
        target = a + (b - a) * i // n
        c = min(starts, key=lambda x: abs(x - target)) if starts else target
        if c > cuts[-1]:
            cuts.append(c)
    cuts.append(b)
    os.makedirs("work/chunks", exist_ok=True)
    jobs = [(cuts[i], cuts[i + 1], f"work/chunks/{args.mode}_{i:03d}.mp4", args.mode) for i in range(len(cuts) - 1)]
    with Pool(args.jobs) as pool:
        outs = pool.map(render_range, jobs, chunksize=1)
    lst = f"work/chunks/{args.mode}_list.txt"
    with open(lst, "w") as f:
        for o in outs:
            f.write(f"file '{os.path.basename(o)}'\n")
    dst = "work/preview_video.mp4" if args.mode == "preview" else "work/final_video.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    dst], check=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()

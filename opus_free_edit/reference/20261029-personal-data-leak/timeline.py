"""EDL (work/edl_blocks.json) -> work/timeline.json

Everything is decided on one integer clock: output frames at FPS=30. A talk segment is a
source frame range [f0, f1) on the same 30 fps grid (source time = f / 30).
"""
import json
import math
import os
import subprocess

import numpy as np

os.chdir("/home/ebi/video-jobs/20261029-personal-data-leak")
FPS = 30
MERGE_GAP = 0.45      # pauses up to this stay untouched
PAD_IN, PAD_OUT = 0.08, 0.15
SPEECH_DB = -45.0
DROP = [(467.9, 468.2), (1702.7, 1705.8)]  # 「はい。」after the aside / 「あの、うん。」hesitation

words = json.load(open("work/words.json"))
db = np.load("work/db10ms.npy")
edl = json.load(open("work/edl_blocks.json"))["blocks"]
clips = json.load(open("work/ebifry/clips.json"))


def active(t0, t1):
    i0, i1 = int(t0 * 100), max(int(t0 * 100) + 1, int(math.ceil(t1 * 100)))
    idx = np.nonzero(db[i0:i1] > SPEECH_DB)[0]
    if len(idx) == 0:
        return None
    return (i0 + idx[0]) / 100, (i0 + idx[-1] + 1) / 100


def block_words(t0, t1):
    out = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        if not (t0 <= mid <= t1) or any(a <= mid <= b for a, b in DROP):
            continue
        s, e = w["start"], w["end"]
        if e - s > 0.8:  # never trust a long word: keep only its audible part
            act = active(s, e)
            if act is None:
                continue
            s, e = act
        out.append({"w": w["word"], "s": s, "e": e})
    return out


def islands(ws):
    isl = []
    for w in ws:
        if isl and w["s"] - isl[-1]["e"] <= MERGE_GAP:
            isl[-1]["e"] = max(isl[-1]["e"], w["e"])
            isl[-1]["words"].append(w)
        else:
            isl.append({"s": w["s"], "e": w["e"], "words": [w]})
    return isl


# speech level of the source measured like check_silence.py (50 ms windows, median of the loud ones)
_w = db[: len(db) // 5 * 5].reshape(-1, 5)
_w50 = 10 * np.log10((10 ** (_w / 10)).mean(1))
SILENT_DB = float(np.median(_w50[_w50 > np.percentile(_w50, 40)])) - 20.0   # 2 dB stricter than the checker
MAX_INNER_SILENCE = 0.40


def split_inner_silences(isl):
    """Split islands where the audio itself is silent for longer than MAX_INNER_SILENCE (word stamps lie)."""
    out = []
    for il in isl:
        i0, i1 = int(il["s"] * 100), int(math.ceil(il["e"] * 100))
        quiet = db[i0:i1] < SILENT_DB
        cuts, k = [], 0
        while k < len(quiet):
            if quiet[k]:
                j = k
                while j < len(quiet) and quiet[j]:
                    j += 1
                if (j - k) / 100 > MAX_INNER_SILENCE:
                    cuts.append(((i0 + k) / 100, (i0 + j) / 100))
                k = j
            else:
                k += 1
        bounds = [il["s"]] + [x for ab in cuts for x in ab] + [il["e"]]
        parts = list(zip(bounds[0::2], bounds[1::2]))
        for pi, (a, b) in enumerate(parts):
            nxt = parts[pi + 1][0] if pi + 1 < len(parts) else 1e9
            lo = cuts[pi - 1][0] if pi else -1e9
            hi = cuts[pi][0] if pi < len(cuts) else 1e9
            ws = [w for w in il["words"] if lo <= w["s"] < hi]
            if b - a > 0.05 and ws:
                out.append({"s": a, "e": b, "words": ws})
            elif out and ws:
                out[-1]["words"] += ws
    return out


def segments_for(t0, t1):
    isl = split_inner_silences(islands(block_words(t0, t1)))
    segs = []
    for k, il in enumerate(isl):
        s = il["s"] - PAD_IN
        e = il["e"] + PAD_OUT
        if k > 0:
            s = max(s, (isl[k - 1]["e"] + il["s"]) / 2)
        if k + 1 < len(isl):
            e = min(e, (il["e"] + isl[k + 1]["s"]) / 2)
        f0, f1 = int(round(s * FPS)), int(round(e * FPS))
        segs.append({"f0": f0, "f1": f1, "words": il["words"]})
    # merge segments that touch on the frame grid (contiguous source)
    merged = []
    for sg in segs:
        if merged and sg["f0"] <= merged[-1]["f1"]:
            merged[-1]["f1"] = max(merged[-1]["f1"], sg["f1"])
            merged[-1]["words"] += sg["words"]
        else:
            merged.append(sg)
    return merged


def media_frames(path):
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True).stdout)
    return int(round(d * FPS))


def build():
    by_id = {b["id"]: b for b in edl}
    splits = {}   # block id -> (split time, ebifry id)
    befores = {}
    for b in edl:
        if b.get("type") == "ebifry":
            if "after" in b:
                splits[b["after"]] = (b["split_at"], b["id"])
            else:
                befores[b["before"]] = b["id"]
    pieces = []

    def add_ebifry(gid):
        g = by_id[gid]
        n = int(math.ceil(clips[gid]["seconds"] * FPS))
        r0 = int(round(g["react"][0] * FPS))
        assert n <= int(g["react"][1] * FPS) - r0, gid
        pieces.append({"kind": "ebifry", "id": gid, "n": n, "text": clips[gid]["text"],
                       "src_f0": r0, "step": pieces[-1]["step"] if pieces else 0})

    def add_talk(b, t0, t1, part):
        for sg in segments_for(t0, t1):
            pieces.append({"kind": "talk", "block": b["id"], "part": part, "f0": sg["f0"], "f1": sg["f1"],
                           "n": sg["f1"] - sg["f0"], "step": b["step"], "slide": b["slide"],
                           "layout": b.get("layout"),
                           "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in sg["words"]]})

    for b in edl:
        t = b.get("type", "talk")
        if t == "ebifry":
            continue
        if t == "stinger":
            pieces.append({"kind": "stinger", "id": b["id"], "file": b["file"], "n": media_frames(b["file"]),
                           "step": pieces[-1]["step"]})
            continue
        if b["id"] in befores:
            pieces.append({"kind": "ebifry_placeholder", "id": befores[b["id"]]})
        if b["id"] in splits:
            at, gid = splits[b["id"]]
            add_talk(b, b["src"][0], at, 0)
            pieces.append({"kind": "ebifry_placeholder", "id": gid})
            add_talk(b, at, b["src"][1], 1)
        else:
            add_talk(b, b["src"][0], b["src"][1], 0)
    pieces.append({"kind": "outro", "file": "assets/EBI_CHAN_OUTRO.mp4", "n": media_frames("assets/EBI_CHAN_OUTRO.mp4"),
                   "step": 0})
    # resolve placeholders (needs the previous piece's step)
    final = []
    for p in pieces:
        if p["kind"] == "ebifry_placeholder":
            pieces_tmp = pieces
            g = by_id[p["id"]]
            n = int(math.ceil(clips[p["id"]]["seconds"] * FPS))
            r0 = int(round(g["react"][0] * FPS))
            assert n <= int(g["react"][1] * FPS) - r0, p["id"]
            final.append({"kind": "ebifry", "id": p["id"], "n": n, "text": clips[p["id"]]["text"], "src_f0": r0,
                          "bubble": g.get("bubble", clips[p["id"]]["text"]),
                          "step": final[-1]["step"] if final else 0})
        else:
            final.append(p)
    o = 0
    for p in final:
        p["o0"] = o
        o += p["n"]
        p["o1"] = o
    return final, o


def src_to_out(pieces, block, t, side):
    """Map a source time inside a block to an output frame (first kept frame >= t, or last <= t)."""
    f = t * FPS
    segs = [p for p in pieces if p["kind"] == "talk" and p["block"] == block]
    if side == "start":
        for p in segs:
            if p["f1"] > f:
                return p["o0"] + max(0, int(round(f)) - p["f0"])
        return segs[-1]["o1"]
    for p in reversed(segs):
        if p["f0"] < f:
            return p["o0"] + min(p["n"], int(round(f)) - p["f0"])
    return segs[0]["o0"]


def events(pieces):
    ev = []
    for b in edl:
        for e in b.get("events", []):
            o0 = src_to_out(pieces, b["id"], e["at"], "start")
            o1 = src_to_out(pieces, b["id"], e.get("until", b["src"][1]), "end")
            ev.append({"kind": e["kind"], "text": e["text"], "o0": o0, "o1": max(o1, o0 + 45), "block": b["id"]})
    ev.sort(key=lambda e: e["o0"])
    # one lower third at a time: an event ends where the next one starts
    for a, b in zip(ev, ev[1:]):
        if a["o1"] > b["o0"]:
            a["o1"] = b["o0"]
    return ev


if __name__ == "__main__":
    pieces, total = build()
    ev = events(pieces)
    talk = [p for p in pieces if p["kind"] == "talk"]
    print(f"silent below {SILENT_DB:.1f} dB; pieces {len(pieces)} talk segments {len(talk)} total {total} frames = {total / FPS:.1f}s")
    json.dump({"fps": FPS, "total": total, "pieces": pieces, "events": ev}, open("work/timeline_raw.json", "w"),
              ensure_ascii=False, indent=0)

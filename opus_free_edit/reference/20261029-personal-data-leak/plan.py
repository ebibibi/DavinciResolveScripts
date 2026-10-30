"""timeline_raw.json -> timeline.json: shots (layout per frame range), chapter banners, sound effects.

Layouts
  FULL   slide content large + round face PiP (top right)
  SPLIT  slide left 1280 px + presenter column right 640 px
  FACE   keyed presenter, progress tracker on the right (FACEC = centred, no tracker, before step 1)
  PUNCH  FACE at 1.12x (gentle punch-in)
  EBI    presenter listening (source frames from a pause) + えびフライ + speech bubble
  RECAP  checklist recap + round face PiP
  CLIP   inserted full-frame clip (stinger / end card)
Framing changes only at cuts (piece boundaries); every shot is >= MIN_SHOT frames.
"""
import json
import os

os.chdir("/home/ebi/video-jobs/20261029-personal-data-leak")
FPS = 30
MIN_SHOT = 36
TARGETS = [330, 270, 360, 300]   # alternate shot lengths (frames) for variety: 11/9/12/10 s

d = json.load(open("work/timeline_raw.json"))
pieces, events = d["pieces"], d["events"]
forced = {b["id"]: b.get("layout") for b in json.load(open("work/edl_blocks.json"))["blocks"]}


def need_face(p):
    for e in events:
        ov = min(p["o1"], e["o1"]) - max(p["o0"], e["o0"])
        if ov > 0 and (ov >= 0.3 * p["n"] or p["o0"] <= e["o0"] < p["o1"]):
            return True
    return False


def build_shots():
    shots = []
    k = 0
    for p in pieces:
        if p["kind"] != "talk":
            shots.append({"o0": p["o0"], "o1": p["o1"], "kind": p["kind"], "block": p.get("id"), "step": p["step"],
                          "slide": None, "face": True})
            continue
        nf = need_face(p)
        cur = shots[-1] if shots else None
        same = (cur is not None and cur["kind"] == "talk" and cur["block"] == p["block"] and cur["face"] == nf
                and cur["o1"] - cur["o0"] < TARGETS[k % len(TARGETS)])
        if same:
            cur["o1"] = p["o1"]
        else:
            if cur is not None and cur["kind"] == "talk":
                k += 1
            shots.append({"o0": p["o0"], "o1": p["o1"], "kind": "talk", "block": p["block"], "step": p["step"],
                          "slide": p["slide"], "face": nf})
    # merge too-short talk shots into a neighbour of the same block
    changed = True
    while changed:
        changed = False
        for i, s in enumerate(shots):
            if s["kind"] != "talk" or s["o1"] - s["o0"] >= MIN_SHOT:
                continue
            for j in (i - 1, i + 1):
                if 0 <= j < len(shots) and shots[j]["kind"] == "talk":
                    t = shots[j]
                    t["o0"], t["o1"] = min(t["o0"], s["o0"]), max(t["o1"], s["o1"])
                    t["face"] = t["face"] or s["face"]
                    shots.pop(i)
                    changed = True
                    break
            if changed:
                break
    return shots


def assign(shots):
    last_slide, last_step = None, 0
    face_alt, slide_alt = 0, 0
    banners = []
    bannered = set()
    for i, s in enumerate(shots):
        if s["kind"] == "ebifry":
            s["layout"] = "EBI"
            continue
        if s["kind"] in ("stinger", "outro"):
            s["layout"] = "CLIP"
            continue
        f = forced.get(s["block"])
        new_step = s["step"] > 0 and s["step"] != last_step
        if f:
            s["layout"] = f
        elif s["slide"] and s["slide"] != last_slide and not s["face"]:
            s["layout"] = "FULL"
            slide_alt = 1
        elif s["face"] or not s["slide"] or (new_step and s["slide"] == last_slide):
            s["layout"] = ["FACE", "PUNCH"][face_alt % 2] if not new_step else "FACE"
            face_alt += 1
        else:
            s["layout"] = ["SPLIT", "FULL", "SPLIT", "FACE"][slide_alt % 4]
            slide_alt += 1
        if s["step"] == 0 and s["layout"] in ("FACE", "PUNCH"):
            s["layout"] += "C"
        swap = {"FULL": "SPLIT", "SPLIT": "FULL", "FACE": "PUNCH", "PUNCH": "FACE", "FACEC": "PUNCHC",
                "PUNCHC": "FACEC"}
        if not f and i > 0 and shots[i - 1].get("layout") == s["layout"]:
            s["layout"] = swap[s["layout"]]
        if s["layout"] in ("FULL", "SPLIT") and s["slide"]:
            last_slide = s["slide"]
        if new_step:
            last_step = s["step"]
        if s["step"] > 0 and s["step"] not in bannered and s["layout"] in ("FACE", "PUNCH"):
            bannered.add(s["step"])
            banners.append({"o0": s["o0"], "o1": min(s["o1"], s["o0"] + 90), "step": s["step"]})
    # a slide may appear only in shots that talk about it; FULL/SPLIT without slide fall back to FACE
    for s in shots:
        if s["layout"] in ("FULL", "SPLIT") and not s.get("slide"):
            s["layout"] = "FACE"
    return banners


def sfx(shots, banners):
    out = []
    prev = None
    for s in shots:
        L = s["layout"]
        if prev is not None:
            fam = lambda x: "slide" if x in ("FULL", "SPLIT") else x
            if L == "EBI":
                out.append({"o": s["o0"] + 4, "kind": "pop"})
            elif (fam(L) != fam(prev["layout"]) and L in ("FULL", "SPLIT", "RECAP")) or \
                    (L in ("FULL", "SPLIT") and s.get("slide") != prev.get("slide")):
                out.append({"o": s["o0"], "kind": "whoosh"})
        prev = s
    for b in banners:
        out.append({"o": b["o0"], "kind": "whoosh"})
    for e in events:
        if e["kind"] == "check":
            out.append({"o": e["o0"] + 3, "kind": "ding"})
    out.sort(key=lambda x: x["o"])
    dedup = []
    for x in out:
        if any(y["kind"] == x["kind"] and x["o"] - y["o"] < 10 for y in dedup[-3:]):
            continue
        if x["kind"] == "whoosh" and any(y["kind"] == "ding" and abs(x["o"] - y["o"]) < 10 for y in out):
            continue  # a ✅ pop already marks this moment; one sound is enough
        dedup.append(x)
    return dedup


shots = build_shots()
banners = assign(shots)
fx = sfx(shots, banners)
d.update({"shots": shots, "banners": banners, "sfx": fx})
json.dump(d, open("work/timeline.json", "w"), ensure_ascii=False, indent=0)
from collections import Counter
print(Counter(s["layout"] for s in shots))
longest = max(((s["o1"] - s["o0"]) / FPS, s["layout"], s["o0"] / FPS) for s in shots if s["layout"] != "CLIP")
print("shots", len(shots), "longest", longest, "shortest",
      min((s["o1"] - s["o0"]) / FPS for s in shots))
# same layout family run check
run, runs = None, []
for s in shots:
    if run and run[0] == s["layout"]:
        run[2] = s["o1"]
    else:
        run = [s["layout"], s["o0"], s["o1"]]
        runs.append(run)
print("runs > 30 s:", [(r[0], round(r[1] / FPS), round((r[2] - r[1]) / FPS)) for r in runs if r[2] - r[1] > 900])

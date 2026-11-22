"""Refuse shorts that would break a platform rule or a standing requirement.

Reads <job>/out/shorts.json (see shorts-brief.md) and checks every file and post text:
- the file exists, is H.264 + AAC, 1080x1920, stereo 48 kHz, voice on both channels
- it fits the length limit of every platform it is made for, and the post queue's attachment size
- post texts exist for those platforms and do not point to YouTube (shorts must stand on their own)
Usage: check_shorts.py <job dir> [--platforms platforms.json]   exit 0 = all good, 1 = problems listed
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError(f"ffprobe failed: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def check_file(path: Path, platforms: list[str], spec: dict) -> list[str]:
    if not path.is_file() or path.stat().st_size == 0:
        return [f"{path}: missing or empty"]
    try:
        info = probe(path)
    except ValueError as e:
        return [f"{path}: {e}"]
    problems = []
    video = [s for s in info["streams"] if s["codec_type"] == "video"]
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    canvas = spec["canvas"]
    if not video or video[0]["codec_name"] != "h264":
        problems.append(f"{path}: video must be H.264")
    elif (video[0]["width"], video[0]["height"]) != (canvas["width"], canvas["height"]):
        problems.append(f"{path}: {video[0]['width']}x{video[0]['height']}, expected {canvas['width']}x{canvas['height']}")
    if not audio or audio[0]["codec_name"] != "aac" or audio[0].get("channels") != 2 \
            or audio[0].get("sample_rate") != "48000":
        problems.append(f"{path}: audio must be AAC stereo 48 kHz")
    duration = float(info["format"]["duration"])
    for p in platforms:
        limit = spec["targets"][p]["max_duration"]
        if duration > limit:
            problems.append(f"{path}: {duration:.1f} s is over the {p} limit of {limit} s")
    if path.stat().st_size > spec["attachment_max_bytes"]:
        problems.append(f"{path}: {path.stat().st_size} bytes is over the post queue limit")
    stereo = subprocess.run([sys.executable, str(HERE / "check_stereo.py"), str(path)], capture_output=True, text=True)
    if stereo.returncode != 0:
        problems.append(f"{path}: {stereo.stdout.strip()} — {stereo.stderr.strip()}")
    return problems


def check_short(job: Path, short: dict, spec: dict) -> list[str]:
    sid = short.get("id") or "?"
    files, posts = short.get("files") or {}, short.get("posts") or {}
    problems = [f"{sid}: missing {k}" for k in ("id", "title", "idea") if not short.get(k)]
    if not files:
        problems.append(f"{sid}: no files")
    unknown = sorted(set(files) - set(spec["targets"]))
    if unknown:
        problems.append(f"{sid}: unknown platforms {unknown}")
    by_file: dict[str, list[str]] = {}
    for platform, rel in files.items():
        if platform in spec["targets"]:
            by_file.setdefault(rel, []).append(platform)
    for rel, platforms in by_file.items():
        problems += check_file(job / rel, platforms, spec)
    for platform in files:
        text = (posts.get(platform) or "").strip()
        if not text:
            problems.append(f"{sid}: no post text for {platform}")
        hits = [w for w in spec["forbidden_in_posts"] if w.lower() in text.lower()]
        if hits:
            problems.append(f"{sid}: {platform} post points to YouTube ({', '.join(hits)}) — shorts must stand alone")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("--platforms", type=Path, default=HERE / "shorts_platforms.json")
    a = ap.parse_args()
    spec = json.loads(a.platforms.read_text())
    manifest_path = a.job / "out" / "shorts.json"
    try:
        shorts = json.loads(manifest_path.read_text())["shorts"]
    except (OSError, ValueError, KeyError) as e:
        sys.exit(f"check_shorts: cannot read {manifest_path}: {e}")
    if not shorts:
        sys.exit("check_shorts: shorts.json lists no shorts")
    problems = [p for s in shorts for p in check_short(a.job, s, spec)]
    for p in problems:
        print(f"NG {p}", file=sys.stderr)
    if problems:
        sys.exit(1)
    print(f"check_shorts: {len(shorts)} short(s) OK")


if __name__ == "__main__":
    main()

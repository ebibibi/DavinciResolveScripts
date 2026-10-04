#!/usr/bin/env python3
"""Normalise the presenter's name and sign-off in Whisper output, in place.

He says 「胡田です」 at the start and 「Stay Hungry. Stay Foolish. 胡田でした」 at the end of every video.
Even with an initial prompt Whisper writes the name as えびすだ／やびすだ／えびした／エビスタ／ヘビスタ and the
sign-off as Stay Fresh／ステイフリッシュ. (A prompt that contains the exact sentence is worse: Whisper then
skips that sentence entirely, so the prompt only describes them and this script fixes the rest.)

Usage: fix_transcript.py input/transcript   (rewrites .json .srt .vtt .txt .tsv that exist)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(
    r"(?:[えエやヤゆユへヘ][びビみミ][すスしシ][だダたタとト]|[えエ][びビ]下|恵比寿田?|指下|胡田)(?=[\s、。]*(?:です|でした))")
SIGNOFF_RE = re.compile(
    r"(?:stay\s*hungry|ステイ\s*ハングリー)[\s,.、。　]*(?:stay\s*f[a-z]*|ステイ\s*フ[ァ-ヶー]*)[\s.。、]*",
    re.IGNORECASE)
SIGNOFF = "Stay Hungry. Stay Foolish. "
# the two halves end up on separate caption lines when a cue boundary falls between them
HALVES = [
    (re.compile(r"ステイ\s*ハングリー[、。]?"), "Stay Hungry."),
    (re.compile(r"ステイ\s*フ[ァ-ヶー]*シュ[、。]?"), "Stay Foolish."),
]


def fix_text(text: str) -> str:
    text = SIGNOFF_RE.sub(SIGNOFF, text)
    for pattern, replacement in HALVES:
        text = pattern.sub(replacement, text)
    return NAME_RE.sub("胡田", text)


def fix_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["text"] = fix_text(data.get("text", ""))
    for segment in data.get("segments", []):
        segment["text"] = fix_text(segment.get("text", ""))
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    stem = Path(sys.argv[1])
    for ext in ("srt", "vtt", "txt", "tsv"):
        path = stem.with_suffix(f".{ext}")
        if path.is_file():
            path.write_text(fix_text(path.read_text(encoding="utf-8")), encoding="utf-8")
    if stem.with_suffix(".json").is_file():
        fix_json(stem.with_suffix(".json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

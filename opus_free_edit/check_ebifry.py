#!/usr/bin/env python3
"""Stop the upload when the edit has too few mascot (えびフライ) cameos.

Every edited video features えびフライ. The final captions prefix each cameo line with
「えびフライ：」, so counting those cues proves the cameos made it into the final cut.
The only way out is ``work/NO_EBIFRY.txt`` holding the presenter's own instruction to skip them.

Usage: check_ebifry.py <job_dir> [--min N]   (exit 0 = ok, 1 = too few, 2 = no captions)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PREFIX = "えびフライ："
MIN_CAMEOS = 3


def count_cameos(srt_text: str) -> int:
    """Number of caption cues whose text starts with the cameo prefix."""
    cues = re.split(r"\n\s*\n", srt_text.replace("\r\n", "\n"))
    count = 0
    for cue in cues:
        lines = [l.strip() for l in cue.strip().split("\n")]
        text = [l for l in lines if l and not l.isdigit() and "-->" not in l]
        if text and text[0].startswith(PREFIX):
            count += 1
    return count


def check(job: Path, minimum: int = MIN_CAMEOS) -> tuple[int, str]:
    waiver = job / "work" / "NO_EBIFRY.txt"
    if waiver.is_file() and waiver.read_text(encoding="utf-8").strip():
        return 0, f"cameos waived by the presenter: {waiver.read_text(encoding='utf-8').strip()[:200]}"
    srt = job / "out" / "captions.srt"
    if not srt.is_file():
        return 2, f"{srt} is missing – cannot confirm the えびフライ cameos"
    n = count_cameos(srt.read_text(encoding="utf-8"))
    if n < minimum:
        return 1, (f"only {n} えびフライ cameo(s) in out/captions.srt (need {minimum}). Add cameos, or write the "
                   "presenter's own instruction to skip them to work/NO_EBIFRY.txt")
    return 0, f"{n} えびフライ cameos"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("--min", type=int, default=MIN_CAMEOS)
    args = ap.parse_args()
    code, message = check(args.job, args.min)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())

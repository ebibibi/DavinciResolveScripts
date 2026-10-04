#!/usr/bin/env python3
"""Find silent stretches left in a rendered video, measured from the audio itself.

Word timestamps cannot be trusted for this: on 2026-10-04 Whisper stretched the single word 「構」
over 390.2-396.6 s while the audio was at -65 dB, so a 6.9 s silence survived the word-gap rule.

The threshold is relative to the speech level of the file (median of the loud windows minus
--below dB), so it works before and after loudness normalisation.

Usage:
  check_silence.py out/final.mp4 [--min 1.0] [--below 22] [--ignore 176.0-710.5 ...]
  (--ignore: ranges in the output timeline that are not the presenter talking, e.g. inserted clips,
   stingers, the end card)
Exit 0 = no silent stretch longer than --min, 1 = found (listed), 2 = cannot read.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import numpy as np

SR = 16000
WINDOW = 0.05
MERGE_GAP = 0.2


def load_audio(path: str) -> np.ndarray:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout:
        raise OSError(f"cannot decode audio of {path}: {result.stderr.decode()[-300:]}")
    return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float64) / 32768.0


def window_db(audio: np.ndarray) -> np.ndarray:
    size = int(SR * WINDOW)
    frames = audio[: len(audio) // size * size].reshape(-1, size)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)


def silent_spans(db: np.ndarray, threshold: float, min_len: float) -> list[tuple[float, float]]:
    spans, start = [], None
    for i, quiet in enumerate(db < threshold):
        if quiet and start is None:
            start = i
        elif not quiet and start is not None:
            if (i - start) * WINDOW >= min_len:
                spans.append((start * WINDOW, i * WINDOW))
            start = None
    if start is not None and (len(db) - start) * WINDOW >= min_len:
        spans.append((start * WINDOW, len(db) * WINDOW))
    return spans


def merge_close(spans: list[tuple[float, float]], bridge: float = MERGE_GAP) -> list[tuple[float, float]]:
    """A click or breath of a few windows must not split one silence into two shorter ones."""
    merged: list[tuple[float, float]] = []
    for a, b in spans:
        if merged and a - merged[-1][1] < bridge:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def parse_range(text: str) -> tuple[float, float]:
    a, b = text.split("-")
    return float(a), float(b)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video")
    parser.add_argument("--min", type=float, default=1.0, help="report silences at least this long (s)")
    parser.add_argument("--below", type=float, default=22.0, help="dB below the speech level that counts as silent")
    parser.add_argument("--ignore", type=parse_range, nargs="*", default=[], help="output ranges to skip, a-b")
    args = parser.parse_args()
    try:
        db = window_db(load_audio(args.video))
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 2
    loud = db[db > np.percentile(db, 40)]
    speech = float(np.median(loud)) if loud.size else float(np.max(db))
    threshold = speech - args.below
    candidates = merge_close(silent_spans(db, threshold, 0.3))
    spans = [(a, b) for a, b in candidates
             if b - a >= args.min and not any(a < i1 and b > i0 for i0, i1 in args.ignore)]
    print(f"speech level {speech:.1f} dB, silent below {threshold:.1f} dB")
    if not spans:
        print(f"ok: no silence of {args.min:.1f} s or more outside the ignored ranges")
        return 0
    print(f"SILENCE LEFT IN THE EDIT ({len(spans)}):")
    for a, b in spans:
        print(f"- {int(a // 60)}:{a % 60:05.2f} - {int(b // 60)}:{b % 60:05.2f}  ({b - a:.1f} s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())

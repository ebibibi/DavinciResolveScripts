"""Refuse a video whose audio is on one channel only.

A recording can carry the microphone on the left channel only. If the edit keeps that layout,
the final video has the presenter in one ear and sounds silent on some players.
Usage: check_stereo.py VIDEO [--max-diff DB]   exit 0 = balanced, 1 = one side is silent
"""
import argparse
import re
import subprocess
import sys


def mean_volume(path: str, channel: str) -> float:
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", path, "-map", "0:a:0",
                        "-af", f"pan=mono|c0={channel},volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", r.stderr)
    if not m:
        sys.exit(f"check_stereo: could not measure {channel} of {path}")
    return float("-inf") if m.group(1) == "-inf" else float(m.group(1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--max-diff", type=float, default=6.0)
    a = ap.parse_args()
    left, right = mean_volume(a.video, "FL"), mean_volume(a.video, "FR")
    diff = abs(left - right)
    print(f"left {left:.1f} dB / right {right:.1f} dB (difference {diff:.1f} dB)")
    if diff > a.max_diff:
        print("one channel is (almost) silent: put the presenter on both channels", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

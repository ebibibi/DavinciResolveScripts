"""The eyecatch soundtrack must land on the same beats as the picture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

EYECATCH = Path(__file__).resolve().parents[1] / "tools" / "eyecatch"
sys.path.insert(0, str(EYECATCH))

from make_audio import RATE, cue_from_timeline, render  # noqa: E402

TIMELINE = json.loads((EYECATCH / "timeline.json").read_text(encoding="utf-8"))


def _window_rms(signal: np.ndarray, start_s: float, length_s: float) -> float:
    start = int(start_s * RATE)
    return float(np.sqrt(np.mean(signal[start : start + int(length_s * RATE)] ** 2)))


@pytest.mark.parametrize("variant", sorted(TIMELINE["variants"]))
def test_soundtrack_matches_the_timeline(variant: str) -> None:
    cue = cue_from_timeline(TIMELINE, variant)
    mix = render(cue)
    hit = cue.seconds(cue.hit_beat)

    assert len(mix) == int(RATE * cue.seconds(cue.beats))
    assert np.max(np.abs(mix)) <= 0.9
    # Dead silence right before the hit, and the loudest moment right after it.
    assert _window_rms(mix, hit - cue.silence_before_hit + 0.005, 0.09) == 0.0
    windows = [_window_rms(mix, i * 0.1, 0.1) for i in range(int(len(mix) / RATE / 0.1))]
    assert _window_rms(mix, hit, 0.1) == max(windows)


def test_video_frame_count_is_a_whole_number_of_frames() -> None:
    seconds = TIMELINE["beats"] * 60 / TIMELINE["bpm"]
    assert (seconds * TIMELINE["fps"]).is_integer()

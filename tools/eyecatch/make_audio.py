"""Synthesize the sound for one eyecatch from the same beat timeline as the picture.

Nothing here is a sample. Each variant has its own sound design (`sounds/`),
built from the oscillators and noise in `synth.py`, but all of them place
events by beat number, so a sound lands on the frame the animation uses for
the same beat, and all of them go silent for a moment right before the logo hits.
"""

from __future__ import annotations

import wave
from pathlib import Path
from types import MappingProxyType

import numpy as np

from cue import Cue
from sounds import SOUNDS
from synth import RATE

__all__ = ["RATE", "Cue", "cue_from_timeline", "render", "write_wav"]


def render(cue: Cue) -> np.ndarray:
    """Stereo (samples x 2) soundtrack, peaking at about -1 dBFS."""
    out = SOUNDS[cue.sound](cue).bus

    # A true silence right before the hit makes the landing hit harder.
    gap_from = int((cue.hit_s - cue.silence_before_hit) * RATE)
    out[gap_from : int(cue.hit_s * RATE)] = 0.0

    fade = int(RATE * 0.15)
    out[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    return out / np.max(np.abs(out)) * 0.89


def write_wav(path: Path, stereo: np.ndarray) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm.tobytes())


def cue_from_timeline(timeline: dict, variant: str) -> Cue:
    spec = timeline["variants"][variant]
    return Cue(
        bpm=timeline["bpm"],
        beats=spec.get("beats", timeline["beats"]),
        hit_beat=spec.get("hitBeat", timeline["hitBeat"]),
        silence_before_hit=timeline["silenceBeforeHit"],
        sound=spec["sound"],
        ticks=tuple(spec.get("ticks", ())),
        riser=tuple(spec.get("riser", (0.0, 1.8))),
        spec=MappingProxyType(spec),
    )

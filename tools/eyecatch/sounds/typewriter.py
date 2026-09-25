from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    Mix,
    decay,
    highpass,
    kick,
    noise,
    note,
    osc,
)


def _key(seed: int) -> np.ndarray:
    # A key is a sharp click on the way down and a softer thunk as it bottoms out.
    click = highpass(noise(0.012, seed), 0.6) * decay(0.012, 400, 0.0003)
    thunk = osc(180 + seed % 5 * 20, 0.05) * decay(0.05, 80)
    out = np.zeros(int(RATE * 0.05))
    out[: len(click)] += click
    return out + thunk * 0.6


def design(cue: Cue) -> Mix:
    """typewriter: one key per typed character, a carriage bell, then Enter."""
    mix = Mix(cue.total_s)
    typing = cue.spec["typing"]
    rng = np.random.default_rng(8)
    for i, char in enumerate(typing["text"]):
        at = cue.seconds(typing["start"] + i * typing["every"])
        if char == " ":
            mix.add(osc(90, 0.08) * decay(0.08, 40), at, 0.5)  # space bar: a deep thud
        else:
            mix.add(_key(i + 1), at + rng.uniform(-0.004, 0.004), 0.45, rng.uniform(-0.3, 0.3))
    ding = sum(osc(note(96) * r, 0.9) / (k + 1) for k, r in enumerate((1, 2.4, 3.9)))
    mix.add(ding * decay(0.9, 5), cue.seconds(cue.riser[0]) - 0.1, 0.25, 0.5)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    mix.add(_key(99) * 2, hit, 0.8)  # the Enter key, hit hard
    mix.add(kick(0.4, 140, 45), hit, 1.0)
    for midi in (57, 64, 69, 73, 76):  # electric piano: sine with a bell-like second partial
        tone = osc(note(midi), tail) + 0.35 * osc(note(midi) * 2, tail) * decay(tail, 8)
        mix.add(tone * decay(tail, 2.2, 0.004), hit, 0.14)
    return mix

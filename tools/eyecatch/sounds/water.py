from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    Mix,
    decay,
    lowpass,
    noise,
    osc,
    supersaw,
    times,
)


def plop(pitch_hz: float, length_s: float = 0.12) -> np.ndarray:
    # A bubble closing: a sine whose pitch rises fast, which is why drops go "bloop".
    t = times(length_s)
    return osc(pitch_hz * (1 + 3 * (1 - np.exp(-t * 60))), length_s) * decay(length_s, 30)


def design(cue: Cue) -> Mix:
    """ripple: water drops, rings of echo, a big splash that floods the frame."""
    mix = Mix(cue.total_s)
    rng = np.random.default_rng(12)
    for i, beat in enumerate(cue.ticks):
        at = cue.seconds(beat)
        pan = (-0.4, 0.4, 0.0)[i % 3]
        mix.add(plop(300 + 80 * i), at, 0.7, pan)
        mix.add(lowpass(noise(0.2, 30 + i), 0.15) * decay(0.2, 18), at, 0.25, pan)
        for echo in range(1, 4):  # the rings, heard as softer and darker repeats
            mix.add(lowpass(plop(300 + 80 * i), 0.3), at + echo * 0.11, 0.35 / (echo + 1), -pan)
    rise_from, rise_to = (cue.seconds(b) for b in cue.riser)
    for k in range(10):  # bubbles rising before the big drop
        mix.add(plop(rng.uniform(500, 1400), 0.06), rng.uniform(rise_from, rise_to), 0.2, rng.uniform(-0.8, 0.8))

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    mix.add(plop(160, 0.3), hit, 1.0)
    mix.add(osc(45 + 30 * np.exp(-times(tail) * 5), tail) * decay(tail, 2.5), hit, 0.8)
    mix.add(lowpass(noise(tail, 77), 0.25) * decay(tail, 3.5), hit, 0.35)
    pad = supersaw((62, 66, 69, 73), tail, "triangle")
    mix.add(pad * decay(tail, 1.4, 0.05), hit, 0.5)
    for k in range(14):
        mix.add(plop(rng.uniform(700, 2000), 0.05), hit + rng.uniform(0.05, 0.8), 0.12, rng.uniform(-0.9, 0.9))
    return mix

from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    Mix,
    decay,
    highpass,
    kick,
    lowpass,
    noise,
    note,
    osc,
    times,
)


def swish(length_s: float, seed: int) -> np.ndarray:
    # Air torn by a blade: noise whose brightness sweeps up and back down.
    ramp = np.sin(np.linspace(0, np.pi, int(RATE * length_s)))
    return highpass(noise(length_s, seed), 0.5 + 0.45 * ramp) * ramp**2


def shing(length_s: float, base_hz: float) -> np.ndarray:
    # Ringing steel: a few inharmonic partials that die at different speeds.
    parts = ((1.0, 3.0), (1.37, 4.5), (2.03, 6.0), (2.71, 8.0))
    return sum(osc(base_hz * r, length_s) * decay(length_s, rate) for r, rate in parts) / len(parts)


def design(cue: Cue) -> Mix:
    """slice: a swish before each cut, ringing steel on it, a taiko hit as it falls apart."""
    mix = Mix(cue.total_s)
    for i, beat in enumerate(cue.ticks):
        at = cue.seconds(beat)
        pan = (-0.7, 0.7, 0.0)[i]
        mix.add(swish(0.14, 50 + i), at - 0.12, 0.6, -pan)
        mix.add(shing(0.6, 2300 + 300 * i), at, 0.4, pan)
        mix.add(kick(0.15, 200, 90), at, 0.25)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    taiko = osc(60 + 50 * np.exp(-times(tail) * 20), tail) * decay(tail, 4)
    skin = lowpass(noise(0.1, 90), 0.2) * decay(0.1, 40)
    mix.add(taiko, hit, 1.0)
    mix.add(skin, hit, 0.6)
    mix.add(shing(tail, 1800), hit, 0.5)
    gong = sum(osc(note(38) * r, tail) for r in (1, 2.02, 2.93)) / 3
    mix.add(gong * decay(tail, 1.8, 0.01), hit, 0.35)
    for step in (0.5, 1.0):
        mix.add(taiko[: int(RATE * 0.3)] * 0.4, hit + cue.seconds(step), 0.5, (-0.3, 0.3)[step == 1.0])
    return mix

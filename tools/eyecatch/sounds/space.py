from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    TAU,
    Mix,
    crash,
    decay,
    kick,
    lowpass,
    note,
    osc,
    times,
)


def ping(hz: float, length_s: float = 0.8) -> np.ndarray:
    return osc(hz, length_s) * decay(length_s, 5, 0.004)


def fm(carrier_hz: float, ratio: float, index: np.ndarray | float, length_s: float) -> np.ndarray:
    # Frequency modulation: the classic sci-fi / DX bell tone.
    t = times(length_s)
    mod = np.sin(TAU * carrier_hz * ratio * t) * index
    return np.sin(TAU * carrier_hz * t + mod)


def design(cue: Cue) -> Mix:
    """orbit: sonar pings, a warbling FM pad that climbs as the planets spiral in."""
    mix = Mix(cue.total_s)
    hit = cue.hit_s
    for i, beat in enumerate(cue.ticks):
        at = cue.seconds(beat)
        for echo in range(4):  # the ping bouncing around empty space
            mix.add(ping(note(81 + (0, 4, 7)[i])), at + echo * 0.16, 0.3 * 0.5**echo, (-0.6, 0.6)[echo % 2])
    ramp = np.linspace(0, 1, int(RATE * hit))
    pad = fm(note(45), 2.0, 1 + 4 * ramp**2, hit) * (0.3 + 0.7 * ramp)
    mix.add(lowpass(pad, 0.05 + 0.2 * ramp), 0, 0.35)
    rise_from, rise_to = (cue.seconds(b) for b in cue.riser)
    length = rise_to - rise_from
    climb = np.linspace(0, 1, int(RATE * length))
    mix.add(osc(200 * 2 ** (4 * climb**2), length) * climb**2, rise_from, 0.25)

    tail = cue.total_s - hit
    mix.add(osc(30 + 60 * np.exp(-times(tail) * 4), tail) * decay(tail, 2), hit, 1.0)
    mix.add(kick(0.4, 160, 40), hit, 0.8)
    for midi in (57, 64, 71, 76):
        mix.add(fm(note(midi), 3.5, 2.5 * decay(tail, 3), tail) * decay(tail, 1.6, 0.004), hit, 0.14)
    mix.add(crash(tail, 5), hit, 0.2)
    return mix

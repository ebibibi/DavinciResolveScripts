from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    Mix,
    crash,
    decay,
    kick,
    lowpass,
    noise,
    osc,
    supersaw,
    times,
)


def design(cue: Cue) -> Mix:
    """tunnel: a droning engine that climbs with the speed, rings whooshing past."""
    mix = Mix(cue.total_s)
    hit = cue.hit_s
    t = times(hit)
    beat = t * cue.bpm / 60
    boost = np.where(beat <= 0, 0, 2 ** (10 * np.clip(beat / cue.hit_beat, 0, 1) - 10))  # expoIn
    speed = cue.spec["speed"][0] + boost * cue.spec["speed"][1]
    drone = osc(40 + 5 * speed, hit, "saw") + osc(40.5 + 5 * speed, hit, "saw")
    mix.add(lowpass(np.tanh(drone * 1.5), 0.02 + 0.004 * speed) * (0.4 + 0.6 * boost), 0, 0.8)

    # Every whole unit of travel is one ring rushing past the camera.
    travel = beat * speed
    passes = np.nonzero(np.diff(np.floor(travel)) > 0)[0] / RATE
    last = -1.0
    for k, at in enumerate(passes):
        if at - last < 0.035:
            continue
        last = at
        whoosh = lowpass(noise(0.08, 100 + k), 0.3) * decay(0.08, 40)
        mix.add(whoosh, at, 0.35, -0.6 if k % 2 else 0.6)
    rise_from, rise_to = (cue.seconds(b) for b in cue.riser)
    reverse_cymbal = crash(rise_to - rise_from, 13)[::-1]
    mix.add(reverse_cymbal, rise_from, 0.35)

    tail = cue.total_s - hit
    mix.add(kick(0.5, 200, 40), hit, 1.0)
    mix.add(osc(80 * np.exp(-times(tail) * 1.5) + 28, tail) * decay(tail, 1.5), hit, 0.9)
    stab = np.tanh(supersaw((45, 52, 57, 64), tail) * 4)
    mix.add(lowpass(stab, 0.08) * decay(tail, 2.5, 0.004), hit, 0.45)
    mix.add(crash(tail, 9), hit, 0.35)
    return mix

from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    Mix,
    crash,
    decay,
    note,
    osc,
    riser,
    supersaw,
    times,
)


def design(cue: Cue) -> Mix:
    """assemble: glittering chimes gather as the particles do, then a bell and a boom."""
    mix = Mix(cue.total_s)
    rng = np.random.default_rng(3)
    start, end = (cue.seconds(b) for b in cue.riser)
    pentatonic = (81, 83, 85, 88, 90, 93, 95, 97, 100)  # A major pentatonic, high
    at = start
    while at < end:
        progress = (at - start) / (end - start)
        pitch = pentatonic[rng.integers(len(pentatonic))]
        chime = osc(note(pitch), 0.25) + 0.3 * osc(note(pitch) * 2.76, 0.25)
        mix.add(chime * decay(0.25, 18), at, 0.10 + 0.12 * progress, rng.uniform(-0.9, 0.9))
        at += 0.12 - 0.09 * progress  # more and more chimes as the logo forms
    swell_len = end - start
    swell = supersaw((57, 64, 69, 73), swell_len, "triangle") * np.linspace(0, 1, int(RATE * swell_len)) ** 3
    mix.add(swell, start, 0.5)
    mix.add(riser(swell_len, 5), start, 0.15)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    boom = osc(35 + 45 * np.exp(-times(tail) * 6), tail) * decay(tail, 2.5)
    mix.add(boom, hit, 1.0)
    for midi in (57, 64, 68, 71, 76):  # A major 9 as a bell: inharmonic partials
        bell = sum(osc(note(midi) * r, tail) / (k + 1) for k, r in enumerate((1, 2.0, 2.76, 5.4)))
        mix.add(bell * decay(tail, 3), hit, 0.12)
    mix.add(crash(tail, 9), hit, 0.2)
    return mix

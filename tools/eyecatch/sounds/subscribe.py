from __future__ import annotations

import numpy as np

from cue import Cue
from synth import Mix, decay, highpass, lowpass, noise, note, osc, supersaw, times


def design(cue: Cue) -> Mix:
    """subscribe: a soft marimba note as each pose rises, then a click, a bell and a warm chord."""
    mix = Mix(cue.total_s)
    every = cue.spec["every"]
    for i, midi in enumerate((72, 76, 79, 84)[:len(cue.spec["poses"])]):
        at = cue.seconds(0.4 + i * every)
        pan = -0.45 + 0.3 * i
        t = times(0.5)
        marimba = (osc(note(midi), 0.5) + 0.3 * osc(note(midi) * 4, 0.5)) * np.exp(-t * 9)
        mix.add(marimba, at, 0.22, pan)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    mix.add(highpass(noise(0.015, 5), 0.3) * decay(0.015, 250), hit, 0.45)
    for k, (midi, delay) in enumerate(((88, 0.0), (95, 0.16))):
        t = times(1.4)
        bell = osc(note(midi), 1.4) + 0.4 * osc(note(midi) * 2.76, 1.4)
        mix.add(bell * np.exp(-t * 3.2), hit + delay, 0.16, (-0.25, 0.25)[k])
    pad = lowpass(supersaw((60, 64, 67, 71), tail, "triangle"), 0.06)
    mix.add(pad * decay(tail, 1.0, 0.08), hit, 0.6)
    return mix

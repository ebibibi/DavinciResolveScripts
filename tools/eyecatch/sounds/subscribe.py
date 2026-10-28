from __future__ import annotations

import numpy as np

from cue import Cue
from synth import RATE, Mix, decay, highpass, kick, lowpass, noise, note, osc, supersaw, times


def design(cue: Cue) -> Mix:
    """subscribe: a cartoon pop on every pose change (climbing the scale), then a click and a bell."""
    mix = Mix(cue.total_s)
    every = cue.spec["every"]
    scale = (67, 69, 71, 72, 74, 76, 79)
    for i, midi in enumerate(scale):
        at = cue.seconds(i * every)
        if at >= cue.hit_s - cue.silence_before_hit - 0.05:
            break
        pan = (-0.6, 0.6)[i % 2] * (i > 0)
        pop = osc(note(midi) * (1 + 0.6 * np.exp(-times(0.14) * 40)), 0.14) * decay(0.14, 22)
        mix.add(pop, at, 0.35, pan)
        mix.add(highpass(noise(0.025, 30 + i), 0.6) * decay(0.025, 160), at, 0.25, pan)
    # light bass bounce under the poses
    for b in range(int(cue.hit_beat)):
        mix.add(kick(0.18, 110, 55), cue.seconds(b), 0.35)
    rise_from, rise_to = (cue.seconds(x) for x in cue.riser)
    length = rise_to - rise_from
    ramp = np.linspace(0, 1, int(RATE * length))
    mix.add(highpass(noise(length, 9), 0.5 + 0.45 * ramp) * ramp ** 2, rise_from, 0.3)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    click = highpass(noise(0.02, 5), 0.3) * decay(0.02, 200)
    mix.add(click, hit, 0.8)
    mix.add(kick(0.3, 140, 55), hit, 0.7)
    # notification bell: two bright partials, then the answer a fifth up
    for k, (midi, delay) in enumerate(((88, 0.0), (95, 0.18))):
        t = times(1.2)
        bell = (osc(note(midi), 1.2) + 0.5 * osc(note(midi) * 2.76, 1.2) + 0.25 * osc(note(midi) * 5.4, 1.2))
        mix.add(bell * np.exp(-t * (3.5 + k)), hit + delay, 0.22, (-0.3, 0.3)[k])
    brass = lowpass(supersaw((60, 64, 67, 72), tail, "square"), 0.05 + 0.2 * decay(tail, 5))
    mix.add(brass * decay(tail, 1.2, 0.02), hit, 1.1)
    return mix

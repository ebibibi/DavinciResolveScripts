from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    TAU,
    Mix,
    decay,
    highpass,
    kick,
    lowpass,
    noise,
    note,
    osc,
    supersaw,
    times,
)


def design(cue: Cue) -> Mix:
    """bounce: every letter lands with a springy boing, rising up the scale."""
    mix = Mix(cue.total_s)
    scale = (60, 62, 64, 65, 67, 69, 71, 72)
    count = len(cue.spec["word"])
    # bounceOut touches the ground at 1/2.75, 2/2.75 and 2.5/2.75 of its length.
    for i in range(count):
        drop_at = i * cue.spec["drop"]["every"]
        pan = -0.8 + 1.6 * i / max(1, count - 1)
        for k, (fraction, gain) in enumerate(((1 / 2.75, 1.0), (2 / 2.75, 0.35), (2.5 / 2.75, 0.15))):
            at = cue.seconds(drop_at + cue.spec["drop"]["length"] * fraction)
            t = times(0.3)
            wobble = 1 + 0.35 * np.exp(-t * 10) * np.sin(TAU * 14 * t)
            spring = osc(note(scale[i] + 12 * (k > 0)) * wobble, 0.3) * decay(0.3, 9)
            block = highpass(noise(0.03, 40 + i), 0.5) * decay(0.03, 150)
            mix.add(spring, at, 0.35 * gain, pan)
            mix.add(block, at, 0.3 * gain, pan)
    exit_at, exit_len = cue.seconds(1.75), cue.seconds(0.25)
    ramp = np.linspace(0, 1, int(RATE * exit_len))
    mix.add(highpass(noise(exit_len, 7), 0.6 + 0.35 * ramp) * ramp, exit_at - 0.02, 0.4)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    pop = osc(900 * np.exp(-times(0.12) * 25) + 120, 0.12) * decay(0.12, 30)
    mix.add(pop, hit, 1.0)
    mix.add(kick(0.3, 130, 60), hit, 0.7)
    for k, pan in enumerate((-0.4, 0.4, 0.0)):  # a clap is a few noise bursts smeared together
        mix.add(highpass(noise(0.12, 60 + k), 0.8) * decay(0.12, 25), hit + 0.008 * k, 0.35, pan)
    brass = lowpass(supersaw((60, 64, 67, 72), tail, "square"), 0.04 + 0.2 * decay(tail, 6))
    mix.add(brass * decay(tail, 1.5, 0.02), hit, 1.3)
    for i, step in enumerate((0.5, 1.0, 1.5)):
        mix.add(osc(note(84 + (4, 7, 12)[i]), 0.2, "triangle") * decay(0.2, 12), hit + cue.seconds(step), 0.18)
    return mix

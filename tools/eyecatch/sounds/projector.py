from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    Mix,
    crash,
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
    """countdown: projector rattle, a beep per number, then an orchestral hit."""
    mix = Mix(cue.total_s)
    hit = cue.hit_s
    # The claw pulling film through the gate: 24 clicks a second, slightly uneven.
    rng = np.random.default_rng(4)
    at = 0.0
    while at < hit - cue.silence_before_hit:
        click = highpass(noise(0.01, int(at * 1000)), 0.7) * decay(0.01, 500, 0.0002)
        mix.add(click, at, 0.18 + rng.uniform(0, 0.06), -0.2)
        at += 1 / 24
    hum = lowpass(osc(60, hit, "saw"), 0.05)
    mix.add(hum, 0, 0.12)
    for i, beat in enumerate(cue.ticks):
        high = i == len(cue.ticks) - 1  # the last number beeps higher
        mix.add(osc(1000 * (2 if high else 1), 0.09) * decay(0.09, 5, 0.002), cue.seconds(beat), 0.35)

    tail = cue.total_s - hit
    mix.add(kick(0.5, 150, 40), hit, 1.0)
    brass = lowpass(supersaw((50, 57, 62, 66, 69), tail, "saw"), 0.06 + 0.25 * decay(tail, 5))
    strings = supersaw((74, 78, 81), tail, "triangle")
    mix.add(brass * decay(tail, 1.6, 0.01), hit, 1.0)
    mix.add(strings * decay(tail, 1.4, 0.02), hit, 0.5)
    mix.add(crash(tail, 17), hit, 0.35)
    timpani = osc(note(38) * (1 + 0.1 * np.exp(-times(tail) * 30)), tail) * decay(tail, 3)
    mix.add(timpani, hit, 0.7)
    return mix

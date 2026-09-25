from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    TAU,
    Mix,
    decay,
    hat,
    kick,
    noise,
    note,
    osc,
    supersaw,
    times,
)


def design(cue: Cue) -> Mix:
    """morph: 8-bit blips, one per shape, each played on the wave that looks like it."""
    mix = Mix(cue.total_s)
    shapes = ("sine", "square", "triangle", "saw")  # circle, square, triangle, star
    melody = (72, 76, 79, 84)
    for i, beat in enumerate(cue.ticks):
        length = cue.seconds(0.5)
        t = times(length)
        # Glide to the next note while the picture morphs to the next shape.
        glide = np.clip((t - cue.seconds(0.2)) / cue.seconds(0.3), 0, 1)
        target = melody[min(i + 1, len(melody) - 1)]
        freq = note(melody[i]) * (note(target) / note(melody[i])) ** (glide * (i < len(melody) - 1))
        vibrato = 1 + 0.01 * np.sin(TAU * 7 * t)
        mix.add(osc(freq * vibrato, length, shapes[i]) * decay(length, 3, 0.004), cue.seconds(beat), 0.22)
        mix.add(osc(note(melody[i] - 24), 0.12, "triangle") * decay(0.12, 20), cue.seconds(beat), 0.4)
        mix.add(hat(i + 1, 0.03), cue.seconds(beat + 0.25), 0.15)
    rise_from, rise_to = (cue.seconds(b) for b in cue.riser)
    arp = np.concatenate([osc(note(m), 0.025, "square") for m in (72, 76, 79, 84) * 20])
    mix.add(arp[: int(RATE * (rise_to - rise_from))], rise_from, 0.15)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    power_up = np.concatenate([osc(note(m), 0.035, "square") for m in (84, 88, 91, 96, 100, 103, 108)])
    mix.add(power_up, hit, 0.35)
    crunch = np.round(noise(tail, 11) * 4) / 4  # 3-bit noise: the NES "crash"
    mix.add(crunch * decay(tail, 5), hit, 0.35)
    mix.add(kick(0.3, 180, 50), hit, 1.0)
    mix.add(supersaw((48, 60, 64, 67), tail, "square") * decay(tail, 1.5, 0.004), hit, 0.7)
    return mix

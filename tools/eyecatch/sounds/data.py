from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    RATE,
    Mix,
    decay,
    kick,
    lowpass,
    note,
    osc,
    supersaw,
)


def crush(signal: np.ndarray, hold: int, levels: int) -> np.ndarray:
    # Lower the sample rate (hold each sample) and the bit depth: instant "digital".
    held = np.repeat(signal[::hold], hold)[: len(signal)]
    return np.round(held * levels) / levels


def design(cue: Cue) -> Mix:
    """pixelate: data chatter that gets faster with each resolution step, then a done chime."""
    mix = Mix(cue.total_s)
    rng = np.random.default_rng(31)
    hit = cue.hit_s
    for i, beat in enumerate(cue.ticks):
        at = cue.seconds(beat)
        chirp_len = 0.08
        chirp = osc(np.linspace(400, 3000, int(RATE * chirp_len)), chirp_len, "square")
        mix.add(crush(chirp * decay(chirp_len, 20), 4, 4), at, 0.3)
        # Each finer step streams more data: more, shorter, higher bleeps.
        end = cue.seconds(cue.ticks[i + 1]) if i + 1 < len(cue.ticks) else hit - cue.silence_before_hit
        step = 0.06 / (i + 1)
        t = at + 0.05
        while t < end - step:
            hz = rng.choice((600, 800, 1200, 1600, 2400)) * (1 + i * 0.25)
            bleep = osc(hz, step * 0.8, "square") * decay(step * 0.8, 10, 0.001)
            mix.add(crush(bleep, 3, 6), t, 0.12, rng.uniform(-0.7, 0.7))
            t += step

    tail = cue.total_s - hit
    mix.add(kick(0.3, 170, 50), hit, 1.0)
    for k, midi in enumerate((84, 91)):  # the "done" two-tone
        mix.add(osc(note(midi), 0.5) * decay(0.5, 5, 0.003), hit + k * 0.09, 0.4)
    chord = crush(supersaw((48, 55, 60, 64), tail, "saw"), 6, 8)
    mix.add(lowpass(chord, 0.15) * decay(tail, 2.0, 0.004), hit, 0.6)
    return mix

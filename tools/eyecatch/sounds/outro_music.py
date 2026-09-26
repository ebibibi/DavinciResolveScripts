from __future__ import annotations

import numpy as np

from cue import Cue
from synth import (
    Mix,
    crash,
    decay,
    hat,
    highpass,
    kick,
    lowpass,
    noise,
    note,
    osc,
    riser,
    supersaw,
    times,
)

# One chord per bar of four beats, cycling A, F#m, D, E; the last bar lands on A.
PROGRESSION = ((45, (57, 61, 64)), (42, (57, 61, 66)), (38, (57, 62, 66)), (40, (56, 59, 64)))
HOME = PROGRESSION[0]


def pluck(midi: float, length_s: float = 0.2, shape: str = "triangle") -> np.ndarray:
    return lowpass(osc(note(midi), length_s, shape), 0.35) * decay(length_s, 14, 0.002)


def click() -> np.ndarray:
    # A mouse button: a sharp down-click and a softer release a moment later.
    down = highpass(noise(0.006, 1), 0.5) * decay(0.006, 700, 0.0002)
    out = np.zeros(int(len(down) * 12))
    out[: len(down)] += down
    out[len(down) * 9 : len(down) * 10] += down * 0.5
    return out


def bell(midi: float, length_s: float = 1.0) -> np.ndarray:
    parts = ((1, 1.0), (2.4, 0.5), (3.9, 0.3), (5.4, 0.2))
    return sum(osc(note(midi) * r, length_s) * g for r, g in parts) * decay(length_s, 4, 0.002)


def thump(length_s: float = 0.3) -> np.ndarray:
    return osc(90 + 120 * np.exp(-times(length_s) * 25), length_s) * decay(length_s, 10)


def whoosh(length_s: float, seed: int) -> np.ndarray:
    ramp = np.sin(np.linspace(0, np.pi, int(48_000 * length_s)))
    return highpass(noise(length_s, seed), 0.6 + 0.3 * ramp) * ramp


def _showcase(mix: Mix, cue: Cue) -> None:
    """Sounds for the full-screen half, placed from the same promo timing as the picture."""
    s = cue.seconds
    promo = cue.spec["promo"]
    mvp = promo["mvp"]
    # The MVP counter ticks up the scale once per year, then lands with a fanfare.
    years = mvp["years"]
    for k in range(1, years):
        progress = k / (years - 1)
        at = mvp["countFrom"] + (mvp["countTo"] - mvp["countFrom"]) * progress
        mix.add(osc(note(69 + k), 0.06, "square") * decay(0.06, 40), s(at) - 0.03, 0.08)
    land = s(mvp["countTo"])
    mix.add(kick(0.5, 170, 42), land, 0.9)
    mix.add(crash(1.2, 31), land, 0.3)
    fanfare = lowpass(supersaw((57, 61, 64, 69), 1.2, "saw"), 0.1) * decay(1.2, 2.5, 0.01)
    mix.add(fanfare, land, 0.6)

    for scene in ("range", "stats", "identity"):  # the yellow sweep between scenes
        mix.add(whoosh(0.3, len(scene)), s(promo[scene]["at"]) - 0.2, 0.3, 0.4)

    rng = promo["range"]
    for at in rng["wordsAt"]:
        mix.add(thump(), s(rng["at"] + at), 0.7)
    mix.add(bell(93, 0.8), s(rng["at"] + rng["taglineAt"]), 0.12, 0.3)

    stats = promo["stats"]
    for i, at in enumerate(stats["tilesAt"]):
        start = s(stats["at"] + at)
        mix.add(thump(0.25), start, 0.5, (-0.4, 0.4)[i % 2])
        if "value" in stats["tiles"][i]:  # a quick run of ticks while the number counts
            for k in range(8):
                mix.add(osc(note(84 + k), 0.03, "square") * decay(0.03, 60), start + 0.04 * k, 0.05)

    who = promo["identity"]
    mix.add(bell(81, 1.2), s(who["at"] + 0.4), 0.15, -0.3)
    mix.add(bell(88, 1.0), s(who["at"] + 1.8), 0.12, 0.3)


def design(cue: Cue) -> Mix:
    """outro: a small club track with a breakdown, and UI sounds on every click."""
    mix = Mix(cue.total_s)
    s = cue.seconds
    end = cue.spec["endAt"]
    gap_from = cue.hit_beat - cue.silence_before_hit * cue.bpm / 60
    calm_from, calm_to = cue.spec["breakdown"]

    def calm(b: float) -> bool:
        return calm_from <= b < calm_to

    # In the breakdown the kick only marks each bar, so the return feels like a lift.
    kicks = [
        float(b) for b in range(int(end))
        if not (gap_from <= b < cue.hit_beat) and (not calm(b) or b % 4 == 0)
    ]
    for b in kicks:
        mix.add(kick(0.3, 140, 48), s(b), 0.8)
    for b in np.arange(0.5, end, 1.0):
        mix.add(hat(int(b * 10), 0.05), s(b), 0.1 if calm(b) else 0.18, 0.3)
    for b in (b for b in range(5, int(end), 2) if not calm(b)):  # claps on 2 and 4 after the intro bar
        for k in range(3):
            mix.add(highpass(noise(0.1, 200 + b * 3 + k), 0.8) * decay(0.1, 28), s(b) + 0.007 * k, 0.22)

    music = Mix(cue.total_s)
    for bar in range(int(np.ceil(cue.beats / 4))):
        start = bar * 4
        if start >= end:
            continue
        final = start >= end - 2
        root, chord = HOME if final else PROGRESSION[bar % len(PROGRESSION)]
        for eighth in range(8 if not final else 1):
            b = start + eighth * 0.5
            if b >= end or gap_from <= b < cue.hit_beat:
                continue
            octave = 12 if eighth % 2 else 0
            if calm(b) and eighth % 2:
                continue
            music.add(lowpass(osc(note(root + octave), 0.22, "saw"), 0.08) * decay(0.22, 9, 0.003), s(b), 0.5)
        arp_gain = 0.16 if start < cue.hit_beat or calm(start) else 0.09
        # The breakdown lifts the arpeggio an octave so the section sounds new.
        tones = [m + (24 if calm(start) else 12) for m in chord] + [chord[0] + 24]
        for step in range(16):
            b = start + step * 0.25
            if b >= end or gap_from <= b < cue.hit_beat:
                continue
            music.add(pluck(tones[step % len(tones)]), s(b), arp_gain, (-0.4, 0.4)[step % 2])
        if start >= cue.hit_beat and not final:  # a soft pad under the call to action
            pad = lowpass(supersaw(chord, s(4), "triangle"), 0.12) * decay(s(4), 0.6, 0.3)
            music.add(pad, s(start), 0.45)
    music.duck([s(b) for b in kicks], 0.55)
    mix.bus += music.bus

    _showcase(mix, cue)
    rise_from, rise_to = (s(b) for b in cue.riser)
    mix.add(riser(rise_to - rise_from, 5), rise_from, 0.35)

    # The wipe itself.
    mix.add(kick(0.5, 180, 40), cue.hit_s, 1.0)
    mix.add(crash(1.5, 9), cue.hit_s, 0.3)

    # Part 2: each card whooshes in; each click gets its own reward sound.
    for i, card in enumerate(cue.spec["cta"]):
        whoosh_len = 0.18
        ramp = np.sin(np.linspace(0, np.pi, int(48_000 * whoosh_len)))
        mix.add(highpass(noise(whoosh_len, 300 + i), 0.6 + 0.3 * ramp) * ramp, s(card["appear"]), 0.3, -0.5)
        at = s(card["click"])
        mix.add(click(), at, 0.8, -0.3)
        if i == 0:  # like: a bubbly pop upward
            pop = osc(500 * 2 ** (times(0.12) * 12), 0.12) * decay(0.12, 25)
            mix.add(pop, at + 0.01, 0.45)
        elif i == 1:  # subscribe: the notification bell, twice
            mix.add(bell(88), at + 0.01, 0.3)
            mix.add(bell(88), at + 0.13, 0.2)
        else:  # join: a run of sparkles
            for k, m in enumerate((88, 92, 95, 100, 104)):
                mix.add(osc(note(m), 0.3) * decay(0.3, 12), at + 0.01 + k * 0.045, 0.16, -0.6 + 0.3 * k)

    # After the clicks the cards glow in turn every two beats; each glow gets a soft chime.
    first_glow = cue.spec["cta"][-1]["click"] + 1.5
    order = cue.spec["glowOrder"]
    for k, b in enumerate(np.arange(first_glow, end, 2.0)):
        # The recommended card's turn gets a brighter chime than the others.
        star = order[k % len(order)] == len(cue.spec["cta"]) - 1
        mix.add(bell(93 if star else 85, 0.6), s(b), 0.1 if star else 0.06, (-0.3, 0.3)[k % 2])

    # The ending: one big chord that rings out.
    tail = cue.total_s - s(end)
    mix.add(kick(0.6, 160, 40), s(end), 1.0)
    mix.add(supersaw((45, 57, 61, 64, 69), tail) * decay(tail, 1.3, 0.005), s(end), 0.9)
    mix.add(bell(81, tail), s(end), 0.15)
    mix.add(crash(tail, 21), s(end), 0.3)
    return mix

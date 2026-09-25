"""Synthesize the sound for one eyecatch from the same beat timeline as the picture.

Nothing here is a sample: every sound is built from sine / square / triangle /
saw waves and shaped noise. Each variant has its own sound design (see SOUNDS),
but all of them place events by beat number, so a sound lands on the frame the
animation uses for the same beat, and all of them go silent for a moment right
before the logo hits.
"""

from __future__ import annotations

import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RATE = 48_000
TAU = 2 * np.pi
DETUNE_CENTS = (-18, -11, -5, 0, 5, 11, 18)


@dataclass(frozen=True)
class Cue:
    bpm: float
    beats: float
    hit_beat: float
    silence_before_hit: float
    sound: str
    ticks: tuple[float, ...]
    riser: tuple[float, float]
    word: str = ""
    drop_every: float = 0.0
    drop_length: float = 0.0
    speed: tuple[float, float] = (0.0, 0.0)

    def seconds(self, beat: float) -> float:
        return beat * 60.0 / self.bpm

    @property
    def hit_s(self) -> float:
        return self.seconds(self.hit_beat)

    @property
    def total_s(self) -> float:
        return self.seconds(self.beats)


# ---------- building blocks ----------


def _t(length_s: float) -> np.ndarray:
    return np.arange(int(RATE * length_s)) / RATE


def _noise(length_s: float, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1.0, 1.0, int(RATE * length_s))


def _one_pole(signal: np.ndarray, coeff: float | np.ndarray, high: bool) -> np.ndarray:
    # One-pole filter. `coeff` may change per sample, which is how sweeps are made.
    c = np.broadcast_to(coeff, signal.shape)
    out = np.empty_like(signal)
    prev_in = prev_out = 0.0
    for i, x in enumerate(signal):
        if high:
            prev_out = c[i] * (prev_out + x - prev_in)
            prev_in = x
        else:
            prev_out += c[i] * (x - prev_out)
        out[i] = prev_out
    return out


def highpass(signal: np.ndarray, coeff: float | np.ndarray = 0.95) -> np.ndarray:
    return _one_pole(signal, coeff, high=True)


def lowpass(signal: np.ndarray, coeff: float | np.ndarray = 0.1) -> np.ndarray:
    return _one_pole(signal, coeff, high=False)


def osc(freq: float | np.ndarray, length_s: float, shape: str = "sine") -> np.ndarray:
    """Oscillator whose frequency may glide sample by sample."""
    n = int(RATE * length_s)
    phase = np.cumsum(np.broadcast_to(freq, (n,))) / RATE % 1.0
    if shape == "square":
        return np.where(phase < 0.5, 1.0, -1.0)
    if shape == "triangle":
        return 4 * np.abs(phase - 0.5) - 1
    if shape == "saw":
        return 2 * phase - 1
    return np.sin(TAU * phase)


def decay(length_s: float, rate: float, attack_s: float = 0.002) -> np.ndarray:
    t = _t(length_s)
    return np.clip(t / attack_s, 0, 1) * np.exp(-t * rate)


def note(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def kick(length_s: float = 0.35, top_hz: float = 150.0, low_hz: float = 45.0) -> np.ndarray:
    t = _t(length_s)
    return osc(low_hz + (top_hz - low_hz) * np.exp(-t * 30), length_s) * np.exp(-t * 9)


def hat(seed: int, length_s: float = 0.06) -> np.ndarray:
    return highpass(_noise(length_s, seed)) * decay(length_s, 70, 0.0005)


def riser(length_s: float, seed: int) -> np.ndarray:
    ramp = np.linspace(0.0, 1.0, int(RATE * length_s))
    body = highpass(_noise(length_s, seed), 0.8 + 0.19 * ramp)
    sweep = osc(200 + 1800 * ramp**2, length_s) * 0.25
    return (body + sweep) * ramp**2


def supersaw(midis: tuple[float, ...], length_s: float, shape: str = "saw") -> np.ndarray:
    out = sum(osc(note(m) * 2 ** (c / 1200), length_s, shape) for m in midis for c in DETUNE_CENTS)
    return out / (len(midis) * len(DETUNE_CENTS))


def crash(length_s: float, seed: int) -> np.ndarray:
    return highpass(_noise(length_s, seed), 0.7) * decay(length_s, 4)


# ---------- mixing ----------


class Mix:
    """Stereo bus with beat-free placement in seconds and simple panning."""

    def __init__(self, total_s: float) -> None:
        self.bus = np.zeros((int(RATE * total_s), 2))

    def add(self, sound: np.ndarray, at_s: float, gain: float, pan: float = 0.0) -> None:
        start = int(at_s * RATE)
        end = min(len(self.bus), start + len(sound))
        if start >= end or start < 0:
            return
        left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        chunk = sound[: end - start] * gain * np.sqrt(2)
        self.bus[start:end, 0] += chunk * left
        self.bus[start:end, 1] += chunk * right

    def duck(self, times: list[float], depth: float = 0.7) -> None:
        # Pull the level down for a moment after each kick: the club-music "pump".
        t = np.arange(len(self.bus)) / RATE
        env = np.ones(len(self.bus))
        for at in times:
            after = t - at
            mask = after >= 0
            env[mask] = np.minimum(env[mask], 1 - depth * np.exp(-after[mask] * 12))
        self.bus *= env[:, None]


# ---------- the four sound designs ----------


def sparkle(cue: Cue) -> Mix:
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
    boom = osc(35 + 45 * np.exp(-_t(tail) * 6), tail) * decay(tail, 2.5)
    mix.add(boom, hit, 1.0)
    for midi in (57, 64, 68, 71, 76):  # A major 9 as a bell: inharmonic partials
        bell = sum(osc(note(midi) * r, tail) / (k + 1) for k, r in enumerate((1, 2.0, 2.76, 5.4)))
        mix.add(bell * decay(tail, 3), hit, 0.12)
    mix.add(crash(tail, 9), hit, 0.2)
    return mix


def boing(cue: Cue) -> Mix:
    """bounce: every letter lands with a springy boing, rising up the scale."""
    mix = Mix(cue.total_s)
    scale = (60, 62, 64, 65, 67, 69, 71, 72)
    count = len(cue.word)
    # bounceOut touches the ground at 1/2.75, 2/2.75 and 2.5/2.75 of its length.
    for i in range(count):
        drop_at = i * cue.drop_every
        pan = -0.8 + 1.6 * i / max(1, count - 1)
        for k, (fraction, gain) in enumerate(((1 / 2.75, 1.0), (2 / 2.75, 0.35), (2.5 / 2.75, 0.15))):
            at = cue.seconds(drop_at + cue.drop_length * fraction)
            t = _t(0.3)
            wobble = 1 + 0.35 * np.exp(-t * 10) * np.sin(TAU * 14 * t)
            spring = osc(note(scale[i] + 12 * (k > 0)) * wobble, 0.3) * decay(0.3, 9)
            block = highpass(_noise(0.03, 40 + i), 0.5) * decay(0.03, 150)
            mix.add(spring, at, 0.35 * gain, pan)
            mix.add(block, at, 0.3 * gain, pan)
    exit_at, exit_len = cue.seconds(1.75), cue.seconds(0.25)
    ramp = np.linspace(0, 1, int(RATE * exit_len))
    mix.add(highpass(_noise(exit_len, 7), 0.6 + 0.35 * ramp) * ramp, exit_at - 0.02, 0.4)

    hit, tail = cue.hit_s, cue.total_s - cue.hit_s
    pop = osc(900 * np.exp(-_t(0.12) * 25) + 120, 0.12) * decay(0.12, 30)
    mix.add(pop, hit, 1.0)
    mix.add(kick(0.3, 130, 60), hit, 0.7)
    for k, pan in enumerate((-0.4, 0.4, 0.0)):  # a clap is a few noise bursts smeared together
        mix.add(highpass(_noise(0.12, 60 + k), 0.8) * decay(0.12, 25), hit + 0.008 * k, 0.35, pan)
    brass = lowpass(supersaw((60, 64, 67, 72), tail, "square"), 0.04 + 0.2 * decay(tail, 6))
    mix.add(brass * decay(tail, 1.5, 0.02), hit, 1.3)
    for i, step in enumerate((0.5, 1.0, 1.5)):
        mix.add(osc(note(84 + (4, 7, 12)[i]), 0.2, "triangle") * decay(0.2, 12), hit + cue.seconds(step), 0.18)
    return mix


def chiptune(cue: Cue) -> Mix:
    """morph: 8-bit blips, one per shape, each played on the wave that looks like it."""
    mix = Mix(cue.total_s)
    shapes = ("sine", "square", "triangle", "saw")  # circle, square, triangle, star
    melody = (72, 76, 79, 84)
    for i, beat in enumerate(cue.ticks):
        length = cue.seconds(0.5)
        t = _t(length)
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
    crunch = np.round(_noise(tail, 11) * 4) / 4  # 3-bit noise: the NES "crash"
    mix.add(crunch * decay(tail, 5), hit, 0.35)
    mix.add(kick(0.3, 180, 50), hit, 1.0)
    mix.add(supersaw((48, 60, 64, 67), tail, "square") * decay(tail, 1.5, 0.004), hit, 0.7)
    return mix


def engine(cue: Cue) -> Mix:
    """tunnel: a droning engine that climbs with the speed, rings whooshing past."""
    mix = Mix(cue.total_s)
    hit = cue.hit_s
    t = _t(hit)
    beat = t * cue.bpm / 60
    boost = np.where(beat <= 0, 0, 2 ** (10 * np.clip(beat / cue.hit_beat, 0, 1) - 10))  # expoIn
    speed = cue.speed[0] + boost * cue.speed[1]
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
        whoosh = lowpass(_noise(0.08, 100 + k), 0.3) * decay(0.08, 40)
        mix.add(whoosh, at, 0.35, -0.6 if k % 2 else 0.6)
    rise_from, rise_to = (cue.seconds(b) for b in cue.riser)
    reverse_cymbal = crash(rise_to - rise_from, 13)[::-1]
    mix.add(reverse_cymbal, rise_from, 0.35)

    tail = cue.total_s - hit
    mix.add(kick(0.5, 200, 40), hit, 1.0)
    mix.add(osc(80 * np.exp(-_t(tail) * 1.5) + 28, tail) * decay(tail, 1.5), hit, 0.9)
    stab = np.tanh(supersaw((45, 52, 57, 64), tail) * 4)
    mix.add(lowpass(stab, 0.08) * decay(tail, 2.5, 0.004), hit, 0.45)
    mix.add(crash(tail, 9), hit, 0.35)
    return mix


SOUNDS: dict[str, Callable[[Cue], Mix]] = {
    "sparkle": sparkle,
    "boing": boing,
    "chiptune": chiptune,
    "engine": engine,
}


def render(cue: Cue) -> np.ndarray:
    """Stereo (samples x 2) soundtrack, peaking at about -1 dBFS."""
    mix = SOUNDS[cue.sound](cue)
    out = mix.bus

    # A true silence right before the hit makes the landing hit harder.
    gap_from = int((cue.hit_s - cue.silence_before_hit) * RATE)
    out[gap_from : int(cue.hit_s * RATE)] = 0.0

    fade = int(RATE * 0.15)
    out[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    return out / np.max(np.abs(out)) * 0.89


def write_wav(path: Path, stereo: np.ndarray) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm.tobytes())


def cue_from_timeline(timeline: dict, variant: str) -> Cue:
    spec = timeline["variants"][variant]
    drop = spec.get("drop", {})
    return Cue(
        bpm=timeline["bpm"],
        beats=timeline["beats"],
        hit_beat=timeline["hitBeat"],
        silence_before_hit=timeline["silenceBeforeHit"],
        sound=spec["sound"],
        ticks=tuple(spec["ticks"]),
        riser=tuple(spec["riser"]),
        word=spec.get("word", ""),
        drop_every=drop.get("every", 0.0),
        drop_length=drop.get("length", 0.0),
        speed=tuple(spec.get("speed", (0.0, 0.0))),
    )

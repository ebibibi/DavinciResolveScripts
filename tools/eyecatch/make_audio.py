"""Synthesize the sound for one eyecatch from the same beat timeline as the picture.

Nothing here is a sample: the kick is a falling sine, hats / risers are shaped
noise, and the chord is seven detuned sawtooth waves. Every event is placed by
beat number, so it lands on the frame the animation uses for the same beat.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RATE = 48_000
CHORD_HZ = (220.0, 277.18, 329.63, 440.0)  # A major, voiced for a short sting
DETUNE_CENTS = (-18, -11, -5, 0, 5, 11, 18)


@dataclass(frozen=True)
class Cue:
    bpm: float
    beats: float
    hit_beat: float
    silence_before_hit: float
    ticks: tuple[float, ...]
    riser: tuple[float, float]

    def seconds(self, beat: float) -> float:
        return beat * 60.0 / self.bpm


def _noise(length: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1.0, 1.0, length)


def _highpass(signal: np.ndarray, amount: float | np.ndarray = 0.95) -> np.ndarray:
    # One-pole high-pass: removes the rumble so noise reads as "tss", not "shh".
    # `amount` may change per sample, which is how the riser brightens as it climbs.
    coeff = np.broadcast_to(amount, signal.shape)
    out = np.empty_like(signal)
    prev_in = prev_out = 0.0
    for i, x in enumerate(signal):
        prev_out = coeff[i] * (prev_out + x - prev_in)
        prev_in = x
        out[i] = prev_out
    return out


def kick(length_s: float = 0.35, top_hz: float = 150.0, low_hz: float = 45.0) -> np.ndarray:
    t = np.arange(int(RATE * length_s)) / RATE
    freq = low_hz + (top_hz - low_hz) * np.exp(-t * 30)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    return np.sin(phase) * np.exp(-t * 9)


def hat(seed: int, length_s: float = 0.06) -> np.ndarray:
    n = int(RATE * length_s)
    return _highpass(_noise(n, seed)) * np.exp(-np.arange(n) / RATE * 70)


def riser(length_s: float, seed: int) -> np.ndarray:
    n = int(RATE * length_s)
    t = np.linspace(0.0, 1.0, n)
    body = _highpass(_noise(n, seed), 0.8 + 0.19 * t)
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 1800 * t**2) / RATE) * 0.25
    return (body + sweep) * t**2


def chord(length_s: float) -> np.ndarray:
    t = np.arange(int(RATE * length_s)) / RATE
    out = np.zeros_like(t)
    for root in CHORD_HZ:
        for cents in DETUNE_CENTS:
            hz = root * 2 ** (cents / 1200)
            out += 2 * (t * hz % 1.0) - 1  # sawtooth
    out /= len(CHORD_HZ) * len(DETUNE_CENTS)
    attack = np.clip(t / 0.005, 0, 1)
    return out * attack * np.exp(-t * 2.2)


def crash(length_s: float, seed: int) -> np.ndarray:
    n = int(RATE * length_s)
    return _highpass(_noise(n, seed), 0.7) * np.exp(-np.arange(n) / RATE * 4)


def _place(track: np.ndarray, sound: np.ndarray, at_s: float, gain: float) -> None:
    start = int(at_s * RATE)
    end = min(len(track), start + len(sound))
    if start < end:
        track[start:end] += sound[: end - start] * gain


def _sidechain(signal: np.ndarray, kick_times: list[float]) -> np.ndarray:
    # Duck everything else for a moment on each kick: the club-music "pump".
    env = np.ones_like(signal)
    t = np.arange(len(signal)) / RATE
    for at in kick_times:
        after = t - at
        mask = after >= 0
        env[mask] = np.minimum(env[mask], 1 - 0.7 * np.exp(-after[mask] * 12))
    return signal * env


def render(cue: Cue) -> np.ndarray:
    total = int(RATE * cue.seconds(cue.beats))
    drums = np.zeros(total)
    music = np.zeros(total)
    hit_s = cue.seconds(cue.hit_beat)

    kick_times = [cue.seconds(b) for b in cue.ticks] + [hit_s]
    for i, at in enumerate(kick_times[:-1]):
        _place(drums, kick(0.25, 120, 55), at, 0.55)
        _place(drums, hat(i + 1), at + cue.seconds(0.5) * 0.5, 0.25)
    _place(drums, kick(), hit_s, 1.0)

    rise_from, rise_to = (cue.seconds(b) for b in cue.riser)
    _place(music, riser(rise_to - rise_from, 5), rise_from, 0.45)
    _place(music, chord(total / RATE - hit_s), hit_s, 0.8)
    _place(music, crash(total / RATE - hit_s, 9), hit_s, 0.3)
    for i in range(1, 8):
        _place(music, hat(20 + i), hit_s + cue.seconds(i * 0.25), 0.18)

    mix = drums + _sidechain(music, kick_times)

    # A true silence right before the hit makes the landing hit harder.
    gap_from = int((hit_s - cue.silence_before_hit) * RATE)
    mix[gap_from : int(hit_s * RATE)] = 0.0

    fade = int(RATE * 0.15)
    mix[-fade:] *= np.linspace(1.0, 0.0, fade)
    return mix / np.max(np.abs(mix)) * 0.89  # about -1 dBFS


def write_wav(path: Path, mono: np.ndarray) -> None:
    pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2")
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(stereo.tobytes())


def cue_from_timeline(timeline: dict, variant: str) -> Cue:
    spec = timeline["variants"][variant]
    return Cue(
        bpm=timeline["bpm"],
        beats=timeline["beats"],
        hit_beat=timeline["hitBeat"],
        silence_before_hit=timeline["silenceBeforeHit"],
        ticks=tuple(spec["ticks"]),
        riser=tuple(spec["riser"]),
    )

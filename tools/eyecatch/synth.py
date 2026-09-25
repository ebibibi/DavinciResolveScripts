"""Synthesis building blocks shared by every eyecatch sound design.

Everything is made from sine / square / triangle / saw oscillators and shaped
noise; `Mix` is a small stereo bus the designs place sounds on, in seconds.
"""

from __future__ import annotations

import numpy as np

RATE = 48_000
TAU = 2 * np.pi
DETUNE_CENTS = (-18, -11, -5, 0, 5, 11, 18)


# ---------- building blocks ----------


def times(length_s: float) -> np.ndarray:
    return np.arange(int(RATE * length_s)) / RATE


def noise(length_s: float, seed: int) -> np.ndarray:
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
    t = times(length_s)
    return np.clip(t / attack_s, 0, 1) * np.exp(-t * rate)


def note(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def kick(length_s: float = 0.35, top_hz: float = 150.0, low_hz: float = 45.0) -> np.ndarray:
    t = times(length_s)
    return osc(low_hz + (top_hz - low_hz) * np.exp(-t * 30), length_s) * np.exp(-t * 9)


def hat(seed: int, length_s: float = 0.06) -> np.ndarray:
    return highpass(noise(length_s, seed)) * decay(length_s, 70, 0.0005)


def riser(length_s: float, seed: int) -> np.ndarray:
    ramp = np.linspace(0.0, 1.0, int(RATE * length_s))
    body = highpass(noise(length_s, seed), 0.8 + 0.19 * ramp)
    sweep = osc(200 + 1800 * ramp**2, length_s) * 0.25
    return (body + sweep) * ramp**2


def supersaw(midis: tuple[float, ...], length_s: float, shape: str = "saw") -> np.ndarray:
    out = sum(osc(note(m) * 2 ** (c / 1200), length_s, shape) for m in midis for c in DETUNE_CENTS)
    return out / (len(midis) * len(DETUNE_CENTS))


def crash(length_s: float, seed: int) -> np.ndarray:
    return highpass(noise(length_s, seed), 0.7) * decay(length_s, 4)


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

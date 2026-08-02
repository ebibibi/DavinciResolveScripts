#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Estimate the time offset between two recordings of the same session.

OBS writes the slide capture and the camera capture as separate files, and the
two files never start at exactly the same moment. Both files carry the same
voice, so the offset is recovered by correlating their loudness envelopes
instead of their raw waveforms. An envelope survives different microphones,
different gain and different codecs, which a raw waveform does not.

The module is intentionally independent of DaVinci Resolve so it can be tested
without launching the application.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# 8 kHz keeps speech energy while making a one hour recording cheap to load.
DEFAULT_SAMPLE_RATE = 8000
# 200 envelope points per second means a 5 ms resolution, well under one frame.
DEFAULT_ENVELOPE_RATE = 200
# Correlating the first 15 minutes is enough and bounds the memory use.
DEFAULT_MAX_SECONDS = 900.0
# How far the winning lag must stand above the other lags, in deviations.
DEFAULT_MINIMUM_CONFIDENCE = 6.0
# Lags with less overlap than this are ignored even for very short recordings.
_MINIMUM_OVERLAP_STEPS = 200


class AudioSyncError(RuntimeError):
    """Raised when the offset between two recordings cannot be trusted."""


@dataclass(frozen=True)
class SyncResult:
    """Where the reference recording's time zero sits inside the target file.

    A positive offset means the target has to be entered that many seconds in
    before it lines up with the start of the reference. A negative offset means
    the reference is the file that has to be entered later.
    """

    offset_seconds: float
    confidence: float
    envelope_rate: int
    analyzed_seconds: float

    def offset_frames(self, frame_rate: float) -> int:
        """Return the offset rounded to whole frames of the given timeline."""
        return int(round(self.offset_seconds * frame_rate))


def read_mono_audio(
    path: Path,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    ffmpeg: str = "ffmpeg",
) -> np.ndarray:
    """Decode the first audio stream of a media file as mono float samples."""
    if not Path(path).exists():
        raise AudioSyncError(f"Media file was not found: {path}")

    command = [
        ffmpeg,
        "-v", "error",
        "-i", str(path),
        "-t", f"{max_seconds:.3f}",
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "-",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise AudioSyncError(f"ffmpeg was not found: {ffmpeg}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", "replace").strip()
        raise AudioSyncError(f"ffmpeg failed to decode {path}: {detail}") from error

    samples = np.frombuffer(completed.stdout, dtype="<f4")
    if samples.size == 0:
        raise AudioSyncError(f"No audio was decoded from {path}")
    return samples.astype(np.float64, copy=False)


def loudness_envelope(
    samples: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    envelope_rate: int = DEFAULT_ENVELOPE_RATE,
) -> np.ndarray:
    """Reduce raw samples to one root-mean-square value per envelope step."""
    if envelope_rate <= 0 or sample_rate <= 0:
        raise AudioSyncError("Sample rate and envelope rate must be positive")

    block = max(1, sample_rate // envelope_rate)
    usable = (samples.size // block) * block
    if usable == 0:
        raise AudioSyncError("The recording is shorter than one envelope step")

    blocks = samples[:usable].reshape(-1, block)
    energy = np.sqrt(np.mean(np.square(blocks), axis=1))
    # A logarithm keeps quiet speech visible next to loud speech, so the match
    # is driven by the rhythm of the talking rather than by the loudest moment.
    return np.log1p(energy * 1000.0)


def _standardize(envelope: np.ndarray) -> np.ndarray:
    """Center and scale an envelope so gain differences stop mattering."""
    centered = envelope - float(np.mean(envelope))
    deviation = float(np.std(centered))
    if deviation <= 0.0:
        raise AudioSyncError("The recording carries no usable audio variation")
    return centered / deviation


def correlate_envelopes(
    reference: np.ndarray,
    target: np.ndarray,
    envelope_rate: int = DEFAULT_ENVELOPE_RATE,
) -> tuple[float, float]:
    """Return the target lag in seconds and how strongly the peak stands out.

    The lag is the point in the target that matches time zero of the reference,
    so a positive lag means the target already contains what the reference is
    still waiting for.
    """
    first = _standardize(reference)
    second = _standardize(target)

    # Correlating is convolving with the reversed signal, which the FFT does in
    # one pass instead of the quadratic loop a direct correlation would need.
    size = first.size + second.size - 1
    transform_size = int(1 << (size - 1).bit_length())
    spectrum = np.fft.rfft(first, transform_size) * np.fft.rfft(
        second[::-1], transform_size
    )
    correlation = np.fft.irfft(spectrum, transform_size)[:size]

    # Long overlaps accumulate larger sums than short ones, so every lag is
    # divided by how many steps actually overlap there.
    positions = np.arange(size)
    overlap = np.minimum(
        np.minimum(positions + 1, size - positions),
        min(first.size, second.size),
    )
    normalized = correlation / overlap

    # Lags that barely overlap are noise, not evidence, so they never win.
    usable = overlap >= max(_MINIMUM_OVERLAP_STEPS, 0.25 * min(first.size, second.size))
    if not usable.any():
        raise AudioSyncError("The recordings are too short to be compared")

    candidates = np.where(usable, normalized, -np.inf)
    peak_index = int(np.argmax(candidates))

    scores = normalized[usable]
    deviation = float(np.std(scores))
    peak = float(normalized[peak_index])
    confidence = (peak - float(np.mean(scores))) / deviation if deviation > 0.0 else 0.0

    # A correlation index counts how far the reference moved; the caller asks
    # the opposite question, so the sign is flipped back here.
    lag_steps = (second.size - 1) - peak_index
    return lag_steps / envelope_rate, confidence


def estimate_offset(
    reference_path: Path,
    target_path: Path,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    envelope_rate: int = DEFAULT_ENVELOPE_RATE,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
    ffmpeg: str = "ffmpeg",
) -> SyncResult:
    """Find where the reference recording's time zero sits inside the target file."""
    reference_samples = read_mono_audio(reference_path, sample_rate, max_seconds, ffmpeg)
    target_samples = read_mono_audio(target_path, sample_rate, max_seconds, ffmpeg)

    reference_envelope = loudness_envelope(reference_samples, sample_rate, envelope_rate)
    target_envelope = loudness_envelope(target_samples, sample_rate, envelope_rate)

    offset_seconds, confidence = correlate_envelopes(
        reference_envelope, target_envelope, envelope_rate
    )
    if confidence < minimum_confidence:
        raise AudioSyncError(
            "The two recordings did not correlate strongly enough "
            f"(confidence {confidence:.1f} < {minimum_confidence:.1f}). "
            "Check that both files belong to the same session and carry audio."
        )

    analyzed_seconds = min(reference_samples.size, target_samples.size) / sample_rate
    return SyncResult(
        offset_seconds=offset_seconds,
        confidence=confidence,
        envelope_rate=envelope_rate,
        analyzed_seconds=analyzed_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="Recording that defines time zero")
    parser.add_argument("target", type=Path, help="Recording to align to the reference")
    parser.add_argument("--frame-rate", type=float, default=30.0)
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    parser.add_argument(
        "--minimum-confidence", type=float, default=DEFAULT_MINIMUM_CONFIDENCE
    )
    arguments = parser.parse_args()

    try:
        result = estimate_offset(
            arguments.reference,
            arguments.target,
            max_seconds=arguments.max_seconds,
            minimum_confidence=arguments.minimum_confidence,
        )
    except AudioSyncError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1

    print(
        json.dumps(
            {
                "offset_seconds": round(result.offset_seconds, 4),
                "offset_frames": result.offset_frames(arguments.frame_rate),
                "confidence": round(result.confidence, 2),
                "analyzed_seconds": round(result.analyzed_seconds, 1),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

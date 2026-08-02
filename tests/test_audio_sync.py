import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "有償版用スクリプト" / "audio_sync.py"
SPEC = importlib.util.spec_from_file_location("audio_sync", SCRIPT_PATH)
AUDIO_SYNC = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
# The module defines a dataclass, which needs the module visible in sys.modules.
sys.modules["audio_sync"] = AUDIO_SYNC
SPEC.loader.exec_module(AUDIO_SYNC)

SAMPLE_RATE = 8000
ENVELOPE_RATE = AUDIO_SYNC.DEFAULT_ENVELOPE_RATE


def speech_like_samples(seconds: float, seed: int = 7) -> np.ndarray:
    """Build noise that starts and stops like speech, without needing a voice."""
    generator = np.random.default_rng(seed)
    total = int(seconds * SAMPLE_RATE)
    carrier = generator.normal(0.0, 0.3, total)

    gate = np.zeros(total)
    position = 0
    while position < total:
        talk = int(generator.uniform(0.4, 1.6) * SAMPLE_RATE)
        pause = int(generator.uniform(0.2, 0.9) * SAMPLE_RATE)
        gate[position : position + talk] = 1.0
        position += talk + pause
    return carrier * gate


def write_media(path: Path, samples: np.ndarray, codec: str = "aac") -> Path:
    """Encode raw samples into a real media file so ffmpeg decoding is covered."""
    raw = path.with_suffix(".raw")
    raw.write_bytes(samples.astype("<f4").tobytes())
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", str(raw),
            "-c:a", codec, str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_envelope_is_one_value_per_step():
    samples = speech_like_samples(2.0)
    envelope = AUDIO_SYNC.loudness_envelope(samples, SAMPLE_RATE, ENVELOPE_RATE)
    assert envelope.size == pytest.approx(2.0 * ENVELOPE_RATE, abs=1)


def test_positive_lag_means_the_target_has_to_be_entered_later():
    shift_seconds = 1.5
    shift_steps = int(shift_seconds * ENVELOPE_RATE)
    reference = AUDIO_SYNC.loudness_envelope(speech_like_samples(60.0), SAMPLE_RATE)
    # The target sees the same audio but only after a silent head of 1.5 seconds.
    target = np.concatenate((np.zeros(shift_steps), reference))

    lag, confidence = AUDIO_SYNC.correlate_envelopes(reference, target, ENVELOPE_RATE)

    assert lag == pytest.approx(shift_seconds, abs=0.01)
    assert confidence > AUDIO_SYNC.DEFAULT_MINIMUM_CONFIDENCE


def test_negative_lag_means_the_target_is_missing_its_head():
    shift_steps = int(0.8 * ENVELOPE_RATE)
    full = AUDIO_SYNC.loudness_envelope(speech_like_samples(60.0), SAMPLE_RATE)
    # This time the reference is the one that begins early, so the reference has
    # to be entered 0.8 seconds in before the target can follow along.
    reference = np.concatenate((np.zeros(shift_steps), full))
    target = full

    lag, _ = AUDIO_SYNC.correlate_envelopes(reference, target, ENVELOPE_RATE)

    assert lag == pytest.approx(-0.8, abs=0.01)


def test_offset_survives_different_gain_and_microphone_noise():
    shift_steps = int(2.4 * ENVELOPE_RATE)
    clean = AUDIO_SYNC.loudness_envelope(speech_like_samples(90.0), SAMPLE_RATE)
    noise = np.random.default_rng(11).normal(0.0, 0.05, clean.size)
    reference = clean
    target = np.concatenate((np.zeros(shift_steps), clean * 0.25 + noise))

    lag, confidence = AUDIO_SYNC.correlate_envelopes(reference, target, ENVELOPE_RATE)

    assert lag == pytest.approx(2.4, abs=0.02)
    assert confidence > AUDIO_SYNC.DEFAULT_MINIMUM_CONFIDENCE


def test_unrelated_recordings_report_low_confidence():
    reference = AUDIO_SYNC.loudness_envelope(speech_like_samples(60.0, seed=1), SAMPLE_RATE)
    target = AUDIO_SYNC.loudness_envelope(speech_like_samples(60.0, seed=2), SAMPLE_RATE)

    _, confidence = AUDIO_SYNC.correlate_envelopes(reference, target, ENVELOPE_RATE)

    assert confidence < AUDIO_SYNC.DEFAULT_MINIMUM_CONFIDENCE


def test_silent_recording_is_rejected_instead_of_returning_zero():
    silence = np.zeros(SAMPLE_RATE)
    with pytest.raises(AUDIO_SYNC.AudioSyncError):
        AUDIO_SYNC.correlate_envelopes(
            AUDIO_SYNC.loudness_envelope(silence, SAMPLE_RATE),
            AUDIO_SYNC.loudness_envelope(silence, SAMPLE_RATE),
            ENVELOPE_RATE,
        )


def test_missing_file_is_reported_clearly(tmp_path):
    with pytest.raises(AUDIO_SYNC.AudioSyncError, match="was not found"):
        AUDIO_SYNC.read_mono_audio(tmp_path / "absent.mkv")


def test_estimate_offset_on_losslessly_encoded_files(tmp_path):
    shift_seconds = 3.2
    session = speech_like_samples(45.0)
    head = np.zeros(int(shift_seconds * SAMPLE_RATE))

    slides = write_media(tmp_path / "slides.wav", session, codec="pcm_s16le")
    camera = write_media(
        tmp_path / "camera.wav", np.concatenate((head, session * 0.4)), codec="pcm_s16le"
    )

    result = AUDIO_SYNC.estimate_offset(slides, camera)

    assert result.offset_seconds == pytest.approx(shift_seconds, abs=0.01)
    assert result.offset_frames(30.0) == 96
    assert result.confidence > AUDIO_SYNC.DEFAULT_MINIMUM_CONFIDENCE


def test_estimate_offset_across_the_obs_container_pair(tmp_path):
    """A real pair is an mkv and an mp4, whose codec priming differs slightly."""
    shift_seconds = 3.2
    session = speech_like_samples(45.0)
    head = np.zeros(int(shift_seconds * SAMPLE_RATE))

    slides = write_media(tmp_path / "slides.mkv", session)
    camera = write_media(tmp_path / "camera.mp4", np.concatenate((head, session * 0.4)))

    result = AUDIO_SYNC.estimate_offset(slides, camera)

    # Lossy containers add up to about a tenth of a second of encoder priming,
    # which is invisible once only one of the two audio tracks is used.
    assert result.offset_seconds == pytest.approx(shift_seconds, abs=0.25)
    assert result.confidence > AUDIO_SYNC.DEFAULT_MINIMUM_CONFIDENCE


def test_a_file_without_audio_is_reported_clearly(tmp_path):
    silent_video = tmp_path / "noaudio.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=30:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent_video),
        ],
        check=True,
        capture_output=True,
    )

    # ffmpeg refuses to write an empty stream, so the failure surfaces as a
    # decode error naming the file rather than as an empty result.
    with pytest.raises(AUDIO_SYNC.AudioSyncError, match="noaudio.mp4"):
        AUDIO_SYNC.read_mono_audio(silent_video)


def test_a_missing_ffmpeg_is_reported_clearly(tmp_path):
    present = write_media(tmp_path / "a.wav", speech_like_samples(1.0), codec="pcm_s16le")

    with pytest.raises(AUDIO_SYNC.AudioSyncError, match="ffmpeg was not found"):
        AUDIO_SYNC.read_mono_audio(present, ffmpeg="ffmpeg-that-does-not-exist")


def test_an_impossible_envelope_rate_is_refused():
    with pytest.raises(AUDIO_SYNC.AudioSyncError, match="must be positive"):
        AUDIO_SYNC.loudness_envelope(np.zeros(100), SAMPLE_RATE, envelope_rate=0)


def test_a_clip_shorter_than_one_envelope_step_is_refused():
    with pytest.raises(AUDIO_SYNC.AudioSyncError, match="shorter than one envelope step"):
        AUDIO_SYNC.loudness_envelope(np.zeros(3), SAMPLE_RATE, ENVELOPE_RATE)


def test_the_command_line_prints_the_offset_in_frames(tmp_path, capsys, monkeypatch):
    slides = write_media(tmp_path / "slides.wav", speech_like_samples(30.0), codec="pcm_s16le")
    head = np.zeros(int(1.5 * SAMPLE_RATE))
    camera = write_media(
        tmp_path / "camera.wav",
        np.concatenate((head, speech_like_samples(30.0))),
        codec="pcm_s16le",
    )
    monkeypatch.setattr(sys, "argv", ["audio_sync.py", str(slides), str(camera)])

    assert AUDIO_SYNC.main() == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["offset_frames"] == 45


def test_the_command_line_reports_a_failure_without_a_traceback(tmp_path, capsys, monkeypatch):
    first = write_media(tmp_path / "one.wav", speech_like_samples(30.0, seed=1), codec="pcm_s16le")
    second = write_media(tmp_path / "two.wav", speech_like_samples(30.0, seed=2), codec="pcm_s16le")
    monkeypatch.setattr(sys, "argv", ["audio_sync.py", str(first), str(second)])

    assert AUDIO_SYNC.main() == 1

    assert "error" in json.loads(capsys.readouterr().out)

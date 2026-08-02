"""Run the non-Resolve half of the dual source route against the real tools.

ffmpeg builds two recordings of the same fake talk, auto-editor finds the
silence, and the placement plan is checked for drift between the two tracks.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT_DIR = Path(__file__).parents[1] / "有償版用スクリプト"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(SCRIPT_DIR))
AUDIO_SYNC = load("audio_sync")
DUAL_SOURCE = load("dual_source")
EDITOR = load("dual_source_video_editor")

SAMPLE_RATE = 8000
FRAME_RATE = 30
# The real template timeline runs faster than the recordings do.
TIMELINE_FRAME_RATE = 60
SLIDE_OFFSET_SECONDS = 2.0

pytestmark = pytest.mark.skipif(
    shutil.which("auto-editor") is None or shutil.which("ffmpeg") is None,
    reason="auto-editor and ffmpeg are required for the dual source integration test",
)


def talk_audio(seconds: float) -> np.ndarray:
    """Speech-like noise with clear silent gaps for auto-editor to remove."""
    generator = np.random.default_rng(5)
    total = int(seconds * SAMPLE_RATE)
    gate = np.zeros(total)
    position = 0
    while position < total:
        talk = int(generator.uniform(1.5, 3.0) * SAMPLE_RATE)
        pause = int(generator.uniform(1.0, 2.0) * SAMPLE_RATE)
        gate[position : position + talk] = 1.0
        position += talk + pause
    return generator.normal(0.0, 0.3, total) * gate


def write_recording(path: Path, samples: np.ndarray, color: str) -> Path:
    raw = path.with_suffix(".raw")
    raw.write_bytes(samples.astype("<f4").tobytes())
    duration = samples.size / SAMPLE_RATE
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=320x180:r={FRAME_RATE}:d={duration:.3f}",
            "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", str(raw),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(path),
        ],
        check=True,
        capture_output=True,
    )
    raw.unlink()
    return path


@pytest.fixture(scope="module")
def recording_folder(tmp_path_factory) -> Path:
    folder = tmp_path_factory.mktemp("obs") / "az900-3"
    folder.mkdir()
    talk = talk_audio(40.0)
    head = np.zeros(int(SLIDE_OFFSET_SECONDS * SAMPLE_RATE))

    write_recording(folder / "PPT.mkv", talk, "blue")
    write_recording(folder / "camera.mp4", np.concatenate((head, talk * 0.5)), "green")
    return folder


def test_the_folder_is_recognized_and_the_two_tracks_stay_in_sync(recording_folder):
    pair = DUAL_SOURCE.find_recording_pair(recording_folder)
    assert pair is not None

    sync = AUDIO_SYNC.estimate_offset(pair.slides, pair.camera)
    assert sync.offset_seconds == pytest.approx(SLIDE_OFFSET_SECONDS, abs=0.25)
    offset_frames = DUAL_SOURCE.seconds_to_frames(sync.offset_seconds, FRAME_RATE)

    # Going through the editor's own call exercises the --export name fallback
    # against whichever auto-editor version is actually installed.
    cut_list_path = recording_folder / "cuts.json"
    document = EDITOR.run_auto_editor_cut_list(pair.camera, cut_list_path)
    assert document is not None, "auto-editor produced no cut list"

    segments = DUAL_SOURCE.parse_cut_list(document)
    assert len(segments) > 1, "the fake talk should be cut into several segments"

    plan = DUAL_SOURCE.build_placements(
        segments,
        rates=DUAL_SOURCE.FrameRates(
            timeline=TIMELINE_FRAME_RATE,
            slides=FRAME_RATE,
            camera=FRAME_RATE,
            cut_list=FRAME_RATE,
        ),
        slides_offset_seconds=sync.offset_seconds,
        timeline_start_frame=300,
    )

    placements = plan.placements
    slides = [p for p in placements if p.role == "slides"]
    camera = [p for p in placements if p.role == "camera"]
    # Same timeline position and same length on both tracks means no drift.
    assert [p.record_frame for p in slides] == [p.record_frame for p in camera]
    assert [p.end_frame - p.start_frame for p in slides] == [
        p.end_frame - p.start_frame for p in camera
    ]
    # Every camera frame maps back to the slide frame recorded at the same moment.
    assert all(
        c.start_frame - s.start_frame == offset_frames for s, c in zip(slides, camera)
    )
    # Record frames count the faster timeline, source frames the slower camera.
    assert plan.end_frame > sum(p.end_frame - p.start_frame for p in camera)
    assert all(p.start_frame >= 0 for p in placements)

"""End-to-end tests for the FFmpeg-only route, using real FFmpeg.

Only the two slow, external stages are replaced: auto-editor and Whisper. The
overlay build, the sound effect synthesis and the final render all run for real,
because those are exactly the parts a unit test cannot prove.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "有償版用スクリプト"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import advanced_video_editor as editor  # noqa: E402

TOOLS_AVAILABLE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
requires_ffmpeg = pytest.mark.skipif(
    not TOOLS_AVAILABLE, reason="FFmpeg integration tools are unavailable"
)

TRANSCRIPT = {
    "segments": [
        {"start": 0.5, "end": 2.0, "text": "This is the opening claim."},
        {"start": 2.5, "end": 4.0, "text": "This is the strongest moment."},
        {"start": 4.5, "end": 5.8, "text": "This is the closing thought."},
    ]
}


def make_clip(path: Path, seconds: int = 6) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=320x180:rate=30:duration={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={seconds}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


@pytest.fixture()
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Stand in for auto-editor, Whisper and Claude with fixed answers."""
    source = make_clip(tmp_path / "recording.mp4")
    output_dir = tmp_path / "out"

    def fake_cut(src: Path, out: Path, reporter=None) -> Path:
        out.mkdir(parents=True, exist_ok=True)
        target = out / f"{src.stem}.cut_master.mp4"
        shutil.copy(src, target)
        return target

    def fake_transcribe(src: Path, out: Path, template=(), reporter=None) -> Path:
        transcript = out / f"{src.stem}.json"
        transcript.write_text(json.dumps(TRANSCRIPT), encoding="utf-8")
        return transcript

    monkeypatch.setattr(editor, "render_cut_master", fake_cut)
    monkeypatch.setattr(editor, "transcribe_cut_master", fake_transcribe)
    monkeypatch.setattr(
        editor,
        "request_editorial_plan",
        lambda *args, **kwargs: {
            "main_takeaway": "One command edits the whole video",
            "highlight_segment_indexes": [1],
            "chapters": [{"segment_index": 2, "title": "The closing"}],
            "telops": [{"segment_index": 1, "text": "Strongest moment"}],
        },
    )
    return source, output_dir


def advanced_config() -> editor.AdvancedConfig:
    return editor.AdvancedConfig(
        minimum_chapter_gap_seconds=1.0,
        video_preset="ultrafast",
        video_crf=30,
    )


def pipeline_config() -> editor.PipelineConfig:
    return editor.PipelineConfig(font_name="DejaVu Sans", font_size=28)


@requires_ffmpeg
def test_the_finished_video_is_longer_than_the_body_by_the_reel(
    prepared: tuple[Path, Path],
) -> None:
    source, output_dir = prepared
    result = editor.run_pipeline(source, output_dir, pipeline_config(), advanced_config())

    assert result.name == "recording.edited.mp4"
    manifest = json.loads((output_dir / "edit_plan.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["takeaway"] == "One command edits the whole video"
    assert len(manifest["highlights"]) == 1

    body = editor.probe_video(Path(manifest["cut_master"])).duration
    reel = sum(item["end"] - item["start"] for item in manifest["highlights"])
    assert editor.probe_video(result).duration == pytest.approx(body + reel, abs=0.35)


@requires_ffmpeg
def test_every_layer_reaches_the_output_directory(
    prepared: tuple[Path, Path],
) -> None:
    source, output_dir = prepared
    editor.run_pipeline(source, output_dir, pipeline_config(), advanced_config())

    overlays = (output_dir / "overlays.ass").read_text(encoding="utf-8-sig")
    assert "One command edits the whole video" in overlays
    assert "Strongest moment" in overlays
    assert "1. The closing" in overlays
    assert "This is the opening claim." in overlays
    assert (output_dir / "sound_effects.wav").stat().st_size > 0


@requires_ffmpeg
def test_dry_run_plans_everything_and_renders_nothing(
    prepared: tuple[Path, Path],
) -> None:
    source, output_dir = prepared
    result = editor.run_pipeline(
        source, output_dir, pipeline_config(), advanced_config(), dry_run=True
    )

    assert result.name == "edit_plan.json"
    assert json.loads(result.read_text(encoding="utf-8"))["status"] == "dry_run"
    assert not (output_dir / "recording.edited.mp4").exists()


@requires_ffmpeg
def test_a_failed_transcription_still_leaves_the_cut_master(
    prepared: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, output_dir = prepared

    def explode(*args, **kwargs):
        raise RuntimeError("whisper is not installed")

    monkeypatch.setattr(editor, "transcribe_cut_master", explode)
    result = editor.run_pipeline(source, output_dir, pipeline_config(), advanced_config())

    assert result.name == "recording.cut_master.mp4"
    manifest = json.loads((output_dir / "edit_plan.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "fallback"
    assert "whisper is not installed" in manifest["fallback_reason"]


@requires_ffmpeg
def test_a_failed_render_deletes_the_partial_file_and_keeps_the_cut_master(
    prepared: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, output_dir = prepared
    monkeypatch.setattr(
        editor,
        "build_render_command",
        lambda *args, **kwargs: ["ffmpeg", "-y", "-f", "lavfi", "-i", "nonexistent"],
    )
    result = editor.run_pipeline(source, output_dir, pipeline_config(), advanced_config())

    assert result.name == "recording.cut_master.mp4"
    assert not (output_dir / "recording.edited.mp4").exists()
    manifest = json.loads((output_dir / "edit_plan.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "fallback"
    assert manifest["fallback_reason"].startswith("render_failed")


@requires_ffmpeg
def test_switching_every_layer_off_still_produces_the_highlight_first_cut(
    prepared: tuple[Path, Path],
) -> None:
    source, output_dir = prepared
    result = editor.run_pipeline(
        source,
        output_dir,
        pipeline_config(),
        editor.AdvancedConfig(
            captions=False,
            telops=False,
            chapters=False,
            sound_effects=False,
            video_preset="ultrafast",
            video_crf=30,
        ),
    )

    assert result.name == "recording.edited.mp4"
    assert not (output_dir / "sound_effects.wav").exists()
    manifest = json.loads((output_dir / "edit_plan.json").read_text(encoding="utf-8"))
    assert manifest["caption_count"] == 0
    assert manifest["sound_cues"] == []
    assert manifest["highlights"]

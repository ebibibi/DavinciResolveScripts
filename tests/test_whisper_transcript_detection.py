import importlib.util
import json
import os
from pathlib import Path


os.environ["DAVINCI_GIT_PULL_DONE"] = "1"

SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "有償版用スクリプト"
    / "auto_video_editor.py"
)
SPEC = importlib.util.spec_from_file_location("auto_video_editor_whisper", SCRIPT_PATH)
EDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EDITOR)


def write_json(path: Path, data: dict, mtime: float = 200.0) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_detects_remote_json_from_sanitized_whisper_audio_name(tmp_path: Path) -> None:
    source = tmp_path / "2026-07-16 11-22-24.mkv"
    transcript = tmp_path / "2026-07-16_11-22-24.whisper_audio.json"
    write_json(
        transcript,
        {"segments": [{"start": 0.0, "end": 1.0, "text": "テスト"}]},
    )

    result = EDITOR.find_whisper_transcript_path(
        tmp_path,
        source,
        min_mtime=100.0,
    )

    assert result == transcript


def test_rejects_valid_transcript_from_a_different_source(tmp_path: Path) -> None:
    source = tmp_path / "2026-07-16 11-22-24.mkv"
    other = tmp_path / "2026-07-15_09-00-00.whisper_audio.json"
    write_json(
        other,
        {"segments": [{"start": 0.0, "end": 1.0, "text": "別動画"}]},
    )

    result = EDITOR.find_whisper_transcript_path(tmp_path, source)

    assert result is None


def test_rejects_matching_json_without_whisper_segments(tmp_path: Path) -> None:
    source = tmp_path / "2026-07-16 11-22-24.mkv"
    invalid = tmp_path / "2026-07-16_11-22-24.whisper_audio.json"
    write_json(invalid, {"actions": []})

    result = EDITOR.find_whisper_transcript_path(tmp_path, source)

    assert result is None

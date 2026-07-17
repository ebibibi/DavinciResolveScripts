import importlib.util
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace


os.environ["DAVINCI_GIT_PULL_DONE"] = "1"

SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "有償版用スクリプト"
    / "auto_video_editor.py"
)
SPEC = importlib.util.spec_from_file_location("auto_video_editor_fallback", SCRIPT_PATH)
EDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EDITOR)


def called_process_error(command, stderr):
    return subprocess.CalledProcessError(
        1,
        command,
        output="",
        stderr=stderr,
    )


def test_empty_timeline_retries_with_full_recording(tmp_path, monkeypatch) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"video")
    calls = []

    def fake_run(command, check=True, cwd=None):
        calls.append((command, check, cwd))
        if len(calls) == 1:
            raise called_process_error(command, "Error! Timeline is empty, nothing to do.")
        return SimpleNamespace(stdout="Starting")

    monkeypatch.setattr(EDITOR, "run_text_subprocess", fake_run)

    result = EDITOR.run_auto_editor(str(tmp_path))

    assert result == source
    assert calls[0][0][calls[0][0].index("--edit") + 1] == "audio:threshold=1%"
    assert calls[1][0][calls[1][0].index("--edit") + 1] == "none"
    assert "--margin" not in calls[1][0]
    assert all(call[2] == str(tmp_path) for call in calls)


def test_unrelated_auto_editor_error_does_not_retry(tmp_path, monkeypatch) -> None:
    (tmp_path / "recording.mkv").write_bytes(b"video")
    calls = []

    def fake_run(command, check=True, cwd=None):
        calls.append(command)
        raise called_process_error(command, "Error! Invalid media file")

    monkeypatch.setattr(EDITOR, "run_text_subprocess", fake_run)

    assert EDITOR.run_auto_editor(str(tmp_path)) is False
    assert len(calls) == 1


def test_full_recording_retry_failure_stops_safely(tmp_path, monkeypatch) -> None:
    (tmp_path / "recording.mkv").write_bytes(b"video")
    calls = []

    def fake_run(command, check=True, cwd=None):
        calls.append(command)
        message = (
            "Error! Timeline is empty, nothing to do."
            if len(calls) == 1
            else "Error! Resolve export failed"
        )
        raise called_process_error(command, message)

    monkeypatch.setattr(EDITOR, "run_text_subprocess", fake_run)

    assert EDITOR.run_auto_editor(str(tmp_path)) is False
    assert len(calls) == 2

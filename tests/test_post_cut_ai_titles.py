import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace


os.environ["DAVINCI_GIT_PULL_DONE"] = "1"

SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "有償版用スクリプト"
    / "auto_video_editor.py"
)
SPEC = importlib.util.spec_from_file_location("auto_video_editor_post_cut", SCRIPT_PATH)
EDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EDITOR)


def test_cut_master_command_keeps_the_proven_auto_editor_settings(tmp_path: Path) -> None:
    source = tmp_path / "recording.mkv"
    output = tmp_path / "cut_master.mp4"

    command = EDITOR.build_cut_master_command(
        source,
        output,
        edit_method="audio:threshold=1%",
    )

    assert command[:2] == ["auto-editor", str(source)]
    assert command[command.index("--edit") + 1] == "audio:threshold=1%"
    assert command[command.index("--margin") + 1] == "0.5sec"
    assert command[command.index("-o") + 1] == str(output)
    assert command[command.index("--video-bitrate") + 1] == "40M"
    assert command[command.index("--audio-bitrate") + 1] == "320k"


def test_cut_master_command_omits_margin_for_full_recording_fallback(tmp_path: Path) -> None:
    command = EDITOR.build_cut_master_command(
        tmp_path / "recording.mkv",
        tmp_path / "cut_master.mp4",
        edit_method="none",
    )

    assert command[command.index("--edit") + 1] == "none"
    assert "--margin" not in command


def test_parse_ai_highlights_accepts_only_grounded_segment_indexes() -> None:
    segments = [
        {"start": 1.0, "end": 4.0, "text": "結論として自動カットを残します"},
        {"start": 10.0, "end": 13.0, "text": "次の説明です"},
    ]
    output = json.dumps({
        "structured_output": {
            "highlights": [
                {"segment_index": 0, "text": "自動カットは残す"},
                {"segment_index": 99, "text": "存在しない発言"},
            ],
        },
    })

    highlights = EDITOR.parse_ai_highlight_cues(output, segments)

    assert highlights == [{
        "time": 1.0,
        "duration": 3.0,
        "text": "自動カットは残す",
        "source_text": "結論として自動カットを残します",
    }]


def test_highlight_ass_uses_cut_video_timestamps_and_escapes_text(tmp_path: Path) -> None:
    ass_path = tmp_path / "ai_highlights.ass"

    EDITOR.write_highlight_ass(
        ass_path,
        [{
            "time": 61.25,
            "duration": 2.5,
            "text": r"結論{重要}\次へ",
        }],
        resolution=(1920, 1080),
        font_name="HGPSoeiKakugothicUB",
    )

    content = ass_path.read_text(encoding="utf-8-sig")
    assert "Style: Highlight,HGPSoeiKakugothicUB" in content
    assert "Dialogue: 0,0:01:01.25,0:01:03.75,Highlight" in content
    assert r"結論\{重要\}\\次へ" in content


def test_render_highlight_video_runs_ffmpeg_from_ass_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "cut_master.mp4"
    source.write_bytes(b"video")
    ass_path = tmp_path / "ai_highlights.ass"
    ass_path.write_text("ass", encoding="utf-8")
    output = tmp_path / "ai_titled.mp4"
    calls = []

    def fake_run(command, check=True, cwd=None):
        calls.append((command, check, cwd))
        output.write_bytes(b"rendered")
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(EDITOR, "run_text_subprocess", fake_run)
    monkeypatch.setattr(EDITOR.shutil, "which", lambda name: "ffmpeg" if name == "ffmpeg" else None)

    result = EDITOR.render_highlight_video(source, ass_path, output)

    assert result == output
    command, check, cwd = calls[0]
    assert command[0] == "ffmpeg"
    assert command[command.index("-vf") + 1] == "ass=ai_highlights.ass"
    assert cwd == str(tmp_path)
    assert check is True

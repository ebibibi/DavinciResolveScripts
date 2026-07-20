import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "有償版用スクリプト" / "highlight_video.py"
SPEC = importlib.util.spec_from_file_location("highlight_video", SCRIPT_PATH)
HIGHLIGHT_VIDEO = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(HIGHLIGHT_VIDEO)


def transcript_segments() -> list[dict]:
    return [
        {"start": 10.0, "end": 15.0, "text": "まず前提を説明します"},
        {
            "start": 120.0,
            "end": 127.0,
            "text": "結論はauto-editorで無音をカットすることです",
        },
        {"start": 900.0, "end": 907.0, "text": "実際に冒頭ハイライトを複数入れます"},
        {
            "start": 1800.0,
            "end": 1807.0,
            "text": "重要なのは大きなテロップで結論を見せることです",
        },
    ]


def test_desired_highlight_count_grows_for_long_form_video() -> None:
    assert HIGHLIGHT_VIDEO.desired_highlight_count(19 * 60, maximum=3) == 1
    assert HIGHLIGHT_VIDEO.desired_highlight_count(20 * 60, maximum=3) == 2
    assert HIGHLIGHT_VIDEO.desired_highlight_count(45 * 60, maximum=3) == 3
    assert HIGHLIGHT_VIDEO.desired_highlight_count(90 * 60, maximum=2) == 2


def test_parse_ai_plan_keeps_grounded_indexes_and_bounded_title() -> None:
    output = json.dumps(
        {
            "structured_output": {
                "main_takeaway": "auto-editorと冒頭ハイライトで動画編集を短縮",
                "highlight_segment_indexes": [1, 99, 3],
            }
        },
        ensure_ascii=False,
    )

    plan = HIGHLIGHT_VIDEO.parse_ai_plan(
        output,
        transcript_segments(),
        desired_count=2,
        padding_seconds=0.5,
        maximum_segment_seconds=8.0,
    )

    assert plan.title == "auto-editorと冒頭ハイライトで動画編集を短縮"
    assert [(item.start, item.end) for item in plan.highlights] == [
        (119.5, 127.5),
        (1799.5, 1807.0),
    ]


def test_local_plan_selects_multiple_separated_highlights() -> None:
    plan = HIGHLIGHT_VIDEO.build_local_plan(
        transcript_segments(),
        video_duration=60 * 60,
        maximum_highlights=3,
        padding_seconds=0.0,
        maximum_segment_seconds=8.0,
        minimum_gap_seconds=30.0,
    )

    assert len(plan.highlights) == 3
    assert plan.title
    assert (
        plan.highlights[0].start < plan.highlights[1].start < plan.highlights[2].start
    )
    assert all(item.end - item.start <= 8.0 for item in plan.highlights)


def test_ai_plan_uses_grounded_structured_output(monkeypatch) -> None:
    payload = json.dumps(
        {
            "structured_output": {
                "main_takeaway": "冒頭で結論を見せる",
                "highlight_segment_indexes": [1, 3],
            }
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO.shutil,
        "which",
        lambda name: "/usr/bin/claude" if name == "claude" else None,
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=payload, stderr="", returncode=0
        ),
    )

    plan = HIGHLIGHT_VIDEO.build_ai_plan(
        transcript_segments(),
        video_duration=3600,
        config=HIGHLIGHT_VIDEO.PipelineConfig(maximum_highlights=2),
    )

    assert plan is not None
    assert plan.title == "冒頭で結論を見せる"
    assert len(plan.highlights) == 2


def test_ai_plan_returns_none_when_claude_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO.shutil, "which", lambda _name: "/usr/bin/claude"
    )

    def fail(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["claude"], 180)

    monkeypatch.setattr(HIGHLIGHT_VIDEO.subprocess, "run", fail)

    assert (
        HIGHLIGHT_VIDEO.build_ai_plan(
            transcript_segments(),
            video_duration=100,
            config=HIGHLIGHT_VIDEO.PipelineConfig(),
        )
        is None
    )


def test_manual_plan_overrides_ai_selection() -> None:
    plan = HIGHLIGHT_VIDEO.build_manual_plan(
        title="今回は冒頭で結論を見せる",
        highlights=[
            {"start": 30, "end": 36},
            {"start": 70, "end": 79},
        ],
        video_duration=100,
        maximum_highlights=3,
        maximum_total_seconds=20,
    )

    assert plan.title == "今回は冒頭で結論を見せる"
    assert [(item.start, item.end) for item in plan.highlights] == [
        (30.0, 36.0),
        (70.0, 79.0),
    ]


def test_manual_plan_rejects_invalid_overlapping_and_excess_ranges() -> None:
    plan = HIGHLIGHT_VIDEO.build_manual_plan(
        title="  結論を　先に見せる  ",
        highlights=[
            {"start": -5, "end": 4},
            {"start": 3, "end": 8},
            {"start": 20, "end": 40},
            {"start": float("nan"), "end": 50},
        ],
        video_duration=30,
        maximum_highlights=3,
        maximum_total_seconds=10,
    )

    assert plan.title == "結論を 先に見せる"
    assert [(item.start, item.end) for item in plan.highlights] == [
        (0.0, 4.0),
        (20.0, 26.0),
    ]


def test_ffmpeg_command_prepends_copies_then_the_complete_main_body(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cut master.mp4"
    subtitle = tmp_path / "opening title.ass"
    output = tmp_path / "final.mp4"
    plan = HIGHLIGHT_VIDEO.HighlightPlan(
        title="冒頭で結論を見せる",
        highlights=(
            HIGHLIGHT_VIDEO.Highlight(10.0, 16.0, "first"),
            HIGHLIGHT_VIDEO.Highlight(50.0, 57.0, "second"),
        ),
    )

    command = HIGHLIGHT_VIDEO.build_ffmpeg_command(source, subtitle, output, plan)
    filter_graph = command[command.index("-filter_complex") + 1]

    assert "trim=start=10.000:end=16.000" in filter_graph
    assert "trim=start=50.000:end=57.000" in filter_graph
    assert "concat=n=3:v=1:a=1" in filter_graph
    assert "ass=opening\\ title.ass" in filter_graph
    assert command[-1] == str(output)


def test_opening_ass_displays_large_takeaway_during_first_highlight(
    tmp_path: Path,
) -> None:
    output = tmp_path / "opening.ass"

    HIGHLIGHT_VIDEO.write_opening_ass(
        output,
        title=r"結論{A}\B",
        display_seconds=4.0,
        resolution=(1920, 1080),
        font_name="Noto Sans CJK JP",
        font_size=88,
    )

    content = output.read_text(encoding="utf-8-sig")
    assert "Style: Takeaway,Noto Sans CJK JP,88" in content
    assert "Dialogue: 0,0:00:00.00,0:00:04.00,Takeaway" in content
    assert r"結論\{A\}\\B" in content


def test_pipeline_writes_review_plan_and_returns_rendered_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    cut_master = tmp_path / "cut_master.mp4"
    cut_master.write_bytes(b"cut")
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps({"segments": transcript_segments()}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "render_cut_master",
        lambda *_args, **_kwargs: cut_master,
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "transcribe_cut_master",
        lambda *_args, **_kwargs: transcript,
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "probe_video",
        lambda _path: HIGHLIGHT_VIDEO.VideoInfo(3600.0, 1920, 1080),
    )

    def fake_render(_source, _ass, output, _plan):
        output.write_bytes(b"rendered")
        return output

    monkeypatch.setattr(HIGHLIGHT_VIDEO, "render_highlight_video", fake_render)
    monkeypatch.setattr(HIGHLIGHT_VIDEO.shutil, "which", lambda _name: None)

    result = HIGHLIGHT_VIDEO.run_pipeline(
        source,
        tmp_path / "output",
        HIGHLIGHT_VIDEO.PipelineConfig(),
    )

    assert result.name.endswith(".highlighted.mp4")
    assert result.read_bytes() == b"rendered"
    plan_data = json.loads(
        (tmp_path / "output" / "highlight_plan.json").read_text(encoding="utf-8")
    )
    assert len(plan_data["highlights"]) == 3
    assert plan_data["output"] == str(result)


def test_manual_pipeline_does_not_require_whisper_or_claude(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    cut_master = tmp_path / "cut.mp4"
    cut_master.write_bytes(b"cut")
    monkeypatch.setattr(HIGHLIGHT_VIDEO, "render_cut_master", lambda *_args: cut_master)
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "probe_video",
        lambda _path: HIGHLIGHT_VIDEO.VideoInfo(100.0, 1920, 1080),
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "transcribe_cut_master",
        lambda *_args: pytest.fail("manual ranges must bypass Whisper"),
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "build_ai_plan",
        lambda *_args, **_kwargs: pytest.fail("manual ranges must bypass Claude"),
    )

    def fake_render(_source, _subtitle, output, _plan):
        output.write_bytes(b"rendered")
        return output

    monkeypatch.setattr(HIGHLIGHT_VIDEO, "render_highlight_video", fake_render)
    config = HIGHLIGHT_VIDEO.PipelineConfig(
        manual_title="結論を先に見せる",
        manual_highlights=({"start": 10, "end": 16},),
    )

    result = HIGHLIGHT_VIDEO.run_pipeline(source, tmp_path / "output", config)

    assert result.read_bytes() == b"rendered"


def test_transcription_failure_keeps_cut_master_and_records_reason(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    cut_master = tmp_path / "cut.mp4"
    cut_master.write_bytes(b"cut")
    output_dir = tmp_path / "output"
    monkeypatch.setattr(HIGHLIGHT_VIDEO, "render_cut_master", lambda *_args: cut_master)
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "probe_video",
        lambda _path: HIGHLIGHT_VIDEO.VideoInfo(100.0, 1920, 1080),
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "transcribe_cut_master",
        lambda *_args: (_ for _ in ()).throw(FileNotFoundError("whisper missing")),
    )

    result = HIGHLIGHT_VIDEO.run_pipeline(
        source,
        output_dir,
        HIGHLIGHT_VIDEO.PipelineConfig(),
    )

    assert result == cut_master
    manifest = json.loads(
        (output_dir / "highlight_plan.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "fallback"
    assert "transcription_failed" in manifest["fallback_reason"]


def test_render_failure_deletes_partial_and_keeps_cut_master(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    cut_master = tmp_path / "cut.mp4"
    cut_master.write_bytes(b"cut")
    output_dir = tmp_path / "output"
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps({"segments": transcript_segments()}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(HIGHLIGHT_VIDEO, "render_cut_master", lambda *_args: cut_master)
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO, "transcribe_cut_master", lambda *_args: transcript
    )
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "probe_video",
        lambda _path: HIGHLIGHT_VIDEO.VideoInfo(3600.0, 1920, 1080),
    )

    def failing_render(_source, _subtitle, output, _plan):
        output.write_bytes(b"partial")
        raise subprocess.CalledProcessError(1, ["ffmpeg"])

    monkeypatch.setattr(HIGHLIGHT_VIDEO, "render_highlight_video", failing_render)
    monkeypatch.setattr(HIGHLIGHT_VIDEO.shutil, "which", lambda _name: None)

    result = HIGHLIGHT_VIDEO.run_pipeline(
        source,
        output_dir,
        HIGHLIGHT_VIDEO.PipelineConfig(),
    )

    assert result == cut_master
    assert not (output_dir / "recording.highlighted.mp4").exists()
    manifest = json.loads(
        (output_dir / "highlight_plan.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "fallback"
    assert "render_failed" in manifest["fallback_reason"]


def test_render_cut_master_retries_empty_timeline_without_margin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    calls = []

    def fake_run(command, *, cwd=None):
        calls.append(command)
        if len(calls) == 1:
            error = subprocess.CalledProcessError(1, command)
            error.stdout = "Timeline is empty"
            error.stderr = ""
            raise error
        output = Path(command[command.index("-o") + 1])
        output.write_bytes(b"cut")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(HIGHLIGHT_VIDEO, "_run", fake_run)

    result = HIGHLIGHT_VIDEO.render_cut_master(source, tmp_path / "output")

    assert result.read_bytes() == b"cut"
    assert calls[0][calls[0].index("--edit") + 1] == "audio:threshold=1%"
    assert calls[0][calls[0].index("--margin") + 1] == "0.5sec"
    assert calls[1][calls[1].index("--edit") + 1] == "none"
    assert "--margin" not in calls[1]


def test_custom_transcript_command_expands_placeholders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "cut master.mp4"
    source.write_bytes(b"cut")
    output_dir = tmp_path / "transcript"
    calls = []

    def fake_run(command, *, cwd=None):
        calls.append((command, cwd))
        (output_dir / "cut master.json").write_text(
            '{"segments": []}', encoding="utf-8"
        )
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(HIGHLIGHT_VIDEO, "_run", fake_run)

    result = HIGHLIGHT_VIDEO.transcribe_cut_master(
        source,
        output_dir,
        ("wrapper", "{input}", "{output_dir}", "{stem}"),
    )

    assert result == output_dir / "cut master.json"
    assert calls[0][0] == [
        "wrapper",
        str(source),
        str(output_dir),
        "cut master",
    ]


def test_probe_video_reads_video_stream(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(HIGHLIGHT_VIDEO.shutil, "which", lambda _name: "ffprobe")
    monkeypatch.setattr(
        HIGHLIGHT_VIDEO,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=json.dumps(
                {
                    "format": {"duration": "12.5"},
                    "streams": [
                        {"codec_type": "audio"},
                        {"codec_type": "video", "width": 1280, "height": 720},
                    ],
                }
            )
        ),
    )

    assert HIGHLIGHT_VIDEO.probe_video(
        tmp_path / "video.mp4"
    ) == HIGHLIGHT_VIDEO.VideoInfo(
        12.5,
        1280,
        720,
    )


def test_load_config_and_latest_recording(tmp_path: Path) -> None:
    old = tmp_path / "old.mkv"
    old.write_bytes(b"old")
    newest = tmp_path / "new.mp4"
    newest.write_bytes(b"new")
    generated = tmp_path / "new.highlighted.mp4"
    generated.write_bytes(b"generated")
    os.utime(old, (1, 1))
    os.utime(newest, (2, 2))
    os.utime(generated, (3, 3))
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "working_dirs": [str(tmp_path)],
                "opening_highlight": {
                    "maximum_highlights": 2,
                    "manual_title": "title",
                    "transcript_command": ["wrapper", "{input}"],
                },
            }
        ),
        encoding="utf-8",
    )

    paths, output, config = HIGHLIGHT_VIDEO.load_config(config_path)

    assert paths == [tmp_path]
    assert output is None
    assert config.maximum_highlights == 2
    assert config.transcript_command == ("wrapper", "{input}")
    assert HIGHLIGHT_VIDEO.latest_recording(paths) == newest


def test_main_uses_explicit_input_and_output(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    output_dir = tmp_path / "output"
    expected = output_dir / "final.mp4"
    calls = []

    def fake_pipeline(actual_source, actual_output, config):
        calls.append((actual_source, actual_output, config))
        return expected

    monkeypatch.setattr(HIGHLIGHT_VIDEO, "run_pipeline", fake_pipeline)

    result = HIGHLIGHT_VIDEO.main([str(source), "--output-dir", str(output_dir)])

    assert result == 0
    assert calls[0][0] == source
    assert calls[0][1] == output_dir

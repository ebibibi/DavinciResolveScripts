#!/usr/bin/env python3
"""Create a highlight-first long-form video without the Resolve API."""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from highlight_plan import (  # noqa: E402
    Highlight,
    HighlightPlan,
    _limit_total_duration,
    ai_plan_schema,
    build_local_plan,
    build_manual_plan,
    clean_text,
    desired_highlight_count,
    parse_ai_plan,
    shorten_text,
)
from progress import ProgressReporter, format_clock  # noqa: E402

SCHEMA_VERSION = 1
MAXIMUM_CAPTURED_LINES = 400

__all__ = [
    "Highlight",
    "HighlightPlan",
    "PipelineConfig",
    "VideoInfo",
    "ai_plan_schema",
    "build_ai_plan",
    "build_local_plan",
    "build_manual_plan",
    "clean_text",
    "desired_highlight_count",
    "main",
    "parse_ai_plan",
    "run_pipeline",
    "shorten_text",
]


@dataclass(frozen=True)
class VideoInfo:
    """Video properties required by the renderer."""

    duration: float
    width: int
    height: int


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for deterministic highlight-first rendering."""

    maximum_highlights: int = 3
    maximum_total_highlight_seconds: float = 24.0
    maximum_segment_seconds: float = 8.0
    padding_seconds: float = 0.5
    minimum_gap_seconds: float = 30.0
    opening_title_seconds: float = 4.0
    font_name: str = "Noto Sans CJK JP"
    font_size: int = 96
    manual_title: str = ""
    manual_highlights: tuple[dict[str, float], ...] = ()
    transcript_command: tuple[str, ...] = ()


def build_ai_plan(
    segments: list[dict[str, Any]],
    *,
    video_duration: float,
    config: PipelineConfig,
) -> HighlightPlan | None:
    """Ask Claude for a grounded takeaway and segment indexes."""
    claude = shutil.which("claude")
    if not claude:
        return None
    count = desired_highlight_count(video_duration, maximum=config.maximum_highlights)
    candidates = [
        {
            "segment_index": index,
            "start": round(float(item.get("start", 0)), 2),
            "end": round(float(item.get("end", 0)), 2),
            "text": clean_text(item.get("text", "")),
        }
        for index, item in enumerate(segments)
        if clean_text(item.get("text", ""))
    ][:300]
    prompt = (
        "You are editing a Japanese long-form YouTube video. Select the strongest "
        f"{count} highlight segments to COPY to the opening. Prefer concrete results, "
        "surprising demonstrations, conclusions, and claims that make viewers want "
        "the context. Write one Japanese takeaway title (48 characters or fewer) that "
        "states what the whole video ultimately communicates. Use only the supplied "
        "segment indexes and never invent content.\n\n"
        + json.dumps(candidates, ensure_ascii=False)
    )
    command = [
        claude,
        "--print",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(ai_plan_schema(), ensure_ascii=False),
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
    ]
    try:
        result = subprocess.run(
            command,
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=True,
        )
        plan = parse_ai_plan(
            result.stdout,
            segments,
            desired_count=count,
            padding_seconds=config.padding_seconds,
            maximum_segment_seconds=config.maximum_segment_seconds,
        )
        return plan if plan.title and plan.highlights else None
    except (subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return None


def _stream_process(
    command: Sequence[str],
    *,
    cwd: Path | None,
    reporter: ProgressReporter,
) -> subprocess.CompletedProcess[str]:
    """Run a child process while echoing its output as it arrives.

    Text mode translates the carriage returns that video tools use to redraw
    their progress bars, so every bar update reaches the reporter as a line.
    """
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None:
        process.kill()
        raise RuntimeError(f"could not read the output of {command[0]}")
    captured: deque[str] = deque(maxlen=MAXIMUM_CAPTURED_LINES)
    with process.stdout as pipe:
        for line in pipe:
            captured.append(line)
            reporter.child_output(line)
    returncode = process.wait()
    output = "".join(captured)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, list(command), output, "")
    return subprocess.CompletedProcess(list(command), returncode, output, "")


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    reporter: ProgressReporter | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command, streaming its output when a reporter is watching."""
    if reporter is not None:
        return _stream_process(command, cwd=cwd, reporter=reporter)
    return subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def render_cut_master(
    source: Path,
    output_dir: Path,
    reporter: ProgressReporter | None = None,
) -> Path:
    """Render the proven auto-editor silence cut as one high-quality MP4."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.cut_master.mp4"
    for edit_method in ("audio:threshold=3%", "none"):
        # Without --no-open, auto-editor launches the media player on the cut
        # master and the rest of the pipeline keeps running behind it.
        command = ["auto-editor", str(source), "--no-open"]
        if edit_method != "none":
            command.extend(["--margin", "0.2sec"])
        command.extend(
            [
                "--edit",
                edit_method,
                "--video-codec",
                "h264",
                "--audio-codec",
                "aac",
                "--video-bitrate",
                "40M",
                "--audio-bitrate",
                "320k",
                "-o",
                str(output),
            ]
        )
        try:
            _run(command, cwd=source.parent, reporter=reporter)
        except subprocess.CalledProcessError as error:
            diagnostic = f"{error.stdout}\n{error.stderr}"
            if edit_method != "none" and "Timeline is empty" in diagnostic:
                if reporter is not None:
                    reporter.warn("silence cut emptied the timeline, keeping every cut")
                continue
            raise
        if output.exists() and output.stat().st_size > 0:
            return output
        raise RuntimeError("auto-editor did not create a usable cut master")
    raise RuntimeError("auto-editor could not preserve the recording")


def transcribe_cut_master(
    source: Path,
    output_dir: Path,
    command_template: Sequence[str] = (),
    reporter: ProgressReporter | None = None,
) -> Path:
    """Transcribe the cut master so all timestamps match the final body."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if command_template:
        command = [
            token.format(
                input=str(source), output_dir=str(output_dir), stem=source.stem
            )
            for token in command_template
        ]
    else:
        whisper = shutil.which("whisper")
        if not whisper:
            raise FileNotFoundError("whisper command was not found")
        command = [
            whisper,
            str(source),
            "--language",
            "Japanese",
            "--output_format",
            "json",
            "--output_dir",
            str(output_dir),
            "--fp16",
            "False",
        ]
    _run(command, cwd=output_dir, reporter=reporter)
    expected = output_dir / f"{source.stem}.json"
    if expected.exists():
        return expected
    candidates = sorted(
        output_dir.glob("*.json"), key=lambda path: path.stat().st_mtime
    )
    if not candidates:
        raise RuntimeError("transcription command did not create JSON")
    return candidates[-1]


def probe_video(path: Path) -> VideoInfo:
    """Read duration and resolution with ffprobe."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise FileNotFoundError("ffprobe command was not found")
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ]
    )
    data = json.loads(result.stdout)
    video = next(
        stream
        for stream in data.get("streams", [])
        if stream.get("codec_type") == "video"
    )
    return VideoInfo(
        duration=float(data["format"]["duration"]),
        width=int(video["width"]),
        height=int(video["height"]),
    )


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def _escape_ass_text(value: str) -> str:
    return (
        clean_text(value).replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    )


def write_opening_ass(
    output: Path,
    *,
    title: str,
    display_seconds: float,
    resolution: tuple[int, int],
    font_name: str,
    font_size: int,
) -> None:
    """Write a prominent centered takeaway shown only at the opening."""
    width, height = resolution
    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Takeaway,{font_name},{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,3,7,2,5,120,120,90,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:00.00,{_ass_time(display_seconds)},Takeaway,,0,0,0,,{{\\fad(120,300)}}{_escape_ass_text(title)}
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8-sig")


def _escape_filter_filename(name: str) -> str:
    return (
        name.replace("\\", r"\\")
        .replace(" ", r"\ ")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )


def build_ffmpeg_command(
    source: Path,
    subtitle: Path,
    output: Path,
    plan: HighlightPlan,
) -> list[str]:
    """Build H1[,H2...] + complete body with a large opening title."""
    filters: list[str] = []
    concat_inputs: list[str] = []
    for index, highlight in enumerate(plan.highlights):
        filters.append(
            f"[0:v]trim=start={highlight.start:.3f}:end={highlight.end:.3f},"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        filters.append(
            f"[0:a]atrim=start={highlight.start:.3f}:end={highlight.end:.3f},"
            f"asetpts=PTS-STARTPTS[a{index}]"
        )
        concat_inputs.append(f"[v{index}][a{index}]")
    filters.extend(
        ["[0:v]setpts=PTS-STARTPTS[vmain]", "[0:a]asetpts=PTS-STARTPTS[amain]"]
    )
    concat_inputs.append("[vmain][amain]")
    filters.append(
        "".join(concat_inputs)
        + f"concat=n={len(plan.highlights) + 1}:v=1:a=1[basev][outa]"
    )
    filters.append(f"[basev]ass={_escape_filter_filename(subtitle.name)}[outv]")
    return [
        "ffmpeg",
        "-y",
        # Drop the build banner but keep -stats, so the console shows the
        # encoding position instead of pages of library versions.
        "-hide_banner",
        "-loglevel",
        "warning",
        "-stats",
        "-i",
        str(source),
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "16",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-movflags",
        "+faststart",
        str(output),
    ]


def render_highlight_video(
    source: Path,
    subtitle: Path,
    output: Path,
    plan: HighlightPlan,
    reporter: ProgressReporter | None = None,
) -> Path:
    """Render the final highlight-first MP4 and reject partial output."""
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg command was not found")
    if output.exists():
        output.unlink()
    _run(
        build_ffmpeg_command(source, subtitle, output, plan),
        cwd=subtitle.parent,
        reporter=reporter,
    )
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("ffmpeg did not create a usable highlighted video")
    return output


def _read_segments(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments", []) if isinstance(data, dict) else []
    return [item for item in segments if isinstance(item, dict)]


def _write_manifest(
    output_dir: Path,
    *,
    source: Path,
    cut_master: Path,
    transcript: Path | None,
    plan: HighlightPlan,
    output: Path,
    status: str,
    fallback_reason: str = "",
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source": str(source),
        "cut_master": str(cut_master),
        "transcript": str(transcript) if transcript else "",
        "takeaway": plan.title,
        "highlights": [asdict(item) for item in plan.highlights],
        "highlight_reel_seconds": sum(
            item.end - item.start for item in plan.highlights
        ),
        "sequence": [f"highlight_{index + 1}" for index in range(len(plan.highlights))]
        + ["complete_cut_master"],
        "output": str(output),
        "fallback_reason": fallback_reason,
    }
    (output_dir / "highlight_plan.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _pipeline_steps(config: PipelineConfig) -> tuple[str, ...]:
    """Name every stage so the console can show real progress."""
    common = ("Removing silence (auto-editor)", "Reading video properties (ffprobe)")
    tail = ("Rendering the highlight video (ffmpeg)",)
    if config.manual_title and config.manual_highlights:
        return common + ("Applying the manual highlight ranges",) + tail
    return (
        common
        + ("Transcribing the cut master (whisper)", "Choosing highlights (claude)")
        + tail
    )


def _select_plan(
    segments: list[dict[str, Any]],
    *,
    video_duration: float,
    config: PipelineConfig,
    reporter: ProgressReporter,
) -> HighlightPlan:
    """Prefer the grounded Claude plan and fall back to the local ranking."""
    plan = build_ai_plan(segments, video_duration=video_duration, config=config)
    if plan is not None:
        return plan
    reporter.warn("claude returned no usable plan, ranking the segments locally")
    return build_local_plan(
        segments,
        video_duration=video_duration,
        maximum_highlights=config.maximum_highlights,
        padding_seconds=config.padding_seconds,
        maximum_segment_seconds=config.maximum_segment_seconds,
        minimum_gap_seconds=config.minimum_gap_seconds,
    )


def run_pipeline(
    source: Path,
    output_dir: Path,
    config: PipelineConfig,
    reporter: ProgressReporter | None = None,
) -> Path:
    """Run cut -> transcribe -> select -> prepend -> title rendering."""
    reporter = reporter if reporter is not None else ProgressReporter(enabled=False)
    steps = _pipeline_steps(config)
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    reporter.start_stage(steps[0], step=1, steps=len(steps))
    cut_master = render_cut_master(source, output_dir, reporter)
    reporter.finish_stage(cut_master.name)

    reporter.start_stage(steps[1], step=2, steps=len(steps))
    video = probe_video(cut_master)
    reporter.finish_stage(
        f"{video.width}x{video.height}, {format_clock(video.duration)} long"
    )
    transcript: Path | None = None
    plan: HighlightPlan

    if config.manual_title and config.manual_highlights:
        reporter.start_stage(steps[2], step=3, steps=len(steps))
        plan = build_manual_plan(
            title=config.manual_title,
            highlights=config.manual_highlights,
            video_duration=video.duration,
            maximum_highlights=config.maximum_highlights,
            maximum_total_seconds=config.maximum_total_highlight_seconds,
        )
        reporter.finish_stage(f"{len(plan.highlights)} highlights")
    else:
        reporter.start_stage(
            steps[2], step=3, steps=len(steps), total_seconds=video.duration
        )
        try:
            transcript = transcribe_cut_master(
                cut_master,
                output_dir,
                config.transcript_command,
                reporter,
            )
            segments = _read_segments(transcript)
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as error:
            reporter.finish_stage("failed")
            reporter.warn(f"transcription failed, keeping the cut master: {error}")
            fallback = HighlightPlan("", ())
            _write_manifest(
                output_dir,
                source=source,
                cut_master=cut_master,
                transcript=None,
                plan=fallback,
                output=cut_master,
                status="fallback",
                fallback_reason=f"transcription_failed: {error}",
            )
            return cut_master
        reporter.finish_stage(f"{len(segments)} segments")

        reporter.start_stage(steps[3], step=4, steps=len(steps))
        plan = _select_plan(
            segments,
            video_duration=video.duration,
            config=config,
            reporter=reporter,
        )
        reporter.finish_stage(f"{len(plan.highlights)} highlights, title: {plan.title}")
    plan = _limit_total_duration(plan, config.maximum_total_highlight_seconds)
    if not plan.title or not plan.highlights:
        reporter.warn("no usable highlight plan, keeping the cut master")
        _write_manifest(
            output_dir,
            source=source,
            cut_master=cut_master,
            transcript=transcript,
            plan=plan,
            output=cut_master,
            status="fallback",
            fallback_reason="no_usable_highlight_plan",
        )
        return cut_master

    subtitle = output_dir / "opening_title.ass"
    display_seconds = min(
        config.opening_title_seconds,
        sum(item.end - item.start for item in plan.highlights),
    )
    write_opening_ass(
        subtitle,
        title=plan.title,
        display_seconds=display_seconds,
        resolution=(video.width, video.height),
        font_name=config.font_name,
        font_size=config.font_size,
    )
    output = output_dir / f"{source.stem}.highlighted.mp4"
    highlight_seconds = sum(item.end - item.start for item in plan.highlights)
    reporter.start_stage(
        steps[-1],
        step=len(steps),
        steps=len(steps),
        total_seconds=video.duration + highlight_seconds,
    )
    try:
        rendered = render_highlight_video(cut_master, subtitle, output, plan, reporter)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        reporter.finish_stage("failed")
        reporter.warn(f"rendering failed, keeping the cut master: {error}")
        if output.exists():
            output.unlink()
        _write_manifest(
            output_dir,
            source=source,
            cut_master=cut_master,
            transcript=transcript,
            plan=plan,
            output=cut_master,
            status="fallback",
            fallback_reason=f"render_failed: {error}",
        )
        return cut_master
    reporter.finish_stage(rendered.name)
    _write_manifest(
        output_dir,
        source=source,
        cut_master=cut_master,
        transcript=transcript,
        plan=plan,
        output=rendered,
        status="success",
    )
    return rendered


def load_config(path: Path | None) -> tuple[list[Path], Path | None, PipelineConfig]:
    """Load non-secret local paths and highlight settings."""
    data: dict[str, Any] = {}
    if path and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    section = data.get("opening_highlight", {})
    if not isinstance(section, dict):
        section = {}
    manual = section.get("manual_highlights", [])
    transcript_command = section.get("transcript_command", [])
    if isinstance(transcript_command, str):
        transcript_command = shlex.split(transcript_command, posix=os.name != "nt")
    config = PipelineConfig(
        maximum_highlights=int(section.get("maximum_highlights", 3)),
        maximum_total_highlight_seconds=float(section.get("maximum_total_seconds", 24)),
        maximum_segment_seconds=float(section.get("maximum_segment_seconds", 8)),
        padding_seconds=float(section.get("padding_seconds", 0.5)),
        minimum_gap_seconds=float(section.get("minimum_gap_seconds", 30)),
        opening_title_seconds=float(section.get("title_seconds", 4)),
        font_name=str(section.get("font_name", "Noto Sans CJK JP")),
        font_size=int(section.get("font_size", 96)),
        manual_title=str(section.get("manual_title", "")),
        manual_highlights=tuple(item for item in manual if isinstance(item, dict)),
        transcript_command=tuple(str(item) for item in transcript_command),
    )
    working_dirs = [Path(item) for item in data.get("working_dirs", [])]
    output_value = section.get("output_dir")
    return working_dirs, Path(output_value) if output_value else None, config


def latest_recording(paths: Sequence[Path]) -> Path:
    """Find the latest recording without considering generated outputs."""
    candidates = [
        item
        for directory in paths
        if directory.is_dir()
        for pattern in ("*.mkv", "*.mp4")
        for item in directory.glob(pattern)
        if ".cut_master" not in item.name and ".highlighted" not in item.name
    ]
    if not candidates:
        raise FileNotFoundError("no MKV or MP4 recording was found")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _use_replacement_characters() -> None:
    """Stop a legacy console encoding from killing the run mid-render."""
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="hide the stage progress report and print only the result path",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=20.0,
        help="how long a silent step may run before it reports it is alive",
    )
    args = parser.parse_args(argv)
    _use_replacement_characters()
    script_dir = Path(__file__).resolve().parent
    config_path = args.config
    if config_path is None:
        config_path = next(
            (
                candidate
                for candidate in (
                    script_dir / "config.local.json",
                    script_dir / "config.json",
                )
                if candidate.exists()
            ),
            None,
        )
    working_dirs, configured_output, config = load_config(config_path)
    source = args.input or latest_recording(working_dirs)
    output_dir = (
        args.output_dir
        or configured_output
        or source.parent / "_highlight_output" / source.stem
    )
    reporter = ProgressReporter(
        enabled=not args.quiet,
        heartbeat_seconds=args.heartbeat_seconds,
    )
    if not args.quiet:
        print(f"Source: {source}")
        print(f"Output directory: {output_dir}")
    result = run_pipeline(source, output_dir, config, reporter)
    reporter.summary()
    print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Highlight pipeline failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

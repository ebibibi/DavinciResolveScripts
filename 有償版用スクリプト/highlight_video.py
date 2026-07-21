#!/usr/bin/env python3
"""Create a highlight-first long-form video without the Resolve API."""

import argparse
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = 1
KEY_PHRASES = (
    "結論",
    "重要",
    "ポイント",
    "つまり",
    "要するに",
    "実際に",
    "理由",
    "意外",
    "できます",
    "解決",
)


@dataclass(frozen=True)
class Highlight:
    """A copied range on the cut-master timeline."""

    start: float
    end: float
    text: str = ""


@dataclass(frozen=True)
class HighlightPlan:
    """The takeaway title and ordered opening highlight ranges."""

    title: str
    highlights: tuple[Highlight, ...]


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


def clean_text(value: Any) -> str:
    """Collapse whitespace and remove control characters."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def shorten_text(value: Any, maximum: int = 48) -> str:
    """Return a display-safe single-line title."""
    text = clean_text(value).strip("「」『』、。,.!? ")
    if len(text) <= maximum:
        return text
    return text[: max(1, maximum - 1)].rstrip() + "…"


def desired_highlight_count(duration: float, *, maximum: int) -> int:
    """Use more opening highlights for longer videos."""
    maximum = max(1, int(maximum))
    if duration >= 45 * 60:
        return min(3, maximum)
    if duration >= 20 * 60:
        return min(2, maximum)
    return 1


def _bounded_highlight(
    segment: dict[str, Any],
    *,
    duration: float,
    padding_seconds: float,
    maximum_segment_seconds: float,
) -> Highlight | None:
    try:
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        return None
    start = max(0.0, start - max(0.0, padding_seconds))
    end = min(duration, end + max(0.0, padding_seconds))
    end = min(end, start + max(1.0, maximum_segment_seconds))
    if end - start < 0.5:
        return None
    return Highlight(start, end, clean_text(segment.get("text", "")))


def _extract_structured_output(output: str) -> dict[str, Any]:
    payload = json.loads(output)
    data = payload.get("structured_output", payload)
    if isinstance(data, dict) and "highlight_segment_indexes" in data:
        return data
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, str):
        nested = json.loads(result)
        if isinstance(nested, dict):
            return nested
    raise ValueError("AI output does not contain a highlight plan")


def parse_ai_plan(
    output: str,
    segments: list[dict[str, Any]],
    *,
    desired_count: int,
    padding_seconds: float,
    maximum_segment_seconds: float,
) -> HighlightPlan:
    """Validate a grounded Claude plan against Whisper segments."""
    data = _extract_structured_output(output)
    duration = max((float(item.get("end", 0)) for item in segments), default=0.0)
    selected: list[Highlight] = []
    seen: set[int] = set()
    indexes = data.get("highlight_segment_indexes", [])
    for raw_index in indexes if isinstance(indexes, list) else []:
        if not isinstance(raw_index, int) or raw_index in seen:
            continue
        if not 0 <= raw_index < len(segments):
            continue
        seen.add(raw_index)
        item = _bounded_highlight(
            segments[raw_index],
            duration=duration,
            padding_seconds=padding_seconds,
            maximum_segment_seconds=maximum_segment_seconds,
        )
        if item is not None:
            selected.append(item)
        if len(selected) >= max(1, desired_count):
            break
    return HighlightPlan(
        title=shorten_text(data.get("main_takeaway", "")),
        highlights=tuple(selected),
    )


def _segment_score(segment: dict[str, Any], index: int) -> tuple[float, int]:
    text = clean_text(segment.get("text", ""))
    score = sum(5 for phrase in KEY_PHRASES if phrase in text)
    score += 3 if re.search(r"\d", text) else 0
    score += 2 if 12 <= len(text) <= 55 else 0
    score += min(3, len(re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", text)))
    return float(score), -index


def build_local_plan(
    segments: list[dict[str, Any]],
    *,
    video_duration: float,
    maximum_highlights: int,
    padding_seconds: float,
    maximum_segment_seconds: float,
    minimum_gap_seconds: float,
) -> HighlightPlan:
    """Select deterministic highlights when Claude is unavailable."""
    count = desired_highlight_count(video_duration, maximum=maximum_highlights)
    ranked = sorted(
        enumerate(segments),
        key=lambda item: _segment_score(item[1], item[0]),
        reverse=True,
    )
    selected: list[Highlight] = []
    for _, segment in ranked:
        candidate = _bounded_highlight(
            segment,
            duration=video_duration,
            padding_seconds=padding_seconds,
            maximum_segment_seconds=maximum_segment_seconds,
        )
        if candidate is None or not candidate.text:
            continue
        if any(
            abs(candidate.start - existing.start) < max(0.0, minimum_gap_seconds)
            for existing in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= count:
            break
    selected.sort(key=lambda item: item.start)
    strongest = max(
        selected, key=lambda item: _segment_score({"text": item.text}, 0), default=None
    )
    return HighlightPlan(
        title=shorten_text(strongest.text if strongest else ""),
        highlights=tuple(selected),
    )


def build_manual_plan(
    *,
    title: str,
    highlights: Sequence[dict[str, Any]],
    video_duration: float,
    maximum_highlights: int,
    maximum_total_seconds: float,
) -> HighlightPlan:
    """Build a validated deterministic plan from manual ranges."""
    selected: list[Highlight] = []
    total = 0.0
    for raw in highlights:
        item = _bounded_highlight(
            raw,
            duration=video_duration,
            padding_seconds=0.0,
            maximum_segment_seconds=max(1.0, maximum_total_seconds),
        )
        if item is None:
            continue
        remaining = maximum_total_seconds - total
        if remaining < 0.5:
            break
        if item.end - item.start > remaining:
            item = Highlight(item.start, item.start + remaining, item.text)
        if any(item.start < old.end and old.start < item.end for old in selected):
            continue
        selected.append(item)
        total += item.end - item.start
        if len(selected) >= max(1, maximum_highlights):
            break
    return HighlightPlan(shorten_text(title), tuple(selected))


def ai_plan_schema() -> dict[str, Any]:
    """Return the strict Claude structured-output schema."""
    return {
        "type": "object",
        "properties": {
            "main_takeaway": {"type": "string"},
            "highlight_segment_indexes": {
                "type": "array",
                "items": {"type": "integer"},
            },
        },
        "required": ["main_takeaway", "highlight_segment_indexes"],
        "additionalProperties": False,
    }


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


def _run(
    command: Sequence[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
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


def render_cut_master(source: Path, output_dir: Path) -> Path:
    """Render the proven auto-editor silence cut as one high-quality MP4."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.cut_master.mp4"
    for edit_method in ("audio:threshold=3%", "none"):
        command = ["auto-editor", str(source)]
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
            _run(command, cwd=source.parent)
        except subprocess.CalledProcessError as error:
            diagnostic = f"{error.stdout}\n{error.stderr}"
            if edit_method != "none" and "Timeline is empty" in diagnostic:
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
    _run(command, cwd=output_dir)
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
) -> Path:
    """Render the final highlight-first MP4 and reject partial output."""
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg command was not found")
    if output.exists():
        output.unlink()
    _run(build_ffmpeg_command(source, subtitle, output, plan), cwd=subtitle.parent)
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("ffmpeg did not create a usable highlighted video")
    return output


def _read_segments(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments", []) if isinstance(data, dict) else []
    return [item for item in segments if isinstance(item, dict)]


def _limit_total_duration(plan: HighlightPlan, maximum: float) -> HighlightPlan:
    selected: list[Highlight] = []
    remaining = max(1.0, maximum)
    for item in plan.highlights:
        duration = min(item.end - item.start, remaining)
        if duration < 0.5:
            break
        selected.append(Highlight(item.start, item.start + duration, item.text))
        remaining -= duration
    return HighlightPlan(plan.title, tuple(selected))


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


def run_pipeline(source: Path, output_dir: Path, config: PipelineConfig) -> Path:
    """Run cut -> transcribe -> select -> prepend -> title rendering."""
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cut_master = render_cut_master(source, output_dir)
    video = probe_video(cut_master)
    transcript: Path | None = None
    plan: HighlightPlan

    if config.manual_title and config.manual_highlights:
        plan = build_manual_plan(
            title=config.manual_title,
            highlights=config.manual_highlights,
            video_duration=video.duration,
            maximum_highlights=config.maximum_highlights,
            maximum_total_seconds=config.maximum_total_highlight_seconds,
        )
    else:
        try:
            transcript = transcribe_cut_master(
                cut_master,
                output_dir,
                config.transcript_command,
            )
            segments = _read_segments(transcript)
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as error:
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
        plan = build_ai_plan(
            segments, video_duration=video.duration, config=config
        ) or build_local_plan(
            segments,
            video_duration=video.duration,
            maximum_highlights=config.maximum_highlights,
            padding_seconds=config.padding_seconds,
            maximum_segment_seconds=config.maximum_segment_seconds,
            minimum_gap_seconds=config.minimum_gap_seconds,
        )
    plan = _limit_total_duration(plan, config.maximum_total_highlight_seconds)
    if not plan.title or not plan.highlights:
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
    try:
        rendered = render_highlight_video(cut_master, subtitle, output, plan)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
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
    result = run_pipeline(source, output_dir, config)
    print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Highlight pipeline failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

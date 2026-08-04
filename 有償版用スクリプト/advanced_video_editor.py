#!/usr/bin/env python3
"""Edit a long-form video end to end with FFmpeg only - no Resolve, no NLE.

The pipeline is deliberately one direction: the recording becomes a cut master,
the cut master becomes a transcript, the transcript becomes an edit decision
list, and the edit decision list becomes exactly one FFmpeg render.

    silence cut -> transcript -> AI edit plan -> ASS + SFX -> single render

Everything an editor would do by hand on a timeline is a value in
`edit_plan.json`: which moments open the video, what the chapter cards say,
which phrases get an emphasis telop, which words are burned as captions and
where the sound effects land. Reviewing a run means reading that file; fixing a
run means editing it and rendering again.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ass_render import build_ass  # noqa: E402
from edit_plan import (  # noqa: E402
    Chapter,
    EditPlan,
    SoundCue,
    Telop,
    build_captions,
    build_local_chapters,
    edit_plan_schema,
    parse_editorial_output,
    parse_structured_json,
)
from highlight_plan import (  # noqa: E402
    HighlightPlan,
    _limit_total_duration,
    build_local_plan,
    build_manual_plan,
    clean_text,
    desired_highlight_count,
    parse_ai_plan,
)
from highlight_video import (  # noqa: E402
    PipelineConfig,
    VideoInfo,
    _read_segments,
    _run,
    latest_recording,
    load_config,
    probe_video,
    render_cut_master,
    transcribe_cut_master,
)
from progress import ProgressReporter, format_clock  # noqa: E402
from sound_design import build_sfx_command, build_sound_cues  # noqa: E402
from timeline import BODY, Slice, build_timeline, total_duration  # noqa: E402

SCHEMA_VERSION = 2
MAXIMUM_CANDIDATE_SEGMENTS = 700
CLAUDE_TIMEOUT_SECONDS = 300

__all__ = [
    "AdvancedConfig",
    "build_edit_plan",
    "build_render_command",
    "load_advanced_config",
    "main",
    "run_pipeline",
]


@dataclass(frozen=True)
class AdvancedConfig:
    """Which editorial layers are switched on, and how loud each one is."""

    captions: bool = True
    telops: bool = True
    chapters: bool = True
    sound_effects: bool = True
    maximum_telops: int = 24
    maximum_chapters: int = 6
    chapter_seconds: float = 3.5
    minimum_chapter_gap_seconds: float = 120.0
    telop_minimum_seconds: float = 1.2
    telop_maximum_seconds: float = 4.0
    caption_maximum_characters: int = 40
    video_crf: int = 18
    video_preset: str = "medium"


def load_advanced_config(
    path: Path | None,
) -> tuple[list[Path], Path | None, PipelineConfig, AdvancedConfig]:
    """Read the shared highlight settings plus the advanced-only section."""
    working_dirs, output_dir, config = load_config(path)
    data: dict[str, Any] = {}
    if path and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    section = data.get("advanced_edit", {})
    if not isinstance(section, dict):
        section = {}
    advanced = AdvancedConfig(
        captions=bool(section.get("captions", True)),
        telops=bool(section.get("telops", True)),
        chapters=bool(section.get("chapters", True)),
        sound_effects=bool(section.get("sound_effects", True)),
        maximum_telops=int(section.get("maximum_telops", 24)),
        maximum_chapters=int(section.get("maximum_chapters", 6)),
        chapter_seconds=float(section.get("chapter_seconds", 3.5)),
        minimum_chapter_gap_seconds=float(
            section.get("minimum_chapter_gap_seconds", 120)
        ),
        telop_minimum_seconds=float(section.get("telop_minimum_seconds", 1.2)),
        telop_maximum_seconds=float(section.get("telop_maximum_seconds", 4.0)),
        caption_maximum_characters=int(section.get("caption_maximum_characters", 40)),
        video_crf=int(section.get("video_crf", 18)),
        video_preset=str(section.get("video_preset", "medium")),
    )
    return working_dirs, output_dir, config, advanced


def _candidate_segments(
    segments: Sequence[dict[str, Any]], limit: int = MAXIMUM_CANDIDATE_SEGMENTS
) -> list[dict[str, Any]]:
    """Send Claude a bounded, evenly spread view that keeps real indexes.

    A one-hour recording produces far more segments than belong in a prompt.
    Dropping the tail would blind the model to the whole second half, so the
    list is thinned by stride instead - and every entry keeps the index the
    renderer will use, which is what makes the answer verifiable.
    """
    usable = [
        {
            "segment_index": index,
            "start": round(float(item.get("start", 0)), 2),
            "end": round(float(item.get("end", 0)), 2),
            "text": clean_text(item.get("text", "")),
        }
        for index, item in enumerate(segments)
        if clean_text(item.get("text", ""))
    ]
    if len(usable) <= limit:
        return usable
    stride = len(usable) / limit
    return [usable[int(position * stride)] for position in range(limit)]


def _editorial_prompt(
    candidates: Sequence[dict[str, Any]],
    *,
    highlight_count: int,
    chapter_count: int,
    telop_count: int,
) -> str:
    return (
        "You are the editor of a Japanese long-form YouTube video. The JSON "
        "below is the transcript of the already silence-cut master. Produce an "
        "edit plan in Japanese.\n"
        f"1. main_takeaway: one line, 48 characters or fewer, stating what the "
        "whole video ultimately tells the viewer.\n"
        f"2. highlight_segment_indexes: the {highlight_count} strongest moments "
        "to COPY to the opening. Prefer concrete results, surprising "
        "demonstrations and conclusions that make a viewer want the context.\n"
        f"3. chapters: up to {chapter_count} topic changes, spread across the "
        "whole video. segment_index marks where the new topic starts and title "
        "is 22 characters or fewer.\n"
        f"4. telops: up to {telop_count} emphasis captions, each 26 characters "
        "or fewer, condensing what is being said in that exact segment.\n"
        "Use only the supplied segment indexes. Never invent content, and never "
        "write a telop that contradicts the words in its segment.\n\n"
        + json.dumps(list(candidates), ensure_ascii=False)
    )


def request_editorial_plan(
    segments: Sequence[dict[str, Any]],
    *,
    video_duration: float,
    config: PipelineConfig,
    advanced: AdvancedConfig,
    reporter: ProgressReporter | None = None,
) -> dict[str, Any] | None:
    """Ask Claude once for the whole edit plan, or return None."""
    import shutil

    claude = shutil.which("claude")
    if not claude:
        return None
    highlight_count = desired_highlight_count(
        video_duration, maximum=config.maximum_highlights
    )
    prompt = _editorial_prompt(
        _candidate_segments(segments),
        highlight_count=highlight_count,
        chapter_count=advanced.maximum_chapters,
        telop_count=advanced.maximum_telops,
    )
    command = [
        claude,
        "--print",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(
            edit_plan_schema(advanced.maximum_chapters, advanced.maximum_telops),
            ensure_ascii=False,
        ),
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
            timeout=CLAUDE_TIMEOUT_SECONDS,
            check=True,
        )
        return parse_structured_json(result.stdout)
    except (subprocess.SubprocessError, ValueError, json.JSONDecodeError) as error:
        if reporter is not None:
            reporter.warn(f"claude did not return a usable edit plan: {error}")
        return None


def build_edit_plan(
    segments: Sequence[dict[str, Any]],
    *,
    video_duration: float,
    config: PipelineConfig,
    advanced: AdvancedConfig,
    ai_data: dict[str, Any] | None,
) -> EditPlan:
    """Combine the AI answer, the deterministic fallbacks and the transcript."""
    notes: list[str] = []
    highlight_plan: HighlightPlan | None = None
    chapters: tuple[Chapter, ...] = ()
    telops: tuple[Telop, ...] = ()

    if config.manual_title and config.manual_highlights:
        highlight_plan = build_manual_plan(
            title=config.manual_title,
            highlights=config.manual_highlights,
            video_duration=video_duration,
            maximum_highlights=config.maximum_highlights,
            maximum_total_seconds=config.maximum_total_highlight_seconds,
        )
        notes.append("manual_highlights")
    elif ai_data is not None:
        try:
            highlight_plan = parse_ai_plan(
                json.dumps(ai_data, ensure_ascii=False),
                list(segments),
                desired_count=desired_highlight_count(
                    video_duration, maximum=config.maximum_highlights
                ),
                padding_seconds=config.padding_seconds,
                maximum_segment_seconds=config.maximum_segment_seconds,
            )
        except (ValueError, json.JSONDecodeError):
            highlight_plan = None
        chapters, telops = parse_editorial_output(
            ai_data,
            segments,
            video_duration=video_duration,
            maximum_chapters=advanced.maximum_chapters,
            maximum_telops=advanced.maximum_telops,
            minimum_chapter_gap_seconds=advanced.minimum_chapter_gap_seconds,
            telop_minimum_seconds=advanced.telop_minimum_seconds,
            telop_maximum_seconds=advanced.telop_maximum_seconds,
        )
        notes.append("ai_edit_plan")

    if highlight_plan is None or not highlight_plan.highlights:
        highlight_plan = build_local_plan(
            list(segments),
            video_duration=video_duration,
            maximum_highlights=config.maximum_highlights,
            padding_seconds=config.padding_seconds,
            maximum_segment_seconds=config.maximum_segment_seconds,
            minimum_gap_seconds=config.minimum_gap_seconds,
        )
        notes.append("local_highlights")
    highlight_plan = _limit_total_duration(
        highlight_plan, config.maximum_total_highlight_seconds
    )

    if advanced.chapters and not chapters:
        chapters = build_local_chapters(
            segments,
            video_duration=video_duration,
            maximum_chapters=advanced.maximum_chapters,
        )
        if chapters:
            notes.append("local_chapters")
    if not advanced.chapters:
        chapters = ()
    if not advanced.telops:
        telops = ()
    captions = (
        build_captions(
            segments,
            video_duration=video_duration,
            maximum_characters=advanced.caption_maximum_characters,
        )
        if advanced.captions
        else ()
    )
    return EditPlan(
        title=highlight_plan.title,
        highlights=highlight_plan.highlights,
        chapters=chapters,
        telops=telops,
        captions=captions,
        notes=tuple(notes),
    )


def _escape_filter_filename(name: str) -> str:
    return (
        name.replace("\\", r"\\")
        .replace(" ", r"\ ")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )


def build_render_command(
    source: Path,
    subtitle: Path,
    output: Path,
    slices: Sequence[Slice],
    *,
    sfx: Path | None = None,
    crf: int = 18,
    preset: str = "medium",
) -> list[str]:
    """Build the single FFmpeg command that produces the finished video."""
    filters: list[str] = []
    concat_inputs: list[str] = []
    for index, item in enumerate(slices):
        if item.kind == BODY and item.source_start <= 0.0:
            # The body is the whole cut master by construction, so it is used
            # untrimmed: trimming to the probed duration would drop the last
            # frames whenever the container rounds it down.
            filters.append(f"[0:v]setpts=PTS-STARTPTS[v{index}]")
            filters.append(f"[0:a]asetpts=PTS-STARTPTS[a{index}]")
        else:
            filters.append(
                f"[0:v]trim=start={item.source_start:.3f}:end={item.source_end:.3f},"
                f"setpts=PTS-STARTPTS[v{index}]"
            )
            filters.append(
                f"[0:a]atrim=start={item.source_start:.3f}:end={item.source_end:.3f},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
        concat_inputs.append(f"[v{index}][a{index}]")
    filters.append(
        "".join(concat_inputs) + f"concat=n={len(slices)}:v=1:a=1[basev][basea]"
    )
    filters.append(f"[basev]ass={_escape_filter_filename(subtitle.name)}[outv]")
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", "-stats"]
    command.extend(["-i", str(source)])
    if sfx is not None:
        command.extend(["-i", str(sfx)])
        # normalize=0 keeps the narration at its original level; the default
        # would halve it the moment a single effect plays.
        # The limiter only catches the moment an effect lands on an already
        # loud word; without it that single frame clips.
        filters.append(
            "[basea][1:a]amix=inputs=2:normalize=0:duration=first:"
            "dropout_transition=0,alimiter=limit=0.95[outa]"
        )
    else:
        filters.append("[basea]anull[outa]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return command


def _write_manifest(
    output_dir: Path,
    *,
    source: Path,
    cut_master: Path,
    transcript: Path | None,
    plan: EditPlan,
    cues: Sequence[SoundCue],
    slices: Sequence[Slice],
    output: Path,
    status: str,
    fallback_reason: str = "",
) -> Path:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source": str(source),
        "cut_master": str(cut_master),
        "transcript": str(transcript) if transcript else "",
        "takeaway": plan.title,
        "notes": list(plan.notes),
        "highlights": [asdict(item) for item in plan.highlights],
        "chapters": [asdict(item) for item in plan.chapters],
        "telops": [asdict(item) for item in plan.telops],
        "caption_count": len(plan.captions),
        "sound_cues": [asdict(item) for item in cues],
        "timeline": [asdict(item) for item in slices],
        "final_duration_seconds": round(total_duration(slices), 2),
        "output": str(output),
        "fallback_reason": fallback_reason,
    }
    manifest = output_dir / "edit_plan.json"
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def _render_sfx(
    cues: Sequence[SoundCue], output_dir: Path, reporter: ProgressReporter
) -> Path | None:
    if not cues:
        return None
    target = output_dir / "sound_effects.wav"
    try:
        _run(build_sfx_command(cues, target))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        reporter.warn(f"sound effects were skipped: {error}")
        return None
    if not target.exists() or target.stat().st_size == 0:
        reporter.warn("sound effects produced no audio, continuing without them")
        return None
    return target


def _steps(advanced: AdvancedConfig) -> tuple[str, ...]:
    return (
        "Removing silence (auto-editor)",
        "Reading video properties (ffprobe)",
        "Transcribing the cut master (whisper)",
        "Planning the edit (claude)",
        "Building overlays and sound effects",
        "Rendering the finished video (ffmpeg)",
    )


def run_pipeline(
    source: Path,
    output_dir: Path,
    config: PipelineConfig,
    advanced: AdvancedConfig,
    reporter: ProgressReporter | None = None,
    *,
    dry_run: bool = False,
    cut_master_override: Path | None = None,
) -> Path:
    """Run cut -> transcribe -> plan -> overlay -> render, keeping every part."""
    reporter = reporter if reporter is not None else ProgressReporter(enabled=False)
    steps = _steps(advanced)
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    reporter.start_stage(steps[0], step=1, steps=len(steps))
    if cut_master_override is not None:
        cut_master = cut_master_override.resolve()
        reporter.finish_stage(f"reusing {cut_master.name}")
    else:
        cut_master = render_cut_master(source, output_dir, reporter)
        reporter.finish_stage(cut_master.name)

    reporter.start_stage(steps[1], step=2, steps=len(steps))
    video: VideoInfo = probe_video(cut_master)
    reporter.finish_stage(
        f"{video.width}x{video.height}, {format_clock(video.duration)} long"
    )

    transcript: Path | None = None
    segments: list[dict[str, Any]] = []
    reporter.start_stage(steps[2], step=3, steps=len(steps), total_seconds=video.duration)
    try:
        transcript = transcribe_cut_master(
            cut_master, output_dir, config.transcript_command, reporter
        )
        segments = _read_segments(transcript)
        reporter.finish_stage(f"{len(segments)} segments")
    except (OSError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        reporter.finish_stage("failed")
        reporter.warn(f"transcription failed, keeping the cut master: {error}")
        _write_manifest(
            output_dir,
            source=source,
            cut_master=cut_master,
            transcript=None,
            plan=EditPlan(""),
            cues=(),
            slices=(),
            output=cut_master,
            status="fallback",
            fallback_reason=f"transcription_failed: {error}",
        )
        return cut_master

    reporter.start_stage(steps[3], step=4, steps=len(steps))
    ai_data = request_editorial_plan(
        segments,
        video_duration=video.duration,
        config=config,
        advanced=advanced,
        reporter=reporter,
    )
    plan = build_edit_plan(
        segments,
        video_duration=video.duration,
        config=config,
        advanced=advanced,
        ai_data=ai_data,
    )
    reporter.finish_stage(
        f"{len(plan.highlights)} highlights, {len(plan.chapters)} chapters, "
        f"{len(plan.telops)} telops, {len(plan.captions)} captions"
    )

    reporter.start_stage(steps[4], step=5, steps=len(steps))
    slices = build_timeline(plan.highlights, video.duration)
    subtitle = output_dir / "overlays.ass"
    subtitle.write_text(
        build_ass(
            plan,
            slices,
            resolution=(video.width, video.height),
            font_name=config.font_name,
            takeaway_font_size=config.font_size,
            takeaway_seconds=min(
                config.opening_title_seconds,
                max(0.0, total_duration(slices)),
            ),
            chapter_seconds=advanced.chapter_seconds,
            body_duration=video.duration,
        ),
        encoding="utf-8-sig",
    )
    cues = (
        build_sound_cues(slices, plan.chapters) if advanced.sound_effects else ()
    )
    sfx = _render_sfx(cues, output_dir, reporter) if cues else None
    reporter.finish_stage(
        f"{subtitle.name}, {len(cues)} sound cues, "
        f"final length {format_clock(total_duration(slices))}"
    )

    output = output_dir / f"{source.stem}.edited.mp4"
    if dry_run:
        manifest = _write_manifest(
            output_dir,
            source=source,
            cut_master=cut_master,
            transcript=transcript,
            plan=plan,
            cues=cues,
            slices=slices,
            output=output,
            status="dry_run",
        )
        reporter.warn(f"dry run: nothing was rendered, review {manifest.name}")
        return manifest

    reporter.start_stage(
        steps[5],
        step=len(steps),
        steps=len(steps),
        total_seconds=total_duration(slices),
    )
    if output.exists():
        output.unlink()
    try:
        _run(
            build_render_command(
                cut_master,
                subtitle,
                output,
                slices,
                sfx=sfx,
                crf=advanced.video_crf,
                preset=advanced.video_preset,
            ),
            cwd=output_dir,
            reporter=reporter,
        )
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("ffmpeg did not create a usable video")
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
            cues=cues,
            slices=slices,
            output=cut_master,
            status="fallback",
            fallback_reason=f"render_failed: {error}",
        )
        return cut_master
    reporter.finish_stage(output.name)
    _write_manifest(
        output_dir,
        source=source,
        cut_master=cut_master,
        transcript=transcript,
        plan=plan,
        cues=cues,
        slices=slices,
        output=output,
        status="success",
    )
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--cut-master",
        type=Path,
        help="reuse an existing cut master instead of running auto-editor again",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write edit_plan.json and overlays.ass without rendering",
    )
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--heartbeat-seconds", type=float, default=20.0)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
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
    working_dirs, configured_output, config, advanced = load_advanced_config(config_path)
    source = args.input or latest_recording(working_dirs)
    output_dir = (
        args.output_dir
        or configured_output
        or source.parent / "_edited_output" / source.stem
    )
    reporter = ProgressReporter(
        enabled=not args.quiet, heartbeat_seconds=args.heartbeat_seconds
    )
    if not args.quiet:
        print(f"Source: {source}")
        print(f"Output directory: {output_dir}")
    result = run_pipeline(
        source,
        output_dir,
        config,
        advanced,
        reporter,
        dry_run=args.dry_run,
        cut_master_override=args.cut_master,
    )
    reporter.summary()
    print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Advanced editing failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

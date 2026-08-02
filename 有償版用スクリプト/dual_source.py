#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Turn a slide recording and a camera recording into one timeline plan.

OBS writes each lecture into its own folder, holding the PowerPoint capture as
an `.mkv` and the green screen camera as an `.mp4`. Both files record the same
talk, so one silence cut list can drive both tracks: as long as every segment is
placed at the same timeline frame on V1 and V2, the two views cannot drift.

Everything in this module is pure data, so the whole plan can be checked without
launching DaVinci Resolve.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

SLIDE_SUFFIX = ".mkv"
CAMERA_SUFFIX = ".mp4"

# The silence cut is tuned to one voice, not to one route, so both editors use
# the same numbers. A test pins them together to stop them drifting apart again.
SILENCE_MARGIN = "0.3sec"
SILENCE_EDIT = "audio:threshold=1%"

SLIDES_TRACK = 1
CAMERA_TRACK = 2
CAMERA_AUDIO_TRACK = 1

VIDEO_ONLY = 1
AUDIO_ONLY = 2

# The camera is usually started first, so the talk can begin a moment before the
# slide capture exists. Up to five seconds of that head is trimmed; more than
# that means the two files are not the same session.
MAXIMUM_HEAD_TRIM_SECONDS = 5.0

# Measured from the manually edited AZ-900 project, where the timeline is
# 1920x1080. The slide capture is shrunk and moved left, which frees the right
# hand side of the frame for the presenter.
TIMELINE_WIDTH = 1920
TIMELINE_HEIGHT = 1080
SLIDES_PROPERTIES = {
    "ZoomX": 0.922,
    "ZoomY": 0.922,
    "Pan": -300.0,
    "Tilt": 2.0,
}
# The camera keeps its own scale and is only moved right and cropped, so the
# presenter stands beside the slides instead of in front of them.
CAMERA_PROPERTIES = {
    "Pan": 626.0,
    "CropLeft": 249.2,
    "CropRight": 337.1,
    "CropTop": 98.9,
}


class DualSourceError(RuntimeError):
    """Raised when the two recordings cannot be combined as they are."""


@dataclass(frozen=True)
class RecordingPair:
    """One lecture folder holding exactly one slide file and one camera file."""

    folder: Path
    slides: Path
    camera: Path


@dataclass(frozen=True)
class Segment:
    """One surviving stretch of talking, in frames of the camera recording."""

    record_frame: int
    duration: int
    source_frame: int

    @property
    def source_end(self) -> int:
        return self.source_frame + self.duration


@dataclass(frozen=True)
class ClipPlacement:
    """One `AppendToTimeline` entry, ready for a media pool item to be attached."""

    role: str
    start_frame: int
    end_frame: int
    record_frame: int
    media_type: int
    track_index: int

    def to_clip_info(self, media_pool_item: object) -> dict:
        return {
            "mediaPoolItem": media_pool_item,
            "startFrame": self.start_frame,
            "endFrame": self.end_frame,
            "recordFrame": self.record_frame,
            "mediaType": self.media_type,
            "trackIndex": self.track_index,
        }


def find_recording_pair(folder: Path) -> RecordingPair | None:
    """Return the slide and camera file of a folder, or None if it is not a pair."""
    folder = Path(folder)
    if not folder.is_dir():
        return None

    slides = sorted(p for p in folder.iterdir() if p.suffix.lower() == SLIDE_SUFFIX)
    cameras = sorted(p for p in folder.iterdir() if p.suffix.lower() == CAMERA_SUFFIX)
    if len(slides) != 1 or len(cameras) != 1:
        return None
    return RecordingPair(folder=folder, slides=slides[0], camera=cameras[0])


def find_latest_recording_pair(working_dir: Path) -> RecordingPair | None:
    """Return the newest subfolder that holds a slide and camera pair."""
    working_dir = Path(working_dir)
    if not working_dir.is_dir():
        return None

    folders = sorted(
        (p for p in working_dir.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for folder in folders:
        pair = find_recording_pair(folder)
        if pair is not None:
            return pair
    return None


def parse_cut_list(document: dict | str | Path) -> tuple[Segment, ...]:
    """Read the surviving segments out of an auto-editor v3 timeline."""
    if isinstance(document, (str, Path)):
        document = json.loads(Path(document).read_text(encoding="utf-8"))

    version = str(document.get("version", ""))
    if version != "3":
        raise DualSourceError(
            f"Unsupported auto-editor timeline version: {version or 'missing'}"
        )

    tracks = document.get("v") or []
    if not tracks or not tracks[0]:
        raise DualSourceError("auto-editor returned no video segments to place")

    segments = tuple(
        Segment(
            record_frame=int(clip["start"]),
            duration=int(clip["dur"]),
            source_frame=int(clip["offset"]),
        )
        for clip in tracks[0]
        if int(clip["dur"]) > 0
    )
    if not segments:
        raise DualSourceError("Every segment in the auto-editor timeline was empty")
    return segments


def cut_list_frame_rate(document: dict) -> Fraction:
    """Return the frame rate the cut list frames are counted in."""
    timebase = document.get("timebase")
    if not timebase:
        raise DualSourceError("The auto-editor timeline has no timebase")
    return Fraction(str(timebase))


def seconds_to_frames(seconds: float, frame_rate: float) -> int:
    return int(round(seconds * frame_rate))


@dataclass(frozen=True)
class FrameRates:
    """Every frame rate involved, which are not required to agree.

    The timeline is whatever the template was built at, the two recordings are
    whatever the camera and OBS produced, and the cut list counts frames at
    auto-editor's own timebase. Mixing them by frame number silently shifts the
    edit, so the plan is computed in seconds and converted once per track.
    """

    timeline: float
    slides: float
    camera: float
    cut_list: float

    def __post_init__(self) -> None:
        for name in ("timeline", "slides", "camera", "cut_list"):
            if getattr(self, name) <= 0:
                raise DualSourceError(f"Frame rate '{name}' must be positive")


@dataclass(frozen=True)
class TimelinePlan:
    """Everything the Resolve side needs to place and to report."""

    placements: tuple[ClipPlacement, ...]
    end_frame: int
    segments_placed: int
    segments_total: int
    head_trim_seconds: float

    def describe(self) -> str:
        """Summarize the plan in one line, so a run can be checked at a glance."""
        parts = [f"{self.segments_placed} segments on V1 and V2"]
        dropped = self.segments_total - self.segments_placed
        if dropped:
            parts.append(f"{dropped} outside the slide capture and not placed")
        if self.head_trim_seconds > 0:
            parts.append(f"{self.head_trim_seconds:.2f}s trimmed off the head")
        return ", ".join(parts)


def build_placements(
    segments: tuple[Segment, ...],
    rates: FrameRates,
    slides_offset_seconds: float,
    timeline_start_frame: int = 0,
    slides_frame_count: int | None = None,
    maximum_head_trim: float = MAXIMUM_HEAD_TRIM_SECONDS,
) -> TimelinePlan:
    """Lay every segment onto the slide track, the camera track and the audio track.

    `slides_offset_seconds` is how far into the camera recording the slide
    recording begins, so subtracting it converts a moment of the camera into the
    moment of the slide capture that was recorded at the same time.

    The camera usually starts rolling first, so the opening of the talk can exist
    on the camera and not on the slides. That head is trimmed off both tracks by
    the same amount rather than placed. Record frames are accumulated from the
    surviving durations, so a trim shifts what follows instead of leaving a hole.
    """
    if not segments:
        raise DualSourceError("There is nothing to place on the timeline")

    first_camera_second = segments[0].source_frame / rates.cut_list
    head_shortfall = slides_offset_seconds - first_camera_second
    if head_shortfall > maximum_head_trim:
        raise DualSourceError(
            "The slide recording starts too late: it is missing the first "
            f"{head_shortfall:.1f} seconds of the talk. Check that both files "
            "belong to the same session."
        )

    slides_limit = (
        slides_frame_count / rates.slides if slides_frame_count is not None else None
    )

    placements: list[ClipPlacement] = []
    record_frame = timeline_start_frame
    placed = 0
    trimmed = 0.0
    for segment in segments:
        camera_second = segment.source_frame / rates.cut_list
        duration_seconds = segment.duration / rates.cut_list
        slide_second = camera_second - slides_offset_seconds
        if slide_second < 0:
            # Skip the part of the talk the slide capture never saw, on both
            # tracks, so the two views stay aligned.
            trimmed += min(-slide_second, duration_seconds)
            duration_seconds += slide_second
            camera_second -= slide_second
            slide_second = 0.0
            if duration_seconds <= 0:
                continue

        if slides_limit is not None and slide_second + duration_seconds > slides_limit:
            # The slide capture was stopped first. Placing a clip past its end
            # makes Resolve reject the whole batch, so the tail is dropped here
            # and reported instead.
            break

        for role, source_second, rate, track, media_type in (
            ("slides", slide_second, rates.slides, SLIDES_TRACK, VIDEO_ONLY),
            ("camera", camera_second, rates.camera, CAMERA_TRACK, VIDEO_ONLY),
            ("camera_audio", camera_second, rates.camera, CAMERA_AUDIO_TRACK, AUDIO_ONLY),
        ):
            start_frame = seconds_to_frames(source_second, rate)
            placements.append(
                ClipPlacement(
                    role=role,
                    start_frame=start_frame,
                    end_frame=start_frame + seconds_to_frames(duration_seconds, rate),
                    record_frame=record_frame,
                    media_type=media_type,
                    track_index=track,
                )
            )
        record_frame += seconds_to_frames(duration_seconds, rates.timeline)
        placed += 1

    if not placements:
        raise DualSourceError(
            "The slide recording is shorter than the first segment of the talk"
        )
    return TimelinePlan(
        placements=tuple(placements),
        end_frame=record_frame,
        segments_placed=placed,
        segments_total=len(segments),
        head_trim_seconds=trimmed,
    )

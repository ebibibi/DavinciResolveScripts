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

SLIDES_TRACK = 1
CAMERA_TRACK = 2
CAMERA_AUDIO_TRACK = 1

VIDEO_ONLY = 1
AUDIO_ONLY = 2

# The camera is usually started first, so the talk can begin a moment before the
# slide capture exists. Up to five seconds of that head is trimmed; more than
# that means the two files are not the same session.
MAXIMUM_HEAD_TRIM_FRAMES = 150

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


def build_placements(
    segments: tuple[Segment, ...],
    slides_offset_frames: int,
    timeline_start_frame: int = 0,
    slides_frame_count: int | None = None,
    maximum_head_trim: int = MAXIMUM_HEAD_TRIM_FRAMES,
) -> tuple[ClipPlacement, ...]:
    """Lay every segment onto the slide track, the camera track and the audio track.

    `slides_offset_frames` is how far into the camera recording the slide
    recording begins, so subtracting it converts a camera source frame into the
    slide source frame that was captured at the same moment.

    The camera usually starts rolling first, so the opening moments of the talk
    can exist on the camera and not on the slides. Those few frames are trimmed
    off the front of both tracks rather than placed, which keeps the two views
    aligned. Record frames are accumulated from the surviving durations, so a
    trim shifts what follows instead of leaving a hole.
    """
    if not segments:
        raise DualSourceError("There is nothing to place on the timeline")

    head_shortfall = slides_offset_frames - segments[0].source_frame
    if head_shortfall > maximum_head_trim:
        raise DualSourceError(
            "The slide recording starts too late: it is missing the first "
            f"{head_shortfall} frames of the talk. Check that both files belong "
            "to the same session."
        )

    placements: list[ClipPlacement] = []
    record_frame = timeline_start_frame
    for segment in segments:
        slide_start = segment.source_frame - slides_offset_frames
        camera_start = segment.source_frame
        duration = segment.duration
        if slide_start < 0:
            # Trim the part of the talk the slide capture never saw, off both
            # tracks by the same amount.
            duration += slide_start
            camera_start -= slide_start
            slide_start = 0
            if duration <= 0:
                continue

        if slides_frame_count is not None and slide_start + duration > slides_frame_count:
            # The slide capture was stopped first. Placing a clip past its end
            # makes Resolve reject the whole batch, so the tail is dropped here
            # and reported by the caller instead.
            break

        for role, start, track, media_type in (
            ("slides", slide_start, SLIDES_TRACK, VIDEO_ONLY),
            ("camera", camera_start, CAMERA_TRACK, VIDEO_ONLY),
            ("camera_audio", camera_start, CAMERA_AUDIO_TRACK, AUDIO_ONLY),
        ):
            placements.append(
                ClipPlacement(
                    role=role,
                    start_frame=start,
                    end_frame=start + duration,
                    record_frame=record_frame,
                    media_type=media_type,
                    track_index=track,
                )
            )
        record_frame += duration

    if not placements:
        raise DualSourceError(
            "The slide recording is shorter than the first segment of the talk"
        )
    return tuple(placements)


def placement_end_frame(placements: tuple[ClipPlacement, ...]) -> int:
    """Return the first timeline frame after everything that was placed."""
    return max(
        placement.record_frame + placement.end_frame - placement.start_frame
        for placement in placements
    )


def describe_plan(placements: tuple[ClipPlacement, ...], segments_planned: int) -> str:
    """Summarize the plan in one line, so a run can be checked at a glance."""
    placed = len([p for p in placements if p.role == "slides"])
    dropped = segments_planned - placed
    tail = f", {dropped} outside the slide capture and not placed" if dropped else ""
    return f"{placed} segments on V1 and V2{tail}"

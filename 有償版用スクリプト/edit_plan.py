#!/usr/bin/env python3
"""The full edit decision list: no subprocesses, no files, no console output.

`highlight_plan.py` decides only what to copy to the opening. This module
describes the whole edited video - opening highlights, chapter cards, emphasis
telops, burned captions and sound cues - as one immutable value that can be
reviewed, diffed and rendered deterministically.

Every timestamp here belongs to the cut-master timeline. Turning those into
positions in the finished video is `timeline.py`'s job, because the same moment
can appear twice once a highlight is copied to the opening.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from highlight_plan import Highlight, clean_text, shorten_text

MAXIMUM_TELOP_CHARACTERS = 26
MAXIMUM_CHAPTER_CHARACTERS = 22
MAXIMUM_CAPTION_CHARACTERS = 40
SENTENCE_BREAK_PATTERN = re.compile(r"(?<=[。！？!?])")


@dataclass(frozen=True)
class Telop:
    """A short emphasis phrase burned over the speaker's own words."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Chapter:
    """A scene title card shown when a new topic starts in the main body."""

    start: float
    title: str


@dataclass(frozen=True)
class Caption:
    """One burned subtitle line taken verbatim from the transcript."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class SoundCue:
    """A generated sound effect placed on the finished timeline.

    Unlike everything else in this module, `at` is already a position in the
    finished video: sound cues are derived from the rendered structure rather
    than from the transcript.
    """

    at: float
    kind: str


@dataclass(frozen=True)
class EditPlan:
    """Everything the renderer needs, with nothing left to decide."""

    title: str
    highlights: tuple[Highlight, ...] = ()
    chapters: tuple[Chapter, ...] = ()
    telops: tuple[Telop, ...] = ()
    captions: tuple[Caption, ...] = ()
    notes: tuple[str, ...] = field(default=())

    def is_renderable(self) -> bool:
        """Report whether anything would actually be added to the cut master."""
        return bool(
            self.title or self.highlights or self.chapters or self.telops or self.captions
        )


def _segment_bounds(segment: dict[str, Any]) -> tuple[float, float] | None:
    try:
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        return None
    return max(0.0, start), end


def split_caption_text(text: str, maximum: int = MAXIMUM_CAPTION_CHARACTERS) -> list[str]:
    """Break one transcript line into display-sized pieces.

    Whisper returns a whole breath as a single segment, which is far too wide
    to burn onto a 16:9 frame. Sentences are preferred break points; only a
    sentence that is still too long is cut by length.
    """
    cleaned = clean_text(text)
    if not cleaned:
        return []
    pieces: list[str] = []
    for sentence in SENTENCE_BREAK_PATTERN.split(cleaned):
        sentence = sentence.strip()
        while len(sentence) > maximum:
            pieces.append(sentence[:maximum])
            sentence = sentence[maximum:]
        if sentence:
            pieces.append(sentence)
    return pieces


def build_captions(
    segments: Sequence[dict[str, Any]],
    *,
    video_duration: float,
    maximum_characters: int = MAXIMUM_CAPTION_CHARACTERS,
) -> tuple[Caption, ...]:
    """Turn transcript segments into burned caption lines.

    A segment's time is shared between its pieces in proportion to their
    length, so a long sentence stays on screen longer than a short one.
    """
    captions: list[Caption] = []
    for segment in segments:
        bounds = _segment_bounds(segment)
        if bounds is None:
            continue
        start, end = bounds
        end = min(end, video_duration) if video_duration > 0 else end
        if end <= start:
            continue
        pieces = split_caption_text(segment.get("text", ""), maximum_characters)
        if not pieces:
            continue
        characters = sum(len(piece) for piece in pieces)
        cursor = start
        for piece in pieces:
            share = (end - start) * (len(piece) / characters)
            piece_end = min(end, cursor + max(0.4, share))
            if piece_end > cursor:
                captions.append(Caption(cursor, piece_end, piece))
            cursor = piece_end
    return tuple(captions)


def _telop_from_segment(
    segment: dict[str, Any],
    text: str,
    *,
    video_duration: float,
    minimum_seconds: float,
    maximum_seconds: float,
) -> Telop | None:
    bounds = _segment_bounds(segment)
    display = shorten_text(text, MAXIMUM_TELOP_CHARACTERS)
    if bounds is None or not display:
        return None
    start, end = bounds
    end = max(end, start + minimum_seconds)
    end = min(end, start + maximum_seconds)
    if video_duration > 0:
        end = min(end, video_duration)
    if end - start < 0.4:
        return None
    return Telop(start, end, display)


def _chapter_from_segment(
    segment: dict[str, Any], title: str, *, video_duration: float
) -> Chapter | None:
    bounds = _segment_bounds(segment)
    display = shorten_text(title, MAXIMUM_CHAPTER_CHARACTERS)
    if bounds is None or not display:
        return None
    start = bounds[0]
    if video_duration > 0 and start >= video_duration:
        return None
    return Chapter(start, display)


def edit_plan_schema(maximum_chapters: int, maximum_telops: int) -> dict[str, Any]:
    """Return the strict structured-output schema for one editorial call."""
    return {
        "type": "object",
        "properties": {
            "main_takeaway": {"type": "string"},
            "highlight_segment_indexes": {
                "type": "array",
                "items": {"type": "integer"},
            },
            "chapters": {
                "type": "array",
                "maxItems": max(1, maximum_chapters),
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_index": {"type": "integer"},
                        "title": {"type": "string"},
                    },
                    "required": ["segment_index", "title"],
                    "additionalProperties": False,
                },
            },
            "telops": {
                "type": "array",
                "maxItems": max(1, maximum_telops),
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_index": {"type": "integer"},
                        "text": {"type": "string"},
                    },
                    "required": ["segment_index", "text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "main_takeaway",
            "highlight_segment_indexes",
            "chapters",
            "telops",
        ],
        "additionalProperties": False,
    }


def parse_editorial_output(
    data: dict[str, Any],
    segments: Sequence[dict[str, Any]],
    *,
    video_duration: float,
    maximum_chapters: int,
    maximum_telops: int,
    minimum_chapter_gap_seconds: float,
    telop_minimum_seconds: float,
    telop_maximum_seconds: float,
) -> tuple[tuple[Chapter, ...], tuple[Telop, ...]]:
    """Validate AI chapters and telops against the transcript.

    Only the segment index is trusted for timing. The AI may write the display
    text, but it can never place a caption where nobody was speaking, and an
    index outside the transcript is dropped instead of clamped.
    """
    chapters: list[Chapter] = []
    for raw in data.get("chapters", []) if isinstance(data.get("chapters"), list) else []:
        if not isinstance(raw, dict):
            continue
        index = raw.get("segment_index")
        if not isinstance(index, int) or not 0 <= index < len(segments):
            continue
        chapter = _chapter_from_segment(
            segments[index], raw.get("title", ""), video_duration=video_duration
        )
        if chapter is None:
            continue
        if any(
            abs(chapter.start - existing.start) < max(0.0, minimum_chapter_gap_seconds)
            for existing in chapters
        ):
            continue
        chapters.append(chapter)
        if len(chapters) >= max(1, maximum_chapters):
            break

    telops: list[Telop] = []
    seen: set[int] = set()
    for raw in data.get("telops", []) if isinstance(data.get("telops"), list) else []:
        if not isinstance(raw, dict):
            continue
        index = raw.get("segment_index")
        if not isinstance(index, int) or index in seen:
            continue
        if not 0 <= index < len(segments):
            continue
        seen.add(index)
        telop = _telop_from_segment(
            segments[index],
            raw.get("text", ""),
            video_duration=video_duration,
            minimum_seconds=telop_minimum_seconds,
            maximum_seconds=telop_maximum_seconds,
        )
        if telop is None:
            continue
        if any(telop.start < old.end and old.start < telop.end for old in telops):
            continue
        telops.append(telop)
        if len(telops) >= max(1, maximum_telops):
            break

    chapters.sort(key=lambda item: item.start)
    telops.sort(key=lambda item: item.start)
    return tuple(chapters), tuple(telops)


def build_local_chapters(
    segments: Sequence[dict[str, Any]],
    *,
    video_duration: float,
    maximum_chapters: int,
) -> tuple[Chapter, ...]:
    """Place evenly spaced chapters when the AI is unavailable.

    The title is the first sentence spoken after the boundary, which is a weak
    but honest summary: it is always something the presenter actually said.
    """
    if video_duration <= 0 or not segments:
        return ()
    count = min(max(1, maximum_chapters), max(1, int(video_duration // (5 * 60))))
    if count < 2:
        return ()
    chapters: list[Chapter] = []
    for step in range(1, count):
        boundary = video_duration * step / count
        segment = next(
            (
                item
                for item in segments
                if (_segment_bounds(item) or (0.0, 0.0))[0] >= boundary
                and clean_text(item.get("text", ""))
            ),
            None,
        )
        if segment is None:
            continue
        chapter = _chapter_from_segment(
            segment, segment.get("text", ""), video_duration=video_duration
        )
        if chapter is not None:
            chapters.append(chapter)
    return tuple(chapters)


def parse_structured_json(output: str) -> dict[str, Any]:
    """Read the plan object out of a Claude CLI JSON response."""
    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise ValueError("AI output is not an object")
    for key in ("structured_output", "result"):
        value = payload.get(key)
        if isinstance(value, dict) and "main_takeaway" in value:
            return value
        if isinstance(value, str):
            try:
                nested = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(nested, dict) and "main_takeaway" in nested:
                return nested
    if "main_takeaway" in payload:
        return payload
    raise ValueError("AI output does not contain an edit plan")

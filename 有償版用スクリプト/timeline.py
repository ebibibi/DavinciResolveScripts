#!/usr/bin/env python3
"""Map cut-master time to finished-video time. Pure functions only.

The finished video is the opening highlight reel followed by the complete cut
master, so one moment in the recording can appear twice: once as a copied
highlight and once in the body. Every overlay has to follow it to both places,
and every position in the reel has to be renumbered from zero. Keeping that
arithmetic in one tested module is what makes captions, telops, chapter cards
and sound cues line up in a single render.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from highlight_plan import Highlight

HIGHLIGHT = "highlight"
BODY = "body"


@dataclass(frozen=True)
class Slice:
    """One piece of the cut master as it appears in the finished video."""

    source_start: float
    source_end: float
    output_start: float
    kind: str

    @property
    def duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    @property
    def output_end(self) -> float:
        return self.output_start + self.duration


def build_timeline(
    highlights: Sequence[Highlight], body_duration: float
) -> tuple[Slice, ...]:
    """Return the copied highlights followed by the complete body."""
    slices: list[Slice] = []
    cursor = 0.0
    for highlight in highlights:
        start = max(0.0, highlight.start)
        end = min(body_duration, highlight.end) if body_duration > 0 else highlight.end
        if end <= start:
            continue
        slices.append(Slice(start, end, cursor, HIGHLIGHT))
        cursor += end - start
    slices.append(Slice(0.0, max(0.0, body_duration), cursor, BODY))
    return tuple(slices)


def total_duration(slices: Sequence[Slice]) -> float:
    """Return the length of the finished video."""
    return max((item.output_end for item in slices), default=0.0)


def reel_duration(slices: Sequence[Slice]) -> float:
    """Return where the complete body starts in the finished video."""
    return next((item.output_start for item in slices if item.kind == BODY), 0.0)


def map_range(
    slices: Iterable[Slice],
    start: float,
    end: float,
    *,
    kinds: Sequence[str] = (HIGHLIGHT, BODY),
    minimum_seconds: float = 0.2,
) -> tuple[tuple[float, float], ...]:
    """Return every finished-video range that shows the given source range.

    A range that only partially overlaps a highlight is clipped rather than
    dropped, so an emphasis telop still appears - shortened - when the editor
    copied the middle of its sentence.
    """
    placements: list[tuple[float, float]] = []
    for item in slices:
        if item.kind not in kinds:
            continue
        overlap_start = max(start, item.source_start)
        overlap_end = min(end, item.source_end)
        if overlap_end - overlap_start < minimum_seconds:
            continue
        offset = item.output_start - item.source_start
        placements.append((overlap_start + offset, overlap_end + offset))
    return tuple(placements)


def map_instant(
    slices: Iterable[Slice],
    at: float,
    *,
    kinds: Sequence[str] = (HIGHLIGHT, BODY),
) -> tuple[float, ...]:
    """Return every finished-video position of one source instant."""
    positions: list[float] = []
    for item in slices:
        if item.kind not in kinds:
            continue
        if item.source_start <= at < item.source_end:
            positions.append(at + item.output_start - item.source_start)
    return tuple(positions)


def transition_positions(slices: Sequence[Slice]) -> tuple[float, ...]:
    """Return where the finished video jumps from one piece to another."""
    return tuple(item.output_start for item in slices[1:])

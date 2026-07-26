#!/usr/bin/env python3
"""Pure highlight selection: no subprocesses, no files, no console output.

Keeping the selection rules free of I/O lets them be tested directly and keeps
`highlight_video.py` focused on running and reporting the pipeline.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Sequence

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

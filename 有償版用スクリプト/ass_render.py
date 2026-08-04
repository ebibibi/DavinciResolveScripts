#!/usr/bin/env python3
"""Turn an edit plan into one ASS file. Pure string building, no I/O calls.

Everything the viewer reads - the opening takeaway, chapter cards, emphasis
telops and burned captions - is drawn by a single libass pass, because one
`ass` filter is far cheaper than stacking four `drawtext` chains and it gives
real Japanese line breaking, outlines and fades for free.
"""

from __future__ import annotations

from typing import Sequence

from edit_plan import Caption, Chapter, EditPlan, Telop
from highlight_plan import clean_text
from timeline import BODY, Slice, map_range

LAYER_CAPTION = 0
LAYER_TELOP = 1
LAYER_CHAPTER = 2
LAYER_TAKEAWAY = 3

REFERENCE_HEIGHT = 1080


def ass_time(seconds: float) -> str:
    """Format seconds as the ASS 0:00:00.00 timestamp."""
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def escape_text(value: str) -> str:
    """Make arbitrary transcript text safe inside an ASS dialogue line."""
    return (
        clean_text(value).replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    )


def _scaled(size: int, height: int) -> int:
    """Keep every font the same visual size on 720p, 1080p and 4K."""
    if height <= 0:
        return size
    return max(12, int(round(size * height / REFERENCE_HEIGHT)))


def build_styles(
    *, font_name: str, height: int, takeaway_font_size: int
) -> tuple[str, ...]:
    """Return the four style rows, sized for the actual frame height."""
    takeaway = _scaled(takeaway_font_size, height)
    chapter = _scaled(58, height)
    telop = _scaled(74, height)
    caption = _scaled(46, height)
    return (
        # Name,Fontname,Fontsize,Primary,Secondary,Outline,Back,Bold,Italic,
        # Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,
        # Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
        f"Style: Takeaway,{font_name},{takeaway},&H00FFFFFF,&H00FFFFFF,"
        "&H00101010,&H80000000,-1,0,0,0,100,100,0,0,3,7,2,5,120,120,90,1",
        f"Style: Chapter,{font_name},{chapter},&H00FFFFFF,&H00FFFFFF,"
        "&H00202020,&HB0000000,-1,0,0,0,100,100,0,0,3,4,0,7,80,80,70,1",
        f"Style: Telop,{font_name},{telop},&H0000E5FF,&H0000E5FF,"
        "&H00202020,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,80,80,190,1",
        f"Style: Caption,{font_name},{caption},&H00FFFFFF,&H00FFFFFF,"
        "&H00101010,&HA0000000,0,0,0,0,100,100,0,0,1,4,1,2,80,80,60,1",
    )


def _dialogue(layer: int, start: float, end: float, style: str, text: str) -> str:
    return (
        f"Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}"
    )


def _caption_events(captions: Sequence[Caption], slices: Sequence[Slice]) -> list[str]:
    events: list[str] = []
    for caption in captions:
        text = escape_text(caption.text)
        if not text:
            continue
        for start, end in map_range(slices, caption.start, caption.end):
            events.append(_dialogue(LAYER_CAPTION, start, end, "Caption", text))
    return events


def _telop_events(telops: Sequence[Telop], slices: Sequence[Slice]) -> list[str]:
    events: list[str] = []
    for telop in telops:
        text = escape_text(telop.text)
        if not text:
            continue
        for start, end in map_range(slices, telop.start, telop.end):
            events.append(
                _dialogue(
                    LAYER_TELOP,
                    start,
                    end,
                    "Telop",
                    r"{\fad(150,200)}" + text,
                )
            )
    return events


def _chapter_events(
    chapters: Sequence[Chapter],
    slices: Sequence[Slice],
    *,
    display_seconds: float,
    body_duration: float,
) -> list[str]:
    """Chapter cards belong to the body only.

    Showing "Chapter 2" inside a highlight that was copied to the opening would
    announce a scene the viewer has not reached yet, so the reel is skipped.
    """
    events: list[str] = []
    for index, chapter in enumerate(chapters, start=1):
        text = escape_text(chapter.title)
        if not text:
            continue
        end = chapter.start + max(1.0, display_seconds)
        if body_duration > 0:
            end = min(end, body_duration)
        for start, stop in map_range(
            slices, chapter.start, end, kinds=(BODY,), minimum_seconds=0.5
        ):
            events.append(
                _dialogue(
                    LAYER_CHAPTER,
                    start,
                    stop,
                    "Chapter",
                    r"{\fad(200,300)}" + f"{index}. {text}",
                )
            )
    return events


def build_ass(
    plan: EditPlan,
    slices: Sequence[Slice],
    *,
    resolution: tuple[int, int],
    font_name: str,
    takeaway_font_size: int,
    takeaway_seconds: float,
    chapter_seconds: float,
    body_duration: float,
) -> str:
    """Render the whole edit plan as one ASS script."""
    width, height = resolution
    events: list[str] = []
    title = escape_text(plan.title)
    if title and takeaway_seconds > 0:
        events.append(
            _dialogue(
                LAYER_TAKEAWAY,
                0.0,
                takeaway_seconds,
                "Takeaway",
                r"{\fad(120,300)}" + title,
            )
        )
    events.extend(_caption_events(plan.captions, slices))
    events.extend(_telop_events(plan.telops, slices))
    events.extend(
        _chapter_events(
            plan.chapters,
            slices,
            display_seconds=chapter_seconds,
            body_duration=body_duration,
        )
    )
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,"
            "ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,"
            "MarginR,MarginV,Encoding",
            *build_styles(
                font_name=font_name,
                height=height,
                takeaway_font_size=takeaway_font_size,
            ),
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        ]
    )
    return header + "\n" + "\n".join(events) + "\n"

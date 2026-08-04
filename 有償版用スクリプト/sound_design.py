#!/usr/bin/env python3
"""Generate the sound effect track with FFmpeg's own signal generators.

Shipping audio files would mean shipping licences, so every effect is
synthesised from `sine` and `anoisesrc`: a filtered noise burst for a cut, a
decaying bell for a chapter card. That keeps the repository free of binary
assets and makes the whole sound design reviewable as text.

Cue positions are on the finished timeline, so the track can be mixed under the
final audio in one pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from edit_plan import Chapter, SoundCue
from timeline import BODY, Slice, map_instant, transition_positions

MAXIMUM_CUES = 48
MINIMUM_CUE_GAP_SECONDS = 0.4
SAMPLE_RATE = 48000

# Each generator is a complete lavfi source graph for one effect.
EFFECT_SOURCES: dict[str, str] = {
    "whoosh": (
        f"anoisesrc=color=brown:duration=0.7:amplitude=0.6:sample_rate={SAMPLE_RATE}"
        ",highpass=f=180,lowpass=f=5000"
        ",afade=t=in:st=0:d=0.3:curve=exp"
        ",afade=t=out:st=0.3:d=0.4:curve=exp"
    ),
    "ding": (
        f"sine=frequency=1046:duration=0.9:sample_rate={SAMPLE_RATE}"
        ",afade=t=out:st=0.03:d=0.87:curve=exp"
    ),
    "pop": (
        f"sine=frequency=660:duration=0.2:sample_rate={SAMPLE_RATE}"
        ",afade=t=out:st=0.02:d=0.18:curve=exp"
    ),
}

EFFECT_GAIN: dict[str, float] = {"whoosh": 0.5, "ding": 0.35, "pop": 0.4}


def build_sound_cues(
    slices: Sequence[Slice],
    chapters: Sequence[Chapter],
    *,
    mark_transitions: bool = True,
    mark_chapters: bool = True,
) -> tuple[SoundCue, ...]:
    """Place one cue on every cut and every chapter card.

    Cues are deliberately derived from structure instead of being chosen by the
    AI: a sound that does not coincide with a visible change is just noise.
    """
    cues: list[SoundCue] = []
    if mark_transitions:
        cues.extend(SoundCue(at, "whoosh") for at in transition_positions(slices))
    if mark_chapters:
        for chapter in chapters:
            cues.extend(
                SoundCue(at, "ding")
                for at in map_instant(slices, chapter.start, kinds=(BODY,))
            )
    kept: list[SoundCue] = []
    for cue in sorted(cues, key=lambda item: (item.at, item.kind != "whoosh")):
        if cue.at < 0:
            continue
        # A chapter that starts right where the video cuts would fire two
        # effects on one frame, which reads as a mistake. The cut wins: it is
        # the change the viewer actually sees.
        if any(abs(cue.at - old.at) < MINIMUM_CUE_GAP_SECONDS for old in kept):
            continue
        kept.append(cue)
    return tuple(kept)[:MAXIMUM_CUES]


def build_sfx_command(cues: Sequence[SoundCue], output: Path) -> list[str]:
    """Build the FFmpeg command that renders every cue into one WAV."""
    usable = [cue for cue in cues if cue.kind in EFFECT_SOURCES]
    if not usable:
        raise ValueError("no usable sound cues")
    command: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    filters: list[str] = []
    labels: list[str] = []
    for index, cue in enumerate(usable):
        command.extend(["-f", "lavfi", "-i", EFFECT_SOURCES[cue.kind]])
        delay = max(0, int(round(cue.at * 1000)))
        gain = EFFECT_GAIN.get(cue.kind, 0.4)
        filters.append(
            f"[{index}:a]adelay={delay}:all=1,volume={gain:.2f},"
            f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:"
            f"channel_layouts=stereo[s{index}]"
        )
        labels.append(f"[s{index}]")
    filters.append(
        "".join(labels) + f"amix=inputs={len(usable)}:normalize=0:duration=longest[out]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            str(output),
        ]
    )
    return command

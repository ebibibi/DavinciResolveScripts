"""When things happen, in beats, for one eyecatch variant."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Cue:
    bpm: float
    beats: float
    hit_beat: float
    silence_before_hit: float
    sound: str
    ticks: tuple[float, ...]
    riser: tuple[float, float]
    # The variant's own settings from timeline.json (word, drop, speed ...),
    # shared with the picture so both read the same numbers.
    spec: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def seconds(self, beat: float) -> float:
        return beat * 60.0 / self.bpm

    @property
    def hit_s(self) -> float:
        return self.seconds(self.hit_beat)

    @property
    def total_s(self) -> float:
        return self.seconds(self.beats)

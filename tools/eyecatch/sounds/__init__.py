"""One sound design per eyecatch variant; timeline.json names which one to use."""

from __future__ import annotations

from collections.abc import Callable

from cue import Cue
from synth import Mix

from . import (
    blade,
    boing,
    chiptune,
    data,
    engine,
    projector,
    space,
    sparkle,
    typewriter,
    water,
)

SOUNDS: dict[str, Callable[[Cue], Mix]] = {
    "sparkle": sparkle.design,
    "boing": boing.design,
    "chiptune": chiptune.design,
    "engine": engine.design,
    "typewriter": typewriter.design,
    "water": water.design,
    "blade": blade.design,
    "space": space.design,
    "data": data.design,
    "projector": projector.design,
}

"""One sound design per eyecatch variant; timeline.json names which one to use."""

from __future__ import annotations

from collections.abc import Callable

from cue import Cue
from synth import Mix

from . import boing, chiptune, engine, sparkle

SOUNDS: dict[str, Callable[[Cue], Mix]] = {
    "sparkle": sparkle.design,
    "boing": boing.design,
    "chiptune": chiptune.design,
    "engine": engine.design,
}

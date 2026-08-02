"""Shared, environment-local settings for auto-editor silence removal."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# Measured on the AZ-900 recordings: at 1% the camera microphone's room tone
# never falls below the threshold and 99.7% of the talk survives. See ADR-013.
DEFAULT_THRESHOLD_PERCENT = 3.0
DEFAULT_MARGIN_SECONDS = 0.3

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent / "有償版用スクリプト" / "config.json"
)


def _number(
    section: Mapping[str, Any],
    key: str,
    default: float,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"auto_editor.{key} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"auto_editor.{key} must be at least {minimum:g}")
    if maximum is not None and result > maximum:
        raise ValueError(f"auto_editor.{key} must be at most {maximum:g}")
    return result


def _compact_number(value: float) -> str:
    return format(value, "g")


@dataclass(frozen=True)
class AutoEditorConfig:
    """Validated values formatted for the auto-editor CLI.

    The shipped threshold is 3%, measured against both microphones: the camera
    microphone that the dual source route analyses never falls below 1%, so that
    default cut nothing at all on the route that needs it most. See ADR-013.
    """

    threshold_percent: float = DEFAULT_THRESHOLD_PERCENT
    margin_seconds: float = DEFAULT_MARGIN_SECONDS

    @property
    def edit_expression(self) -> str:
        return f"audio:threshold={_compact_number(self.threshold_percent)}%"

    @property
    def margin(self) -> str:
        return f"{_compact_number(self.margin_seconds)}sec"


def parse_auto_editor_config(data: Mapping[str, Any]) -> AutoEditorConfig:
    """Parse the optional ``auto_editor`` section of a complete config."""
    section = data.get("auto_editor", {})
    if not isinstance(section, dict):
        raise ValueError("auto_editor must be a JSON object")
    return AutoEditorConfig(
        threshold_percent=_number(
            section,
            "threshold_percent",
            DEFAULT_THRESHOLD_PERCENT,
            minimum=0.000001,
            maximum=100.0,
        ),
        margin_seconds=_number(
            section,
            "margin_seconds",
            DEFAULT_MARGIN_SECONDS,
            minimum=0.0,
        ),
    )


def load_auto_editor_config(path: Path = DEFAULT_CONFIG_PATH) -> AutoEditorConfig:
    """Load a local config, retaining shipped defaults when it is absent."""
    if not path.exists():
        return AutoEditorConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config.json must contain a JSON object")
    return parse_auto_editor_config(data)

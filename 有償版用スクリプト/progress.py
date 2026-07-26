#!/usr/bin/env python3
"""Live progress reporting for the long-running highlight pipeline.

Every heavy step (auto-editor, Whisper, Claude, FFmpeg) used to run with its
output captured, so the console stayed silent for many minutes and the run was
indistinguishable from a hang. This module turns each step into a visible
stage with elapsed time, echoes throttled child-process output, and prints a
heartbeat whenever a child stays quiet.

All reporter text is intentionally ASCII so a Japanese Windows console
(cp932) can render it without mojibake.
"""

from __future__ import annotations

import math
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, TextIO

FFMPEG_TIME_PATTERN = re.compile(r"time=(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
TRANSCRIPT_TIME_PATTERN = re.compile(r"-->\s*(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)")
PERCENT_PATTERN = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
NOISY_LINE_PATTERN = re.compile(r"time=|-->|%")


@dataclass(frozen=True)
class StageResult:
    """One finished pipeline stage and how long it took."""

    label: str
    seconds: float
    note: str = ""


def format_clock(seconds: float) -> str:
    """Return H:MM:SS for long spans and MM:SS for short ones."""
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{whole_seconds:02d}"
    return f"{minutes:02d}:{whole_seconds:02d}"


def parse_media_position(line: str) -> float | None:
    """Read how far into the media a child process has progressed."""
    match = FFMPEG_TIME_PATTERN.search(line)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    match = TRANSCRIPT_TIME_PATTERN.search(line)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes) * 60 + float(seconds)
    return None


def parse_percent(line: str) -> float | None:
    """Read a self-reported percentage such as the auto-editor bar."""
    match = PERCENT_PATTERN.search(line)
    if not match:
        return None
    value = float(match.group(1))
    return value if 0.0 <= value <= 100.0 else None


def is_noisy(line: str) -> bool:
    """Report whether a line is a repeating progress update."""
    return bool(NOISY_LINE_PATTERN.search(line))


class ProgressReporter:
    """Print what the pipeline is doing while it is still doing it."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        enabled: bool = True,
        heartbeat_seconds: float = 20.0,
        echo_interval_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._enabled = enabled
        self._heartbeat_seconds = max(1.0, heartbeat_seconds)
        self._echo_interval_seconds = max(0.0, echo_interval_seconds)
        self._clock = clock
        self._lock = threading.RLock()
        self._results: list[StageResult] = []
        self._label = ""
        self._stage_started = 0.0
        self._total_seconds = 0.0
        self._last_output = 0.0
        self._last_echo = -math.inf
        self._saw_output = False
        self._transient_width = 0
        self._stopper: threading.Event | None = None
        self._heartbeat: threading.Thread | None = None
        self._started = self._clock()

    @property
    def results(self) -> tuple[StageResult, ...]:
        """Return every finished stage in order."""
        return tuple(self._results)

    def _write(self, text: str, *, transient: bool = False) -> None:
        if not self._enabled:
            return
        padding = max(0, self._transient_width - len(text))
        prefix = "\r" if self._transient_width else ""
        suffix = "\r" if transient else "\n"
        payload = f"{prefix}{text}{' ' * padding}{suffix}"
        try:
            self._stream.write(payload)
            self._stream.flush()
        except UnicodeError:
            # A legacy Japanese console cannot encode every transcript
            # character, which must never silence the whole report.
            self._stream.write(payload.encode("ascii", "replace").decode("ascii"))
            self._stream.flush()
        except (OSError, ValueError):
            self._enabled = False
            return
        self._transient_width = len(text) if transient else 0

    def _is_interactive(self) -> bool:
        try:
            return bool(self._stream.isatty())
        except (AttributeError, OSError, ValueError):
            return False

    def start_stage(
        self,
        label: str,
        *,
        step: int = 0,
        steps: int = 0,
        total_seconds: float = 0.0,
    ) -> None:
        """Announce a stage and begin watching its child process."""
        with self._lock:
            self._label = label
            self._stage_started = self._clock()
            self._total_seconds = max(0.0, total_seconds)
            self._last_output = self._stage_started
            # Never throttle the first update: it is the proof of life the
            # console has been waiting for.
            self._last_echo = -math.inf
            self._saw_output = False
            counter = f"[{step}/{steps}] " if steps else ""
            self._write(f"{counter}{label} ... started")
        self._start_heartbeat()

    def child_output(self, line: str) -> None:
        """Echo one line of child output, throttling repeated progress."""
        text = line.strip()
        with self._lock:
            self._last_output = self._clock()
            self._saw_output = True
            if not text or not self._enabled:
                return
            now = self._clock()
            if is_noisy(text):
                if now - self._last_echo < self._echo_interval_seconds:
                    return
                self._last_echo = now
                self._write(self._progress_line(text), transient=self._is_interactive())
                return
            self._last_echo = now
            self._write(f"    | {text[:160]}")

    def _progress_line(self, text: str) -> str:
        elapsed = self._clock() - self._stage_started
        fraction = self._fraction(text)
        parts = [f"    {self._label}"]
        if fraction is not None:
            parts.append(f"{fraction * 100:5.1f}%")
            if self._total_seconds:
                position = fraction * self._total_seconds
                parts.append(
                    f"{format_clock(position)} / {format_clock(self._total_seconds)}"
                )
        parts.append(f"elapsed {format_clock(elapsed)}")
        if fraction and fraction > 0.01:
            parts.append(f"eta {format_clock(elapsed * (1 - fraction) / fraction)}")
        return "  ".join(parts)

    def _fraction(self, text: str) -> float | None:
        position = parse_media_position(text)
        if position is not None and self._total_seconds > 0:
            return min(1.0, position / self._total_seconds)
        percent = parse_percent(text)
        return percent / 100.0 if percent is not None else None

    def _start_heartbeat(self) -> None:
        self._stop_heartbeat()
        stopper = threading.Event()
        thread = threading.Thread(
            target=self._beat, args=(stopper,), name="progress-heartbeat", daemon=True
        )
        self._stopper = stopper
        self._heartbeat = thread
        thread.start()

    def _beat(self, stopper: threading.Event) -> None:
        while not stopper.wait(1.0):
            with self._lock:
                quiet = self._clock() - self._last_output
                if quiet < self._heartbeat_seconds:
                    continue
                self._last_output = self._clock()
                elapsed = format_clock(self._clock() - self._stage_started)
                tail = "still no output" if not self._saw_output else "still working"
                self._write(f"    {self._label} ... {tail} (elapsed {elapsed})")

    def _stop_heartbeat(self) -> None:
        stopper, thread = self._stopper, self._heartbeat
        self._stopper = self._heartbeat = None
        if stopper is not None:
            stopper.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def finish_stage(self, note: str = "") -> StageResult:
        """Close the current stage and record how long it took."""
        self._stop_heartbeat()
        with self._lock:
            seconds = self._clock() - self._stage_started
            result = StageResult(self._label or "stage", seconds, note)
            self._results.append(result)
            detail = f" ({note})" if note else ""
            self._write(f"    done in {format_clock(seconds)}{detail}")
            self._label = ""
            return result

    def warn(self, message: str) -> None:
        """Report a recoverable problem without stopping the pipeline."""
        with self._lock:
            self._write(f"    ! {message}")

    def summary(self) -> None:
        """Print the per-stage timing table once the pipeline is done."""
        self._stop_heartbeat()
        with self._lock:
            total = self._clock() - self._started
            self._write(f"Total elapsed {format_clock(total)}")
            for result in self._results:
                detail = f"  ({result.note})" if result.note else ""
                self._write(
                    f"    {format_clock(result.seconds)}  {result.label}{detail}"
                )

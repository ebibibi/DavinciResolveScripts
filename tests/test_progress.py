import importlib.util
import io
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).parents[1] / "有償版用スクリプト"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PROGRESS = _load("progress")
HIGHLIGHT_VIDEO = _load("highlight_video")


class FakeClock:
    """A monotonic clock the tests can advance deliberately."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_reporter(**overrides):
    stream = io.StringIO()
    clock = FakeClock()
    defaults = {
        "enabled": True,
        "heartbeat_seconds": 3600.0,
        "echo_interval_seconds": 0.0,
        "clock": clock,
    }
    reporter = PROGRESS.ProgressReporter(stream, **{**defaults, **overrides})
    return reporter, stream, clock


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00"), (9.4, "00:09"), (61, "01:01"), (3600, "1:00:00"), (-5, "00:00")],
)
def test_format_clock_scales_to_the_span(seconds: float, expected: str) -> None:
    assert PROGRESS.format_clock(seconds) == expected


def test_parse_media_position_reads_the_ffmpeg_clock() -> None:
    line = "frame= 900 fps=30 q=24.0 size=1024kB time=00:02:03.50 bitrate=1000.0kbits/s"
    assert PROGRESS.parse_media_position(line) == pytest.approx(123.5)


def test_parse_media_position_reads_a_transcript_timestamp() -> None:
    assert PROGRESS.parse_media_position("[00:20.000 --> 00:24.500]  text") == 24.5


def test_parse_media_position_ignores_unrelated_lines() -> None:
    assert PROGRESS.parse_media_position("Loading the Whisper model") is None


def test_parse_percent_rejects_impossible_values() -> None:
    assert PROGRESS.parse_percent("  42.5% cutting") == pytest.approx(42.5)
    assert PROGRESS.parse_percent("error 500%") is None


def test_a_stage_reports_its_start_and_elapsed_time() -> None:
    reporter, stream, clock = make_reporter()

    reporter.start_stage("Removing silence", step=1, steps=4)
    clock.advance(75.0)
    result = reporter.finish_stage("cut_master.mp4")

    text = stream.getvalue()
    assert "[1/4] Removing silence ... started" in text
    assert "done in 01:15 (cut_master.mp4)" in text
    assert result.seconds == pytest.approx(75.0)
    assert reporter.results[0].label == "Removing silence"


def test_progress_lines_show_percent_and_eta_against_the_duration() -> None:
    reporter, stream, clock = make_reporter()
    reporter.start_stage("Rendering", step=4, steps=4, total_seconds=1000.0)

    clock.advance(60.0)
    reporter.child_output("frame=1 time=00:04:10.00 bitrate=1kbits/s\r")

    line = stream.getvalue().splitlines()[-1]
    assert "25.0%" in line
    assert "04:10 / 16:40" in line
    assert "elapsed 01:00" in line
    assert "eta 03:00" in line


def test_repeated_progress_lines_are_throttled_but_plain_lines_are_not() -> None:
    reporter, stream, clock = make_reporter(echo_interval_seconds=5.0)
    reporter.start_stage("Cutting", step=1, steps=4)

    reporter.child_output("10% cutting")
    reporter.child_output("11% cutting")
    clock.advance(6.0)
    reporter.child_output("12% cutting")
    reporter.child_output("Timeline is empty")

    text = stream.getvalue()
    assert "10.0%" in text
    assert "11.0%" not in text
    assert "12.0%" in text
    assert "| Timeline is empty" in text


def test_a_silent_stage_still_reports_that_it_is_alive() -> None:
    reporter, stream, _ = make_reporter(heartbeat_seconds=0.05, clock=time.monotonic)

    reporter.start_stage("Choosing highlights", step=4, steps=5)
    time.sleep(1.3)
    reporter.finish_stage()

    assert "still no output" in stream.getvalue()


def test_a_disabled_reporter_stays_completely_silent() -> None:
    reporter, stream, _ = make_reporter(enabled=False)

    reporter.start_stage("Rendering", step=1, steps=1)
    reporter.child_output("50% done")
    reporter.warn("something")
    reporter.finish_stage()

    assert stream.getvalue() == ""


def test_an_unencodable_character_does_not_silence_the_report() -> None:
    class NarrowStream(io.StringIO):
        def write(self, text: str) -> int:
            text.encode("ascii")
            return super().write(text)

    stream = NarrowStream()
    reporter = PROGRESS.ProgressReporter(stream, heartbeat_seconds=3600.0)

    reporter.warn("結論を先に見せる")
    reporter.warn("plain warning")

    assert "plain warning" in stream.getvalue()


def test_streaming_echoes_child_output_and_keeps_it_for_diagnostics() -> None:
    reporter, stream, _ = make_reporter()
    reporter.start_stage("Cutting", step=1, steps=1)

    result = HIGHLIGHT_VIDEO._run(
        [sys.executable, "-c", "print('hello from the child')"],
        reporter=reporter,
    )

    assert "hello from the child" in result.stdout
    assert "| hello from the child" in stream.getvalue()


def test_streaming_reports_a_failure_with_the_captured_output() -> None:
    reporter, _, _ = make_reporter()
    reporter.start_stage("Cutting", step=1, steps=1)
    command = [sys.executable, "-c", "print('Timeline is empty'); raise SystemExit(1)"]

    with pytest.raises(subprocess.CalledProcessError) as failure:
        HIGHLIGHT_VIDEO._run(command, reporter=reporter)

    assert "Timeline is empty" in failure.value.stdout


def test_a_carriage_return_progress_bar_arrives_as_separate_updates() -> None:
    reporter, stream, _ = make_reporter()
    reporter.start_stage("Cutting", step=1, steps=1)
    script = (
        "import sys\n"
        "for value in (10, 55, 99):\n"
        "    sys.stdout.write(f'  {value}% cutting\\r')\n"
        "    sys.stdout.flush()\n"
    )

    HIGHLIGHT_VIDEO._run([sys.executable, "-c", script], reporter=reporter)

    text = stream.getvalue()
    assert "10.0%" in text
    assert "99.0%" in text


def test_the_summary_lists_every_stage() -> None:
    reporter, stream, clock = make_reporter()
    reporter.start_stage("First", step=1, steps=2)
    clock.advance(30.0)
    reporter.finish_stage()
    reporter.start_stage("Second", step=2, steps=2)
    clock.advance(90.0)
    reporter.finish_stage()

    reporter.summary()

    text = stream.getvalue()
    assert "Total elapsed 02:00" in text
    assert "00:30  First" in text
    assert "01:30  Second" in text

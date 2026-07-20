import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "有償版用スクリプト" / "highlight_video.py"
SPEC = importlib.util.spec_from_file_location(
    "highlight_video_integration", SCRIPT_PATH
)
HIGHLIGHT_VIDEO = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(HIGHLIGHT_VIDEO)


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg integration tools are unavailable",
)
def test_ffmpeg_output_contains_highlights_and_the_complete_body(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cut_master.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=6",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subtitle = tmp_path / "opening.ass"
    HIGHLIGHT_VIDEO.write_opening_ass(
        subtitle,
        title="Highlight first",
        display_seconds=2.0,
        resolution=(320, 180),
        font_name="DejaVu Sans",
        font_size=28,
    )
    plan = HIGHLIGHT_VIDEO.HighlightPlan(
        "Highlight first",
        (
            HIGHLIGHT_VIDEO.Highlight(1.0, 2.0, "first"),
            HIGHLIGHT_VIDEO.Highlight(4.0, 5.0, "second"),
        ),
    )
    output = tmp_path / "highlighted.mp4"

    HIGHLIGHT_VIDEO.render_highlight_video(source, subtitle, output, plan)
    info = HIGHLIGHT_VIDEO.probe_video(output)

    assert output.stat().st_size > 0
    assert info.width == 320
    assert info.height == 180
    assert info.duration == pytest.approx(8.0, abs=0.25)

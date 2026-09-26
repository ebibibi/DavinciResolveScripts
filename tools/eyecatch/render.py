"""Render branded eyecatch stingers to MP4.

index.html draws one frame at a time on a canvas; headless Chromium is asked for
frame 0, 1, 2 ... and each PNG is piped straight into ffmpeg. The sound comes
from make_audio.py using the same timeline.json, then both are muxed.

    python tools/eyecatch/render.py                  # every variant
    python tools/eyecatch/render.py morph tunnel     # just these
    python tools/eyecatch/render.py --out D:/assets  # somewhere else
"""

from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from make_audio import cue_from_timeline, render as render_audio, write_wav  # noqa: E402

DEFAULT_OUT = HERE / "out"


def _serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    # The logo is sampled with getImageData, which a file:// page is not allowed to do.
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


def _encode_video(page, variant: str, timeline: dict, base: str, video_path: Path) -> None:
    frames = page.evaluate(
        "([config, name, logo]) => window.setup(config, name, logo)",
        [timeline, variant, f"{base}/logo.png"],
    )
    ffmpeg = subprocess.Popen(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "image2pipe", "-framerate", str(timeline["fps"]), "-i", "-",
            "-c:v", "libx264", "-preset", "slow", "-crf", "14",
            "-pix_fmt", "yuv420p", str(video_path),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for frame in range(frames):
            data_url = page.evaluate(
                "(f) => { window.renderFrame(f); return document.getElementById('out').toDataURL('image/png'); }",
                frame,
            )
            ffmpeg.stdin.write(base64.b64decode(data_url.split(",", 1)[1]))
            print(f"\r  {variant}: frame {frame + 1}/{frames}", end="", flush=True)
    finally:
        ffmpeg.stdin.close()
        if ffmpeg.wait() != 0:
            raise RuntimeError(f"ffmpeg failed while encoding {variant}")
    print()


def _mux(video: Path, audio: Path, target: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
            "-movflags", "+faststart", str(target),
        ],
        check=True,
    )


def main() -> int:
    timeline = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("variants", nargs="*", help=f"any of: {', '.join(timeline['variants'])}")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    names = args.variants or list(timeline["variants"])
    unknown = [n for n in names if n not in timeline["variants"]]
    if unknown:
        parser.error(f"unknown variant(s): {', '.join(unknown)}")
    if not shutil.which("ffmpeg"):
        parser.error("ffmpeg is not on PATH")
    args.out.mkdir(parents=True, exist_ok=True)

    server, base = _serve(HERE)
    work = Path(tempfile.mkdtemp(prefix="eyecatch-"))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": timeline["width"], "height": timeline["height"]})
            for name in names:
                page.goto(f"{base}/index.html")
                video = work / f"{name}.video.mp4"
                audio = work / f"{name}.wav"
                _encode_video(page, name, timeline, base, video)
                write_wav(audio, render_audio(cue_from_timeline(timeline, name)))
                output = timeline["variants"][name].get("output", f"EBI_CHAN_EYECATCH_{name}")
                target = args.out / f"{output}.mp4"
                _mux(video, audio, target)
                print(f"  -> {target}")
            browser.close()
    finally:
        server.shutdown()
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

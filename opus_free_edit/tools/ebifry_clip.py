"""えびフライの一言クリップを作る（声＝Gemini TTS Fenrir、口パクするキャラ、透過 .mov）。

使い方: python3 ebifry_clip.py lines.json OUT_DIR
lines.json: [{"id": "g01", "text": "字幕にする文", "spoken": "読み（省略可）", "pose": "standing"}, ...]
pose: standing / glasses / faceup / ageage / rockstar / dark / sleeping
出力: OUT_DIR/<id>.mov（PNG コーデック・アルファ付き・30fps・音声 48kHz）と <id>.wav、clips.json（秒数）
既にある <id>.wav は作り直さない（Gemini は有料・1日100リクエスト）。
画面上の大きさ: 560x520。足元が下端。ffmpeg の overlay でそのまま重ねられる。
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path.home() / "work/ebi-explainer-video"
sys.path.insert(0, str(REPO))
from explainer import char  # noqa: E402
from explainer.config import VoiceConfig  # noqa: E402
from explainer.synth import post_filter  # noqa: E402
from explainer.tts.gemini import Engine  # noqa: E402

FPS, W, H, LEAD, TAIL = 30, 560, 520, 0.25, 0.35
char.CENTER_X, char.FOOT_Y = W // 2, H - 10


def synth(text: str, out: Path) -> None:
    if out.exists():
        return
    raw = out.with_suffix(".raw.wav")
    Engine(VoiceConfig(engine="gemini", voice="Fenrir", pitch=1.07)).synth(text, raw)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw), "-af", post_filter(1.07),
                    "-ar", "48000", "-ac", "1", str(out)], check=True)
    raw.unlink()


def envelope(wav: Path) -> np.ndarray:
    with wave.open(str(wav)) as w:
        sr, x = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    hop = sr // FPS
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x), hop)]) / 32768
    return np.clip(rms / max(rms.max(), 1e-6) * 1.3, 0, 1)


def render(item: dict, out_dir: Path) -> float:
    wav = out_dir / f"{item['id']}.wav"
    synth(item.get("spoken") or item["text"], wav)
    env = envelope(wav)
    n = int((LEAD + len(env) / FPS + TAIL) * FPS)
    pose = item.get("pose", "standing")
    fdir = out_dir / f"_{item['id']}"
    fdir.mkdir(exist_ok=True)
    for f in range(n):
        t = f / FPS
        k = f - int(LEAD * FPS)
        amp = float(env[k]) if 0 <= k < len(env) else 0.0
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        char.draw(frame, t, pose, amp, t, t).save(fdir / f"{f:05d}.png")
    mov = out_dir / f"{item['id']}.mov"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(fdir / "%05d.png"),
                    "-itsoffset", str(LEAD), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "png",
                    "-pix_fmt", "rgba", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                    "-af", "apad", "-t", f"{n / FPS:.3f}", str(mov)], check=True)
    for p in fdir.iterdir():
        p.unlink()
    fdir.rmdir()
    return n / FPS


def main() -> None:
    items = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = out_dir / "clips.json"
    done = json.loads(meta.read_text()) if meta.exists() else {}
    for it in items:
        done[it["id"]] = {"text": it["text"], "pose": it.get("pose", "standing"), "seconds": round(render(it, out_dir), 3)}
        print(it["id"], done[it["id"]]["seconds"], flush=True)
        meta.write_text(json.dumps(done, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

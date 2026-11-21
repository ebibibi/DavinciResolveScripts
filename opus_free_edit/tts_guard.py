"""Make a missing えびフライ voice impossible to overlook.

えびフライ speaks with Gemini TTS (Fenrir). When Gemini cannot be used (prepaid credits depleted = HTTP 402,
daily quota), tools/ebifry_clip.py falls back to Irodori-TTS, which sounds different. On 2026-11-21 that
fallback was only mentioned deep inside EDIT_NOTES.md and the presenter noticed it in the finished video.
There is no check before editing: the Gemini prepayment now tops itself up (2026-11-21), so a test request
per job would only spend money.

Usage:
  tts_guard.py report <job>     after editing: if any cameo used another voice, write out/VOICE_WARNING.md
                                and put a banner at the top of out/EDIT_NOTES.md.
  tts_guard.py announce <job>   after upload: tell Discord again, with the video URL, when VOICE_WARNING.md exists.

Discord target: $NOTIFY_THREAD or $DISCORD_THREAD_ID (the thread that started the job), else the EbiBot channel.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

BOT_ENV_FILES = ("~/claude-code-discord-bridge/.env", "~/discord-bot/.env")
EBIBOT_NOTIFY = os.environ.get("EBIBOT_NOTIFY_URL", "http://127.0.0.1:8099/api/notify")
WARNING = "out/VOICE_WARNING.md"
BANNER_MARK = "<!-- voice-warning -->"
GEMINI_PREFIX = "gemini"

TOP_UP = "AI Studio（https://ai.studio/projects）でプリペイドを追加してください"
REASONS = {
    "credits": f"Gemini TTS のプリペイド残高が切れています（HTTP 402）。{TOP_UP}。",
    "quota": "Gemini TTS の1日上限（100リクエスト）に当たっています。太平洋時間の0時に戻ります。",
    "error": "Gemini TTS が使えません。",
}


# ---------- Discord ----------

def _bot_token() -> str | None:
    for f in BOT_ENV_FILES:
        path = Path(os.path.expanduser(f))
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DISCORD_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"')
    return None


def _post_json(url: str, payload: dict, headers: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    urllib.request.urlopen(req, timeout=15).read()


def notify(message: str) -> bool:
    """Tell the human. A failed notification is printed but never stops the job."""
    thread = os.environ.get("NOTIFY_THREAD") or os.environ.get("DISCORD_THREAD_ID")
    try:
        token = _bot_token() if thread else None
        if thread and token:
            _post_json(f"https://discord.com/api/v10/channels/{thread}/messages", {"content": message[:1900]},
                       {"Authorization": f"Bot {token}", "User-Agent": "DiscordBot (opus_free_edit, 0.1)"})
        else:
            _post_json(EBIBOT_NOTIFY, {"message": message[:1900], "title": "動画編集: えびフライの声"}, {})
        return True
    except Exception as e:  # noqa: BLE001 - notification must not break the edit
        print(f"[tts_guard] notify failed: {e}", flush=True)
        return False


# ---------- report ----------

def clip_voices(job: Path) -> dict[str, str]:
    """Voice of every えびフライ clip, from the clips.json files tools/ebifry_clip.py writes."""
    voices: dict[str, str] = {}
    for meta in sorted((job / "work").rglob("clips.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for cid, info in data.items():
            if isinstance(info, dict):
                voices[f"{meta.parent.name}/{cid}"] = str(info.get("voice") or "unknown")
    return voices


def assess(job: Path) -> str | None:
    """Return a Japanese warning when the video may not use the usual voice, else None."""
    if (job / "work" / "NO_EBIFRY.txt").exists():
        return None
    voices = clip_voices(job)
    other = sorted({v for v in voices.values() if not v.startswith(GEMINI_PREFIX) and v != "unknown"})
    if other:
        n = sum(1 for v in voices.values() if not v.startswith(GEMINI_PREFIX) and v != "unknown")
        return (f"えびフライのセリフ {len(voices)} 本のうち {n} 本が、いつもの Gemini（Fenrir）ではなく"
                f" **{', '.join(other)}** の声です。")
    return None


def report(job: Path) -> str | None:
    warning = assess(job)
    if not warning:
        return None
    cause = REASONS["error"]
    body = (f"# ⚠️ えびフライの声がいつもと違います\n\n{warning}\n\n"
            f"- 原因: {cause}\n"
            f"- 直し方: {TOP_UP}。そのあと `tools/ebifry_clip.py` で作り直し（古い `<id>.wav` を消してから）、"
            "編集スクリプトの描画・音声だけを流し直せば差し替わります。\n")
    (job / "out").mkdir(parents=True, exist_ok=True)
    (job / WARNING).write_text(body, encoding="utf-8")
    notes = job / "out" / "EDIT_NOTES.md"
    old = notes.read_text(encoding="utf-8") if notes.exists() else ""
    if BANNER_MARK not in old:
        banner = f"{BANNER_MARK}\n> [!warning] **えびフライの声がいつもと違います**\n> {warning}\n> 詳細: `out/VOICE_WARNING.md`\n\n"
        notes.write_text(banner + old, encoding="utf-8")
    print(f"[tts_guard] !!! {warning}", flush=True)
    return warning


def announce(job: Path, send=notify) -> bool:
    path = job / WARNING
    if not path.exists():
        return False
    url = ""
    try:
        url = json.loads((job / "out" / "youtube_upload.json").read_text(encoding="utf-8")).get("url", "")
    except (OSError, json.JSONDecodeError):
        pass
    where = f"非公開でアップロードしました: {url}" if url else "（まだアップロードしていません）"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    send(f"⚠️ **完成動画のえびフライの声がいつもと違います**（`{job.name}`）{where}\n" + "\n".join(lines))
    return True


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("report", "announce"):
        print(__doc__, file=sys.stderr)
        return 2
    job = Path(argv[2]).resolve()
    {"report": report, "announce": announce}[argv[1]](job)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

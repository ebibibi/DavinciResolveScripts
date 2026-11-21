"""えびフライの声が Gemini 以外になったら、編集前と完成時に見落とせない形で知らせる（2026-11-21）。"""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

OPUS = Path(__file__).resolve().parents[1] / "opus_free_edit"
sys.path.insert(0, str(OPUS))
import tts_guard  # noqa: E402


class CreditsDepleted(RuntimeError):
    pass


def _job(tmp_path: Path) -> Path:
    for d in ("work", "out"):
        (tmp_path / d).mkdir()
    return tmp_path


def _clips(job: Path, voices: dict, folder: str = "ebifry") -> None:
    d = job / "work" / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "clips.json").write_text(json.dumps({k: {"text": "x", "seconds": 1.0, **({"voice": v} if v else {})}
                                              for k, v in voices.items()}), encoding="utf-8")


# ---------- preflight ----------

def test_preflight_402_notifies_before_editing(tmp_path):
    job = _job(tmp_path)
    sent = []

    def probe():
        raise CreditsDepleted("Gemini TTS のプリペイド残高が尽きました（402）")
    result = tts_guard.preflight(job, probe=probe, send=sent.append)
    assert result["ok"] is False and result["kind"] == "credits"
    assert len(sent) == 1
    assert "えびフライの声がいつもと違う声になります" in sent[0] and "AI Studio" in sent[0]
    saved = json.loads((job / "work" / "tts_preflight.json").read_text(encoding="utf-8"))
    assert saved["kind"] == "credits"


def test_preflight_recognises_402_from_a_plain_http_error(tmp_path):
    def probe():
        raise RuntimeError("HTTP Error 402: Payment Required")
    assert tts_guard.preflight(_job(tmp_path), probe=probe, send=lambda m: None)["kind"] == "credits"


def test_preflight_ok_stays_quiet(tmp_path):
    sent = []
    result = tts_guard.preflight(_job(tmp_path), probe=lambda: None, send=sent.append)
    assert result["ok"] is True and sent == []


# ---------- report ----------

def test_report_flags_fallback_voice_at_the_top_of_edit_notes(tmp_path):
    job = _job(tmp_path)
    (job / "out" / "EDIT_NOTES.md").write_text("# 編集メモ\n本文\n", encoding="utf-8")
    _clips(job, {"e01": "irodori", "e02": "irodori", "e03": "gemini:Fenrir"})
    warning = tts_guard.report(job)
    assert warning and "3 本のうち 2 本" in warning and "irodori" in warning
    notes = (job / "out" / "EDIT_NOTES.md").read_text(encoding="utf-8")
    assert notes.startswith(tts_guard.BANNER_MARK) and "えびフライの声がいつもと違います" in notes.splitlines()[1]
    assert notes.endswith("# 編集メモ\n本文\n")
    assert (job / "out" / "VOICE_WARNING.md").exists()
    tts_guard.report(job)  # rerunning does not stack banners
    assert (job / "out" / "EDIT_NOTES.md").read_text(encoding="utf-8").count(tts_guard.BANNER_MARK) == 1


def test_report_reads_clips_in_any_work_subfolder(tmp_path):
    job = _job(tmp_path)
    _clips(job, {"g01": "irodori"}, folder="cameos/v2")
    assert tts_guard.report(job)


def test_report_silent_when_all_gemini(tmp_path):
    job = _job(tmp_path)
    _clips(job, {"e01": "gemini:Fenrir", "e02": "gemini:Fenrir"})
    assert tts_guard.report(job) is None
    assert not (job / "out" / "VOICE_WARNING.md").exists()


def test_report_warns_when_gemini_failed_and_no_voice_was_recorded(tmp_path):
    """The agent may have made clips some other way: without a record, a failed preflight is enough."""
    job = _job(tmp_path)
    tts_guard.preflight(job, probe=lambda: (_ for _ in ()).throw(CreditsDepleted("402")), send=lambda m: None)
    _clips(job, {"e01": None})
    assert "可能性が高い" in tts_guard.report(job)


def test_report_silent_when_ebifry_was_waived(tmp_path):
    job = _job(tmp_path)
    _clips(job, {"e01": "irodori"})
    (job / "work" / "NO_EBIFRY.txt").write_text("本人が不要と言った", encoding="utf-8")
    assert tts_guard.report(job) is None


# ---------- announce ----------

def test_announce_includes_the_video_url(tmp_path):
    job = _job(tmp_path)
    _clips(job, {"e01": "irodori"})
    tts_guard.report(job)
    (job / "out" / "youtube_upload.json").write_text(json.dumps({"url": "https://youtu.be/abc"}), encoding="utf-8")
    sent = []
    assert tts_guard.announce(job, send=sent.append) is True
    assert "https://youtu.be/abc" in sent[0] and "いつもと違います" in sent[0]


def test_announce_silent_without_warning(tmp_path):
    sent = []
    assert tts_guard.announce(_job(tmp_path), send=sent.append) is False and sent == []


# ---------- notify target ----------

def test_notify_prefers_the_job_thread(monkeypatch):
    calls = []
    monkeypatch.setenv("DISCORD_THREAD_ID", "123")
    monkeypatch.delenv("NOTIFY_THREAD", raising=False)
    monkeypatch.setattr(tts_guard, "_bot_token", lambda: "tok")
    monkeypatch.setattr(tts_guard, "_post_json", lambda url, payload, headers: calls.append(url))
    assert tts_guard.notify("hi") is True
    assert calls == ["https://discord.com/api/v10/channels/123/messages"]


def test_notify_falls_back_to_ebibot_and_never_raises(monkeypatch):
    monkeypatch.delenv("DISCORD_THREAD_ID", raising=False)
    monkeypatch.delenv("NOTIFY_THREAD", raising=False)
    urls = []

    def boom(url, payload, headers):
        urls.append(url)
        raise OSError("down")
    monkeypatch.setattr(tts_guard, "_post_json", boom)
    assert tts_guard.notify("hi") is False
    assert urls == [tts_guard.EBIBOT_NOTIFY]


# ---------- run.sh wiring ----------

def test_run_sh_checks_before_prepare_and_reports_after_the_agent():
    run = (OPUS / "run.sh").read_text(encoding="utf-8")
    assert run.index("tts_guard.py\" preflight") < run.index("prepare.sh\" \"$SOURCE\"")
    assert run.index("usage_report.py") < run.index("tts_guard.py\" report") < run.index("python3 \"$HERE/check_stereo.py\"")
    assert run.index("upload_private.py\" \"$JOB\"") < run.index("tts_guard.py\" announce")


def test_cli_rejects_unknown_command():
    r = subprocess.run([sys.executable, str(OPUS / "tts_guard.py"), "nope", "x"], capture_output=True)
    assert r.returncode == 2


# ---------- ebifry_clip fallback ----------

STUB = {
    "explainer/__init__.py": "",
    "explainer/char.py": "CENTER_X = FOOT_Y = 0\ndef draw(*a, **k):\n    raise NotImplementedError\n",
    "explainer/config.py": "class VoiceConfig:\n    def __init__(self, **kw):\n        self.__dict__.update(kw)\n",
    "explainer/synth.py": "def post_filter(p):\n    return 'anull'\n",
    "explainer/errors.py": ("class PipelineError(RuntimeError): pass\n"
                            "class QuotaExceeded(PipelineError): pass\n"
                            "class CreditsDepleted(PipelineError): pass\n"),
    "explainer/tts/__init__.py": "",
    "explainer/tts/gemini.py": "class Engine:\n    def __init__(self, v):\n        pass\n",
    "explainer/tts/irodori.py": "class Engine:\n    def __init__(self, v):\n        pass\n",
}


@pytest.fixture
def clip(tmp_path, monkeypatch):
    repo = tmp_path / "explainer_repo"
    for rel, body in STUB.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
    monkeypatch.setenv("EBI_EXPLAINER_REPO", str(repo))
    for name in [m for m in sys.modules if m == "explainer" or m.startswith("explainer.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.syspath_prepend(str(OPUS / "tools"))
    mod = importlib.import_module("ebifry_clip")
    mod = importlib.reload(mod)
    monkeypatch.setattr(mod, "_encode", lambda raw, out, filters: out.write_bytes(b"wav"))
    yield mod
    sys.modules.pop("ebifry_clip", None)


def test_clip_falls_back_to_irodori_once_gemini_is_out_of_credits(clip, tmp_path):
    gemini_calls, irodori_calls = [], []

    def gemini(text, raw):
        gemini_calls.append(text)
        raise clip.errors.CreditsDepleted("402")
    clip._gemini = gemini
    clip._irodori = lambda text, raw: irodori_calls.append(text)
    assert clip.synth("ひとつめ", tmp_path / "e01.wav") == "irodori"
    assert clip.synth("ふたつめ", tmp_path / "e02.wav") == "irodori"
    assert gemini_calls == ["ひとつめ"]  # once Gemini is out of credits it is not tried again
    assert irodori_calls == ["ひとつめ", "ふたつめ"]
    assert (tmp_path / "e01.voice").read_text().strip() == "irodori"
    # an existing clip keeps the voice it was made with
    assert clip.synth("ひとつめ", tmp_path / "e01.wav") == "irodori"


def test_clip_uses_gemini_when_it_works(clip, tmp_path):
    clip._gemini = lambda text, raw: None
    clip._irodori = lambda text, raw: pytest.fail("must not fall back")
    assert clip.synth("やあ", tmp_path / "g.wav") == "gemini:Fenrir"


def test_clip_does_not_hide_other_gemini_errors(clip, tmp_path):
    def gemini(text, raw):
        raise clip.errors.PipelineError("400 bad request")
    clip._gemini = gemini
    with pytest.raises(clip.errors.PipelineError):
        clip.synth("やあ", tmp_path / "g.wav")

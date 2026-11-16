import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "opus_free_edit"))
import check_ebifry  # noqa: E402


def _srt(*texts: str) -> str:
    return "\n\n".join(f"{i}\n00:00:0{i},000 --> 00:00:0{i},900\n{t}" for i, t in enumerate(texts, 1)) + "\n"


def _job(tmp_path: Path, srt: str | None = None, waiver: str | None = None) -> Path:
    (tmp_path / "out").mkdir()
    (tmp_path / "work").mkdir()
    if srt is not None:
        (tmp_path / "out" / "captions.srt").write_text(srt, encoding="utf-8")
    if waiver is not None:
        (tmp_path / "work" / "NO_EBIFRY.txt").write_text(waiver, encoding="utf-8")
    return tmp_path


def test_counts_only_cues_starting_with_prefix():
    srt = _srt("えびフライ：ほんとに？", "今日はえびフライの話ではない", "えびフライ：胡田さん、\n熱いね", "普通の字幕")
    assert check_ebifry.count_cameos(srt) == 2


def test_passes_with_three_cameos(tmp_path):
    job = _job(tmp_path, _srt("えびフライ：a", "本編", "えびフライ：b", "えびフライ：c"))
    assert check_ebifry.check(job)[0] == 0


def test_fails_with_too_few_cameos(tmp_path):
    job = _job(tmp_path, _srt("えびフライ：a", "本編", "えびフライ：b"))
    code, message = check_ebifry.check(job)
    assert code == 1 and "only 2" in message


def test_missing_captions_is_an_error(tmp_path):
    assert check_ebifry.check(_job(tmp_path))[0] == 2


def test_waiver_with_reason_skips_the_check(tmp_path):
    job = _job(tmp_path, _srt("本編"), waiver="「今回はえびフライなしで」と収録中に指示")
    assert check_ebifry.check(job)[0] == 0


def test_empty_waiver_does_not_count(tmp_path):
    job = _job(tmp_path, _srt("本編"), waiver="  \n")
    assert check_ebifry.check(job)[0] == 1

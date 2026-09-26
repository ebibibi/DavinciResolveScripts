"""Where the clips appended after the edited body come from."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

import ending_media

REPO_ROOT = Path(__file__).parents[1]
SCRIPT_DIR = REPO_ROOT / "有償版用スクリプト"
FREE_SCRIPT_DIR = REPO_ROOT / "無料版用スクリプト"


def test_the_onedrive_end_card_is_preferred_over_the_bundled_copy(tmp_path):
    missing, onedrive = tmp_path / "old", tmp_path / "new"
    onedrive.mkdir()
    (onedrive / ending_media.OUTRO_FILE_NAME).write_bytes(b"")
    bundled = tmp_path / "assets" / ending_media.OUTRO_FILE_NAME
    bundled.parent.mkdir()
    bundled.write_bytes(b"")

    found = ending_media.find_outro_video([str(missing), str(onedrive)], bundled)

    assert found == str(onedrive / ending_media.OUTRO_FILE_NAME)


def test_the_bundled_end_card_is_used_when_onedrive_has_none(tmp_path):
    bundled = tmp_path / ending_media.OUTRO_FILE_NAME
    bundled.write_bytes(b"")

    found = ending_media.find_outro_video([str(tmp_path / "missing")], bundled)

    assert found == str(bundled)


def test_no_end_card_anywhere_is_reported_as_none(tmp_path):
    assert ending_media.find_outro_video([str(tmp_path)], tmp_path / "none.mp4") is None


def test_the_end_card_is_looked_for_in_the_same_folders_as_the_ending_clip():
    endings = ending_media.material_candidates(ending_media.ENDING_FILE_NAME)
    outros = ending_media.outro_candidates()

    assert [Path(p).parent for p in outros[:-1]] == [Path(p).parent for p in endings]
    assert outros[-1] == str(ending_media.BUNDLED_OUTRO_PATH)


def test_the_bundled_end_card_is_committed_and_small_enough_to_pull():
    bundled = ending_media.BUNDLED_OUTRO_PATH

    assert bundled == REPO_ROOT / "assets" / "EBI_CHAN_OUTRO.mp4"
    assert bundled.is_file()
    assert bundled.stat().st_size < 25 * 1024 * 1024


def probe(stream: str, entries: str) -> dict[str, str]:
    output = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", stream,
            "-show_entries", entries,
            "-of", "default=noprint_wrappers=1",
            str(ending_media.BUNDLED_OUTRO_PATH),
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    return dict(re.findall(r"^(\w+)=(.*)$", output, re.MULTILINE))


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not available")
def test_the_bundled_end_card_is_20_seconds_of_1080p60_with_stereo_sound():
    video = probe("v:0", "stream=width,height,r_frame_rate,pix_fmt:format=duration")
    audio = probe("a:0", "stream=channels")

    assert (video["width"], video["height"]) == ("1920", "1080")
    assert video["r_frame_rate"] == "60/1"
    assert video["pix_fmt"] == "yuv420p"
    assert abs(float(video["duration"]) - 20.0) < 0.1
    assert audio["channels"] == "2"


def _position(content: str, needle: str) -> int:
    index = content.find(needle)
    assert index >= 0, f"{needle!r} not found"
    return index


def test_the_stable_route_appends_the_end_card_after_the_ending_clip():
    content = (SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")

    ending = _position(content, 'append_closing_clip(media_pool, ending_video_path')
    outro = _position(content, 'append_closing_clip(media_pool, outro_video_path')
    # Both land on the imported timeline before its clips are copied into main.
    copy = _position(content, "XMLタイムラインの内容をmainタイムラインに挿入します")
    assert ending < outro < copy


def test_the_free_route_appends_the_end_card_after_the_ending_clip():
    content = (FREE_SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")

    ending = _position(content, "'mediaPoolItem': ending_clip")
    outro = _position(content, "'mediaPoolItem': outro_clip")
    copy = _position(content, "新しいタイムラインをメインタイムラインに挿入します")
    assert "find_outro_video()" in content
    assert ending < outro < copy

"""mvp_logo.py: the real embroidered MVP logo is detected, pasted and enforced.

Fixtures are 1280x720 JPEG copies of real frames and thumbnails (2026-11-21 job, where a regenerated
thumbnail lost the logo and was uploaded; other recordings in a T-shirt, a sweater, and with the
logo cut off by the bottom edge). Needs the YuNet face model (downloaded once to ~/.cache/opencv).
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "opus_free_edit"))
import ai_thumbnail  # noqa: E402
import mvp_logo  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "mvp_logo"
RUN_SH = Path(__file__).resolve().parents[1] / "opus_free_edit" / "run.sh"
BRIEF = Path(__file__).resolve().parents[1] / "opus_free_edit" / "brief.md"


def image(name: str) -> np.ndarray:
    bgr = cv2.imread(str(FIXTURES / name))
    assert bgr is not None, name
    return bgr


def test_logo_found_in_the_source_frame_with_its_position():
    match = mvp_logo.find_logo(image("frame_logo.jpg"))
    assert match.found
    x0, y0, x1, y1 = match.box
    # on his left chest, below the face, about as wide as 0.57 face widths
    assert 700 < x0 < 800 and 600 < y0 < 650 and 120 < x1 - x0 < 150


@pytest.mark.parametrize("name", ["frame_tshirt.jpg", "frame_sweater.jpg"])
def test_no_logo_on_other_clothes(name):
    match = mvp_logo.find_logo(image(name))
    assert not match.found
    assert match.inliers < mvp_logo.MIN_INLIERS


@pytest.mark.parametrize("name", ["ai_raw_no_logo.jpg", "thumbnail_no_logo.jpg"])
def test_generated_shirt_has_no_logo(name):
    assert not mvp_logo.find_logo(image(name)).found


def test_hand_fixed_thumbnail_has_the_logo():
    assert mvp_logo.find_logo(image("thumbnail_fixed.jpg")).found


def test_paste_puts_the_real_logo_on_the_shirt():
    frame = image("frame_logo.jpg")
    raw = cv2.resize(image("ai_raw_no_logo.jpg"), (1280, 720))
    pasted = mvp_logo.paste_logo(frame, raw)
    match = mvp_logo.find_logo(pasted)
    assert match.found and match.ncc > 0.9
    x0, y0, x1, y1 = match.box
    assert 1000 < x0 < 1100 and 540 < y0 < 620  # his left chest in the generated picture
    changed = np.argwhere(np.abs(pasted.astype(int) - raw.astype(int)).max(2) > 0)
    (cy0, cx0), (cy1, cx1) = changed.min(0), changed.max(0)
    assert cx1 - cx0 < 200 and cy1 - cy0 < 120  # only the logo and a margin of shirt were touched
    assert not np.shares_memory(pasted, raw)


def test_paste_refuses_a_logo_cut_off_by_the_frame():
    with pytest.raises(mvp_logo.MvpLogoError, match="cut off"):
        mvp_logo.paste_logo(image("frame_logo_cut_off.jpg"), image("ai_raw_no_logo.jpg"))


def test_paste_refuses_without_a_logo_in_the_source():
    with pytest.raises(mvp_logo.MvpLogoError, match="no MVP logo"):
        mvp_logo.paste_logo(image("frame_tshirt.jpg"), image("ai_raw_no_logo.jpg"))


def test_check_rejects_the_uploaded_thumbnail_without_the_logo():
    problems = mvp_logo.check(FIXTURES / "thumbnail_no_logo.jpg", [("frame", image("frame_logo.jpg"))])
    assert problems and "MVP logo" in problems[0]


def test_check_passes_the_fixed_thumbnail():
    assert mvp_logo.check(FIXTURES / "thumbnail_fixed.jpg", [("frame", image("frame_logo.jpg"))]) == []


def test_check_requires_nothing_when_he_wears_other_clothes():
    sources = [("tshirt", image("frame_tshirt.jpg")), ("sweater", image("frame_sweater.jpg"))]
    assert mvp_logo.check(FIXTURES / "thumbnail_no_logo.jpg", sources) == []


def test_any_source_with_the_logo_makes_it_required():
    sources = [("tshirt", image("frame_tshirt.jpg")), ("recording", image("frame_logo_cut_off.jpg"))]
    assert mvp_logo.check(FIXTURES / "thumbnail_no_logo.jpg", sources)


def test_default_sources_are_the_job_frames_and_recording(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "input").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "work" / "thumbnail_frame.png").write_bytes(b"x")
    (tmp_path / "work" / "thumbnail_ai_frame.png").write_bytes(b"x")
    (tmp_path / "input" / "source.mkv").write_bytes(b"x")
    frames, video = mvp_logo.default_sources(tmp_path / "out" / "thumbnail.png")
    assert [f.name for f in frames] == ["thumbnail_frame.png", "thumbnail_ai_frame.png"]
    assert video == tmp_path / "input" / "source.mkv"


def test_ai_thumbnail_always_pastes_the_logo_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_thumbnail, "LOGO", tmp_path / "missing-channel-logo.png")
    out = tmp_path / "out" / "thumbnail.png"
    ai_thumbnail.finish(FIXTURES / "ai_raw_no_logo.jpg", out, FIXTURES / "frame_logo.jpg")
    assert mvp_logo.find_logo(cv2.imread(str(out))).found


def test_ai_thumbnail_leaves_other_clothes_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_thumbnail, "LOGO", tmp_path / "missing-channel-logo.png")
    out = tmp_path / "thumbnail.png"
    ai_thumbnail.finish(FIXTURES / "ai_raw_no_logo.jpg", out, FIXTURES / "frame_tshirt.jpg")
    assert not mvp_logo.find_logo(cv2.imread(str(out))).found


def test_ai_thumbnail_fails_when_the_logo_cannot_be_pasted(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_thumbnail, "LOGO", tmp_path / "missing-channel-logo.png")
    out = tmp_path / "thumbnail.png"
    with pytest.raises(mvp_logo.MvpLogoError):
        ai_thumbnail.finish(FIXTURES / "ai_raw_no_logo.jpg", out, FIXTURES / "frame_logo_cut_off.jpg")
    assert not out.exists()  # nothing without the logo is written


def test_run_sh_gates_the_upload_on_the_logo():
    text = RUN_SH.read_text(encoding="utf-8")
    assert '"$HERE/mvp_logo.py"' in text.split("log \"agent edit")[0]  # copied into the job for the agent
    gate = text.index('mvp_logo.py" check out/thumbnail.png')
    assert gate < text.index("upload_private.py")


def test_brief_names_the_one_command_check():
    assert "python3 mvp_logo.py check out/thumbnail.png" in BRIEF.read_text(encoding="utf-8")

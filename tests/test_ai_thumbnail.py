"""ai_thumbnail.py: prompt, face crop and logo placement (no image generation)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "opus_free_edit"))
import ai_thumbnail as at  # noqa: E402


def test_prompt_contains_texts_and_keeps_the_face():
    prompt = at.build_prompt("EWS廃止", sub="Exchange Online", badge="MS週報", motif="a cracked server")
    assert '"MS週報"' in prompt and '"EWS廃止"' in prompt and '"Exchange Online"' in prompt
    assert "a cracked server" in prompt
    assert "do not change the expression" in prompt
    assert prompt.index("MS週報") < prompt.index("EWS廃止")  # badge listed first


def test_prompt_without_badge_or_sub():
    prompt = at.build_prompt("EWS廃止")
    assert "badge" not in prompt and "smaller line" not in prompt
    assert "1. A huge main headline" in prompt


def test_face_crop_box_is_clamped():
    assert at.face_crop_box((100, 50, 100, 120), 400, 300) == (0, 0, 320, 300)
    assert at.face_crop_box((800, 300, 200, 200), 1920, 1080) == (560, 100, 1240, 900)


def test_logo_prefers_top_right():
    assert at.pick_logo_corner((300, 200, 600, 600)) == (1280 - 100 - 16, 16)


def test_logo_skipped_when_head_reaches_top_right():
    assert at.pick_logo_corner((900, 0, 1280, 500)) is None


def test_prompt_reserves_the_logo_corner():
    assert "top-right corner" in at.build_prompt("EWS廃止")


def test_logo_top_right_without_face():
    assert at.pick_logo_corner(None) == (1280 - 100 - 16, 16)


def test_logo_fits_next_to_a_face_on_the_right():
    # 2026-10-05 generation: face 885,148 248x365; the corner above-right of the hair is empty
    keepout = at.logo_keepout((885, 148, 248, 365))
    assert keepout == (861, 57, 1157, 513)
    assert at.pick_logo_corner(keepout) == (1164, 16)

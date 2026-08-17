"""Tests for the FFmpeg-only advanced editing route."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "有償版用スクリプト"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import advanced_video_editor as editor  # noqa: E402
from ass_render import build_ass  # noqa: E402
from edit_plan import (  # noqa: E402
    Chapter,
    EditPlan,
    build_captions,
    build_local_chapters,
    parse_editorial_output,
    parse_structured_json,
    split_caption_text,
)
from highlight_plan import Highlight  # noqa: E402
from sound_design import build_sfx_command, build_sound_cues  # noqa: E402
from timeline import BODY, HIGHLIGHT, build_timeline, map_range, total_duration  # noqa: E402


def segment(start: float, end: float, text: str) -> dict[str, object]:
    return {"start": start, "end": end, "text": text}


TRANSCRIPT = [
    segment(0.0, 4.0, "今日はffmpegだけで動画編集を全部やる話です。"),
    segment(10.0, 14.0, "結論から言うと、編集時間は3分の1になりました。"),
    segment(60.0, 64.0, "ここからは実際のコードを見ていきます。"),
    segment(120.0, 124.0, "重要なのはタイムラインの写像です。"),
]


# --- timeline ---------------------------------------------------------------


def test_timeline_places_highlights_before_the_complete_body():
    slices = build_timeline((Highlight(10.0, 14.0, "a"), Highlight(120.0, 124.0, "b")), 300.0)
    assert [item.kind for item in slices] == [HIGHLIGHT, HIGHLIGHT, BODY]
    assert [item.output_start for item in slices] == [0.0, 4.0, 8.0]
    assert total_duration(slices) == pytest.approx(308.0)


def test_body_is_never_shortened_by_copying_highlights():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    body = slices[-1]
    assert (body.source_start, body.source_end) == (0.0, 300.0)


def test_a_copied_moment_is_shown_in_both_places():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    placements = map_range(slices, 11.0, 13.0)
    assert placements == ((1.0, 3.0), (15.0, 17.0))


def test_a_partially_copied_range_is_clipped_not_dropped():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    placements = map_range(slices, 13.0, 20.0)
    assert placements[0] == pytest.approx((3.0, 4.0))
    assert placements[1] == pytest.approx((17.0, 24.0))


def test_chapter_cards_can_be_restricted_to_the_body():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    assert map_range(slices, 11.0, 13.0, kinds=(BODY,)) == ((15.0, 17.0),)


def test_a_timeline_without_highlights_is_just_the_body():
    slices = build_timeline((), 120.0)
    assert len(slices) == 1
    assert map_range(slices, 5.0, 7.0) == ((5.0, 7.0),)


# --- captions ---------------------------------------------------------------


def test_captions_break_on_sentences_before_length():
    pieces = split_caption_text("これは一文目です。これは二文目です。", maximum=40)
    assert pieces == ["これは一文目です。", "これは二文目です。"]


def test_a_long_sentence_is_cut_to_the_display_width():
    pieces = split_caption_text("あ" * 95, maximum=40)
    assert [len(piece) for piece in pieces] == [40, 40, 15]


def test_caption_pieces_share_the_segment_time_in_order():
    captions = build_captions(
        [segment(10.0, 20.0, "前半の話です。後半の話です。")], video_duration=300.0
    )
    assert len(captions) == 2
    assert captions[0].start == pytest.approx(10.0)
    assert captions[1].end <= 20.0
    assert captions[0].end == pytest.approx(captions[1].start)


def test_captions_never_run_past_the_video():
    captions = build_captions([segment(9.0, 30.0, "終わりの話。")], video_duration=10.0)
    assert captions[-1].end <= 10.0


# --- AI plan validation -----------------------------------------------------


def test_ai_chapters_and_telops_are_grounded_in_real_segments():
    chapters, telops = parse_editorial_output(
        {
            "chapters": [
                {"segment_index": 2, "title": "実装を見る"},
                {"segment_index": 99, "title": "存在しない章"},
            ],
            "telops": [{"segment_index": 1, "text": "編集時間は3分の1"}],
        },
        TRANSCRIPT,
        video_duration=300.0,
        maximum_chapters=6,
        maximum_telops=10,
        minimum_chapter_gap_seconds=30.0,
        telop_minimum_seconds=1.2,
        telop_maximum_seconds=4.0,
    )
    assert [item.title for item in chapters] == ["実装を見る"]
    assert chapters[0].start == pytest.approx(60.0)
    assert [item.text for item in telops] == ["編集時間は3分の1"]
    assert telops[0].start == pytest.approx(10.0)


def test_chapters_closer_than_the_minimum_gap_are_dropped():
    chapters, _ = parse_editorial_output(
        {
            "chapters": [
                {"segment_index": 0, "title": "はじめに"},
                {"segment_index": 1, "title": "すぐ次の章"},
            ],
            "telops": [],
        },
        TRANSCRIPT,
        video_duration=300.0,
        maximum_chapters=6,
        maximum_telops=10,
        minimum_chapter_gap_seconds=120.0,
        telop_minimum_seconds=1.2,
        telop_maximum_seconds=4.0,
    )
    assert len(chapters) == 1


def test_overlapping_telops_are_dropped():
    _, telops = parse_editorial_output(
        {
            "chapters": [],
            "telops": [
                {"segment_index": 0, "text": "ひとつめ"},
                {"segment_index": 0, "text": "同じ場所"},
            ],
        },
        TRANSCRIPT,
        video_duration=300.0,
        maximum_chapters=6,
        maximum_telops=10,
        minimum_chapter_gap_seconds=30.0,
        telop_minimum_seconds=1.2,
        telop_maximum_seconds=4.0,
    )
    assert len(telops) == 1


def test_structured_output_is_read_from_a_nested_result_string():
    payload = json.dumps(
        {"result": json.dumps({"main_takeaway": "要点", "chapters": []}, ensure_ascii=False)}
    )
    assert parse_structured_json(payload)["main_takeaway"] == "要点"


def test_local_chapters_only_appear_on_long_videos():
    assert build_local_chapters(TRANSCRIPT, video_duration=300.0, maximum_chapters=6) == ()
    chapters = build_local_chapters(
        [segment(index * 60.0, index * 60.0 + 4.0, f"話題{index}") for index in range(30)],
        video_duration=1800.0,
        maximum_chapters=6,
    )
    assert len(chapters) >= 2


# --- ASS --------------------------------------------------------------------


def build_sample_plan() -> EditPlan:
    return EditPlan(
        title="ffmpegだけで編集は完結する",
        highlights=(Highlight(10.0, 14.0, "結論"),),
        chapters=(Chapter(60.0, "実装を見る"),),
        telops=(editor.Telop(10.0, 13.0, "編集時間は3分の1"),),
        captions=build_captions(TRANSCRIPT, video_duration=300.0),
    )


def test_ass_contains_every_layer_once_mapped():
    plan = build_sample_plan()
    slices = build_timeline(plan.highlights, 300.0)
    content = build_ass(
        plan,
        slices,
        resolution=(1920, 1080),
        font_name="Noto Sans CJK JP",
        takeaway_font_size=96,
        takeaway_seconds=4.0,
        chapter_seconds=3.5,
        body_duration=300.0,
    )
    assert "Style: Takeaway" in content and "Style: Caption" in content
    assert content.count("ffmpegだけで編集は完結する") == 1
    # The telop sits inside the copied highlight, so it is drawn twice.
    # Match the telop event itself: the caption of the same sentence contains
    # the identical words.
    assert content.count(r"{\fad(150,200)}編集時間は3分の1") == 2
    # The chapter card belongs to the body only.
    assert content.count("1. 実装を見る") == 1


def test_ass_braces_cannot_escape_into_override_tags():
    plan = EditPlan(title="{\\an8}偽のタグ")
    content = build_ass(
        plan,
        build_timeline((), 10.0),
        resolution=(1920, 1080),
        font_name="Noto Sans CJK JP",
        takeaway_font_size=96,
        takeaway_seconds=2.0,
        chapter_seconds=3.5,
        body_duration=10.0,
    )
    assert r"\{" in content and "{\\an8}偽" not in content


def test_font_sizes_scale_with_the_frame_height():
    plan = EditPlan(title="タイトル")
    small = build_ass(
        plan,
        build_timeline((), 10.0),
        resolution=(1280, 720),
        font_name="Noto Sans CJK JP",
        takeaway_font_size=96,
        takeaway_seconds=2.0,
        chapter_seconds=3.5,
        body_duration=10.0,
    )
    assert "Style: Takeaway,Noto Sans CJK JP,64," in small


# --- sound design -----------------------------------------------------------


def test_sound_cues_mark_every_cut_and_chapter():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    cues = build_sound_cues(slices, (Chapter(60.0, "章"),))
    kinds = [cue.kind for cue in cues]
    assert kinds == ["whoosh", "ding"]
    # The chapter is at 60s in the body, which starts 4s into the finished cut.
    assert cues[1].at == pytest.approx(64.0)


def test_sfx_command_delays_each_cue_and_keeps_levels():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    cues = build_sound_cues(slices, (Chapter(60.0, "章"),))
    command = build_sfx_command(cues, Path("/tmp/sfx.wav"))
    joined = " ".join(command)
    assert "adelay=4000:all=1" in joined
    assert "adelay=64000:all=1" in joined
    assert "normalize=0" in joined


def test_sfx_command_refuses_an_empty_cue_list():
    with pytest.raises(ValueError):
        build_sfx_command((), Path("/tmp/sfx.wav"))


# --- render command ---------------------------------------------------------


def test_render_command_trims_highlights_and_keeps_the_whole_body():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    command = editor.build_render_command(
        Path("/tmp/cut.mp4"), Path("/tmp/overlays.ass"), Path("/tmp/out.mp4"), slices
    )
    graph = command[command.index("-filter_complex") + 1]
    assert "trim=start=10.000:end=14.000" in graph
    assert "[0:v]setpts=PTS-STARTPTS[v1]" in graph
    assert "concat=n=2:v=1:a=1[basev][basea]" in graph
    assert "ass=overlays.ass[outv]" in graph
    assert "amix" not in graph


def test_render_command_mixes_the_sound_track_without_ducking_speech():
    slices = build_timeline((), 300.0)
    command = editor.build_render_command(
        Path("/tmp/cut.mp4"),
        Path("/tmp/overlays.ass"),
        Path("/tmp/out.mp4"),
        slices,
        sfx=Path("/tmp/sfx.wav"),
    )
    graph = command[command.index("-filter_complex") + 1]
    assert "[basea][1:a]amix=inputs=2:normalize=0:duration=first" in graph
    assert command.count("-i") == 2


# --- plan assembly ----------------------------------------------------------


def test_build_edit_plan_falls_back_to_local_selection_without_ai():
    plan = editor.build_edit_plan(
        TRANSCRIPT,
        video_duration=300.0,
        config=editor.PipelineConfig(),
        advanced=editor.AdvancedConfig(),
        ai_data=None,
    )
    assert plan.highlights
    assert "local_highlights" in plan.notes
    assert plan.captions
    assert plan.telops == ()


def test_build_edit_plan_uses_the_ai_answer_when_it_validates():
    plan = editor.build_edit_plan(
        TRANSCRIPT,
        video_duration=300.0,
        config=editor.PipelineConfig(),
        advanced=editor.AdvancedConfig(minimum_chapter_gap_seconds=30.0),
        ai_data={
            "main_takeaway": "編集は全部プログラムでできる",
            "highlight_segment_indexes": [1],
            "chapters": [{"segment_index": 2, "title": "実装"}],
            "telops": [{"segment_index": 1, "text": "3分の1に短縮"}],
        },
    )
    assert plan.title == "編集は全部プログラムでできる"
    assert plan.highlights[0].start == pytest.approx(9.5)
    assert [item.title for item in plan.chapters] == ["実装"]
    assert [item.text for item in plan.telops] == ["3分の1に短縮"]
    assert "ai_edit_plan" in plan.notes


def test_disabled_layers_are_really_empty():
    plan = editor.build_edit_plan(
        TRANSCRIPT,
        video_duration=300.0,
        config=editor.PipelineConfig(),
        advanced=editor.AdvancedConfig(captions=False, telops=False, chapters=False),
        ai_data={
            "main_takeaway": "要点",
            "highlight_segment_indexes": [1],
            "chapters": [{"segment_index": 2, "title": "実装"}],
            "telops": [{"segment_index": 1, "text": "3分の1"}],
        },
    )
    assert plan.captions == () and plan.telops == () and plan.chapters == ()


def test_advanced_config_reads_its_own_section(tmp_path: Path):
    config_file = tmp_path / "config.local.json"
    config_file.write_text(
        json.dumps(
            {
                "working_dirs": [str(tmp_path)],
                "opening_highlight": {"maximum_highlights": 2},
                "advanced_edit": {"captions": False, "maximum_telops": 5},
            }
        ),
        encoding="utf-8",
    )
    _, _, config, advanced = editor.load_advanced_config(config_file)
    assert config.maximum_highlights == 2
    assert advanced.captions is False
    assert advanced.maximum_telops == 5


def test_a_chapter_landing_on_a_cut_does_not_fire_two_effects():
    slices = build_timeline((Highlight(10.0, 14.0, "a"),), 300.0)
    # The chapter starts at the very first frame of the body, which is also
    # where the reel cuts away.
    cues = build_sound_cues(slices, (Chapter(0.0, "本編"),))
    assert [cue.kind for cue in cues] == ["whoosh"]


def test_the_mix_is_limited_so_an_effect_cannot_clip_a_loud_word():
    command = editor.build_render_command(
        Path("/tmp/cut.mp4"),
        Path("/tmp/overlays.ass"),
        Path("/tmp/out.mp4"),
        build_timeline((), 60.0),
        sfx=Path("/tmp/sfx.wav"),
    )
    graph = command[command.index("-filter_complex") + 1]
    assert "alimiter=limit=0.95[outa]" in graph

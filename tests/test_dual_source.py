import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "有償版用スクリプト" / "dual_source.py"
SPEC = importlib.util.spec_from_file_location("dual_source", SCRIPT_PATH)
DUAL_SOURCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["dual_source"] = DUAL_SOURCE
SPEC.loader.exec_module(DUAL_SOURCE)


def cut_list(clips: list[dict]) -> dict:
    return {"version": "3", "timebase": "30/1", "v": [clips]}


def segments(*triples: tuple[int, int, int]) -> tuple:
    return tuple(
        DUAL_SOURCE.Segment(record_frame=s, duration=d, source_frame=o)
        for s, d, o in triples
    )


def rates(timeline=30.0, slides=30.0, camera=30.0, cut_list=30.0):
    return DUAL_SOURCE.FrameRates(
        timeline=timeline, slides=slides, camera=camera, cut_list=cut_list
    )


def plan_of(*triples, offset_seconds=0.0, **kwargs):
    """Build a plan from segments given as (record, duration, source) frames."""
    return DUAL_SOURCE.build_placements(
        segments(*triples),
        rates=kwargs.pop("rates", rates()),
        slides_offset_seconds=offset_seconds,
        **kwargs,
    )


def make_pair_folder(root: Path, name: str, files: list[str]) -> Path:
    folder = root / name
    folder.mkdir()
    for filename in files:
        (folder / filename).write_bytes(b"")
    return folder


def test_a_folder_with_one_mkv_and_one_mp4_is_a_pair(tmp_path):
    folder = make_pair_folder(tmp_path, "az900-3", ["PPT.mkv", "camera.mp4"])

    pair = DUAL_SOURCE.find_recording_pair(folder)

    assert pair.slides.name == "PPT.mkv"
    assert pair.camera.name == "camera.mp4"


def test_a_folder_with_a_second_camera_file_is_not_a_pair(tmp_path):
    folder = make_pair_folder(tmp_path, "split", ["PPT.mkv", "a.mp4", "b.mp4"])

    assert DUAL_SOURCE.find_recording_pair(folder) is None


def test_a_folder_with_only_one_recording_is_not_a_pair(tmp_path):
    folder = make_pair_folder(tmp_path, "single", ["talk.mkv"])

    assert DUAL_SOURCE.find_recording_pair(folder) is None


def touch(path: Path, when: int) -> None:
    import os

    os.utime(path, (when, when))


def test_the_newest_pair_folder_wins(tmp_path):
    old = make_pair_folder(tmp_path, "az900-1", ["PPT.mkv", "camera.mp4"])
    new = make_pair_folder(tmp_path, "az900-2", ["PPT.mkv", "camera.mp4"])
    make_pair_folder(tmp_path, "az900-3", ["only.mkv"])
    for name in ("PPT.mkv", "camera.mp4"):
        touch(old / name, 1_000_000)
        touch(new / name, 2_000_000)

    pair = DUAL_SOURCE.find_latest_recording_pair(tmp_path)

    assert pair.folder == new


def test_a_cut_list_left_behind_does_not_make_an_old_folder_look_newest(tmp_path):
    # The editor writes its cut list into the folder it processed, which used to
    # bump that folder's timestamp and pin every later run to the same lecture.
    processed = make_pair_folder(tmp_path, "az900-1", ["PPT.mkv", "camera.mp4"])
    newest = make_pair_folder(tmp_path, "az900-2", ["PPT.mkv", "camera.mp4"])
    for name in ("PPT.mkv", "camera.mp4"):
        touch(processed / name, 1_000_000)
        touch(newest / name, 2_000_000)
    (processed / "_auto_editor_cuts.v3").write_bytes(b"{}")

    assert DUAL_SOURCE.find_latest_recording_pair(tmp_path).folder == newest


def test_cut_list_is_read_as_segments():
    document = cut_list(
        [
            {"start": 0, "dur": 650, "offset": 3104},
            {"start": 650, "dur": 363, "offset": 4016},
        ]
    )

    parsed = DUAL_SOURCE.parse_cut_list(document)

    assert parsed[0].source_end == 3754
    assert parsed[1].record_frame == 650
    assert DUAL_SOURCE.cut_list_frame_rate(document) == 30


def test_an_unknown_cut_list_version_is_refused():
    with pytest.raises(DUAL_SOURCE.DualSourceError, match="version"):
        DUAL_SOURCE.parse_cut_list({"version": "2", "v": [[]]})


def test_an_empty_cut_list_is_refused(tmp_path):
    path = tmp_path / "cuts.json"
    path.write_text(json.dumps(cut_list([])), encoding="utf-8")

    with pytest.raises(DUAL_SOURCE.DualSourceError, match="no video segments"):
        DUAL_SOURCE.parse_cut_list(path)


def test_both_tracks_are_cut_at_the_same_timeline_frames():
    plan = plan_of((0, 650, 3104), (650, 363, 4016), offset_seconds=3.0)

    slides = [p for p in plan.placements if p.role == "slides"]
    camera = [p for p in plan.placements if p.role == "camera"]
    assert [p.record_frame for p in slides] == [p.record_frame for p in camera]
    assert [p.end_frame - p.start_frame for p in slides] == [650, 363]


def test_the_slide_track_is_shifted_by_the_measured_offset():
    plan = plan_of((0, 650, 3104), offset_seconds=3.0)

    slides = next(p for p in plan.placements if p.role == "slides")
    assert (slides.start_frame, slides.end_frame) == (3014, 3664)


def test_a_faster_timeline_stretches_the_record_frames_only():
    # A 60 fps timeline with 30 fps recordings: the same moment, twice the frames.
    plan = plan_of(
        (0, 300, 90), (300, 200, 500), rates=rates(timeline=60.0), timeline_start_frame=186
    )

    camera = [p for p in plan.placements if p.role == "camera"]
    # Source frames stay in the recording's own numbering...
    assert (camera[0].start_frame, camera[0].end_frame) == (90, 390)
    # ...while the timeline advances at 60 fps: 300 source frames is 10 seconds.
    assert [p.record_frame for p in camera] == [186, 786]
    assert plan.end_frame == 186 + 600 + 400


def test_a_camera_that_differs_from_the_slide_capture_keeps_its_own_frames():
    plan = plan_of(
        (0, 600, 600),
        rates=rates(timeline=60.0, slides=30.0, camera=60.0, cut_list=60.0),
        offset_seconds=2.0,
    )

    slides = next(p for p in plan.placements if p.role == "slides")
    camera = next(p for p in plan.placements if p.role == "camera")
    # Ten seconds into a 60 fps camera is frame 600; the same moment on a 30 fps
    # slide capture that started two seconds later is frame 240.
    assert (camera.start_frame, camera.end_frame) == (600, 1200)
    assert (slides.start_frame, slides.end_frame) == (240, 540)


def test_both_tracks_cover_the_same_span_on_the_real_frame_rates():
    """A 30 fps capture and a 59.94 fps camera on the template's 60 fps timeline.

    Resolve gives a 30 fps frame two timeline frames and a 59.94 fps frame one, so
    a length worked out separately per track rounds differently on each. That left
    a one frame hole between clips and pulled V1 out of step with V2.
    """
    real = rates(timeline=60.0, slides=30.0, camera=59.94, cut_list=59.94)
    plan = plan_of(
        (0, 114, 1253), (114, 50, 1416), (164, 67, 1491), (231, 39, 1896),
        rates=real,
    )

    slides = [p for p in plan.placements if p.role == "slides"]
    camera = [p for p in plan.placements if p.role == "camera"]
    spans = [
        following - current
        for current, following in zip(
            [p.record_frame for p in camera],
            [p.record_frame for p in camera[1:]] + [plan.end_frame],
        )
    ]
    # Every clip butts against the next one, so no black frame shows through, and
    # a slide frame is worth two timeline frames while a camera frame is worth one.
    assert all(span > 0 for span in spans)
    for slide, shot, span in zip(slides, camera, spans):
        assert (slide.end_frame - slide.start_frame) * 2 == span
        assert shot.end_frame - shot.start_frame == span


def test_a_long_clip_asks_for_its_full_length_even_though_its_start_moved():
    """Scaling the length as well loses a frame past about eight seconds."""
    real = rates(timeline=60.0, slides=30.0, camera=59.94, cut_list=59.94)
    plan = plan_of((0, 771, 60000), rates=real)

    shot = next(p for p in plan.placements if p.role == "camera")
    assert shot.start_frame == 59940  # 60000 pulled back by 59.94/60
    # 771 frames of a 59.94 fps cut list is 772 frames of a 60 fps timeline, and
    # the request keeps all 772 rather than shrinking with the start.
    assert shot.end_frame - shot.start_frame == 772
    assert plan.end_frame == 772


def test_the_camera_request_is_pulled_back_by_the_conform_it_will_be_read_through():
    """Resolve lands 0.1% deeper into a 59.94 fps camera than the request says."""
    real = rates(timeline=60.0, slides=30.0, camera=59.94, cut_list=59.94)
    plan = plan_of((0, 60, 119379), rates=real)

    camera = next(p for p in plan.placements if p.role == "camera")
    # Asking for 119260 is what makes Resolve show frame 119379.
    assert camera.start_frame == 119260
    # The 30 fps capture conforms to 60 exactly, so its request is left alone.
    slide = next(p for p in plan.placements if p.role == "slides")
    assert slide.start_frame == DUAL_SOURCE.seconds_to_frames(119379 / 59.94, 30.0)


def test_the_audio_matches_the_camera_video_frame_for_frame():
    real = rates(timeline=60.0, slides=30.0, camera=59.94, cut_list=59.94)
    plan = plan_of((0, 114, 1253), (114, 50, 1416), rates=real)

    camera = [p for p in plan.placements if p.role == "camera"]
    audio = [p for p in plan.placements if p.role == "camera_audio"]
    assert [(p.start_frame, p.end_frame) for p in camera] == [
        (p.start_frame, p.end_frame) for p in audio
    ]


def test_a_recording_that_does_not_divide_into_the_timeline_is_refused():
    with pytest.raises(DUAL_SOURCE.DualSourceError, match="whole frames"):
        DUAL_SOURCE.conform_factor(25.0, 60.0)


def test_a_camera_at_the_timeline_rate_keeps_one_frame_per_frame():
    assert DUAL_SOURCE.conform_factor(59.94, 60.0) == 1
    assert DUAL_SOURCE.conform_factor(30.0, 60.0) == 2
    assert DUAL_SOURCE.conform_factor(30.0, 30.0) == 1


def test_a_frame_rate_of_zero_is_refused():
    with pytest.raises(DUAL_SOURCE.DualSourceError, match="must be positive"):
        rates(camera=0.0)


def test_the_camera_supplies_the_audio_and_the_slides_do_not():
    placements = plan_of((0, 650, 3104)).placements

    audio = [p for p in placements if p.media_type == DUAL_SOURCE.AUDIO_ONLY]
    assert len(audio) == 1
    assert audio[0].role == "camera_audio"
    assert all(p.media_type == DUAL_SOURCE.VIDEO_ONLY for p in placements if p != audio[0])


def test_clips_land_on_v1_and_v2():
    tracks = {p.role: p.track_index for p in plan_of((0, 650, 3104)).placements}

    assert tracks == {"slides": 1, "camera": 2, "camera_audio": 1}


def test_the_opening_clip_pushes_everything_later():
    plan = plan_of((0, 650, 3104), (650, 363, 4016), timeline_start_frame=300)

    assert [p.record_frame for p in plan.placements if p.role == "camera"] == [300, 950]
    assert plan.end_frame == 300 + 650 + 363


def test_a_slide_recording_that_starts_far_too_late_is_refused():
    with pytest.raises(DUAL_SOURCE.DualSourceError, match="missing the first 496.5 seconds"):
        plan_of((0, 650, 3104), offset_seconds=600.0)


def test_a_camera_started_minutes_before_the_slides_is_trimmed_not_refused():
    # Measured from the AZ-900 recordings: the camera rolled 17.3 seconds early,
    # which the old five-second limit refused outright.
    plan = plan_of((0, 900, 0), (900, 60000, 1200), offset_seconds=17.32)

    assert plan.segments_placed == 2
    assert plan.head_trim_seconds == pytest.approx(17.32)
    # What survives of the opening segment starts at the first frame of the slides.
    slides = [p for p in plan.placements if p.role == "slides"]
    assert (slides[0].start_frame, slides[0].end_frame) == (0, 380)


def test_a_talk_that_begins_before_the_slide_capture_is_trimmed_on_both_tracks():
    # The camera rolled a third of a second earlier than the slides, and
    # auto-editor's margin reaches back into those frames.
    plan = plan_of((0, 650, 3104), (650, 363, 4016), offset_seconds=3104 / 30 + 1 / 3)

    slides = [p for p in plan.placements if p.role == "slides"]
    camera = [p for p in plan.placements if p.role == "camera"]
    assert (slides[0].start_frame, slides[0].end_frame) == (0, 640)
    assert (camera[0].start_frame, camera[0].end_frame) == (3114, 3754)
    # The trim shifts what follows instead of leaving a hole on the timeline.
    assert [p.record_frame for p in camera] == [0, 640]
    assert plan.end_frame == 640 + 363
    assert plan.head_trim_seconds == pytest.approx(1 / 3)


def test_a_segment_entirely_before_the_slide_capture_is_skipped():
    plan = plan_of((0, 20, 0), (20, 100, 40), offset_seconds=1.0)

    assert plan.segments_placed == 1
    slides = [p for p in plan.placements if p.role == "slides"]
    assert (slides[0].start_frame, slides[0].end_frame) == (10, 110)


def test_segments_past_the_end_of_the_slide_capture_are_dropped_not_guessed():
    plan = plan_of(
        (0, 100, 0), (100, 100, 100), (200, 100, 200), slides_frame_count=150
    )

    assert plan.describe() == (
        "1 segments on V1 and V2, 2 outside the slide capture and not placed"
    )


def test_a_slide_capture_shorter_than_the_first_segment_is_refused():
    with pytest.raises(DUAL_SOURCE.DualSourceError, match="shorter than the first"):
        plan_of((0, 100, 0), slides_frame_count=10)


def test_clip_info_carries_the_media_pool_item():
    placement = plan_of((0, 650, 3104)).placements[0]

    info = placement.to_clip_info("MEDIA_POOL_ITEM")

    assert info == {
        "mediaPoolItem": "MEDIA_POOL_ITEM",
        "startFrame": 3104,
        "endFrame": 3754,
        "recordFrame": 0,
        "mediaType": 1,
        "trackIndex": 1,
    }


def test_seconds_convert_to_whole_frames():
    assert DUAL_SOURCE.seconds_to_frames(3.2, 30.0) == 96
    assert DUAL_SOURCE.seconds_to_frames(-1.5, 30.0) == -45

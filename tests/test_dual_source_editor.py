"""Exercise the Resolve facing half of the dual source route with fake objects.

The DaVinci Resolve API cannot be imported here, so every object the editor
touches is replaced by a small stand-in that records what was asked of it.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).parents[1] / "有償版用スクリプト"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("auto_video_editor", SCRIPT_DIR / "auto_video_editor.py")
EDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["auto_video_editor"] = EDITOR
SPEC.loader.exec_module(EDITOR)

FRAME_RATE = 30.0


class FakeItem:
    def __init__(self, name: str, end: int = 0):
        self._name = name
        self._end = end
        self.properties: dict = {}

    def GetName(self) -> str:
        return self._name

    def GetEnd(self) -> int:
        return self._end

    def SetProperty(self, properties) -> bool:
        self.properties.update(properties)
        return True


class FakeMediaPoolItem:
    def __init__(self, name: str, frames: int):
        self._name = name
        self._frames = frames

    def GetName(self) -> str:
        return self._name

    def GetClipProperty(self, key: str) -> str:
        return str(self._frames)


class FakeTimeline:
    def __init__(self, items: list[FakeItem], video_tracks: int = 1):
        self._items = items
        self.video_tracks = video_tracks
        self.timecode = None

    def GetItemsInTrack(self, track_type: str, index: int) -> dict:
        return {i: item for i, item in enumerate(self._items)}

    def GetSetting(self, key: str) -> str:
        return str(FRAME_RATE)

    def GetTrackCount(self, track_type: str) -> int:
        return self.video_tracks

    def AddTrack(self, track_type: str) -> bool:
        self.video_tracks += 1
        return True

    def SetCurrentTimecode(self, timecode: str) -> bool:
        self.timecode = timecode
        return True


class FakeMediaPool:
    def __init__(self, frames_by_name: dict):
        self.frames_by_name = frames_by_name
        self.appended: list[list[dict]] = []

    def ImportMedia(self, paths):
        items = []
        for path in paths:
            name = Path(path).name
            items.append(FakeMediaPoolItem(name, self.frames_by_name.get(name, 100000)))
        return items

    def AppendToTimeline(self, clip_infos):
        self.appended.append(clip_infos)
        return [FakeItem(f"clip{i}") for i in range(len(clip_infos))]


class FakeProject:
    def __init__(self):
        self.current_timeline = None

    def SetCurrentTimeline(self, timeline) -> bool:
        self.current_timeline = timeline
        return True

    def GetName(self) -> str:
        return "自動編集_test"


@pytest.fixture
def pair(tmp_path):
    folder = tmp_path / "az900-3"
    folder.mkdir()
    slides = folder / "PPT.mkv"
    camera = folder / "camera.mp4"
    slides.write_bytes(b"")
    camera.write_bytes(b"")
    return EDITOR.dual_source.RecordingPair(folder=folder, slides=slides, camera=camera)


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Replace the two external tools with predictable answers."""

    def fake_offset(reference, target, **kwargs):
        return EDITOR.audio_sync.SyncResult(
            offset_seconds=2.0, confidence=12.0, envelope_rate=200, analyzed_seconds=60.0
        )

    def fake_cut_list(camera_path, output_path):
        return {
            "version": "3",
            "timebase": "30/1",
            "v": [[
                {"start": 0, "dur": 300, "offset": 90},
                {"start": 300, "dur": 200, "offset": 500},
            ]],
        }

    monkeypatch.setattr(EDITOR.audio_sync, "estimate_offset", fake_offset)
    monkeypatch.setattr(EDITOR, "run_auto_editor_cut_list", fake_cut_list)
    monkeypatch.setattr(EDITOR, "first_existing_path", lambda candidates: None)


def test_the_opening_clip_end_becomes_the_insert_point():
    timeline = FakeTimeline([FakeItem("01_EBI_CHAN_OP.mov", end=300)])

    assert EDITOR.find_opening_end_frame(timeline) == 300


def test_a_timeline_without_an_opening_clip_starts_at_zero():
    timeline = FakeTimeline([FakeItem("something else.mov", end=300)])

    assert EDITOR.find_opening_end_frame(timeline) == 0


def test_the_camera_track_is_created_when_the_template_has_only_v1():
    timeline = FakeTimeline([], video_tracks=1)

    assert EDITOR.ensure_video_tracks(timeline, 2) is True
    assert timeline.video_tracks == 2


def test_the_dual_route_places_both_tracks_and_sizes_the_camera(pair, stub_pipeline):
    media_pool = FakeMediaPool({"PPT.mkv": 100000, "camera.mp4": 100000})
    timeline = FakeTimeline([FakeItem("01_EBI_CHAN_OP.mov", end=300)])

    assert EDITOR.run_dual_source_edit(FakeProject(), media_pool, timeline, pair, 300)

    clip_infos = media_pool.appended[0]
    slides = [c for c in clip_infos if c["trackIndex"] == 1 and c["mediaType"] == 1]
    camera = [c for c in clip_infos if c["trackIndex"] == 2]
    audio = [c for c in clip_infos if c["mediaType"] == 2]
    assert len(slides) == len(camera) == len(audio) == 2
    # A two second sync offset at 30 fps means the slides are entered 60 frames earlier.
    assert slides[0]["startFrame"] == 30
    assert camera[0]["startFrame"] == 90
    assert slides[0]["recordFrame"] == camera[0]["recordFrame"] == 300


def test_the_audio_comes_from_the_camera_file_only(pair, stub_pipeline):
    media_pool = FakeMediaPool({"PPT.mkv": 100000, "camera.mp4": 100000})

    EDITOR.run_dual_source_edit(FakeProject(), media_pool, FakeTimeline([]), pair, 0)

    audio = [c for c in media_pool.appended[0] if c["mediaType"] == 2]
    assert {c["mediaPoolItem"].GetName() for c in audio} == {"camera.mp4"}


def test_a_frame_rate_mismatch_stops_the_run(pair, stub_pipeline, monkeypatch):
    monkeypatch.setattr(
        EDITOR,
        "run_auto_editor_cut_list",
        lambda camera, out: {
            "version": "3",
            "timebase": "60/1",
            "v": [[{"start": 0, "dur": 300, "offset": 0}]],
        },
    )
    media_pool = FakeMediaPool({})

    assert EDITOR.run_dual_source_edit(FakeProject(), media_pool, FakeTimeline([]), pair, 0) is False
    assert media_pool.appended == []


def test_a_failed_sync_stops_the_run_instead_of_guessing(pair, stub_pipeline, monkeypatch):
    def refuse(reference, target, **kwargs):
        raise EDITOR.audio_sync.AudioSyncError("did not correlate")

    monkeypatch.setattr(EDITOR.audio_sync, "estimate_offset", refuse)
    media_pool = FakeMediaPool({})

    assert EDITOR.run_dual_source_edit(FakeProject(), media_pool, FakeTimeline([]), pair, 0) is False
    assert media_pool.appended == []


def test_the_measured_placement_is_applied_to_every_clip(pair, stub_pipeline):
    media_pool = FakeMediaPool({"PPT.mkv": 100000, "camera.mp4": 100000})
    appended: list[FakeItem] = []

    original = media_pool.AppendToTimeline

    def remember(clip_infos):
        items = original(clip_infos)
        appended.extend(items)
        return items

    media_pool.AppendToTimeline = remember

    EDITOR.run_dual_source_edit(FakeProject(), media_pool, FakeTimeline([]), pair, 0)

    sized = [item for item in appended if item.properties]
    assert len(sized) == 4  # two slide clips and two camera clips
    zooms = [item.properties.get("ZoomX") for item in sized if "ZoomX" in item.properties]
    pans = sorted(item.properties["Pan"] for item in sized)
    assert zooms == [0.922, 0.922]
    assert pans == [-300.0, -300.0, 626.0, 626.0]


def test_the_cut_list_is_written_next_to_the_recording(pair, tmp_path, monkeypatch):
    recorded = {}

    def fake_run(command, capture_output, text, check):
        recorded["command"] = command
        Path(command[command.index("--output") + 1]).write_text(
            json.dumps({"version": "3", "timebase": "30/1", "v": [[]]}), encoding="utf-8"
        )

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(EDITOR.subprocess, "run", fake_run)
    output = pair.folder / "_auto_editor_cuts.json"

    document = EDITOR.run_auto_editor_cut_list(pair.camera, output)

    assert document["version"] == "3"
    assert output.exists()
    assert "--margin" in recorded["command"] and "0.2sec" in recorded["command"]
    assert "audio:threshold=3%" in recorded["command"]

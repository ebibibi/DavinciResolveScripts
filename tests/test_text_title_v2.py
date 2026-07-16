import importlib.util
import os
from pathlib import Path


os.environ["DAVINCI_GIT_PULL_DONE"] = "1"

SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "有償版用スクリプト"
    / "auto_video_editor.py"
)
SPEC = importlib.util.spec_from_file_location("auto_video_editor_v2", SCRIPT_PATH)
EDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EDITOR)


class FakeTextTool:
    def __init__(self, font_readback: str = EDITOR.TEXT_TITLE_FONT) -> None:
        self.inputs = {}
        self.font_readback = font_readback

    def SetInput(self, name, value):
        self.inputs[name] = value
        return True

    def GetInput(self, name):
        if name == "Font":
            return self.font_readback
        return self.inputs.get(name)


class FakeComp:
    def __init__(self, tool: FakeTextTool) -> None:
        self.tool = tool

    def GetToolList(self, _selected, tool_type):
        return {1: self.tool} if tool_type == "TextPlus" else {}


class FakeTitleItem:
    def __init__(self, tool: FakeTextTool) -> None:
        self.comp = FakeComp(tool)
        self.clip_color = None

    def SetClipColor(self, color):
        self.clip_color = color
        return True

    def GetFusionCompCount(self):
        return 1

    def GetFusionCompByIndex(self, _index):
        return self.comp


class FakeAppendedItem:
    def __init__(self, track_index: int) -> None:
        self.track_index = track_index

    def GetTrackTypeAndIndex(self):
        return ["video", self.track_index]


class FakeUnverifiableItem:
    pass


class FakeBrokenTrackItem:
    def GetTrackTypeAndIndex(self):
        raise RuntimeError("Resolve API error")


class FakeMainTimeline:
    def __init__(self) -> None:
        self.deleted = []
        self.track_count = 1

    def GetTrackCount(self, _track_type):
        return self.track_count

    def AddTrack(self, _track_type):
        self.track_count += 1
        return True

    def DeleteClips(self, items, ripple):
        self.deleted.append((items, ripple))
        return True

    def InsertFusionTitleIntoTimeline(self, _name):
        raise AssertionError("The main timeline must never receive direct title insertion")


class FakeMediaPool:
    def __init__(self, appended_track: int = 2) -> None:
        self.appended_track = appended_track
        self.clip_infos = []

    def AppendToTimeline(self, clip_infos):
        self.clip_infos.extend(clip_infos)
        return [FakeAppendedItem(self.appended_track)]


class FakeCompoundItem:
    def __init__(self, media_item) -> None:
        self.media_item = media_item

    def GetMediaPoolItem(self):
        return self.media_item


class FakeFactoryTimeline:
    def __init__(self, title_item, media_item) -> None:
        self.title_item = title_item
        self.media_item = media_item
        self.direct_insertions = 0

    def InsertFusionTitleIntoTimeline(self, name):
        assert name == "Text+"
        self.direct_insertions += 1
        return self.title_item

    def CreateCompoundClip(self, items, info):
        assert items == [self.title_item]
        assert info["name"].startswith("AI Topic")
        return FakeCompoundItem(self.media_item)


class FakeProject:
    def __init__(self, main_timeline) -> None:
        self.main_timeline = main_timeline
        self.current = main_timeline
        self.history = []

    def SetCurrentTimeline(self, timeline):
        self.current = timeline
        self.history.append(timeline)
        return True


class FakeFactoryMediaPool(FakeMediaPool):
    def __init__(self, factory_timeline) -> None:
        super().__init__()
        self.factory_timeline = factory_timeline
        self.deleted_timelines = []

    def CreateEmptyTimeline(self, name):
        assert name.startswith("AI Topic")
        return self.factory_timeline

    def DeleteTimelines(self, timelines):
        self.deleted_timelines.extend(timelines)
        return True


def test_font_is_set_and_verified_exactly() -> None:
    tool = FakeTextTool()
    item = FakeTitleItem(tool)

    configured = EDITOR.configure_text_title_item(item, "いまの話題")

    assert configured is True
    assert tool.inputs["Font"] == "HGPSoeiKakugothicUB"
    assert tool.GetInput("Font") == "HGPSoeiKakugothicUB"


def test_font_configuration_fails_when_readback_is_different() -> None:
    tool = FakeTextTool(font_readback="Open Sans")
    item = FakeTitleItem(tool)

    configured = EDITOR.configure_text_title_item(item, "いまの話題")

    assert configured is False


def test_append_title_explicitly_targets_v2() -> None:
    media_pool = FakeMediaPool(appended_track=2)
    timeline = FakeMainTimeline()
    media_item = object()

    result = EDITOR.append_text_title_to_track(
        media_pool,
        timeline,
        media_item,
        frame=186,
        fps=30,
        seconds=4.0,
        target_track_index=2,
    )

    assert result
    assert media_pool.clip_infos == [{
        "mediaPoolItem": media_item,
        "startFrame": 0,
        "endFrame": 120,
        "recordFrame": 186,
        "mediaType": 1,
        "trackIndex": 2,
    }]
    assert timeline.deleted == []


def test_wrong_track_title_is_deleted_without_ripple() -> None:
    media_pool = FakeMediaPool(appended_track=1)
    timeline = FakeMainTimeline()

    result = EDITOR.append_text_title_to_track(
        media_pool,
        timeline,
        object(),
        frame=186,
        fps=30,
        seconds=4.0,
        target_track_index=2,
    )

    assert result == 0
    assert len(timeline.deleted) == 1
    assert timeline.deleted[0][1] is False


def test_unverifiable_title_is_deleted_without_ripple() -> None:
    media_pool = FakeMediaPool()
    timeline = FakeMainTimeline()
    item = FakeUnverifiableItem()
    media_pool.AppendToTimeline = lambda _clip_infos: {1: item}

    result = EDITOR.append_text_title_to_track(
        media_pool,
        timeline,
        object(),
        frame=186,
        fps=30,
        seconds=4.0,
        target_track_index=2,
    )

    assert result == 0
    assert timeline.deleted == [([item], False)]


def test_title_is_deleted_when_track_lookup_fails() -> None:
    media_pool = FakeMediaPool()
    timeline = FakeMainTimeline()
    item = FakeBrokenTrackItem()
    media_pool.AppendToTimeline = lambda _clip_infos: [item]

    result = EDITOR.append_text_title_to_track(
        media_pool,
        timeline,
        object(),
        frame=186,
        fps=30,
        seconds=4.0,
        target_track_index=2,
    )

    assert result == 0
    assert timeline.deleted == [([item], False)]


def test_text_title_asset_is_built_away_from_main_timeline() -> None:
    main_timeline = FakeMainTimeline()
    title_item = FakeTitleItem(FakeTextTool())
    media_item = object()
    factory_timeline = FakeFactoryTimeline(title_item, media_item)
    media_pool = FakeFactoryMediaPool(factory_timeline)
    project = FakeProject(main_timeline)
    style = EDITOR.text_action_style({"style": "current_topic"})

    asset, temporary_timeline = EDITOR.create_text_title_asset(
        project,
        media_pool,
        main_timeline,
        "いまの話題\nV2配置",
        style,
        "AI Topic 001",
    )

    assert asset is media_item
    assert temporary_timeline is factory_timeline
    assert factory_timeline.direct_insertions == 1
    assert project.current is main_timeline


def test_ai_text_pipeline_uses_factory_asset_and_appends_only_to_v2() -> None:
    main_timeline = FakeMainTimeline()
    title_item = FakeTitleItem(FakeTextTool())
    factory_timeline = FakeFactoryTimeline(title_item, object())
    media_pool = FakeFactoryMediaPool(factory_timeline)
    project = FakeProject(main_timeline)
    plan = {
        "enabled": True,
        "source_duration": 8.0,
        "actions": [
            {
                "type": "text_title",
                "style": "current_topic",
                "time": 0.0,
                "duration": 4.0,
                "text": "いまの話題\nV2配置",
            },
            {
                "type": "text_title",
                "style": "current_topic",
                "time": 4.0,
                "duration": 4.0,
                "text": "いまの話題\nV2配置",
            },
        ],
        "qc_notes": [],
    }

    result = EDITOR.insert_ai_assist_text_objects(
        main_timeline,
        186,
        plan,
        fps=30,
        edited_duration_frames=240,
        project=project,
        media_pool=media_pool,
    )

    assert result["inserted"] == 2
    assert result["topic_inserted"] == 2
    assert factory_timeline.direct_insertions == 1
    assert len(media_pool.clip_infos) == 2
    assert all(info["trackIndex"] == 2 for info in media_pool.clip_infos)
    assert media_pool.deleted_timelines == [factory_timeline]

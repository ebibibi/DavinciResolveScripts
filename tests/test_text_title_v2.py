import importlib.util
import os
import zipfile
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
    def __init__(
        self,
        font_readback: str = EDITOR.TEXT_TITLE_FONT,
        style_readback: str = "Regular",
    ) -> None:
        self.inputs = {}
        self.font_readback = font_readback
        self.style_readback = style_readback

    def SetInput(self, name, value):
        self.inputs[name] = value
        return True

    def GetInput(self, name):
        if name == "Font":
            return self.font_readback
        if name == "Style":
            return self.style_readback
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


class FakeAppendedItem(FakeTitleItem):
    def __init__(self, track_index: int, tool=None) -> None:
        super().__init__(tool or FakeTextTool())
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


class FakeMediaItem:
    def __init__(self, name) -> None:
        self.name = name

    def GetName(self):
        return self.name


class FakeFolder:
    def __init__(self, clips=None, subfolders=None) -> None:
        self.clips = clips or []
        self.subfolders = subfolders or []

    def GetClipList(self):
        return self.clips

    def GetSubFolderList(self):
        return self.subfolders


class FakeNativeTitleMediaPool(FakeMediaPool):
    def __init__(self, title_template, appended_track=2) -> None:
        super().__init__()
        self.appended_track = appended_track
        self.title_template = title_template
        self.root_folder = FakeFolder(
            subfolders=[FakeFolder(clips=[title_template])]
        )
        self.appended_items = []

    def GetRootFolder(self):
        return self.root_folder

    def AppendToTimeline(self, clip_infos):
        self.clip_infos.extend(clip_infos)
        item = FakeAppendedItem(self.appended_track)
        self.appended_items.append(item)
        return [item]


def test_font_is_set_and_verified_exactly() -> None:
    tool = FakeTextTool()
    item = FakeTitleItem(tool)

    configured = EDITOR.configure_text_title_item(item, "いまの話題")

    assert configured is True
    assert tool.inputs["Font"] == "HGPSoeiKakugothicUB"
    assert tool.inputs["Style"] == "Regular"
    assert tool.GetInput("Font") == "HGPSoeiKakugothicUB"
    assert tool.GetInput("Style") == "Regular"


def test_font_configuration_fails_when_readback_is_different() -> None:
    tool = FakeTextTool(font_readback="Open Sans")
    item = FakeTitleItem(tool)

    configured = EDITOR.configure_text_title_item(item, "いまの話題")

    assert configured is False


def test_font_configuration_fails_when_semibold_remains_active() -> None:
    tool = FakeTextTool(style_readback="Semibold")
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

    assert result is not None
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

    assert result is None
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

    assert result is None
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

    assert result is None
    assert timeline.deleted == [([item], False)]


def test_native_text_plus_template_is_found_recursively() -> None:
    template = FakeMediaItem("テロップ")
    media_pool = FakeNativeTitleMediaPool(template)

    result = EDITOR.find_native_text_title_template(media_pool)

    assert result is template


def test_project_template_contains_native_text_plus_media_pool_item() -> None:
    project_template = SCRIPT_PATH.parent / "テンプレート.drp"

    with zipfile.ZipFile(project_template) as archive:
        media_pool_xml = archive.read("MediaPool/Master/MpFolder.xml")

    xml_text = media_pool_xml.decode("utf-8")
    generator_start = xml_text.index("<Sm2MpGenerator")
    generator_end = xml_text.index("</Sm2MpGenerator>", generator_start)
    generator_xml = xml_text[generator_start:generator_end]

    assert "<Name>テロップ</Name>" in generator_xml
    assert "546578742b" in generator_xml
    assert "<CompositionTable>" in generator_xml


def test_ai_text_pipeline_appends_native_text_plus_template_only_to_v2() -> None:
    main_timeline = FakeMainTimeline()
    template = FakeMediaItem("テロップ")
    media_pool = FakeNativeTitleMediaPool(template)
    plan = {
        "enabled": True,
        "source_duration": 8.0,
        "actions": [
            {
                "type": "text_title",
                "style": "current_topic",
                "time": 0.0,
                "duration": 4.0,
                "text": "V2へ安全に配置する方法",
            },
            {
                "type": "text_title",
                "style": "current_topic",
                "time": 4.0,
                "duration": 4.0,
                "text": "V2へ安全に配置する方法",
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
        media_pool=media_pool,
    )

    assert result["inserted"] == 2
    assert result["topic_inserted"] == 2
    assert len(media_pool.clip_infos) == 2
    assert all(info["mediaPoolItem"] is template for info in media_pool.clip_infos)
    assert all(info["trackIndex"] == 2 for info in media_pool.clip_infos)
    assert all(item.comp.tool.inputs["Font"] == "HGPSoeiKakugothicUB" for item in media_pool.appended_items)
    assert all(item.comp.tool.inputs["Style"] == "Regular" for item in media_pool.appended_items)
    assert all(
        item.comp.tool.inputs["HorizontalJustification"] == -1
        for item in media_pool.appended_items
    )
    assert all(
        item.comp.tool.inputs["StyledText"] == "V2へ安全に配置する方法"
        for item in media_pool.appended_items
    )


def test_ai_text_pipeline_deletes_native_title_when_font_validation_fails(
    monkeypatch,
) -> None:
    main_timeline = FakeMainTimeline()
    template = FakeMediaItem("テロップ")
    media_pool = FakeNativeTitleMediaPool(template)
    plan = {
        "enabled": True,
        "source_duration": 4.0,
        "actions": [
            {
                "type": "text_title",
                "style": "current_topic",
                "time": 0.0,
                "duration": 4.0,
                "text": "いまの話題",
            },
        ],
        "qc_notes": [],
    }
    monkeypatch.setattr(
        EDITOR,
        "configure_text_title_item",
        lambda *args, **kwargs: False,
    )

    result = EDITOR.insert_ai_assist_text_objects(
        main_timeline,
        186,
        plan,
        fps=30,
        edited_duration_frames=120,
        media_pool=media_pool,
    )

    assert result["inserted"] == 0
    assert main_timeline.deleted == [([media_pool.appended_items[0]], False)]

"""The branded intro and outro always receive an editable subscription CTA."""

from unittest.mock import Mock

import subscribe_cta


class FakeClip:
    def __init__(self, name: str, start: int = 0, end: int = 0):
        self.name = name
        self.start = start
        self.end = end

    def GetName(self) -> str:
        return self.name

    def GetStart(self) -> int:
        return self.start

    def GetEnd(self) -> int:
        return self.end


class FakeFolder:
    def __init__(self, clips=None, children=None):
        self.clips = clips or []
        self.children = children or []

    def GetClipList(self) -> list:
        return self.clips

    def GetSubFolderList(self) -> list:
        return self.children


class FakeTimeline:
    def __init__(self, clips, track_count=1):
        self.clips = clips
        self.track_count = track_count

    def GetItemsInTrack(self, track_type: str, index: int) -> dict:
        return {position: clip for position, clip in enumerate(self.clips)}

    def GetTrackCount(self, track_type: str) -> int:
        return self.track_count

    def AddTrack(self, track_type: str) -> bool:
        self.track_count += 1
        return True


class FakeMediaPool:
    def __init__(self, root, appended_items):
        self.root = root
        self.appended_items = iter(appended_items)
        self.requests = []

    def GetRootFolder(self):
        return self.root

    def AppendToTimeline(self, request):
        self.requests.append(request[0])
        return [next(self.appended_items)]


def title_item():
    tool = Mock()
    composition = Mock()
    composition.GetToolList.return_value = {1: tool}
    item = Mock()
    item.GetFusionCompCount.return_value = 1
    item.GetFusionCompByIndex.return_value = composition
    return item, tool


def test_ctas_cover_the_full_intro_and_outro_on_v3():
    template = FakeClip("テロップ")
    first_item, first_tool = title_item()
    second_item, second_tool = title_item()
    media_pool = FakeMediaPool(
        FakeFolder(children=[FakeFolder([template])]), [first_item, second_item]
    )
    timeline = FakeTimeline(
        [
            FakeClip("01_EBI_CHAN_OP.mov", 0, 180),
            FakeClip("talk.mkv", 180, 1800),
            FakeClip("03_EBI_CHAN_IN.mov", 1800, 1950),
        ]
    )

    assert subscribe_cta.add_subscribe_ctas(media_pool, timeline) == 2
    assert timeline.track_count == 3
    assert [
        (request["recordFrame"], request["endFrame"], request["trackIndex"])
        for request in media_pool.requests
    ] == [(0, 179, 3), (1800, 149, 3)]
    first_tool.SetInput.assert_any_call("StyledText", subscribe_cta.CTA_TEXT)
    second_tool.SetInput.assert_any_call("StyledText", subscribe_cta.CTA_TEXT)
    first_tool.SetInput.assert_any_call("Center", {1: 0.5, 2: 0.18})
    first_tool.SetInput.assert_any_call("Thickness2", 0.08)
    first_item.SetProperty.assert_any_call(
        {
            "ZoomX": 1.0,
            "ZoomY": 1.0,
            "Pan": 0.0,
            "Tilt": 0.0,
            "RotationAngle": 0.0,
        }
    )


def test_non_branded_clips_are_left_untouched():
    media_pool = FakeMediaPool(FakeFolder([FakeClip("テロップ")]), [])
    timeline = FakeTimeline([FakeClip("talk.mkv", 0, 900)])

    assert subscribe_cta.add_subscribe_ctas(media_pool, timeline) == 0
    assert media_pool.requests == []
    assert timeline.track_count == 1

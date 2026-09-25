"""Add the standard channel-subscription prompt over branded clips."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

CTA_TEXT = "チャンネル登録よろしくね！"
CTA_TEMPLATE_NAMES = ("テロップ", "Text+")
CTA_CLIP_MARKERS = ("01_EBI_CHAN_OP", "03_EBI_CHAN_IN")
CTA_TRACK_INDEX = 3


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _item_name(item: Any) -> str:
    try:
        name = item.GetName()
        if name:
            return str(name)
    except Exception:
        pass
    try:
        properties = item.GetClipProperty()
        return str(properties.get("Clip Name") or "")
    except Exception:
        return ""


def find_title_template(media_pool: Any) -> Any | None:
    """Find the editable Text+ generator bundled in the project template."""
    try:
        pending = [media_pool.GetRootFolder()]
    except Exception as error:
        print(f"✗ CTA用Media Poolを取得できませんでした: {error}")
        return None

    while pending:
        folder = pending.pop()
        try:
            clips = _as_list(folder.GetClipList())
        except Exception:
            clips = []
        for wanted_name in CTA_TEMPLATE_NAMES:
            for clip in clips:
                if _item_name(clip) == wanted_name:
                    return clip
        try:
            pending.extend(_as_list(folder.GetSubFolderList()))
        except Exception:
            pass
    return None


def _ensure_video_track(timeline: Any, track_index: int) -> bool:
    try:
        while int(timeline.GetTrackCount("video")) < track_index:
            if not timeline.AddTrack("video"):
                return False
        return True
    except Exception as error:
        print(f"✗ CTA用V{track_index}を準備できませんでした: {error}")
        return False


def _first_text_tool(timeline_item: Any) -> Any | None:
    try:
        if timeline_item.GetFusionCompCount() < 1:
            return None
        composition = timeline_item.GetFusionCompByIndex(1)
        tools = composition.GetToolList(False, "TextPlus")
    except Exception:
        return None
    return next(iter(tools.values()), None) if isinstance(tools, dict) else None


def _set_input(tool: Any, name: str, value: Any) -> None:
    try:
        tool.SetInput(name, value)
    except Exception:
        pass


def configure_cta(timeline_item: Any, text: str = CTA_TEXT) -> bool:
    """Style one editable Text+ item for safe-area display over animation."""
    text_tool = _first_text_tool(timeline_item)
    if text_tool is None:
        print("✗ CTAのText+を編集できませんでした")
        return False

    # The bundled legacy title has an Edit-page offset. Normalize it before
    # placing the text in Fusion coordinates (where Y increases upward).
    try:
        timeline_item.SetProperty(
            {
                "ZoomX": 1.0,
                "ZoomY": 1.0,
                "Pan": 0.0,
                "Tilt": 0.0,
                "RotationAngle": 0.0,
            }
        )
    except Exception:
        pass

    _set_input(text_tool, "StyledText", text)
    _set_input(text_tool, "Size", 0.065)
    _set_input(text_tool, "Center", {1: 0.5, 2: 0.18})
    _set_input(text_tool, "HorizontalJustification", 1)
    _set_input(text_tool, "VerticalJustification", 1)
    _set_input(text_tool, "Red1", 1.0)
    _set_input(text_tool, "Green1", 1.0)
    _set_input(text_tool, "Blue1", 1.0)
    # Black outline keeps the white CTA readable over every frame of the animation.
    _set_input(text_tool, "Enabled2", 1.0)
    _set_input(text_tool, "Red2", 0.0)
    _set_input(text_tool, "Green2", 0.0)
    _set_input(text_tool, "Blue2", 0.0)
    _set_input(text_tool, "Thickness2", 0.08)
    try:
        timeline_item.SetClipColor("Red")
    except Exception:
        pass
    return True


def _branded_clip_ranges(timeline: Any) -> Iterable[tuple[str, int, int]]:
    try:
        items = _as_list(timeline.GetItemsInTrack("video", 1))
    except Exception:
        return []

    ranges = []
    for item in items:
        name = _item_name(item)
        if not any(marker in name for marker in CTA_CLIP_MARKERS):
            continue
        try:
            ranges.append((name, int(item.GetStart()), int(item.GetEnd())))
        except Exception as error:
            print(f"! CTA対象クリップの範囲を読めませんでした ({name}): {error}")
    return ranges


def add_subscribe_ctas(media_pool: Any, timeline: Any) -> int:
    """Overlay the standard CTA on both the opening and ending animations."""
    ranges = list(_branded_clip_ranges(timeline))
    if not ranges:
        print("! CTA対象のオープニング／エンディングがありません")
        return 0

    title_template = find_title_template(media_pool)
    if title_template is None:
        print("✗ CTA用Text+テンプレートがMedia Poolにありません")
        return 0
    if not _ensure_video_track(timeline, CTA_TRACK_INDEX):
        return 0

    added = 0
    for clip_name, start, end in ranges:
        if end <= start:
            continue
        clip_info = {
            "mediaPoolItem": title_template,
            "startFrame": 0,
            # Resolve's source endpoint is inclusive.
            "endFrame": end - start - 1,
            "recordFrame": start,
            "mediaType": 1,
            "trackIndex": CTA_TRACK_INDEX,
        }
        try:
            appended = _as_list(media_pool.AppendToTimeline([clip_info]))
        except Exception as error:
            print(f"✗ CTAを追加できませんでした ({clip_name}): {error}")
            continue
        if appended and configure_cta(appended[0]):
            added += 1
            print(f"✓ チャンネル登録CTAを追加しました: {clip_name}")
    return added

import importlib.util
import os
from pathlib import Path


os.environ["DAVINCI_GIT_PULL_DONE"] = "1"

SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "有償版用スクリプト"
    / "auto_video_editor.py"
)
SPEC = importlib.util.spec_from_file_location("auto_video_editor", SCRIPT_PATH)
EDITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EDITOR)


def segment(start: float, end: float, text: str) -> dict:
    return {"start": start, "end": end, "text": text, "words": []}


def test_build_topic_ranges_covers_transcript_without_overlap() -> None:
    segments = [
        segment(0, 18, "今回はClaude Codeのスキルについて説明します"),
        segment(18, 41, "SKILL.mdとスクリプトの構成を確認します"),
        segment(48, 64, "次にMCPを使った外部サービス連携を説明します"),
        segment(64, 92, "直接APIを使う場合との違いを比較します"),
    ]

    topics = EDITOR.build_topic_ranges(
        segments,
        target_seconds=45,
        min_seconds=15,
        max_seconds=70,
        max_topics=10,
    )

    assert len(topics) == 2
    assert topics[0]["start"] == 0
    assert topics[0]["end"] == topics[1]["start"]
    assert topics[-1]["end"] == 92
    assert all(topic["label"] for topic in topics)
    assert "Claude" in topics[0]["label"]
    assert "MCP" in topics[1]["label"]


def test_short_final_topic_is_merged_into_previous_topic() -> None:
    segments = [
        segment(0, 30, "文字起こしを使って話題を判定します"),
        segment(30, 60, "話題を画面の端に表示します"),
        segment(60, 67, "最後にまとめます"),
    ]

    topics = EDITOR.build_topic_ranges(
        segments,
        target_seconds=30,
        min_seconds=15,
        max_seconds=60,
        max_topics=10,
    )

    assert topics[-1]["end"] == 67
    assert topics[-1]["end"] - topics[-1]["start"] >= 15


def test_topic_overlay_actions_fill_every_topic_range() -> None:
    topics = [
        {"start": 0.0, "end": 10.0, "label": "スキルの構造"},
        {"start": 10.0, "end": 17.0, "label": "MCPとの連携"},
    ]

    actions = EDITOR.build_topic_overlay_actions(topics, refresh_seconds=4.0)

    assert actions[0] == {
        "type": "text_title",
        "style": "current_topic",
        "time": 0.0,
        "duration": 4.0,
        "text": "いまの話題\nスキルの構造",
    }
    assert actions[-1]["time"] == 14.0
    for topic in topics:
        topic_actions = [
            action
            for action in actions
            if topic["start"] <= action["time"] < topic["end"]
        ]
        assert topic_actions[0]["time"] == topic["start"]
        assert topic_actions[-1]["time"] + topic_actions[-1]["duration"] == topic["end"]
        for left, right in zip(topic_actions, topic_actions[1:]):
            assert left["time"] + left["duration"] == right["time"]


def test_current_topic_style_is_small_and_at_top_right() -> None:
    style = EDITOR.text_action_style({"style": "current_topic"})

    assert style["size"] < 0.05
    assert style["position"][0] > 0.5
    assert style["position"][1] > 0.5
    assert style["clip_color"] == "Purple"


def test_default_actions_use_topic_overlay_instead_of_hook_or_key_points(monkeypatch) -> None:
    monkeypatch.setattr(
        EDITOR,
        "LOCAL_CONFIG",
        {"ai_edit_actions": {"key_point_titles": True}},
    )
    plan = {
        "hook_text": "古いフック",
        "topics": [{"start": 0.0, "end": 8.0, "label": "現在の話題"}],
        "key_point_cues": [{"time": 1.0, "label": "旧方式", "note": "旧方式"}],
        "chapters": [],
    }

    actions = EDITOR.build_ai_edit_actions(plan, [])

    assert actions
    assert {action.get("style") for action in actions} == {"current_topic"}
    assert all(action["type"] == "text_title" for action in actions)


def test_insertion_result_is_written_to_status_file(tmp_path, monkeypatch) -> None:
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text("{}", encoding="utf-8")
    plan = {
        "enabled": True,
        "transcript_path": str(transcript_path),
        "source_duration": 8.0,
        "topics": [{"start": 0.0, "end": 8.0, "label": "現在の話題"}],
        "actions": EDITOR.build_topic_overlay_actions(
            [{"start": 0.0, "end": 8.0, "label": "現在の話題"}],
            refresh_seconds=4.0,
        ),
        "chapters": [],
        "qc_notes": [],
    }
    inserted = iter([object(), None])
    monkeypatch.setattr(
        EDITOR,
        "find_native_text_title_template",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        EDITOR,
        "append_text_title_to_track",
        lambda *args, **kwargs: next(inserted),
    )
    monkeypatch.setattr(
        EDITOR,
        "configure_text_title_item",
        lambda *args, **kwargs: True,
    )

    class FakeProject:
        def SetCurrentTimeline(self, _timeline):
            return True

    class FakeMediaPool:
        pass

    result = EDITOR.insert_ai_assist_text_objects(
        object(),
        0,
        plan,
        fps=30,
        edited_duration_frames=240,
        project=FakeProject(),
        media_pool=FakeMediaPool(),
    )

    assert result == {
        "expected": 2,
        "inserted": 1,
        "topic_expected": 2,
        "topic_inserted": 1,
    }
    status = (tmp_path / "ai_assist_status.txt").read_text(encoding="utf-8")
    assert "topic_titles_expected: 2" in status
    assert "topic_titles_inserted: 1" in status

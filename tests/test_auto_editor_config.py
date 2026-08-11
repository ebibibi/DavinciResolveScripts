import json
from pathlib import Path

import pytest

from auto_editor_config import AutoEditorConfig, load_auto_editor_config


def test_missing_local_config_uses_the_shipped_defaults(tmp_path: Path) -> None:
    config = load_auto_editor_config(tmp_path / "config.json")

    assert config == AutoEditorConfig(threshold_percent=1.0, margin_seconds=0.3)
    assert config.edit_expression == "audio:threshold=1%"
    assert config.margin == "0.3sec"


def test_local_config_overrides_silence_detection(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "auto_editor": {
                    "threshold_percent": 2.5,
                    "margin_seconds": 0.45,
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_auto_editor_config(path)

    assert config.edit_expression == "audio:threshold=2.5%"
    assert config.margin == "0.45sec"


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ({"threshold_percent": 0}, "threshold_percent"),
        ({"threshold_percent": 101}, "threshold_percent"),
        ({"threshold_percent": True}, "threshold_percent"),
        ({"margin_seconds": -0.1}, "margin_seconds"),
        ({"margin_seconds": "0.3"}, "margin_seconds"),
    ],
)
def test_invalid_silence_settings_fail_clearly(
    tmp_path: Path,
    section: dict[str, object],
    message: str,
) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"auto_editor": section}), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_auto_editor_config(path)


def test_auto_editor_section_must_be_an_object(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"auto_editor": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="auto_editor"):
        load_auto_editor_config(path)


def test_root_config_must_be_an_object(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="config.json"):
        load_auto_editor_config(path)

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "有償版用スクリプト" / "resolve_session.py"
SPEC = importlib.util.spec_from_file_location("resolve_session_under_test", SCRIPT_PATH)
RESOLVE_SESSION = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["resolve_session_under_test"] = RESOLVE_SESSION
SPEC.loader.exec_module(RESOLVE_SESSION)


class ProjectManager:
    def __init__(self, names=(), *, imported=True, project=None) -> None:
        self.names = names
        self.imported = imported
        self.project = project

    def GetProjectListInCurrentFolder(self):
        return self.names

    def ImportProject(self, _path, _name):
        return self.imported

    def LoadProject(self, _name):
        return self.project


class NamedObject:
    def __init__(self, name: str) -> None:
        self.name = name

    def GetName(self) -> str:
        return self.name


def test_project_name_is_only_changed_when_it_already_exists() -> None:
    assert RESOLVE_SESSION.make_unique_name(ProjectManager(), "talk") == "talk"

    duplicate = RESOLVE_SESSION.make_unique_name(ProjectManager(["talk"]), "talk")

    assert duplicate.startswith("talk_")


def test_template_is_imported_and_loaded(tmp_path: Path) -> None:
    template = tmp_path / "template.drp"
    template.write_bytes(b"template")
    project = NamedObject("talk")

    result = RESOLVE_SESSION.create_project_from_template(
        ProjectManager(project=project),
        template,
        "talk",
    )

    assert result is project


def test_missing_template_fails_before_resolve_is_called(tmp_path: Path) -> None:
    with pytest.raises(RESOLVE_SESSION.ResolveSessionError, match="テンプレート"):
        RESOLVE_SESSION.create_project_from_template(
            ProjectManager(),
            tmp_path / "missing.drp",
            "talk",
        )


@pytest.mark.parametrize(("value", "expected"), [("29.97", 29.97), ("0", 30.0)])
def test_timeline_frame_rate_has_a_safe_fallback(value: str, expected: float) -> None:
    class Timeline:
        def GetSetting(self, _name):
            return value

    assert RESOLVE_SESSION.timeline_frame_rate(Timeline()) == expected


def test_missing_main_timeline_is_reported() -> None:
    class Project:
        def GetCurrentTimeline(self):
            return None

    with pytest.raises(RESOLVE_SESSION.ResolveSessionError, match="タイムライン"):
        RESOLVE_SESSION.open_main_timeline(Project())

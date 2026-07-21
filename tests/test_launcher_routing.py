import re
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
SCRIPT_DIR = REPO_ROOT / "有償版用スクリプト"


def powershell_python_targets(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    return re.findall(r'^& python\s+"?([^"\s]+\.py)"?', content, re.MULTILINE)


def test_familiar_launcher_routes_only_to_stable_resolve_editor() -> None:
    launcher = SCRIPT_DIR / "run_auto_video_editor.ps1"

    assert powershell_python_targets(launcher) == ["auto_video_editor.py"]
    assert "highlight_video.py" not in launcher.read_text(encoding="utf-8")


def test_advanced_launcher_routes_only_to_highlight_editor() -> None:
    launcher = SCRIPT_DIR / "run_advanced_auto_video_editor.ps1"
    content = launcher.read_text(encoding="utf-8")

    assert '$Arguments = @("highlight_video.py")' in content
    assert 'python "auto_video_editor.py"' not in content


def test_shortcut_creator_exposes_both_routes_with_clear_names() -> None:
    content = (SCRIPT_DIR / "create_desktop_shortcut.ps1").read_text(
        encoding="utf-8"
    )

    assert 'File = "run_auto_video_editor.ps1"' in content
    assert 'Name = "DaVinci Resolve Auto Editor - Stable.lnk"' in content
    assert 'File = "run_advanced_auto_video_editor.ps1"' in content
    assert 'Name = "DaVinci Resolve Auto Editor - Advanced.lnk"' in content

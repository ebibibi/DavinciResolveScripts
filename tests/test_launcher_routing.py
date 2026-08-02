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


def test_stable_editor_uses_current_silence_cut_settings() -> None:
    content = (SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")

    assert '"--margin", "0.3sec"' in content
    assert '"--edit", "audio:threshold=3%"' in content
    assert "threshold=1%" not in content


def test_both_routes_cut_silence_with_the_same_settings() -> None:
    stable = (SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")
    shared = (SCRIPT_DIR / "dual_source.py").read_text(encoding="utf-8")

    margin = re.search(r'"--margin", "([^"]+)"', stable).group(1)
    edit = re.search(r'"--edit", "([^"]+)"', stable).group(1)
    assert f'SILENCE_MARGIN = "{margin}"' in shared
    assert f'SILENCE_EDIT = "{edit}"' in shared


def test_shortcut_creator_exposes_both_routes_with_clear_names() -> None:
    content = (SCRIPT_DIR / "create_desktop_shortcut.ps1").read_text(
        encoding="utf-8"
    )

    assert 'File = "run_auto_video_editor.ps1"' in content
    assert 'Name = "DaVinci Resolve Auto Editor - Stable.lnk"' in content
    assert 'File = "run_advanced_auto_video_editor.ps1"' in content
    assert 'Name = "DaVinci Resolve Auto Editor - Advanced.lnk"' in content


def test_dual_source_launcher_routes_only_to_its_own_editor() -> None:
    launcher = SCRIPT_DIR / "run_dual_source_video_editor.ps1"
    content = launcher.read_text(encoding="utf-8")

    # The script name is passed explicitly and relatively, like the advanced route.
    assert '$Arguments = @("dual_source_video_editor.py")' in content
    assert "auto_video_editor.py" not in content
    assert "highlight_video.py" not in content


def test_the_stable_launcher_did_not_take_on_the_dual_source_route() -> None:
    stable = (SCRIPT_DIR / "run_auto_video_editor.ps1").read_text(encoding="utf-8")
    stable_editor = (SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")

    assert "dual_source" not in stable
    assert "dual_source" not in stable_editor


def test_shortcut_creator_exposes_the_dual_source_route() -> None:
    content = (SCRIPT_DIR / "create_desktop_shortcut.ps1").read_text(encoding="utf-8")

    assert 'File = "run_dual_source_video_editor.ps1"' in content
    assert 'Name = "DaVinci Resolve Auto Editor - Dual Source.lnk"' in content

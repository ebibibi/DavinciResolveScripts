import re
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
SCRIPT_DIR = REPO_ROOT / "有償版用スクリプト"
FREE_SCRIPT_DIR = REPO_ROOT / "無料版用スクリプト"


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


def test_stable_editor_loads_environment_silence_cut_settings() -> None:
    content = (SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")

    assert "load_auto_editor_config()" in content
    assert '"--margin", auto_editor.margin' in content
    assert '"--edit", auto_editor.edit_expression' in content


def test_all_paid_routes_use_the_shared_silence_settings() -> None:
    stable = (SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")
    dual = (SCRIPT_DIR / "dual_source_video_editor.py").read_text(encoding="utf-8")
    advanced = (SCRIPT_DIR / "highlight_video.py").read_text(encoding="utf-8")

    assert "load_auto_editor_config()" in stable
    assert "load_auto_editor_config()" in dual
    assert "parse_auto_editor_config(data)" in advanced


def test_free_route_uses_the_shared_silence_settings() -> None:
    content = (FREE_SCRIPT_DIR / "auto_video_editor.py").read_text(encoding="utf-8")

    assert "load_auto_editor_config()" in content
    assert '"--margin", auto_editor.margin' in content
    assert '"--edit", auto_editor.edit_expression' in content


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

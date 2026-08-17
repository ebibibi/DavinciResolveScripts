import re
from pathlib import Path

import pytest


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


def test_advanced_launcher_routes_only_to_the_ffmpeg_editor() -> None:
    """ADR-015 以降、advanced ルートの入口は advanced_video_editor.py になる。"""
    launcher = SCRIPT_DIR / "run_advanced_auto_video_editor.ps1"
    content = launcher.read_text(encoding="utf-8")

    assert '$Arguments = @("advanced_video_editor.py")' in content
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


LAUNCHERS = (
    "run_auto_video_editor.ps1",
    "run_advanced_auto_video_editor.ps1",
    "run_dual_source_video_editor.ps1",
    "create_desktop_shortcut.ps1",
)


@pytest.mark.parametrize("launcher", LAUNCHERS)
def test_every_launcher_updates_itself_before_it_runs(launcher: str) -> None:
    """A merged fix that never reaches the editing machine is not a fix.

    PR #29 sat unmerged for two weeks and the working copy was never pulled, so
    the broken placement kept shipping. Each entry point now updates first.
    """
    content = (SCRIPT_DIR / launcher).read_text(encoding="utf-8")

    assert 'update_repository.ps1' in content
    assert "Update-Repository -RepositoryRoot" in content


def test_the_update_step_never_stops_the_run_and_never_discards_work() -> None:
    content = (SCRIPT_DIR / "update_repository.ps1").read_text(encoding="utf-8")

    # 編集できないより、少し古い版で編集できる方がよい。失敗はすべて $false を
    # 返して続行する。
    assert "throw" not in content
    assert "exit 1" not in content
    # 作業を捨てる操作は入れない。未コミットの変更があれば更新しないだけ。
    assert "reset --hard" not in content
    assert "checkout --force" not in content
    assert "clean -" not in content
    # ff-onlyでない pull は勝手にマージコミットを作る。
    assert "pull --ff-only" in content


def test_the_update_step_reports_the_version_that_actually_ran() -> None:
    content = (SCRIPT_DIR / "update_repository.ps1").read_text(encoding="utf-8")

    assert "Get-RepositoryVersion" in content
    # 「更新しなかった」と「更新したのにおかしい」を取り違えないよう、失敗経路でも
    # 動いている版を出す。
    assert content.count("現在の版") >= 3

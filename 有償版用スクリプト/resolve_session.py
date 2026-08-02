#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Connect to DaVinci Resolve and open a project made from the template.

The stable editor keeps its own copy of this bootstrap on purpose: ADR-007 says
its behavior must not move when something else changes. This module exists so
newer entry points do not have to repeat the connection dance themselves.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RESOLVE_API_MODULE_PATHS = {
    "Windows": [
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules",
    ],
    "Darwin": [
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
    ],
    "Linux": [
        "/opt/resolve/Developer/Scripting/Modules",
        "/home/resolve/Developer/Scripting/Modules",
    ],
}

RESOLVE_EXECUTABLES = {
    "Windows": [
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
        r"C:\Program Files (x86)\Blackmagic Design\DaVinci Resolve\Resolve.exe",
    ],
    "Darwin": ["/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve"],
    "Linux": ["/opt/resolve/bin/resolve", "/usr/bin/resolve"],
}


class ResolveSessionError(RuntimeError):
    """Raised when DaVinci Resolve cannot be reached or prepared."""


def add_resolve_api_to_sys_path() -> None:
    """Make `DaVinciResolveScript` importable from an outside interpreter."""
    candidates = []
    env_api = os.environ.get("RESOLVE_SCRIPT_API")
    if env_api:
        candidates.append(os.path.join(env_api, "Modules"))
    candidates += RESOLVE_API_MODULE_PATHS.get(platform.system(), [])

    for candidate in candidates:
        if candidate and os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.append(candidate)
            print(f"✓ APIパス追加: {candidate}")


def launch_resolve_if_needed() -> bool:
    """Start DaVinci Resolve if it is installed but not running."""
    for executable in RESOLVE_EXECUTABLES.get(platform.system(), []):
        if os.path.isfile(executable):
            try:
                print(f"DaVinci Resolveを起動中: {executable}")
                subprocess.Popen(
                    [executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True
            except OSError as error:
                print(f"起動失敗: {error}")
    return False


def connect(retries: int = 60, interval: float = 1.0):
    """Return the Resolve object, launching the application if it is not up."""
    add_resolve_api_to_sys_path()
    try:
        import DaVinciResolveScript as bmd
    except ImportError as error:
        raise ResolveSessionError(f"DaVinciResolveScript を読み込めません: {error}") from error

    resolve = bmd.scriptapp("Resolve")
    if resolve is not None:
        return resolve

    print("DaVinci Resolveが起動していません。起動を試行...")
    launch_resolve_if_needed()
    time.sleep(10)
    for attempt in range(retries):
        resolve = bmd.scriptapp("Resolve")
        if resolve:
            print(f"✓ 接続成功（試行 {attempt + 1}/{retries}）")
            return resolve
        time.sleep(interval)

    raise ResolveSessionError("DaVinci Resolveに接続できませんでした")


def make_unique_name(project_manager, base_name: str) -> str:
    """Add a timestamp only when the plain project name is already taken."""
    try:
        existing = set(project_manager.GetProjectListInCurrentFolder() or [])
    except Exception:
        existing = set()

    if base_name not in existing:
        return base_name
    return f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def create_project_from_template(project_manager, template_path: Path, project_name: str):
    """Import the template and open it under a name that is free."""
    template_path = Path(template_path)
    if not template_path.exists():
        raise ResolveSessionError(f"テンプレートファイルが見つかりません: {template_path}")

    safe_name = make_unique_name(project_manager, project_name)
    print(f"テンプレートからプロジェクトを作成: {safe_name}")

    imported = project_manager.ImportProject(str(template_path), safe_name)
    if not imported:
        raise ResolveSessionError("テンプレートインポートに失敗しました")

    project = project_manager.LoadProject(safe_name)
    if not project:
        raise ResolveSessionError(f"プロジェクトを開けませんでした: {safe_name}")

    print(f"✓ プロジェクトを開きました: {project.GetName()}")
    return project


def open_main_timeline(project):
    """Return the timeline the body of the video is built on."""
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise ResolveSessionError("タイムラインが見つかりません")
    print(f"✓ 対象タイムライン: {timeline.GetName()}")
    return timeline


def timeline_frame_rate(timeline) -> float:
    """Return the timeline frame rate, falling back to 30 when unreadable."""
    try:
        frame_rate = float(timeline.GetSetting("timelineFrameRate"))
    except (TypeError, ValueError, AttributeError):
        return 30.0
    return frame_rate if frame_rate > 0 else 30.0


def finish(resolve, project, timeline) -> None:
    """Park the playhead at the start and show the result on the Edit page."""
    try:
        timeline.SetCurrentTimecode("00:00:00:00")
    except Exception as error:
        print(f"編集ポジション移動エラー: {error}")

    try:
        resolve.OpenPage("edit")
    except Exception:
        pass

    print(f"\n✓ 全処理完了！プロジェクト '{project.GetName()}' が準備できました。")

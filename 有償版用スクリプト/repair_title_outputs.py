"""Reconnect missing EBI title outputs on the current timeline, after a backup."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import resolve_session


def disconnected_titles(timeline: Any) -> list[tuple[str, Any, Any, Any]]:
    candidates = []
    for track in range(1, timeline.GetTrackCount("video") + 1):
        for item in timeline.GetItemListInTrack("video", track) or []:
            if not item.GetName().startswith("EBI_"):
                continue
            comp = item.GetFusionCompByIndex(1)
            if comp is None:
                continue
            template = comp.FindTool("Template")
            media_out = comp.FindTool("MediaOut1")
            if template is None or media_out is None:
                continue
            if template.GetAttrs().get("TOOLS_RegID") != "MacroOperator":
                continue
            # These published controls identify the bundled EBI graph.
            if (
                template.FindInput("StyledText") is None
                or template.FindInput("Scale") is None
            ):
                continue
            destination = media_out.FindMainInput(1)
            output = template.FindMainOutput(1)
            if destination is None or output is None:
                print(
                    f"Skipped {item.GetName()}: missing input/output; inspect in Fusion."
                )
                continue
            if destination.GetConnectedOutput() is not None:
                print(
                    f"Already connected: {item.GetName()} (any render error needs separate diagnosis)."
                )
                continue
            candidates.append((item.GetName(), comp, media_out, output))
    return candidates


def repair_current_timeline(manager: Any, backup: Path, dry_run: bool = False) -> int:
    project = manager.GetCurrentProject()
    if project is None or project.GetCurrentTimeline() is None:
        raise RuntimeError("Open the affected project and timeline in Resolve first.")
    candidates = disconnected_titles(project.GetCurrentTimeline())
    print(f"Disconnected EBI titles on current timeline: {len(candidates)}")
    if dry_run or not candidates:
        return 0
    if backup.exists():
        raise FileExistsError(f"Refusing to overwrite backup: {backup}")
    backup.parent.mkdir(parents=True, exist_ok=True)
    if (
        not manager.ExportProject(project.GetName(), str(backup))
        or not backup.is_file()
    ):
        raise RuntimeError("Project backup failed; no connections were changed.")
    print(f"Project backup: {backup}")
    repaired = 0
    for name, comp, media_out, output in candidates:
        comp.StartUndo("Reconnect EBI title output")
        try:
            if media_out.ConnectInput("Input", output) is False:
                raise RuntimeError(f"Could not reconnect {name}")
            if media_out.FindMainInput(1).GetConnectedOutput() is None:
                raise RuntimeError(f"Connection read-back failed for {name}")
            repaired += 1
            print(f"Reconnected: {name}")
        finally:
            comp.EndUndo(True)
    if not manager.SaveProject():
        raise RuntimeError(
            "Connections changed, but saving failed. Save the project in Resolve."
        )
    print(
        f"Reconnected {repaired} titles. Verify their images in Resolve; rendering has not been verified by this script."
    )
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    resolve_session.add_resolve_api_to_sys_path()
    import DaVinciResolveScript as bmd

    resolve = bmd.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError("Start Resolve and open the affected timeline first.")
    backup = args.backup or (
        Path.home()
        / "Documents"
        / "ResolveTitleRepair"
        / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".drp")
    )
    repair_current_timeline(resolve.GetProjectManager(), backup, args.dry_run)


if __name__ == "__main__":
    main()

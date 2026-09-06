"""Import the bundled DRP as a separate project and export title boundary frames.

Requires a running Resolve Studio and Pillow on the validation machine. Leaves
the review project open; never edits an existing project or starts queued jobs.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from build_title_presets import ROOT, load_presets


def pool_clips(folder) -> dict:
    """Collect clips from the whole Media Pool tree, not just its root."""
    clips = {clip.GetName(): clip for clip in folder.GetClipList() or []}
    for sub in folder.GetSubFolderList() or []:
        clips.update(pool_clips(sub))
    return clips


def title_bin(folder, names: set):
    """Return the bin holding the bundled titles."""
    if names <= {clip.GetName() for clip in folder.GetClipList() or []}:
        return folder
    for sub in folder.GetSubFolderList() or []:
        found = title_bin(sub, names)
        if found is not None:
            return found
    return None


def validate(destination: Path) -> dict:
    sys.path.insert(0, str(ROOT / "有償版用スクリプト"))
    import resolve_session
    from PIL import Image

    resolve_session.add_resolve_api_to_sys_path()
    import DaVinciResolveScript as bmd

    resolve = bmd.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError("Open Resolve Studio before validating titles.")
    manager = resolve.GetProjectManager()
    current = manager.GetCurrentProject()
    if current is not None:
        root = current.GetMediaPool().GetRootFolder()
        # SaveProject() on a never-saved project opens a modal "Save Current
        # Project" dialog that blocks every later scripting call, so leave a
        # pristine "Untitled Project" alone: it holds nothing to lose.
        holds_work = (
            current.GetTimelineCount() or root.GetClipList() or root.GetSubFolderList()
        )
        if holds_work and not manager.SaveProject():
            raise RuntimeError("Could not save the currently open project.")
    name = "EBI_Title_Library_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if not manager.ImportProject(str(ROOT / "有償版用スクリプト/テンプレート.drp"), name):
        raise RuntimeError("Could not import the template into a separate project.")
    project = manager.LoadProject(name)
    pool = project.GetMediaPool()
    clips = pool_clips(pool.GetRootFolder())
    fonts = resolve.Fusion().FontManager.GetFontList()
    destination.mkdir(parents=True, exist_ok=True)
    report = {"version": resolve.GetVersionString(), "project": name, "checks": []}
    for seconds in (2, 5, 15):
        timeline = pool.CreateEmptyTimeline(f"EBI preview {seconds}s")
        project.SetCurrentTimeline(timeline)
        fps = round(float(timeline.GetSetting("timelineFrameRate")))
        for preset in load_presets():
            assert preset["style"] in fonts.get(preset["font"], {}), preset["font"]
            items = pool.AppendToTimeline([{
                "mediaPoolItem": clips[preset["name"]],
                # Resolve 20.1's generator API uses an exclusive source end.
                "startFrame": 0, "endFrame": seconds * fps,
            }])
            assert len(items) == 1, preset["name"]
            item = items[0]
            assert item.GetDuration() == seconds * fps, item.GetDuration()
            comp = item.GetFusionCompByIndex(1)
            output = comp.FindTool("MediaOut1").FindMainInput(1).GetConnectedOutput()
            assert output is not None, f"Disconnected: {preset['name']}"
            assert comp.FindTool("MainText").GetInput("StyledText") == preset["text"]
            controls = comp.FindTool("Template").GetInputList() or {}
            assert any(i.GetAttrs().get("INPS_ID") == "StyledText" for i in controls.values())
            for edge, frame in (("first", item.GetStart()), ("last", item.GetEnd() - 1)):
                frame = int(frame)
                s, f = divmod(frame, fps)
                m, s = divmod(s, 60)
                h, m = divmod(m, 60)
                assert timeline.SetCurrentTimecode(f"{h:02}:{m:02}:{s:02}:{f:02}")
                path = destination / f"{preset['id']}_{seconds}s_{edge}.png"
                assert project.ExportCurrentFrameAsStill(str(path)), path
                # Empty/no-frame output is black. This checks actual pixels,
                # separately from the API's export-success return value.
                with Image.open(path) as image:
                    extrema = image.convert("RGB").getextrema()
                    assert max(high - low for low, high in extrema) > 30, path
                report["checks"].append({"preset": preset["name"], "seconds": seconds,
                                         "edge": edge, "path": str(path)})
            print(f"PASS {seconds}s {preset['name']}", flush=True)
    folder = title_bin(pool.GetRootFolder(), {p["name"] for p in load_presets()})
    assert folder is not None, "Bundled titles are not in a single bin"
    assert folder.Export(str(ROOT / "title_presets/EBI_Titles.drb"))
    assert manager.SaveProject()
    (destination / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(args.output)

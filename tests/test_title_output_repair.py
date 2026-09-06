"""Repair must never change footage, connected titles, text or clip timing."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "有償版用スクリプト"))
from repair_title_outputs import repair_current_timeline


def setup_project(
    backup, *, connected=False, name="EBI_01_通常_白文字", backup_ok=True
):
    manager = MagicMock()
    project = manager.GetCurrentProject.return_value
    timeline = project.GetCurrentTimeline.return_value
    timeline.GetTrackCount.return_value = 1
    item = MagicMock()
    item.GetName.return_value = name
    timeline.GetItemListInTrack.return_value = [item]
    comp = item.GetFusionCompByIndex.return_value
    template, media_out, output = MagicMock(), MagicMock(), MagicMock()
    template.GetAttrs.return_value = {"TOOLS_RegID": "MacroOperator"}
    template.FindMainOutput.return_value = output
    comp.FindTool.side_effect = lambda name: {
        "Template": template,
        "MediaOut1": media_out,
    }[name]
    dest = media_out.FindMainInput.return_value
    dest.GetConnectedOutput.return_value = output if connected else None

    def connect(name, target):
        assert name == "Input" and target is output
        dest.GetConnectedOutput.return_value = target
        return True

    media_out.ConnectInput.side_effect = connect

    def export(name, path):
        if backup_ok:
            Path(path).write_bytes(b"backup")
        return backup_ok

    manager.ExportProject.side_effect = export
    manager.SaveProject.return_value = True
    return manager, comp, template, media_out


def test_repair_backs_up_and_reconnects_without_rebuilding(tmp_path):
    backup = tmp_path / "before.drp"
    manager, comp, template, media_out = setup_project(backup)
    assert repair_current_timeline(manager, backup) == 1
    assert backup.read_bytes() == b"backup"
    template.SetInput.assert_not_called()
    comp.LoadSettings.assert_not_called()
    media_out.ConnectInput.assert_called_once()
    manager.SaveProject.assert_called_once()
    comp.EndUndo.assert_called_once_with(True)


@pytest.mark.parametrize(
    "connected,name", [(True, "EBI_01_通常_白文字"), (False, "my footage")]
)
def test_other_or_connected_clips_are_untouched(tmp_path, connected, name):
    backup = tmp_path / "before.drp"
    manager, _, _, media_out = setup_project(backup, connected=connected, name=name)
    assert repair_current_timeline(manager, backup) == 0
    media_out.ConnectInput.assert_not_called()
    manager.ExportProject.assert_not_called()
    manager.SaveProject.assert_not_called()


def test_failed_backup_prevents_any_edit(tmp_path):
    backup = tmp_path / "before.drp"
    manager, _, _, media_out = setup_project(backup, backup_ok=False)
    with pytest.raises(RuntimeError, match="backup failed"):
        repair_current_timeline(manager, backup)
    media_out.ConnectInput.assert_not_called()


def test_dry_run_and_existing_backup_prevent_changes(tmp_path):
    backup = tmp_path / "before.drp"
    manager, _, _, media_out = setup_project(backup)
    assert repair_current_timeline(manager, backup, dry_run=True) == 0
    manager.ExportProject.assert_not_called()
    backup.write_text("existing")
    with pytest.raises(FileExistsError):
        repair_current_timeline(manager, backup)
    media_out.ConnectInput.assert_not_called()
    assert backup.read_text() == "existing"


def test_failed_connection_is_not_reported_as_success(tmp_path):
    backup = tmp_path / "before.drp"
    manager, comp, _, media_out = setup_project(backup)
    media_out.ConnectInput.side_effect = None
    media_out.ConnectInput.return_value = False
    with pytest.raises(RuntimeError, match="Could not reconnect"):
        repair_current_timeline(manager, backup)
    manager.SaveProject.assert_not_called()
    comp.EndUndo.assert_called_once_with(True)

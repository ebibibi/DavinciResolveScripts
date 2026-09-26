"""The generated clips land in one Media Pool bin without disturbing the edit."""

import json
from pathlib import Path

import pytest

import ending_media
import media_pool_clips

REPO_ROOT = Path(__file__).parents[1]
SCRIPT_DIR = REPO_ROOT / "有償版用スクリプト"
FREE_SCRIPT_DIR = REPO_ROOT / "無料版用スクリプト"


class FakeClip:
    def __init__(self, name: str):
        self._name = name

    def GetName(self) -> str:
        return self._name


class FakeFolder:
    def __init__(self, name: str, clips=()):
        self._name = name
        self.clips = [FakeClip(c) for c in clips]
        self.subfolders: list["FakeFolder"] = []

    def GetName(self) -> str:
        return self._name

    def GetSubFolderList(self):
        return list(self.subfolders)

    def GetClipList(self):
        return list(self.clips)


class FakeMediaPool:
    def __init__(self, root=None):
        self.root = root or FakeFolder("Master")
        self.current = self.root
        self.import_calls: list[list[str]] = []
        self.fail_import = False
        self.refuse_folder = False

    def GetRootFolder(self):
        return self.root

    def GetCurrentFolder(self):
        return self.current

    def SetCurrentFolder(self, folder) -> bool:
        if self.refuse_folder and folder is not self.root:
            return False
        self.current = folder
        return True

    def AddSubFolder(self, parent, name):
        folder = FakeFolder(name)
        parent.subfolders.append(folder)
        return folder

    def ImportMedia(self, paths):
        self.import_calls.append(list(paths))
        if self.fail_import:
            raise RuntimeError("Resolve refused the import")
        items = [FakeClip(Path(p).name) for p in paths]
        self.current.clips.extend(items)
        return items


@pytest.fixture
def bundled(tmp_path):
    """Three generated clips, all present only as bundled copies."""
    clips = []
    for name in ("EBI_CHAN_EYECATCH_morph.mp4", "EBI_CHAN_EYECATCH_slice.mp4",
                 "EBI_CHAN_OUTRO.mp4"):
        path = tmp_path / "assets" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"")
        clips.append((name, path))
    return tuple(clips)


def run(media_pool, clips, folders=()):
    return media_pool_clips.ensure_generated_clips(media_pool, clips, folders=folders)


def the_bin(media_pool):
    return media_pool_clips.find_bin(media_pool.root, media_pool_clips.BIN_NAME)


def test_the_bin_is_created_under_the_root_and_filled(bundled):
    media_pool = FakeMediaPool()

    imported = run(media_pool, bundled)

    folder = the_bin(media_pool)
    assert folder is not None
    assert imported == [name for name, _ in bundled]
    assert media_pool_clips.clip_names_in(folder) == {name for name, _ in bundled}
    # Nothing was imported into the root.
    assert media_pool.root.clips == []


def test_the_current_folder_is_put_back(bundled):
    other = FakeFolder("Timelines")
    media_pool = FakeMediaPool()
    media_pool.root.subfolders.append(other)
    media_pool.current = other

    run(media_pool, bundled)

    assert media_pool.current is other


def test_running_twice_imports_nothing_the_second_time(bundled):
    media_pool = FakeMediaPool()

    run(media_pool, bundled)
    second = run(media_pool, bundled)

    assert second == []
    assert len(media_pool.import_calls) == 1
    assert len([f for f in media_pool.root.subfolders
                if f.GetName() == media_pool_clips.BIN_NAME]) == 1


def test_clips_already_in_the_bin_are_skipped(bundled):
    existing = FakeFolder(media_pool_clips.BIN_NAME, clips=["EBI_CHAN_OUTRO.mp4"])
    media_pool = FakeMediaPool()
    media_pool.root.subfolders.append(existing)

    imported = run(media_pool, bundled)

    assert imported == ["EBI_CHAN_EYECATCH_morph.mp4", "EBI_CHAN_EYECATCH_slice.mp4"]
    assert [Path(p).name for p in media_pool.import_calls[0]] == imported


def test_a_clip_found_nowhere_is_skipped_and_the_rest_imported(bundled, tmp_path):
    clips = (*bundled, ("EBI_CHAN_EYECATCH_gone.mp4", tmp_path / "missing.mp4"))
    media_pool = FakeMediaPool()

    imported = run(media_pool, clips)

    assert "EBI_CHAN_EYECATCH_gone.mp4" not in imported
    assert len(imported) == 3


def test_a_failed_import_never_stops_the_edit(bundled, capsys):
    media_pool = FakeMediaPool()
    media_pool.fail_import = True

    assert run(media_pool, bundled) == []
    assert media_pool.current is media_pool.root
    assert "編集は続けます" in capsys.readouterr().out


def test_a_bin_that_cannot_be_created_is_skipped(bundled):
    media_pool = FakeMediaPool()
    media_pool.AddSubFolder = lambda parent, name: None

    assert run(media_pool, bundled) == []
    assert media_pool.import_calls == []


def test_a_bin_that_cannot_be_opened_imports_nothing_into_the_wrong_folder(bundled):
    media_pool = FakeMediaPool()
    media_pool.refuse_folder = True

    assert run(media_pool, bundled) == []
    assert media_pool.import_calls == []


def test_the_onedrive_copy_of_a_stinger_is_preferred(bundled, tmp_path):
    onedrive = tmp_path / "onedrive"
    onedrive.mkdir()
    (onedrive / "EBI_CHAN_EYECATCH_morph.mp4").write_bytes(b"")
    media_pool = FakeMediaPool()

    run(media_pool, bundled, folders=[str(tmp_path / "old"), str(onedrive)])

    paths = media_pool.import_calls[0]
    assert str(onedrive / "EBI_CHAN_EYECATCH_morph.mp4") in paths
    assert str(bundled[1][1]) in paths  # slice only exists as the bundled copy


def test_every_generated_clip_is_bundled_with_its_eyecatch_name():
    timeline = json.loads(
        (REPO_ROOT / "tools" / "eyecatch" / "timeline.json").read_text(encoding="utf-8")
    )
    stingers = [n for n, v in timeline["variants"].items() if v.get("kind") != "outro"]

    assert list(ending_media.EYECATCH_VARIANTS) == stingers
    names = [name for name, _ in ending_media.GENERATED_CLIPS]
    assert names == [f"EBI_CHAN_EYECATCH_{n}.mp4" for n in stingers] + ["EBI_CHAN_OUTRO.mp4"]
    for name, bundled in ending_media.GENERATED_CLIPS:
        assert bundled.is_file(), bundled
        assert bundled.name == name
        assert bundled.stat().st_size < 5 * 1024 * 1024 or name == "EBI_CHAN_OUTRO.mp4"


def test_the_bundled_stingers_resolve_when_onedrive_has_none():
    for name, bundled in ending_media.GENERATED_CLIPS:
        assert ending_media.find_material(name, bundled, folders=()) == str(bundled)


@pytest.mark.parametrize(
    ("script", "edit_starts"),
    [
        (SCRIPT_DIR / "auto_video_editor.py", "ImportTimelineFromFile("),
        (SCRIPT_DIR / "dual_source_video_editor.py", "open_main_timeline(project)"),
        (FREE_SCRIPT_DIR / "auto_video_editor.py", "ImportTimelineFromFile("),
    ],
    ids=["stable", "dual", "free"],
)
def test_every_resolve_route_fills_the_bin_right_after_it_has_the_media_pool(
    script, edit_starts
):
    content = script.read_text(encoding="utf-8")

    fill = content.index("ensure_generated_clips(media_pool)")
    assert content.index("media_pool = project.GetMediaPool()") < fill
    assert fill < content.index(edit_starts)

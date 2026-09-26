"""Put the channel's generated clips into a Media Pool bin of every project.

Every Resolve route calls `ensure_generated_clips` right after it has the
project's Media Pool. The ten eyecatch stingers and the end card are imported
into one bin under the root, so they are at hand while finishing an edit.

This never stops an edit: anything that goes wrong is reported and skipped.
Clips already in the bin are not imported again, and the Media Pool's current
folder is put back afterwards, so the rest of each script imports exactly where
it did before.
"""

from __future__ import annotations

from ending_media import GENERATED_CLIPS, MATERIAL_DIR_CANDIDATES, find_material

BIN_NAME = "EBI アイキャッチ"


def find_bin(root, name: str):
    """ルート直下の `name` という名前のビン（無ければNone）"""
    for folder in root.GetSubFolderList() or []:
        if folder.GetName() == name:
            return folder
    return None


def clip_names_in(folder) -> set[str]:
    return {item.GetName() for item in folder.GetClipList() or []}


def ensure_generated_clips(
    media_pool,
    clips=GENERATED_CLIPS,
    bin_name: str = BIN_NAME,
    folders=MATERIAL_DIR_CANDIDATES,
) -> list[str]:
    """ビンを用意し、まだ入っていない生成素材を取り込む。取り込んだ名前を返す。"""
    print(f"生成素材をメディアプールのビン「{bin_name}」に用意します")
    try:
        previous = media_pool.GetCurrentFolder()
    except Exception as error:
        print(f"! 現在のフォルダを取得できません（生成素材の取り込みをスキップ）: {error}")
        return []

    try:
        return _import_missing(media_pool, clips, bin_name, folders)
    except Exception as error:
        print(f"! 生成素材を取り込めませんでした（編集は続けます）: {error}")
        return []
    finally:
        _restore_folder(media_pool, previous)


def _import_missing(media_pool, clips, bin_name, folders) -> list[str]:
    root = media_pool.GetRootFolder()
    folder = find_bin(root, bin_name) or media_pool.AddSubFolder(root, bin_name)
    if not folder:
        print(f"! ビン「{bin_name}」を作れませんでした（スキップ）")
        return []

    present = clip_names_in(folder)
    paths = []
    for name, bundled in clips:
        if name in present:
            continue
        path = find_material(name, bundled, folders)
        if path is None:
            print(f"! 生成素材が見つかりません（スキップ）: {name}")
            continue
        paths.append(path)

    if not paths:
        print(f"✓ 生成素材はすべてビン「{bin_name}」にあります")
        return []

    if not media_pool.SetCurrentFolder(folder):
        print(f"! ビン「{bin_name}」を開けませんでした（スキップ）")
        return []
    imported = [item.GetName() for item in media_pool.ImportMedia(paths) or []]
    if len(imported) < len(paths):
        print(f"! 生成素材の一部を取り込めませんでした（{len(imported)}/{len(paths)}）")
    print(f"✓ 生成素材を{len(imported)}本ビン「{bin_name}」に取り込みました")
    return imported


def _restore_folder(media_pool, previous) -> None:
    if previous is None:
        return
    try:
        media_pool.SetCurrentFolder(previous)
    except Exception as error:
        print(f"! 元のフォルダに戻せませんでした: {error}")

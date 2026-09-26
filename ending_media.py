"""Locate the channel's clips: the ending, the end card and the stingers.

The order at the end of a video is the channel ending `03_EBI_CHAN_IN.mov`
followed by the end card `EBI_CHAN_OUTRO.mp4`. The clips live in the OneDrive
`!動画素材` folder, whose name has changed over time, so every known location
is tried. The generated clips (the end card and the eyecatch stingers from
`tools/eyecatch`) are also bundled in this repository, and that copy is used
when OneDrive does not have one: the launchers pull the repository before every
run, so the bundled copies are always present on the editing PC.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# OneDriveのフォルダ名は過去に変わっているため、実在する方を使う
MATERIAL_DIR_CANDIDATES = (
    r"C:\Users\masah\OneDrive - Masahiko Ebisuda (1)\Youtube動画作成場所\!動画素材",
    r"C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!動画素材",
    r"C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!動画素材",
)

ASSETS_DIR = REPO_ROOT / "assets"
ENDING_FILE_NAME = "03_EBI_CHAN_IN.mov"
OUTRO_FILE_NAME = "EBI_CHAN_OUTRO.mp4"
BUNDLED_OUTRO_PATH = ASSETS_DIR / OUTRO_FILE_NAME

# tools/eyecatch/timeline.json の順（テストで一致を確認している）
EYECATCH_VARIANTS = (
    "assemble", "bounce", "morph", "tunnel", "typewriter",
    "ripple", "slice", "orbit", "pixelate", "countdown",
)


def eyecatch_file_name(variant: str) -> str:
    return f"EBI_CHAN_EYECATCH_{variant}.mp4"


# tools/eyecatch で作った素材: (ファイル名, リポジトリ同梱版)
GENERATED_CLIPS = (
    *(
        (eyecatch_file_name(v), ASSETS_DIR / "eyecatch" / eyecatch_file_name(v))
        for v in EYECATCH_VARIANTS
    ),
    (OUTRO_FILE_NAME, BUNDLED_OUTRO_PATH),
)


def first_existing_path(candidates):
    """候補のうち実在する最初のパスを返す（無ければNone）"""
    return next((str(path) for path in candidates if os.path.exists(path)), None)


def material_candidates(file_name: str, folders=MATERIAL_DIR_CANDIDATES) -> list[str]:
    """`!動画素材` の各候補フォルダにある `file_name` のパス"""
    return [os.path.join(folder, file_name) for folder in folders]


def bundled_candidates(
    file_name: str, bundled: Path, folders=MATERIAL_DIR_CANDIDATES
) -> list[str]:
    """素材の候補。OneDriveを優先し、最後にリポジトリ同梱版"""
    return [*material_candidates(file_name, folders), str(bundled)]


def find_material(file_name: str, bundled: Path, folders=MATERIAL_DIR_CANDIDATES):
    """使う素材のパス（どこにも無ければNone）"""
    return first_existing_path(bundled_candidates(file_name, bundled, folders))


def outro_candidates(
    folders=MATERIAL_DIR_CANDIDATES, bundled: Path = BUNDLED_OUTRO_PATH
) -> list[str]:
    """エンドカードの候補。OneDriveを優先し、最後にリポジトリ同梱版"""
    return bundled_candidates(OUTRO_FILE_NAME, bundled, folders)


def find_outro_video(
    folders=MATERIAL_DIR_CANDIDATES, bundled: Path = BUNDLED_OUTRO_PATH
):
    """使うエンドカードのパス（どこにも無ければNone）"""
    return find_material(OUTRO_FILE_NAME, bundled, folders)

"""Locate the clips every Resolve route appends after the edited body.

The order at the end of a video is the channel ending `03_EBI_CHAN_IN.mov`
followed by the end card `EBI_CHAN_OUTRO.mp4`. Both live in the OneDrive
`!動画素材` folder, whose name has changed over time, so every known location
is tried. The end card is also bundled in this repository, and that copy is
used when OneDrive does not have one: the launchers pull the repository before
every run, so the bundled copy is always present on the editing PC.
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

ENDING_FILE_NAME = "03_EBI_CHAN_IN.mov"
OUTRO_FILE_NAME = "EBI_CHAN_OUTRO.mp4"
BUNDLED_OUTRO_PATH = REPO_ROOT / "assets" / OUTRO_FILE_NAME


def first_existing_path(candidates):
    """候補のうち実在する最初のパスを返す（無ければNone）"""
    return next((str(path) for path in candidates if os.path.exists(path)), None)


def material_candidates(file_name: str, folders=MATERIAL_DIR_CANDIDATES) -> list[str]:
    """`!動画素材` の各候補フォルダにある `file_name` のパス"""
    return [os.path.join(folder, file_name) for folder in folders]


def outro_candidates(
    folders=MATERIAL_DIR_CANDIDATES, bundled: Path = BUNDLED_OUTRO_PATH
) -> list[str]:
    """エンドカードの候補。OneDriveを優先し、最後にリポジトリ同梱版"""
    return [*material_candidates(OUTRO_FILE_NAME, folders), str(bundled)]


def find_outro_video(
    folders=MATERIAL_DIR_CANDIDATES, bundled: Path = BUNDLED_OUTRO_PATH
):
    """使うエンドカードのパス（どこにも無ければNone）"""
    return first_existing_path(outro_candidates(folders, bundled))

"""Remove named clips from the `main` timeline of a bundled Resolve DRP.

This is an offline asset tool, like build_title_presets.py. It deletes whole
timeline items (the `<Element>` around a `Sm2TiVideoClip` or `Sm2TiAudioClip`)
and nothing else: the Media Pool entry stays, and every other archive member is
written back with identical content and the same per-member compression.

    python tools/remove_timeline_clip.py 01_EBI_CHAN_OP.mov --template <drp>
"""

import argparse
import re
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "有償版用スクリプト" / "テンプレート.drp",
    ROOT / "無料版用スクリプト" / "テンプレート.drp",
)
SEQUENCE_PREFIX = "SeqContainer/"
CLIP_ELEMENT = re.compile(
    r"[ \t]*<Element>\s*<(Sm2TiVideoClip|Sm2TiAudioClip)\b.*?</\1>\s*</Element>\r?\n",
    re.DOTALL,
)
EMPTY_ITEMS = re.compile(r"<Items>\s*</Items>")


def timeline_members(archive: zipfile.ZipFile) -> list[str]:
    return [
        name
        for name in archive.namelist()
        if name.startswith(SEQUENCE_PREFIX) and name.endswith(".xml")
    ]


def clip_names(xml: str) -> list[str]:
    """Names of every timeline item in one sequence container."""
    return [
        re.search(r"<Name>(.*?)</Name>", match[0])[1]
        for match in CLIP_ELEMENT.finditer(xml)
    ]


def without_clip(xml: str, name: str) -> tuple[str, list[str]]:
    """Drop every item named `name`; return the new XML and the removed DbIds.

    A removed item must not leave a reference behind, so linked items
    (`LinkedItemSync`) pointing at it are refused rather than silently orphaned.
    """
    removed: list[str] = []

    def drop(match: re.Match) -> str:
        block = match[0]
        if re.search(r"<Name>(.*?)</Name>", block)[1] != name:
            return block
        removed.append(re.search(r'DbId="([^"]+)"', block)[1])
        return ""

    updated = CLIP_ELEMENT.sub(drop, xml)
    for identity in removed:
        if identity in updated:
            raise ValueError(f"{name} ({identity}) is still referenced after removal")
    # Resolve writes a track without items as <Items/>.
    return EMPTY_ITEMS.sub("<Items/>", updated), removed


def write_archive(source: Path, destination: Path, replacements: dict[str, bytes]) -> None:
    """Rewrite the archive, replacing only the given members."""
    with zipfile.ZipFile(source) as archive:
        members = {info.filename: info for info in archive.infolist()}
        unknown = set(replacements) - set(members)
        if unknown:
            raise ValueError(f"Not in the archive: {sorted(unknown)}")
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".drp", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, "w") as output:
                for info in archive.infolist():
                    data = replacements.get(info.filename)
                    output.writestr(
                        info, archive.read(info.filename) if data is None else data
                    )
            with zipfile.ZipFile(temporary) as check:
                if check.testzip():
                    raise ValueError("Generated DRP failed CRC validation")
            archive.close()  # Windows cannot replace an open source archive.
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def remove_clip(template: Path, name: str) -> list[str]:
    """Remove `name` from every timeline in `template`; return removed DbIds."""
    replacements: dict[str, bytes] = {}
    removed: list[str] = []
    with zipfile.ZipFile(template) as archive:
        for member in timeline_members(archive):
            xml = archive.read(member).decode("utf-8")
            updated, gone = without_clip(xml, name)
            if gone:
                replacements[member] = updated.encode("utf-8")
                removed += gone
    if replacements:
        write_archive(template, template, replacements)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="timeline item name, e.g. 01_EBI_CHAN_OP.mov")
    parser.add_argument("--template", type=Path, action="append")
    args = parser.parse_args()
    for template in args.template or TEMPLATES:
        removed = remove_clip(template, args.name)
        print(f"{template}: removed {len(removed)} item(s) {removed}")


if __name__ == "__main__":
    main()

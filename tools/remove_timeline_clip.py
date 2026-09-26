"""Remove named clips from the `main` timeline of a bundled Resolve DRP.

This is an offline asset tool, like build_title_presets.py. It deletes whole
timeline items (the `<Element>` around a `Sm2TiVideoClip` or `Sm2TiAudioClip`),
keeps the timeline's recorded length (`MediaExtents`) in step with what is
left, and with `--media-pool` also deletes the clip's Media Pool entry once
nothing refers to it any more. Every other archive member is written back with
identical content and the same per-member compression.

    python tools/remove_timeline_clip.py 01_EBI_CHAN_OP.mov
    python tools/remove_timeline_clip.py "Big 10 - TrackTribe.mp3" --media-pool
"""

import argparse
import re
import struct
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "有償版用スクリプト" / "テンプレート.drp",
    ROOT / "無料版用スクリプト" / "テンプレート.drp",
)
SEQUENCE_PREFIX = "SeqContainer/"
FOLDER = "MediaPool/Master/MpFolder.xml"
CLIP_ELEMENT = re.compile(
    r"[ \t]*<Element>\s*<(Sm2TiVideoClip|Sm2TiAudioClip)\b.*?</\1>\s*</Element>\r?\n",
    re.DOTALL,
)
# Media Pool items sit directly in the folder's MediaVec, two spaces deep.
POOL_ELEMENT = re.compile(
    r"^  <Element>\s*<(Sm2Mp\w+)\b.*?</\1>\s*</Element>\r?\n",
    re.DOTALL | re.MULTILINE,
)
EMPTY_ITEMS = re.compile(r"<Items>\s*</Items>")


def timeline_members(archive: zipfile.ZipFile) -> list[str]:
    return [
        name
        for name in archive.namelist()
        if name.startswith(SEQUENCE_PREFIX) and name.endswith(".xml")
    ]


def element_name(block: str) -> str:
    return re.search(r"<Name>(.*?)</Name>", block)[1]


def clip_names(xml: str) -> list[str]:
    """Names of every timeline item in one sequence container."""
    return [element_name(match[0]) for match in CLIP_ELEMENT.finditer(xml)]


def without_clip(xml: str, name: str) -> tuple[str, list[str]]:
    """Drop every item named `name`; return the new XML and the removed DbIds.

    A removed item must not leave a reference behind, so linked items
    (`LinkedItemSync`) pointing at it are refused rather than silently orphaned.
    """
    removed: list[str] = []

    def drop(match: re.Match) -> str:
        block = match[0]
        if element_name(block) != name:
            return block
        removed.append(re.search(r'DbId="([^"]+)"', block)[1])
        return ""

    updated = CLIP_ELEMENT.sub(drop, xml)
    for identity in removed:
        if identity in updated:
            raise ValueError(f"{name} ({identity}) is still referenced after removal")
    # Resolve writes a track without items as <Items/>.
    return EMPTY_ITEMS.sub("<Items/>", updated), removed


def timeline_end_frame(xml: str) -> int:
    """The frame where the last remaining timeline item ends."""
    return max(
        (
            int(re.search(r"<Start>(-?\d+)</Start>", m[0])[1])
            + int(re.search(r"<Duration>(\d+)</Duration>", m[0])[1])
            for m in CLIP_ELEMENT.finditer(xml)
        ),
        default=0,
    )


def with_extent(folder: str, sequence: str, end_frame: int) -> str:
    """Set a sequence's recorded length (two little-endian seconds) to `end_frame`."""
    pattern = re.compile(
        rf'(<Sm2Sequence DbId="{re.escape(sequence)}">.*?<MediaExtents>)'
        r"([0-9a-f]{32})(</MediaExtents>\s*<FrameRate>)([0-9a-f]{32})",
        re.DOTALL,
    )
    match = pattern.search(folder)
    if not match:
        raise ValueError(f"Sequence {sequence} has no MediaExtents")
    start, _ = struct.unpack("<dd", bytes.fromhex(match[2]))
    rate = struct.unpack("<d", bytes.fromhex(match[4])[:8])[0]
    if rate <= 0:
        raise ValueError(f"Sequence {sequence} has no frame rate")
    extent = struct.pack("<dd", start, end_frame / rate).hex()
    return folder[: match.start(2)] + extent + folder[match.end(2) :]


def without_pool_item(folder: str, name: str, others: list[str]) -> tuple[str, list[str]]:
    """Drop Media Pool items named `name` that nothing else refers to.

    `others` are the other archive members. An item still referred to anywhere
    (by DbId or media pool identity) is refused rather than orphaned.
    """
    removed: list[str] = []

    def drop(match: re.Match) -> str:
        block = match[0]
        if element_name(block) != name:
            return block
        removed.append(block)
        return ""

    updated = POOL_ELEMENT.sub(drop, folder)
    for block in removed:
        identities = re.findall(r'DbId="([^"]+)"', block) + re.findall(
            r"<UniqueMediaPoolItemId>(.*?)</UniqueMediaPoolItemId>", block
        )
        for identity in identities:
            if any(identity in text for text in [updated, *others]):
                raise ValueError(f"{name} ({identity}) is still referenced")
    return updated, [re.search(r'DbId="([^"]+)"', b)[1] for b in removed]


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


def remove_clip(template: Path, name: str, media_pool: bool = False) -> dict:
    """Remove `name` from every timeline (and optionally the Media Pool)."""
    with zipfile.ZipFile(template) as archive:
        texts = {n: archive.read(n).decode("utf-8") for n in archive.namelist()}
    original = dict(texts)
    report = {"timeline": [], "media_pool": []}

    for member in [n for n in texts if n.startswith(SEQUENCE_PREFIX)]:
        updated, gone = without_clip(texts[member], name)
        if not gone:
            continue
        texts[member] = updated
        report["timeline"] += gone
        sequence = re.search(r"<Sequence>(.*?)</Sequence>", updated)[1]
        texts[FOLDER] = with_extent(texts[FOLDER], sequence, timeline_end_frame(updated))

    if media_pool:
        others = [text for member, text in texts.items() if member != FOLDER]
        texts[FOLDER], report["media_pool"] = without_pool_item(
            texts[FOLDER], name, others
        )

    replacements = {
        member: text.encode("utf-8")
        for member, text in texts.items()
        if text != original[member]
    }
    if replacements:
        write_archive(template, template, replacements)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="timeline item name, e.g. 01_EBI_CHAN_OP.mov")
    parser.add_argument("--template", type=Path, action="append")
    parser.add_argument(
        "--media-pool", action="store_true", help="also remove the Media Pool entry"
    )
    args = parser.parse_args()
    for template in args.template or TEMPLATES:
        report = remove_clip(template, args.name, args.media_pool)
        print(f"{template}: {report}")


if __name__ == "__main__":
    main()

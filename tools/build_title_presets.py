"""Rebuild EBI titles and add them to the existing DRP without editing timelines.

Build dependency: zstandard. Runtime installers need only the Python standard library.
"""

import argparse
import json
import re
import tempfile
import uuid
import zipfile
from pathlib import Path

from title_archive import (
    extract_composition,
    generator_blocks,
    pack_composition,
    renamed_generator_fields,
)
from title_graph import composition_tools, setting_text

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "title_presets"
FOLDER = "MediaPool/Master/MpFolder.xml"


def archive_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Map real member names to their entries.

    Resolve stores UTF-8 member names without the zip UTF-8 flag, and zipfile
    then decodes them as cp437. Recover the real name so a bin such as
    "000_テロップ" is not rewritten as mojibake.
    """
    members = {}
    for info in archive.infolist():
        name = info.filename
        if not info.flag_bits & 0x800:
            try:
                name = name.encode("cp437").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        members[name] = info
    return members


def folder_id(xml: str) -> str:
    match = re.search(r'<Sm2MpFolder DbId="([a-f0-9-]+)"', xml)
    if not match:
        raise ValueError("Media Pool folder has no DbId")
    return match[1]


def load_presets() -> list[dict]:
    presets = json.loads((ASSETS / "presets.json").read_text(encoding="utf-8"))
    names = [item["name"] for item in presets]
    if len(names) != len(set(names)) or not names:
        raise ValueError("Preset names must be unique and nonempty")
    for item in presets:
        if any(c in item["name"] for c in "<>&/\\"):
            raise ValueError("Unsafe preset name")
    return presets


def replace_element(block: str, tag: str, value: str) -> str:
    return re.sub(
        rf"(<{tag}>).*?(</{tag}>)",
        lambda m: m[1] + value + m[2],
        block,
        count=1,
        flags=re.DOTALL,
    )


def make_generator(original: str, preset: dict, parent: str) -> str:
    block = original
    for old in re.findall(r'(?:DbId=")([a-f0-9-]+)', original):
        new = str(
            uuid.uuid5(uuid.NAMESPACE_URL, "ebi-title/" + preset["id"] + "/" + old)
        )
        block = block.replace(old, new)
    unique = str(uuid.uuid5(uuid.NAMESPACE_URL, "ebi-title/pool/" + preset["id"]))
    block = replace_element(block, "UniqueMediaPoolItemId", unique)
    blob = re.search(r"<FieldsBlob>(.*?)</FieldsBlob>", block, re.DOTALL)[1]
    block = replace_element(
        block, "FieldsBlob", renamed_generator_fields(blob, preset["name"])
    )
    block = replace_element(block, "Name", preset["name"])
    block = replace_element(block, "MpFolder", parent)
    block = replace_element(block, "CurPlayheadPosition", "0")
    return replace_element(
        block,
        "CompositionBA",
        pack_composition(composition_tools(preset), preset["name"]),
    )


def owned_ids(presets: list[dict]) -> set[str]:
    """Stable identities that survive display-name changes."""
    return {
        str(uuid.uuid5(uuid.NAMESPACE_URL, "ebi-title/pool/" + p["id"]))
        for p in presets
    }


def read_title_folder(source: Path) -> tuple[str, str]:
    """Return the member name and XML of the folder holding the bundled titles."""
    with zipfile.ZipFile(source) as archive:
        members = archive_members(archive)
        folders = {
            name: archive.read(info).decode("utf-8")
            for name, info in members.items()
            if name.endswith("MpFolder.xml")
        }
    target = title_home(folders, owned_ids(load_presets()))
    return target, folders[target]


def title_home(folders: dict[str, str], owned: set[str]) -> str:
    """Return the folder the bundled titles already live in, Master otherwise.

    Editors move the collection into a bin of their own in Resolve; rebuilding
    into Master would leave that bin holding a stale, duplicated copy.
    """
    homes = {
        name
        for name, xml in folders.items()
        for identity in re.findall(
            r"<UniqueMediaPoolItemId>(.*?)</UniqueMediaPoolItemId>", xml
        )
        if identity in owned
    }
    if len(homes) > 1:
        raise ValueError(f"Bundled titles are split across bins: {sorted(homes)}")
    return homes.pop() if homes else FOLDER


def build_project(source: Path, destination: Path) -> None:
    presets = load_presets()
    with zipfile.ZipFile(source) as archive:
        members = archive_members(archive)
        if FOLDER not in members:
            raise ValueError("Missing the Master Media Pool folder")
        folders = {
            name: archive.read(info).decode("utf-8")
            for name, info in members.items()
            if name.endswith("MpFolder.xml")
        }
        original = [
            b for b in generator_blocks(folders[FOLDER]) if "<Name>テロップ</Name>" in b
        ]
        if len(original) != 1:
            raise ValueError("Expected the existing native テロップ generator")
        # Do not leave an old copy behind when a preset is renamed.
        owned = owned_ids(presets)
        target = title_home(folders, owned)
        for name, folder in folders.items():
            for block in generator_blocks(folder):
                identity = re.search(
                    r"<UniqueMediaPoolItemId>(.*?)</UniqueMediaPoolItemId>", block
                )
                if identity and identity[1] in owned:
                    folder = folder.replace(block, "", 1)
            folders[name] = folder
        xml = folders[target]
        # Exactly one MediaVec at this level; refuse a different template schema.
        if xml.count("</MediaVec>") != 1:
            raise ValueError("Unexpected Media Pool folder structure")
        extra = "".join(make_generator(original[0], p, folder_id(xml)) for p in presets)
        xml = xml.replace(" </MediaVec>", extra + " </MediaVec>", 1)
        for preset in presets:
            if preset["text"] not in extract_composition(xml, preset["name"]):
                raise ValueError("Generated composition failed read-back")
        folders[target] = xml
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".drp", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, "w") as output:
                for name, info in members.items():
                    info.filename = name
                    output.writestr(
                        info,
                        folders[name].encode()
                        if name == target
                        else archive.read(info),
                    )
            with zipfile.ZipFile(temporary) as check:
                if check.testzip():
                    raise ValueError("Generated DRP failed CRC validation")
            archive.close()  # Windows cannot replace an open source archive.
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "有償版用スクリプト" / "テンプレート.drp",
    )
    args = parser.parse_args()
    settings = ASSETS / "Edit" / "Titles" / "EBI"
    settings.mkdir(parents=True, exist_ok=True)
    for preset in load_presets():
        (settings / (preset["name"] + ".setting")).write_text(
            setting_text(preset), encoding="utf-8"
        )
    build_project(args.template, args.template)
    print(f"Built {len(load_presets())} titles in {args.template}")


if __name__ == "__main__":
    main()

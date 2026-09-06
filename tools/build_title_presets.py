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


def make_generator(original: str, preset: dict) -> str:
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
    block = replace_element(block, "CurPlayheadPosition", "0")
    return replace_element(
        block, "CompositionBA", pack_composition(composition_tools(preset))
    )


def build_project(source: Path, destination: Path) -> None:
    presets = load_presets()
    with zipfile.ZipFile(source) as archive:
        xml = archive.read(FOLDER).decode("utf-8")
        original = [b for b in generator_blocks(xml) if "<Name>テロップ</Name>" in b]
        if len(original) != 1:
            raise ValueError("Expected the existing native テロップ generator")
        # Stable identities survive display-name changes; do not leave an old
        # copy behind when a preset is renamed in the catalog.
        owned = {
            str(uuid.uuid5(uuid.NAMESPACE_URL, "ebi-title/pool/" + p["id"]))
            for p in presets
        }
        for block in generator_blocks(xml):
            identity = re.search(
                r"<UniqueMediaPoolItemId>(.*?)</UniqueMediaPoolItemId>", block
            )
            if identity and identity[1] in owned:
                xml = xml.replace(block, "", 1)
        extra = "".join(make_generator(original[0], p) for p in presets)
        # Exactly one MediaVec at this level; refuse a different template schema.
        if xml.count("</MediaVec>") != 1:
            raise ValueError("Unexpected Media Pool folder structure")
        xml = xml.replace(" </MediaVec>", extra + " </MediaVec>", 1)
        for preset in presets:
            if preset["text"] not in extract_composition(xml, preset["name"]):
                raise ValueError("Generated composition failed read-back")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".drp", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, "w") as output:
                for info in archive.infolist():
                    output.writestr(
                        info,
                        xml.encode()
                        if info.filename == FOLDER
                        else archive.read(info.filename),
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

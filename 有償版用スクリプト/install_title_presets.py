"""Install bundled Fusion titles; never overwrite a locally edited preset."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

MANIFEST = ".ebi-installed.json"
SOURCE = (
    Path(__file__).resolve().parents[1] / "title_presets" / "Edit" / "Titles" / "EBI"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        file.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install_presets(source: Path, destination: Path) -> tuple[int, int]:
    files = sorted(source.glob("*.setting"))
    if not files:
        raise ValueError(f"No title presets found in {source}")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / MANIFEST
    previous = (
        json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    )
    if not isinstance(previous, dict):
        raise TypeError("Invalid title installation manifest")
    recorded = dict(previous)
    updated = skipped = 0
    for asset in files:
        target = destination / asset.name
        content = asset.read_bytes()
        expected = digest(content)
        if target.is_symlink():
            print(f"Preserved symbolic link: {asset.name}")
            skipped += 1
            continue
        if target.exists():
            current = digest(target.read_bytes())
            if current == expected:
                recorded[asset.name] = expected
                continue
            if current != previous.get(asset.name):
                print(f"Preserved customized title: {asset.name}")
                skipped += 1
                continue
        atomic_write(target, content)
        recorded[asset.name] = expected
        updated += 1
    atomic_write(
        manifest, (json.dumps(recorded, ensure_ascii=False, indent=2) + "\n").encode()
    )
    return updated, skipped


def default_destination() -> Path:
    if sys.platform == "win32":
        return (
            Path(os.environ["APPDATA"])
            / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Templates/Edit/Titles/EBI"
        )
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles/EBI"
        )
    return Path.home() / ".local/share/DaVinciResolve/Fusion/Templates/Edit/Titles/EBI"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination", type=Path, help="Override the user Fusion Titles/EBI folder"
    )
    args = parser.parse_args()
    destination = args.destination or default_destination()
    updated, skipped = install_presets(SOURCE, destination)
    print(
        f"EBI titles: {updated} installed/updated; {skipped} customized files preserved."
    )
    print(f"Titles folder: {destination}")
    if updated:
        print(
            "If Resolve is already running, restart it when convenient to refresh the Effects Library."
        )


if __name__ == "__main__":
    main()

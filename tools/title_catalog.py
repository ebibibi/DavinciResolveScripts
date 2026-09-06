"""Create a labeled layout reference from preset data (not a Resolve render)."""

import html
from pathlib import Path

from build_title_presets import ASSETS, load_presets


def rgb(values: list) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in values)


def make_catalog(destination: Path) -> None:
    tiles = []
    width, height = 640, 360
    for index, preset in enumerate(load_presets()):
        x = 30 + (index % 3) * 680
        y = 145 + (index // 3) * 450
        tile = [
            f'<g transform="translate({x},{y})">',
            f'<text x="0" y="0" fill="#e5edf9" font-size="24">{html.escape(preset["name"])}</text>',
            '<g transform="translate(0,20)">',
            '<rect width="640" height="360" rx="8" fill="#25334a"/>',
            '<path d="M0,300 L640,60 M0,180 L640,180 M320,0 L320,360" stroke="#36445a" fill="none"/>',
        ]
        if "box" in preset:
            cx, cy, w, h = preset["box"]
            tile.append(
                f'<rect x="{(cx - w / 2) * width}" y="{(1 - cy - h / 2) * height}" '
                f'width="{w * width}" height="{h * height}" rx="6" '
                f'fill="{rgb(preset["background"])}" opacity="{preset.get("opacity", 0.9)}"/>'
            )
        for field, center, size, color in [
            ("text", preset["center"], preset["size"], preset["color"]),
            (
                "subtitle",
                preset.get("subcenter", [0.5, 0.5]),
                preset.get("subsize", 0.03),
                preset.get("subcolor", [1, 1, 1]),
            ),
        ]:
            if field not in preset:
                continue
            stroke = (
                'stroke="#000" stroke-width="1" paint-order="stroke"'
                if preset.get("outline")
                else ""
            )
            # Approximate sizing: the actual font metrics and Fusion renderer differ.
            tile.append(
                f'<text x="{center[0] * width}" y="{(1 - center[1]) * height}" '
                f'font-weight="700" font-size="{size * width}" fill="{rgb(color)}" '
                f'text-anchor="middle" dominant-baseline="central" {stroke}>'
                f"{html.escape(preset[field])}</text>"
            )
        tile += [
            "</g>",
            f'<text x="0" y="410" fill="#aabbd2" font-size="20">{html.escape(preset["usage"])}</text>',
            "</g>",
        ]
        tiles.extend(tile)
    document = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="2070" height="1970" viewBox="0 0 2070 1970">'
        '<rect width="2070" height="1970" fill="#111b2c"/>'
        '<g font-family="Noto Sans CJK JP,Noto Sans JP,Yu Gothic,sans-serif">'
        '<text x="30" y="55" fill="white" font-size="38">EBI TITLES — 12種類のテロップ</text>'
        '<text x="30" y="98" fill="#aabbd2" font-size="23">配置見本 / Layout reference — Resolve実機レンダーではありません</text>'
        + "\n".join(tiles)
        + "</g></svg>"
    )
    destination.write_text(document, encoding="utf-8")


if __name__ == "__main__":
    make_catalog(ASSETS / "catalog.svg")

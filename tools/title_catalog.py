"""Create a labeled layout reference from preset data (not a Resolve render)."""

import html
from pathlib import Path

from build_title_presets import ASSETS, load_presets


def rgb(values: list) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in values)


def make_catalog(destination: Path) -> None:
    tiles = []
    cards = []
    presets = load_presets()
    width, height = 640, 360
    for index, preset in enumerate(presets):
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
                f'font-family="{html.escape(preset["font"])}" '
                f'font-weight="{400 if preset["style"] == "Regular" else 700}" '
                f'font-size="{size * width}" fill="{rgb(color)}" '
                f'text-anchor="middle" dominant-baseline="central" {stroke}>'
                f"{html.escape(preset[field])}</text>"
            )
        tile += [
            "</g>",
            f'<text x="0" y="410" fill="#aabbd2" font-size="20">{html.escape(preset["usage"])}</text>',
            "</g>",
        ]
        tiles.extend(tile)
        background = (
            "文字のみ" if "box" not in preset else
            "黒背景" if preset["background"] == [0, 0, 0] else "色付き背景"
        )
        preview = '\n'.join(tile[2:-2])
        cards.append(
            f'<article data-language="{preset["language"]}" '
            f'data-font="{html.escape(preset["font"])}" data-background="{background}">'
            f'<h2>{html.escape(preset["name"])}</h2>'
            f'<svg viewBox="0 0 640 400" role="img" aria-label="{html.escape(preset["label"])}">'
            f'{preview}</svg><p>{html.escape(preset["usage"])}</p>'
            f'<small>{preset["language"]} · {html.escape(preset["font"])} · {background}</small></article>'
        )
    page_height = 170 + ((len(presets) + 2) // 3) * 450
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="2070" height="{page_height}" viewBox="0 0 2070 {page_height}">'
        f'<rect width="2070" height="{page_height}" fill="#111b2c"/>'
        '<g font-family="Noto Sans CJK JP,Noto Sans JP,Yu Gothic,sans-serif">'
        f'<text x="30" y="55" fill="white" font-size="38">EBI TITLES — {len(presets)}種類のテロップ</text>'
        '<text x="30" y="98" fill="#aabbd2" font-size="23">配置見本 / Layout reference — Resolve実機レンダーではありません</text>'
        + "\n".join(tiles)
        + "</g></svg>"
    )
    destination.write_text(document, encoding="utf-8")
    fonts = sorted({p["font"] for p in presets})
    html_page = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EBI テロップカタログ</title><style>
body{margin:32px;background:#111b2c;color:#e5edf9;font-family:Meiryo,sans-serif}
h1{margin-bottom:8px} header p{color:#aabbd2;max-width:900px;line-height:1.8}
nav{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0;align-items:end}
label{display:grid;gap:8px}select,input{padding:10px;font:inherit;border-radius:6px;border:1px solid #536580;background:#25334a;color:white}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:20px}
article{background:#1b2940;border:1px solid #36445a;border-radius:10px;overflow:hidden;padding:16px}
h2{font-size:16px;overflow-wrap:anywhere}svg{width:100%}small{color:#aabbd2}article[hidden]{display:none}
a{color:#a0ccff}</style><header><h1>EBI テロップカタログ</h1>
<p>字幕・見出し・章タイトルを、言語・背景・書体で探せます。素材名をResolveのメディアプールで検索し、映像より上のトラックへ配置してください。インスペクタで本文・書体・色を変更できます。</p>
<p>配置見本です。Resolveの実機レンダーではありません。<a href="README.md">使い方</a></p></header>
<nav><label>言語<select id="language"><option value="">すべて</option><option>JP</option><option>EN</option></select></label>
<label>背景<select id="background"><option value="">すべて</option><option>文字のみ</option><option>黒背景</option><option>色付き背景</option></select></label>
<label>フォント<select id="font"><option value="">すべて</option>FONT_OPTIONS</select></label>
<label>名前・用途<input id="query" type="search" placeholder="例：字幕、章、青帯"></label><output id="count" aria-live="polite"></output></nav>
<main>CARDS</main><script>
const fields=['language','background','font'], cards=[...document.querySelectorAll('article')];
function filter(){let count=0;for(const card of cards){
const match=fields.every(id=>!document.getElementById(id).value||card.dataset[id]===document.getElementById(id).value)
&&card.textContent.toLowerCase().includes(document.getElementById('query').value.toLowerCase());
card.hidden=!match;if(match)count++;}document.getElementById('count').textContent=count+' / '+cards.length+' 種類';}
document.querySelectorAll('select,input').forEach(el=>el.addEventListener('input',filter));filter();
</script></html>'''
    html_page = html_page.replace("FONT_OPTIONS", "".join(f'<option>{html.escape(font)}</option>' for font in fonts))
    destination.with_suffix(".html").write_text(html_page.replace("CARDS", "\n".join(cards)), encoding="utf-8")


if __name__ == "__main__":
    make_catalog(ASSETS / "catalog.svg")

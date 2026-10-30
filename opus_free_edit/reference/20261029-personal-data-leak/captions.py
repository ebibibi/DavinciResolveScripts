"""timeline.json -> work/cues.json (burn-in pages) + out/captions.srt"""
import json
import os
import re

from janome.tokenizer import Tokenizer

os.chdir("/home/ebi/video-jobs/20261029-personal-data-leak")
FPS = 30
LINE = 17          # full-width chars per line
PAGE = 2 * LINE
UNIT_GAP = 0.6     # output seconds of silence that end a caption unit

FIX = [
    (r"やびさ|エビスタ|ヘビスタ", "胡田"),
    (r"ステイハングリー、?ステイフ[ーリ]*ッシュ、?", "Stay Hungry. Stay Foolish. "),
    (r"私の使い手で", "私の使ってる"),
    (r"年金の入った", "年季の入った"),
    (r"銘柄が分かってたら", "名前が分かってたら"),
    (r"個々のもの", "こういうもの"),
    (r"解禁ですと", "最近ですと"),
    (r"フィッシングサイド", "フィッシングサイト"),
    (r"悪いサイド", "悪いサイト"),
    (r"一網打ちに", "一網打尽に"),
    (r"いつのところを", "いろんなところを"),
    (r"多様子認証|対応素認証", "多要素認証"),
    (r"思い越し", "重い腰"),
    (r"便になった", "便利になった"),
    (r"コンビニター", "コンピューター"),
    (r"実系列", "時系列"),
    (r"規定に", "既定に"),
    (r"ケレブルス認証", "Kerberos認証"),
    (r"インフロ", "インフラ"),
    (r"情報漏え(?!い)", "情報漏えい"),
    (r"うんぬかんぬ", "うんぬんかんぬん"),
    (r"腹を打ち破って", "殻を打ち破って"),
    (r"銀行コーダー", "銀行口座"),
    (r"ドッカーみたいな", "どっかみたいな"),
    (r"出店", "出典"),
    (r"presentations\.\s*ebisa\.\s*net", "presentations.ebisuda.net"),
    (r"情報漏洩祭", "情報漏えい祭り"),
    (r"何が生まれた", "何が漏れた"),
    (r"使えないサード", "使えないサイト"),
    (r"ITでパスワード", "IDとパスワード"),
    (r"長い漢字", "長い感じ"),
    (r"文字った", "もじった"),
    (r"じゃあ、使いましょう、やめましょう", "じゃあ、使い回しやめましょう"),
    (r"パスワードを使いますっていう", "パスワードを使い回すっていう"),
    (r"その意の一番", "そのいの一番"),
    (r"登録しまくみたい", "登録しまくるみたい"),
    (r"それではWindows", "それで、Windows"),
    (r"水素の間", "ついこの間"),
    (r"返させられたり", "変えさせられたり"),
    (r"こんなにUSB", "こんなふうにUSB"),
    (r"言ってるのことは", "言ってることは"),
    (r"冒頭から来たところで、?", ""),
    (r"WindowsHello", "Windows Hello"),
]
tok = Tokenizer()


def units(pieces):
    """Group words of talk pieces into caption units (list of (char, time) + end)."""
    out = []
    for p in pieces:
        if p["kind"] != "talk":
            out.append(None)
            continue
        for w in p["words"]:
            s = p["o0"] / FPS + (w["s"] - p["f0"] / FPS)
            e = p["o0"] / FPS + (w["e"] - p["f0"] / FPS)
            s, e = max(s, p["o0"] / FPS), min(e, p["o1"] / FPS)
            if e < s:
                continue
            cur = out[-1] if out else None
            if cur is None or s - cur["end"] > UNIT_GAP or cur["block"] != p["block"] or \
                    cur["text"].endswith(("。", "？", "?")):
                cur = {"chars": [], "end": e, "block": p["block"], "text": ""}
                out.append(cur)
            txt = w["w"]
            n = max(len(txt), 1)
            for k, ch in enumerate(txt):
                cur["chars"].append([ch, s + (e - s) * k / n])
            cur["end"] = e
            cur["text"] += txt
    return [u for u in out if u]


def apply_fixes(chars):
    for pat, rep in FIX:
        while True:
            s = "".join(c for c, _ in chars)
            m = re.search(pat, s)
            if not m:
                break
            t = chars[m.start()][1] if m.start() < len(chars) else chars[-1][1]
            chars = chars[:m.start()] + [[c, t] for c in rep] + chars[m.end():]
            if rep and re.search(pat, rep):
                break
    return chars


def boundaries(text):
    """Character offsets where a line/page may break (between janome tokens, never before a particle)."""
    ok = set()
    pos = 0
    toks = list(tok.tokenize(text))
    for i, t in enumerate(toks):
        pos += len(t.surface)
        if i + 1 < len(toks):
            nxt = toks[i + 1]
            p0 = nxt.part_of_speech.split(",")
            if p0[0] in ("助詞", "助動詞") or p0[1] in ("接尾", "非自立") or p0[0] == "記号" and nxt.surface in "、。？！)」』" \
                    or nxt.surface in ("ー", "ッ"):
                continue
            prev = t.part_of_speech.split(",")
            if prev[0] == "名詞" and (p0[0] == "名詞" or nxt.base_form == "する" or nxt.surface[0] in "はがをにへでとものや"):
                continue
            if prev[0] == "接頭詞":
                continue
            # do not split inside an ASCII word
            if text[pos - 1:pos].isascii() and text[pos:pos + 1].isascii() and text[pos - 1:pos].isalnum() \
                    and text[pos:pos + 1].isalnum():
                continue
            ok.add(pos)
    return ok


def width(s):
    return sum(0.55 if c.isascii() else 1.0 for c in s)


def clean(s):
    return s.replace("。", "").strip("、 　")


def fits(text):
    return all(width(l) <= LINE + 1 for l in lines_of(text))


def split_pages(chars):
    text = "".join(c for c, _ in chars)
    if fits(text):
        return [chars]
    b = boundaries(text)
    pages, start = [], 0
    while not fits(text[start:]):
        best, bscore = None, None
        for pos in sorted(b):
            if pos <= start + 4:
                continue
            w = width(clean(text[start:pos]))
            if w > PAGE:
                break
            if not fits(text[start:pos]):
                continue
            rest = width(clean(text[pos:]))
            score = (0 if text[pos - 1] in "、。" else 6) + abs(w - min(PAGE, (w + rest) / 2)) * 0.3
            if bscore is None or score < bscore:
                best, bscore = pos, score
        if best is None:
            raw, pos = [], 0
            for t in tok.tokenize(text):
                pos += len(t.surface)
                raw.append(pos)
            cands = [q for q in raw if start + 2 < q <= start + LINE + 1 and q < len(text)]
            best = max(cands) if cands else min(len(text), start + LINE)
        pages.append(chars[start:best])
        start = best
        if start >= len(text):
            break
    pages.append(chars[start:])
    return [pg for pg in pages if pg]


def lines_of(text):
    text = clean(text)
    sh = "Stay Hungry. Stay Foolish."
    if sh in text and text.strip() != sh:
        i = text.index(sh) + len(sh)
        return [clean(text[:i]), clean(text[i:])]
    if width(text) <= LINE + 1:
        return [text]
    b = boundaries(text)
    best, bscore = None, None
    for pos in b:
        a, c = clean(text[:pos]), clean(text[pos:])
        if not a or not c:
            continue
        over = max(0, width(a) - LINE - 1) + max(0, width(c) - LINE - 1)
        score = over * 10 + abs(width(a) - width(c)) + (0 if text[pos - 1] == "、" else 1.5)
        if bscore is None or score < bscore:
            best, bscore = pos, score
    if best is None:
        best = len(text) // 2
    return [clean(text[:best]), clean(text[best:])]


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    d = json.load(open("work/timeline.json"))
    cues = []
    for u in units(d["pieces"]):
        chars = apply_fixes(u["chars"])
        pages = split_pages(chars)
        for k, pg in enumerate(pages):
            s = pg[0][1]
            e = pages[k + 1][0][1] if k + 1 < len(pages) else u["end"]
            text = "".join(c for c, _ in pg)
            if not clean(text):
                continue
            cues.append({"s": s, "e": e, "lines": lines_of(text), "block": u["block"]})
    # timing: hold a little, never overlap, at least 0.7 s
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["s"] if i + 1 < len(cues) else c["e"] + 1
        c["e"] = min(max(c["e"] + 0.25, c["s"] + 0.7), nxt)
    # cue must not run into a non-talk piece (ebifry / stinger)
    for c in cues:
        for p in d["pieces"]:
            if p["kind"] != "talk" and p["o0"] / FPS < c["e"] and p["o0"] / FPS >= c["s"]:
                c["e"] = p["o0"] / FPS
    ebis = [{"s": p["o0"] / FPS + 0.25, "e": p["o1"] / FPS, "lines": [p["text"]], "ebifry": True}
            for p in d["pieces"] if p["kind"] == "ebifry"]
    json.dump(cues, open("work/cues.json", "w"), ensure_ascii=False, indent=0)
    allc = sorted(cues + ebis, key=lambda c: c["s"])
    with open("out/captions.srt", "w") as f:
        for i, c in enumerate(allc, 1):
            body = "\n".join(c["lines"])
            if c.get("ebifry"):
                body = "えびフライ：" + body
            f.write(f"{i}\n{srt_time(c['s'])} --> {srt_time(c['e'])}\n{body}\n\n")
    print(len(cues), "cues;", "max line width", max(width(l) for c in cues for l in c["lines"]))


if __name__ == "__main__":
    main()

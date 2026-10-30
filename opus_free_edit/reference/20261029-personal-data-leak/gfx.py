"""Graphics built with Pillow: backgrounds, slide placements, tracker, lower thirds, captions, bubbles, recap."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

JOB = "/home/ebi/video-jobs/20261029-personal-data-leak"
FONT_DIR = "/home/ebi/.local/share/fonts"
W, H = 1920, 1080
CREAM = (251, 248, 238)
TEAL = (20, 117, 111)
TEAL_L = (230, 242, 240)
INK = (33, 37, 41)
GREY = (120, 124, 128)
CAP_BOTTOM = 1040          # bottom of the last caption line
LT_BOTTOM = 800            # lower thirds end above the two-line caption band
SLIDE_BBOX = {1: (82, 89, 1197, 903), 2: (82, 85, 1200, 634), 3: (82, 85, 1197, 862), 4: (82, 85, 1197, 997),
              5: (76, 85, 1197, 997), 6: (82, 85, 1197, 821), 7: (82, 85, 1197, 902), 8: (76, 85, 839, 874),
              9: (76, 85, 1017, 857), 10: (82, 86, 1197, 637)}
STEPS = ["まず確認", "パスワード", "カード", "住所・電話・メール", "免許証の画像",
         "使い回しをやめる", "パスワードマネージャー", "パスキー", "今日やる3つ"]
RECAP = [("漏れたら", ["何が漏れたか、公式サイトで自分から確認", "パスワードは全部違うものに変える",
                    "カード会社に連絡してカードを止める", "届いたメール・SMS・荷物はまず疑う",
                    "免許証の画像なら信用情報機関などに連絡"]),
         ("普段から", ["パスワードを使い回さない", "パスワードマネージャーに覚えさせる",
                    "大事なアカウントからパスキーへ"])]


@lru_cache(None)
def font(size, weight="Bold"):
    return ImageFont.truetype(f"{FONT_DIR}/NotoSansCJKjp-{weight}.otf", size)


def rgba(img):
    return np.array(img.convert("RGBA"))


def rounded(draw, box, r, fill=None, outline=None, width=0):
    draw.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def background():
    """Cream studio background with a soft light and two quiet teal shapes."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.array(CREAM, np.float32)
    light = np.exp(-(((x - 760) / 900) ** 2 + ((y - 380) / 700) ** 2))
    img = base * (0.94 + 0.06 * light[..., None])
    teal = np.array(TEAL_L, np.float32)
    for cx, cy, r in ((1700, 980, 420), (140, 120, 260)):
        m = np.clip((r - np.hypot(x - cx, y - cy)) / 3, 0, 1)[..., None] * 0.55
        img = img * (1 - m) + teal * m
    return img.clip(0, 255).astype(np.uint8)


def slide_img(n):
    return Image.open(f"{JOB}/slides/stills/slide_{n:02d}.png").convert("RGB")


def slide_split(n):
    """Slide for the left 1280 px; scaled so its content stays above the caption band."""
    x0, y0, x1, y1 = SLIDE_BBOX[n]
    s = min(1.0, 790 / y1)
    im = slide_img(n).resize((round(1280 * s), round(1080 * s)), Image.LANCZOS)
    canvas = Image.new("RGB", (1280, H), CREAM)
    canvas.paste(im, ((1280 - im.width) // 2, 0))
    return np.array(canvas)


def slide_full(n):
    """Slide content enlarged into the area left of the round PiP and above the captions."""
    x0, y0, x1, y1 = SLIDE_BBOX[n]
    x0, y0, x1, y1 = x0 - 30, y0 - 30, x1 + 30, y1 + 30
    bw, bh = 1500, 770
    s = min(bw / (x1 - x0), bh / (y1 - y0), 1.45)
    im = slide_img(n).crop((x0, y0, x1, y1))
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), CREAM)
    canvas.paste(im, (40 + (bw - im.width) // 2, 30 + (bh - im.height) // 2))
    return np.array(canvas)


def circle_mask(d):
    big = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
    return np.array(big.resize((d, d), Image.LANCZOS)).astype(np.float32) / 255


def ring(d, width=8):
    im = Image.new("RGBA", (d + 2 * width, d + 2 * width), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((2, 2, d + 2 * width - 3, d + 2 * width - 3), outline=TEAL + (255,), width=width)
    return rgba(im)


def tracker(step, glow=0.0):
    """Progress tracker panel (RGBA) for steps 1..9; glow 0..1 pulses the current row."""
    w, row = 430, 52
    h = 70 + 2 * 46 + len(STEPS) * row + 20
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rounded(dr, (0, 0, w - 1, h - 1), 22, fill=(255, 255, 255, 228), outline=(214, 222, 220, 255), width=2)
    dr.text((24, 16), "やることマップ", font=font(30), fill=TEAL)
    dr.text((w - 24, 18), f"{step} / {len(STEPS)}", font=font(28), fill=GREY, anchor="ra")
    y = 70
    for gi, (label, idx) in enumerate((("漏れたら", range(0, 5)), ("普段から", range(5, 9)))):
        dr.text((24, y + 6), label, font=font(26, "Medium"), fill=GREY)
        y += 46
        for i in idx:
            cur, done = i + 1 == step, i + 1 < step
            if cur:
                a = int(255 * (0.85 + 0.15 * glow))
                rounded(dr, (14, y, w - 14, y + row - 6), 14, fill=TEAL + (a,))
                if glow > 0:
                    rounded(dr, (10, y - 4, w - 10, y + row - 2), 16, outline=(120, 200, 190, int(200 * glow)), width=4)
            mark_x = 40
            if done:
                dr.line([(mark_x - 10, y + 24), (mark_x - 2, y + 33), (mark_x + 12, y + 14)], fill=TEAL, width=5)
            else:
                dr.ellipse((mark_x - 8, y + 16, mark_x + 8, y + 32), outline=(255, 255, 255) if cur else (170, 174, 178),
                           width=3)
            col = (255, 255, 255) if cur else (INK if not done else GREY)
            dr.text((66, y + (row - 6) // 2), STEPS[i], font=font(32 if cur else 30, "Bold" if cur else "Medium"),
                    fill=col, anchor="lm")
            y += row
    return rgba(im)


def check_icon(d):
    im = Image.new("RGBA", (d * 4, d * 4), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=(46, 160, 90, 255))
    s = d * 4
    dr.line([(s * 0.27, s * 0.52), (s * 0.43, s * 0.68), (s * 0.74, s * 0.34)], fill=(255, 255, 255, 255),
            width=int(s * 0.11), joint="curve")
    return im.resize((d, d), Image.LANCZOS)


def lower_third(kind, text):
    """✅ action line (white card) or keyword telop (teal card). Returns RGBA array, its bottom sits at LT_BOTTOM."""
    lines = text.split("\n")
    fs = 56 if kind == "check" else 54
    f = font(fs)
    tw = max(f.getbbox(l)[2] for l in lines)
    lh = int(fs * 1.32)
    pad_x, pad_y = 34, 22
    icon = 70 if kind == "check" else 0
    w = tw + 2 * pad_x + (icon + 20 if icon else 0)
    h = lh * len(lines) + 2 * pad_y
    im = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((6, 8, w + 6, h + 8), 20, fill=(0, 0, 0, 70))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(5)))
    dr = ImageDraw.Draw(im)
    if kind == "check":
        rounded(dr, (0, 0, w, h), 20, fill=(255, 255, 255, 250), outline=(46, 160, 90, 255), width=4)
        im.alpha_composite(check_icon(icon), (pad_x - 6, (h - icon) // 2))
        tx, col = pad_x + icon + 14, INK
    else:
        rounded(dr, (0, 0, w, h), 20, fill=TEAL + (245,))
        tx, col = pad_x, (255, 255, 255)
    for i, l in enumerate(lines):
        dr.text((tx, pad_y + i * lh + lh // 2), l, font=f, fill=col, anchor="lm")
    return rgba(im)


def caption(lines):
    """Burned-in caption: bold ~88 px white with dark outline, centred, bottom at CAP_BOTTOM."""
    f = font(88)
    lh = 106
    h = lh * len(lines) + 30
    im = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        dr.text((W // 2, 10 + i * lh + lh // 2), l, font=f, fill=(255, 255, 255, 255), anchor="mm",
                stroke_width=9, stroke_fill=(24, 28, 36, 255))
    return rgba(im)  # render.py crops it to the text box


def bubble(text):
    """Speech bubble for えびフライ (max two lines), tail at bottom right pointing at him."""
    f = font(60)
    words = text
    if "\n" in words:
        lines = words.split("\n")
    elif f.getbbox(words)[2] > 700:
        # split at the most balanced punctuation/space
        best = min(range(4, len(words) - 3), key=lambda i: abs(i - len(words) / 2) - (3 if words[i - 1] in "、！？…」" else 0))
        lines = [words[:best], words[best:]]
    else:
        lines = [words]
    tw = max(f.getbbox(l)[2] for l in lines)
    lh = 78
    w, h = tw + 70, lh * len(lines) + 46
    im = Image.new("RGBA", (w + 20, h + 70), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    tail = [(w - 170, h - 6), (w - 90, h - 6), (w - 60, h + 60)]
    dr.polygon(tail, fill=(255, 255, 255, 255), outline=INK)
    rounded(dr, (0, 0, w, h), 34, fill=(255, 255, 255, 255), outline=INK + (255,), width=5)
    dr.polygon([(tail[0][0] + 6, h - 8), (tail[1][0] - 4, h - 8), (tail[2][0] - 3, tail[2][1] - 10)],
               fill=(255, 255, 255, 255))
    dr.line([tail[0], tail[2]], fill=INK, width=5)
    dr.line([tail[1], tail[2]], fill=INK, width=5)
    for i, l in enumerate(lines):
        dr.text((35, 23 + i * lh + lh // 2), l, font=f, fill=INK, anchor="lm")
    return rgba(im)


def recap_card(visible_items):
    """Recap checklist; visible_items = how many items are shown (animated in)."""
    im = Image.fromarray(background()).convert("RGBA")
    dr = ImageDraw.Draw(im)
    dr.text((70, 46), "今日のまとめ：やることリスト", font=font(64), fill=TEAL)
    k = 0
    cols = [(60, 170, 900), (990, 170, 860)]
    for (label, items), (x, y, cw) in zip(RECAP, cols):
        rounded(dr, (x, y, x + cw, y + 90 + len(items) * 104), 26, fill=(255, 255, 255, 235),
                outline=(214, 222, 220, 255), width=2)
        dr.text((x + 30, y + 22), label, font=font(40), fill=GREY)
        yy = y + 90
        for it in items:
            if k < visible_items:
                im.alpha_composite(check_icon(56), (x + 24, yy + 10))
                dr.text((x + 96, yy + 38), it, font=font(40), fill=INK, anchor="lm")
            yy += 104
            k += 1
    return np.array(im.convert("RGB"))


RECAP_N = sum(len(i) for _, i in RECAP)

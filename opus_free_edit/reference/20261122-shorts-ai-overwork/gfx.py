"""Vertical re-draws of the deck's numbers and diagrams (values from long/slides/capture.json and the slides).
Each gfx draws on a 1080x500 RGBA 'stage' that sits at y=STAGE_Y on the 1080x1920 canvas.
t = seconds in the short; at(raw) maps a raw-recording time to short time (for syncing to his words)."""
import math
from PIL import Image, ImageDraw
from text import draw_line, width, font, text_block

STAGE_Y, SW, SH = 560, 1080, 500
CX = 515                 # visual centre (right edge keeps clear of the button column)
L, R = 75, 955           # text must stay inside x in [64, 960]
FG = (244, 238, 232, 255)
MUTED = (168, 153, 140, 255)
ACC = (255, 106, 61, 255)
BLUE = (91, 143, 217, 255)
PANEL = (34, 28, 25, 235)
LINE = (70, 58, 50, 255)


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def pop(x):
    """0..1 with a little overshoot"""
    x = max(0.0, min(1.0, x))
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if x < 1 else 1.0


def _stage():
    im = Image.new('RGBA', (SW, SH), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _panel(d, box, r=26, fill=PANEL, outline=LINE, w=2):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)


def _ctext(d, cx, y, s, size, fill=FG, bold=True):
    draw_line(d, cx - width(s, size, bold) / 2, y, s, size, fill, bold=bold)


def _alpha(im, a):
    if a >= 1:
        return im
    r, g, b, al = im.split()
    al = al.point(lambda v: int(v * a))
    im.putalpha(al)
    return im


# ---------------------------------------------------------------- s1
WEEKS = [('10/5', 552), ('10/12', 460), ('10/19', 281), ('10/26', 277), ('11/2', 370), ('11/9', 690), ('11/16', 377)]


def weekly(t, t0, at, args):
    im, d = _stage()
    _panel(d, (L, 10, R, SH - 10))
    _ctext(d, CX, 70, 'AIへの指示（件／週）', 36, MUTED)
    n = len(WEEKS)
    bw, gap = 88, 32
    x0 = CX - (n * bw + (n - 1) * gap) / 2
    base, top = 420, 150
    for i, (lab, v) in enumerate(WEEKS):
        k = ease((t - t0 - 0.05 * i) / 0.45)
        hi = lab == '11/9'
        if hi:
            k = ease((t - t0 - 0.55) / 0.45)
        h = (base - top) * v / 690 * k
        x = x0 + i * (bw + gap)
        d.rounded_rectangle((x, base - h, x + bw, base), 8, fill=ACC if hi else (120, 110, 101, 255))
        _ctext(d, x + bw / 2, base + 42, lab, 28, ACC if hi else MUTED)
        if k > 0.6:
            if hi:
                _ctext(d, x + bw / 2, base - h - 16, '690', 64, ACC)
            else:
                _ctext(d, x + bw / 2, base - h - 12, str(v), 30, MUTED)
    return im


HOURS = [(6, 2), (7, 43), (8, 46), (9, 74), (10, 105), (11, 123), (12, 84), (13, 126), (14, 111), (15, 121), (16, 141),
         (17, 108), (18, 116), (19, 84), (20, 44), (21, 171), (22, 155), (23, 100), (0, 38)]


def hours(t, t0, at, args):
    im, d = _stage()
    _panel(d, (L, 10, R, SH - 10))
    _ctext(d, CX, 70, 'AIへのメッセージ（時台別・4週間合計）', 34, MUTED)
    n = len(HOURS)
    bw, gap = 34, 9.5
    x0 = CX - (n * bw + (n - 1) * gap) / 2
    base, top = 410, 215
    for i, (hr, v) in enumerate(HOURS):
        k = ease((t - t0 - 0.025 * i) / 0.4)
        hi = hr == 21
        h = (base - top) * v / 171 * k
        x = x0 + i * (bw + gap)
        d.rounded_rectangle((x, base - h, x + bw, base), 5, fill=ACC if hi else (120, 110, 101, 255))
        if hr in (6, 9, 12, 15, 18, 21, 0):
            _ctext(d, x + bw / 2, base + 40, f'{hr}', 28, ACC if hi else MUTED)
        if hi and k > 0.7:
            _ctext(d, x + bw / 2 - 40, base - h - 64, '夜9時台', 40, ACC)
            _ctext(d, x + bw / 2 - 40, base - h - 16, '171件', 40, ACC)
    _ctext(d, CX, base + 76, '（時）', 24, MUTED)
    return im


def moon(d, cx, cy, r, fill):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    d.ellipse((cx - r + r * 0.55, cy - r - r * 0.25, cx + r + r * 0.55, cy + r - r * 0.25), fill=(0, 0, 0, 0))


def night185(t, t0, at, args):
    im, d = _stage()
    _panel(d, (L, 10, R, SH - 10))
    a = ease((t - t0) / 0.3)
    moon(d, 210, 120, 50, (255, 214, 130, int(255 * a)))
    draw_line(d, 300, 145, '夜9時 〜 朝5時', 62, FG)
    k = (t - at(404.90)) / 0.55
    if k > 0:
        draw_line(d, 160, 290, '1週間で', 46, MUTED)
        n = int(round(185 * ease(k)))
        s = pop(k * 1.3)
        im2 = text_block([f'{n}'], int(190 * s), fill=ACC)
        im.alpha_composite(im2, (int(560 - im2.width / 2 + 30), int(330 - im2.height / 2)))
        if k > 0.8:
            draw_line(d, 760, 420, '件', 64, ACC)
    return im


def bp(t, t0, at, args):
    im, d = _stage()
    _panel(d, (L, 10, R, SH - 10))
    _ctext(d, CX, 80, '病院で測った血圧', 42, MUTED)
    k1 = (t - max(t0 + 0.15, at(53.88) - 0.6)) / 0.35
    k2 = (t - at(55.30)) / 0.35
    if k1 > 0:
        s = pop(k1)
        b = text_block(['160'], int(230 * s), fill=ACC)
        im.alpha_composite(b, (int(330 - b.width / 2), int(270 - b.height / 2)))
        _ctext(d, 330, 455, '上', 36, MUTED)
    if k2 > 0:
        s = pop(k2)
        b = text_block(['/109'], int(170 * s), fill=FG)
        im.alpha_composite(b, (int(700 - b.width / 2), int(300 - b.height / 2)))
        _ctext(d, 730, 455, '下', 36, MUTED)
    return im


# ---------------------------------------------------------------- s2
def grid(t, t0, at, args):
    im, d = _stage()
    _ctext(d, CX, 50, '同時に動かしているAI', 36, MUTED)
    cols, rows, tw, th, g = 5, 4, 150, 86, 18
    x0 = CX - (cols * tw + (cols - 1) * g) / 2
    y0 = 90
    t10, t20 = at(372.28), at(373.04)
    for i in range(20):
        ts = t10 + 0.045 * i if i < 10 else t20 + 0.045 * (i - 10)
        if i < 4:
            ts = t0 + 0.06 * i
        k = (t - ts) / 0.22
        if k <= 0:
            continue
        s = pop(k)
        r, c = divmod(i, cols)
        x, y = x0 + c * (tw + g) + tw / 2, y0 + r * (th + g) + th / 2
        w2, h2 = tw / 2 * s, th / 2 * s
        busy = (math.sin((t - ts) * 5 + i) + 1) / 2
        d.rounded_rectangle((x - w2, y - h2, x + w2, y + h2), 14, fill=(48, 40, 35, 255),
                            outline=ACC if i >= 4 else (150, 136, 124, 255), width=3)
        if s > 0.8:
            _ctext(d, x, y + 6, 'AI', 34, FG)
            bwid = (tw - 36) * (0.25 + 0.75 * busy)
            d.rounded_rectangle((x - tw / 2 + 18, y + 22, x - tw / 2 + 18 + bwid, y + 30), 4, fill=ACC)
    return im


def backlog(t, t0, at, args):
    im, d = _stage()
    for j, (lab, v, tk, col) in enumerate([('未完了の仕事', 398, at(1065.88), FG), ('返事待ちの判断', 47, at(1071.24), ACC)]):
        x0 = L + j * 450
        _panel(d, (x0, 30, x0 + 430, SH - 30))
        k = (t - tk) / 0.5
        _ctext(d, x0 + 215, 110, lab, 40, MUTED)
        if k > 0:
            n = int(round(v * ease(k)))
            b = text_block([str(n)], 170, fill=col)
            im.alpha_composite(b, (int(x0 + 200 - b.width / 2), int(280 - b.height / 2)))
            draw_line(d, x0 + 200 + b.width / 2 - 20, 352, '件', 50, col)
    return im


def bottleneck(t, t0, at, args):
    im, d = _stage()
    _ctext(d, CX, 50, 'AIは並列、確認は1列', 48, FG)
    # AI chips on the left
    ta, tm = at(1085.82), at(1089.60)
    for i in range(6):
        k = (t - ta - 0.07 * i) / 0.25
        if k <= 0:
            continue
        y = 105 + i * 62
        d.rounded_rectangle((L + 10, y, L + 150, y + 48), 12, fill=(48, 40, 35, 255), outline=(150, 136, 124, 255), width=2)
        _ctext(d, L + 80, y + 36, 'AI', 30, FG)
        # arrows converge to the human box
        d.line((L + 155, y + 24, 470, 285), fill=(110, 96, 86, 255), width=3)
    k = (t - tm) / 0.3
    if k > 0:
        s = pop(k)
        bx, by, bw2, bh2 = 560, 285, 95 * s, 85 * s
        d.rounded_rectangle((bx - bw2, by - bh2, bx + bw2, by + bh2), 18, fill=(60, 30, 22, 255), outline=ACC, width=4)
        if s > 0.9:
            _ctext(d, bx, by - 8, '確認は', 34, FG)
            _ctext(d, bx, by + 42, '私1人', 44, ACC)
        # queue piling up to the right
        n = int(min(9, max(0, (t - tm - 0.2) * 5)))
        for q in range(n):
            qy = 420 - q * 34
            d.rounded_rectangle((700, qy - 26, 900, qy), 8, fill=(84, 70, 62, 255), outline=(130, 112, 100, 255), width=2)
        if n >= 5:
            draw_line(d, 700, 470, '待ち行列が伸びる', 30, MUTED)
    return im


def brake(t, t0, at, args):
    im, d = _stage()
    _panel(d, (L + 40, 60, R - 40, SH - 60))
    _ctext(d, CX, 140, 'AIからの提案', 40, MUTED)
    _ctext(d, CX, 250, '夜9時以降は', 66, FG)
    _ctext(d, CX, 340, 'AIを使わない', 66, FG)
    return im


RULES = ['完了の条件を決め、/満たせばAIが閉じる', '返事がなければ推奨案で進む/（取り消せるものだけ）', '定期ジョブは異常時だけ知らせ、/正常なら1日1回まとめて']


def rules(t, t0, at, args):
    im, d = _stage()
    _ctext(d, CX, 44, '止めずに、流れを直す', 48, FG)
    n = args['n']
    for i in range(n):
        y = 80 + i * 136
        cur = i == n - 1
        k = ease((t - t0) / 0.35) if cur else 1
        xo = (1 - k) * 60
        _panel(d, (L + xo, y, R + xo, y + 120), 20, fill=(60, 30, 22, 245) if cur else PANEL, outline=ACC if cur else LINE, w=3 if cur else 2)
        d.ellipse((L + 22 + xo, y + 32, L + 78 + xo, y + 88), fill=ACC if cur else (110, 96, 86, 255))
        _ctext(d, L + 50 + xo, y + 74, str(i + 1), 38, (255, 255, 255, 255))
        from text import wrap
        lines = wrap(RULES[i], 42, R - L - 125)
        for j, ln in enumerate(lines):
            yy = y + (76 if len(lines) == 1 else 52 + j * 48)
            draw_line(d, L + 100 + xo, yy, ln, 42 if len(lines) == 1 else 39, FG if cur else MUTED)
    return im


# ---------------------------------------------------------------- s3
def _gauge(d, cx, cy, r, col):
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=col, width=10)
    d.line((cx, cy, cx + r * 0.6 * math.cos(math.radians(300)), cy + r * 0.6 * math.sin(math.radians(300))), fill=col, width=8)
    d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=col)


def _wifi(d, cx, cy, col):
    for k, r in enumerate((24, 50, 76)):
        d.arc((cx - r, cy - r, cx + r, cy + r), 225, 315, fill=col, width=10)
    d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=col)


def _chart(d, cx, cy, col):
    d.rounded_rectangle((cx - 52, cy - 70, cx + 52, cy + 70), 14, outline=col, width=6)
    pts = [(cx - 34, cy + 30), (cx - 14, cy + 8), (cx + 4, cy + 18), (cx + 30, cy - 30)]
    d.line(pts, fill=col, width=7)


def sync(t, t0, at, args):
    im, d = _stage()
    _ctext(d, CX, 60, '測ったら、勝手に記録される', 44, FG)
    steps = [(at(1420.56), '血圧計で測る', _gauge), (at(1422.02), 'Wi-Fiで同期', _wifi), (at(1424.66), '自動で記録', _chart)]
    xs = [L + 130, CX, R - 130]
    for i, (tk, lab, icon) in enumerate(steps):
        k = (t - tk) / 0.3
        if k <= 0:
            continue
        s = pop(k)
        x = xs[i]
        r = 118 * s
        d.ellipse((x - r, 250 - r, x + r, 250 + r), fill=(48, 40, 35, 255), outline=ACC if i == 2 else LINE, width=4)
        if s > 0.85:
            if icon is _gauge:
                _gauge(d, x, 270, 62, FG)
            elif icon is _wifi:
                _wifi(d, x, 300, FG)
            else:
                _chart(d, x, 250, ACC)
            _ctext(d, x, 430, lab, 36, FG if i < 2 else ACC)
        if i > 0:
            d.polygon([(xs[i - 1] + 132, 240), (xs[i - 1] + 132, 260), (xs[i] - 132, 260), (xs[i] - 132, 240)], fill=(110, 96, 86, 255))
    return im


CHECK = [('AIに週何件、指示しているか', '多い週で690件'), ('何時台がいちばん多いか', '夜9時台'), ('生活リズム・睡眠', '眠れなくなった')]


def check(t, t0, at, args):
    im, d = _stage()
    _ctext(d, CX, 44, '見ておきたい「自分の数字」', 46, FG)
    shown = args.get('from', 0)
    times = {r: at(rt) for rt, r in args['rows']}
    y0 = 84
    for i in range(3):
        r = i + 1
        on = r <= shown or (r in times and t >= times[r])
        if not on:
            continue
        k = ease((t - times[r]) / 0.3) if r in times else 1
        y = y0 + i * 136
        xo = (1 - k) * 50
        live = [rr for rr, tt in times.items() if t >= tt]
        cur = bool(live) and min(max(live), 3) == r
        _panel(d, (L + xo, y, R + xo, y + 124), 20, fill=(60, 30, 22, 245) if cur else PANEL, outline=ACC if cur else LINE)
        draw_line(d, L + 26 + xo, y + 54, CHECK[i][0], 40, FG)
        draw_line(d, L + 26 + xo, y + 104, '私の場合：', 32, MUTED)
        draw_line(d, L + 26 + xo + width('私の場合：', 32), y + 105, CHECK[i][1], 38, ACC)
    return im


GFX = dict(weekly=weekly, hours=hours, night185=night185, bp=bp, grid=grid, backlog=backlog, bottleneck=bottleneck,
           brake=brake, rules=rules, sync=sync, check=check)

"""Text drawing with Windows 11 fonts: Yu Gothic UI Bold for Japanese, Segoe UI Bold for Latin/digits."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

YU = '/home/ebi/.local/share/fonts/yugothic/YuGothB.ttc'   # index 1 = Yu Gothic UI Bold
SEG = '/home/ebi/.local/share/fonts/segoe/segoeuib.ttf'      # Segoe UI Bold
YU_REG = '/home/ebi/.local/share/fonts/yugothic/YuGothM.ttc'  # index 1 = Yu Gothic UI Regular
SEG_REG = '/home/ebi/.local/share/fonts/segoe/segoeui.ttf'


@lru_cache(None)
def font(size, latin=False, bold=True):
    if latin:
        return ImageFont.truetype(SEG if bold else SEG_REG, size)
    return ImageFont.truetype(YU if bold else YU_REG, size, index=1)


def _is_latin(ch):
    return ch.isascii() and ch not in '「」'


def runs(s):
    out = []
    for ch in s:
        lat = _is_latin(ch)
        if out and out[-1][1] == lat:
            out[-1][0] += ch
        else:
            out.append([ch, lat])
    return out


def width(s, size, bold=True):
    return sum(font(size, lat, bold).getlength(r) for r, lat in runs(s))


def draw_line(d, x, y, s, size, fill, stroke=0, stroke_fill=(0, 0, 0), bold=True, accents=(), accent_fill=None):
    """draw at baseline y starting at x. accents: substrings drawn in accent_fill"""
    colors = [fill] * len(s)
    for a in accents:
        i = s.find(a)
        while a and i >= 0:
            for k in range(i, i + len(a)):
                colors[k] = accent_fill
            i = s.find(a, i + len(a))
    k = 0
    for r, lat in runs(s):
        f = font(size, lat, bold)
        # split run further by colour
        j = 0
        while j < len(r):
            c = colors[k + j]
            m = j
            while m < len(r) and colors[k + m] == c:
                m += 1
            seg = r[j:m]
            d.text((x, y), seg, font=f, fill=c, anchor='ls', stroke_width=stroke, stroke_fill=stroke_fill)
            x += f.getlength(seg)
            j = m
        k += len(r)
    return x


BREAK_AFTER = set('はがをにでてともの、。？！」')


def wrap(s, size, maxw):
    """split into <=2 lines at a phrase boundary nearest the middle"""
    if '/' in s:
        return [x.strip() for x in s.split('/')]
    if width(s, size) <= maxw:
        return [s]
    best, bestd = None, 1e9
    for i in range(2, len(s) - 1):
        if s[i - 1] in BREAK_AFTER or s[i] == ' ' or (s[i - 1] == ' '):
            a, b = s[:i].rstrip(), s[i:].lstrip()
            if s[i] in 'ゃゅょっぁぃぅぇぉー、。かよねなみ':
                continue
            wa, wb = width(a, size), width(b, size)
            if max(wa, wb) > maxw:
                continue
            dd = abs(wa - wb)
            if dd < bestd:
                best, bestd = (a, b), dd
    if best is None:
        i = len(s) // 2
        best = (s[:i], s[i:])
    return list(best)


def text_block(lines, size, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0), line_h=None, align='center',
               accents=(), accent_fill=None, shadow=0, bold=True):
    """render lines into a tight RGBA image"""
    line_h = line_h or int(size * 1.28)
    pad = stroke + shadow + 8
    w = int(max(width(l, size, bold) for l in lines)) + pad * 2
    h = line_h * len(lines) + pad * 2 + int(size * 0.15)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        lw = width(l, size, bold)
        x = pad + (w - 2 * pad - lw) / 2 if align == 'center' else pad
        y = pad + line_h * i + int(size * 1.0)
        draw_line(d, x, y, l, size, fill, stroke, stroke_fill, bold, accents, accent_fill)
    if shadow:
        a = im.split()[3].filter(ImageFilter.GaussianBlur(shadow))
        sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.75)))
        sh = Image.composite(Image.new('RGBA', im.size, (0, 0, 0, 255)), sh, a.point(lambda v: int(v * 0.75)))
        out = Image.new('RGBA', im.size, (0, 0, 0, 0))
        out.alpha_composite(sh, (0, 4))
        out.alpha_composite(im)
        im = out
    return im

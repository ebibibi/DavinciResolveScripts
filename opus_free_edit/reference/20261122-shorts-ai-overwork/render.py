"""Render one short: python3 render.py s1 [--preview] [--frames 0,30,...]
timeline (raw pieces + えびフライ) -> audio mix -> per-frame composite -> H.264/AAC mp4."""
import json, os, subprocess, sys, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter

ROOT = '/home/ebi/video-jobs/20261121-ai-overwork-shorts/'
os.chdir(ROOT)
sys.path.insert(0, ROOT + 'work/scripts')
import spec, snap, gfx
from text import text_block, wrap, width

FPS, W, H, SR = 30, 1080, 1920, 48000
SPF = SR // FPS
BG = (23, 20, 18)
ACC = (255, 106, 61)
CAP_Y = 1172            # caption block centre
CAP_MAXW = 860
CX = 515
EBI_DIRS = ['work/ebifry', 'long/work/ebifry']
EBI_TAIL_TRIM = 0.15


# ------------------------------------------------------------------ timeline
def kept(it):
    a, b = it['raw']
    segs, cur = [], a
    for c0, c1 in sorted(it.get('cut', [])):
        segs.append([cur, c0]); cur = c1
    segs.append([cur, b])
    return [s for s in segs if s[1] - s[0] > 0.05]


def ebi_info(eid):
    for dd in EBI_DIRS:
        cj = os.path.join(dd, 'clips.json')
        if os.path.exists(cj):
            c = json.load(open(cj))
            if eid in c:
                return os.path.join(dd, eid + '.mov'), c[eid]
    raise KeyError(eid)


def build_timeline(sh):
    pieces, f = [], 0
    for ii, it in enumerate(sh['items']):
        if it['k'] == 'say':
            for s, e in kept(it):
                for a, b in snap.islands(s, e, thr=-50, min_gap=0.2, pad=0.07):
                    n = max(1, round((b - a) * FPS))
                    pieces.append(dict(item=ii, kind='say', raw=a, n=n, f0=f)); f += n
        else:
            mov, info = ebi_info(it['id'])
            y = read_ebi_audio(mov)
            hop = SR // 100
            e = 20 * np.log10(np.sqrt((y[:len(y) // hop * hop].reshape(-1, hop) ** 2).mean(1)) + 1e-9)
            on = np.where(e > e.max() - 30)[0]
            v0, v1 = on[0] / 100, (on[-1] + 1) / 100
            skip = max(0, int((v0 - 0.08) * FPS)) if f == 0 else int(0.1 * FPS)
            n = round((v1 + 0.22) * FPS) - skip
            pieces.append(dict(item=ii, kind='ebi', mov=mov, text=info['text'], n=n, f0=f, skip=skip)); f += n
    return pieces, f


def make_at(pieces, ii):
    """raw time -> short time for item ii"""
    ps = [p for p in pieces if p['item'] == ii and p['kind'] == 'say']

    def at(r):
        for p in ps:
            if r < p['raw'] + p['n'] / FPS:
                return (p['f0'] + max(0.0, r - p['raw']) * FPS) / FPS
        p = ps[-1]
        return (p['f0'] + p['n']) / FPS
    return at


# ------------------------------------------------------------------ audio
def read_wav_any(path):
    out = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768


def read_ebi_audio(mov):
    """ebifry_clip.py muxes the voice with -itsoffset LEAD; keep that offset so the mouth matches the voice"""
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=start_time', '-of', 'csv=p=0', mov],
                       capture_output=True, text=True).stdout.strip()
    lead = float(r) if r and r != 'N/A' else 0.0
    return np.concatenate([np.zeros(int(round(lead * SR)), np.float32), read_wav_any(mov)])


def build_audio(sh, pieces, total, path):
    out = np.zeros(total * SPF, np.float32)
    X = snap.X
    fade = int(0.006 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    voice_rms = []
    for p in pieces:
        if p['kind'] != 'say':
            continue
        i0 = int(round(p['raw'] * SR)); n = p['n'] * SPF
        seg = X[i0:i0 + n].copy()
        seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        out[p['f0'] * SPF:p['f0'] * SPF + n] = seg
        voice_rms.append(np.sqrt(np.mean(seg ** 2)))
    vr = float(np.median(voice_rms))
    for p in pieces:
        if p['kind'] != 'ebi':
            continue
        y = read_ebi_audio(p['mov'])
        n = p['n'] * SPF
        y = y[p['skip'] * SPF:p['skip'] * SPF + n]
        act = y[np.abs(y) > 0.01]
        g = vr / max(1e-6, np.sqrt(np.mean(act ** 2))) * 1.05 if len(act) else 1
        y = y * g
        y[-fade:] *= ramp[::-1]
        out[p['f0'] * SPF:p['f0'] * SPF + len(y)] = y
    st = np.stack([out, out], 1)
    st = np.clip(st * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


# ------------------------------------------------------------------ static layers
def background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - 820) / H) ** 2)
    glow = np.clip(1 - d * 1.6, 0, 1) ** 2
    img = np.zeros((H, W, 3), np.float32)
    img[:] = BG
    img += glow[..., None] * np.array([26, 16, 10], np.float32)
    vig = np.clip(1 - np.maximum(0, d - 0.35) * 0.9, 0.55, 1)
    img *= vig[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def headline_img(sh):
    return text_block(sh['headline'], 78, fill=(255, 255, 255), stroke=0, accents=sh['hl_accent'], accent_fill=ACC,
                      line_h=104, shadow=6)


def caption_img(s):
    big = s.startswith('!')
    s = s.lstrip('!')
    size = 74 if big else 64
    lines = wrap(s, size, CAP_MAXW)
    if any(width(l, size) > CAP_MAXW for l in lines):
        size = 58
        lines = wrap(s, size, CAP_MAXW)
    return text_block(lines, size, fill=(255, 220, 90) if big else (255, 255, 255), stroke=9, stroke_fill=(12, 10, 9),
                      line_h=int(size * 1.3))


def caveat_img(s):
    return text_block([s], 29, fill=(196, 184, 174), bold=False)


def bubble_img(s):
    lines = wrap(s, 50, 760)
    tb = text_block(lines, 50, fill=(30, 22, 18), line_h=66)
    pw, ph = tb.width + 56, tb.height + 30
    im = Image.new('RGBA', (pw, ph + 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), 34, fill=(255, 250, 240, 255), outline=ACC, width=5)
    d.polygon([(pw / 2 - 26, ph - 6), (pw / 2 + 26, ph - 6), (pw / 2 + 4, ph + 30)], fill=(255, 250, 240, 255))
    d.line([(pw / 2 - 26, ph - 3), (pw / 2 + 4, ph + 30), (pw / 2 + 26, ph - 3)], fill=ACC, width=5)
    im.alpha_composite(tb, (28, 12))
    return im


def over(base, im, x, y, alpha=1.0):
    """alpha-composite PIL RGBA onto numpy RGB base (in place)"""
    a = np.asarray(im)
    x, y = int(round(x)), int(round(y))
    h, w = a.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = a[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    al = sub[..., 3:4] / 255 * alpha
    reg = base[y0:y1, x0:x1].astype(np.float32)
    base[y0:y1, x0:x1] = (reg * (1 - al) + sub[..., :3] * al).astype(np.uint8)


# ------------------------------------------------------------------ presenter
class Matte:
    def __init__(self):
        self.jobs = json.load(open('work/matte/jobs.json')) if os.path.exists('work/matte/jobs.json') else []
        import glob
        self.files = []
        for fn in glob.glob('work/matte/m_*.mov'):
            if fn.endswith('.part.mov'):
                continue
            a, b = os.path.basename(fn)[2:-4].split('_')
            self.files.append((float(a), float(b), fn))
        self.cur = None

    def frame(self, raw):
        for a, b, fn in self.files:
            if a <= raw <= b - 0.02:
                break
        else:
            raise RuntimeError(f'no matte for raw {raw:.2f}')
        idx = int(round((raw - a) * FPS))
        if not self.cur or self.cur['fn'] != fn or idx < self.cur['idx']:
            if self.cur:
                self.cur['p'].kill()
            p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', fn, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'],
                                 stdout=subprocess.PIPE)
            self.cur = dict(fn=fn, p=p, idx=-1, last=None)
        c = self.cur
        while c['idx'] < idx:
            buf = c['p'].stdout.read(1200 * 1080 * 4)
            if len(buf) < 1200 * 1080 * 4:
                break
            c['last'] = np.frombuffer(buf, np.uint8).reshape(1080, 1200, 4)
            c['idx'] += 1
        return c['last']


FACE = (560, 390)        # face centre in the matte crop (1200x1080)
ANCHOR = (CX, 848)       # where it lands on the canvas
BASE_S = 1.0
FADE_Y0, FADE_Y1 = 1390, 1530


def place_presenter(base, rgba, zoom):
    s = BASE_S * zoom
    M = np.float32([[s, 0, ANCHOR[0] - FACE[0] * s], [0, s, ANCHOR[1] - FACE[1] * s]])
    warped = cv2.warpAffine(rgba, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    al = warped[..., 3:4].astype(np.float32) / 255
    al *= FADE[..., None]
    base[:] = (base * (1 - al) + warped[..., :3] * al).astype(np.uint8)


FADE = np.ones((H, W), np.float32)
FADE[FADE_Y0:FADE_Y1] = np.linspace(1, 0, FADE_Y1 - FADE_Y0)[:, None]
FADE[FADE_Y1:] = 0


# ------------------------------------------------------------------ ebifry
class EbiClip:
    def __init__(self, mov):
        out = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', mov, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'],
                             capture_output=True, check=True).stdout
        self.frames = np.frombuffer(out, np.uint8).reshape(-1, 520, 560, 4)

    def get(self, k):
        return Image.fromarray(self.frames[min(k, len(self.frames) - 1)], 'RGBA')


# ------------------------------------------------------------------ main
def plan_frames(sh, pieces, total):
    """per item: sorted vis events in short time; captions in short time"""
    items = sh['items']
    vis, caps, cav = [], [], []
    for ii, it in enumerate(items):
        ps = [p for p in pieces if p['item'] == ii]
        f0, f1 = ps[0]['f0'], ps[-1]['f0'] + ps[-1]['n']
        if it['k'] == 'ebi':
            vis.append((f0 / FPS, 'ebi', {'clip': ps[0]}))
            continue
        at = make_at(pieces, ii)
        for rt, lay, args in it['vis']:
            vis.append((at(rt) if rt > it['raw'][0] else f0 / FPS, lay, dict(args, at=at, t0=at(rt) if rt > it['raw'][0] else f0 / FPS)))
        cs = it['cap']
        for k, (rt, txt) in enumerate(cs):
            ts = at(rt) if rt > it['raw'][0] else f0 / FPS
            te = at(cs[k + 1][0]) if k + 1 < len(cs) else f1 / FPS
            caps.append((ts, te, txt))
        if it.get('caveat'):
            cav.append((f0 / FPS, f1 / FPS, it['caveat']))
    vis.sort(key=lambda v: v[0])
    return vis, caps, cav


def render(sid, preview=False, only=None):
    sh = next(s for s in spec.SHORTS if s['id'] == sid)
    pieces, total = build_timeline(sh)
    os.makedirs('work/build', exist_ok=True)
    json.dump(pieces, open(f'work/build/{sid}_pieces.json', 'w'), indent=0)
    vis, caps, cav = plan_frames(sh, pieces, total)
    print(sid, 'frames', total, 'sec', total / FPS, flush=True)
    wav = f'work/build/{sid}.wav'
    if only is None:
        build_audio(sh, pieces, total, wav)
    bg = background()
    hl = headline_img(sh)
    hl_x, hl_y = CX - hl.width / 2, 276
    matte = Matte()
    cache = {}
    ebi_cache = {}

    def cached(key, fn):
        if key not in cache:
            cache[key] = fn()
        return cache[key]

    piece_at = np.zeros(total, np.int32)
    for i, p in enumerate(pieces):
        piece_at[p['f0']:p['f0'] + p['n']] = i

    enc = None
    if only is None:
        out = f'work/build/{sid}_video.mp4' if not preview else f'work/build/{sid}_preview_video.mp4'
        enc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                                '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast' if preview else 'slow',
                                '-crf', '24' if preview else '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p', out],
                               stdin=subprocess.PIPE)
    frames = range(total) if only is None else only
    prev_lay = None
    for f in frames:
        t = f / FPS
        p = pieces[piece_at[f]]
        cur = None
        for v in vis:
            if v[0] <= t + 1e-6:
                cur = v
        lay, args = cur[1], cur[2]
        img = bg.copy()
        if lay == 'talk':
            raw = p['raw'] + (f - p['f0']) / FPS
            place_presenter(img, matte.frame(raw), args.get('zoom', 1.0))
        elif lay == 'gfx':
            g = gfx.GFX[args['g']](t, args['t0'], args['at'], args)
            k = gfx.ease((t - args['t0']) / 0.18) if (prev_lay is None or prev_lay != ('gfx', args['g'])) else 1
            over(img, g, 0, gfx.STAGE_Y + (1 - gfx.ease((t - args['t0']) / 0.18)) * 40, alpha=min(1, (t - args['t0']) / 0.12 + 0.2))
        elif lay == 'ebi':
            cp = args['clip']
            if cp['mov'] not in ebi_cache:
                ebi_cache[cp['mov']] = EbiClip(cp['mov'])
            k = f - cp['f0']
            ec = ebi_cache[cp['mov']].get(k + cp['skip'])
            s = 1.0 if cp['f0'] == 0 else max(0.3, gfx.pop(k / 6))
            ew, eh = int(560 * 1.15 * s), int(520 * 1.15 * s)
            ec = ec.resize((ew, eh), Image.LANCZOS)
            over(img, ec, CX - ew / 2, 1252 - eh)
            bub = cached(('bub', cp['text']), lambda: bubble_img(cp['text']))
            over(img, bub, CX - bub.width / 2, 585, alpha=1.0 if cp['f0'] == 0 else min(1, k / 4))
        # headline (always)
        over(img, hl, hl_x, hl_y)
        for a, b, s in cav:
            if a <= t < b:
                ci = cached(('cav', s), lambda: caveat_img(s))
                over(img, ci, CX - ci.width / 2, 486)
        if lay != 'ebi':
            for a, b, s in caps:
                if a <= t < b:
                    ci = cached(('cap', s), lambda: caption_img(s))
                    over(img, ci, CX - ci.width / 2, CAP_Y - ci.height / 2)
        if enc:
            enc.stdin.write(img.tobytes())
        else:
            Image.fromarray(img).save(f'work/build/{sid}_f{f:05d}.png')
        if f % 150 == 0 and enc:
            print(sid, f, '/', total, flush=True)
    if enc:
        enc.stdin.close(); enc.wait()
    return pieces, total


if __name__ == '__main__':
    sid = sys.argv[1]
    preview = '--preview' in sys.argv
    only = None
    if '--frames' in sys.argv:
        only = [int(x) for x in sys.argv[sys.argv.index('--frames') + 1].split(',')]
    render(sid, preview, only)

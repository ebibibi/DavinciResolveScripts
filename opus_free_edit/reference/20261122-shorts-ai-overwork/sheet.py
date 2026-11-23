"""Contact sheet: first frame large + one frame every 3 s.  usage: sheet.py out/s1.mp4 out/s1_sheet.jpg"""
import subprocess, sys, json, os
from PIL import Image, ImageDraw, ImageFont
src, dst = sys.argv[1], sys.argv[2]
dur = float(json.loads(subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', src], capture_output=True, text=True).stdout)['format']['duration'])
def grab(t, w):
    out = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', f'{t:.3f}', '-i', src, '-frames:v', '1', '-vf', f'scale={w}:-1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
    import io; return Image.open(io.BytesIO(out)).convert('RGB')
first = grab(0, 540)
ts = [t for t in [3 * k for k in range(1, 100)] if t < dur - 0.2]
tw, th, cols = 216, 384, 6
rows = (len(ts) + cols - 1) // cols
W = 540 + 20 + cols * (tw + 8)
H = max(960, rows * (th + 30)) + 20
sheet = Image.new('RGB', (W, H), (30, 30, 30))
sheet.paste(first, (10, 10))
d = ImageDraw.Draw(sheet)
f = ImageFont.truetype('/home/ebi/.local/share/fonts/segoe/segoeuib.ttf', 20)
d.text((14, 972 if H > 985 else 940), '0.0 s (first frame)', font=f, fill=(255, 220, 90))
for k, t in enumerate(ts):
    r, c = divmod(k, cols)
    x, y = 560 + c * (tw + 8), 10 + r * (th + 30)
    sheet.paste(grab(t, tw), (x, y))
    d.text((x + 4, y + th + 2), f'{t:.0f} s', font=f, fill=(220, 220, 220))
sheet.save(dst, quality=85)
print(dst, sheet.size)

"""Matte the presenter out of the raw room recording with Robust Video Matting (CPU).
usage: matte.py START END OUT.mov   (raw seconds) -> ProRes4444 w/ alpha, 30fps, crop x 460..1660 (1200x1080)
"""
import os, subprocess, sys, time
import numpy as np, torch
os.chdir('/home/ebi/video-jobs/20261121-ai-overwork-shorts')
SRC = 'long/input/source.mkv'
X0, CW, CH = 460, 1200, 1080
start, end, out = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
torch.set_num_threads(int(os.environ.get('MT', '8')))
model = torch.jit.load('work/models/rvm_mobilenetv3_fp32.torchscript').eval()
dec = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-ss', f'{max(0,start-1.0):.3f}', '-i', SRC, '-ss', f'{min(1.0,start):.3f}',
                        '-t', f'{end-start:.3f}', '-vf', f'fps=30,crop={CW}:{CH}:{X0}:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{CW}x{CH}', '-r', '30',
                        '-i', '-', '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', out], stdin=subprocess.PIPE)
rec = [None] * 4
n, t0 = 0, time.time()
with torch.no_grad():
    while True:
        buf = dec.stdout.read(CW * CH * 3)
        if len(buf) < CW * CH * 3:
            break
        f = np.frombuffer(buf, np.uint8).reshape(CH, CW, 3)
        src = torch.from_numpy(f).permute(2, 0, 1).float().div(255).unsqueeze(0)
        fgr, pha, *rec = model(src, *rec, 0.4)
        a = pha[0, 0].numpy()
        # tighten soft edges a bit, kill faint background speckle
        a = np.clip((a - 0.04) / 0.92, 0, 1)
        fg = fgr[0].permute(1, 2, 0).numpy()
        rgba = np.dstack([np.clip(fg * 255, 0, 255), a * 255]).astype(np.uint8)
        enc.stdin.write(rgba.tobytes())
        n += 1
enc.stdin.close(); enc.wait()
print(f'{out}: {n} frames, {n/(time.time()-t0):.1f} fps')

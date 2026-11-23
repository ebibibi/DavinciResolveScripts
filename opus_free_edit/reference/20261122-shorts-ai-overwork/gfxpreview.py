import sys, os
sys.path.insert(0,'/home/ebi/video-jobs/20261121-ai-overwork-shorts/work/scripts')
import render, spec
from PIL import Image
for sh in spec.SHORTS:
    pieces, total = render.build_timeline(sh)
    vis, caps, cav = render.plan_frames(sh, pieces, total)
    fr = []
    for i, v in enumerate(vis):
        if v[1] in ('gfx', 'ebi'):
            end = vis[i+1][0] if i+1 < len(vis) else total/30
            fr.append(int(min(end - 0.1, v[0] + 2.2) * 30))
    render.render(sh['id'], only=fr)
    ims = [Image.open(f'work/build/{sh["id"]}_f{f:05d}.png').resize((360, 640)) for f in fr]
    m = Image.new('RGB', (360 * len(ims), 640))
    for k, im in enumerate(ims): m.paste(im, (k * 360, 0))
    m.save(f'work/look/gfx_{sh["id"]}.jpg', quality=88)
    print(sh['id'], fr)

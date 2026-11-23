import os, subprocess, sys, json
from concurrent.futures import ThreadPoolExecutor
os.chdir('/home/ebi/video-jobs/20261121-ai-overwork-shorts')
sys.path.insert(0, 'work/scripts'); import spec
os.makedirs('work/matte', exist_ok=True)
jobs = []
for s in spec.SHORTS:
    for it in s['items']:
        if it['k'] != 'say': continue
        if all(v[1] != 'talk' for v in it['vis']): continue
        a, b = it['raw'][0] - 0.3, it['raw'][1] + 0.3
        # skip big cut holes: matte each kept sub-range separately
        keep, cur = [], a
        for c0, c1 in sorted(it.get('cut', [])):
            if c1 - c0 > 1.5: keep.append([cur, c0 + 0.2]); cur = c1 - 0.2
            
        keep.append([cur, b])
        for k0, k1 in keep:
            name = f'work/matte/m_{k0:.2f}_{k1:.2f}.mov'
            if not os.path.exists(name): jobs.append((k0, k1, name))
json.dump(jobs, open('work/matte/jobs.json', 'w'))
print(len(jobs), 'jobs', sum(j[1]-j[0] for j in jobs), 's')
def run(j):
    env = dict(os.environ, MT='4')
    tmp = j[2] + '.part.mov'
    r = subprocess.run(['python3', 'work/scripts/matte.py', f'{j[0]:.3f}', f'{j[1]:.3f}', tmp], env=env, capture_output=True, text=True)
    if r.returncode == 0: os.rename(tmp, j[2])
    print(j, r.stdout.strip(), r.stderr.strip()[-300:] if r.returncode else '', flush=True)
with ThreadPoolExecutor(4) as ex: list(ex.map(run, jobs))

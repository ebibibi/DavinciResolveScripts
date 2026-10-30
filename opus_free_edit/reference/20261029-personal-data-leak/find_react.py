import json, subprocess, numpy as np, sys
sys.path.insert(0,'work/scripts')
words=json.load(open('work/words.json'))
gaps=[(a['end']+0.3,b['start']-0.3) for a,b in zip(words,words[1:]) if b['start']-a['end']>4.5]
def frames(t0,t1):
    n=int((t1-t0)*4)
    p=subprocess.run(['ffmpeg','-v','error','-ss',str(t0),'-i','input/proxy.mp4','-vf','fps=4','-frames:v',str(n),'-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    return np.frombuffer(p,np.uint8).reshape(-1,540,960,3)
res=[]
for t0,t1 in gaps:
    F=frames(t0,t1).astype(np.float32)
    r,g,b=F[...,0],F[...,1],F[...,2]
    fgm=((g-np.maximum(r,b))/(g+8))<0.12
    fgm[:,:,:75]=False; fgm[:,:,745:]=False
    tops=[]
    for m in fgm:
        rows=np.nonzero(m[:, 380:540].sum(1)>8)[0]
        tops.append(rows[0]*2 if len(rows) else 999)
    tops=np.array(tops)
    mot=np.abs(np.diff(F[:,40:250,380:540].mean(3),axis=0)).mean((1,2)) if len(F)>1 else np.array([0])
    res.append((t0,t1,tops,mot))
    print(f"{t0:7.1f}-{t1:7.1f} top med {np.median(tops):.0f} min {tops.min()} max {tops.max()} motion med {np.median(mot):.2f} max {mot.max():.2f}")

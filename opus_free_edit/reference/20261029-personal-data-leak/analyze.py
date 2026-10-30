import json, numpy as np, wave
W=json.load(open('input/transcript.json'))
words=[w for s in W['segments'] for w in s['words']]
json.dump(words,open('work/words.json','w'),ensure_ascii=False)
wf=wave.open('work/src_audio.wav'); sr=wf.getframerate()
a=np.frombuffer(wf.readframes(wf.getnframes()),dtype=np.int16).reshape(-1,2).astype(np.float32).mean(1)/32768
hop=sr//100  # 10ms
n=len(a)//hop
rms=np.sqrt((a[:n*hop].reshape(n,hop)**2).mean(1)+1e-12)
db=20*np.log10(rms)
np.save('work/db10ms.npy',db)
def lvl(t0,t1):
    x=db[int(t0*100):int(t1*100)]
    return (np.percentile(x,90) if len(x) else -99)
print('long words:')
for w in words:
    d=w['end']-w['start']
    if d>0.8: print(f"  {w['start']:.2f}-{w['end']:.2f} {d:.2f}s '{w['word']}' p90={lvl(w['start'],w['end']):.1f}dB")

import json,sys
d=json.load(open('/home/ebi/video-jobs/20261121-ai-overwork-shorts/long/input/transcript.json'))
a,b=float(sys.argv[1]),float(sys.argv[2])
for s in d['segments']:
    if s['end']<a or s['start']>b: continue
    print(' '.join('%s[%.2f-%.2f]'%(w['word'].strip(),w['start'],w['end']) for w in s['words'] if a-1<=w['start']<=b+1))

import json, os, sys
os.chdir('/home/ebi/video-jobs/20261121-ai-overwork-shorts')
sys.path.insert(0, 'work/scripts'); import spec
import eyecatch  # noqa: E402  (closing eyecatch, revision 2)
posts = json.load(open('work/posts.json'))
IDEA = {
 's1': 'AIエージェントを並列で回して週690件・夜にも185件指示していたら血圧160/109で受診した告白と、「AIは疲れず、人間は疲れる」という教訓。',
 's2': 'AIを10〜20並列で回すと、判断する人間1人がボトルネックになる。AIを止めずに流れを直す3つのルールと「任せる仕組み」の話。',
 's3': 'AI疲れには自分の数字で気づく。血圧の自動記録が効いた体験と、AI指示件数・時間帯・睡眠を見る勧め。',
}
TITLE = {s['id']: ' '.join(s['headline']) for s in spec.SHORTS}
shorts = []
for s in spec.SHORTS:
    sid = s['id']
    pieces = json.load(open(f'work/build/{sid}_pieces.json'))
    rng = []
    for p in pieces:
        if p['kind'] != 'say': continue
        a, b = round(p['raw'], 2), round(p['raw'] + p['n'] / 30, 2)
        if rng and abs(rng[-1][1] - a) < 0.3: rng[-1][1] = b
        else: rng.append([a, b])
    plats = ['tiktok', 'instagram', 'facebook', 'threads', 'x']
    shorts.append({'id': sid, 'title': TITLE[sid], 'idea': IDEA[sid],
                   'files': {p: f'out/{sid}.mp4' for p in plats},
                   'posts': {p: posts[sid][p] for p in plats},
                   'source_ranges': rng, 'source_ranges_note': 'raw recording seconds (long/input/source.mkv)',
                   'uses_ebifry': True if eyecatch.PHRASE.get(sid) else any(it['k'] == 'ebi' for it in s['items']),
                   'closing_eyecatch': {'seconds': eyecatch.N / 30, 'phrase': eyecatch.PHRASE[sid],
                                        'note': 'silent えびフライ + gold slash lines + theme phrase; no call to action'}})
vid = open('VIDEO_ID').read().strip()
json.dump({'source_video_id': vid, 'shorts': shorts}, open('out/shorts.json', 'w'), ensure_ascii=False, indent=1)
print('ok', [len(s['source_ranges']) for s in shorts])

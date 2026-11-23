import sys, whisper, warnings
warnings.filterwarnings('ignore')
m = whisper.load_model('small')
for f in sys.argv[1:]:
    r = m.transcribe(f, language='ja')
    print('##', f)
    for s in r['segments']:
        print(f"{s['start']:6.2f}-{s['end']:6.2f} {s['text']}")

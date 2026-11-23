"""Loudness-normalise the short's audio (2-pass loudnorm to -14 LUFS / -1.5 dBTP) and mux with the video.
usage: finalize.py s1 [--preview] [--ec]"""
import json, os, subprocess, sys
os.chdir('/home/ebi/video-jobs/20261121-ai-overwork-shorts')
sid = sys.argv[1]
preview = '--preview' in sys.argv
ec = '--ec' in sys.argv          # with the closing eyecatch from eyecatch.py (2026-11-22 review)
tag = '_ec' if ec else ''
vid = f'work/build/{sid}_preview_video.mp4' if preview else f'work/build/{sid}{tag}_video.mp4'
wav = f'work/build/{sid}{tag}.wav'
out = f'work/build/{sid}_preview.mp4' if preview else f'out/{sid}.mp4'
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', wav, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                   capture_output=True, text=True)
js = r.stderr[r.stderr.rfind('{'):r.stderr.rfind('}') + 1]
m = json.loads(js)
af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
      f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', vid, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                '-af', af, '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-shortest', '-movflags', '+faststart', out],
               check=True)
print(out)

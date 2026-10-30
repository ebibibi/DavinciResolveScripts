#!/bin/bash
# usage: mux.sh VIDEO OUT  -- two-pass loudnorm of work/audio_mix.wav to -14 LUFS, AAC 48k stereo, faststart
set -euo pipefail
cd /home/ebi/video-jobs/20261029-personal-data-leak
V=$1; OUT=$2
J=$(ffmpeg -nostdin -hide_banner -i work/audio_mix.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
mi=$(echo "$J" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['input_i'])")
mtp=$(echo "$J" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['input_tp'])")
mlra=$(echo "$J" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['input_lra'])")
mth=$(echo "$J" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['input_thresh'])")
off=$(echo "$J" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['target_offset'])")
ffmpeg -nostdin -v error -y -i "$V" -i work/audio_mix.wav -map 0:v:0 -map 1:a:0 -c:v copy \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$mi:measured_TP=$mtp:measured_LRA=$mlra:measured_thresh=$mth:offset=$off:linear=true,aresample=48000" \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest -movflags +faststart "$OUT"
echo "muxed $OUT"

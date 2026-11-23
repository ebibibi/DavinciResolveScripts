set -e
cd /home/ebi/video-jobs/20261121-ai-overwork-shorts
for s in s1 s2 s3; do
  python3 work/scripts/render.py $s 2>&1 | grep -v -E "Broken|trailer|^s[0-9] [0-9]+ /" || true
  python3 work/scripts/finalize.py $s
  python3 work/scripts/sheet.py out/$s.mp4 out/${s}_sheet.jpg
done
echo ALLDONE

set -e
# revision 2: append the closing eyecatch to the approved renders (no content re-render)
cd /home/ebi/video-jobs/20261121-ai-overwork-shorts
for s in s1 s2 s3; do
  python3 work/scripts/eyecatch.py $s --png
  python3 work/scripts/finalize.py $s --ec
  python3 work/scripts/sheet.py out/$s.mp4 out/${s}_sheet.jpg
done
echo ALLDONE

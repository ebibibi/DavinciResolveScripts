#!/bin/bash
# usage: bg.sh MODE JOBS  -> renders in the background, log in work/MODE.log
cd /home/ebi/video-jobs/20261029-personal-data-leak
start=$(date +%s)
python3 work/scripts/render.py "$1" --jobs "$2" > "work/$1.log" 2>&1
echo "exit $? after $(( $(date +%s) - start )) s" >> "work/$1.log"

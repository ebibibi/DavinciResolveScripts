---
type: kb
title: The advanced run looks frozen and plays a video by itself
symptom: After `Starting advanced highlight-first editing...` the console stays silent for 15 minutes, and a media player opens the video once on its own.
status: solved
date: 2026-07-26
updated: 2026-07-26
component: [DavinciResolveScripts, auto-editor, Whisper, FFmpeg]
tags: [progress, subprocess, auto-editor, ffmpeg, whisper, console]
scope: context
context: DavinciResolveScripts
---

# The advanced run looks frozen and plays a video by itself

## Symptom

`run_advanced_auto_video_editor.ps1` prints its two banner lines and then shows
nothing at all for 15 minutes or more. There is no way to tell whether the run
is progressing, stuck, or dead. Partway through, the media player opens and
plays a video once, which nobody asked for.

## Cause

Two independent causes with the same visible result.

1. `highlight_video.py` ran every child process through a helper that used
   `stdout=subprocess.PIPE, stderr=subprocess.PIPE`. auto-editor, Whisper and
   FFmpeg all print progress, but that output went into a pipe that was only
   read after the process exited. Four multi-minute steps ran back to back
   (silence cut, transcription, `claude --print` with a 180 second timeout,
   and the final H.264 encode), so the console was silent for the whole run.
2. auto-editor opens the finished file in the system media player unless
   `--no-open` is passed. That is the video that plays by itself, and it is
   also the only visible sign that step 1 of 5 has finished.

Video tools redraw their progress bars with a carriage return rather than a
newline, so simply forwarding the pipe is not enough — the reader has to treat
`\r` as a line break. Python's text mode does this already, because universal
newline translation converts `\r` to `\n`.

## Resolution

- Stream child output instead of capturing it. `_stream_process` in
  `highlight_video.py` uses `subprocess.Popen` with `text=True` and
  `stderr=subprocess.STDOUT`, and forwards each line to `ProgressReporter`
  while keeping the last 400 lines so error diagnostics still work.
- Report named stages: `[3/5] Transcribing the cut master (whisper) ...`,
  with elapsed time, percentage and ETA. The percentage comes from the FFmpeg
  `time=` field, Whisper `-->` timestamps, or a self-reported `NN%`, compared
  against the known media duration.
- Print a heartbeat every 20 seconds while a step is silent, which covers
  `claude --print` — it prints nothing at all until it answers.
- Pass `--no-open` to auto-editor so the pipeline stops launching the player.
- Pass `-hide_banner -loglevel warning -stats` to FFmpeg so the useful stats
  line is not buried under 40 lines of build configuration.

## Consequences

- The console shows which of the five steps is running and how far along it is.
- `--quiet` restores the old silent behaviour for scripted use; the final path
  is still the last line on stdout either way.
- Progress text is ASCII only, and the reporter falls back to replacement
  characters if the console encoding cannot represent a transcript line, so a
  cp932 console cannot kill a render that has already run for ten minutes.

## Related

- [auto-editor reports an empty timeline](auto-editor-empty-timeline.md)

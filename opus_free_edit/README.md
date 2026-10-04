# Agentic free-form edit (experiment)

The advanced route (ADR-015) asks the model for one strict JSON plan and renders it
deterministically. This experiment does the opposite: a `claude -p` session receives the
transcript, frames and tools and makes **every** editorial decision itself - structure, cuts,
overlays, stingers, previews, self-review, final render, title and description.

Only the steps that are the same for every recording are scripted:

| step | script | notes |
|---|---|---|
| probe, 16 kHz audio, 540p proxy | `prepare.sh` | proxy is used for previews |
| Whisper large-v3-turbo with word timestamps | `prepare.sh` | runs on the GPU host (`WHISPER_HOST`, default `spark`) |
| name and sign-off normalised in the transcript | `fix_transcript.py` | Whisper prompt describes them; the script fixes remaining variants |
| silence map, frames every 10 s, 4x4 contact sheets | `prepare.sh` | inputs for the agent |
| slides of the deck that was presented (optional) | `prepare.sh` with `DECK_SLUG` | uses `npm run capture:video` in presentations-web (`PRESENTATIONS_REPO`) |
| the edit | `claude -p` with `brief.md` | model: `EDIT_MODEL` (default `claude-opus-5-5`) |
| token and cost summary | `usage_report.py` | reads the stream-json log |
| thumbnail must show the whole head (gate before upload) | `check_thumbnail.py` | YuNet face detector; rejects text, panels, gradients or the logo over the head |
| no silence left in the presenter's parts | `check_silence.py` | measured from the audio, not from Whisper word timestamps |
| private upload with title, captions, thumbnail | `upload_private.py` | never public; leaves `~/video-jobs/handoff/<video_id>/` so the post-upload automation keeps the editor thumbnail |

```bash
WINNING_PATTERN=/path/to/winning-pattern.md \
  opus_free_edit/run.sh /path/to/recording.mkv /path/to/job-dir   # add --no-upload to skip the upload
```

The job directory keeps everything the agent produced: `work/` (its EDL, render scripts,
agent log) and `out/` (`final.mp4`, `youtube.json`, `captions.srt`, `thumbnail.png`,
`EDIT_NOTES.md`, `USAGE.md`). `EDIT_NOTES.md` lists the steps the agent itself found mechanical;
those are the candidates to move into `prepare.sh` next.

The agent runs with `--permission-mode bypassPermissions` inside the job directory. Run it only on
recordings you own, on a machine where that is acceptable.

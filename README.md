# Highlight-First Video Editor

This repository automates the repetitive first pass for long-form YouTube videos.
The default workflow is deliberately independent of the DaVinci Resolve API.

## Default workflow

1. Find the newest OBS recording.
2. Use `auto-editor` to remove silence with the proven settings:
   `audio:threshold=1%` and `--margin 0.5sec`.
3. Transcribe the cut master, so every timestamp is on the edited timeline.
4. Select one highlight for a short video, two for a 20+ minute video, or three
   for a 45+ minute video.
5. Copy the selected highlights to the beginning. The same moments remain in
   the complete main body.
6. Render a large opening takeaway title over the first highlight.
7. Save the final MP4 and a reviewable `highlight_plan.json` manifest.

The output order is always:

```text
highlight 1 -> [highlight 2 -> highlight 3] -> complete cut master
```

DaVinci Resolve can still be used for final review or manual corrections, but
Text+, Fusion, topic labels, and timeline manipulation are no longer part of
the default automation path.

## Requirements

- Python 3.10 or later
- [auto-editor](https://auto-editor.com/)
- FFmpeg and ffprobe with libass support
- Whisper CLI for automatic transcription
- Claude CLI is optional; deterministic local highlight selection is used when
  Claude is unavailable

## Quick start on Windows

1. Copy `有償版用スクリプト/config.example.json` to
   `有償版用スクリプト/config.local.json`.
2. Set `working_dirs` to the OBS recording folder.
3. Run `有償版用スクリプト/run_auto_video_editor.ps1`.
4. Review the generated MP4 and `highlight_plan.json` under
   `_highlight_output/<recording name>/`.

You can also pass a recording explicitly:

```powershell
python "有償版用スクリプト/highlight_video.py" "C:\Videos\recording.mkv"
```

## Configuration

The `opening_highlight` object supports:

| Key | Purpose | Default |
|---|---|---:|
| `maximum_highlights` | Maximum opening clips | `3` |
| `maximum_total_seconds` | Total highlight reel duration | `24` |
| `maximum_segment_seconds` | Maximum copied length per clip | `8` |
| `padding_seconds` | Context added around selected speech | `0.5` |
| `minimum_gap_seconds` | Minimum source distance between highlights | `30` |
| `title_seconds` | Opening takeaway display duration | `4` |
| `font_name` / `font_size` | ASS title style | `Noto Sans CJK JP` / `96` |
| `manual_title` | Deterministic title override | empty |
| `manual_highlights` | Deterministic `{start, end}` ranges | empty |
| `transcript_command` | Custom transcription command with placeholders | empty |

`transcript_command` accepts `{input}`, `{output_dir}`, and `{stem}`. This
allows a local wrapper or remote GPU workflow without embedding credentials in
the repository.

Example manual override:

```json
{
  "opening_highlight": {
    "manual_title": "The practical workflow that cuts editing time",
    "manual_highlights": [
      {"start": 125.0, "end": 132.0},
      {"start": 921.0, "end": 928.0}
    ]
  }
}
```

Manual highlights use cut-master timestamps and bypass Whisper and Claude.

## Safe fallbacks

- If auto-editor reports an empty timeline, the recording is preserved with
  `--edit none`.
- If transcription or highlight selection fails, the usable cut master remains
  the output.
- If FFmpeg rendering fails, a partial file is deleted and the cut master is
  retained.
- Every fallback reason is recorded in `highlight_plan.json`.

## Legacy Resolve script

`有償版用スクリプト/auto_video_editor.py` has been restored to the last
pre-AI-editing baseline for historical/manual use. It is not called by the
default runner. The free-edition script is likewise kept as a legacy utility.

## Tests

```bash
python -m pytest -q
python -m coverage run --branch -m pytest
python -m coverage report --fail-under=80
ruff check .
bandit -r "有償版用スクリプト"
```

## License

This project may be used for personal and commercial work.

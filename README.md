# DaVinci Resolve Auto Editors

This repository provides three explicit editing routes for long-form YouTube
videos. The stable route preserves the long-running DaVinci Resolve workflow,
the dual source route edits a screen capture and a camera file as one timeline,
and the advanced route is where new automation is developed and tested.

## Choose a workflow

| Route | Run this | Use it when |
|---|---|---|
| **Stable** | `有償版用スクリプト/run_auto_video_editor.ps1` | The recording is one file and only needs proven silence removal and the standard Resolve template timeline. |
| **Dual source** | `有償版用スクリプト/run_dual_source_video_editor.ps1` | The recording folder holds one `.mkv` screen capture and one `.mp4` camera file that belong on V1 and V2. |
| **Advanced** | `有償版用スクリプト/run_advanced_auto_video_editor.ps1` | You intentionally want to try the latest highlight, title, or other experimental features. |

The familiar `run_auto_video_editor.ps1` name deliberately remains attached to
the stable workflow. New features must not silently change its output — each
route names its own Python entry point and nothing else.

## Stable workflow

The stable launcher runs `auto_video_editor.py` and keeps the established
DaVinci Resolve process:

1. Start or connect to DaVinci Resolve.
2. Create a project from `テンプレート.drp`.
3. Find the newest OBS recording.
4. Use `auto-editor` to remove silence with the values from
   `有償版用スクリプト/config.json`
   (default: `audio:threshold=3%` and `--margin 0.3sec`).
5. Import the generated timeline and combine it with the template timeline and
   ending clip.

Use this route when the instruction is effectively “do nothing extra.”

## Dual source workflow

`run_dual_source_video_editor.ps1` runs `dual_source_video_editor.py` for a
lecture recorded as two files in one folder, for example `!OBS録画/az900-3/`:

1. Take the newest subfolder holding exactly one `.mkv` and one `.mp4`.
2. Align the two files by correlating their audio, and stop if they do not match.
3. Run `auto-editor` once, on the camera file that carries the microphone, and
   read the surviving segments from its JSON cut list. The export is called `v3`
   on current auto-editor and `json` on older ones; both are tried.
4. Place every segment three times at the same timeline frame: the slide capture
   on V1, the camera on V2, and the camera audio on A1. The slide audio is not
   used.
5. Apply the camera and slide placement measured from the AZ-900 project.
   The timeline, the two recordings and the cut list may all run at different
   frame rates, so the plan is computed in seconds and converted per track.
6. Append the template's ending clip after the last segment.

The folder can also be given explicitly:

```powershell
& ".\有償版用スクリプト\run_dual_source_video_editor.ps1" --folder "C:\...\!OBS録画\az900-3"
```

Smooth Cut and the green screen key remain manual, because the Resolve scripting
API can add neither transitions nor Edit page effects. See
[docs/dual-source-editing-plan.md](docs/dual-source-editing-plan.md) and
[ADR-009](docs/adr/009-give-dual-source-editing-its-own-script-and-launcher.md).

The measured offset can also be checked on its own:

```powershell
python "有償版用スクリプト/audio_sync.py" slides.mkv camera.mp4
```

## Advanced workflow

1. Find the newest OBS recording.
2. Use `auto-editor` to remove silence with the values from
   `有償版用スクリプト/config.json`.
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
Text+, Fusion, topic labels, and timeline manipulation are not part of this
advanced pipeline.

### Watching a run

The advanced run takes many minutes, so every step reports itself while it
works. Each stage is numbered, and long steps show a percentage, the position
in the media and an ETA:

```text
[3/5] Transcribing the cut master (whisper) ... started
    Transcribing the cut master (whisper)   43.0%  00:13 / 00:30  elapsed 00:10  eta 00:14
    done in 00:46 (128 segments)
```

A step that produces no output of its own, such as the Claude call, prints a
heartbeat every 20 seconds so a slow run is never mistaken for a hang. Use
`--heartbeat-seconds` to change that interval, and `--quiet` to suppress the
report entirely when another script only needs the final path from stdout.

## Requirements

- Python 3.10 or later
- NumPy (installed with auto-editor)
- [auto-editor](https://auto-editor.com/)
- FFmpeg and ffprobe with libass support
- Whisper CLI for automatic transcription
- Claude CLI is optional; deterministic local highlight selection is used when
  Claude is unavailable

## Quick start on Windows

For the stable workflow, run:

```powershell
& ".\有償版用スクリプト\run_auto_video_editor.ps1"
```

For the advanced workflow:

1. Copy `有償版用スクリプト/config.example.json` to
   `有償版用スクリプト/config.json`.
2. Set `working_dirs` to the OBS recording folder.
3. Run `有償版用スクリプト/run_advanced_auto_video_editor.ps1`.
4. Review the generated MP4 and `highlight_plan.json` under
   `_highlight_output/<recording name>/`.

Run `有償版用スクリプト/create_desktop_shortcut.ps1` once to create separate
**Stable**, **Dual Source** and **Advanced** desktop shortcuts.

You can also pass a recording explicitly:

```powershell
python "有償版用スクリプト/highlight_video.py" "C:\Videos\recording.mkv"
```

## Staying up to date

Every `.ps1` entry point runs `git pull --ff-only` on itself before it starts and
prints the commit it is about to run with. A merged fix that never reaches the
editing machine is not a fix: PR #29 sat unmerged for two weeks and the working
copy was never pulled, so a known-broken placement kept shipping.

The update never stops a run — an edit with a slightly old script beats no edit
at all — but it always says what happened, because "it did not update" and "it
updated and is still wrong" send the next hour into different code. It declines
to update, and says so, when the checkout is on another branch, has uncommitted
changes to tracked files, or cannot reach the remote. It never discards work:
there is no `reset --hard` anywhere in it, and `config.json` is ignored by Git,
so environment-local tuning is never touched.

Changes to a launcher itself take effect on the following run, because
PowerShell has already read the file it is executing. The Python it starts
afterwards is always the freshly pulled version.

## Silence-cut configuration

`有償版用スクリプト/config.json` is ignored by Git, so each recording
environment can keep its existing local tuning. The same file is used by the
stable, dual-source, advanced, and free workflows:

```json
{
  "auto_editor": {
    "threshold_percent": 3,
    "margin_seconds": 0.3
  }
}
```

`threshold_percent` must be greater than 0 and no more than 100.
`margin_seconds` must be 0 or greater. If the file does not exist, the shown
values are used as defaults. Invalid values stop the run with a clear error
instead of silently using different settings.

An environment that still holds `"threshold_percent": 1` from an earlier release
should raise it: the camera microphone the dual-source route analyses never
falls below 1%, so that value keeps 99.7% of a talk and removes no silence at
all. See [ADR-013](docs/adr/013-cut-silence-at-3-percent-for-a-hot-camera-microphone.md).

## Opening-highlight configuration

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

## Stability boundary

`有償版用スクリプト/auto_video_editor.py` is the protected stable entry point.
Every other workflow lives in its own module, named explicitly by its own
launcher: `dual_source_video_editor.py` for the slides plus camera edit and
`highlight_video.py` for the advanced route. `resolve_session.py` holds the
Resolve bootstrap those newer entry points share; the stable editor keeps its
own copy on purpose, so changing one cannot move the other. The free-edition
script is kept as a separate legacy utility.

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

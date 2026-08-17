# Dual source editing (slides + camera)

## The recording shape

OBS writes one folder per lecture, for example `!OBS録画/az900-3/`:

| File | Content | Destination |
|---|---|---|
| `*.mkv` | PowerPoint screen capture | V1 |
| `*.mp4` | The presenter in front of a green screen | V2, and the only audio |

The two files start at different moments, so they have to be aligned before
anything else happens. Both carry the same voice, which is the only reliable way
to align them without a clapperboard.

This route has its own entry point, `dual_source_video_editor.py`, started by
`run_dual_source_video_editor.ps1`, which names that script explicitly. The
stable single source editor is untouched. See
[ADR-009](adr/009-give-dual-source-editing-its-own-script-and-launcher.md).

## Pipeline

1. **Pick the pair.** Take the newest subfolder that holds exactly one `.mkv`
   and one `.mp4`, or the folder named by `--folder`. Anything else stops the
   run with a pointer to the stable launcher, rather than editing half of it.
2. **Align the audio.** `audio_sync.py` decodes both files to 8 kHz mono,
   reduces each to a loudness envelope at 200 points per second, and correlates
   them. The result is the point in the camera file that matches time zero of
   the slide file, plus the correlation coefficient at that point. A weak match
   stops the run instead of silently assuming zero.
3. **Find the silence.** Run `auto-editor` once, on the camera file that carries
   the microphone, with the proven `audio:threshold=3%` and `--margin 0.3sec`.
   The export that prints a v3 timeline is named `v3` on current versions and
   `json` on older ones, so both are tried in that order. Current auto-editor
   also rewrites the `--output` extension to `.v3` regardless of what was asked
   for, so the file that was actually written is looked up rather than assumed,
   and any leftover from a previous run is deleted first. On Windows the input
   path inside that JSON is written in the active code page rather than UTF-8,
   so the file is decoded leniently — only the numbers matter, and a path that
   cannot be decoded must not stop the run. The result describes every surviving
   segment as `{start, dur, offset}` — a machine readable cut list rather than a
   finished timeline.
4. **Build both tracks.** Each surviving segment becomes three
   `AppendToTimeline` entries sharing one record frame: the slide clip on V1,
   the camera clip on V2, and the camera audio on A1. One length in timeline
   frames drives all three, divided by each track's conform factor, so the two
   views cannot drift and no hole opens between clips. Record frames are
   accumulated from the placed durations, so trimming one segment shifts what
   follows instead of leaving a hole. Every imported clip has its start timecode
   zeroed first — see ADR-012, without which the camera lands 64 seconds away.
5. **Size the camera.** `SetProperty` applies the measured placement below to
   every clip on both tracks.
6. **Wrap it.** The template's opening clip decides where the body starts, and
   the ending clip is appended after the last segment.

## Four frame rates, none of which have to agree

The template timeline runs at 60 fps while the recordings usually do not, and
auto-editor counts the cut list in its own timebase. Frame numbers therefore
mean different things depending on which of the four they belong to:

| Rate | What it counts |
|---|---|
| Timeline | `recordFrame` — where a clip sits on the timeline |
| Slide capture | `startFrame` / `endFrame` of every V1 clip |
| Camera | `startFrame` / `endFrame` of every V2 and A1 clip |
| Cut list | the `{start, dur, offset}` auto-editor reported |

The plan is therefore computed in seconds and converted once per track, using
the frame rate Resolve reports for that clip. Mixing them by frame number would
shift the edit silently, which is exactly the kind of error that only shows up
after the render.

Two corrections come out of that, both measured against Resolve rather than
derived from the documentation:

- **Conform factor.** Resolve gives one frame of the 30 fps capture two timeline
  frames and one frame of the 59.94 fps camera one. Each segment's length is
  therefore decided once in timeline frames and divided by that factor, instead
  of being rounded separately per track — otherwise the two roundings disagree on
  about one segment in six and leave a one frame hole.
- **Placement scale.** `startFrame` is read through the same conform, so a 59.94
  fps camera lands 0.1% deeper into the media than asked: 119 frames two thirds
  of the way through a 43 minute talk. The request is scaled by the clip's
  conformed rate over the timeline's, which cancels it exactly. The 30 fps
  capture conforms to 60 on the nose, so its scale is 1.

## Measured placement

Taken from the manually edited AZ-900 project, whose timeline is 1920x1080. The
slide capture is shrunk and moved left; the camera keeps its scale and is moved
right and cropped, so the presenter stands beside the slides.

| Track | Property | Value |
|---|---|---:|
| V1 slides | `ZoomX` / `ZoomY` | 0.922 |
| V1 slides | `Pan` / `Tilt` | -300 / 2 px |
| V2 camera | `Pan` | 626 px |
| V2 camera | `CropLeft` / `CropRight` / `CropTop` | 249.2 / 337.1 / 98.9 px |

These live in `dual_source.py` as `SLIDES_PROPERTIES` and `CAMERA_PROPERTIES`.
The crop belongs to the camera framing of that particular shoot, so it is the
first thing to re-check if the camera moves.

## When the two recordings do not cover the same moments

- **The camera started first**, which is normal: it is started by hand while the
  slide capture is started by OBS, so the opening of the talk can exist only on
  the camera — 17 seconds of it in the AZ-900 recordings of 2026-08-02. That head
  is trimmed off both tracks together. Only a head longer than five minutes stops
  the run; the real guard against two unrelated files is the sync confidence, and
  a limit tight enough to second-guess it just refuses valid sessions.
- **The slide capture stopped first**: segments past its end are dropped rather
  than placed, and the count is logged.

## What still has to be done by hand

- **Smooth Cut on the camera track.** The Resolve scripting API has no
  transition call — there is no `AddTransition`, and the word "transition" does
  not appear in the v19.1 or v20.3 API reference. Smooth Cut is also Resolve
  specific, so it cannot be smuggled in through FCPXML, which only knows generic
  dissolves. Set Smooth Cut as the standard transition once, select the camera
  track and apply it to every edit point. The AZ-900 project used 14 frames.
- **The green screen key.** In the AZ-900 project the 3D keyer is an Edit page
  effect on each camera clip, which the API cannot set either. Applying the key
  as a Color page node instead would make it scriptable, because
  `TimelineItem.CopyGrades` can push one clip's node stack onto all the others.

A `.drp` is a zip holding a readable `project.xml`, so writing the transition
into the project file is the one route to full automation. It is also the route
that breaks silently on a Resolve update, so it stays out of the production
script until there is a reason to pay that price.

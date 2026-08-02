# Dual source editing plan (slides + camera)

## The recording shape

OBS now writes one folder per lecture, for example `!OBS録画/az900-3/`:

| File | Content | Destination |
|---|---|---|
| `*.mkv` | PowerPoint screen capture | V1 |
| `*.mp4` | The presenter in front of a green screen | V2 |

The two files start at different moments, so they have to be aligned before
anything else happens. Both carry the same voice, which is the only reliable
way to align them without a clapperboard.

## Pipeline

1. **Pick the pair.** Take the newest subfolder that holds exactly one `.mkv`
   and one `.mp4`. Anything else falls back to the existing single source
   behavior, so old recordings keep editing exactly as before.
2. **Align the audio.** `audio_sync.py` decodes both files to 8 kHz mono,
   reduces each to a loudness envelope at 200 points per second, and correlates
   them. The result is the point in the camera file that matches time zero of
   the slide file, plus a confidence score. A weak match stops the run instead
   of silently assuming zero.
3. **Find the silence.** Run `auto-editor` once, on the file that carries the
   microphone, with the proven `audio:threshold=3%` and `--margin 0.2sec`, and
   `-ex json`. That prints a v3 timeline describing every surviving segment as
   `{start, dur, offset}` in timeline frames — a machine readable cut list
   rather than a finished timeline.
4. **Build both tracks.** For each surviving segment call
   `MediaPool.AppendToTimeline` twice, with the same `recordFrame` and duration:
   once with the slide clip on `trackIndex: 1`, once with the camera clip on
   `trackIndex: 2` and its source frames shifted by the measured offset. Because
   both tracks are cut at the same timeline frames, the two views stay in sync
   for the whole video.
5. **Size the camera.** Every camera item gets `SetProperty` for `ZoomX`,
   `ZoomY`, `Pan` and `Tilt`, so the presenter sits in the agreed corner at the
   agreed size.
6. **Smooth the camera cuts.** See below — this is the one step the API cannot
   do.

## What is already proven

- `audio_sync.py` recovers a known offset to within one frame on lossless audio
  and within a quarter of a second across an mkv/mp4 pair, and reports low
  confidence for unrelated recordings. Covered by `tests/test_audio_sync.py`.
- `auto-editor 25.0.1 -ex json` emits the v3 cut list described above. Verified
  locally.
- `AppendToTimeline` accepts `trackIndex` and `recordFrame`, which this
  repository already relies on for placing Text+ on V2.
- `TimelineItem.SetProperty` exposes `ZoomX`, `ZoomY`, `Pan` and `Tilt`, so the
  camera placement is fully scriptable.

## The one blocker: Smooth Cut

The DaVinci Resolve scripting API has no transition call. There is no
`AddTransition`, and the word "transition" does not appear anywhere in the
v19.1 or v20.3 API reference. Smooth Cut is also Resolve specific, so it cannot
be smuggled in through FCPXML, which only knows generic dissolves.

The three ways out, in the order they should be tried:

1. **One keystroke at the end.** Set Smooth Cut once as the standard transition,
   then select the camera track and apply the standard transition to every edit
   point. Fully automated timeline, three seconds of human work.
2. **Drive the keystroke from the launcher.** The PowerShell launcher can send
   the same keys to Resolve. It works, but it depends on window focus and menu
   layout, so it belongs behind an explicit opt-in flag.
3. **Write the transition into the project file.** A `.drp` is a zip holding a
   readable `project.xml`, so a Resolve native timeline can in principle be
   authored outside Resolve. This is the only route to full automation, and it
   is also the only route that can break silently on a Resolve update, so it
   needs a real sample project to study first.

## Open questions

- Which file carries the microphone, and should the other file's audio be muted
  or removed?
- The exact camera size and position used in the Az900 project.
- Whether Smooth Cut was applied to every camera cut, and with what duration.
- Whether the existing opening and ending clips from the template still wrap the
  result.

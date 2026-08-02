---
type: kb
title: Camera clips land 64 seconds away from the cut
symptom: The dual source timeline builds without error, but the camera shows a different moment from the slides and the removed silences are still audible.
status: solved
date: 2026-08-02
updated: 2026-08-02
component: [DavinciResolveScripts, DaVinci Resolve, dual-source]
tags: [timecode, drop-frame, AppendToTimeline, frame-rate]
scope: context
context: DavinciResolveScripts
---

# Camera clips land 64 seconds away from the cut

## Symptom

`run_dual_source_video_editor.ps1` reports success — every segment placed, the
transforms applied, the ending clip appended — but on the Edit page:

- the camera on V2 shows a different part of the talk from the slides on V1
- the audio still contains the pauses auto-editor removed
- near the end of the timeline the camera clips are empty or zero length

Nothing in the log points at it. Raising the silence threshold does not help,
because the cut list is correct; the residual silence inside a placed clip is at
most the margin, 0.6 seconds.

## Cause

`MediaPool.AppendToTimeline` interprets `startFrame` against the clip's **start
timecode**, not against the first frame of the media. A camera that stamps the
time of day carries a timecode like `17:54:31;54`, so every source position is
displaced. Measured on the template's 60 fps `main` timeline with a 59.94 fps
camera:

| clip | start timecode | asked for | got |
| --- | --- | --- | --- |
| screen capture `.mkv` | 00:00:00:00 | 108 | 108 |
| camera `.MP4` | 17:54:31;54 | 1253 | 5119 |

The screen capture is unaffected because OBS writes `00:00:00:00`, which is why
only one of the two tracks looks wrong.

The displacement grows across the talk — 3866 frames at the start, 3984 near the
end — at 0.1%, the ratio between 59.94 and 60. Once it exceeds the remaining
media, Resolve pins the clip to the last frame and its length collapses to zero.

`recordFrame` is not involved: the shift is identical whether it is supplied or
omitted.

## Resolution

Set the start timecode of every imported clip to `00:00:00:00` before computing
any frame number:

```python
media_pool_item.SetClipProperty("Start TC", "00:00:00:00")
```

The same request then lands where it was asked to, within the one frame that
59.94 against 60 costs. See ADR-012, which also covers deriving one timeline
length per segment so V1 and V2 cannot round apart.

## Consequences

- The clips inside the generated project no longer report the shooting time. The
  files on disk are untouched.
- Any future entry point that computes source frames has to do the same, so the
  helper lives next to the import rather than inside one function.

## Related

- [ADR-012: Zero the source timecode before placing clips](../adr/012-zero-the-source-timecode-before-placing-clips.md)

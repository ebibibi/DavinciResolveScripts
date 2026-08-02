---
type: adr
id: ADR-014
title: Zero the source timecode before placing clips
decision: Set every imported clip's start timecode to 00:00:00:00, and derive one timeline length per segment for all tracks.
status: accepted
date: 2026-08-02
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, dual-source, timecode, frame-rate]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by:
---

# Zero the source timecode before placing clips

## Context

The first dual source run that reached DaVinci Resolve produced a timeline that
looked right — 356 cuts, both tracks, the ending clip — and was wrong in every
frame. The camera showed a different moment from the slides, and the audio kept
the silences auto-editor had removed.

Two separate faults, both about how a frame number is read.

**The source timecode.** `MediaPool.AppendToTimeline` reads `startFrame` against
the clip's start timecode, not against its first frame. The camera stamps the
time of day — `17:54:31;54`, drop frame — so every camera clip landed 3866 frames
(64.5 seconds) away from the moment the cut list picked. The screen capture is
`00:00:00:00` and landed exactly where it was asked to, which is why the two
views never met. Measured on the template's `main` timeline:

| clip | start timecode | asked for | got |
| --- | --- | --- | --- |
| screen capture `.mkv` | 00:00:00:00 | 108 | 108 |
| camera `.MP4` | 17:54:31;54 | 1253 | 5119 |
| camera `.MP4`, timecode zeroed | 00:00:00:00 | 1253 | 1254 |

The error was not constant: it grew from 3866 to 3984 frames across the talk, at
0.1%, the ratio between 59.94 and 60. Near the end the camera clips ran past the
end of the media and Resolve pinned them to the last frame at zero length.

**The conform factor.** Resolve gives one frame of a 30 fps capture two frames of
a 60 fps timeline, and one frame of a 59.94 fps camera one frame. Each track's
length was being worked out from seconds at its own rate, so the two roundings
disagreed on about one segment in six, leaving a one frame hole between clips and
letting V1 slip a frame against V2.

Underneath that sat a smaller version of the same fault. `startFrame` is read
through the conform, so the camera landed 0.1% deeper into the media than asked
— 119 frames two thirds of the way in, 156 by the end. Pulling the request back
by the clip's conformed rate over the timeline's cancels it exactly, measured to
zero residual across the whole 43 minutes. The scale belongs to the entry point
only: the frames between `startFrame` and `endFrame` are laid down one for one,
and scaling the length as well shortens every clip past about eight seconds by a
frame, which is what left 55 holes on V2 and A1.

## Alternatives considered

- **Add the timecode offset to `startFrame` instead of zeroing it** — Rejected.
  It means reimplementing Resolve's drop frame arithmetic; the measured shift of
  3866 does not match the textbook drop count of 3868, so the calculation would
  be a guess that fails silently.
- **Render an intermediate without timecode** — Rejected. A full re-encode of a
  17 GB camera file for every run, to work around one property.
- **Round every segment up to whole timeline frames per track** — Rejected. It
  fixes the holes but not the drift, because the two tracks still round apart.

## Decision

- Every clip the dual source editor imports has its start timecode set to
  `00:00:00:00` before any frame is computed, and a clip that refuses stops the
  run rather than being placed at the wrong moment.
- `build_placements` works out one length in timeline frames per segment and
  divides it by each track's conform factor, so V1, V2 and the audio always cover
  exactly the same span.
- The frame a clip is entered at is scaled by that clip's conformed rate over the
  timeline's; its length is not.
- A frame rate that is not a whole multiple of the timeline rate is refused, since
  the factor would have to be guessed.

## Rationale

The timecode is metadata about when the camera was rolling, and nothing in this
workflow reads it. Zeroing it makes frame numbers mean what the rest of the code
already assumes they mean. The conform factor is measured from Resolve rather
than derived, because the nominal-rate rule is not in the API documentation.

## Consequences

- The imported clips in the generated project no longer carry the shooting time.
  The originals on disk are untouched.
- A camera at a rate that does not divide the timeline stops the run with a clear
  message instead of drifting.

## Related

- [ADR-009: Give dual source editing its own script and launcher](009-give-dual-source-editing-its-own-script-and-launcher.md)
- [ADR-013: Cut silence at 3 percent for a hot camera microphone](013-cut-silence-at-3-percent-for-a-hot-camera-microphone.md)

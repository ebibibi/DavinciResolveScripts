---
type: adr
id: ADR-011
title: Cut silence at 3 percent for a hot camera microphone
decision: Return the shared silence threshold to 3% with 0.3-second margins, measured against both microphones.
status: accepted
date: 2026-08-02
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, auto-editor, video-editing, dual-source]
scope: context
context: DavinciResolveScripts
supersedes: ADR-010
superseded_by:
---

# Cut silence at 3 percent for a hot camera microphone

## Context

ADR-010 pinned both routes to `audio:threshold=1%`, a number that had been tuned
against the OBS screen capture. The dual source route does not analyse that file:
it runs auto-editor on the camera recording, because the camera microphone is the
only audio that survives into the timeline.

The two microphones are not comparable. Measured on the AZ-900 recordings of
2026-08-02:

| source | mean volume | peak |
| --- | --- | --- |
| OBS capture (`.mkv`) | -32.9 dB | -2.0 dB |
| camera (`.MP4`) | -15.2 dB | 0.0 dB, clipping |

At 1% the camera's room tone never falls below the threshold, so auto-editor
returned three segments covering 99.7% of a 43-minute talk — the silence cut was
doing nothing at all on the route that needs it most.

Measured on the same recordings, with `--margin 0.3sec`:

| threshold | camera kept | OBS capture kept |
| --- | --- | --- |
| 1% | 99.7% | 69.3% |
| 3% | 66.2% | 61.5% |
| 5% | 64.1% | 54.2% |

3% is the knee of the camera curve: it is where the room tone finally falls below
the threshold, and going further buys almost nothing while eating into speech.

## Alternatives considered

- **Keep 1% and give the dual source route its own threshold** — Rejected. ADR-010
  is right that the setting belongs to the voice, and two numbers drift apart. The
  measurement shows 3% serves both microphones, so one number still works.
- **Normalise the camera audio before analysing it** — Rejected. It adds a full
  decode of a 17 GB file to every run and only moves the same threshold problem
  behind a second knob.

## Decision

- The silence cut is `--margin 0.3sec` with `--edit audio:threshold=3%` in both
  routes, restoring ADR-008's threshold with ADR-010's margin.
- The structure ADR-010 established is kept: `dual_source.py` holds
  `SILENCE_MARGIN` and `SILENCE_EDIT`, `auto_video_editor.py` keeps its literals,
  and a test asserts the two agree.

## Rationale

ADR-010 changed the number without measuring the camera, because the dual source
route had not been run end to end yet. The first real run exposed it. The margin
is unchanged, since nothing in the evidence pointed at it.

## Consequences

- The stable route now cuts a little more than before: 61.5% kept instead of
  69.3% on the same recording. That is the tuning ADR-008 shipped for months.
- ADR-010's numbers should not be quoted; its reasoning about keeping one shared
  constant still stands.

## Related

- [ADR-008: Tune silence detection to 3 percent with 0.2-second margins](008-tune-silence-detection-to-3-percent-with-0.2-second-margins.md)
- [ADR-010: Cut silence at 1 percent with 0.3-second margins](010-cut-silence-at-1-percent-with-0.3-second-margins.md)

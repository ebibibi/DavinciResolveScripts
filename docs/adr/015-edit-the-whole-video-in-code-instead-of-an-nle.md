---
type: adr
id: ADR-015
title: Edit the whole video in code instead of an NLE
decision: The advanced route builds one edit decision list from the transcript - highlights, chapter cards, emphasis telops, burned captions and generated sound effects - and renders it with a single FFmpeg command, with DaVinci Resolve out of the loop entirely.
status: accepted
date: 2026-08-04
deciders: [Masahiko Ebisuda, Claude]
tags: [ffmpeg, ass, libass, whisper, claude, telop, captions, sound-design, video-editing]
scope: context
context: DavinciResolveScripts
supersedes: ADR-006
superseded_by:
---

# Edit the whole video in code instead of an NLE

## Context

ADR-006 already removed Resolve from the advanced route, but it kept only two
treatments: copy the strongest moments to the opening and burn one takeaway
title. Everything else an editor does by hand - chapter titles, emphasis
telops, subtitles, sound effects - was still assumed to need a timeline
application.

That assumption was never tested. FFmpeg concatenates, libass draws four
independent styled layers in one pass, `sine` and `anoisesrc` synthesise the
sound effects, Whisper supplies the words, and Claude can choose what deserves
emphasis. The missing piece was never a rendering capability; it was a data
structure that says what the finished video contains.

## Alternatives considered

- **Go back to the Resolve API for titles and effects** — Rejected. ADR-006
  documents why that path failed repeatedly, and nothing about it has changed.
- **Add each treatment as its own pass over the video** — Rejected. Four
  sequential renders of a 45-minute recording cost hours and lose quality at
  every generation.
- **Let the AI emit FFmpeg commands directly** — Rejected. An invalid or unsafe
  command is undetectable until it runs, and the result cannot be reviewed
  before rendering.
- **Have the AI choose the sound effect positions too** — Rejected. A sound
  that does not coincide with a visible change is noise; cues are derived from
  the rendered structure instead.
- **Describe the finished video as one immutable edit plan and render it once**
  — Selected.

## Decision

`advanced_video_editor.py` is the advanced route, and the advanced launcher
points at it. The pipeline is:

1. Cut silence with auto-editor using the shared ADR-010 settings.
2. Transcribe the cut master, so every timestamp is on the edited body.
3. Ask Claude once, with a strict JSON schema, for the takeaway, the highlight
   segment indexes, the chapter boundaries and the emphasis telops.
4. Validate that answer against the transcript. Only segment indexes are
   trusted for timing; the AI may write display text but can never place an
   overlay where nobody was speaking. An index outside the transcript is
   dropped, never clamped.
5. Build captions from the transcript itself, split on sentence boundaries.
6. Derive sound cues from the timeline: a noise burst on every cut, a bell on
   every chapter card.
7. Write `overlays.ass` and `sound_effects.wav`, then render one FFmpeg command
   that concatenates the reel and the body, burns all four subtitle layers and
   mixes the effects under the narration with `amix=normalize=0`.
8. Save `edit_plan.json` describing every decision, including the resolved
   timeline.

Time in the plan always belongs to the cut master. `timeline.py` maps it to the
finished video, where a copied highlight makes one moment appear twice: an
overlay follows its words to both places, while a chapter card is restricted to
the body so it cannot announce a scene the viewer has not reached.

Every layer can be switched off individually in the `advanced_edit` section of
the config, and each has a deterministic fallback, so a missing Claude CLI
degrades the edit instead of failing it.

## Rationale

- The edit becomes a reviewable value. Reading a run means reading
  `edit_plan.json`; correcting one means editing it and rendering again.
- Grounding every overlay in a transcript index is what makes an AI editor
  safe: it can be wrong about emphasis, never about who said what and when.
- One render keeps a long recording to a single encode and one generation loss.
- Synthesised effects keep the repository free of binary assets and licences.
- The whole decision layer is pure Python and is tested without a video file.

## Consequences

- The advanced launcher no longer produces `highlight_plan.json` in
  `_highlight_output`; it produces `edit_plan.json` in `_edited_output`.
  `highlight_video.py` remains and still runs on its own for the older
  behaviour.
- Burned captions are a deliberate choice, not a soft subtitle track. A
  correction means a re-render.
- The takeaway title, telop and caption styles are now sized relative to the
  frame height, so 720p and 4K recordings look the same.
- The font must exist on the rendering machine; libass silently substitutes.
- ADR-010's silence numbers are now read from `dual_source.py` by this route as
  well, which is the drift #25 left behind.

## Related

- [ADR-006: Prepend copied highlights and a takeaway title without Resolve automation](006-highlight-first-rendering-without-resolve-automation.md)
- [ADR-007: Separate stable and advanced editing launchers](007-separate-stable-and-advanced-editing-launchers.md)
- [ADR-010: Cut silence at 1 percent with 0.3-second margins](010-cut-silence-at-1-percent-with-0.3-second-margins.md)

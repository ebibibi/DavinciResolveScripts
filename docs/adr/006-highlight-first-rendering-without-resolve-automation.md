---
type: adr
id: ADR-006
title: Prepend copied highlights and a takeaway title without Resolve automation
decision: Keep the proven auto-editor silence cut, copy one or more grounded highlights to the opening, render a large takeaway title with FFmpeg and ASS, and remove Resolve API editing from the default workflow.
status: accepted
date: 2026-07-20
deciders: [Masahiko Ebisu, Codex]
tags: [auto-editor, highlights, ffmpeg, ass, whisper, youtube, video-editing]
scope: context
context: DavinciResolveScripts
supersedes: ADR-005
superseded_by:
---

# Prepend copied highlights and a takeaway title without Resolve automation

## Context

Repeated attempts to automate Text+, Fusion titles, topic overlays, track placement,
and title duration through the DaVinci Resolve API did not create a dependable
time-saving workflow. The successful video
"Claude Fable Plans, GPT-5.6 Implements" showed a more valuable editing pattern:
show the strongest moments first and state the video's takeaway immediately.

The silence removal performed by auto-editor is already reliable and matches the
presenter's recording style. The failed part is the growing Resolve automation
layer, not the cut itself.

## Alternatives considered

- **Continue repairing Resolve API title automation** — Rejected because several
  independent API boundaries have failed in real use and the effort does not
  improve the opening hook.
- **Keep full-body AI emphasis titles from ADR-005** — Rejected as the default
  because it adds a second full render and many editorial decisions while leaving
  the highest-impact opening work unfinished.
- **Use one fixed demo at the opening** — Rejected because the useful unit is a
  highlight, not necessarily a demonstration, and longer videos can benefit from
  multiple moments.
- **Build the opening externally after the proven cut** — Selected because it is
  deterministic, testable without Resolve, and directly implements the observed
  success factors.

## Decision

The default workflow is:

1. Render a high-quality cut master with auto-editor using
   `audio:threshold=1%` and `--margin 0.5sec`.
2. Transcribe the cut master so all selected timestamps belong to the edited body.
3. Select one highlight for short videos, two for videos of at least 20 minutes,
   and three for videos of at least 45 minutes, subject to configured duration
   limits and manual overrides.
4. Copy those ranges to the beginning. Do not remove the original moments from
   the complete body.
5. Render one large, centered takeaway statement over the first seconds using ASS.
6. Concatenate the highlight reel and 100% of the cut master in one FFmpeg render.
7. Preserve the cut master, transcript, ASS file, and `highlight_plan.json`.

Claude CLI may select grounded segment indexes and the takeaway. If it is missing
or invalid, a deterministic transcript-based selector is used. Manual title and
range overrides bypass both Whisper and Claude.

The default PowerShell runner does not launch or control DaVinci Resolve. Resolve
remains available only for optional final review or manual correction.

## Rationale

- It automates the two opening treatments that produced a concrete improvement:
  visible highlights and a large statement of the video's point.
- Multiple highlights scale to long-form videos without turning the whole video
  into an automated overlay experiment.
- Copying instead of moving guarantees that the complete cut body is preserved.
- The cut-master timeline removes original-to-edited timestamp mapping.
- FFmpeg and ASS are deterministic and can be tested end to end on Linux and
  Windows without a running Resolve instance.

## Consequences

- The final MP4 is a single rendered artifact; corrections require updating the
  manifest/config and rerunning, or importing the cut master into Resolve.
- Whisper is required for fully automatic selection. Without it, the cut master
  remains usable and the manifest records the fallback reason.
- Claude is optional and never receives video or audio, only bounded transcript
  candidates.
- The legacy Resolve scripts stay in the repository at the pre-AI baseline but
  are no longer called by the default runner.

## Related

- [ADR-005: Render AI titles after the auto-editor cut](005-render-ai-titles-after-auto-editor.md)
- [Issue #17](https://github.com/ebibibi/DavinciResolveScripts/issues/17)
- [Auto-editor empty timeline KB](../kb/auto-editor-empty-timeline.md)

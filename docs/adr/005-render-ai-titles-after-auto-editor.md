---
type: adr
id: ADR-005
title: Render AI emphasis titles after the proven auto-editor cut
decision: Keep auto-editor silence cutting as the immutable core, render its result once, transcribe the cut video, and burn selected emphasis titles with FFmpeg and ASS before importing the candidate into Resolve.
status: accepted
date: 2026-07-18
deciders: [Masahiko Ebisu, Codex, Claude Fable]
tags: [auto-editor, whisper, ffmpeg, ass, davinci-resolve, video-editing]
scope: context
context: DavinciResolveScripts
supersedes: [ADR-001, ADR-003, ADR-004]
superseded_by:
---

# Render AI emphasis titles after the proven auto-editor cut

## Context

The silence-cutting workflow is complete, valuable, and matched by the presenter's recording style. The failed experiment was only the add-on that attempted to create and place AI-generated Text+ objects through the Resolve scripting API.

Real runs exposed V1 ripple, compound-clip conversion, unavailable font/style combinations, and unreliable Fusion title manipulation. Removing or weakening auto-editor would regress the workflow instead of isolating the failed add-on.

## Alternatives considered

- **Continue automating Resolve Text+** — Rejected because the failures are in the scripting boundary and repeat across track, duration, template, and font operations.
- **Map original Whisper timestamps through the cut list** — Rejected because frame rounding and margins create an unnecessary second time-axis implementation.
- **Render the cut video, transcribe it, and burn titles externally** — Selected because the transcript timestamps directly match the candidate video and the existing Whisper/FFmpeg assets can be reused.
- **Generate only an opening highlight** — Deferred until the full-body emphasis-title path works; it does not by itself satisfy the original add-on requirement.
- **Rebuild the long video in Remotion** — Rejected as excessive. Remotion remains an option for a short animated opening highlight later.

## Decision

Always run the existing auto-editor Resolve export first. Also render the same `audio:threshold=1%` and `0.5sec` margin result to a high-bitrate H.264 intermediate. If auto-editor reports an empty timeline, preserve the existing full-recording fallback.

Run Whisper again against the cut intermediate. Select a small number of grounded, high-impact statements with one structured Claude CLI call and a deterministic local fallback. Generate an ASS file using the cut-video timestamps and burn it with FFmpeg.

Import the resulting single candidate clip into the main Resolve timeline, followed by the existing ending. Keep the Resolve FCPXML, untitled cut intermediate, transcript, highlight JSON, and ASS file as escape hatches. If any post-cut stage fails, use the original multi-clip Resolve XML path without changing the proven cut behavior.

## Rationale

- The highest-value auto-editor behavior remains unchanged.
- Re-transcribing the cut video removes the source-to-edited time mapping problem.
- ASS rendering is deterministic and avoids Resolve Text+/Fusion scripting.
- The original FCPXML preserves detailed manual editability.
- Every new stage fails open to the existing Resolve workflow.

## Consequences

- Successful runs perform two video encodes. The first uses a 40 Mbps H.264 intermediate for compatibility with auto-editor 25.0.1; the second defaults to CRF 16 for the titled candidate.
- Burned titles are not editable in Resolve, so JSON, ASS, the untitled cut master, and FCPXML must be retained.
- The first implementation uses a horizontal-video ASS style and `HGPSoeiKakugothicUB`.
- A later opening-highlight phase can reuse the cut transcript and quality decisions.

## Related

- [ADR-001: Persistent topic overlays](001-persistent-topic-overlay.md)
- [ADR-003: Native Text+ template](003-use-native-text-plus-template.md)
- [ADR-004: Viewer-focused topic labels](004-generate-viewer-focused-topic-labels.md)
- [Auto-editor empty timeline KB](../kb/auto-editor-empty-timeline.md)

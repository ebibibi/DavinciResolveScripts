---
type: adr
id: ADR-017
title: Drop the template opening and append the end card after the ending clip
decision: Remove 01_EBI_CHAN_OP.mov from the main timeline of both templates, start the body at the timeline start, and have every Resolve route append EBI_CHAN_OUTRO.mp4 after 03_EBI_CHAN_IN.mov instead of baking it into the template.
status: accepted
date: 2026-09-26
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, template, opening, end-card, outro]
scope: context
context: DavinciResolveScripts
---

# Drop the template opening and append the end card after the ending clip

## Context

Both templates (`有償版用スクリプト/テンプレート.drp` and
`無料版用スクリプト/テンプレート.drp`) started the `main` timeline with the
opening clip `01_EBI_CHAN_OP.mov` on V1, with the `MasahikoEbisuda_MicrosoftMVP.mov`
overlay layered above it. The scripts looked for that clip by name and placed
the edited body right after it.

A different opening will be used from now on, and every video should end with
the new 20-second end card (`tools/eyecatch`, `EBI_CHAN_OUTRO.mp4`) after the
existing ending clip `03_EBI_CHAN_IN.mov`.

## Decision

- Remove only the `01_EBI_CHAN_OP.mov` timeline item from both templates
  (`tools/remove_timeline_clip.py`). The overlay, the BGM item and every other
  archive member are unchanged. The Media Pool entry stays, like the unused
  `02_EBI_CHAN_OP.mov` and `03_EBI_CHAN_IN.mov` entries already did.
- The routes keep honouring an opening clip if one is placed by hand; without
  one, the body starts at the timeline's start frame (`GetStartFrame()`, usually
  01:00:00:00), never at frame 0, which lies an hour before the timeline.
- The stable, dual-source and free routes append `03_EBI_CHAN_IN.mov` and then
  `EBI_CHAN_OUTRO.mp4`. The end card is looked for in the same OneDrive
  `!動画素材` folders as the ending clip, then in the copy bundled at
  `assets/EBI_CHAN_OUTRO.mp4` (`ending_media.py`). A missing end card is
  reported and skipped rather than failing an edit.

## Why the end card is not baked into the template

- **Its position depends on the body.** The template timeline is not replaced
  by the edit; the body is added to it. The stable and free routes append the
  body with `AppendToTimeline`, which adds after what is already on the track,
  and the dual-source route places it from the start frame with explicit record
  frames. A clip baked into the template would therefore land *before* the body
  (or be overwritten by it), never after it. The ending clip `03` is appended by
  the scripts for the same reason.
- **Paths stay portable.** A template item stores one absolute OneDrive path.
  The `!動画素材` folder name has changed before, and a baked item would simply
  go offline. The scripts try every known folder and fall back to the bundled
  copy, which `update_repository.ps1` keeps current before every run.

## Consequences

- Re-rendering the end card means refreshing `assets/EBI_CHAN_OUTRO.mp4`
  (see `tools/eyecatch/README.md`); a newer copy in OneDrive wins in the meantime.
- The bundled copy is re-encoded (H.264 CRF 20, AAC copied, about 10 MB) so the
  repository stays light to pull.
- The dual-source route places the end card's picture on V1 and its sound on
  A1; the ending clip keeps its earlier picture-only placement.
- The advanced (FFmpeg) route does not use the template or an ending clip and is
  unchanged.
- As with ADR-016, the structural check of the edited DRP does not replace an
  import in Resolve on the editing PC.

## Related

- [ADR-007: Separate stable and advanced editing launchers](007-separate-stable-and-advanced-editing-launchers.md)
- [ADR-016: Bundle editable title presets](016-bundle-editable-title-presets.md)
- [Issue #60](https://github.com/ebibibi/DavinciResolveScripts/issues/60)

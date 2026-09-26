---
type: adr
id: ADR-018
title: Import the generated clips into a Media Pool bin at run time
decision: Every Resolve route ensures an "EBI アイキャッチ" bin and imports the ten stingers and the end card into it (OneDrive first, bundled copy as fallback), instead of authoring Media Pool items inside the template DRP. The template BGM is removed.
status: accepted
date: 2026-09-26
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, media-pool, eyecatch, end-card, template]
scope: context
context: DavinciResolveScripts
---

# Import the generated clips into a Media Pool bin at run time

## Context

The ten eyecatch stingers and the end card from `tools/eyecatch` should be at
hand in every project the Resolve routes create. The owner also asked to remove
the BGM `Big 10 - TrackTribe.mp3` from the templates, following the opening
clip (ADR-017).

## Decision

- Remove the BGM timeline item and its Media Pool entry from both templates
  with `tools/remove_timeline_clip.py` and its `media-pool` option. The pool
  entry is only removed because nothing else refers to it (checked by DbId and
  media pool identity across every member, including decompressed blobs). The
  timeline's recorded length (`MediaExtents`) is updated to what is left.
- Bundle compact copies of the stingers in `assets/eyecatch/` next to the end
  card, and resolve every generated clip the same way: OneDrive `!動画素材`
  first, the bundled copy otherwise (`ending_media.find_material`).
- `media_pool_clips.ensure_generated_clips` runs in the stable, dual-source and
  free routes right after the Media Pool is available. It finds or creates the
  bin `EBI アイキャッチ` under the root, imports only the clips not already in
  it, restores the current folder, and reports and skips on any failure.

## Alternatives considered

- **Author new Media Pool items inside the DRP** — Rejected. A native item
  carries clip metadata, embedded audio descriptions, thumbnails and IDs that
  Resolve normally derives from the file itself; writing them by hand risks a
  project that imports wrongly, and would pin one absolute OneDrive path.
- **Import only the end card when it is used** — Rejected; the stingers are
  placed by hand, so they must be in the pool before editing starts.

## Consequences

- A run imports the end card twice: once into the bin and once into the current
  folder when it is appended after `03_EBI_CHAN_IN.mov`.
- Re-rendering a stinger means refreshing `assets/eyecatch/` too; a new variant
  also has to be added to `EYECATCH_VARIANTS` (a test compares it with
  `timeline.json`).
- The Resolve behaviour (bin creation, import into the bin) is covered with
  fakes only until it runs on the editing PC.

## Related

- [ADR-017: Drop the template opening and append the end card](017-drop-the-template-opening-and-append-the-end-card.md)
- [Issue #62](https://github.com/ebibibi/DavinciResolveScripts/issues/62)

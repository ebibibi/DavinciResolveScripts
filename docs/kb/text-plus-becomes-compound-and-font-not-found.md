---
type: kb
title: Text+ becomes a compound clip and reports Font Not Found
symptom: V2 overlays appear as `AI Topic ...` compound clips and Resolve displays `Font Not Found: HGPSoeiKakugothicUB Semibold`.
status: solved
date: 2026-07-16
updated: 2026-07-16
component: [DaVinci Resolve, Fusion TextPlus, Resolve Scripting API]
tags: [text-plus, compound-clip, font, video-track]
scope: context
context: DavinciResolveScripts
---

# Text+ becomes a compound clip and reports Font Not Found

## Symptoms

- Generated V2 clips are named `AI Topic ...` and open as compound clips instead of native Text+ items.
- The viewer displays `Font Not Found: HGPSoeiKakugothicUB Semibold`.
- Setting only the TextPlus `Font` input appears to succeed but still renders a missing-font warning.

## Environment

- DaVinci Resolve Studio with external Python scripting.
- A project imported from the bundled `テンプレート.drp`.
- Text+ titles appended to video track 2.

## Cause

Converting a temporary Text+ timeline item with `CreateCompoundClip()` creates a compound Media Pool asset. Appending that asset preserves the compound clip, not the original native Text+ timeline-item type.

TextPlus stores the font family and face style separately. Changing `Font` to `HGPSoeiKakugothicUB` while leaving the template's `Style` at `Semibold` makes Resolve search for the unavailable family/style combination `HGPSoeiKakugothicUB Semibold`.

## Resolution

1. Find the native Fusion Title generator named `テロップ` in the imported template project's Media Pool.
2. Append that Media Pool item directly with `trackIndex: 2` and `recordFrame`.
3. On the appended timeline item's TextPlus node, set `Style` to `Regular` before setting `Font` to `HGPSoeiKakugothicUB`.
4. Read both inputs back and require exact matches.
5. Verify `GetTrackTypeAndIndex()` returns video track 2. Delete the item with `ripple=False` if any validation fails.

Do not create a temporary timeline or call `CreateCompoundClip()` for this workflow.

## Lesson

A successful Fusion `SetInput("Font", ...)` call does not prove that the resulting font face exists. Validate both family and style. When a native generator already exists in the Media Pool, append it directly to preserve its timeline type.

## Related

- [ADR-003: Append the bundled native Text+ template directly to V2](../adr/003-use-native-text-plus-template.md)
- [GitHub Issue #9](https://github.com/ebibibi/DavinciResolveScripts/issues/9)

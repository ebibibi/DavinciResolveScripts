---
type: adr
id: ADR-002
title: Build Text+ assets off-timeline and append them explicitly to V2
decision: Create Text+ titles on temporary timelines, convert them to compound Media Pool assets, and append them to verified V2 positions.
status: superseded
date: 2026-07-16
deciders: [Masahiko Ebisu, Claude]
tags: [davinci-resolve, text-plus, timeline, video-track]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by: ADR-003
---

# Build Text+ assets off-timeline and append them explicitly to V2

## Context

`InsertFusionTitleIntoTimeline()` does not accept a track index. Locking V1 before calling it appeared plausible in API-level reasoning, but real Resolve execution still placed every generated Text+ on V1. The titles rippled the existing video and made the resulting timeline unusable. Retrying without locks made the destructive behavior certain.

The font setter also returned without verifying whether Resolve accepted `HGPSoeiKakugothicUB`.

## Alternatives considered

- **Keep the V1 lock workaround** — Rejected because real Resolve ignored it.
- **Insert on V1 and move the item afterward** — Rejected because the scripting API exposes track reads but no supported timeline-item move operation; V1 is already rippled before any recovery.
- **Import titles through FCPXML** — Rejected because it complicates Fusion title styling and editability.
- **Create Media Pool title assets and append with clip info** — Selected because `AppendToTimeline()` supports `trackIndex`, `recordFrame`, and an exact source duration.

## Decision

Never call title insertion APIs on the main timeline. Create each unique styled Text+ on a temporary timeline, verify its text and font, convert it to a compound clip, then append that Media Pool item to the main timeline with `trackIndex: 2`.

After append, read `GetTrackTypeAndIndex()`. If the item is not on video track 2, delete it without ripple and count the action as failed.

Read the TextPlus `Font` input back after setting it. The title asset is invalid unless the value exactly equals `HGPSoeiKakugothicUB`.

## Rationale

This isolates all potentially rippling title creation from the user's main timeline and uses the documented track-aware append path for final placement. Verification turns API deviations into explicit failures instead of damaged timelines.

## Consequences

- Temporary timelines and compound clips are created during processing; temporary timelines are deleted after placement.
- The Media Pool contains reusable compound title assets for the generated topics.
- If compound title creation is unsupported in a Resolve version, no title is added to the main timeline and the status reports failure.

## Related

- [ADR-001: Persistent topic overlays](001-persistent-topic-overlay.md)
- [ADR-003: Append the bundled native Text+ template directly to V2](003-use-native-text-plus-template.md)
- [GitHub Issue #7](https://github.com/ebibibi/DavinciResolveScripts/issues/7)

---
type: adr
id: ADR-003
title: Append the bundled native Text+ template directly to V2
decision: Reuse the native Text+ generator named `テロップ` from the bundled project template and append it directly to V2.
status: accepted
date: 2026-07-16
deciders: [Masahiko Ebisu, Claude]
tags: [davinci-resolve, text-plus, timeline, video-track, font]
scope: context
context: DavinciResolveScripts
supersedes: ADR-002
superseded_by:
---

# Append the bundled native Text+ template directly to V2

## Context

ADR-002 avoided V1 ripple damage by converting Text+ titles to compound clips before appending them to V2. Real Resolve output proved that this changed the user-visible timeline objects into compound clips named `AI Topic ...`, violating the requirement that every overlay remain a native, editable Text+ item.

The bundled `テンプレート.drp` already contains a native Fusion Title generator named `テロップ` in its Media Pool. The font warning also showed that changing only `Font` retained the Text+ template's `Semibold` style, creating the unavailable combination `HGPSoeiKakugothicUB Semibold`.

## Alternatives considered

- **Keep compound clips** — Rejected because the resulting timeline items are not Text+.
- **Insert Text+ directly on the main timeline** — Rejected because the API cannot select V2 and real runs rippled V1.
- **Import a separate DRB file containing Text+** — Unnecessary because the bundled project already provides the required native generator.
- **Append the bundled native Text+ Media Pool item** — Selected because `AppendToTimeline()` can target V2 while preserving the native Text+ composition.

## Decision

Find the Media Pool item named `テロップ` recursively after importing `テンプレート.drp`. Append that exact generator for every overlay with `trackIndex: 2` and `recordFrame`, then configure the appended timeline item's TextPlus node.

Set both `Style=Regular` and `Font=HGPSoeiKakugothicUB`, in that order. Read both values back and delete the appended item without ripple if either value differs or the item is not on V2.

Never create temporary timelines or compound clips for topic overlays.

## Rationale

The template generator is already deployable with the script, remains a native Text+ item in Resolve, and works with the track-aware append API. Explicitly selecting `Regular` prevents Resolve from looking for a nonexistent `HGPSoeiKakugothicUB Semibold` face.

## Consequences

- Topic overlays remain directly editable as Text+ on V2.
- The bundled project template must keep its native generator named `テロップ`.
- Missing templates, wrong tracks, missing TextPlus nodes, or rejected font/style combinations become explicit failures and invalid items are removed.

## Related

- [ADR-001: Persistent topic overlays](001-persistent-topic-overlay.md)
- [ADR-002: Build Text+ assets off-timeline](002-append-text-titles-to-v2.md)
- [GitHub Issue #9](https://github.com/ebibibi/DavinciResolveScripts/issues/9)

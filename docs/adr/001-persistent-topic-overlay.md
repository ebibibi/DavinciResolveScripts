---
type: adr
id: ADR-001
title: Use refreshed Text+ clips for persistent topic overlays
decision: Represent each transcript topic with consecutive short Text+ clips at the edge of the frame.
status: accepted
date: 2026-07-16
deciders: [Masahiko Ebisu, Claude]
tags: [davinci-resolve, whisper, text-plus, video-editing]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by:
---

# Use refreshed Text+ clips for persistent topic overlays

## Context

The previous AI-assisted edit generated brief hook and key-point titles. In real DaVinci Resolve use, those objects were unreliable and did not continuously tell viewers what the speaker was discussing.

The replacement must use the Whisper transcript, keep a short current-topic label visible near the edge of the frame, remain editable in Resolve, and report insertion failures clearly.

Resolve's scripting API exposes title insertion and timeline-item read methods, but no supported method for setting a title item's end frame or duration after insertion.

## Alternatives considered

- **One long Text+ item per topic** — Produces a clean timeline, but the API cannot reliably extend the inserted title to the next topic boundary.
- **Subtitle track generated from SRT** — Provides exact timing, but gives less control over placing and styling the topic label as a small edge overlay.
- **Burn the label into rendered video** — Guarantees appearance, but removes editability and adds a rendering dependency.
- **Consecutive short Text+ items** — Uses supported title insertion, stays editable, and avoids depending on title-duration mutation.

## Decision

Group Whisper segments into topic ranges and generate a short label for each range. Place that label at the upper-right edge as consecutive short Text+ items until the next topic begins.

The generated plan records both topic ranges and individual overlay actions. Runtime status records expected and successful insertion counts.

## Rationale

This is the most reliable option available through the supported scripting surface while preserving editability. It also lets topic analysis be unit-tested without DaVinci Resolve and makes partial insertion failures visible.

## Consequences

- The timeline contains more title items than the one-title-per-topic design.
- The refresh interval must stay at or below Resolve's configured default title duration to avoid visible gaps.
- Topic labels are heuristic and may need future improvement through an optional summarization backend.
- If Resolve later exposes supported title-duration editing, this decision should be revisited.

## Related

- [Automation experiments](../automation-experiments.md)
- [GitHub Issue #3](https://github.com/ebibibi/DavinciResolveScripts/issues/3)

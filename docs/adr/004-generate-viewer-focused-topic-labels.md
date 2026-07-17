---
status: accepted
date: 2026-07-17
decision: Generate viewer-focused topic statements with one structured Claude CLI call and use a local transcript fallback.
---

# Generate viewer-focused topic labels

## Context

The first real Resolve output displayed `いまの話題 / AI` over the presenter's face. The placement worked technically, but the label did not help a viewer understand the section. The existing algorithm counted repeated terms, so a broad word such as `AI` could outrank the actual point being explained.

## Decision

Send all transcript topic blocks to Claude CLI in one structured-output request. Ask for a concrete Japanese statement that tells the viewer what they can understand in that section. Reject short generic labels and claims unsupported by the transcript.

If Claude CLI is unavailable or the response is invalid, select the most informative transcript sentence locally, prioritizing methods, mechanisms, reasons, differences, and viewer outcomes.

Do not display a redundant `いまの話題` heading. Render only the useful statement, smaller and left-aligned near the upper-left safe edge so it does not cover the presenter in the standard screen-plus-camera layout.

## Consequences

- Topic text becomes semantic rather than keyword-based.
- One Claude request is added per edited video, not per topic.
- Editing remains available without Claude CLI through the deterministic fallback.
- The final position still requires a Resolve visual check because Fusion templates can have their own layout offsets.

## References

- [Issue #11](https://github.com/ebibibi/DavinciResolveScripts/issues/11)
- [ADR-001: Persistent topic overlays](001-persistent-topic-overlay.md)
- [ADR-003: Native Text+ template](003-use-native-text-plus-template.md)

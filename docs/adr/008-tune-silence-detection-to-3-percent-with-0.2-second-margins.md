---
type: adr
id: ADR-008
title: Tune silence detection to 3 percent with 0.2-second margins
decision: Use audio:threshold=3% and --margin 0.2sec for silence removal in both stable and advanced workflows.
status: accepted
date: 2026-07-21
deciders: [Masahiko Ebisu, Codex]
tags: [auto-editor, silence-removal, video-editing]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by:
---

# Tune silence detection to 3 percent with 0.2-second margins

## Context

Both Stable and Advanced routes share the same silence-removal behavior. Their
previous settings treated audio above 1% as speech and retained 0.5 seconds at
cut boundaries. The production preference is now a tighter cut with a higher
speech threshold.

## Alternatives considered

- **Keep 1% and 0.5 seconds** — Rejected because it preserves more low-level
  audio and more space around each spoken section than currently desired.
- **Tune only one route** — Rejected because the same recording should not get
  different basic silence cuts merely because Advanced features were selected.
- **Use 3% and 0.2 seconds in both routes** — Selected as the explicit production
  setting.

## Decision

Every normal auto-editor silence cut uses:

```text
--edit audio:threshold=3% --margin 0.2sec
```

The empty-timeline fallback remains `--edit none` and does not receive a margin.

## Rationale

A shared value prevents Stable and Advanced output from drifting before their
post-cut processing diverges. Keeping the values explicit in both Python entry
points and regression tests makes future changes deliberate.

## Consequences

- More low-level audio is classified as silence.
- Each retained speech section has 0.2 seconds of boundary context instead of
  0.5 seconds, producing tighter edits.
- Quiet speech is more likely to be removed and should be checked during the
  first real-video review after this change.

## Related

- [ADR-006: Prepend copied highlights and a takeaway title without Resolve automation](006-highlight-first-rendering-without-resolve-automation.md)
- [ADR-007: Separate stable and advanced editing launchers](007-separate-stable-and-advanced-editing-launchers.md)
- [Issue #21](https://github.com/ebibibi/DavinciResolveScripts/issues/21)

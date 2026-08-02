---
type: adr
id: ADR-010
title: Cut silence at 1 percent with 0.3-second margins
decision: Use a 1% audio threshold and 0.3-second margins, and keep the number in one place both routes read.
status: accepted
date: 2026-08-02
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, auto-editor, video-editing]
scope: context
context: DavinciResolveScripts
supersedes: ADR-008
superseded_by:
---

# Cut silence at 1 percent with 0.3-second margins

## Context

ADR-008 recorded a 3% threshold with 0.2-second margins. On 2026-07-26 the
stable editor was retuned to `audio:threshold=1%` and `--margin 0.3sec`, but
neither the ADR nor the test that pins those numbers was updated, so the test
suite has been failing on `main` since that commit and the ADR has been stating
the opposite of what runs.

The dual source route, written later against the ADR, picked up the old 3% and
0.2 seconds — the two routes were cutting the same voice differently.

## Alternatives considered

- **Return the code to 3% and 0.2 seconds** — Rejected. The retune was a
  deliberate reaction to real recordings; the document was what fell behind.
- **Let each route carry its own numbers** — Rejected. The setting belongs to
  the voice and the microphone, not to the route, so drift between them is a
  bug either way.

## Decision

- The silence cut is `--margin 0.3sec` with `--edit audio:threshold=1%`.
- `dual_source.py` holds `SILENCE_MARGIN` and `SILENCE_EDIT`, which the dual
  source editor uses.
- `auto_video_editor.py` keeps its literals, because it stays independent by
  design, and a test reads the numbers out of it and asserts the shared
  constants match. Retuning one route now fails the suite until the other
  follows.

## Rationale

A test that compares the two files catches drift without making the protected
stable editor import anything, which keeps ADR-007 intact.

## Consequences

- Changing the tuning means changing both places in the same commit.
- ADR-008 is superseded and its numbers should not be quoted.

## Related

- [ADR-008: Tune silence detection to 3 percent with 0.2-second margins](008-tune-silence-detection-to-3-percent-with-0.2-second-margins.md)
- [ADR-009: Give dual source editing its own script and launcher](009-give-dual-source-editing-its-own-script-and-launcher.md)

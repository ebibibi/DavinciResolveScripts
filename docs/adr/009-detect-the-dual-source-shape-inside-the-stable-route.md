---
type: adr
id: ADR-009
title: Detect the dual source shape inside the stable route
decision: Let the shape of the recording folder select the dual source route, instead of adding a third launcher or a configuration flag.
status: accepted
date: 2026-08-02
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, auto-editor, video-editing, stability]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by:
---

# Detect the dual source shape inside the stable route

## Context

OBS now records each lecture as a folder holding two files: the PowerPoint
capture as an `.mkv` and the green screen camera as an `.mp4`. Both belong on
the same timeline, on V1 and V2, cut at the same frames.

ADR-007 protects `run_auto_video_editor.ps1` as the route whose output does not
change. The dual source treatment has to reach that route, because it is the
routine production edit and not an experiment, without putting older single file
recordings at risk.

## Alternatives considered

- **A third launcher** — Rejected because the choice would have to be made
  before every recording, while the recording folder already states which shape
  it is. Two shortcuts that both mean "just edit this" invite the wrong click.
- **A configuration flag** — Rejected for the reason ADR-007 gives: a flag
  persists silently between recordings, so the behavior stops being visible at
  launch time.
- **Detect the shape of the input** — Selected. A subfolder holding exactly one
  `.mkv` and one `.mp4` is unambiguous, and it is the same fact a human uses to
  decide.

## Decision

- `auto_video_editor.py` looks for the newest subfolder of the recording folder
  that holds exactly one `.mkv` and one `.mp4`.
- If it finds one, it builds the dual source timeline and says so in the log.
- If it does not, it runs the established single source path unchanged, and says
  that too.
- Anything ambiguous — two camera files, no camera file, loose files in the
  recording folder — is not a pair, so it falls back rather than guessing.

## Rationale

The input decides, so a recording made the old way still edits exactly the way
it did before, bit for bit. Nothing has to be remembered between runs, and the
log states which route ran, so a surprising result is one line away from being
explained.

## Consequences

- A folder that accidentally holds one `.mkv` and one `.mp4` will be treated as
  a lecture pair. The log names the folder and both files before any work
  starts.
- Splitting a camera recording into two `.mp4` files makes the folder stop being
  a pair. That is deliberate: joining split camera files is a separate decision,
  not something to infer.
- The stable launcher now owns two code paths, so changes to shared helpers have
  to be verified against both.

## Related

- [ADR-007: Separate stable and advanced editing launchers](007-separate-stable-and-advanced-editing-launchers.md)
- [Dual source editing plan](../dual-source-editing-plan.md)

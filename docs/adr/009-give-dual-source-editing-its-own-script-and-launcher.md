---
type: adr
id: ADR-009
title: Give dual source editing its own script and launcher
decision: Run the slides plus camera edit from its own Python entry point, started by its own launcher that passes the relative script name explicitly.
status: accepted
date: 2026-08-02
deciders: [Masahiko Ebisuda, Claude]
tags: [davinci-resolve, auto-editor, video-editing, stability]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by:
---

# Give dual source editing its own script and launcher

## Context

OBS now records each lecture as a folder holding two files: the PowerPoint
capture as an `.mkv` and the green screen camera as an `.mp4`. Both belong on
the same timeline, on V1 and V2, cut at the same frames.

ADR-007 already established the shape this repository uses for a distinct
workflow: one launcher, naming one Python entry point, chosen deliberately at
launch time. The dual source edit is a third workflow of that kind.

## Alternatives considered

- **Detect the folder shape inside the stable editor** — Rejected. It makes the
  protected entry point own two workflows, so every later change has to be
  argued against both, and the same shortcut would mean two different things
  depending on what is on disk.
- **A configuration flag** — Rejected for the reason ADR-007 gives: a flag
  persists silently between recordings, so the behavior stops being visible at
  launch time.
- **Its own script and launcher** — Selected. It matches the advanced route,
  keeps the stable editor byte for byte unchanged, and makes the choice visible
  as a third desktop shortcut.

## Decision

- `dual_source_video_editor.py` is the entry point for the slides plus camera
  edit. It owns the folder detection, the audio sync, the shared cut list and
  the camera placement.
- `run_dual_source_video_editor.ps1` starts it with the relative script name
  passed explicitly, `$Arguments = @("dual_source_video_editor.py")`, exactly as
  the advanced launcher names `highlight_video.py`. Extra arguments given to the
  launcher are forwarded, so a specific folder can be edited on demand.
- `auto_video_editor.py` and `run_auto_video_editor.ps1` are untouched. The
  stable route neither detects nor mentions the dual source case.
- The Resolve connection and template bootstrap the new entry point needs live
  in `resolve_session.py`. The stable editor deliberately keeps its own copy, so
  changing one cannot move the other.

## Rationale

Three named routes are easier to reason about than two routes where one changes
meaning based on the contents of a folder. A run can be explained by which
shortcut was clicked, without asking what was on disk at the time.

## Consequences

- The dual source script refuses to run when the folder is not a pair, and says
  which launcher to use instead, rather than quietly falling back.
- `resolve_session.py` and the stable editor hold similar bootstrap code. That
  duplication is the price of the stability boundary and is intentional.
- `create_desktop_shortcut.ps1` now creates three shortcuts.

## Related

- [ADR-007: Separate stable and advanced editing launchers](007-separate-stable-and-advanced-editing-launchers.md)
- [Dual source editing plan](../dual-source-editing-plan.md)

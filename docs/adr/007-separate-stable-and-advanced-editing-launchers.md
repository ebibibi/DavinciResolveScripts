---
type: adr
id: ADR-007
title: Separate stable and advanced editing launchers
decision: Keep the familiar runner on the proven Resolve workflow and expose experimental editing through a separately named advanced runner.
status: accepted
date: 2026-07-21
deciders: [Masahiko Ebisu, Codex]
tags: [davinci-resolve, auto-editor, powershell, stability, video-editing]
scope: context
context: DavinciResolveScripts
supersedes:
superseded_by:
---

# Separate stable and advanced editing launchers

## Context

Some recordings should receive only the long-running production treatment:
auto-editor silence removal followed by timeline creation from the DaVinci
Resolve template. Other recordings are suitable for the actively developed
highlight-first pipeline and future experiments.

Using one runner for both meanings made the result depend on whichever workflow
was most recently promoted to the repository default. That is unsafe for routine
videos where “do nothing extra” is an explicit editorial requirement.

## Alternatives considered

- **Add a prompt to one launcher** — Rejected because unattended use becomes
  harder and a mistaken selection can change the output.
- **Use one configuration flag** — Rejected because the selected behavior is
  less visible at launch time and can persist accidentally between recordings.
- **Make Advanced the unqualified default** — Rejected because development work
  must not silently replace the proven production behavior.
- **Provide two explicit launchers** — Selected because the choice is visible,
  scriptable, and easy to represent as two desktop shortcuts.

## Decision

- `run_auto_video_editor.ps1` is the stable route. It calls
  `auto_video_editor.py`, which performs silence removal and Resolve template
  timeline creation.
- `run_advanced_auto_video_editor.ps1` is the advanced route. It calls
  `highlight_video.py`, which owns highlight-first rendering and future
  experiments.
- `create_desktop_shortcut.ps1` creates clearly labeled Stable and Advanced
  shortcuts.
- Advanced development must not alter the stable launcher's target or introduce
  optional enhancements into the stable Python entry point.

## Rationale

Keeping the familiar filename stable favors predictable production behavior.
The explicit Advanced label creates a deliberate opt-in boundary around changing
features. Separate entry points also make routing testable without launching
DaVinci Resolve or processing a video.

## Consequences

- Users choose the route before each recording instead of relying on a mutable
  repository-wide default.
- The two pipelines may duplicate a small amount of launcher setup code.
- Improvements that genuinely belong to both routes must be applied deliberately
  and verified against each route.
- Existing users who launch `run_auto_video_editor.ps1` get the established
  Resolve behavior again.

## Related

- [ADR-006: Prepend copied highlights and a takeaway title without Resolve automation](006-highlight-first-rendering-without-resolve-automation.md)
- [Issue #19](https://github.com/ebibibi/DavinciResolveScripts/issues/19)

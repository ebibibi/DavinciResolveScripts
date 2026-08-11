---
type: adr
id: ADR-011
title: Configure silence settings per recording environment
decision: Read one ignored repository-root config.json in every auto-editor workflow while retaining the prior values as defaults.
status: accepted
date: 2026-08-11
deciders: [Masahiko Ebisuda, Codex]
tags: [davinci-resolve, auto-editor, configuration, video-editing]
scope: context
context: DavinciResolveScripts
supersedes: ADR-010
superseded_by:
---

# Configure silence settings per recording environment

## Context

The microphone, room noise, and recording level vary by environment. A single
hard-coded threshold and margin therefore cannot remain correct everywhere.
The values were also duplicated across editing routes, making them easy to
retune inconsistently.

## Alternatives considered

- **Keep fixed values in Python** — Rejected because every environment change
  requires a code edit and risks route drift.
- **Keep one config beside each script** — Rejected because duplicated local
  files can disagree even though all routes process recordings from the same
  environment.
- **Use command-line flags only** — Rejected as the primary interface because
  desktop shortcuts should retain the machine's tuning without extra arguments.

## Decision

- A Git-ignored `config.json` at the repository root is the environment-local
  source of truth.
- `config.example.json` documents `auto_editor.threshold_percent` and
  `auto_editor.margin_seconds`.
- Stable, dual-source, advanced, and free workflows all use the shared loader.
- Missing local configuration retains ADR-010's 1% threshold and 0.3-second
  margin for backward compatibility.
- Invalid values fail clearly rather than silently falling back.

## Rationale

One file makes per-machine tuning easy and prevents different launchers on the
same machine from cutting the same recording differently. Keeping the old
values as defaults avoids changing output for existing users.

## Consequences

- Users copy `config.example.json` to `config.json` once per environment.
- The stable entry point now imports the small shared configuration module;
  editing behavior remains independent beyond those two settings.
- The advanced launcher's older script-local config files remain fallback
  inputs for compatibility, but the repository-root file takes precedence.

## Related

- [ADR-010: Cut silence at 1 percent with 0.3-second margins](010-cut-silence-at-1-percent-with-0.3-second-margins.md)
- [Issue #31](https://github.com/ebibibi/DavinciResolveScripts/issues/31)

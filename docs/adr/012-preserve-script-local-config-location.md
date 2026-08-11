---
type: adr
id: ADR-012
title: Preserve the existing paid-script configuration location
decision: Keep 有償版用スクリプト/config.json as the environment-local source of truth while all workflows share its auto-editor settings.
status: accepted
date: 2026-08-11
deciders: [Masahiko Ebisuda, Codex]
tags: [davinci-resolve, auto-editor, configuration, compatibility]
scope: context
context: DavinciResolveScripts
supersedes: ADR-011
superseded_by:
---

# Preserve the existing paid-script configuration location

## Context

ADR-011 correctly centralized threshold and margin parsing, but moved the local
file from `有償版用スクリプト/config.json` to the repository root. Existing
Windows environments already maintain the script-local file, so moving it
creates unnecessary migration and makes the established setting appear ignored.

## Alternatives considered

- **Require migration to a root config** — Rejected because there is no benefit
  large enough to justify breaking an existing working convention.
- **Read both files with precedence rules** — Rejected because two active files
  recreate the ambiguity and drift that shared configuration is meant to remove.
- **Preserve the existing location as the only source** — Accepted because it
  keeps every installed environment working without migration.

## Decision

- `有償版用スクリプト/config.json` remains the environment-local source of
  truth and `config.example.json` remains beside it.
- The shared loader used by stable, dual-source, advanced, and free workflows
  points to that file.
- Existing `config.local.json` support remains an advanced-workflow compatibility
  fallback for its non-auto-editor settings.

## Consequences

- Existing users do not move or recreate their configuration.
- The free workflow reads its silence settings from the paid-script config;
  this is intentional so one environment has one tuning.
- ADR-011's root-location decision must not be followed.

## Related

- [ADR-011: Configure silence settings per recording environment](011-configure-silence-settings-per-environment.md)
- [Issue #33](https://github.com/ebibibi/DavinciResolveScripts/issues/33)

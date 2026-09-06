---
type: kb
title: EBI title reports No frame available for MediaOut1
symptom: A title dragged onto the timeline displays No frame available for MediaOut1 instead of text.
status: open
date: 2026-09-06
updated: 2026-09-06
component: [Fusion, title presets, DRP]
tags: [titles, mediaout, macro, output]
scope: context
context: DavinciResolveScripts
---

# EBI title reports No frame available for MediaOut1

The user reported this error after the twelve EBI titles were shipped in PR #38.
The DRP graph declared the macro output as `MainOutput1`, but the hand-authored
MediaOut connection referred to `Output`. The original graph test asserted the
wrong literal instead of checking that the requested port existed in the macro.

The builder now references the declared `MainOutput1`, and regression tests check
both newly generated graphs and the actual compositions extracted from the
shipped DRP. This corrects a concrete graph inconsistency. It does **not** prove
that it was the only cause of the user's rendering error: Resolve application
validation remains pending.

## Existing clips

Updating the DRP does not modify titles already in a project. With the affected
project and timeline open, run from the updated repository:

```powershell
& ".\有償版用スクリプト\repair_title_outputs.ps1"
```

The script looks only for `EBI_` title clips on the **current timeline** with the
bundled macro signature and an unconnected MediaOut input. It first exports a
project backup under `Documents/ResolveTitleRepair`. It then connects that input
to `Template.FindMainOutput(1)` using live Fusion objects, rather than guessing a
serialized port alias. It does not recreate clips or edit text, timing, position,
or styles. Each connection change is an undo step; the resulting project is saved.

`--dry-run` reports candidates without a backup or edit. Existing connected
outputs, other footage, other timelines and Media Pool prototypes are not changed.
If a title is already connected but still fails to render, this repair will skip
it; inspect the upstream node, font and frame range separately.

For one clip, the equivalent manual check is to open its Fusion page and connect
the output of `Template` to the yellow image input of `MediaOut1`. Save the project
before working on it. If that does not restore the image, collect the Fusion node
layout and console error before making additional changes.

## Validation

Two regression tests failed against the original graph and pass with the changed
port reference. Automated repair tests cover backup failure, dry run, existing
backup preservation, skipping footage/connected outputs, and connection failure.
The full suite has 189 passing tests. No Resolve GUI or render test was available;
keep this KB and issue #37 open until the user confirms the result.

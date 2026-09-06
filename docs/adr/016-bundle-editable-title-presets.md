---
type: adr
id: ADR-016
title: Bundle original Fusion titles in the existing project and Effects Library
decision: Add twelve static, editable title presets with reproducible source graphs and non-destructive user installation.
status: accepted
date: 2026-09-06
tags: [davinci-resolve, fusion, titles, templates]
scope: context
context: DavinciResolveScripts
---

# Bundle original Fusion titles in the project and Effects Library

The existing project supplies one reusable title. The requested improvement is
an assortment that is easy to select and edit in the established Resolve
workflow. It does not require automatic decisions about where to place titles.

Use twelve original static Fusion macros, with a single preset catalog as the
source for the project generators and Effects Library `.setting` files. Expose
text, typography, whole-layout position/scale and banner controls. Preserve the
original project timeline and original title. Install presets before the stable
and dual-source launchers connect to Resolve, preserving local customizations
using the last-installed file hashes.

Downloading a large third-party pack would introduce redistribution terms,
fonts and plugin dependencies. Effects-Library-only installation would miss the
requested project-template assets. A runtime title-generation stage would add
new timeline/API failure modes to the established editing routes. The chosen
approach ships assets and does not add timeline placement automation.

The tradeoff is that adding the generator records offline uses the bundled
Resolve 20.2.1 DRP format rather than an official archive-authoring API. The
builder checks the known container shape and preserves all unrelated archive
members. Structural validation is not a substitute for importing and rendering
in Resolve; that application-level check remains outstanding until the editing
PC is available. The assets can independently be installed as `.setting` files.

This does not supersede the Advanced route's FFmpeg architecture. See the
[title library guide](../../title_presets/README.md) and [issue #37](https://github.com/ebibibi/DavinciResolveScripts/issues/37).

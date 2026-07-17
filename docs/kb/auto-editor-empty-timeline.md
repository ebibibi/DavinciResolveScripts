---
type: kb
title: auto-editor reports an empty timeline
symptom: auto-editor exits before Resolve XML export with `Timeline is empty, nothing to do.`
status: solved
date: 2026-07-17
updated: 2026-07-17
component: [DavinciResolveScripts, auto-editor, DaVinci Resolve]
tags: [auto-editor, audio, silence, fcpxml, fallback]
scope: context
context: DavinciResolveScripts
---

# auto-editor reports an empty timeline

## Symptom

The normal command fails before the Whisper and topic-overlay stages:

```text
auto-editor recording.mkv --margin 0.5sec --edit audio:threshold=1% --export resolve
Error! Timeline is empty, nothing to do.
```

## Cause

The audio edit expression returned no loud sections. This can happen when all audio is below the configured threshold or when the expected audio stream cannot be analyzed. auto-editor then has no timeline ranges to export.

## Resolution

Detect only the `Timeline is empty` error and retry the same source with:

```text
auto-editor recording.mkv --edit none --export resolve
```

In auto-editor 25.0.1, `--edit none` marks the complete source as loud and produces a Resolve FCPXML without removing any section. The rest of the pipeline can then continue. Unrelated errors must still stop safely.

The fallback was verified against auto-editor 25.0.1 with a generated silent MP4; it produced `silent_ALTERED.fcpxml`.

## Consequences

- The recording remains usable and the automation proceeds to Resolve and Whisper.
- Silence is not removed for that recording, so manual trimming may still be needed.
- If the recording truly has no usable speech, Whisper can still return an empty transcript and topic overlays will be skipped honestly.

## Related

- [GitHub Issue #13](https://github.com/ebibibi/DavinciResolveScripts/issues/13)

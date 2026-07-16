---
type: kb
title: Remote Whisper JSON is downloaded but not detected
symptom: Remote Whisper succeeds and SCP downloads a JSON file, but AI assistance reports that no matching transcript was found.
status: solved
date: 2026-07-16
updated: 2026-07-16
component: [DavinciResolveScripts, OpenAI Whisper, SSH]
tags: [whisper, transcript, filename, windows, ssh]
scope: context
context: DavinciResolveScripts
---

# Remote Whisper JSON is downloaded but not detected

## Symptom

The log shows a successful remote Whisper command and SCP download, followed by:

```text
JSON was downloaded, but it could not be detected as a transcript JSON.
AI assistance was skipped because transcription failed.
```

The observed filename pattern was:

```text
Source:          2026-07-16 11-22-24.mkv
Extracted audio: 2026-07-16_11-22-24.whisper_audio.m4a
Whisper JSON:    2026-07-16_11-22-24.whisper_audio.json
```

## Environment

- Windows runs the DaVinci Resolve automation script.
- Audio is extracted locally and sent over SSH to a remote Whisper host.
- The remote filename is sanitized before upload.

## Cause

Transcript detection compared the raw source stem, which contained spaces, with the sanitized remote filename, which contained underscores and the `.whisper_audio` suffix. The names referred to the same source but did not pass the substring check.

## Resolution

Canonicalize both stems with the same remote-name sanitizer, accept only the exact source stem or its recognized `.whisper_audio` variant, and verify that the JSON object contains a `segments` array.

Regression tests must cover:

- spaces converted to underscores;
- the `.whisper_audio` suffix;
- rejection of a different source filename;
- rejection of JSON without Whisper segments.

## Prevention

Whenever an intermediate media file changes the basename, define the naming contract once and reuse it in both producer and consumer code. Do not solve this by accepting the newest arbitrary JSON; source isolation and content validation must remain in place.

## Related

- [GitHub Issue #5](https://github.com/ebibibi/DavinciResolveScripts/issues/5)
- [Persistent topic overlay ADR](../adr/001-persistent-topic-overlay.md)

# Knowledge Base

- [Remote Whisper JSON is downloaded but not detected](remote-whisper-json-not-detected.md) — AI assistance is skipped after a successful remote transcription because the returned filename differs from the source video stem. (2026-07-16)
- [Text+ becomes a compound clip and reports Font Not Found](text-plus-becomes-compound-and-font-not-found.md) — Append the native template directly and validate both font family and style. (solved, 2026-07-16)
- [auto-editor reports an empty timeline](auto-editor-empty-timeline.md) — Retry Resolve export with `--edit none` and keep the full recording. (solved, 2026-07-17)
- [The advanced run looks frozen and plays a video by itself](advanced-run-looks-frozen.md) — Stream child output into a stage reporter and stop auto-editor from opening the player. (solved, 2026-07-26)
- [Camera clips land 64 seconds away from the cut](camera-clips-land-64-seconds-off.md) — AppendToTimeline reads startFrame against the clip's start timecode, so a camera stamped with the time of day places every cut elsewhere. (solved, 2026-08-02)

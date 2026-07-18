# Architecture Decision Records

- [ADR-001: Use refreshed Text+ clips for persistent topic overlays](001-persistent-topic-overlay.md) — Keep the current topic visible by placing short, consecutive editable titles. (superseded, 2026-07-16)
- [ADR-002: Build Text+ assets off-timeline and append them explicitly to V2](002-append-text-titles-to-v2.md) — Compound clips prevented V1 ripple but did not remain native Text+. (superseded, 2026-07-16)
- [ADR-003: Append the bundled native Text+ template directly to V2](003-use-native-text-plus-template.md) — Reuse `テロップ`, verify V2, and require `HGPSoeiKakugothicUB Regular`. (superseded, 2026-07-16)
- [ADR-004: Generate viewer-focused topic labels](004-generate-viewer-focused-topic-labels.md) — Use one structured Claude CLI request and a deterministic local fallback. (superseded, 2026-07-17)
- [ADR-005: Render AI titles after the auto-editor cut](005-render-ai-titles-after-auto-editor.md) — Preserve the proven silence cut and move AI title rendering to the cut video's own timeline. (accepted, 2026-07-18)

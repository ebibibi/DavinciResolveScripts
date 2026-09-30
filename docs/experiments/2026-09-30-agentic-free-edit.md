# 2026-09-30 first agentic free-form edit

One real recording (46:40, 1080p60, face-to-camera talk, no screen share) edited end to end by
`opus_free_edit/run.sh` with `claude-opus-5-5`, then uploaded as a private video.

## Result

- Final: 32:21 at 1080p30, -14.0 LUFS, A/V difference 3 ms, CRF 19 (about 2.5 GB)
- Structure chosen by the agent: 22 s cold open from the strongest statements, stinger, 12 chapters,
  end card. Stingers only at the five act changes, not before every chapter.
- 350 joins in the body: about 11 min of pauses removed, about 4 min of retakes and one 75 s
  interruption removed; a claim the agent could not verify was cut with the interruption.
- Added: chapter cards and a persistent chapter tag, 14 information panels, 24 lower thirds,
  alternating 1.2x punch-in to hide jump cuts, voice processing, corrected captions (about 60
  product-name fixes), thumbnail, title, description with chapters and official references.
- Two preview review passes found and fixed five visual/audio defects before the final render.

## Cost

| stage | wall time |
|---|---|
| prepare (proxy 10 min, Whisper 4 min) | 14.9 min |
| agent (API time 18.1 min, the rest is rendering) | 83.9 min |
| upload | 2.7 min |
| total | 101.5 min |

| model | input | cache write | cache read | output | API-equivalent USD |
|---|---:|---:|---:|---:|---:|
| claude-opus-5-5 | 198 | 266,382 | 18,151,907 | 105,253 | 7.87 |

114 turns, 113 tool calls. Billed to the subscription; the USD figure is for scale only.

## What the agent found mechanical (candidates for `prepare.sh`)

- Pause removal with -35 dB silences shrunk where the edges carry weak speech (> -50 dB within 0.45 s);
  the plain -35 dB map cut into word onsets for a quiet voice (-38 LUFS body).
- Whisper hallucination removal in long silences and a shared product-name caption dictionary.
- Caption retiming against the EDL, punch-in alternation rules, chapter tags and timestamps.
- Split parallel render by frame-accurate parts, concat, two-pass loudnorm; pad asset audio to the
  video length.
- Retake candidates (the same phrase repeated within seconds) can be proposed by rule; the decision
  stays with the model.

## Harness follow-ups

- Run the proxy render in parallel with Whisper (the proxy took 10 of the 15 preparation minutes).
- Tune the silence map per recording from the measured noise floor.

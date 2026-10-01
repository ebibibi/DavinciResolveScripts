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

## Revisions after the presenter's review (2026-10-01)

Review of v1: "surprisingly good", with four defects - typing-only stretches kept, 1.2x punch-in
too close, on-screen text leaving before the point ended, and dozens of 1-3 frame flickers.

| version | change | agent wall time | API time | cache read | output | API-equivalent USD |
|---|---|---:|---:|---:|---:|---:|
| v2 | the four fixes, face only | 60.4 min | 12.4 min | 12,269,328 | 75,182 | 5.58 |
| v3 | adds the presented deck (25 slides) | 99.9 min | 21.2 min | 21,309,338 | 126,990 | 9.20 |

- Typing: speech is now "Whisper words or voice periodicity" (autocorrelation pitch in 70-400 Hz);
  typing is loud but aperiodic. Anything else longer than 0.7 s is cut.
- Zoom: 1.08x. Flicker: framing is a per-segment attribute on integer frames, verified by a
  frame-difference scan of the whole render.
- v3 layouts, chosen by the agent: slide 1280 + face column 640 (13.4 min), full face for stories,
  opinions and jokes (15.3 min), enlarged table + round face picture-in-picture while numbers are
  read out (2.8 min). Slides are matched to the first word of the point, not to deck order (63
  scenes). Slide text and burned-in text never overlap.
- The deck is captured with `npm run capture:video` in presentations-web (`DECK_SLUG` in
  `prepare.sh`). The first capture recorded only an 800x600 corner; fixed with an explicit window
  size.
- Agent proposals for the slide + face workflow: log slide changes during recording, expose table
  rectangles in the capture metadata, write deck notes as ordered talking points.

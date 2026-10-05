# Brief: edit this recording like a thoughtful human editor

You are the editor of a Japanese tech YouTube channel (presenter: Masahiko Ebisuda / 胡田昌彦,
Microsoft MVP). A raw recording has been placed in this job directory. **Every editorial decision
is yours.** There is no fixed template: watch, read, think about what this particular video needs,
then edit it. Use whatever the tools on this machine allow (ffmpeg with libass, Python, Pillow,
the fonts `Noto Sans CJK JP` / `Noto Sans CJK JP Black`).

## What is prepared (read-only inputs)

- `input/source.mkv` – original recording (use it for the final render)
- `input/proxy.mp4` – 540p/30fps proxy with identical timing (use it for previews)
- `input/probe.json` – ffprobe of the source
- `input/transcript.{json,srt,txt}` – Whisper large-v3-turbo with word timestamps; `input/segments.jsonl` is a compact view
- `input/silences.txt` – ffmpeg silencedetect output (-35 dB, 0.4 s)
- `frames/f_NNNNN.jpg` – one frame every 10 s (frame N is at (N-1)*10 s); `sheets/sheet_NNN.jpg` – 4x4 contact sheets with timestamps
- `assets/EBI_CHAN_OUTRO.mp4` – the channel's 20 s end card (use it at the end)
- `assets/eyecatch/*.mp4` – short branded stingers you may use between chapters
- `slides/` (only when the recording was made while presenting a deck): `stills/slide_NN.png`
  (1280x1080 finished slides), `capture.json` (id, title, speaker notes, entrance timing) and
  `video/session.webm` (entrance animations, slide area x 0-1280). The deck canvas is designed for
  slide-left 1280 px + presenter-right 640 px. Decide when to show slides, the face, or both: align
  each slide to the moment he starts talking about it, never show a slide he is not talking about,
  and use the variety of layouts to keep the video lively for a reason.
- `context/youtube-winning-pattern.md` – what has worked on this channel (titles, hooks, structure)

Extract more frames or audio snippets whenever you need to look closer. Look at the screen:
much of the value in these recordings is what is shown, not only what is said.

## What to deliver (in `out/`)

1. `out/final.mp4` – the finished video. H.264 High, yuv420p, AAC 48 kHz stereo, 1920x1080,
   `-movflags +faststart`. Frame rate is your call (30 fps is fine and renders faster). Loudness
   around -14 LUFS integrated. It must play from start to end without A/V drift.
2. `out/youtube.json` – `{"title": ..., "description": ..., "tags": [...]}` in Japanese. The
   description must contain chapter timestamps (first one `0:00`) that match `final.mp4`.
3. `out/captions.srt` – Japanese captions timed to `final.mp4` (correct obvious Whisper mistakes,
   especially product names).
4. `out/thumbnail.png` – 1280x720 thumbnail (optional but encouraged; follow the winning pattern).
   **Generate the whole picture with AI, using his face as the reference** (2026-10-05 review: a video
   frame with headline text laid next to it looked weak – "use my face, generate everything else, a
   normal YouTube thumbnail is better"). Save a sharp frame where he looks at the camera as
   `work/thumbnail_frame.png` and run, in this directory:
   `python3 ai_thumbnail.py work/thumbnail_frame.png --headline "<3-7 chars, e.g. EWS廃止>" --sub
   "<product, e.g. Exchange Online>" --badge "<series label, e.g. MS週報, or omit>" --motif "<in English:
   the product of the week's biggest change, shown breaking or changing>"`.
   The series label (e.g. **MS週報**) must stand out as a big program-logo badge. Never ask for another
   expression or pose (surprised face, pointing): the model then redraws his face and it is no longer
   him – that variant was rejected. Look at the result: same face as the photo, whole head visible,
   nothing over the hair or face, every word spelt exactly. Regenerate (it is cheap) until it is right;
   if it never is, fall back to a real frame plus text and then save that frame as
   `work/thumbnail_source.png` and run `python3 check_thumbnail.py out/thumbnail.png --source
   work/thumbnail_source.png` (do **not** save `thumbnail_source.png` for an AI thumbnail: the pixel
   comparison only works for a pasted photo). The harness refuses to upload a rejected thumbnail.
5. `out/EDIT_NOTES.md` – in Japanese: what you understood the video to be about, who it is for,
   every significant decision (what you cut and why, what you added and why), what you tried and
   rejected, what you would do with more time, and **which of your steps felt mechanical enough to
   be scripted next time**. This file is as important as the video.

## How to work

- Start by understanding the whole recording (transcript + contact sheets) before cutting anything.
- Decide the structure yourself: hook in the first seconds, what to remove (silences, fillers,
  retakes, dead time, off-topic tangents, technical trouble), chapters, on-screen text, emphasis,
  zooms on small UI text, stingers, anything that makes it better to watch. Do not invent facts:
  on-screen text must be grounded in what is said or shown.
- House rules learned from the presenter's review (non-negotiable):
  - **Burn captions into every stretch where the presenter talks, and still deliver
    `out/captions.srt`** for the YouTube caption track (2026-10-04 request). Bottom centre, bold Noto
    Sans CJK JP **about 90 px at 1080p, never more than two lines** (2026-10-05: "bigger, two lines
    max"): about 17 full-width characters per line, lines balanced, broken only at phrase boundaries
    (use a morphological analyser such as janome — never inside a word or before a particle), and a
    cue that does not fit is split in time into several two-line pages. White with a dark outline.
    Lift them above any lower-third while it is on screen. Do not burn them over inserted clips that already carry their own captions (e.g. the
    えびフライ part) or over stingers and the end card.
  - **Never trust a word timestamp across a pause.** Whisper sometimes stretches one word over a
    silence (2026-10-04: 「構」 spanned 390.2-396.6 s while the audio sat at -65 dB, so a 6.9 s
    silence survived the cut). Treat any word longer than about 0.8 s as suspect and check the
    audio level there. Before finishing, run `python3 check_silence.py out/final.mp4 --ignore <ranges
    of inserted clips, stingers and the end card>` and cut every silence it reports in the
    presenter's parts.
  - **The sign-off is always 「Stay Hungry. Stay Foolish.」** (Steve Jobs, Stanford 2005), followed by
    「胡田でした」. Write it exactly like that in captions and telops however it was transcribed
    (ステイハングリー／ステイフリッシュ／ステイフーリッシュ …). His name is 胡田 (えびすだ), never
    エビスタ／ヘビスタ／恵比寿.
  - **Cut every span without speech**, including typing, clicking or rustling. Loudness is not
    speech: find gaps from the transcript word timestamps (no words for more than about 1 s) and
    check them, instead of trusting the silence map alone.
  - **Zoom gently or not at all.** Never more than about 1.1x, keep head and shoulders with
    headroom. A close-up of the face is unpleasant to him.
  - **Keep on-screen text up while its point is being talked about**, until the topic changes,
    not for a fixed few seconds.
  - **No flicker.** Decide framing per frame index from the same integer frame counts used to cut
    (never from rounded continuous times), change framing only at a cut, keep each framing state at
    least about 1 s, and scan the final render for 1-3 frame anomalies before finishing.
  - **One integer clock for every input.** When several streams are combined (camera, slides,
    picture-in-picture), give each `settb=1/FPS,setpts=N` before overlaying; never use
    `setpts=N/FPS/TB` on inputs whose time bases differ (it drifts by a frame every few frames).
  - **Never show slide text and burned-in text at the same time.** Lower thirds, panels and
    chapter tags belong to face-only stretches.
  - **Round face picture-in-picture: frame the whole head, not the top of it.** Centre the
    circle crop lower than the eyes (around the mouth/chin), with a little space above the hair
    and the chin and neck visible. In the 2026-10-01 review the circle cut off too much of the
    lower face.
- Keep an edit decision list you can re-render from (e.g. `work/edl.json` + a render script) so
  that fixing one decision does not mean starting over.
- Render previews from the proxy first, **look at frames from your preview** (especially around
  cuts and overlays) and fix what is wrong. Do at least one review pass; two or three is better.
- Render the final from `input/source.mkv` only once you are satisfied. CPU only (16 cores), so
  prefer a single ffmpeg pass (`-preset medium` or faster) over many generations.
- Verify `out/final.mp4` with ffprobe (duration, streams) and sample frames before finishing.
- Do not upload, publish or post anything. The harness uploads `out/final.mp4` as a private video
  after you finish.
- Never modify `input/`. Put scratch files under `work/`.

When you are done, print a short Japanese summary: final duration, number of cuts, what you added,
and the path of each deliverable.

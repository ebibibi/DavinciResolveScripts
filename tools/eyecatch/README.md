# Eyecatch stingers from code

Two-second branded stingers (1920x1080, 60 fps, stereo 48 kHz) for chapter
breaks, rendered entirely from code. They sit alongside the three hand-made
clips in `!動画素材` (`01_EBI_CHAN_OP`, `02_EBI_CHAN_OP`, `03_EBI_CHAN_IN`).

| Variant | What happens |
|---|---|
| `assemble` | ~4,200 particles sampled from the logo swirl in and assemble it; the brand yellow opens on the hit |
| `bounce` | E-B-I-S-U-D-A drop in and bounce, fly off, and the logo pops out with confetti |
| `morph` | circle → square → triangle → star (the same 240 outline points), then the logo |
| `tunnel` | wireframe cube inside a tunnel accelerating at the camera, then the logo slams in |

## Run

```bash
pip install -r requirements-dev.txt
playwright install chromium
python tools/eyecatch/render.py                # all variants -> tools/eyecatch/out/
python tools/eyecatch/render.py morph --out D:/素材
```

`ffmpeg` must be on `PATH`. A full run takes about a minute.

## How it is put together

- **Everything is timed in beats.** `timeline.json` sets 120 BPM, so one beat is
  exactly 30 frames and the four-beat stinger is exactly 120 frames. The logo
  lands on beat 2 in the picture (`index.html`) and in the sound
  (`make_audio.py`), which both read the same file, so they cannot drift.
- **Motion is easing curves.** `expoOut` for fast-then-settle, `backOut` for the
  overshooting pop, `bounceOut` for the dropping letters.
- **Finishing.** Each frame is drawn 10 times across half a frame of shutter and
  averaged (motion blur), with film grain, a vignette, and an RGB-split glitch
  around the hit.
- **Sound is synthesized.** Falling-sine kicks, high-passed noise hats and riser,
  a seven-voice detuned saw chord, sidechain ducking on each kick, and 0.1 s of
  true silence right before the hit.
- `render.py` serves this folder on localhost (the logo is sampled with
  `getImageData`, which a `file://` page may not do), steps headless Chromium
  frame by frame, pipes PNGs to ffmpeg, and muxes the audio.

To add a variant, add a `variants.<name>` object with `setup()` and
`draw(ctx, beat, cue)` in `index.html` and an entry in `timeline.json`.

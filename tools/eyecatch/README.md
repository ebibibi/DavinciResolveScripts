# Eyecatch stingers from code

Two-second branded stingers (1920x1080, 60 fps, stereo 48 kHz) for chapter
breaks, rendered entirely from code. They sit alongside the three hand-made
clips in `!動画素材` (`01_EBI_CHAN_OP`, `02_EBI_CHAN_OP`, `03_EBI_CHAN_IN`).

| Variant | Picture | Sound |
|---|---|---|
| `assemble` | ~4,200 particles sampled from the logo swirl in and assemble it; the brand yellow opens on the hit | glittering chimes that thicken as the logo forms, a swelling pad, then a deep boom and a bell chord |
| `bounce` | E-B-I-S-U-D-A drop in and bounce, fly off, and the logo pops out with confetti | a springy boing per letter landing (rising up the scale, panned left to right), a whoosh, then pop, clap and brass |
| `morph` | circle → square → triangle → star (the same 240 outline points), then the logo | 8-bit blips played on the wave that matches each shape (sine, square, triangle, saw), gliding as they morph, then a power-up arpeggio |
| `tunnel` | wireframe cube inside a tunnel accelerating at the camera, then the logo slams in | an engine drone that climbs with the speed, a whoosh per ring rushing past, a reverse cymbal, then a heavy impact and sub drop |

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
- **Sound is synthesized, one design per variant** (`SOUNDS` in `make_audio.py`),
  from sine / square / triangle / saw waves and shaped noise. Sounds that follow
  the picture read their timing from `timeline.json` too: the letter drops
  (`drop`), the word (`word`) and the tunnel speed (`speed`). Every variant has
  0.1 s of true silence right before the hit.
- `render.py` serves this folder on localhost (the logo is sampled with
  `getImageData`, which a `file://` page may not do), steps headless Chromium
  frame by frame, pipes PNGs to ffmpeg, and muxes the audio.

To add a variant, add a `variants.<name>` object with `setup()` and
`draw(ctx, beat, cue)` in `index.html`, a sound function in `SOUNDS`, and an
entry in `timeline.json` naming both.

# Eyecatch stingers from code

Ten two-second branded stingers (1920x1080, 60 fps, stereo 48 kHz) for chapter
breaks, rendered entirely from code. They sit alongside the three hand-made
clips in `!動画素材` (`01_EBI_CHAN_OP`, `02_EBI_CHAN_OP`, `03_EBI_CHAN_IN`).
`01_EBI_CHAN_OP` is no longer part of the Resolve template.

| Variant | Picture | Sound |
|---|---|---|
| `assemble` | ~4,200 particles sampled from the logo swirl in and assemble it; the brand yellow opens on the hit | glittering chimes that thicken as the logo forms, a swelling pad, then a deep boom and a bell chord |
| `bounce` | E-B-I-S-U-D-A drop in and bounce, fly off, and the logo pops out with confetti | a springy boing per letter landing (rising up the scale, panned left to right), a whoosh, then pop, clap and brass |
| `morph` | circle → square → triangle → star (the same 240 outline points), then the logo | 8-bit blips played on the wave that matches each shape (sine, square, triangle, saw), gliding as they morph, then a power-up arpeggio |
| `tunnel` | wireframe cube inside a tunnel accelerating at the camera, then the logo slams in | an engine drone that climbs with the speed, a whoosh per ring rushing past, a reverse cymbal, then a heavy impact and sub drop |
| `typewriter` | a terminal types `> EBISUDA CHANNEL` one key per step, Enter lands the logo | a click-and-thunk per key, a deep space bar, the carriage bell, then Enter and an electric piano chord |
| `ripple` | drops fall into still water and send out rings; the last one floods the frame yellow | bubble "bloops" with darker echoes for the rings, rising bubbles, then a big splash and a soft pad |
| `slice` | three blade strokes cut the dark frame open; on the hit the halves fall away | a swish before each cut and ringing steel on it, then a taiko hit and a gong |
| `orbit` | planets circle on tilted orbits, speed up and spiral into the centre | sonar pings echoing through space, a warbling FM pad that climbs, then a deep boom and FM bells |
| `pixelate` | the logo arrives as coarse pixels and sharpens one step per beat | data chatter that gets faster and higher each step, bit-crushed, then a two-tone "done" chime |
| `countdown` | an old film leader counts 4-3-2-1 with a sweeping hand, scratches and flicker | projector rattle at 24 clicks a second, a beep per number, then an orchestral hit |

## End card (`outro`)

A 20-second (40-beat) card for new videos: a full-screen showcase of the channel,
then a layout built around the YouTube end screen.

**Beats 0–20 — full-screen showcase** (`variants/outro-promo.js`, `promo` in `timeline.json`)

1. **Microsoft MVP**: a ring of one segment per year fills while the number counts
   up to the streak, then lands with a fanfare and confetti (年連続受賞).
2. **Range**: topic chips scroll in three rows while オンプレ → クラウド → 生成AI
   lands one word per beat, then "ぜんぶ、ここで解説します".
3. **Track record**: four tiles pop in on the beat and count up — 解説動画 900本以上,
   インフラの現場で 20年以上, PCに触れてきて 40年以上, and the book.
4. **Who this is**: logo, name, what the channel covers, and an MVP badge, over a
   musical breakdown that rises into the switch.

A yellow bar sweeps across between scenes. The track-record numbers are written as
"…以上" so they stay true; **the MVP streak (`promo.mvp.years` and
`promo.identity.badge`) is the one value to bump each year.**

**Beats 20–40 — end-screen layout** (`variants/outro.js`)

Set the video's end screen to the last 10 seconds: two video elements stacked on the
left and a subscribe element at the bottom right. Those regions are `endScreen` in
`timeline.json` and are drawn as framed slots. In between, 高評価, チャンネル登録・通知オン
and メンバーシップ (tagged おすすめ, glowing twice as often via `glowOrder`) are clicked
on the beat; thanks appears under the logo on beat 34 and the logo pulses on the final
chord at beat 38.

It renders to `EBI_CHAN_OUTRO.mp4` (about 11 minutes: 1,200 frames x 10 blur samples).

The Resolve editing scripts append this card after `03_EBI_CHAN_IN.mov` at the end of
every edit, using the copy in `!動画素材` if there is one and otherwise the bundled
`assets/EBI_CHAN_OUTRO.mp4`. **After re-rendering the end card, refresh
`assets/EBI_CHAN_OUTRO.mp4` too**, re-encoded so the repository stays small:

```bash
ffmpeg -i tools/eyecatch/out/EBI_CHAN_OUTRO.mp4 -c:v libx264 -preset slow -crf 20 \
  -pix_fmt yuv420p -r 60 -c:a copy -movflags +faststart assets/EBI_CHAN_OUTRO.mp4
```

A variant can set its own `beats`, `hitBeat` and `output` name in `timeline.json`;
anything it leaves out comes from the top level.

## Run

```bash
pip install -r requirements-dev.txt
playwright install chromium
python tools/eyecatch/render.py                # all variants + end card -> tools/eyecatch/out/
python tools/eyecatch/render.py outro          # just the end card
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

## Files

- `timeline.json` — BPM, length, the hit beat, and each variant's own timing
- `engine.js` — maths, easing, shared drawing, motion blur and finishing, the frame loop
- `variants/<name>.js` — one picture per file (`outro.js` is the end card)
- `synth.py` — oscillators, noise, filters and the stereo `Mix`
- `sounds/<name>.py` — one sound design per file, registered in `sounds/__init__.py`
- `make_audio.py` / `render.py` — soundtrack assembly and the renderer

To add a variant: write `variants/<name>.js` (a `variants.<name>` object with
`setup()` and `draw(ctx, beat, cue)`) and include it in `index.html`, write
`sounds/<sound>.py` with a `design(cue)` and register it, and add an entry to
`timeline.json` naming the sound.

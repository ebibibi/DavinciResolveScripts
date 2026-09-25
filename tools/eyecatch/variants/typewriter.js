// A terminal types the channel name one key per step, then Enter lands the logo.
variants.typewriter = {
  setup() {},
  draw(ctx, beat, cue) {
    const { text, start, every } = cue.typing;
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);

    // Faint scanlines so it reads as a screen.
    ctx.fillStyle = 'rgba(255,255,255,0.035)';
    for (let y = 0; y < H; y += 6) ctx.fillRect(0, y, W, 2);

    const typed = Math.max(0, Math.min(text.length, Math.floor((beat - start) / every) + 1));
    const line = text.slice(0, typed);
    const enter = span(beat, cue.hit - 0.12, 0.12, ease.expoIn);
    ctx.save();
    ctx.font = '700 110px "DejaVu Sans Mono", monospace';
    ctx.textBaseline = 'middle';
    const full = ctx.measureText(text).width;
    const x = W / 2 - full / 2;
    const y = H / 2 - enter * 140;
    ctx.globalAlpha = 1 - enter;
    ctx.fillStyle = BRAND.yellow;
    ctx.shadowColor = BRAND.yellow;
    ctx.shadowBlur = 24;
    ctx.fillText(line, x, y);
    // The cursor blinks twice a beat and sits after the last typed character.
    if (Math.floor(beat * 4) % 2 === 0 || typed < text.length) {
      ctx.fillRect(x + ctx.measureText(line).width + 8, y - 55, 60, 110);
    }
    ctx.restore();

    if (beat >= cue.hit) {
      const open = span(beat, cue.hit, 0.35, ease.expoOut);
      ctx.fillStyle = BRAND.yellow;
      ctx.fillRect(0, H / 2 - (open * H) / 2, W, open * H);
      stripes(ctx, beat);
    }
    landLogo(ctx, beat, cue.hit, 0.5);
    flash(ctx, beat, cue.hit, 0.1);
  },
};

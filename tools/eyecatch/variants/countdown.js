// An old film leader: a sweeping hand counts down, then the logo takes the screen.
variants.countdown = {
  setup() {},
  draw(ctx, beat, cue) {
    const rand = mulberry32(Math.floor(beat * 24) + 1); // film runs at 24 fps: flicker per film frame
    const flicker = 0.9 + rand() * 0.1;
    ctx.fillStyle = `rgb(${Math.round(222 * flicker)},${Math.round(200 * flicker)},${Math.round(172 * flicker)})`;
    ctx.fillRect(0, 0, W, H);

    const index = cue.ticks.filter((t) => beat >= t).length - 1;
    if (beat < cue.hit && index >= 0) {
      const from = cue.ticks[index];
      const to = cue.ticks[index + 1] ?? cue.hit;
      const sweep = clamp01((beat - from) / (to - from));
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.fillStyle = 'rgba(28,20,17,0.22)';
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.arc(0, 0, 1200, -Math.PI / 2, -Math.PI / 2 + sweep * Math.PI * 2);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = BRAND.ink;
      ctx.lineWidth = 6;
      [300, 380].forEach((r) => { ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke(); });
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(-W, 0); ctx.lineTo(W, 0);
      ctx.moveTo(0, -H); ctx.lineTo(0, H);
      ctx.stroke();
      const number = cue.ticks.length - index;
      const punch = span(beat, from, 0.15, ease.backOut);
      ctx.font = '900 380px "Noto Sans CJK JP", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.scale(lerp(1.3, 1, punch), lerp(1.3, 1, punch));
      ctx.fillStyle = index === cue.ticks.length - 1 ? BRAND.red : BRAND.ink;
      ctx.fillText(String(number), 0, 20);
      ctx.restore();

      // Scratches and dust: a few vertical hairlines and specks per film frame.
      ctx.fillStyle = 'rgba(28,20,17,0.5)';
      for (let i = 0; i < 3; i++) ctx.fillRect(rand() * W, 0, 1 + rand() * 2, H);
      for (let i = 0; i < 12; i++) {
        ctx.beginPath();
        ctx.arc(rand() * W, rand() * H, 1 + rand() * 5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (beat >= cue.hit) {
      ctx.fillStyle = BRAND.yellow;
      ctx.fillRect(0, 0, W, H);
      stripes(ctx, beat);
    }
    landLogo(ctx, beat, cue.hit, 0.6);
    flash(ctx, beat, cue.hit, 0.15);
  },
};

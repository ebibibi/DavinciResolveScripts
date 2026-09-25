// Drops fall into still water; every splash sends out rings, the last one floods the frame.
variants.ripple = {
  setup() {},
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.cream;
    ctx.fillRect(0, 0, W, H);

    const splashes = cue.ticks;
    splashes.forEach((at, i) => {
      // The drop falls for half a beat and accelerates like it should.
      const fall = span(beat, at - 0.4, 0.4, ease.expoIn);
      if (fall > 0 && fall < 1) {
        const y = lerp(-80, H / 2, fall);
        ctx.fillStyle = BRAND.red;
        ctx.beginPath();
        ctx.ellipse(W / 2, y, 26, 26 + fall * 40, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      for (let ring = 0; ring < 3; ring++) {
        const p = span(beat, at + ring * 0.08, 1.4, ease.expoOut);
        if (p <= 0 || p >= 1) continue;
        ctx.save();
        ctx.strokeStyle = i % 2 ? BRAND.yellow : BRAND.red;
        ctx.globalAlpha = (1 - p) * (1 - ring * 0.25);
        ctx.lineWidth = lerp(22, 3, p);
        ctx.beginPath();
        // Seen at an angle, so the rings are flattened ellipses.
        ctx.ellipse(W / 2, H / 2, p * 700, p * 230, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
    });

    const fall = span(beat, cue.hit - 0.4, 0.3, ease.expoIn);
    if (fall > 0 && beat < cue.hit) {
      ctx.fillStyle = BRAND.yellow;
      ctx.beginPath();
      ctx.ellipse(W / 2, lerp(-120, H / 2, fall), 40, 40 + fall * 60, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    const flood = span(beat, cue.hit, 0.6, ease.expoOut);
    if (flood > 0) {
      ctx.fillStyle = BRAND.yellow;
      ctx.beginPath();
      ctx.ellipse(W / 2, H / 2, flood * 1500, flood * 1100, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    landLogo(ctx, beat, cue.hit, 0.1);
    shockwave(ctx, beat, cue.hit, BRAND.cream);
  },
};

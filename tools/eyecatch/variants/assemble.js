variants.assemble = {
  setup() {
    const rand = mulberry32(7);
    this.particles = logoPoints.map((target) => {
      const angle = rand() * Math.PI * 2;
      const radius = 900 + rand() * 700;
      return {
        ...target,
        sx: W / 2 + Math.cos(angle) * radius,
        sy: H / 2 + Math.sin(angle) * radius * 0.7,
        delay: rand() * 0.5,
        size: 2 + rand() * 3,
      };
    });
  },
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);

    // The brand yellow opens from the centre on the hit.
    const open = span(beat, cue.hit, 0.5, ease.expoOut);
    if (open > 0) {
      ctx.fillStyle = BRAND.yellow;
      ctx.beginPath();
      ctx.arc(W / 2, H / 2, open * 1200, 0, Math.PI * 2);
      ctx.fill();
    }

    if (beat < cue.hit + 0.1) {
      const fade = 1 - span(beat, cue.hit, 0.1);
      ctx.globalAlpha = fade;
      for (const p of this.particles) {
        const t = span(beat, 0.25 + p.delay, 1.3, ease.expoOut);
        const swirl = (1 - t) * 1.6;
        const dx = p.sx - W / 2;
        const dy = p.sy - H / 2;
        const rx = W / 2 + dx * Math.cos(swirl) - dy * Math.sin(swirl);
        const ry = H / 2 + dx * Math.sin(swirl) + dy * Math.cos(swirl);
        ctx.fillStyle = p.color;
        ctx.fillRect(lerp(rx, p.x, t), lerp(ry, p.y, t), p.size, p.size);
      }
      ctx.globalAlpha = 1;
    }
    landLogo(ctx, beat, cue.hit, 0.85);
    shockwave(ctx, beat, cue.hit, BRAND.cream);
    flash(ctx, beat, cue.hit);
  },
};

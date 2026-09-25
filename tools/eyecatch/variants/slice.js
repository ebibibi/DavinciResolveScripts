// Three blade strokes cut the dark frame open; on the hit the pieces fall away.
variants.slice = {
  setup() {
    // Each cut: an angle and an offset from the centre, crossing the whole frame.
    this.cuts = [
      { angle: -0.5, offset: -160 },
      { angle: 0.35, offset: 120 },
      { angle: -0.15, offset: 20 },
    ];
  },
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.yellow;
    ctx.fillRect(0, 0, W, H);
    stripes(ctx, beat);

    const apart = span(beat, cue.hit, 0.5, ease.expoOut);
    // The dark frame as two halves split along the last cut, pushed apart on the hit.
    const last = this.cuts[this.cuts.length - 1];
    [-1, 1].forEach((side) => {
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.rotate(last.angle);
      ctx.translate(0, side * apart * 1500 + last.offset);
      ctx.rotate(side * apart * 0.2);
      ctx.beginPath();
      ctx.rect(-2000, side < 0 ? -2000 : 0, 4000, 2000);
      ctx.clip();
      ctx.rotate(-last.angle);
      ctx.translate(0, -last.offset);
      this.drawDark(ctx, beat, cue);
      ctx.restore();
    });
    landLogo(ctx, beat, cue.hit, 0.3);
    flash(ctx, beat, cue.hit, 0.1);
  },
  drawDark(ctx, beat, cue) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(-W, -H, W * 2, H * 2);
    this.cuts.forEach((cut, i) => {
      const at = cue.ticks[i];
      const stroke = span(beat, at - 0.1, 0.12, ease.expoOut);
      if (stroke <= 0) return;
      const gap = span(beat, at, 0.4, ease.expoOut) * 26;
      ctx.save();
      ctx.rotate(cut.angle);
      ctx.translate(0, cut.offset);
      // The slit shows the yellow underneath, the blade leaves a bright streak.
      ctx.fillStyle = BRAND.yellow;
      ctx.fillRect(-1400, -gap / 2, 2800 * stroke, gap);
      ctx.fillStyle = '#fff';
      ctx.globalAlpha = 1 - span(beat, at, 0.3);
      ctx.fillRect(-1400, -3, 2800 * stroke, 6);
      ctx.restore();
    });
  },
};

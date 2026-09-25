variants.bounce = {
  setup() {},
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.yellow;
    ctx.fillRect(0, 0, W, H);
    stripes(ctx, beat);

    const letters = cue.word.split('');
    const pitch = 190;
    const left = W / 2 - ((letters.length - 1) * pitch) / 2;
    const exit = span(beat, 1.75, 0.25, ease.expoIn);
    ctx.font = '900 300px "Noto Sans CJK JP", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    letters.forEach((letter, i) => {
      const drop = span(beat, i * cue.drop.every, cue.drop.length, ease.bounceOut);
      if (drop <= 0) return;
      const y = lerp(-300, H / 2, drop) - exit * (900 + i * 60);
      const x = left + i * pitch;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate((1 - drop) * (i % 2 ? 0.4 : -0.4));
      ctx.fillStyle = BRAND.ink;
      ctx.fillText(letter, 10, 12);
      ctx.fillStyle = BRAND.red;
      ctx.fillText(letter, 0, 0);
      ctx.restore();
    });

    burst(ctx, beat, cue.hit, 11);
    landLogo(ctx, beat, cue.hit, 0.2);
    shockwave(ctx, beat, cue.hit, BRAND.red);
  },
};

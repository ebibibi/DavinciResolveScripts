variants.tunnel = {
  setup() {},
  draw(ctx, beat, cue) {
    const focal = 700;
    const [cruise, boost] = cue.speed;
    const speed = cruise + span(beat, 0, cue.hit, ease.expoIn) * boost;
    const travel = beat * speed;

    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2, H / 2);

    // Square rings rushing towards the camera: farther means smaller.
    for (let i = 0; i < 26; i++) {
      const z = 26 - ((i + travel) % 26);
      if (z < 0.3) continue;
      const s = (focal / z) * 1.2;
      ctx.globalAlpha = clamp01(1.4 - z / 20);
      ctx.strokeStyle = i % 4 === 0 ? BRAND.yellow : BRAND.cream;
      ctx.lineWidth = Math.max(1, 14 / z);
      ctx.strokeRect(-s, -s * 0.62, s * 2, s * 1.24);
    }
    ctx.globalAlpha = 1;

    // A wireframe cube in the middle, projected by hand.
    const cube = [-1, 1].flatMap((x) => [-1, 1].flatMap((y) => [-1, 1].map((z) => [x, y, z])));
    const ry = beat * 2.2;
    const rx = beat * 1.3;
    const size = 130 + span(beat, 1, 1, ease.expoIn) * 600;
    const projected = cube.map(([x, y, z]) => {
      const x1 = x * Math.cos(ry) - z * Math.sin(ry);
      const z1 = x * Math.sin(ry) + z * Math.cos(ry);
      const y1 = y * Math.cos(rx) - z1 * Math.sin(rx);
      const z2 = y * Math.sin(rx) + z1 * Math.cos(rx);
      const k = 4 / (4 + z2);
      return [x1 * size * k, y1 * size * k];
    });
    ctx.strokeStyle = BRAND.red;
    ctx.lineWidth = 6;
    ctx.beginPath();
    for (let i = 0; i < 8; i++) {
      for (let j = i + 1; j < 8; j++) {
        const diff = cube[i].filter((v, n) => v !== cube[j][n]).length;
        if (diff !== 1) continue;
        ctx.moveTo(...projected[i]);
        ctx.lineTo(...projected[j]);
      }
    }
    ctx.stroke();
    ctx.restore();

    if (beat >= cue.hit) {
      ctx.fillStyle = BRAND.yellow;
      ctx.fillRect(0, 0, W, H);
      stripes(ctx, beat);
      const slam = span(beat, cue.hit, 0.35, ease.expoOut);
      drawLogo(ctx, lerp(2.6, 1, slam), 1);
    }
    flash(ctx, beat, cue.hit, 0.2);
  },
};

// Every shape is the same 240 points, so any two can be blended point by point.
const OUTLINE_POINTS = 240;

function polygonOutline(corners, rotation = -Math.PI / 2, inner = 1) {
  const vertices = [];
  const count = inner === 1 ? corners : corners * 2;
  for (let i = 0; i < count; i++) {
    const r = inner !== 1 && i % 2 ? inner : 1;
    const a = rotation + (i / count) * Math.PI * 2;
    vertices.push([Math.cos(a) * r, Math.sin(a) * r]);
  }
  const points = [];
  for (let i = 0; i < OUTLINE_POINTS; i++) {
    const t = (i / OUTLINE_POINTS) * vertices.length;
    const k = Math.floor(t);
    const [ax, ay] = vertices[k];
    const [bx, by] = vertices[(k + 1) % vertices.length];
    points.push([lerp(ax, bx, t - k), lerp(ay, by, t - k)]);
  }
  return points;
}

function circleOutline() {
  return Array.from({ length: OUTLINE_POINTS }, (_, i) => {
    const a = -Math.PI / 2 + (i / OUTLINE_POINTS) * Math.PI * 2;
    return [Math.cos(a), Math.sin(a)];
  });
}

variants.morph = {
  setup() {
    this.shapes = [
      circleOutline(),
      polygonOutline(4, -Math.PI / 4),
      polygonOutline(3),
      polygonOutline(5, -Math.PI / 2, 0.45),
    ];
    this.colors = [BRAND.red, BRAND.yellow, BRAND.ink, BRAND.red];
  },
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.cream;
    ctx.fillRect(0, 0, W, H);

    const step = Math.min(3, Math.floor(beat / 0.5));
    const next = Math.min(3, step + 1);
    const t = step === 3 ? 0 : span(beat, step * 0.5 + 0.2, 0.3, ease.inOutCubic);
    const a = this.shapes[step];
    const b = this.shapes[next];
    const grow = span(beat, cue.hit - 0.25, 0.25, ease.expoIn);
    const radius = 300 * span(beat, 0, 0.35, ease.backOut) + grow * 1800;
    const spin = beat * 1.4;

    if (beat < cue.hit + 0.05) {
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.rotate(spin);
      ctx.fillStyle = step === 3 ? this.colors[3] : blend(this.colors[step], this.colors[next], t);
      ctx.beginPath();
      a.forEach(([ax, ay], i) => {
        const x = lerp(ax, b[i][0], t) * radius;
        const y = lerp(ay, b[i][1], t) * radius;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    if (beat >= cue.hit) {
      ctx.fillStyle = BRAND.yellow;
      ctx.fillRect(0, 0, W, H);
      stripes(ctx, beat);
    }
    landLogo(ctx, beat, cue.hit, 0.3);
    shockwave(ctx, beat, cue.hit, BRAND.cream);
  },
};

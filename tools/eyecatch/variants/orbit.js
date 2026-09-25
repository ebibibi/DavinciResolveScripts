// Planets circle on tilted orbits, speed up, and spiral into the centre.
variants.orbit = {
  setup() {
    const rand = mulberry32(21);
    this.stars = Array.from({ length: 260 }, () => [rand() * W, rand() * H, rand()]);
    this.planets = [
      { radius: 260, tilt: 0.35, speed: 1.6, size: 26, color: BRAND.yellow, phase: 0 },
      { radius: 400, tilt: 0.28, speed: 1.1, size: 34, color: BRAND.red, phase: 2.1 },
      { radius: 540, tilt: 0.22, speed: 0.8, size: 20, color: BRAND.cream, phase: 4.2 },
    ];
  },
  position(planet, beat, cue) {
    const pull = 1 - span(beat, 1.3, cue.hit - 1.3, ease.expoIn);
    // Angle is the integral of a speed that grows, so the planet never jumps back.
    const angle = planet.phase + planet.speed * (beat * 2 + beat * beat * 1.6);
    const r = planet.radius * pull;
    const x = Math.cos(angle) * r;
    const z = Math.sin(angle) * r;
    const k = 900 / (900 + z * 0.8);
    return { x: W / 2 + x * k, y: H / 2 + z * planet.tilt * k, k, pull };
  },
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);
    for (const [x, y, s] of this.stars) {
      ctx.fillStyle = `rgba(232,206,176,${0.2 + s * 0.6})`;
      ctx.fillRect(x, y, 1 + s * 2, 1 + s * 2);
    }
    if (beat < cue.hit) {
      ctx.save();
      ctx.strokeStyle = 'rgba(232,206,176,0.25)';
      ctx.lineWidth = 2;
      for (const planet of this.planets) {
        const { pull } = this.position(planet, beat, cue);
        ctx.beginPath();
        ctx.ellipse(W / 2, H / 2, planet.radius * pull, planet.radius * planet.tilt * pull, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
      const core = 30 + 30 * span(beat, 1.3, cue.hit - 1.3, ease.expoIn);
      ctx.fillStyle = BRAND.yellow;
      ctx.shadowColor = BRAND.yellow;
      ctx.shadowBlur = 60;
      ctx.beginPath();
      ctx.arc(W / 2, H / 2, core, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      for (const planet of this.planets) {
        const { x, y, k } = this.position(planet, beat, cue);
        ctx.fillStyle = planet.color;
        ctx.beginPath();
        ctx.arc(x, y, planet.size * k, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const bloom = span(beat, cue.hit, 0.5, ease.expoOut);
    if (bloom > 0) {
      ctx.fillStyle = BRAND.yellow;
      ctx.beginPath();
      ctx.arc(W / 2, H / 2, bloom * 1200, 0, Math.PI * 2);
      ctx.fill();
    }
    landLogo(ctx, beat, cue.hit, 0.05);
    shockwave(ctx, beat, cue.hit, BRAND.red);
    flash(ctx, beat, cue.hit, 0.15);
  },
};

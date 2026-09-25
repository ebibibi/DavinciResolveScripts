// The logo arrives as coarse pixels and sharpens one step per beat.
variants.pixelate = {
  setup() {
    this.small = document.createElement('canvas');
  },
  draw(ctx, beat, cue) {
    const blocks = cue.blocks; // block size in pixels, one per tick
    const step = cue.ticks.filter((t) => beat >= t).length - 1;
    const sharp = beat >= cue.hit;
    const size = sharp ? 1 : blocks[Math.max(0, step)];

    // Render the finished frame at low resolution, then blow it up without smoothing.
    const sw = Math.ceil(W / size);
    const sh = Math.ceil(H / size);
    this.small.width = sw;
    this.small.height = sh;
    const g = this.small.getContext('2d');
    g.save();
    g.scale(sw / W, sh / H);
    g.fillStyle = BRAND.yellow;
    g.fillRect(0, 0, W, H);
    const pop = sharp ? lerp(1.25, 1, span(beat, cue.hit, 0.4, ease.backOut)) : 1;
    drawLogo(g, pop, 1);
    g.restore();

    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.small, 0, 0, sw * size, sh * size);
    ctx.restore();

    if (!sharp) {
      // Blocks not yet "loaded" stay dark, filling in fast at the start of each step.
      const rand = mulberry32(step + 40);
      const loaded = span(beat, cue.ticks[Math.max(0, step)], 0.3, ease.expoOut);
      ctx.fillStyle = 'rgba(160,104,20,0.55)';
      for (let y = 0; y < sh; y++) {
        for (let x = 0; x < sw; x++) {
          if (rand() > loaded) ctx.fillRect(x * size, y * size, size, size);
        }
      }
      ctx.strokeStyle = 'rgba(28,20,17,0.35)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let x = 0; x <= W; x += size) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
      for (let y = 0; y <= H; y += size) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
      ctx.stroke();
    }
    shockwave(ctx, beat, cue.hit, BRAND.cream);
  },
};

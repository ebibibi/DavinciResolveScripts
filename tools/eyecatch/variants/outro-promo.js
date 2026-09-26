// The end card's first half: a full-screen showcase of the channel, four scenes
// of five beats each. Every fact comes from cue.promo in timeline.json; the MVP
// streak is the one number that needs a yearly bump there.
const outroPromo = {
  chipWidths: null,

  draw(ctx, beat, cue) {
    const scenes = cue.promo;
    if (beat < scenes.range.at) this.mvp(ctx, beat, scenes.mvp);
    else if (beat < scenes.stats.at) this.range(ctx, beat, cue, scenes.range);
    else if (beat < scenes.identity.at) this.stats(ctx, beat, scenes.stats);
    else this.identity(ctx, beat, cue, scenes.identity);
    // A yellow bar sweeps across at every scene change.
    [scenes.range.at, scenes.stats.at, scenes.identity.at].forEach((at) => {
      const p = span(beat, at - 0.25, 0.5, ease.inOutCubic);
      if (p <= 0 || p >= 1) return;
      ctx.fillStyle = BRAND.yellow;
      const x = lerp(-W, W, p);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + W * 0.7, 0);
      ctx.lineTo(x + W * 0.5, H);
      ctx.lineTo(x - W * 0.2, H);
      ctx.closePath();
      ctx.fill();
    });
  },

  // ---------- scene 1: the MVP streak ----------

  mvp(ctx, beat, s) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);
    // Slow rotating rays: the "award" backdrop.
    ctx.save();
    ctx.translate(W / 2, 540);
    ctx.rotate(beat * 0.15);
    ctx.fillStyle = 'rgba(242,182,50,0.07)';
    for (let i = 0; i < 18; i++) {
      ctx.rotate((Math.PI * 2) / 18);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(-90, -1400);
      ctx.lineTo(90, -1400);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();

    const counted = span(beat, s.countFrom, s.countTo - s.countFrom, ease.inOutCubic);
    const shown = Math.max(1, Math.round(lerp(1, s.years, counted)));
    const done = beat >= s.countTo;

    // One ring segment per year, lighting up as the counter climbs.
    const gap = 0.05;
    for (let i = 0; i < s.years; i++) {
      const a0 = -Math.PI / 2 + (i / s.years) * Math.PI * 2 + gap;
      const a1 = -Math.PI / 2 + ((i + 1) / s.years) * Math.PI * 2 - gap;
      const lit = i < shown && beat >= s.countFrom;
      ctx.strokeStyle = lit ? (done ? BRAND.yellow : BRAND.cream) : 'rgba(232,206,176,0.15)';
      ctx.lineWidth = 34;
      ctx.beginPath();
      ctx.arc(W / 2, 540, 300, a0, a1);
      ctx.stroke();
    }

    const pop = done ? 1 + 0.25 * Math.exp(-(beat - s.countTo) * 5) : 1;
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.translate(W / 2, 540);
    ctx.scale(pop, pop);
    ctx.fillStyle = done ? BRAND.yellow : BRAND.cream;
    ctx.font = `900 300px ${JP}`;
    ctx.fillText(String(shown), 0, 10);
    ctx.restore();

    const title = span(beat, 0, 0.5, ease.expoOut);
    ctx.save();
    ctx.textAlign = 'center';
    ctx.globalAlpha = title;
    ctx.fillStyle = BRAND.cream;
    ctx.font = `900 84px ${JP}`;
    ctx.fillText(s.title, W / 2, 170 - (1 - title) * 40);
    const sub = span(beat, s.countTo, 0.4, ease.backOut);
    ctx.globalAlpha = clamp01(sub);
    ctx.fillStyle = BRAND.yellow;
    ctx.font = `900 ${Math.round(88 * sub)}px ${JP}`;
    ctx.fillText(s.suffix, W / 2, 965);
    ctx.globalAlpha = span(beat, s.countTo + 0.5, 0.5);
    ctx.fillStyle = BRAND.cream;
    ctx.font = `700 34px ${JP}`;
    ctx.fillText(s.category, W / 2, 1040);
    ctx.restore();
    if (done) {
      shockwave(ctx, beat, s.countTo, BRAND.yellow, 1100);
      burst(ctx, beat, s.countTo, 5);
    }
  },

  // ---------- scene 2: the range ----------

  range(ctx, beat, cue, s) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);
    const local = beat - s.at;
    this.marquee(ctx, local, cue.topics);

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.globalAlpha = span(local, 0, 0.4, ease.expoOut);
    ctx.font = `700 40px ${JP}`;
    ctx.fillStyle = BRAND.cream;
    ctx.fillText(s.kicker, W / 2, 400);
    ctx.globalAlpha = 1;

    ctx.font = `900 118px ${JP}`;
    const arrow = 120;
    const widths = s.words.map((w) => ctx.measureText(w).width);
    let x = W / 2 - (widths.reduce((a, b) => a + b, 0) + arrow * (s.words.length - 1)) / 2;
    const lastAt = s.wordsAt[s.wordsAt.length - 1];
    const nod = local >= lastAt ? 1 + 0.05 * Math.exp(-(beat % 1) * 8) : 1;
    s.words.forEach((word, i) => {
      const p = span(local, s.wordsAt[i], 0.45, ease.backOut);
      if (p > 0) {
        ctx.save();
        ctx.translate(x + widths[i] / 2, 540);
        ctx.scale(p * nod, p * nod);
        ctx.fillStyle = i === s.words.length - 1 ? BRAND.yellow : BRAND.cream;
        ctx.fillText(word, 0, 0);
        ctx.restore();
      }
      x += widths[i];
      if (i < s.words.length - 1) {
        const a = span(local, s.wordsAt[i] + 0.5, 0.3, ease.expoOut);
        ctx.globalAlpha = a;
        ctx.fillStyle = BRAND.red;
        ctx.fillText('→', x + arrow / 2 - (1 - a) * 40, 540);
        ctx.globalAlpha = 1;
        x += arrow;
      }
    });
    const tag = span(local, s.taglineAt, 0.5, ease.expoOut);
    ctx.globalAlpha = tag;
    ctx.font = `900 62px ${JP}`;
    ctx.fillStyle = BRAND.yellow;
    ctx.fillText(s.tagline, W / 2, 690 + (1 - tag) * 40);
    ctx.restore();
  },

  marquee(ctx, beat, topics) {
    const ys = [150, 260, 930];
    ctx.save();
    ctx.font = `700 38px ${JP}`;
    ctx.textBaseline = 'middle';
    if (!this.chipWidths) this.chipWidths = topics.map((row) => row.map((t) => ctx.measureText(t).width + 64));
    const travel = beat * 150 + Math.pow(span(beat, 3, 2), 3) * 700;
    const lit = Math.floor(beat * 2);
    topics.forEach((row, r) => {
      const widths = this.chipWidths[r];
      const loop = widths.reduce((a, b) => a + b + 24, 0);
      const dir = r % 2 ? 1 : -1;
      const enter = span(beat, r * 0.15, 0.6, ease.expoOut);
      let x = (((dir * travel) % loop) + loop) % loop - loop + dir * (1 - enter) * 1400;
      for (let k = 0; x < W + loop; k++) {
        const i = k % row.length;
        const w = widths[i];
        if (x + w > 0 && x < W) {
          const hot = (lit + r * 3) % row.length === i;
          ctx.fillStyle = hot ? BRAND.red : r === 1 ? BRAND.yellow : 'rgba(232,206,176,0.12)';
          ctx.beginPath();
          ctx.roundRect(x, ys[r] - 34, w, 68, 34);
          ctx.fill();
          ctx.fillStyle = r === 1 && !hot ? BRAND.ink : BRAND.cream;
          ctx.textAlign = 'center';
          ctx.fillText(row[i], x + w / 2, ys[r] + 2);
        }
        x += w + 24;
      }
    });
    ctx.restore();
  },

  // ---------- scene 3: credentials that stay true ----------

  stats(ctx, beat, s) {
    ctx.fillStyle = BRAND.yellow;
    ctx.fillRect(0, 0, W, H);
    stripes(ctx, beat);
    const local = beat - s.at;
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const head = span(local, 0, 0.5, ease.expoOut);
    ctx.globalAlpha = head;
    ctx.fillStyle = BRAND.ink;
    ctx.font = `900 60px ${JP}`;
    ctx.fillText(s.heading, W / 2, 120 - (1 - head) * 30);
    ctx.restore();

    const tileW = 820;
    const tileH = 360;
    s.tiles.forEach((tile, i) => {
      const at = s.tilesAt[i];
      const p = span(local, at, 0.45, ease.backOut);
      if (p <= 0) return;
      const cx = W / 2 + (i % 2 ? 1 : -1) * (tileW / 2 + 20);
      const cy = 400 + Math.floor(i / 2) * (tileH + 40);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(p, p);
      ctx.fillStyle = BRAND.ink;
      ctx.shadowColor = 'rgba(28,20,17,0.35)';
      ctx.shadowBlur = 30;
      ctx.shadowOffsetY = 10;
      ctx.beginPath();
      ctx.roundRect(-tileW / 2, -tileH / 2, tileW, tileH, 34);
      ctx.fill();
      ctx.shadowColor = 'transparent';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = BRAND.cream;
      ctx.font = `700 40px ${JP}`;
      ctx.fillText(tile.label, 0, -110);
      if (tile.value !== undefined) {
        // Numbers count up over most of a beat, then sit.
        const n = Math.round(tile.value * ease.expoOut(clamp01((local - at) / 0.9)));
        ctx.font = `900 170px ${JP}`;
        const digits = n.toLocaleString('ja-JP');
        const dw = ctx.measureText(digits).width;
        ctx.font = `900 64px ${JP}`;
        const uw = ctx.measureText(tile.unit).width;
        const left = -(dw + uw + 16) / 2;
        ctx.textAlign = 'left';
        ctx.fillStyle = BRAND.yellow;
        ctx.font = `900 170px ${JP}`;
        ctx.fillText(digits, left, 30);
        ctx.fillStyle = BRAND.cream;
        ctx.font = `900 64px ${JP}`;
        ctx.fillText(tile.unit, left + dw + 16, 62);
      } else {
        ctx.fillStyle = BRAND.yellow;
        ctx.font = `900 64px ${JP}`;
        // Shrink a long title until it fits inside the tile.
        const fit = Math.min(1, (tileW - 80) / ctx.measureText(tile.text).width);
        ctx.font = `900 ${Math.floor(64 * fit)}px ${JP}`;
        ctx.fillText(tile.text, 0, 30);
        if (tile.sub) {
          ctx.fillStyle = BRAND.cream;
          ctx.font = `500 32px ${JP}`;
          ctx.fillText(tile.sub, 0, 110);
        }
      }
      ctx.restore();
    });
  },

  // ---------- scene 4: who this is ----------

  identity(ctx, beat, cue, s) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);
    const local = beat - s.at;
    const drift = local * 12;

    const inLogo = span(local, 0, 0.6, ease.expoOut);
    const h = 700;
    const w = h * (logo.width / logo.height);
    ctx.drawImage(logo, lerp(-w, 180, inLogo) - drift * 0.5, 540 - h / 2, w, h);

    const x = 820 + drift;
    ctx.save();
    ctx.textBaseline = 'middle';
    const name = span(local, 0.4, 0.5, ease.expoOut);
    ctx.globalAlpha = name;
    ctx.fillStyle = BRAND.cream;
    ctx.font = `900 150px ${JP}`;
    ctx.fillText(s.name, x + (1 - name) * 80, 380);
    const line = span(local, 1, 0.5, ease.expoOut);
    ctx.globalAlpha = line;
    ctx.fillStyle = BRAND.yellow;
    ctx.font = `900 56px ${JP}`;
    s.lines.forEach((text, i) => ctx.fillText(text, x + (1 - line) * 80, 560 + i * 80));
    ctx.restore();

    const badge = span(local, 1.8, 0.45, ease.backOut);
    if (badge > 0) {
      ctx.save();
      ctx.translate(x + 300, 800);
      ctx.scale(badge, badge);
      ctx.fillStyle = BRAND.red;
      ctx.beginPath();
      ctx.roundRect(-300, -50, 600, 100, 50);
      ctx.fill();
      ctx.fillStyle = '#FFFFFF';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = `900 46px ${JP}`;
      ctx.fillText(s.badge, 0, 3);
      ctx.restore();
    }
  },
};

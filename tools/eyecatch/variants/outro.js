// End card, reusable on every video: first the channel's range (on-prem → cloud →
// generative AI, over scrolling topic chips), then like / subscribe / join, each
// one "clicked" on the beat. Nothing here is dated, so it never goes stale.
const JP = '"Noto Sans CJK JP", sans-serif';
const EMOJI = '"Noto Color Emoji", sans-serif';

variants.outro = {
  setup() {
    this.chipWidths = null;
  },

  draw(ctx, beat, cue) {
    if (beat < cue.hit + 0.4) this.drawRange(ctx, beat, cue);
    // The CTA half wipes in diagonally on the hit, over the range half.
    const wipe = span(beat, cue.hit, 0.4, ease.expoOut);
    if (wipe > 0) {
      ctx.save();
      ctx.beginPath();
      const edge = lerp(-600, W + 600, wipe);
      ctx.moveTo(-600, 0);
      ctx.lineTo(edge + 300, 0);
      ctx.lineTo(edge - 300, H);
      ctx.lineTo(-600, H);
      ctx.closePath();
      ctx.clip();
      this.drawCta(ctx, beat, cue);
      ctx.restore();
    }
  },

  // ---------- part 1: the range ----------

  drawRange(ctx, beat, cue) {
    ctx.fillStyle = BRAND.ink;
    ctx.fillRect(0, 0, W, H);
    this.drawMarquee(ctx, beat, cue);

    const kicker = span(beat, 0, 0.4, ease.expoOut);
    ctx.save();
    ctx.globalAlpha = kicker;
    ctx.font = `700 40px ${JP}`;
    ctx.textAlign = 'center';
    ctx.fillStyle = BRAND.cream;
    ctx.fillText('胡田昌彦チャンネルの守備範囲', W / 2, 400 - (1 - kicker) * 30);
    ctx.restore();

    const { words, at, tagline, taglineAt } = cue.range;
    ctx.save();
    ctx.font = `900 112px ${JP}`;
    ctx.textBaseline = 'middle';
    const arrow = 110;
    const widths = words.map((w) => ctx.measureText(w).width);
    let x = W / 2 - (widths.reduce((a, b) => a + b, 0) + arrow * (words.length - 1)) / 2;
    // Every word nods on each beat once it is in, so the line keeps moving with the music.
    const nod = 1 + 0.05 * Math.exp(-(beat % 1) * 8) * (beat >= at[at.length - 1] ? 1 : 0);
    words.forEach((word, i) => {
      const p = span(beat, at[i], 0.45, ease.backOut);
      if (p > 0) {
        ctx.save();
        ctx.translate(x + widths[i] / 2, 540);
        ctx.scale(p * nod, p * nod);
        ctx.fillStyle = i === words.length - 1 ? BRAND.yellow : BRAND.cream;
        ctx.textAlign = 'center';
        ctx.fillText(word, 0, 0);
        ctx.restore();
      }
      x += widths[i];
      if (i < words.length - 1) {
        const a = span(beat, at[i] + 0.5, 0.3, ease.expoOut);
        ctx.fillStyle = BRAND.red;
        ctx.globalAlpha = a;
        ctx.textAlign = 'center';
        ctx.fillText('→', x + arrow / 2 - (1 - a) * 40, 540);
        ctx.globalAlpha = 1;
        x += arrow;
      }
    });
    const tag = span(beat, taglineAt, 0.5, ease.expoOut);
    ctx.globalAlpha = tag;
    ctx.font = `700 60px ${JP}`;
    ctx.textAlign = 'center';
    ctx.fillStyle = BRAND.yellow;
    ctx.fillText(tagline, W / 2, 680 + (1 - tag) * 40);
    ctx.restore();
  },

  drawMarquee(ctx, beat, cue) {
    const rows = cue.topics;
    const ys = [150, 260, 930];
    ctx.save();
    ctx.font = `700 38px ${JP}`;
    ctx.textBaseline = 'middle';
    if (!this.chipWidths) {
      this.chipWidths = rows.map((row) => row.map((t) => ctx.measureText(t).width + 64));
    }
    // Speed grows toward the wipe, so the first half builds into the second.
    const travel = beat * 150 + Math.pow(span(beat, 5, 3), 3) * 900;
    const lit = Math.floor(beat * 2); // one chip lights up every half beat
    rows.forEach((row, r) => {
      const widths = this.chipWidths[r];
      const loop = widths.reduce((a, b) => a + b + 24, 0);
      const enter = span(beat, r * 0.15, 0.6, ease.expoOut);
      const dir = r % 2 ? 1 : -1;
      let offset = ((dir * travel) % loop + loop) % loop - loop;
      offset += dir * (1 - enter) * 1400;
      for (let x = offset, k = 0; x < W + loop; k++) {
        const i = k % row.length;
        const w = widths[i];
        if (x + w > 0 && x < W) {
          const hot = beat >= 4 && (lit + r * 3) % 7 === i;
          const pulse = hot ? 1 + 0.12 * Math.exp(-(beat * 2 % 1) * 6) : 1;
          ctx.save();
          ctx.translate(x + w / 2, ys[r]);
          ctx.scale(pulse, pulse);
          ctx.globalAlpha = r === 1 ? 1 : 0.8;
          ctx.fillStyle = hot ? BRAND.red : r === 1 ? BRAND.yellow : 'rgba(232,206,176,0.12)';
          ctx.strokeStyle = r === 1 ? BRAND.yellow : BRAND.cream;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.roundRect(-w / 2, -34, w, 68, 34);
          ctx.fill();
          if (r !== 1) ctx.stroke();
          ctx.fillStyle = r === 1 && !hot ? BRAND.ink : BRAND.cream;
          ctx.textAlign = 'center';
          ctx.fillText(row[i], 0, 2);
          ctx.restore();
        }
        x += w + 24;
      }
    });
    ctx.restore();
  },

  // ---------- part 2: like / subscribe / join ----------

  drawCta(ctx, beat, cue) {
    ctx.fillStyle = BRAND.yellow;
    ctx.fillRect(0, 0, W, H);
    stripes(ctx, beat);

    const head = span(beat, cue.hit + 0.2, 0.5, ease.expoOut);
    ctx.save();
    ctx.globalAlpha = head;
    ctx.font = `900 64px ${JP}`;
    ctx.fillStyle = BRAND.ink;
    ctx.fillText('応援よろしくお願いします！', 130, 190 - (1 - head) * 30);
    ctx.restore();

    const cards = cue.cta;
    const cardY = (i) => 290 + i * 210;
    cards.forEach((card, i) => this.drawCard(ctx, beat, card, i, cardY(i)));
    this.drawCursor(ctx, beat, cards, cardY);
    this.drawSign(ctx, beat, cue);
  },

  drawCard(ctx, beat, card, i, y) {
    const inn = span(beat, card.appear, 0.5, ease.expoOut);
    if (inn <= 0) return;
    const clicked = beat >= card.click;
    const press = clicked ? 1 - 0.05 * Math.exp(-(beat - card.click) * 14) : 1;
    const x = 130 - (1 - inn) * 900;
    const w = 860;
    const h = 170;
    const themes = [
      { bg: '#FFFFFF', fg: BRAND.ink },
      { bg: clicked ? '#E4E0DA' : BRAND.red, fg: clicked ? BRAND.ink : '#FFFFFF' },
      { bg: BRAND.ink, fg: BRAND.yellow },
    ];
    const theme = themes[i];
    ctx.save();
    ctx.translate(x + w / 2, y + h / 2);
    ctx.scale(press, press);
    ctx.shadowColor = 'rgba(28,20,17,0.3)';
    ctx.shadowBlur = 30;
    ctx.shadowOffsetY = 10;
    ctx.fillStyle = theme.bg;
    ctx.beginPath();
    ctx.roundRect(-w / 2, -h / 2, w, h, 36);
    ctx.fill();
    ctx.shadowColor = 'transparent';

    // Icon: the thumb jumps, the bell swings, the star spins — each on its click.
    const since = beat - card.click;
    ctx.save();
    ctx.translate(-w / 2 + 100, 4);
    if (clicked && i === 0) ctx.translate(0, -40 * Math.exp(-since * 6) * Math.abs(Math.sin(since * 12)));
    if (clicked && i === 1) ctx.rotate(0.5 * Math.exp(-since * 3) * Math.sin(since * 18));
    if (clicked && i === 2) ctx.rotate(Math.PI * 2 * ease.expoOut(clamp01(since / 0.6)));
    ctx.font = `90px ${EMOJI}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(card.icon, 0, 0);
    ctx.restore();

    const label = clicked && i === 1 ? '登録済み' : card.label;
    ctx.fillStyle = theme.fg;
    ctx.textBaseline = 'middle';
    ctx.font = `900 60px ${JP}`;
    ctx.fillText(label, -w / 2 + 190, -18);
    ctx.globalAlpha = 0.75;
    ctx.font = `500 32px ${JP}`;
    ctx.fillText(card.note, -w / 2 + 192, 46);
    ctx.globalAlpha = 1;
    if (clicked) {
      const tick = span(beat, card.click, 0.3, ease.backOut);
      ctx.save();
      ctx.translate(w / 2 - 80, 0);
      ctx.scale(tick, tick);
      ctx.fillStyle = BRAND.red;
      ctx.beginPath();
      ctx.arc(0, 0, 40, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 10;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(-17, 2);
      ctx.lineTo(-4, 15);
      ctx.lineTo(19, -12);
      ctx.stroke();
      ctx.restore();
    }
    ctx.restore();

    if (clicked && i === 0) {
      const up = span(beat, card.click, 1, ease.expoOut);
      ctx.save();
      ctx.globalAlpha = 1 - up;
      ctx.font = `900 56px ${JP}`;
      ctx.fillStyle = BRAND.red;
      ctx.fillText('+1', x + 150, y - up * 90);
      ctx.restore();
    }
    if (clicked && i === 2) this.sparkle(ctx, beat, card.click, x + 100, y + h / 2);
  },

  sparkle(ctx, beat, at, cx, cy) {
    const p = span(beat, at, 1.2, ease.expoOut);
    if (p <= 0 || p >= 1) return;
    const rand = mulberry32(77);
    ctx.save();
    ctx.globalAlpha = 1 - p;
    for (let i = 0; i < 28; i++) {
      const a = rand() * Math.PI * 2;
      const d = (80 + rand() * 260) * p;
      ctx.fillStyle = i % 2 ? BRAND.yellow : '#FFFFFF';
      ctx.beginPath();
      ctx.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, 4 + rand() * 7, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  },

  drawCursor(ctx, beat, cards, cardY) {
    // The pointer glides to each card (expo) and clicks on the card's beat.
    const home = { x: 1250, y: 1150 };
    const targets = cards.map((c, i) => ({ x: 720, y: cardY(i) + 110, at: c.click }));
    let pos = home;
    let prev = home;
    let from = cards[0].appear;
    for (const t of targets) {
      const p = span(beat, Math.max(from, t.at - 0.7), 0.6, ease.expoOut);
      pos = { x: lerp(prev.x, t.x, p), y: lerp(prev.y, t.y, p) };
      if (beat < t.at) break;
      prev = t;
      from = t.at + 0.2;
    }
    const last = cards[cards.length - 1].click;
    const leave = span(beat, last + 0.6, 0.6, ease.expoIn);
    pos = { x: lerp(pos.x, home.x, leave), y: lerp(pos.y, home.y, leave) };

    for (const t of targets) {
      const ring = span(beat, t.at, 0.4, ease.expoOut);
      if (ring <= 0 || ring >= 1) continue;
      ctx.save();
      ctx.strokeStyle = BRAND.ink;
      ctx.globalAlpha = 1 - ring;
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.arc(t.x, t.y, 20 + ring * 70, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    const pressed = targets.some((t) => beat >= t.at && beat < t.at + 0.12);
    ctx.save();
    ctx.translate(pos.x, pos.y);
    ctx.scale(pressed ? 0.85 : 1, pressed ? 0.85 : 1);
    ctx.fillStyle = '#FFFFFF';
    ctx.strokeStyle = BRAND.ink;
    ctx.lineWidth = 5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, 78);
    ctx.lineTo(20, 60);
    ctx.lineTo(34, 92);
    ctx.lineTo(48, 86);
    ctx.lineTo(34, 55);
    ctx.lineTo(60, 55);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  },

  drawSign(ctx, beat, cue) {
    // The logo on the right, bobbing with the beat; thanks under it; one last pulse.
    const inn = span(beat, cue.hit + 0.3, 0.5, ease.backOut);
    if (inn <= 0) return;
    const bob = Math.sin(beat * Math.PI) * 8 * (beat < cue.endAt ? 1 : 0);
    const end = beat >= cue.endAt ? 1 + 0.08 * Math.exp(-(beat - cue.endAt) * 6) : 1;
    const h = 520 * inn * end;
    const w = h * (logo.width / logo.height);
    ctx.drawImage(logo, 1440 - w / 2, 470 - h / 2 + bob, w, h);
    if (beat >= cue.endAt) {
      const p = span(beat, cue.endAt, 0.8, ease.expoOut);
      ctx.save();
      ctx.strokeStyle = BRAND.red;
      ctx.globalAlpha = 1 - p;
      ctx.lineWidth = lerp(30, 2, p);
      ctx.beginPath();
      ctx.arc(1440, 470, lerp(200, 520, p), 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    const thanks = span(beat, cue.thanksAt, 0.6, ease.expoOut);
    ctx.save();
    ctx.globalAlpha = thanks;
    ctx.font = `900 52px ${JP}`;
    ctx.textAlign = 'center';
    ctx.fillStyle = BRAND.ink;
    ctx.fillText('ご視聴ありがとうございました！', 1440, 850 + (1 - thanks) * 30);
    ctx.restore();
  },
};

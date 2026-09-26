// End card. Until cue.hit it is a full-screen showcase of the channel
// (outro-promo.js). From cue.hit it switches to the layout built around the
// YouTube end screen: two video elements down the left and a subscribe element
// at the bottom right (cue.endScreen) stay framed slots, and the asks and the
// thanks live in the space between them.
const JP = '"Noto Sans CJK JP", sans-serif';
const EMOJI = '"Noto Color Emoji", sans-serif';
const CENTER = { x: 700, y: 125, w: 815, h: 800 };
const SIDE = { x: 1545, w: 335 };
// The logo and name sit above the subscribe slot, which YouTube fills with a large button.
const LOGO_Y = 265;
const CARD_H = 240;
const CARD_GAP = 40;

variants.outro = {
  setup() {
    this.chipWidths = null;
  },

  draw(ctx, beat, cue) {
    if (beat < cue.hit) {
      outroPromo.draw(ctx, beat, cue);
      return;
    }
    // Layout elements time their entrances from the switch, not from zero.
    const local = beat - cue.hit;
    ctx.fillStyle = BRAND.yellow;
    ctx.fillRect(0, 0, W, H);
    stripes(ctx, beat);
    this.drawMarquee(ctx, beat, local, cue);
    this.drawSlots(ctx, beat, local, cue);
    this.drawSide(ctx, beat, local, cue);
    cue.cta.forEach((card, i) => this.drawCard(ctx, beat, cue, card, i));
    this.drawCursor(ctx, beat, cue);
  },

  cardY(i) {
    return CENTER.y + i * (CARD_H + CARD_GAP);
  },

  // ---------- always on ----------

  drawMarquee(ctx, beat, local, cue) {
    // Topic chips run along the top and bottom edges for the whole card,
    // so something is always moving even while the viewer reads.
    const rows = [cue.topics[0].concat(cue.topics[1]), cue.topics[2].concat(cue.topics[1])];
    const ys = [58, 1022];
    ctx.save();
    ctx.font = `700 30px ${JP}`;
    ctx.textBaseline = 'middle';
    if (!this.chipWidths) this.chipWidths = rows.map((row) => row.map((t) => ctx.measureText(t).width + 48));
    const travel = beat * 110;
    const lit = Math.floor(beat * 2);
    rows.forEach((row, r) => {
      const widths = this.chipWidths[r];
      const loop = widths.reduce((a, b) => a + b + 18, 0);
      const dir = r ? 1 : -1;
      const enter = span(local, r * 0.2, 0.7, ease.expoOut);
      let x = (((dir * travel) % loop) + loop) % loop - loop + dir * (1 - enter) * 1400;
      for (let k = 0; x < W + loop; k++) {
        const i = k % row.length;
        const w = widths[i];
        if (x + w > 0 && x < W) {
          const hot = (lit * 3 + r * 5) % row.length === i;
          ctx.fillStyle = hot ? BRAND.red : BRAND.ink;
          ctx.beginPath();
          ctx.roundRect(x, ys[r] - 27, w, 54, 27);
          ctx.fill();
          ctx.fillStyle = hot ? '#FFFFFF' : BRAND.cream;
          ctx.textAlign = 'center';
          ctx.fillText(row[i], x + w / 2, ys[r] + 1);
        }
        x += w + 18;
      }
    });
    ctx.restore();
  },

  drawSlots(ctx, beat, local, cue) {
    // YouTube covers these with its own elements; the frame makes them look planned.
    const { videos, subscribe } = cue.endScreen;
    const slots = videos.concat([subscribe]);
    slots.forEach(([x, y, w, h], i) => {
      const p = span(local, 0.2 + i * 0.25, 0.5, ease.expoOut);
      ctx.save();
      ctx.globalAlpha = p;
      ctx.fillStyle = 'rgba(28,20,17,0.16)';
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 22);
      ctx.fill();
      ctx.setLineDash([18, 12]);
      ctx.lineDashOffset = -beat * 30;
      ctx.lineWidth = 4;
      ctx.strokeStyle = BRAND.ink;
      ctx.stroke();
      ctx.restore();
    });
    ctx.save();
    ctx.font = `900 28px ${JP}`;
    ctx.fillStyle = BRAND.ink;
    ctx.globalAlpha = span(local, 0.4, 0.5);
    ctx.fillText('▶ 次に見るならこちら', videos[0][0] + 6, videos[0][1] - 14);
    ctx.textAlign = 'center';
    const nudge = 6 * Math.abs(Math.sin(beat * Math.PI));
    ctx.fillText('チャンネル登録はここ ↓', subscribe[0] + subscribe[2] / 2, subscribe[1] - 16 - nudge);
    ctx.restore();
  },

  drawSide(ctx, beat, local, cue) {
    const cx = SIDE.x + SIDE.w / 2;
    const inn = span(local, 0.3, 0.6, ease.backOut);
    const pulse = beat >= cue.endAt ? 1 + 0.1 * Math.exp(-(beat - cue.endAt) * 6) : 1;
    const bob = Math.sin(beat * Math.PI) * 6;
    const h = 330 * inn * pulse;
    const w = h * (logo.width / logo.height);
    if (h > 0) ctx.drawImage(logo, cx - w / 2, LOGO_Y - h / 2 + bob, w, h);
    if (beat >= cue.endAt) {
      const p = span(beat, cue.endAt, 0.8, ease.expoOut);
      ctx.save();
      ctx.strokeStyle = BRAND.red;
      ctx.globalAlpha = 1 - p;
      ctx.lineWidth = lerp(24, 2, p);
      ctx.beginPath();
      ctx.arc(cx, LOGO_Y, lerp(130, 330, p), 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    // Under the logo: who this is, then (near the end) thanks.
    const thanks = span(beat, cue.thanksAt, 0.6, ease.expoOut);
    ctx.save();
    ctx.textAlign = 'center';
    ctx.fillStyle = BRAND.ink;
    ctx.globalAlpha = span(local, 0.8, 0.5) * (1 - thanks);
    ctx.font = `900 40px ${JP}`;
    ctx.fillText('胡田昌彦', cx, 476);
    ctx.font = `700 21px ${JP}`;
    ctx.fillText('Windows / Azure / M365 / 生成AI', cx, 512);
    ctx.globalAlpha = thanks;
    ctx.font = `900 27px ${JP}`;
    ctx.fillText('ご視聴', cx, 468 + (1 - thanks) * 20);
    ctx.fillText('ありがとうございました！', cx, 508 + (1 - thanks) * 20);
    ctx.restore();
  },

  // ---------- the asks ----------

  drawCard(ctx, beat, cue, card, i) {
    const inn = span(beat, card.appear, 0.5, ease.expoOut);
    if (inn <= 0) return;
    const clicked = beat >= card.click;
    // After every card is in, the cards take turns glowing, two beats each.
    const last = cue.cta[cue.cta.length - 1].click + 1.5;
    // glowOrder lists whose turn it is; the card we most want clicked appears in it most often.
    const order = cue.glowOrder;
    const turn = beat >= last && beat < cue.endAt ? order[Math.floor((beat - last) / 2) % order.length] : -1;
    const glowing = turn === i;
    const glowAt = last + Math.floor((beat - last) / 2) * 2;
    const press = clicked ? 1 - 0.05 * Math.exp(-(beat - card.click) * 14) : 1;
    const lift = glowing ? 1 + 0.025 * Math.exp(-(beat - glowAt) * 3) : 1;
    const x = CENTER.x + (1 - inn) * 1300;
    const y = this.cardY(i);
    const w = CENTER.w;
    const themes = [
      { bg: '#FFFFFF', fg: BRAND.ink },
      { bg: clicked ? '#EFEBE6' : BRAND.red, fg: clicked ? BRAND.ink : '#FFFFFF' },
      { bg: BRAND.ink, fg: BRAND.yellow },
    ];
    const theme = themes[i];
    ctx.save();
    ctx.translate(x + w / 2, y + CARD_H / 2);
    ctx.scale(press * lift, press * lift);
    ctx.shadowColor = 'rgba(28,20,17,0.28)';
    ctx.shadowBlur = glowing ? 40 : 24;
    ctx.shadowOffsetY = 8;
    ctx.fillStyle = theme.bg;
    ctx.beginPath();
    ctx.roundRect(-w / 2, -CARD_H / 2, w, CARD_H, 30);
    ctx.fill();
    ctx.shadowColor = 'transparent';
    if (glowing) {
      ctx.strokeStyle = BRAND.red;
      ctx.lineWidth = 6;
      ctx.stroke();
    }
    if (card.badge) this.drawBadge(ctx, beat, card, -w / 2 + 170, -CARD_H / 2);

    // Icons move on their click and again on their turn to glow.
    const since = Math.min(clicked ? beat - card.click : 99, glowing ? beat - glowAt : 99);
    ctx.save();
    ctx.translate(-w / 2 + 95, 0);
    if (since < 3) {
      if (i === 0) ctx.translate(0, -34 * Math.exp(-since * 6) * Math.abs(Math.sin(since * 12)));
      if (i === 1) ctx.rotate(0.5 * Math.exp(-since * 3) * Math.sin(since * 18));
      if (i === 2) ctx.rotate(Math.PI * 2 * ease.expoOut(clamp01(since / 0.6)));
    }
    ctx.font = `96px ${EMOJI}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(card.icon, 0, 4);
    ctx.restore();

    const label = clicked && i === 1 ? '登録済み・通知オン' : card.label;
    ctx.fillStyle = theme.fg;
    ctx.textBaseline = 'middle';
    ctx.font = `900 52px ${JP}`;
    ctx.fillText(label, -w / 2 + 180, card.link ? -40 : -30);
    ctx.globalAlpha = 0.8;
    ctx.font = `500 29px ${JP}`;
    ctx.fillText(card.note, -w / 2 + 182, card.link ? 18 : 38);
    ctx.globalAlpha = 1;
    if (card.link) {
      ctx.font = `700 28px ${JP}`;
      ctx.fillStyle = BRAND.yellow;
      ctx.fillText(`${card.link} →`, -w / 2 + 182, 70);
    }
    if (clicked) this.drawCheck(ctx, beat, card.click, w / 2 - 60);
    ctx.restore();

    if (clicked && i === 0) {
      const up = span(beat, card.click, 1, ease.expoOut);
      ctx.save();
      ctx.globalAlpha = 1 - up;
      ctx.font = `900 50px ${JP}`;
      ctx.fillStyle = BRAND.red;
      ctx.fillText('+1', x + 140, y + 20 - up * 80);
      ctx.restore();
    }
    if (clicked && i === 2) this.sparkle(ctx, beat, card.click, x + 95, y + CARD_H / 2);
  },

  drawBadge(ctx, beat, card, x, top) {
    // A tab on the card's top edge, popping in with the card and nodding on the beat.
    const p = span(beat, card.appear + 0.3, 0.4, ease.backOut);
    if (p <= 0) return;
    const nod = 1 + 0.06 * Math.exp(-(beat % 1) * 8);
    ctx.save();
    ctx.translate(x + 80, top);
    ctx.scale(p * nod, p * nod);
    ctx.fillStyle = BRAND.red;
    ctx.beginPath();
    ctx.roundRect(-80, -26, 160, 52, 26);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.font = `900 30px ${JP}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(card.badge, 0, 2);
    ctx.restore();
  },

  drawCheck(ctx, beat, at, x) {
    const tick = span(beat, at, 0.3, ease.backOut);
    ctx.save();
    ctx.translate(x, 0);
    ctx.scale(tick, tick);
    ctx.fillStyle = BRAND.red;
    ctx.beginPath();
    ctx.arc(0, 0, 34, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 9;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(-15, 2);
    ctx.lineTo(-4, 13);
    ctx.lineTo(16, -10);
    ctx.stroke();
    ctx.restore();
  },

  sparkle(ctx, beat, at, cx, cy) {
    const p = span(beat, at, 1.2, ease.expoOut);
    if (p <= 0 || p >= 1) return;
    const rand = mulberry32(77);
    ctx.save();
    ctx.globalAlpha = 1 - p;
    for (let i = 0; i < 28; i++) {
      const a = rand() * Math.PI * 2;
      const d = (70 + rand() * 240) * p;
      ctx.fillStyle = i % 2 ? BRAND.yellow : '#FFFFFF';
      ctx.beginPath();
      ctx.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, 4 + rand() * 7, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  },

  drawCursor(ctx, beat, cue) {
    // The pointer glides to each card (expo), clicks on the card's beat, then leaves.
    const home = { x: 1300, y: 1180 };
    const targets = cue.cta.map((c, i) => ({ x: 1230, y: this.cardY(i) + 150, at: c.click }));
    let prev = home;
    let pos = home;
    let from = cue.cta[0].appear;
    for (const t of targets) {
      const p = span(beat, Math.max(from, t.at - 0.7), 0.6, ease.expoOut);
      pos = { x: lerp(prev.x, t.x, p), y: lerp(prev.y, t.y, p) };
      if (beat < t.at) break;
      prev = t;
      from = t.at + 0.2;
    }
    const leave = span(beat, targets[targets.length - 1].at + 0.6, 0.6, ease.expoIn);
    pos = { x: lerp(pos.x, home.x, leave), y: lerp(pos.y, home.y, leave) };
    if (leave >= 1) return;

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
};

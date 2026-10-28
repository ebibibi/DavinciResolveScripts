// えびフライ asks for a subscription, switching pose on every half beat, then all poses line up
// and the subscribe button is pressed on the hit.
const EBI_POSES = ['standing', 'glasses', 'faceup', 'ageage', 'rockstar', 'dark', 'sleeping'];
const EBI_FILES = {
  standing: 'ebi-standing.png', glasses: 'ebi-glasses-flash.png', faceup: 'ebi-face-up.png',
  ageage: 'ebi-ageage.png', rockstar: 'ebi-rockstar.png', dark: 'ebi-dark.png', sleeping: 'ebi-sleeping.png',
};
const ebiImages = {};

function drawEbi(ctx, name, x, footY, height, rotation = 0, alpha = 1) {
  const img = ebiImages[name];
  const w = height * (img.width / img.height);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(x, footY);
  ctx.rotate(rotation);
  ctx.drawImage(img, -w / 2, -height, w, height);
  ctx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function speechBubble(ctx, beat, cue) {
  const p = span(beat, 0, 0.6, ease.expoOut);
  if (p <= 0) return;
  const [first, second] = cue.lines;
  ctx.save();
  ctx.translate(W / 2, 215);
  ctx.scale(p, p);
  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = BRAND.ink;
  ctx.lineWidth = 12;
  roundRect(ctx, -620, -185, 1240, 330, 70);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(-60, 139);
  ctx.lineTo(0, 225);
  ctx.lineTo(60, 139);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.fillRect(-52, 127, 104, 18);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const s1 = span(beat, 0.25, 0.4, ease.expoOut);
  if (s1 > 0) {
    ctx.save();
    ctx.translate(0, -85);
    ctx.scale(s1, s1);
    ctx.font = '900 140px "Noto Sans CJK JP", sans-serif';
    ctx.fillStyle = BRAND.red;
    ctx.fillText(first, 0, 0);
    ctx.restore();
  }
  const s2 = span(beat, 0.9, 0.4, ease.expoOut);
  if (s2 > 0) {
    ctx.save();
    ctx.translate(0, 65);
    ctx.scale(s2, s2);
    ctx.font = '900 120px "Noto Sans CJK JP", sans-serif';
    ctx.fillStyle = BRAND.ink;
    ctx.fillText(second, 0, 0);
    ctx.restore();
  }
  ctx.restore();
}

function subscribeButton(ctx, beat, hit) {
  const p = span(beat, hit - 0.5, 0.4, ease.backOut);
  if (p <= 0) return;
  const press = beat >= hit ? 1 - 0.12 * Math.exp(-(beat - hit) * 10) : 1;
  const done = beat >= hit;
  ctx.save();
  ctx.translate(W / 2, H - 150);
  ctx.scale(p * press, p * press);
  ctx.fillStyle = done ? '#606060' : '#CC0000';
  roundRect(ctx, -330, -75, 660, 150, 75);
  ctx.fill();
  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '900 78px "Noto Sans CJK JP", sans-serif';
  ctx.fillText(done ? '登録済み ✓' : 'チャンネル登録', 0, 4);
  ctx.restore();
  // a hand-drawn cursor arrives just before the hit
  const c = span(beat, hit - 0.45, 0.4, ease.expoOut);
  if (c > 0 && beat < hit + 1) {
    ctx.save();
    ctx.translate(lerp(W / 2 + 520, W / 2 + 90, c), lerp(H + 60, H - 120, c));
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = BRAND.ink;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, 80);
    ctx.lineTo(22, 60);
    ctx.lineTo(38, 96);
    ctx.lineTo(52, 90);
    ctx.lineTo(36, 54);
    ctx.lineTo(64, 54);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
}

variants.subscribe = {
  async setup() {
    await Promise.all(Object.keys(EBI_FILES).map(async (name) => {
      const img = new Image();
      img.src = `characters/${EBI_FILES[name]}`;
      await img.decode();
      ebiImages[name] = img;
    }));
  },
  draw(ctx, beat, cue) {
    ctx.fillStyle = BRAND.yellow;
    ctx.fillRect(0, 0, W, H);
    stripes(ctx, beat * 0.4);

    // a few poses rise in one by one and stay, side by side
    const n = cue.poses.length;
    cue.poses.forEach((name, i) => {
      const p = span(beat, 0.4 + i * cue.every, 0.6, ease.expoOut);
      if (p <= 0) return;
      const x = W / 2 + (i - (n - 1) / 2) * 400;
      const sway = Math.sin(beat * Math.PI * 0.5 + i) * 0.025;
      const hop = beat >= cue.hit ? Math.sin(clamp01((beat - cue.hit) / 0.6) * Math.PI) * 30 : 0;
      drawEbi(ctx, name, x, H - 235 + (1 - p) * 120 - hop, 400, sway, p);
    });
    speechBubble(ctx, beat, cue);
    subscribeButton(ctx, beat, cue.hit);
  },
};

// Every event is written in beats. render.py and make_audio.py read the same
// timeline.json, so picture and sound cannot drift apart.

const BRAND = {
  yellow: '#F2B632',
  cream: '#E8CEB0',
  red: '#C8102E',
  ink: '#1C1411',
};

const SUBFRAMES = 10;      // motion blur samples per frame (5 left visible steps)
const SHUTTER = 0.5;       // fraction of a frame the virtual shutter stays open
const LOGO_HEIGHT = 600;

// ---------- maths ----------

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const lerp = (a, b, t) => a + (b - a) * t;

const ease = {
  linear: (t) => t,
  expoOut: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  expoIn: (t) => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
  backOut: (t) => {
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },
  bounceOut: (t) => {
    const n1 = 7.5625;
    const d1 = 2.75;
    if (t < 1 / d1) return n1 * t * t;
    if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
    if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
    return n1 * (t -= 2.625 / d1) * t + 0.984375;
  },
  inOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
};

/** 0..1 progress of an event that starts on `from` and lasts `length` beats. */
function span(beat, from, length, curve = ease.linear) {
  return curve(clamp01((beat - from) / length));
}

// ---------- shared drawing ----------

let W = 1920;
let H = 1080;
let logo = null;
let logoPoints = [];

function drawLogo(ctx, scale = 1, alpha = 1, rotation = 0) {
  const h = LOGO_HEIGHT * scale;
  const w = h * (logo.width / logo.height);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(W / 2, H / 2);
  ctx.rotate(rotation);
  ctx.drawImage(logo, -w / 2, -h / 2, w, h);
  ctx.restore();
}

/** Opaque logo pixels as points in canvas space, each with its own colour. */
function sampleLogo(count, seed) {
  const c = document.createElement('canvas');
  c.width = logo.width;
  c.height = logo.height;
  const g = c.getContext('2d');
  g.drawImage(logo, 0, 0);
  const data = g.getImageData(0, 0, c.width, c.height).data;
  const opaque = [];
  for (let y = 0; y < c.height; y += 2) {
    for (let x = 0; x < c.width; x += 2) {
      const i = (y * c.width + x) * 4;
      if (data[i + 3] > 200) opaque.push([x, y, data[i], data[i + 1], data[i + 2]]);
    }
  }
  const rand = mulberry32(seed);
  const scale = LOGO_HEIGHT / logo.height;
  const points = [];
  for (let n = 0; n < count; n++) {
    const [x, y, r, gg, b] = opaque[Math.floor(rand() * opaque.length)];
    points.push({
      x: W / 2 + (x - logo.width / 2) * scale,
      y: H / 2 + (y - logo.height / 2) * scale,
      color: `rgb(${r},${gg},${b})`,
    });
  }
  return points;
}

function shockwave(ctx, beat, at, color, maxRadius = 900) {
  const p = span(beat, at, 0.6, ease.expoOut);
  if (p <= 0 || p >= 1) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.globalAlpha = 1 - p;
  ctx.lineWidth = lerp(60, 2, p);
  ctx.beginPath();
  ctx.arc(W / 2, H / 2, lerp(40, maxRadius, p), 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function flash(ctx, beat, at, length = 0.12) {
  const p = span(beat, at, length);
  if (p <= 0 || p >= 1) return;
  ctx.save();
  ctx.fillStyle = '#fff';
  ctx.globalAlpha = 0.85 * (1 - p);
  ctx.fillRect(0, 0, W, H);
  ctx.restore();
}

/** Logo landing on the hit beat: pop in with overshoot, then settle. */
function landLogo(ctx, beat, hit, from = 0.4) {
  const p = span(beat, hit, 0.5, ease.backOut);
  if (beat < hit) return;
  drawLogo(ctx, lerp(from, 1, p), clamp01((beat - hit) * 8));
}

// ---------- variants ----------

const variants = {};

// ---------- helpers several variants share ----------

function stripes(ctx, beat) {
  ctx.save();
  ctx.globalAlpha = 0.12;
  ctx.fillStyle = BRAND.cream;
  const offset = (beat * 120) % 160;
  ctx.translate(W / 2, H / 2);
  ctx.rotate(-0.35);
  for (let x = -1600 - offset; x < 1600; x += 160) ctx.fillRect(x, -1200, 60, 2400);
  ctx.restore();
}

/** Confetti thrown outward from the centre on the hit beat. */
function burst(ctx, beat, at, seed) {
  const p = span(beat, at, 1.4, ease.expoOut);
  if (p <= 0) return;
  const rand = mulberry32(seed);
  const colors = [BRAND.red, BRAND.cream, BRAND.ink, '#ffffff'];
  ctx.save();
  ctx.globalAlpha = 1 - span(beat, at + 0.8, 1.2);
  for (let i = 0; i < 180; i++) {
    const angle = rand() * Math.PI * 2;
    const dist = (300 + rand() * 900) * p;
    const size = 8 + rand() * 18;
    ctx.fillStyle = colors[i % colors.length];
    ctx.save();
    ctx.translate(W / 2 + Math.cos(angle) * dist, H / 2 + Math.sin(angle) * dist + p * p * 120);
    ctx.rotate(rand() * 6 + p * 8);
    ctx.fillRect(-size / 2, -size / 4, size, size / 2);
    ctx.restore();
  }
  ctx.restore();
}


function blend(c1, c2, t) {
  const parse = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const [a, b] = [parse(c1), parse(c2)];
  return `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], t))).join(',')})`;
}


// ---------- finishing ----------

let grainTile = null;

function makeGrain() {
  const size = 256;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const g = c.getContext('2d');
  const img = g.createImageData(size, size);
  const rand = mulberry32(99);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.floor(rand() * 255);
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return c;
}

function grain(ctx, frame) {
  const rand = mulberry32(frame + 1);
  ctx.save();
  ctx.globalAlpha = 0.06;
  ctx.globalCompositeOperation = 'overlay';
  ctx.translate(-Math.floor(rand() * 256), -Math.floor(rand() * 256));
  ctx.fillStyle = ctx.createPattern(grainTile, 'repeat');
  ctx.fillRect(0, 0, W + 256, H + 256);
  ctx.restore();
}

function vignette(ctx) {
  const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 1.05);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(0,0,0,0.26)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
}

/** Split red / green / blue sideways, then shear a few horizontal slices. */
function glitch(ctx, source, frame, strength) {
  const rand = mulberry32(frame * 31 + 5);
  const shift = Math.round(24 * strength);
  ctx.save();
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, W, H);
  ctx.globalCompositeOperation = 'lighter';
  const g = channel.getContext('2d');
  [['#ff0000', -shift], ['#00ff00', 0], ['#0000ff', shift]].forEach(([color, dx]) => {
    g.globalCompositeOperation = 'source-over';
    // Enlarged, then offset inside the layer, so a shifted channel still covers every edge.
    g.drawImage(source, dx - shift, 0, W + shift * 2, H);
    g.globalCompositeOperation = 'multiply';
    g.fillStyle = color;
    g.fillRect(0, 0, W, H);
    ctx.drawImage(channel, 0, 0);
  });
  ctx.restore();
  for (let i = 0; i < 7; i++) {
    const y = Math.floor(rand() * H);
    const h = 8 + Math.floor(rand() * 60);
    const dx = Math.round((rand() - 0.5) * 160 * strength);
    ctx.drawImage(ctx.canvas, 0, y, W, h, dx, y, W, h);
  }
}

// ---------- frame loop ----------

let out;
let scene;
let accum;
let channel;
let timeline;
let variant;
let variantSpec;

function canvasOf(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

window.setup = async function (config, variantName, logoUrl) {
  timeline = config;
  W = config.width;
  H = config.height;
  out = document.getElementById('out');
  out.width = W;
  out.height = H;
  scene = canvasOf(W, H);
  accum = canvasOf(W, H);
  channel = canvasOf(W, H);
  logo = new Image();
  logo.src = logoUrl;
  await logo.decode();
  logoPoints = sampleLogo(4200, 3);
  grainTile = makeGrain();
  variant = variants[variantName];
  variantSpec = config.variants[variantName];
  if (!variant) throw new Error(`Unknown variant: ${variantName}`);
  variant.setup();
  // A variant may run longer than a stinger (the end card does) and hit elsewhere.
  const beats = variantSpec.beats ?? config.beats;
  return Math.round((beats * 60 / config.bpm) * config.fps);
};

window.renderFrame = function (frame) {
  const { bpm, fps } = timeline;
  const hitBeat = variantSpec.hitBeat ?? timeline.hitBeat;
  const cue = { ...variantSpec, hit: hitBeat };
  const sceneCtx = scene.getContext('2d');
  const accumCtx = accum.getContext('2d');

  // Motion blur: draw the scene at several instants inside the shutter and average.
  for (let s = 0; s < SUBFRAMES; s++) {
    const t = (frame + (s / SUBFRAMES - 0.5) * SHUTTER) / fps;
    const beat = Math.max(0, t) * bpm / 60;
    sceneCtx.save();
    variant.draw(sceneCtx, beat, cue);
    sceneCtx.restore();
    accumCtx.globalAlpha = 1 / (s + 1);
    accumCtx.drawImage(scene, 0, 0);
  }
  accumCtx.globalAlpha = 1;

  const ctx = out.getContext('2d');
  const beat = (frame / fps) * bpm / 60;
  const glitchStrength = Math.max(
    span(beat, hitBeat - 0.3, 0.3) * (beat < hitBeat ? 0.6 : 0),
    1 - span(beat, hitBeat, 0.2),
  );
  if (glitchStrength > 0.05 && beat >= hitBeat - 0.3 && beat < hitBeat + 0.2) {
    glitch(ctx, accum, frame, glitchStrength);
  } else {
    ctx.drawImage(accum, 0, 0);
  }
  grain(ctx, frame);
  vignette(ctx);
};

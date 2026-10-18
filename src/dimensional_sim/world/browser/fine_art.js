/** Fine sprite renderer: turns a coarse colour grid (cell sprites on 4x7 px cells, the pixel
 * avatar on 2x2 px cells) into high-density lit art, painted once per pose at the render
 * resolution and cached.
 *
 * Every device pixel is shaded from two height fields: the whole silhouette (a soft volume -
 * the sprite reads as a body, not a flat cut-out) and its colour region (each part - a horn, a
 * sleeve, a stone - is rounded on its own). Light comes from the upper left, like the trees and
 * rocks. Convex cell corners are rounded off, a soft dark outline hugs the shape, and glyph
 * texture characters are drawn as small vector marks (strokes, dots, rings, waves) in the
 * role's ink instead of font text, so they stay crisp at any zoom.
 *
 * Presentation only and deterministic: the same grid paints the same pixels. Without a DOM
 * (node tests) `fineCanvas` returns null and callers fall back to their direct paint.
 */
export const OUTLINE_RGB = [7, 10, 6];
let RES = 2;
const cache = new Map();
/** Called by art.setResolution: fine sprites are repainted at the new density. */
export function fineResolution(res) {
  if (res !== RES) { RES = res; cache.clear(); }
}
export const fineCount = () => cache.size;

const LIGHT = (() => { const v = [-.5, -.65, .6], n = Math.hypot(...v); return v.map(c => c / n); })();
const hex = color => {
  const h = color.replace('#', '');
  const full = h.length === 3 ? [...h].map(c => c + c).join('') : h.slice(0, 6);
  return [0, 2, 4].map(i => parseInt(full.slice(i, i + 2), 16));
};
const smooth = t => t * t * (3 - 2 * t);

/** Two-pass chamfer distance (device px) from every pixel to the nearest pixel where
 * `seed(i)` is true. */
function chamfer(w, h, seed) {
  const d = new Float32Array(w * h), BIG = 1e6, D = Math.SQRT2;
  for (let i = 0; i < w * h; i++) d[i] = seed(i) ? 0 : BIG;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x; let v = d[i];
    if (x > 0) v = Math.min(v, d[i - 1] + 1);
    if (y > 0) { v = Math.min(v, d[i - w] + 1); if (x > 0) v = Math.min(v, d[i - w - 1] + D); if (x < w - 1) v = Math.min(v, d[i - w + 1] + D); }
    d[i] = v;
  }
  for (let y = h - 1; y >= 0; y--) for (let x = w - 1; x >= 0; x--) {
    const i = y * w + x; let v = d[i];
    if (x < w - 1) v = Math.min(v, d[i + 1] + 1);
    if (y < h - 1) { v = Math.min(v, d[i + w] + 1); if (x < w - 1) v = Math.min(v, d[i + w + 1] + D); if (x > 0) v = Math.min(v, d[i + w - 1] + D); }
    d[i] = v;
  }
  return d;
}

/**
 * A cached fine canvas for a colour grid, or null without a DOM.
 * spec: {key, cols, rows, cw, ch, color(c, r) -> '#rrggbb' | null, mark(c, r) -> {ch, ink} | null,
 *        round (corner radius as a fraction of the smaller cell side), flat (flash: no texture)}
 * The canvas has logical size (cols*cw + 2, rows*ch + 2): a 1 px border for the outline, so
 * draw it at (left - 1, top - 1). Logical size is on canvas.lw / canvas.lh.
 */
export function fineCanvas(spec) {
  const key = spec.key;
  if (cache.has(key)) return cache.get(key);
  if (typeof document === 'undefined' || !document.createElement) return null;
  const {cols, rows, cw, ch} = spec, P = 1, k = RES;
  const W = cols * cw + 2 * P, H = rows * ch + 2 * P, DW = Math.ceil(W * k), DH = Math.ceil(H * k);
  // Cell colours and region ids.
  const palette = [], index = new Map(), grid = new Int16Array(cols * rows).fill(-1);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const color = spec.color(c, r);
    if (!color) continue;
    if (!index.has(color)) { index.set(color, palette.length); palette.push(hex(color)); }
    grid[r * cols + c] = index.get(color);
  }
  const at = (c, r) => (c < 0 || r < 0 || c >= cols || r >= rows) ? -1 : grid[r * cols + c];
  const rr = Math.min(cw, ch) * (spec.round ?? .5);
  // Rasterise at device resolution, rounding convex corners.
  const region = new Int16Array(DW * DH).fill(-1);
  for (let j = 0; j < DH; j++) for (let i = 0; i < DW; i++) {
    const lx = (i + .5) / k - P, ly = (j + .5) / k - P;
    const c = Math.floor(lx / cw), r = Math.floor(ly / ch), g = at(c, r);
    if (g < 0) continue;
    const fx = lx - c * cw, fy = ly - r * ch;
    let cut = false;
    for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
      if (at(c + sx, r) >= 0 || at(c, r + sy) >= 0 || at(c + sx, r + sy) >= 0) continue;
      const ox = sx < 0 ? rr - fx : fx - (cw - rr), oy = sy < 0 ? rr - fy : fy - (ch - rr);
      if (ox > 0 && oy > 0 && ox * ox + oy * oy > rr * rr) { cut = true; break; }
    }
    if (!cut) region[j * DW + i] = g;
  }
  const inside = i => region[i] >= 0;
  const dOut = chamfer(DW, DH, i => !inside(i));
  const dIn = chamfer(DW, DH, inside);
  const dReg = chamfer(DW, DH, i => {
    if (!inside(i)) return true;
    const x = i % DW, g = region[i];
    return (x > 0 && region[i - 1] !== g) || (x < DW - 1 && region[i + 1] !== g)
      || (i >= DW && region[i - DW] !== g) || (i < DW * (DH - 1) && region[i + DW] !== g);
  });
  const Rg = 3.2 * k, Rr = 1.4 * k;
  const height = new Float32Array(DW * DH);
  for (let i = 0; i < DW * DH; i++) if (inside(i))
    height[i] = .62 * smooth(Math.min(1, dOut[i] / Rg)) + .38 * smooth(Math.min(1, dReg[i] / Rr));
  const img = new ImageData(DW, DH), px = img.data, S = 1.9;
  const flash = spec.flat ? hex(spec.flat) : null;
  for (let j = 0; j < DH; j++) for (let i = 0; i < DW; i++) {
    const n = j * DW + i, o = n * 4;
    if (!inside(n)) {
      const d = dIn[n] / k;   // soft outline: solid for ~0.8 px, fading by 1.3 px
      if (d <= 1.3) { const a = d <= .8 ? 1 : 1 - (d - .8) / .5;
        px[o] = OUTLINE_RGB[0]; px[o + 1] = OUTLINE_RGB[1]; px[o + 2] = OUTLINE_RGB[2]; px[o + 3] = Math.round(255 * a); }
      continue;
    }
    const hx = (i > 0 && inside(n - 1) ? height[n - 1] : 0), hX = (i < DW - 1 && inside(n + 1) ? height[n + 1] : 0);
    const hy = (j > 0 && inside(n - DW) ? height[n - DW] : 0), hY = (j < DH - 1 && inside(n + DW) ? height[n + DW] : 0);
    const gx = (hX - hx) / 2 * k * S, gy = (hY - hy) / 2 * k * S;
    const len = Math.hypot(gx, gy, 1);
    const light = Math.max(0, (-gx * LIGHT[0] - gy * LIGHT[1] + LIGHT[2]) / len);
    const ly = ((j + .5) / k - P) / (H - 2 * P);
    let f = (.5 + .85 * light) * (1.07 - .14 * ly);
    const base = flash || palette[region[n]];
    let rgb = base.map(v => Math.min(255, v * f));
    if (light > .82) { const s = (light - .82) * 1.1; rgb = rgb.map(v => v + (255 - v) * s * .5); }   // a soft sheen
    if (dOut[n] < .6 * k) rgb = rgb.map(v => v * .82);   // inner edge, so the outline reads clean
    px[o] = rgb[0]; px[o + 1] = rgb[1]; px[o + 2] = rgb[2]; px[o + 3] = 255;
  }
  const canvas = document.createElement('canvas');
  canvas.width = DW; canvas.height = DH; canvas.lw = W; canvas.lh = H;
  const ctx = canvas.getContext('2d');
  ctx.putImageData(img, 0, 0);
  if (spec.mark && !flash) {
    ctx.scale(k, k); ctx.translate(P, P);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      if (at(c, r) < 0) continue;
      const m = spec.mark(c, r);
      if (m && m.ch !== ' ') drawMark(ctx, m.ch, c * cw, r * ch, cw, ch, m.ink);
    }
  }
  cache.set(key, canvas);
  return canvas;
}

/** A glyph texture character as a small vector mark inside a cw x ch cell at (x, y). */
export function drawMark(ctx, glyph, x, y, cw, ch, ink) {
  const X = u => x + u * cw, Y = v => y + v * ch;
  ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = Math.max(.5, cw * .16);
  ctx.globalAlpha = .92;
  const line = (...pts) => { ctx.beginPath(); ctx.moveTo(X(pts[0]), Y(pts[1])); for (let i = 2; i < pts.length; i += 2) ctx.lineTo(X(pts[i]), Y(pts[i + 1])); ctx.stroke(); };
  const dot = (u, v, r = .11) => { ctx.beginPath(); ctx.arc(X(u), Y(v), r * cw, 0, Math.PI * 2); ctx.fill(); };
  const ring = (u, v, r, fill = false) => { ctx.beginPath(); ctx.ellipse(X(u), Y(v), r * cw, r * cw * 1.05, 0, 0, Math.PI * 2); fill ? ctx.fill() : ctx.stroke(); };
  switch (glyph) {
    case '|': line(.5, .1, .5, .9); break;
    case '/': line(.85, .1, .15, .9); break;
    case '\\': line(.15, .1, .85, .9); break;
    case '-': line(.15, .5, .85, .5); break;
    case '_': line(0, .9, 1, .9); break;
    case '=': line(.1, .38, .9, .38); line(.1, .64, .9, .64); break;
    case '~': ctx.beginPath(); ctx.moveTo(X(.05), Y(.55)); ctx.bezierCurveTo(X(.3), Y(.3), X(.45), Y(.3), X(.5), Y(.5));
      ctx.bezierCurveTo(X(.55), Y(.7), X(.7), Y(.7), X(.95), Y(.45)); ctx.stroke(); break;
    case '.': dot(.5, .78); break;
    case ',': dot(.5, .7); line(.5, .72, .35, .9); break;
    case "'": line(.5, .1, .45, .32); break;
    case '"': line(.32, .1, .3, .32); line(.68, .1, .66, .32); break;
    case '`': line(.35, .1, .55, .28); break;
    case ':': dot(.5, .36); dot(.5, .72); break;
    case ';': dot(.5, .34); dot(.5, .68); line(.5, .7, .36, .88); break;
    case 'o': ring(.5, .55, .26); break;
    case 'O': case '0': ring(.5, .5, .36); break;
    case '@': ring(.5, .5, .38); dot(.5, .5, .14); break;
    case '*': line(.5, .25, .5, .75); line(.2, .5, .8, .5); line(.28, .32, .72, .68); line(.72, .32, .28, .68); break;
    case '+': line(.5, .25, .5, .75); line(.2, .5, .8, .5); break;
    case 'x': case 'X': line(.2, .25, .8, .75); line(.8, .25, .2, .75); break;
    case '#': line(.35, .15, .3, .85); line(.7, .15, .65, .85); line(.1, .38, .9, .38); line(.1, .64, .9, .64); break;
    case '^': line(.15, .6, .5, .2, .85, .6); break;
    case 'v': case 'V': line(.15, .3, .5, .75, .85, .3); break;
    case '<': line(.8, .2, .2, .5, .8, .8); break;
    case '>': line(.2, .2, .8, .5, .2, .8); break;
    case '(': ctx.beginPath(); ctx.ellipse(X(.85), Y(.5), .55 * cw, .4 * ch, 0, Math.PI * .65, Math.PI * 1.35); ctx.stroke(); break;
    case ')': ctx.beginPath(); ctx.ellipse(X(.15), Y(.5), .55 * cw, .4 * ch, 0, -Math.PI * .35, Math.PI * .35); ctx.stroke(); break;
    case '[': line(.75, .12, .3, .12, .3, .88, .75, .88); break;
    case ']': line(.25, .12, .7, .12, .7, .88, .25, .88); break;
    default:
      ctx.font = `${Math.round(ch * .9)}px Consolas, "Liberation Mono", monospace`;
      ctx.textBaseline = 'top'; ctx.textAlign = 'left'; ctx.fillText(glyph, x, y);
  }
  ctx.globalAlpha = 1;
}

/** Fine canvas for a cell sprite ({paint, glyph}) with role colours {role: {fill, ink}}. */
let roleIds = new WeakMap(), nextRoleId = 0;
export function cellSpriteCanvas(sprite, roles, cw, ch, {flash = null} = {}) {
  if (!roleIds.has(roles)) roleIds.set(roles, ++nextRoleId);
  const key = `cell|${roleIds.get(roles)}|${cw}x${ch}|${flash || ''}|${sprite.paint.join('/')}|${sprite.glyph.join('/')}`;
  return fineCanvas({key, cols: sprite.paint[0].length, rows: sprite.paint.length, cw, ch, flat: flash,
    color: (c, r) => { const role = sprite.paint[r][c]; return role === ' ' ? null : roles[role]?.fill ?? null; },
    mark: (c, r) => { const role = sprite.paint[r][c]; return role === ' ' ? null : {ch: sprite.glyph[r]?.[c] ?? ' ', ink: roles[role]?.ink}; }});
}

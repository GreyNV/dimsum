/** ASCII shader: the world's trees, rocks, actors and props are shaded as hidden pictures and
 * shown as text, the way an ASCII post-process reads a lit 3D scene.
 *
 * The picture is read in small character cells. For every cell:
 *   - an edge (a silhouette, or a sharp step in light) becomes a stroke glyph along it:
 *     '|' for an upright edge, '-' or '_' for a level one, '/' and '\' for the diagonals;
 *   - otherwise the cell's light picks a glyph by ink - '.' and ':' in the shade, 'c' 'o' 'Q'
 *     in the mid tones, '#' '8' '@' '$' where the light is strongest - with a little stable
 *     variety among glyphs of the same weight, so flat areas shimmer like type, not tiles;
 *   - the glyph takes the cell's own colour, lifted toward the light; behind the figure lies a
 *     faint dark ground so the text reads over grass, but there is no solid backing: the gaps
 *     between characters stay open.
 * Glyph weights are measured once from the real font. Presentation only; without a DOM
 * nothing here runs.
 */
export const CELL_W = 1.4, CELL_H = 2.5;
export const FONT = '"DejaVu Sans Mono", Consolas, "Liberation Mono", Menlo, monospace';
/** Candidate glyphs (no edge strokes: those are chosen from the edges). */
export const GLYPHS = " .'`^\",:;Il!i><~+?][}{1)(tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";
const OUTLINE = 'rgba(4, 7, 4, .58)';
const ramps = new Map();
export const asciiReady = () => typeof document !== 'undefined' && !!document.createElement;

/** Glyphs sorted by measured ink (0 = blank .. 1 = the densest). */
function glyphRamp(set = GLYPHS) {
  if (ramps.has(set)) return ramps.get(set);
  const W = 20, H = 34, c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d', {willReadFrequently: true});
  const list = [];
  for (const ch of set) {
    g.clearRect(0, 0, W, H); g.fillStyle = '#fff';
    g.font = `${H}px ${FONT}`; g.textBaseline = 'top';
    g.fillText(ch, 0, 0);
    const d = g.getImageData(0, 0, W, H).data;
    let ink = 0;
    for (let i = 3; i < d.length; i += 4) ink += d[i] / 255;
    list.push({ch, ink: ink / (W * H)});
  }
  const top = Math.max(...list.map(x => x.ink));
  for (const x of list) x.ink /= top;
  const sorted = list.sort((a, b) => a.ink - b.ink);
  ramps.set(set, sorted);
  return sorted;
}
/** A glyph of about `t` ink, picked with stable variety among the glyphs that close to it. */
function glyphFor(t, salt, set) {
  const list = glyphRamp(set);
  const near = list.filter(x => Math.abs(x.ink - t) < .028);
  if (near.length) return near[((salt * 2654435761) >>> 0) % near.length].ch;
  let best = list[0];
  for (const x of list) if (Math.abs(x.ink - t) < Math.abs(best.ink - t)) best = x;
  return best.ch;
}
const lum = (r, g, b) => (.2126 * r + .7152 * g + .0722 * b) / 255;

/**
 * Read `source` (painted at `k` device px per logical px; the w x h frame starts `pad` logical
 * px in) in character cells and return a same-size canvas written in text.
 */
export function asciify(source, w, h, k, {cell = [CELL_W, CELL_H], pad = 0, ground = true, lift = 1, absolute = null, base = null, edges = true, glyphs = GLYPHS, whiten = .22} = {}) {
  const [cw, chh] = cell;
  const cols = Math.ceil(w / cw), rows = Math.ceil(h / chh);
  const src = source.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, source.width, source.height).data;
  const SW = source.width, SH = source.height;
  const cov = new Float32Array(cols * rows), light = new Float32Array(cols * rows), rgb = new Float32Array(cols * rows * 3);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const x0 = Math.floor((pad + c * cw) * k), y0 = Math.floor((pad + r * chh) * k);
    const x1 = Math.min(SW, Math.floor((pad + (c + 1) * cw) * k)), y1 = Math.min(SH, Math.floor((pad + (r + 1) * chh) * k));
    let R = 0, G = 0, B = 0, A = 0, n = 0;
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
      const i = (y * SW + x) * 4, a = src[i + 3] / 255;
      n++;
      if (a) { R += src[i] * a; G += src[i + 1] * a; B += src[i + 2] * a; A += a; }
    }
    const i = r * cols + c;
    cov[i] = n ? A / n : 0;
    if (A) { rgb[i * 3] = R / A; rgb[i * 3 + 1] = G / A; rgb[i * 3 + 2] = B / A; light[i] = lum(R / A, G / A, B / A); }
  }
  // light is read relative to the piece, so a dark wolf and a pale skull both span the glyphs
  const lit = [];
  for (let i = 0; i < cov.length; i++) if (cov[i] > .3) lit.push(light[i]);
  lit.sort((a, b) => a - b);
  const [lo, hi] = absolute || [lit[Math.floor(lit.length * .03)] ?? 0, lit[Math.floor(lit.length * .97)] ?? 1], span = Math.max(.1, hi - lo);
  const norm = i => Math.max(0, Math.min(1, (light[i] - lo) / span));
  const C = (c, r) => (c < 0 || r < 0 || c >= cols || r >= rows) ? 0 : cov[r * cols + c];
  const L = (c, r) => (c < 0 || r < 0 || c >= cols || r >= rows || cov[r * cols + c] < .3) ? 0 : norm(r * cols + c);
  const sobel = (F, c, r) => [
    (F(c + 1, r - 1) + 2 * F(c + 1, r) + F(c + 1, r + 1)) - (F(c - 1, r - 1) + 2 * F(c - 1, r) + F(c - 1, r + 1)),
    (F(c - 1, r + 1) + 2 * F(c, r + 1) + F(c + 1, r + 1)) - (F(c - 1, r - 1) + 2 * F(c, r - 1) + F(c + 1, r - 1))];
  const out = document.createElement('canvas');
  out.width = source.width; out.height = source.height;
  const o = out.getContext('2d');
  o.scale(k, k); o.translate(pad, pad);
  if (base) { o.fillStyle = base; o.fillRect(0, 0, w, h); }
  if (ground) {   // a soft dark ground under the text, so it reads over grass
    o.save(); o.filter = `blur(${(.9 * k).toFixed(1)}px)`; o.fillStyle = OUTLINE;
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) if (cov[r * cols + c] > .4) o.fillRect(c * cw, r * chh, cw, chh);
    o.restore();
  }
  o.font = `${chh * 1.04}px ${FONT}`; o.textBaseline = 'top'; o.textAlign = 'left';
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const i = r * cols + c;
    if (cov[i] < .22) continue;
    // edges: the silhouette first, then a strong step in light inside the figure
    let [gx, gy] = edges ? sobel(C, c, r) : [0, 0], mag = Math.hypot(gx, gy);
    if (edges && mag < 2.2) { [gx, gy] = sobel(L, c, r); mag = Math.hypot(gx, gy) * .8; }
    const t = norm(i);
    let ch;
    if (mag > 2.2) {
      const a = Math.abs(Math.atan2(gy, gx) * 180 / Math.PI);   // 0 = light to the east, 90 = below
      ch = a < 22.5 || a > 157.5 ? '|' : a > 67.5 && a < 112.5 ? (gy < 0 && C(c, r + 1) < .1 ? '_' : '-') : gx * gy > 0 ? '\\' : '/';
    } else ch = glyphFor(Math.min(1, (.08 + t * .92) * Math.min(1, cov[i] * 1.3)), r * 977 + c * 131, glyphs);
    if (ch === ' ') continue;
    const boost = lift * (1 + t * .75), white = whiten * t;   // lit glyphs glow toward white
    const tone = j => Math.min(255, (rgb[i * 3 + j] * boost + 26) * (1 - white) + 255 * white) | 0;
    o.fillStyle = `rgb(${tone(0)},${tone(1)},${tone(2)})`;
    o.globalAlpha = Math.min(1, cov[i] * 1.6);
    o.fillText(ch, c * cw, r * chh);
  }
  o.globalAlpha = 1;
  out.lw = source.lw; out.lh = source.lh; out.pad = source.pad;
  return out;
}

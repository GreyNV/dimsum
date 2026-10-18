/** ASCII rendering by shape (after Alex Harri, "ASCII characters are not pixels").
 *
 * Every tree, rock, actor and prop is first painted as a lit picture, then read back as text.
 * A cell's character is chosen by *shape*, not just by brightness:
 *   - each character is measured once from the real font as a 6-component shape vector: how much
 *     ink falls in six staggered sampling circles (two columns of three, the left column a little
 *     lower than the right), each component normalised by its maximum over all characters;
 *   - each cell of the picture is measured the same way (light in the same six circles), so a
 *     cell lit along its top picks '"' or '^', lit on the left '[' or '(', an even mid tone '+' or
 *     'o', a full bright patch '@' or '#' - edges and features read in the characters themselves;
 *   - contrast is sharpened before matching: directionally (each circle against ten circles that
 *     reach into the neighbouring cells, so boundaries do not staircase) and globally (the
 *     weaker components of a cell are pushed down against its strongest);
 *   - the nearest character (Euclidean) wins; results are cached by the quantised vector.
 * The pictures stay bright and full: by default a cell keeps a darkened tint of its own colour
 * behind its character (STYLE.backing), so a figure reads as a solid, coloured body written in
 * text rather than a hollow outline. Presentation only; without a DOM nothing here runs.
 */
export const CELL_W = 1.4, CELL_H = 2.5;
export const FONT = '"DejaVu Sans Mono", Consolas, "Liberation Mono", Menlo, monospace';
export const GLYPHS = Array.from({length: 95}, (_, i) => String.fromCharCode(32 + i)).join('');
/** Reading resolution: pictures are painted this many device px per logical px for reading. */
export const READ_K = 8;
const OUTLINE = 'rgba(4, 7, 4, .58)';
export const asciiReady = () => typeof document !== 'undefined' && !!document.createElement;

/* How the text is laid down; the whole look can be switched (STYLE presets, setAsciiStyle).
 *   backing: 'none' (characters only) | 'tint' (each cell filled with its colour, darkened) |
 *            'paint' (the picture itself, dimmed, under the characters)
 *   dim: backing brightness, lift / whiten: character brightness and glow toward white */
export const STYLES = Object.freeze({
  glyphs: {backing: 'none', dim: 0, lift: 1.35, whiten: .35},
  tint: {backing: 'tint', dim: .42, lift: 1.3, whiten: .3},
  paint: {backing: 'paint', dim: .62, lift: 1.2, whiten: .45},
  bold: {backing: 'paint', dim: .72, lift: 1.15, whiten: .5, cell: [2, 3.6], gain: .85},
  picture: {backing: 'picture'}});   // the painted picture as is (no text): for comparison
let STYLE = STYLES.paint;   // bright pictures with text texture (Andrew: the bright drawings were more fun)
const listeners = new Set();
export const currentStyle = () => STYLE;
export function onStyleChange(f) { listeners.add(f); }
export function setAsciiStyle(style) {
  STYLE = typeof style === 'string' ? STYLES[style] : {...STYLE, ...style};
  for (const f of listeners) f();
}

// --- shape vectors ------------------------------------------------------------------------
/* Six internal circles (cell-relative centres; radius as a fraction of cell height), and ten
 * external ones reaching into the neighbours, each listed with the internal circles it bounds. */
const R = .15;
const INTERNAL = [[.3, .27], [.3, .54], [.3, .81], [.7, .19], [.7, .46], [.7, .73]];
const EXTERNAL = [
  [[.3, -.06], [0]], [[.7, -.14], [3]],                 // above
  [[.3, 1.08], [2]], [[.7, 1.0], [5]],                  // below
  [[-.2, .27], [0]], [[-.2, .54], [1]], [[-.2, .81], [2]],   // left
  [[1.2, .19], [3]], [[1.2, .46], [4]], [[1.2, .73], [5]]];  // right
const DIRECTIONAL = 2.6, GLOBAL = 1.8;
let chars = null;
const cache = new Map();

function characterVectors() {
  if (chars) return chars;
  const H = 96, W = Math.round(H * CELL_W / CELL_H), c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d', {willReadFrequently: true});
  const list = [];
  for (const ch of GLYPHS) {
    g.clearRect(0, 0, W, H); g.fillStyle = '#fff';
    g.font = `${H * 1.04}px ${FONT}`; g.textBaseline = 'top'; g.textAlign = 'left';
    g.fillText(ch, 0, 0);
    const d = g.getImageData(0, 0, W, H).data;
    const v = INTERNAL.map(([cx, cy]) => {
      let ink = 0, n = 0;
      const rx = R * H, x0 = cx * W, y0 = cy * H;
      for (let y = Math.floor(y0 - rx); y <= y0 + rx; y++) for (let x = Math.floor(x0 - rx); x <= x0 + rx; x++) {
        if ((x - x0) ** 2 + (y - y0) ** 2 > rx * rx) continue;
        n++;
        if (x >= 0 && y >= 0 && x < W && y < H) ink += d[(y * W + x) * 4 + 3] / 255;
      }
      return n ? ink / n : 0;
    });
    list.push({ch, v});
  }
  for (let i = 0; i < 6; i++) {
    const top = Math.max(...list.map(x => x.v[i])) || 1;
    for (const x of list) x.v[i] /= top;
  }
  chars = list;
  return list;
}
function nearest(v, set = null) {
  const key = (set || '') + '|' + v.map(x => Math.min(31, Math.round(x * 31))).join(',');
  if (cache.has(key)) return cache.get(key);
  let best = ' ', score = Infinity;
  for (const {ch, v: w} of characterVectors()) {
    if (set && !set.includes(ch)) continue;
    let s = 0;
    for (let i = 0; i < 6; i++) { const d = w[i] - v[i]; s += d * d; }
    if (s < score) { score = s; best = ch; }
  }
  cache.set(key, best);
  return best;
}
const lum = (r, g, b) => (.2126 * r + .7152 * g + .0722 * b) / 255;

/**
 * Read `source` (painted at `kIn` device px per logical px; its w x h frame starts `pad` logical
 * px in) in character cells; return a canvas at `kOut` device px per logical px written in text.
 * opts: cell, pad, ground (soft dark halo), absolute ([lo, hi] light scale instead of the
 * piece's own), base (a solid colour under everything), glyphs (allowed characters), style.
 */
export function asciify(source, w, h, kIn, kOut = kIn, {cell = null, pad = 0, ground = true, absolute = null, base = null, glyphs = null, style = null} = {}) {
  const st = {gain: .8, ...STYLE, ...(style || {})};
  const [cw, chh] = cell || st.cell || [CELL_W, CELL_H];
  const cols = Math.ceil(w / cw), rows = Math.ceil(h / chh);
  const SW = source.width, SH = source.height;
  const src = source.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, SW, SH).data;
  const at = (lx, ly) => {   // light x alpha and alpha at a logical point (frame coordinates)
    const x = Math.floor((pad + lx) * kIn), y = Math.floor((pad + ly) * kIn);
    if (x < 0 || y < 0 || x >= SW || y >= SH) return [0, 0];
    const i = (y * SW + x) * 4, a = src[i + 3] / 255;
    return [a ? lum(src[i], src[i + 1], src[i + 2]) : 0, a];
  };
  // cell colour and coverage
  const cov = new Float32Array(cols * rows), rgb = new Float32Array(cols * rows * 3), light = new Float32Array(cols * rows);
  const step = 1 / kIn;
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    let Rr = 0, G = 0, B = 0, A = 0, n = 0;
    for (let ly = r * chh; ly < (r + 1) * chh; ly += step) for (let lx = c * cw; lx < (c + 1) * cw; lx += step) {
      const x = Math.floor((pad + lx) * kIn), y = Math.floor((pad + ly) * kIn);
      n++;
      if (x < 0 || y < 0 || x >= SW || y >= SH) continue;
      const i = (y * SW + x) * 4, a = src[i + 3] / 255;
      if (a) { Rr += src[i] * a; G += src[i + 1] * a; B += src[i + 2] * a; A += a; }
    }
    const i = r * cols + c;
    cov[i] = n ? A / n : 0;
    if (A) { rgb[i * 3] = Rr / A; rgb[i * 3 + 1] = G / A; rgb[i * 3 + 2] = B / A; light[i] = lum(Rr / A, G / A, B / A); }
  }
  const lit = [];
  for (let i = 0; i < cov.length; i++) if (cov[i] > .3) lit.push(light[i]);
  lit.sort((a, b) => a - b);
  const [lo, hi] = absolute || [lit[Math.floor(lit.length * .02)] ?? 0, lit[Math.floor(lit.length * .98)] ?? 1];
  const span = Math.max(.08, hi - lo);
  // light in a circle (centre in logical px, radius r): relative light x coverage
  const circle = (cx, cy, rad) => {
    let s = 0, n = 0;
    const d = Math.max(step, rad / 2);
    for (let y = cy - rad; y <= cy + rad; y += d) for (let x = cx - rad; x <= cx + rad; x += d) {
      if ((x - cx) ** 2 + (y - cy) ** 2 > rad * rad) continue;
      const [l, a] = at(x, y);
      s += a * Math.max(0, Math.min(1, (l - lo) / span * .9 + .1)); n++;
    }
    return n ? s / n : 0;
  };
  const out = document.createElement('canvas');
  out.width = Math.ceil(SW / kIn * kOut); out.height = Math.ceil(SH / kIn * kOut);
  const o = out.getContext('2d');
  if (st.backing === 'picture') { o.drawImage(source, 0, 0, out.width, out.height); out.lw = source.lw; out.lh = source.lh; out.pad = source.pad; return out; }
  o.scale(kOut, kOut); o.translate(pad, pad);
  if (base) { o.fillStyle = base; o.fillRect(0, 0, w, h); }
  if (ground) {   // a soft dark halo under the figure, so it reads over grass
    o.save(); o.filter = `blur(${(.9 * kOut).toFixed(1)}px)`; o.fillStyle = OUTLINE;
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) if (cov[r * cols + c] > .4) o.fillRect(c * cw - .3, r * chh - .3, cw + .6, chh + .6);
    o.restore();
  }
  if (st.backing === 'paint') {
    o.save(); o.translate(-pad, -pad); o.filter = `brightness(${st.dim})`;
    o.drawImage(source, 0, 0, SW / kIn, SH / kIn); o.restore();
  } else if (st.backing === 'tint') {
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const i = r * cols + c;
      if (cov[i] < .35) continue;
      o.globalAlpha = Math.min(1, cov[i] * 1.3);
      o.fillStyle = `rgb(${rgb[i * 3] * st.dim | 0},${rgb[i * 3 + 1] * st.dim | 0},${rgb[i * 3 + 2] * st.dim | 0})`;
      o.fillRect(c * cw, r * chh, cw + .02, chh + .02);
    }
    o.globalAlpha = 1;
  }
  o.font = `${chh * 1.04}px ${FONT}`; o.textBaseline = 'top'; o.textAlign = 'left';
  const rad = R * chh;
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const i = r * cols + c;
    if (cov[i] < .12) continue;
    const x0 = c * cw, y0 = r * chh;
    const v = INTERNAL.map(([cx, cy]) => circle(x0 + cx * cw, y0 + cy * chh, rad));
    // directional contrast: each circle against the outside circles that bound it
    const ext = EXTERNAL.map(([[cx, cy]]) => circle(x0 + cx * cw, y0 + cy * chh, rad));
    for (let k = 0; k < 6; k++) {
      let m = v[k];
      EXTERNAL.forEach(([, affects], e) => { if (affects.includes(k)) m = Math.max(m, ext[e]); });
      if (m > 0) v[k] = (v[k] / m) ** DIRECTIONAL * m;
    }
    // global contrast: weaker parts of the cell against its strongest
    const M = Math.max(...v);
    if (M > 0) for (let k = 0; k < 6; k++) v[k] = (v[k] / M) ** GLOBAL * M * st.gain;   // mid tones keep lighter glyphs
    const ch = nearest(v, glyphs);
    if (ch === ' ') continue;
    const t = Math.max(0, Math.min(1, (light[i] - lo) / span));
    const boost = st.lift * (.95 + t * .7), white = st.whiten * t;
    const tone = j => Math.min(255, (rgb[i * 3 + j] * boost + 22) * (1 - white) + 255 * white) | 0;
    o.fillStyle = `rgb(${tone(0)},${tone(1)},${tone(2)})`;
    o.globalAlpha = Math.min(1, cov[i] * 1.8);
    o.fillText(ch, x0, y0);
  }
  o.globalAlpha = 1;
  out.lw = source.lw; out.lh = source.lh; out.pad = source.pad;
  return out;
}

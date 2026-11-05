/** Item icons: a small painted picture per catalog art key (catalog ItemDef.art), drawn on a
 * 32x32 canvas in the item's own colour. Kinds get their own slot shade in style.css
 * (.slots li.food / material / gear / treasure). tests/test_world_systems.py checks every
 * catalog art key has an entry here; an unknown key falls back to the item's glyph. */

const OUT = '#1a140d';

/** A colour lighter (k > 0) or darker (k < 0) by k (-1..1). */
export function shade(hex, k) {
  const n = parseInt(hex.slice(1), 16), c = [n >> 16, n >> 8 & 255, n & 255];
  const m = c.map(v => Math.round(k > 0 ? v + (255 - v) * k : v * (1 + k)));
  return `rgb(${m.join(',')})`;
}

const P = {
  ellipse(g, x, y, rx, ry, fill, rot = 0) {
    g.beginPath(); g.ellipse(x, y, rx, ry, rot, 0, Math.PI * 2);
    g.fillStyle = fill; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke();
  },
  poly(g, pts, fill, stroke = OUT) {
    g.beginPath(); g.moveTo(...pts[0]); for (const p of pts.slice(1)) g.lineTo(...p); g.closePath();
    if (fill) { g.fillStyle = fill; g.fill(); }
    if (stroke) { g.lineWidth = 1.5; g.strokeStyle = stroke; g.stroke(); }
  },
  line(g, pts, color, width) {
    g.lineCap = 'round'; g.lineJoin = 'round';
    g.beginPath(); g.moveTo(...pts[0]); for (const p of pts.slice(1)) g.lineTo(...p);
    g.lineWidth = width + 2.5; g.strokeStyle = OUT; g.stroke();
    g.lineWidth = width; g.strokeStyle = color; g.stroke();
  },
  glint(g, x, y, r = 1.6) { g.fillStyle = 'rgba(255,255,255,.75)'; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); },
};

/** art key -> paint(g, colour) on a 32x32 canvas. */
export const ITEM_ART = Object.freeze({
  wild_berries: (g, c) => {
    P.line(g, [[16, 5], [16, 11], [10, 13]], '#5f7a3a', 1.5);
    for (const [x, y] of [[11, 17], [20, 16], [15, 23], [22, 24], [9, 25]]) { P.ellipse(g, x, y, 4.6, 4.6, c); P.glint(g, x - 1.4, y - 1.6, 1.1); }
  },
  bird_egg: (g, c) => { P.ellipse(g, 16, 17, 8.5, 11, c); for (const [x, y] of [[13, 13], [19, 19], [15, 22], [20, 12]]) { g.fillStyle = '#9a8f72'; g.fillRect(x, y, 2, 2); } P.glint(g, 12, 11, 1.8); },
  boar_meat: (g, c) => {
    P.ellipse(g, 15, 17, 11, 8, c, -.4); P.ellipse(g, 15, 17, 6, 4, shade(c, .35), -.4);
    P.line(g, [[23, 11], [28, 6]], '#eee2c8', 3); P.ellipse(g, 28.5, 5.5, 2.3, 2.3, '#eee2c8');
  },
  venison: (g, c) => {
    P.poly(g, [[5, 20], [12, 9], [25, 8], [28, 18], [19, 26], [8, 26]], c);
    P.line(g, [[10, 18], [22, 13]], shade(c, .45), 2); P.line(g, [[12, 22], [23, 18]], shade(c, .45), 1.5);
  },
  pale_mushroom: (g, c) => {
    P.poly(g, [[13, 17], [19, 17], [20, 28], [12, 28]], shade(c, .3));
    g.beginPath(); g.moveTo(4, 18); g.quadraticCurveTo(16, 0, 28, 18); g.closePath();
    g.fillStyle = c; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke();
    for (const [x, y] of [[11, 12], [18, 9], [22, 14]]) P.glint(g, x, y, 1.4);
  },
  snared_hare: (g, c) => {
    P.ellipse(g, 17, 20, 10, 7, c); P.ellipse(g, 9, 14, 5, 4.5, c);
    P.ellipse(g, 6, 6, 1.8, 5.5, shade(c, -.1), -.3); P.ellipse(g, 10, 6, 1.8, 5.5, shade(c, -.1), .2);
    g.fillStyle = OUT; g.fillRect(7, 13, 2, 2); P.line(g, [[24, 22], [29, 27]], '#c8b080', 1.2);
  },
  river_fish: (g, c) => {
    P.ellipse(g, 14, 16, 11, 6.5, c); P.poly(g, [[24, 16], [30, 9], [30, 23]], shade(c, -.15));
    g.fillStyle = OUT; g.beginPath(); g.arc(8, 15, 1.4, 0, 7); g.fill();
    P.line(g, [[13, 12], [13, 20]], shade(c, -.25), 1);
  },
  stick: (g, c) => { P.line(g, [[5, 27], [27, 5]], c, 4); P.line(g, [[16, 16], [22, 22]], c, 2.5); P.line(g, [[10, 22], [8, 16]], c, 2); },
  bramble_thorn: (g, c) => {
    P.line(g, [[4, 26], [28, 8]], '#6b8a43', 3);
    for (const [x, y, dx, dy] of [[10, 22, -3, -6], [15, 18, 4, 5], [20, 14, -3, -6], [25, 10, 4, 5]]) P.poly(g, [[x - 2, y], [x + 2, y], [x + dx, y + dy]], c);
  },
  boar_hide: (g, c) => {
    P.poly(g, [[6, 6], [13, 8], [19, 5], [26, 7], [25, 15], [28, 24], [19, 27], [12, 25], [5, 27], [7, 17]], c);
    for (const [x, y] of [[11, 13], [18, 12], [14, 19], [21, 20]]) P.line(g, [[x, y], [x + 3, y + 2]], shade(c, -.3), 1);
  },
  boar_tusk: (g, c) => {
    g.beginPath(); g.moveTo(6, 26); g.quadraticCurveTo(6, 6, 26, 4); g.quadraticCurveTo(14, 12, 12, 27); g.closePath();
    g.fillStyle = c; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke(); P.glint(g, 11, 13, 1.3);
  },
  deer_antler: (g, c) => {
    P.line(g, [[10, 28], [14, 16], [12, 5]], c, 3); P.line(g, [[14, 16], [22, 11], [27, 4]], c, 2.5);
    P.line(g, [[13, 10], [7, 6]], c, 2); P.line(g, [[22, 11], [27, 14]], c, 2);
  },
  tarnished_coin: (g, c) => {
    P.ellipse(g, 16, 16, 11, 11, c); g.lineWidth = 1.2; g.strokeStyle = shade(c, -.35);
    g.beginPath(); g.arc(16, 16, 7.5, 0, 7); g.stroke(); g.fillStyle = shade(c, -.35); g.fillRect(14, 11, 4, 10); P.glint(g, 11, 10, 1.6);
  },
  amber_charm: (g, c) => {
    P.line(g, [[8, 4], [16, 10], [24, 4]], '#8a6a40', 1.2);
    P.poly(g, [[16, 9], [25, 18], [16, 29], [7, 18]], c); P.poly(g, [[16, 13], [21, 18], [16, 24], [11, 18]], shade(c, .35), null);
    P.glint(g, 13, 15, 1.5);
  },
  hide_wrap: (g, c) => {
    P.poly(g, [[8, 7], [24, 7], [27, 26], [5, 26]], c);
    P.line(g, [[6, 16], [26, 16]], shade(c, -.35), 2.5); P.line(g, [[12, 9], [10, 24]], shade(c, .2), 1);
  },
  padded_jerkin: (g, c) => {
    P.poly(g, [[10, 5], [22, 5], [28, 11], [25, 14], [24, 28], [8, 28], [7, 14], [4, 11]], c);
    for (const y of [12, 17, 22]) P.line(g, [[10, y], [22, y]], shade(c, -.25), 1);
  },
  leather_jerkin: (g, c) => {
    P.poly(g, [[10, 5], [22, 5], [28, 11], [25, 14], [24, 28], [8, 28], [7, 14], [4, 11]], c);
    P.line(g, [[16, 7], [16, 27]], shade(c, -.35), 1.5); for (const y of [11, 16, 21]) P.ellipse(g, 16, y, 1.2, 1.2, '#d8c090');
  },
  studded_wrap: (g, c) => {
    P.poly(g, [[8, 7], [24, 7], [27, 26], [5, 26]], shade(c, -.25));
    for (const [x, y] of [[11, 11], [16, 11], [21, 11], [10, 17], [16, 17], [22, 17], [11, 23], [16, 23], [21, 23]]) P.ellipse(g, x, y, 1.6, 1.6, c);
  },
  leather_hood: (g, c) => {
    g.beginPath(); g.moveTo(6, 27); g.quadraticCurveTo(4, 4, 16, 4); g.quadraticCurveTo(28, 4, 26, 27); g.closePath();
    g.fillStyle = c; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke();
    P.ellipse(g, 16, 18, 6, 7.5, '#1d1712');
  },
  hide_boots: (g, c) => {
    P.poly(g, [[6, 5], [14, 5], [14, 20], [20, 22], [21, 27], [5, 27]], c);
    P.poly(g, [[17, 7], [24, 7], [24, 19], [29, 21], [29, 26], [17, 26]], shade(c, -.2));
    P.line(g, [[6, 10], [14, 10]], shade(c, .3), 1.2);
  },
  leather_pack: (g, c) => {
    P.poly(g, [[7, 9], [25, 9], [26, 28], [6, 28]], c); P.poly(g, [[7, 9], [25, 9], [24, 17], [8, 17]], shade(c, .2));
    P.line(g, [[11, 9], [12, 4], [20, 4], [21, 9]], shade(c, -.3), 1.8); P.ellipse(g, 16, 17, 1.8, 1.8, '#d8c090');
  },
  leather_gloves: (g, c) => {
    P.poly(g, [[8, 28], [8, 14], [9, 6], [12, 6], [12, 13], [13, 4], [16, 4], [16, 13], [17, 5], [20, 5], [20, 14], [21, 8], [24, 8], [24, 18], [20, 28]], c);
    P.line(g, [[9, 24], [21, 24]], shade(c, -.3), 2);
  },
  walking_staff: (g, c) => { P.line(g, [[8, 29], [23, 4]], c, 3.5); P.ellipse(g, 23.5, 4.5, 3, 3, shade(c, -.2)); P.line(g, [[13, 21], [16, 16]], shade(c, -.35), 3.5); },
  spear: (g, c) => { P.line(g, [[5, 28], [22, 9]], '#9a7650', 2.5); P.poly(g, [[20, 7], [28, 3], [25, 11]], c); P.line(g, [[19, 12], [17, 10]], '#c8b080', 2); },
  axe: (g, c) => {
    P.line(g, [[7, 28], [22, 6]], '#9a7650', 3);
    g.beginPath(); g.moveTo(17, 7); g.quadraticCurveTo(29, 6, 28, 18); g.lineTo(21, 13); g.closePath();
    g.fillStyle = c; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke(); P.glint(g, 25, 11, 1.2);
  },
  cloth_scrap: (g, c) => { P.poly(g, [[5, 9], [14, 6], [27, 10], [24, 18], [27, 26], [13, 25], [6, 27], [9, 18]], c); P.line(g, [[10, 13], [22, 15]], shade(c, -.25), 1); P.line(g, [[11, 20], [21, 21]], shade(c, -.25), 1); },
  old_bone: (g, c) => {
    P.line(g, [[8, 24], [24, 8]], c, 5);
    for (const [x, y] of [[6, 23], [9, 27], [23, 5], [27, 9]]) P.ellipse(g, x, y, 3, 3, c);
    P.line(g, [[13, 18], [18, 13]], shade(c, -.35), 1);
  },
  rope: (g, c) => {
    for (const r of [11, 7.5, 4]) { g.beginPath(); g.arc(16, 16, r, 0, 7); g.lineWidth = 5; g.strokeStyle = OUT; g.stroke(); g.lineWidth = 3; g.strokeStyle = c; g.stroke(); }
    P.line(g, [[25, 22], [29, 28]], c, 3);
  },
  iron_nails: (g, c) => { for (const [x, d] of [[9, -.25], [16, 0], [23, .25]]) { P.line(g, [[x, 7], [x + d * 8, 27]], c, 2.2); P.line(g, [[x - 3, 7], [x + 3, 7]], shade(c, -.2), 2.5); } },
  river_scales: (g, c) => {
    for (const [x, y] of [[10, 12], [20, 11], [15, 18], [24, 20], [9, 23], [18, 26]]) {
      g.beginPath(); g.arc(x, y, 5, Math.PI * .1, Math.PI * .9, true); g.closePath();
      g.fillStyle = c; g.fill(); g.lineWidth = 1.3; g.strokeStyle = OUT; g.stroke(); P.glint(g, x - 1.5, y - 2.5, .9);
    }
  },
  wolf_fang: (g, c) => {
    g.beginPath(); g.moveTo(10, 5); g.quadraticCurveTo(24, 8, 19, 28); g.quadraticCurveTo(14, 14, 10, 5);
    g.fillStyle = c; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke(); P.glint(g, 15, 10, 1.2);
  },
  bread: (g, c) => {
    P.ellipse(g, 16, 18, 13, 8.5, c); P.ellipse(g, 16, 15, 11, 5, shade(c, .2));
    for (const x of [10, 16, 22]) P.line(g, [[x - 2, 17], [x + 2, 12]], shade(c, -.35), 1.4);
  },
  turnip: (g, c) => {
    P.line(g, [[14, 9], [10, 3]], '#5f8a3a', 2.5); P.line(g, [[16, 9], [17, 2]], '#5f8a3a', 2.5); P.line(g, [[18, 9], [23, 4]], '#5f8a3a', 2.5);
    g.beginPath(); g.moveTo(6, 15); g.quadraticCurveTo(16, 4, 26, 15); g.quadraticCurveTo(24, 24, 16, 30); g.quadraticCurveTo(8, 24, 6, 15);
    g.fillStyle = c; g.fill(); g.lineWidth = 1.5; g.strokeStyle = OUT; g.stroke();
    g.fillStyle = '#8a5a9a'; g.beginPath(); g.moveTo(6.8, 14); g.quadraticCurveTo(16, 5, 25.2, 14); g.quadraticCurveTo(16, 11, 6.8, 14); g.fill();
  },
});

const cache = new Map();

/** A fresh 32x32 canvas showing the item's icon, or null for an unknown art key (the caller shows
 * the glyph). A canvas, not an <img>: the local server's CSP has no data: images. */
export function itemIcon(art, color, doc = globalThis.document) {
  const master = iconMaster(art, color, doc);
  if (!master) return null;
  const copy = doc.createElement('canvas'); copy.width = copy.height = 32;
  copy.getContext('2d').drawImage(master, 0, 0);
  return copy;
}

/** The shared 32x32 picture (for drawing onto another canvas), or null. */
export function iconMaster(art, color, doc = globalThis.document) {
  const paint = ITEM_ART[art];
  if (!paint || !doc?.createElement) return null;
  const key = `${art}|${color}`;
  let master = cache.get(key);
  if (!master) {
    master = doc.createElement('canvas'); master.width = master.height = 32;
    const g = master.getContext?.('2d');
    if (!g) return null;
    paint(g, /^#[0-9a-f]{6}$/i.test(color || '') ? color : '#c8b8a0');
    cache.set(key, master);
  }
  return master;
}

/** The frame's item table ({id: [art key, kind]}, session ITEM_ART) and colours, set by app.js. */
const INFO = {art: {}, colors: {}};
export function setItemInfo(art, colors) { if (art) INFO.art = art; if (colors) INFO.colors = colors; }
export function itemArt(id) { return INFO.art[id]?.[0]; }

/** An inline item: its icon on its kind's shade, then `text` (the name, a count...). Text alone
 * when the item is unknown or the document cannot draw (tests). */
export function itemChip(doc, id, text) {
  const chip = doc.createElement('span');
  const [art, kind] = INFO.art[id] || [];
  chip.className = `item-chip ${kind || ''}`.trim();
  const icon = art && itemIcon(art, INFO.colors[id], doc);
  if (icon) { icon.className = 'item-chip-icon'; icon.setAttribute('aria-hidden', 'true'); chip.append(icon); }
  chip.append(doc.createTextNode(text));
  return chip;
}

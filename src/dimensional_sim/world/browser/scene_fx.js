/** Screen-space and per-chunk effects for the world scene (cosmetic only). */
import {TILE_W, TILE_H} from './view.js';

/** A cached canvas washing each tile in its own region's colour (generator v3 sends
 * one tint code per tile). `picture` is the chunk's painted-picture cache entry. */
export function tintPicture(chunk, picture) {
  if (!picture) return null;
  if (picture.tint) return picture.tint;
  const canvas = document.createElement('canvas');
  canvas.width = chunk.width * TILE_W; canvas.height = chunk.height * TILE_H;
  const c = canvas.getContext('2d');
  chunk.tint_rows.forEach((row, y) => {
    let start = 0;
    for (let x = 1; x <= row.length; x++) if (x === row.length || row[x] !== row[start]) {
      const color = chunk.tint_legend?.[row[start]];
      if (color) { c.fillStyle = color; c.fillRect(start * TILE_W, y * TILE_H, (x - start) * TILE_W, TILE_H); }
      start = x;
    }
  });
  picture.tint = canvas;
  return canvas;
}

/** Prologue: black while the eyes are closed, then two lids part from the middle. */
export function drawEyelids(ctx, opening, width, height, reducedMotion) {
  if (!opening.dark) return;
  const lid = (1 - (reducedMotion ? opening.eyes : 1 - (1 - opening.eyes) ** 2)) * height / 2;
  ctx.fillStyle = '#000';
  if (opening.eyes <= 0) { ctx.fillRect(0, 0, width, height); return; }
  ctx.fillRect(0, 0, width, lid); ctx.fillRect(0, height - lid, width, lid);
  for (const [y0, y1] of [[lid, lid + 40], [height - lid, height - lid - 40]]) {
    const edge = ctx.createLinearGradient(0, y0, 0, y1);
    edge.addColorStop(0, '#000'); edge.addColorStop(1, '#0000');
    ctx.fillStyle = edge; ctx.fillRect(0, Math.min(y0, y1), width, 40);
  }
}

/** A soft dark vignette around the screen edges. */
export function drawVignette(ctx, width, height) {
  const shade = ctx.createRadialGradient(width/2, height/2, Math.min(width, height)*.27, width/2, height/2, Math.max(width, height)*.7);
  shade.addColorStop(0, '#00000000'); shade.addColorStop(1, '#070c0755');
  ctx.fillStyle = shade; ctx.fillRect(0, 0, width, height);
}

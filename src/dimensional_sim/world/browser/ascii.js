/** Character-cell presentation of the existing authoritative world snapshot. */
import {TILE_W, TILE_H, cameraView, follow, residentBounds} from './view.js';

const COLOR = Object.freeze({
  T: '#789665', '^': '#8b8066', '#': '#a58c67', '=': '#a99b70',
  '~': '#72b4b6', ';': '#b88a69', 'o': '#7eae7c', 'x': '#c38b6d',
  ':': '#ae755d', '.': '#526d51', ',': '#668060', '/': '#a99477'
});

function glyph(ctx, character, x, y, color = '#a7bd91', size = 21) {
  ctx.fillStyle = color;
  ctx.font = `700 ${size}px ui-monospace, Consolas, monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(character, (x + .5) * TILE_W, (y + .5) * TILE_H + 1);
}

export function paintAsciiChunk(chunk) {
  const surface = document.createElement('canvas');
  surface.width = chunk.width * TILE_W;
  surface.height = chunk.height * TILE_H;
  const p = surface.getContext('2d');
  p.fillStyle = chunk.tint || '#10190f';
  p.fillRect(0, 0, surface.width, surface.height);
  for (let y = 0; y < chunk.height; y++) for (let x = 0; x < chunk.width; x++) {
    const letter = chunk.tiles[y][x];
    if (letter && letter !== ' ') glyph(p, letter, x, y, COLOR[letter] || '#63805d', 20);
  }
  return surface;
}

const spotGlyph = spot => spot.kind === 'fight' ? 'B' :
  spot.encounter === 'animal_tracks' ? '?' :
  spot.kind === 'drink' ? '~' : '*';

export function drawAsciiWorld(ctx, state, chunks, cache, camera, actor, viewport, now, reducedMotion) {
  const {width, height, dpr, zoom, dt} = viewport;
  const tx = (state.player.x + .5) * TILE_W, ty = (state.player.y + .5) * TILE_H;
  actor.x = reducedMotion ? tx : follow(actor.x, tx, dt, 55);
  actor.y = reducedMotion ? ty : follow(actor.y, ty, dt, 55);
  camera.x = reducedMotion ? actor.x : follow(camera.x, actor.x, dt, 140);
  camera.y = reducedMotion ? actor.y : follow(camera.y, actor.y, dt, 140);
  const resident = [...chunks.values()].sort((a, b) => a.y - b.y || a.x - b.x);
  const view = cameraView(camera, width, height, zoom, residentBounds(resident));
  const scale = view.scale * dpr;
  ctx.setTransform(scale, 0, 0, scale, Math.round(dpr * width / 2 - scale * view.x),
                   Math.round(dpr * height / 2 - scale * view.y));
  ctx.imageSmoothingEnabled = false;
  for (const chunk of resident) {
    if (!cache.has(chunk.id)) cache.set(chunk.id, paintAsciiChunk(chunk));
    ctx.drawImage(cache.get(chunk.id), chunk.x * chunk.width * TILE_W, chunk.y * chunk.height * TILE_H);
  }
  const anchor = state.expedition?.anchor;
  if (anchor) {
    // Persistent geography: the origin alone carries the caravan wreck.
    for (const [dx, dy, character] of [[-6,-1,'#'],[-5,-1,'='],[-4,-1,'#'],[-6,0,'O'],[-4,0,'O'],
                                       [5,-1,'#'],[6,-1,'\\'],[7,-1,'#'],[5,0,'O'],[7,0,'O'],
                                       [-3,1,'x'],[4,1,'x'],[-7,-2,'/'],[8,-2,'/']])
      glyph(ctx, character, anchor.x + dx, anchor.y + dy, '#c49a72');
    glyph(ctx, 'A', anchor.x, anchor.y, '#a7d8eb', 23);
  }
  for (const spot of state.spots || []) glyph(ctx, spotGlyph(spot), spot.x, spot.y,
    spot.encounter === 'animal_tracks' ? '#d5c697' : '#e3b871', 22);
  for (const target of state.targets) if (target.hp > 0) glyph(ctx, 'B', target.x, target.y, '#df8d78', 24);
  glyph(ctx, '@', state.player.x, state.player.y, '#f4e5bb', 26);
  return view;
}

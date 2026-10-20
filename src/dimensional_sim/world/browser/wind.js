/** Wind (presentation only): gusts roll across the map and bend grass and treetops.
 *
 * One field for everything, so neighbours move together: a slow sway everywhere, plus gust
 * fronts travelling west to east (a band of stronger push sweeping across a grove), plus a
 * quick flutter that is stronger on grass than on trunks. A plant is drawn sheared about its
 * base: the root stays put, the top leans downwind. Pure functions of (place, clock), so the
 * tree drawn on the ground pass and the same tree repainted over an actor always agree.
 */
export {putSwayed} from './art.js';

const GUST_SPEED = 0.0016;      // gust fronts: radians of phase per ms
const GUST_SPAN = 0.085;        // ... per tile across the map (a front is ~70 tiles apart)
const SWAY = 0.0011;            // the slow everyday sway
const FLUTTER = 0.0062;         // the quick shiver on top

/** Shear strength by kind: how far the top leans per pixel of height, at full gust. */
export const BEND = Object.freeze({tree: 0.032, bush: 0.05, sapling: 0.07, ferns: 0.12});

/** The wind kind of a drawn object: undergrowth by its decor kind, a 'T' tile is a tree,
 * stones, mushrooms, rocks and structures stand still (no entry in BEND). */
export const swayKind = (item, tile) => item.decor || (tile === 'T' ? 'tree' : null);

/** Wind push at global tile (gx, gy) and clock `t` ms: about -0.3..1 (downwind east is positive). */
export function windAt(gx, gy, t) {
  const front = Math.sin(gx * GUST_SPAN + gy * GUST_SPAN * .35 - t * GUST_SPEED);
  const gust = Math.max(0, front) ** 3;                       // narrow, strong fronts
  const sway = Math.sin(t * SWAY + gx * .37 + gy * .21) * .35;
  return .18 + sway * .5 + gust * .82;
}

/** Shear for a plant of `kind` at (gx, gy): lean of the top per pixel above its base. */
export function windShear(gx, gy, t, kind) {
  const bend = BEND[kind];
  if (!bend) return 0;
  const flutter = Math.sin(t * FLUTTER + gx * 1.7 + gy * 2.3) * (kind === 'tree' ? .08 : .28);
  return bend * (windAt(gx, gy, t) + flutter);
}

/** Leaves carried on the gusts: a few small flecks in world px over the view rectangle. */
export function drawBlownLeaves(ctx, x0, y0, x1, y1, t, {count = 18, tileW = 24, tileH = 28} = {}) {
  const w = x1 - x0, h = y1 - y0;
  if (w <= 0 || h <= 0) return;
  ctx.save();
  for (let i = 0; i < count; i++) {
    const seed = (i * 2654435761) >>> 0;
    const speed = .035 + (seed % 97) / 97 * .05;               // px per ms, downwind
    const life = 5200 + seed % 3800;
    const age = (t + seed % life) % life;
    const sx = x0 + ((seed >>> 7) % 1000) / 1000 * w - w * .25;
    const sy = y0 + ((seed >>> 3) % 1000) / 1000 * h;
    const x = sx + age * speed, y = sy + Math.sin(age / 340 + i) * 9 + age * .004;
    if (x < x0 - 10 || x > x1 + 10) continue;
    const push = windAt(Math.floor(x / tileW), Math.floor(y / tileH), t);
    const fade = Math.min(1, age / 600, (life - age) / 600) * Math.min(1, .25 + push);
    if (fade <= 0) continue;
    ctx.save();
    ctx.globalAlpha = fade * .85;
    ctx.fillStyle = i % 3 ? '#9fb36a' : '#c9a85a';
    ctx.translate(x, y); ctx.rotate(age / 260 + i);
    ctx.fillRect(-1.6, -.7, 3.2, 1.4);
    ctx.restore();
  }
  ctx.restore();
}

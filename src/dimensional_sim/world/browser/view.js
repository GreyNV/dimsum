/** Pure presentation math. No simulation, generation, DOM, or network. */
export const TILE_W = 24;
export const TILE_H = 28;
export const CELL_W = 4;
export const CELL_H = 7;
/** Default zoom frames a fight legibly; players can zoom out to survey terrain. */
export const ZOOM = Object.freeze({min: .7, initial: 1.3, max: 2.4});
export const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
/** A touch stick chooses one of the four movement directions used by the runtime. */
export function stickDirection(dx, dy, deadZone = 10) {
  if (Math.hypot(dx, dy) < deadZone) return null;
  return Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'east' : 'west')
    : (dy >= 0 ? 'south' : 'north');
}
/** Stable uint32 visual noise. Never used for gameplay or terrain selection. */
export function visualHash(x, y, seed = 0) {
  let n = (Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263) ^ seed) >>> 0;
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return (n ^ (n >>> 16)) >>> 0;
}
export function residentBounds(chunks) {
  if (!chunks.length) return null;
  return {left: Math.min(...chunks.map(c => c.x * c.width * TILE_W)),
    top: Math.min(...chunks.map(c => c.y * c.height * TILE_H)),
    right: Math.max(...chunks.map(c => (c.x + 1) * c.width * TILE_W)),
    bottom: Math.max(...chunks.map(c => (c.y + 1) * c.height * TILE_H))};
}
/** Fit within actual resident coverage, including very large browser windows. */
export function cameraView(camera, width, height, requestedScale, bounds) {
  if (!bounds) return {x: camera.x, y: camera.y, scale: requestedScale};
  const availableW = Math.max(TILE_W, bounds.right - bounds.left - TILE_W * 2);
  const availableH = Math.max(TILE_H, bounds.bottom - bounds.top - TILE_H * 2);
  const scale = Math.max(requestedScale, width / availableW, height / availableH);
  const halfW = width / scale / 2, halfH = height / scale / 2;
  return {scale, x: clamp(camera.x, bounds.left + halfW, bounds.right - halfW),
    y: clamp(camera.y, bounds.top + halfH, bounds.bottom - halfH)};
}
export function follow(current, target, dt, duration = 85) {
  return current + (target - current) * (1 - Math.exp(-Math.max(0, dt) / duration));
}
export function retainResident(cache, resident) {
  const ids = new Set(resident);
  for (const id of cache.keys()) if (!ids.has(id)) cache.delete(id);
}
export function tileAt(chunks, x, y) {
  const chunk = chunks.find(c => Math.floor(x / c.width) === c.x && Math.floor(y / c.height) === c.y);
  if (!chunk) return null;
  const localX = x - chunk.x * chunk.width, localY = y - chunk.y * chunk.height;
  return {glyph: chunk.tiles[localY][localX], blocked: chunk.collision[localY][localX] === '1'};
}
/** A short press survives between requests. Consume only after a successful send.
 * Movement taps are queued too: a key pressed and released between two polls still
 * reaches the server once, and repeated same-direction taps are separated by a
 * release (move:null) so the server sees one press edge -- one step -- per tap. */
export class Controls {
  constructor() { this.held = new Map(); this.taps = []; this.lastSentMove = null; this.attackHeld = false; this.attackQueued = false; this.serial = 0; this.attackRevision = 0; this.ackAttackRevision = 0; this.lastSentAttack = false; }
  press(key, direction) {
    if (this.held.has(key)) return;
    this.held.set(key, {direction, order: ++this.serial});
    this.taps.push(direction);
    if (this.taps.length > 4) this.taps.shift();
  }
  release(key) { this.held.delete(key); }
  steer(key, direction) {
    if (!direction) { this.release(key); return; }
    if (!this.held.has(key)) this.held.set(key, {direction, order: ++this.serial});
    else this.held.get(key).direction = direction;
  }
  nextMove() {
    const held = [...this.held.values()].sort((a, b) => b.order - a.order)[0]?.direction;
    if (held) return held;
    if (!this.taps.length) return null;
    return this.taps[0] === this.lastSentMove ? null : this.taps[0];
  }
  attack(down) { if (down && !this.attackHeld) { this.attackQueued = true; this.attackRevision++; } this.attackHeld = down; }
  payload(paused, known) {
    return {move: paused ? null : this.nextMove(),
      attack: !paused && (this.attackHeld || this.attackQueued) && !(this.lastSentAttack && this.attackRevision > this.ackAttackRevision), paused, known};
  }
  acknowledge(sent, revision = this.attackRevision) {
    this.lastSentMove = sent.move;
    const tap = sent.move ? this.taps.indexOf(sent.move) : -1;
    if (tap >= 0) this.taps.splice(0, tap + 1);
    this.lastSentAttack = sent.attack;
    if (sent.attack) {
      this.ackAttackRevision = revision;
      if (revision === this.attackRevision) this.attackQueued = false;
    }
  }
  reset() { this.held.clear(); this.taps = []; this.attackHeld = false; this.attackQueued = false; }
}

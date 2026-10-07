/** Places and people in the world: encounter spots, the anchor camp, the ambush
 * site and the old man of the prologue. Ground decoration only (never blocking). */
import {CELL_W, CELL_H, visualHash} from './view.js';
import {setupText} from './art.js';
import {ACTOR_FOOT, OUTLINE, mirrorSprite, paintParts} from './sprites.js';

/** Encounter spot sprites: small ground features, outlined like actors. */
const SPOT_ROLES = Object.freeze({
  r: {fill: '#b8323f', ink: '#ffb0a0'}, l: {fill: '#3f6a2e', ink: '#8fbf5a'},
  o: {fill: '#7a5532', ink: '#c39a62'}, a: {fill: '#3c6f8f', ink: '#bfe8ff'},
  g: {fill: '#6d7468', ink: '#b9bfae'}, q: {fill: '#55743c', ink: '#a9c97a'},
  u: {fill: '#3b2a1c', ink: '#8b6b4a'}, x: {fill: '#6d7468', ink: '#f2d27a'},
  y: {fill: '#e5c772', ink: '#fff3bc'}, c: {fill: '#a6bacc', ink: '#e8f5ff'}
});
export const SPOTS = Object.freeze({
  bramble_berries: {paint: ['  l r l  ', ' lrlrlrl ', 'lrrllrrll', ' lllrlll '], glyph: ['  / o \\  ', ' /o/o/o\\ ', ';o;v;o;v;', ' \\;o;;;/ ']},
  fallen_branches: {paint: ['   l  l   ', ' oooooooo ', 'oooooooooo'], glyph: ['   /  \\   ', ' /==\\==\\  ', '=\\===/===/']},
  animal_tracks: {paint: ['u  u   u ', '  u  u   ', 'u   u  u '], glyph: ['v  v   v ', '  v  v   ', 'v   v  v ']},
  gnarled_tree: {paint: ['   lll   ', '  lllll  ', '  lolol  ', '   ooo   ', '  oo oo  '], glyph: ['   ^^^   ', '  /:::\\  ', '  (|:|)  ', '   |||   ', '  /| |\\  ']},
  forest_spring: {paint: ['  cccccc  ', ' gaaaaaag ', 'gaaaaaaaag', ' gggggggg '], glyph: ['  .    .  ', ' /~~~~~~\\ ', '|~*~~~~*~|', ' \\______/ ']},
  mossy_stone: {paint: ['   qqq   ', '  qgqgq  ', ' ggggggg ', '  ggggg  '], glyph: ['   .^.   ', '  /:,:\\  ', ' /:___:\\ ', '  \\___/  ']},
  old_carvings: {paint: ['   xxx   ', '  ggggg  ', '  gxgxg  ', '  ggggg  '], glyph: ['   *:*   ', '  /___\\  ', '  |*o*|  ', '  /___\\  ']},
  abandoned_camp: {paint: ['  rrrrr  ', 'orrrrrro ', ' ooooooo ', ' qooqooq '],
    glyph: ['  /^^^\\  ', ' /_____\\ ', ' |# # #| ', ' /_o_o_\\ ']},
  moonlit_pool: {paint: ['  ccccc  ', ' caaaaac ', 'caaaaaaac', ' gcccccg '],
    glyph: ['  .***.  ', ' /~~~~~\\ ', '|~*~~~*~|', ' \\_____/ ']},
  fallen_watchtower: {paint: ['  qxxq   ', '  qxxq   ', ' qxxxxq  ', ' qgxxgq  ', ' qgggggq '],
    glyph: ['  /++\\   ', '  |::|   ', ' /|::|\\  ', ' |/__\\|  ', ' /_//_\\  ']},
  mushroom_ring: {paint: [' r r r r ', 'rggrggrgr', ' gg gg gg', 'rgggggggr'],
    glyph: [' ^ ^ ^ ^ ', '/o\\/o\\/o\\', ' .. .. ..', '^.......^']},
  wayside_shrine: {paint: ['    y    ', '  ggggg  ', ' ggggggg ', '  gxyxg  ', '  ggggg  ', ' qgggggq '],
    glyph: ['    +    ', '  /^^^\\  ', ' /_____\\ ', '  |*i*|  ', '  |___|  ', ' ;/___\\; ']}
});

/** The anchor stone at the anchor cell. Ground decoration only (non-blocking). */
const CAMP_ROLES = Object.freeze({g: {fill: '#5d6470', ink: '#9fd0ff'}, v: {fill: '#2b3140', ink: '#cfe6ff'},
  a: {fill: '#a9bed4', ink: '#f1faff'}, c: {fill: '#294661', ink: '#99daff'}});
export const CAMP = Object.freeze({
  stone: {paint: ['   aaa   ', '  agvga  ', '  gcvgg  ', '  gvcvg  ', '  gcvgg  ', '  ggvgg  ', ' ggggggg '],
    glyph: ['   /\\    ', '  /<>\\   ', '  |*|:|  ', '  |:O:|  ', '  |:|*|  ', '  \\:::/  ', ' /_____\\ ']}
});

export function drawCamp(ctx, x, y, {clock = 0, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const pulse = reducedMotion ? .35 : .3 + .18 * Math.sin(clock / 520);
  // The soul tether rises behind the stone, never entering the location asset.
  ctx.save();
  ctx.globalAlpha = reducedMotion ? .18 : .14 + pulse * .18;
  const beam = ctx.createLinearGradient(x - 18, y - 88, x - 18, y + 12);
  beam.addColorStop(0, '#9bd9ff00');
  beam.addColorStop(.35, '#9bd9ff');
  beam.addColorStop(1, '#cceeff00');
  ctx.fillStyle = beam;
  ctx.beginPath(); ctx.moveTo(x - 26, y - 86); ctx.lineTo(x - 10, y - 86);
  ctx.lineTo(x - 2, y + 14); ctx.lineTo(x - 34, y + 14); ctx.closePath(); ctx.fill();
  ctx.restore();
  ctx.save(); ctx.globalAlpha = pulse;
  const glow = ctx.createRadialGradient(x, y + 2, 2, x, y + 2, 46);
  glow.addColorStop(0, '#9fd0ff'); glow.addColorStop(1, '#9fd0ff00');
  ctx.fillStyle = glow; ctx.beginPath(); ctx.ellipse(x, y + 4, 46, 20, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  ctx.save(); ctx.strokeStyle = '#80b9e3'; ctx.lineWidth = 2; ctx.globalAlpha = pulse + .18;
  ctx.beginPath(); ctx.ellipse(x - 18, y + 14, 42, 13, 0, 0, Math.PI * 2); ctx.stroke();
  for (let i = 0; i < 8; i++) {
    const angle = i * Math.PI / 4, rx = x - 18 + Math.cos(angle) * 42, ry = y + 14 + Math.sin(angle) * 13;
    ctx.fillStyle = '#d4eeff'; ctx.fillRect(Math.round(rx) - 1, Math.round(ry) - 1, 3, 3);
  }
  ctx.restore();
  paintParts(ctx, CAMP.stone, CAMP_ROLES, x - 36, y - 56);
  for (let i = 0; i < 4; i++) {
    const phase = reducedMotion ? i * 1.57 : clock / 700 + i * 1.57;
    const sx = x - 18 + Math.cos(phase) * (24 + i % 2 * 6);
    const sy = y - 44 + Math.sin(phase) * 9 - i * 6;
    ctx.save(); ctx.globalAlpha = .45 + pulse * .5;
    ctx.fillStyle = '#c8edff'; ctx.fillRect(Math.round(sx) - 1, Math.round(sy) - 3, 3, 6);
    ctx.fillStyle = '#f3fcff'; ctx.fillRect(Math.round(sx), Math.round(sy) - 2, 1, 3);
    ctx.restore();
  }
  ctx.globalAlpha = 1;
}

/** The origin is the road ambush: two broken wagons and scattered supplies.
 * Scenery only, behind actors and independent of collision. Every piece is an
 * outlined 4x7 cell sprite like SPOTS and CAMP (wood family + one red canopy). */
const AMBUSH_ROLES = Object.freeze({
  w: {fill: '#7a5532', ink: '#3b2a1c'}, u: {fill: '#3b2a1c', ink: '#9b7944'},
  l: {fill: '#9b7944', ink: '#3b2a1c'}, b: {fill: '#b59050', ink: '#7a5532'},
  r: {fill: '#b8323f', ink: '#ffb0a0'}});
export const AMBUSH = Object.freeze({
  // Side view; the front wheel is gone, so the bed's front end has dropped to the ground.
  wagon: {paint: [
    '  u    u    u         ',
    ' bbbbbbbbbbbbbbu      ',
    ' wwwwwwwwwwwwwwbbbbb  ',
    ' wwwwwwwwwwwwwwwwwwwbb',
    ' uulllu' + 'uuuuuuuuwwwwwww',
    '  lllll       uuuuuuuu',
    '   lll          uuuuu '], glyph: [
    '  |    |    /         ',
    ' =-==-==-==-==-|      ',
    ' |::|::|::|::|=-==-=  ',
    ' |::|::|::|::|::|::\\=\\',
    ' __/|\\_________|::|::|',
    '  (-o-)       \\_____/_',
    '   \\|/          ____/ ']},
  // Tipped on its side: underside and both wheels face us, torn canopy spills out.
  tipped: {paint: [
    '   lll      lll     ',
    ' uuuuuuuuuuuuuuuuu  ',
    ' wwwwwwwwwwwwwwwwwr ',
    ' wwwwwwwwwwwwwwwwwrr',
    ' bbbbbbbbbbbbbbbbrrr',
    '  rrrrrrrrrrrrrrrrr ',
    '    rr rrrrr  rrr   '], glyph: [
    '   /o\\      /o\\     ',
    ' =|=========|====   ',
    ' |:|:|:|:|:|:|:|:|\\ ',
    ' |:|:|:|:|:|:|:|:|~\\',
    ' =-==-==-==-==-==/~~',
    '  ~/~~\\~~/~~\\~~/~~\\ ',
    '    \\/ \\~/~/  \\~/   ']},
  wheel: {paint: ['lllll'], glyph: ['(=o=)']},
  crate: {paint: ['llll', 'llll'], glyph: ['[==]', '|\\/|']},
  crateDark: {paint: ['wwww', 'wwww'], glyph: ['[==]', '|/\\|']},
  plank: {paint: ['bbbbb'], glyph: ['=-==-']},
  plankShort: {paint: ['bbb'], glyph: ['==-']},
  plankTilted: {paint: ['   bb', ' bb  ', 'b    '], glyph: ['   /=', ' /=  ', '/    ']},
  spoke: {paint: ['uu'], glyph: ['-o']},
  arrow: {paint: ['uuuuub'], glyph: ['----->']},
  sack: {paint: [' lll ', 'lllll'], glyph: [' /_\\ ', '(ooo)']},
  tornCloth: {paint: ['rrrrrr', ' r rrr'], glyph: ['\\~/~~/', ' \\ /~/']}
});
export function drawAmbushSite(ctx, x, y) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const part = (name, dx, dy) => paintParts(ctx, AMBUSH[name], AMBUSH_ROLES, x + dx, y + dy);
  // Broken wagon to the west of the anchor, its lost wheel lying beside it.
  part('wagon', -148, -35);
  part('wheel', -52, 18);
  // Second wagon on its side to the east; torn crimson cover recalls the raid.
  part('tipped', 72, -35);
  // Crates and loose planks on both sides of the road.
  part('crate', -44, 17); part('crateDark', -24, 30); part('crate', 44, 22); part('crateDark', 62, 38);
  part('plank', -152, 28); part('plankShort', -12, 40); part('plankTilted', 30, -38);
  part('plank', 150, 32); part('spoke', 92, 28); part('plankShort', -96, 30);
  // Arrows and spilled cargo identify the wreck as a violent caravan ambush.
  part('arrow', -83, -28); part('arrow', 125, -48);
  part('sack', -78, 35); part('sack', 19, 34); part('tornCloth', 115, 39);
}

/** Spot at tile center (x, y); a sparkle marks it, brighter when it is the goal. */
export function drawSpot(ctx, spot, x, y, {clock = 0, goal = false, fade = 0} = {}) {
  const sprite = SPOTS[spot.encounter];
  if (!sprite) return;
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const w = sprite.paint[0].length * CELL_W, h = sprite.paint.length * CELL_H;
  const left = x - w / 2, top = y + ACTOR_FOOT - 2 - h;
  ctx.save(); ctx.globalAlpha = 1 - fade;
  ctx.fillStyle = OUTLINE;
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role !== ' ') ctx.fillRect(left + c * CELL_W - 1, top + r * CELL_H - 1, CELL_W + 2, CELL_H + 2);
  }));
  sprite.paint.forEach((row, r) => [...row].forEach((role, c) => {
    if (role === ' ') return;
    ctx.fillStyle = SPOT_ROLES[role].fill; ctx.fillRect(left + c * CELL_W, top + r * CELL_H, CELL_W, CELL_H);
    const ch = sprite.glyph[r][c];
    if (ch !== ' ') { ctx.fillStyle = SPOT_ROLES[role].ink; ctx.fillText(ch, left + c * CELL_W, top + r * CELL_H); }
  }));
  if (!fade) {
    const lift = Math.round(Math.sin((clock + visualHash(spot.x, spot.y, 3) % 900) / 300) * 2);
    const sy = top - 7 + lift, size = goal ? 3 : 2;
    ctx.fillStyle = OUTLINE; ctx.fillRect(x - size - 1, sy - size - 1, size * 2 + 2, size * 2 + 2);
    ctx.fillStyle = goal ? '#fff0b0' : '#d8b860'; ctx.fillRect(x - size, sy - size, size * 2, size * 2);
  }
  ctx.restore();
}

/** A finished task leaves a brief, readable seal over its former spot. This is
 * presentation only; the encounter log and simulation decide completion. */
export function drawSpotCompletion(ctx, spot, x, y, age, reducedMotion = false) {
  if (age < 0 || age >= 650) return;
  const t = age / 650;
  ctx.save(); ctx.globalAlpha = Math.max(0, 1 - t);
  const color = spot.encounter === 'forest_spring' ? '#a9eaff'
    : spot.encounter === 'old_carvings' ? '#d3b6ff' : '#ffe5a0';
  ctx.strokeStyle = color; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(x, y + 4, reducedMotion ? 19 : 6 + t * 23,
    reducedMotion ? 8 : 3 + t * 9, 0, 0, Math.PI * 2); ctx.stroke();
  for (let i = 0; i < 6; i++) {
    const angle = i * Math.PI / 3 + (reducedMotion ? 0 : t * .5);
    const radius = reducedMotion ? 21 : 8 + t * 26;
    ctx.fillStyle = i % 2 ? '#fff9df' : color;
    ctx.fillRect(Math.round(x + Math.cos(angle) * radius) - 2,
      Math.round(y - 4 + Math.sin(angle) * radius * .55) - 2, 4, 4);
  }
  ctx.restore();
}

/** The old man who finds the newborn avatar: hooded grey robe, white beard, staff.
 * Presentation only; the server says where he stands during the prologue. */
const ELDER_ROLES = Object.freeze({h: {fill: '#6b6457', ink: '#a39a86'}, r: {fill: '#57594f', ink: '#8d8f80'},
  s: {fill: '#d8b48c', ink: '#3a2618'}, w: {fill: '#ece6d6', ink: '#b9b19c'}, o: {fill: '#7b5a36', ink: '#b88c58'},
  g: {fill: '#f1d27a', ink: '#fff6cf'}, b: {fill: '#3a2c20', ink: '#76604a'}});
export const ELDER = Object.freeze({paint: [
  ' g  hhh   ', ' o hhhhh  ', ' o hsshh  ', ' oswwwhr  ', ' o wwwrrr ',
  ' o rwrrrr ', ' o rrrrrr ', ' o rrrrrr ', ' o  bb bb '], glyph: [
  ' *  /^\\   ', ' | /:::\\  ', ' | (o.:\\  ', ' |-;;;:|\\ ', ' | ;;;:::\\',
  ' | |;::::|', ' | |::::| ', ' | /::::\\ ', ' |  -- -- ']});
export function drawElder(ctx, x, y, {clock = 0, facing = 'west', alpha = 1, talking = false, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const sprite = facing === 'east' ? mirrorSprite(ELDER) : ELDER;
  const width = sprite.paint[0].length * CELL_W, height = sprite.paint.length * CELL_H;
  const sway = reducedMotion ? 0 : Math.floor(clock / 900) % 2;
  const left = x - width / 2, top = y + ACTOR_FOOT - height + sway;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.fillStyle = 'rgba(3, 6, 3, .5)';
  ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 1, 15, 4, 0, 0, Math.PI * 2); ctx.fill();
  paintParts(ctx, sprite, ELDER_ROLES, left, top, alpha);
  // Lantern-warm glint on the staff head.
  const gx = facing === 'east' ? left + width - CELL_W * 2 : left + CELL_W;
  ctx.globalAlpha = alpha * (.35 + (reducedMotion ? .1 : .15 * Math.sin(clock / 300)));
  const glow = ctx.createRadialGradient(gx + 2, top + 3, 1, gx + 2, top + 3, 14);
  glow.addColorStop(0, '#ffe7a0'); glow.addColorStop(1, '#ffe7a000');
  ctx.fillStyle = glow; ctx.fillRect(gx - 12, top - 11, 28, 28);
  if (talking) {  // three speech dots above the hood
    for (let i = 0; i < 3; i++) {
      const lift = reducedMotion ? 0 : Math.round(Math.max(0, Math.sin(clock / 160 - i * .9)) * 3);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = OUTLINE; ctx.fillRect(x - 9 + i * 7, top - 12 - lift, 6, 6);
      ctx.fillStyle = '#f3e7c6'; ctx.fillRect(x - 8 + i * 7, top - 11 - lift, 4, 4);
    }
  }
  ctx.restore();
  return {left, top, width, height};
}

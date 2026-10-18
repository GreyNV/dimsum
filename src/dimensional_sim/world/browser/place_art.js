/** Places and people in the world: encounter spots, the anchor camp, the ambush
 * site and the old man of the prologue. Ground decoration only (never blocking). */
import {CELL_W, CELL_H, visualHash} from './view.js';
import {setupText} from './art.js';
import {ACTOR_FOOT, OUTLINE, mirrorSprite, paintParts} from './sprites.js';
import {ELDER_H, ELDER_W, STONE_H, STONE_W, anchorStoneCanvas, drawFireArt, drawPainted, elderCanvas} from './painted.js';
import {partCanvas, spotCanvas} from './painted_props.js';

/** Encounter spot sprites: small ground features, outlined like actors. */
const SPOT_ROLES = Object.freeze({
  r: {fill: '#b8323f', ink: '#ffb0a0'}, l: {fill: '#3f6a2e', ink: '#8fbf5a'},
  o: {fill: '#7a5532', ink: '#c39a62'}, a: {fill: '#3c6f8f', ink: '#bfe8ff'},
  g: {fill: '#6d7468', ink: '#b9bfae'}, q: {fill: '#55743c', ink: '#a9c97a'},
  u: {fill: '#3b2a1c', ink: '#8b6b4a'}, x: {fill: '#6d7468', ink: '#f2d27a'},
  y: {fill: '#e5c772', ink: '#fff3bc'}, c: {fill: '#a6bacc', ink: '#e8f5ff'},
  d: {fill: '#9a6a3c', ink: '#d9b07a'}, w: {fill: '#e8dcc4', ink: '#fff8e8'}, k: {fill: '#4a3626', ink: '#a88a64'},
  // rare phenomena: an off-colour shimmer and shadows that fall the wrong way
  v: {fill: '#5b3f8a', ink: '#e2d2ff'}, s: {fill: '#16131f', ink: '#5d5080'}
});
export const SPOTS = Object.freeze({
  bramble_berries: {paint: ['  l r l  ', ' lrlrlrl ', 'lrrllrrll', ' lllrlll '], glyph: ['  / o \\  ', ' /o/o/o\\ ', ';o;v;o;v;', ' \\;o;;;/ ']},
  fallen_branches: {paint: ['   l  l   ', ' oooooooo ', 'oooooooooo'], glyph: ['   /  \\   ', ' /==\\==\\  ', '=\\===/===/']},
  animal_tracks: {paint: ['u  u   u ', '  u  u   ', 'u   u  u '], glyph: ['v  v   v ', '  v  v   ', 'v   v  v ']},
  gnarled_tree: {paint: ['   lll   ', '  lllll  ', '  lolol  ', '   ooo   ', '  oo oo  '], glyph: ['   ^^^   ', '  /:::\\  ', '  (|:|)  ', '   |||   ', '  /| |\\  ']},
  forest_spring: {paint: ['  cccccc  ', ' gaaaaaag ', 'gaaaaaaaag', ' gggggggg '], glyph: ['  .    .  ', ' /~~~~~~\\ ', '|~*~~~~*~|', ' \\______/ ']},
  hanging_leaf: {paint: ['    v    ', '   qqq   ', '  qqqqq  ', '   qqq   ', '         ', '  s s s  '],
    glyph: ['    *    ', '   /^\\   ', '  <:|:>  ', '   \\v/   ', '         ', '  . . .  ']},
  backward_ripple: {paint: [' aaavaaa ', 'aavaaavaa', ' aaavaaa '], glyph: [' ~~~^~~~ ', '~~^~~~^~~', ' ~~~^~~~ ']},
  double_shadow: {paint: ['    qqq    ', '   qgqgq   ', '  ggggggg  ', 'sss ggg sss'],
    glyph: ['    .^.    ', '   /:,:\\   ', '  /:___:\\  ', '::: \\_/ :::']},
  split_shadow_tree: {paint: ['  v lll v  ', '   lllll   ', '   lolol   ', '    ooo    ', 'sss ooo sss'],
    glyph: ['  * ^^^ *  ', '   /:::\\   ', '   (|:|)   ', '    |||    ', '::: /|\\ :::']},
  mossy_stone: {paint: ['   qqq   ', '  qgqgq  ', ' ggggggg ', '  ggggg  '], glyph: ['   .^.   ', '  /:,:\\  ', ' /:___:\\ ', '  \\___/  ']},
  old_carvings: {paint: ['   xxx   ', '  ggggg  ', '  gxgxg  ', '  ggggg  '], glyph: ['   *:*   ', '  /___\\  ', '  |*o*|  ', '  /___\\  ']},
  moonlit_pool: {paint: ['  ccccc  ', ' caaaaac ', 'caaaaaaac', ' gcccccg '],
    glyph: ['  .***.  ', ' /~~~~~\\ ', '|~*~~~*~|', ' \\_____/ ']},
  mushroom_ring: {paint: [' r r r r ', 'rggrggrgr', ' gg gg gg', 'rgggggggr'],
    glyph: [' ^ ^ ^ ^ ', '/o\\/o\\/o\\', ' .. .. ..', '^.......^']},
  // Landmark site encounters (abandoned camp, fallen watchtower).
  camp_packs: {paint: ["  dd  oo ", " dddd ooo", " dddd ooo", "  uu  uu "],
    glyph: ["  /\\  ,. ", " (::) (*)", " (__) (_)", "  \"\"  \"\" "]},
  camp_firepit: {paint: ["    k    ", "  okkko  ", " gooooog ", "  ggggg  "],
    glyph: ["    |    ", "  \\.:./  ", " o=====o ", "  o-o-o  "]},
  camp_bedroll: {paint: ["  wwwwww ", " rrrrrrrr", " rwrwrwrr", "  uu  uu "],
    glyph: ["  ~~~~~~ ", " (======)", " (::::::)", "  \"\"  \"\" "]},
  tower_rubble: {paint: ["   gg    ", "  gxgg o ", " ggggxgo ", "gggggggg "],
    glyph: ["   ..    ", "  /:\\. / ", " /:.:\\./ ", "/______\\ "]},
  tower_stair: {paint: ["      gg ", "    gggg ", "  gggggg ", "gggggggg "],
    glyph: ["      _| ", "    _|:| ", "  _|::.| ", "_|:::::| "]},
  tower_armory: {paint: ["  ooooo  ", " oxoxoxo ", " ooooooo ", " gggggg  "],
    glyph: ["  |=|=|  ", " |+|+|+| ", " |_|_|_| ", " /::::\\  "]},
  // Woodcutters' clearing, hunter's lodge, ruined shrine, old barrow.
  lumber_logs: {paint: ['  oo oo  ', ' oooooooo', 'oooooooo ', ' uu   uu '],
    glyph: ['  () ()  ', ' (@)(@)(@', '(@)(@)(@)', ' "" ""   ']},
  lumber_shed: {paint: [' kkkkkkk ', 'kooooooo ', 'ko rr go ', 'ko dd go '],
    glyph: [' /=====\\ ', '/|-----| ', '||&& !|| ', '||[] ||| ']},
  lumber_oak: {paint: ['ll    l  ', 'llloooooo', ' looooooo', '  u    u '],
    glyph: ['^v    ^  ', 'v^(=====@', ' ^(=====@', '  "    " ']},
  lodge_racks: {paint: ['k     k ', 'kdddddk ', 'kdddddk ', 'k     k '],
    glyph: ['+-----+ ', '|#####| ', '|#:#:#| ', '/     \\ ']},
  lodge_snares: {paint: ['o   o   ', ' rr  rr ', 'oqqoqqoq', ' u   u  '],
    glyph: ['|   |   ', ' ()  () ', '-;;-;;-;', ' "   "  ']},
  lodge_trophies: {paint: ['w  w  w ', 'wkkwkkw ', ' kkkkk  ', ' k   k  '],
    glyph: ['Y  )  Y ', '\\=|=|=/ ', ' |===|  ', ' |   |  ']},
  shrine_altar: {paint: ['   yy    ', '  ggggg  ', ' gxg gxg ', ' ggg ggg ', 'ggggggggg'],
    glyph: ['   **    ', '  _/ \\_  ', ' |*| |*| ', ' |_| |_| ', '/_______\\']},
  shrine_offerings: {paint: ['  y  y   ', ' ggg ggg ', ' gyg gxg ', '  g   g  '],
    glyph: ['  .  $   ', ' \\$/ \\o/ ', ' (_) (_) ', '  "   "  ']},
  shrine_pillars: {paint: ['  xgx  ', '  g g  ', '  gxg  ', '  g g  ', ' ggggg '],
    glyph: ['  =o=  ', '  |@|  ', '  |o|  ', '  |@|  ', ' /___\\ ']},
  barrow_goods: {paint: ['  qqqqq  ', ' qgggggq ', 'qgu y ugq', 'qgu w ugq'],
    glyph: ['  _;;;_  ', ' /=====\\ ', '/|  $  |\\', ';|  "  |;']},
  barrow_stones: {paint: ['g   g   g', 'g q g q g', 'g q g q g', 'qqqqqqqqq'],
    glyph: ['n   n   n', '| , | , |', '| ; | ; |', ';;;;;;;;;']},
  barrow_bones: {paint: ['   w     ', '  www w  ', ' wwwwwww ', '  u   u  '],
    glyph: ['   o     ', '  )=( )  ', ' <=o==o> ', '  "   "  ']},
  // Forest chain leads: clues that point on, and what they lead to.
  broken_branches: {paint: ['  l    l ', ' oo   oo ', 'o  o o  o', ' u  u  u '],
    glyph: ['  ^    ^ ', ' /=   =\\ ', '/  \\ /  \\', ' "  "  " ']},
  cut_wood: {paint: [' o   kk  ', 'dddddkkk ', 'ddddddddd', ' u     u '],
    glyph: [' |   /\\  ', '(@)(@)\\| ', '(@)(@)(@)', ' "     " ']},
  trampled_bushes: {paint: ['l  l   l ', 'llqllqlll', 'qqqqqqqqq', ' u u u u '],
    glyph: ['v  ;   v ', '_,_;__,_;', '=========', ' v v v v ']},
  feeding_ground: {paint: ['  l r l  ', ' lllrlll ', 'u lllll u', '  u   u  '],
    glyph: ['  / o \\  ', ' /;;o;;\\ ', 'v ;;;;; v', '  v   v  ']},
  mushroom_dust: {paint: ['  c   c  ', ' c  c   c', 'w  c  c  ', '  w    w '],
    glyph: ['  .   \'  ', ' ,  .   \'', 'o  ,  .  ', '  o    o ']},
  rotten_log: {paint: ['  w  w   ', 'kkkkkkkkk', 'kukkkkkuk', ' qq   qq '],
    glyph: ['  n  n   ', '(=======)', '(o:::::o)', ' ;;   ;; ']},
  trail_marker: {paint: ['  dddd   ', '  dddd   ', '   k     ', '   k     ', '  qqq    '],
    glyph: ['  <==|   ', '  |==>   ', '   |     ', '   |     ', '  ;;;    ']},
  looping_path: {paint: [' dddddd  ', 'd      d ', 'd  ddd  d', ' ddd ddd '],
    glyph: [' .-~~-.  ', '(      ) ', '\'  .-.  )', ' \'-\' \'-\' ']},
  map_scrap: {paint: ['dddddddd ', 'ddrdddkd ', 'dddrrddd ', 'kddddddd '],
    glyph: ['.------. ', '|.-.  x| ', "|  '-.-| ", "'------' "]},
  hidden_stash: {paint: ['   uuu   ', ' uuddduu ', 'uudydduu ', ' uuuuuu  '],
    glyph: ['   ,.,   ', ' ./==\\.  ', '.|[o]=|. ', ' \'\'\'\'\'\'  ']},
  // The riverbank: things beside a river or ford, and the chains that lead along it.
  reed_bed: {paint: ['q q q q  ', 'qlqlqlq  ', 'qlqlqlql ', 'aaaaaaaaa'],
    glyph: ['| | | |  ', '|\\|/|\\|  ', '|||||||/ ', '~~~~~~~~~']},
  fishing_pool: {paint: ['  ggggg  ', ' gaaaaag ', 'gaacaaaag', ' ggggggg '],
    glyph: ['  .---.  ', ' /~ ~~ \\ ', '(~ ><> ~)', ' \\_____/ ']},
  river_shallows: {paint: ['  aa aa  ', ' agaagaa ', 'aaagaagaa', ' aaaaaaa '],
    glyph: ['  ~~ ~~  ', ' ~o~~o~~ ', '~~~O~~o~~', ' ~~~~~~~ ']},
  fishing_net: {paint: [' w   r   ', 'wdddddddw', 'dwdwdwdwd', ' ddddddd '],
    glyph: [' o   o   ', '#########', '#+#+#+#+#', ' ####### ']},
  fish_scales: {paint: ['  c   c  ', ' c  c   c', '  c   c  ', ' uu  uu  '],
    glyph: ['  *   *  ', ' *  \'   *', '  \'   *  ', ' ""  ""  ']},
  busy_pool: {paint: [' c  c  c ', ' gaaaaag ', 'gaacaacag', ' ggggggg '],
    glyph: [' \'  .  \' ', ' /~><~~\\ ', '(~ ><> <)', ' \\_____/ ']},
  ripples: {paint: [' aaaaaaa ', 'aaaaaaaaa', ' aaaaaaa '],
    glyph: [' ( ~ ~ ) ', '( ( O ) )', ' ( ~ ~ ) ']},
  float_line: {paint: ['r   r   r', 'kkkkkkkkk', 'aaaaaaaaa'],
    glyph: ['o   o   o', '~-~-~-~-~', '~~~~~~~~~']},
  fishing_platform: {paint: ['ooooo    ', 'oo oo k  ', 'k  k  kk ', 'aaaaaaaaa'],
    glyph: ['=====    ', '== =/ |  ', '|  |  |\\ ', '~~~~~~~~~']},
  bootprints: {paint: ['u    u   ', '  u    u ', 'u    u   ', '  u    u '],
    glyph: ['0    0   ', '  0    0 ', '0    0   ', '  0    0 ']},
  fishing_camp: {paint: ['  dd   k k', ' dddd  kck', 'dduudd kck', 'dduudd k k'],
    glyph: ['  /\\   | |', ' /..\\  |<|', '/_||_\\ |<|', '|_||_| | |']},
  fresh_footprints: {paint: ['u   u    ', '  u   u  ', '    u   u', 'qq    qq '],
    glyph: ['o   o    ', '  o   o  ', '    o   o', ';;    ;; ']},
  hidden_ford: {paint: ['aaaaaaaaa', 'agaaagaaa', 'aaagaaaga', 'aaaaaaaaa'],
    glyph: ['~~~~~~~~~', '~O~~~O~~~', '~~~O~~~O~', '~~~~~~~~~']},
  // Needs an axe: a standing dead tree to chop.
  dead_tree: {paint: ['  k   k  ', ' kk k kk ', '  kkokk  ', '   ooo   ', '  oo oo  '],
    glyph: ['  \\   /  ', ' \\\\ | // ', '  \\\\|//  ', '   |||   ', '  /| |\\  ']},
  // Temporary deer leads: a fresh hoof trail, then the deer itself at the crossing.
  deer_trail: {paint: ['k   k     ', '  k   k   ', '    k   k ', ' oo     k '],
    glyph: ['"   "     ', '  "   "   ', '    "   " ', ' /=     " ']},
  deer: {paint: ['       k k', '       dd ', ' wddddddd ', '  ddddddd ', '  d d  d d', '  k k  k k'],
    glyph: ['       Y Y', '       o> ', ' ,=====/  ', '  ;:;:;:  ', '  | |  | |', '  " "  " "']},
  wayside_shrine: {paint: ['    y    ', '  ggggg  ', ' ggggggg ', '  gxyxg  ', '  ggggg  ', ' qgggggq '],
    glyph: ['    +    ', '  /^^^\\  ', ' /_____\\ ', '  |*i*|  ', '  |___|  ', ' ;/___\\; ']}
});

/** A campfire the avatar made this life: a ring of stones, crossed sticks and a small
 * flickering flame with a warm glow. Ground decoration only (non-blocking). */
const FIRE_BASE = Object.freeze({paint: [' ko ok ', 'gokkkog', 'ggggggg'],
  glyph: [' \\/ \\/ ', 'o=XXX=o', 'o.o.o.o']});
const FLAME_ROLES = Object.freeze({y: {fill: '#ffd36a', ink: '#fff6c8'}, r: {fill: '#e8742c', ink: '#ffd36a'},
  d: {fill: '#b8323f', ink: '#ff9a5a'}});
export const FLAMES = Object.freeze([
  {paint: ['   y   ', '  yry  ', '  rdr  '], glyph: ['   ^   ', '  ^*^  ', '  ***  ']},
  {paint: ['  y    ', '  ryy  ', '  rdr  '], glyph: ['  ^    ', '  *^^  ', '  ***  ']},
  {paint: ['    y  ', '  yyr  ', '  rdr  '], glyph: ['    ^  ', '  ^^*  ', '  ***  ']},
]);
export function drawCampfire(ctx, x, y, {clock = 0, reducedMotion = false} = {}) {
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const ground = y + ACTOR_FOOT - 2;
  ctx.save();
  const pulse = reducedMotion ? 0 : Math.sin(clock / 240) * .04;
  const glow = ctx.createRadialGradient(x, ground - 8, 2, x, ground - 8, 46);
  glow.addColorStop(0, `rgba(255,170,80,${.30 + pulse})`); glow.addColorStop(1, 'rgba(255,140,60,0)');
  ctx.fillStyle = glow; ctx.beginPath(); ctx.ellipse(x, ground - 6, 46, 30, 0, 0, Math.PI * 2); ctx.fill();
  if (drawFireArt(ctx, x, ground, clock, reducedMotion)) { ctx.restore(); return; }
  const baseW = FIRE_BASE.paint[0].length * CELL_W;
  paintParts(ctx, FIRE_BASE, SPOT_ROLES, x - baseW / 2, ground - FIRE_BASE.paint.length * CELL_H);
  const flame = FLAMES[reducedMotion ? 0 : Math.floor(clock / 180) % FLAMES.length];
  const flameW = flame.paint[0].length * CELL_W;
  paintParts(ctx, flame, FLAME_ROLES, x - flameW / 2, ground - (FIRE_BASE.paint.length + 2) * CELL_H);
  ctx.restore();
}

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
  const stone = anchorStoneCanvas();
  if (stone) drawPainted(ctx, stone, x - 18 - STONE_W / 2, y - 5 - STONE_H);
  else paintParts(ctx, CAMP.stone, CAMP_ROLES, x - 36, y - 56);
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
  const part = (name, dx, dy) => {
    const painted = partCanvas(name === 'sack' ? 'ambushSack' : name);
    if (!painted?.canvas) { paintParts(ctx, AMBUSH[name], AMBUSH_ROLES, x + dx, y + dy); return; }
    drawPainted(ctx, painted.canvas, x + dx, y + dy + AMBUSH[name].paint.length * CELL_H - painted.h);
  };
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

/** Drawn for a spot whose art key has no sprite yet, so content is never invisible. */
export const FALLBACK_SPOT = Object.freeze({paint: ['  ggg  ', ' gxxxg ', '  ggg  '],
  glyph: ['  .-.  ', ' ( ? ) ', "  '-'  "]});

/** Sprite for a spot: its catalog art key (ActionDef.art, default the action id). */
export const spotSprite = spot => SPOTS[spot.art || spot.encounter] || FALLBACK_SPOT;

/** Spot at tile center (x, y); a sparkle marks it, brighter when it is the goal and in its
 * rarity color (catalog RarityDef, frame `glint`) for uncommon and rarer spots. */
export function drawSpot(ctx, spot, x, y, {clock = 0, goal = false, fade = 0} = {}) {
  if (!spot.encounter && !spot.art) return;
  const sprite = spotSprite(spot);
  setupText(ctx);
  x = Math.round(x); y = Math.round(y);
  const painted = spotCanvas(SPOTS[spot.art || spot.encounter] ? spot.art || spot.encounter : null);
  const w = painted ? painted.lw - 2 * painted.pad : sprite.paint[0].length * CELL_W;
  const h = painted ? painted.lh - 2 * painted.pad : sprite.paint.length * CELL_H;
  const left = x - w / 2, top = y + ACTOR_FOOT - 2 - h;
  ctx.save();
  if (painted) drawPainted(ctx, painted, left, top, 1 - fade);
  else paintParts(ctx, sprite, SPOT_ROLES, left, top, 1 - fade);
  ctx.globalAlpha = 1 - fade;
  if (!fade) {
    const lift = Math.round(Math.sin((clock + visualHash(spot.x, spot.y, 3) % 900) / 300) * 2);
    const sy = top - 7 + lift, size = goal || spot.glint ? 3 : 2;
    const diamond = r => { ctx.beginPath(); ctx.moveTo(x, sy - r * 1.3); ctx.lineTo(x + r, sy); ctx.lineTo(x, sy + r * 1.3); ctx.lineTo(x - r, sy); ctx.closePath(); ctx.fill(); };
    ctx.fillStyle = OUTLINE; diamond(size + 1.2);
    ctx.fillStyle = spot.glint || (goal ? '#fff0b0' : '#d8b860'); diamond(size);
    ctx.fillStyle = 'rgba(255, 255, 240, .7)'; ctx.fillRect(x - .5, sy - size * .9, 1, size * .8);
    if (spot.glint && Math.floor((clock + visualHash(spot.x, spot.y, 5) % 1200) / 400) % 3 === 0) {
      ctx.fillStyle = spot.glint;   // a slow twinkle: four points around the sparkle
      for (const [dx, dy] of [[0, -6], [0, 6], [-6, 0], [6, 0]]) ctx.fillRect(x + dx - 1, sy + dy - 1, 2, 2);
    }
  }
  ctx.restore();
}

/** A finished task leaves a brief, readable seal over its former spot. This is
 * presentation only; the encounter log and simulation decide completion. */
export function drawSpotCompletion(ctx, spot, x, y, age, reducedMotion = false) {
  if (age < 0 || age >= 650) return;
  const t = age / 650;
  ctx.save(); ctx.globalAlpha = Math.max(0, 1 - t);
  const color = spot.seal || '#ffe5a0';   // catalog CategoryStyle.seal
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
  const painted = elderCanvas(facing === 'east' ? 'east' : 'west');
  const width = painted ? ELDER_W : sprite.paint[0].length * CELL_W, height = painted ? ELDER_H : sprite.paint.length * CELL_H;
  const sway = reducedMotion ? 0 : Math.floor(clock / 900) % 2;
  const left = x - width / 2, top = y + ACTOR_FOOT - height + sway;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.fillStyle = 'rgba(3, 6, 3, .5)';
  ctx.beginPath(); ctx.ellipse(x, y + ACTOR_FOOT - 1, 15, 4, 0, 0, Math.PI * 2); ctx.fill();
  if (painted) drawPainted(ctx, painted, left, top, alpha);
  else paintParts(ctx, sprite, ELDER_ROLES, left, top, alpha);
  // Lantern-warm glint on the staff head.
  const gx = painted ? (facing === 'east' ? left + width - 6.1 : left + 2.1) : facing === 'east' ? left + width - CELL_W * 2 : left + CELL_W;
  ctx.globalAlpha = alpha * (.35 + (reducedMotion ? .1 : .15 * Math.sin(clock / 300)));
  const glow = ctx.createRadialGradient(gx + 2, top + 3.8, 1, gx + 2, top + 3.8, 12);
  glow.addColorStop(0, '#ffe7a0'); glow.addColorStop(1, '#ffe7a000');
  ctx.fillStyle = glow; ctx.fillRect(gx - 12, top - 11, 28, 28);
  if (talking) {  // three speech dots above the hood
    for (let i = 0; i < 3; i++) {
      const lift = reducedMotion ? 0 : Math.round(Math.max(0, Math.sin(clock / 160 - i * .9)) * 3);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = OUTLINE; ctx.beginPath(); ctx.arc(x - 6 + i * 7, top - 9 - lift, 3, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#f3e7c6'; ctx.beginPath(); ctx.arc(x - 6 + i * 7, top - 9 - lift, 2, 0, Math.PI * 2); ctx.fill();
    }
  }
  ctx.restore();
  return {left, top, width, height};
}

/** Buildings at the anchor camp (catalog BUILDINGS), built from several small parts in the same
 * outlined cell style as the ambush wreckage beside them. Presentation only. */
const BUILDING_ROLES = Object.freeze({
  d: {fill: '#4a3626', ink: '#a88a64'}, w: {fill: '#7a5532', ink: '#3b2a1c'},
  t: {fill: '#b59050', ink: '#6e5233'}, i: {fill: '#5f6660', ink: '#c9d0c4'},
  s: {fill: '#788278', ink: '#d9ddd0'}, h: {fill: '#a6845d', ink: '#5a4128'},
  r: {fill: '#c8a46a', ink: '#6e5233'}, c: {fill: '#8f7a55', ink: '#3b2a1c'},
  y: {fill: '#e5c772', ink: '#fff3bc'}});
export const BUILDING_PARTS = Object.freeze({
  rack: {paint: ["ddddddd", "dhhhhhd", "dhhhhhd", "d hhh d", "d     d"],
    glyph: ["+-=-=-+", "|/~~~\\|", "|(:::)|", "| \\_/ |", "|     |"]},
  bench: {paint: ["  i  y    ", "tttttttttt", "wwiiwwrrww", "w        w"],
    glyph: ["  T  o    ", "=-==-==-==", "|[=]|(@)||", "/        \\"]},
  grind: {paint: [" sss ", "sssss", "d s d"],
    glyph: [" .-. ", "(-o-)", "/ | \\"]},
  stump: {paint: [" ii ", "dddd", " dd "],
    glyph: [" /] ", "(@@)", " || "]},
  chest: {paint: [" ttttttt ", "wiwwwwwiw", "wiwwywwiw", "ddddddddd"],
    glyph: [" /=====\\ ", "|#|-=-|#|", "|#|=o=|#|", "\\_______/"]},
  barrel: {paint: [" dd ", "wiiw", "wwww", "wiiw"],
    glyph: [" __ ", "(==)", "|  |", "(==)"]},
  rope: {paint: ["rrr", "rrr"],
    glyph: [".@.", "(@)"]},
  sack: {paint: [" c ", "ccc", "ccc"],
    glyph: [" ^ ", "(:)", "(_)"]},
});
/** Per building: where it stands (tile offset from the anchor stone) and its parts, back to
 * front, as [part, dx px, dy px] with dy measured up from the ground line. */
export const BUILDING_ART = Object.freeze({
  crafting_station: {slot: [-3, 2], parts: [['rack', -34, 6], ['grind', -44, 0], ['bench', -20, 0],
    ['stump', 22, 0]]},
  storage_chest: {slot: [3, 2], parts: [['barrel', -32, 0], ['chest', -16, 0], ['sack', 22, 0], ['rope', 21, -2]]},
});

/** Draw `buildings` ({id, bound}) around the anchor stone at (x, y); bound ones carry a soul glint. */
export function drawBuildings(ctx, x, y, buildings = [], {clock = 0} = {}) {
  setupText(ctx);
  buildings.forEach((b, i) => {
    const art = BUILDING_ART[b.id];
    const [sx, sy] = art?.slot || [3, -2];
    const bx = Math.round(x + sx * 24), ground = Math.round(y + sy * 28 + ACTOR_FOOT - 2);
    ctx.save();
    if (art) {
      ctx.fillStyle = 'rgba(0,0,0,.28)';   // a soft footprint so the pieces read as one place
      ctx.beginPath(); ctx.ellipse(bx - 4, ground + 3, 30, 6, 0, 0, Math.PI * 2); ctx.fill();
      for (const [name, dx, dy] of art.parts) {
        const part = BUILDING_PARTS[name];
        const painted = partCanvas(name);
        if (painted?.canvas) drawPainted(ctx, painted.canvas, bx + dx, ground - dy - painted.h);
        else paintParts(ctx, part, BUILDING_ROLES, bx + dx, ground - dy - part.paint.length * CELL_H);
      }
    } else {
      paintParts(ctx, FALLBACK_SPOT, SPOT_ROLES, bx - 14, ground - 21);
    }
    if (b.bound) {   // bound to the anchor: a slow blue spark above it
      ctx.globalAlpha = .55 + .35 * Math.sin(clock / 600 + i);
      ctx.fillStyle = '#9fd0ff'; ctx.fillRect(bx - 2, ground - 48 - Math.round(Math.sin(clock / 400) * 2), 3, 3);
    }
    ctx.restore();
  });
}

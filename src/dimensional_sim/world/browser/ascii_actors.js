/** Fine ASCII actors: the avatar, the enemies and the old man as hand-made cell sprites on
 * small character cells (FINE: 2.2 x 3.6 px, against the classic 4 x 7), so a person can be
 * drawn about six heads tall and a boar half a person high, in the same paint + glyph rows as
 * every other sprite (sprites.js paintSprite). West views are the east rows mirrored.
 * Presentation only.
 */
export const FINE = Object.freeze([2.2, 3.6]);
const fill = (rows, w) => rows.map(r => r.padEnd(w, ' ').slice(0, w));
/** A fine sprite from paint and glyph rows (padded to the widest row) and its roles. */
export function fine(paint, glyph, roles) {
  const w = Math.max(...paint.map(r => r.length), ...glyph.map(r => r.length));
  if (paint.length !== glyph.length) throw new Error('paint and glyph rows differ');
  return Object.freeze({paint: fill(paint, w), glyph: fill(glyph, w), roles, cell: FINE});
}

// --- the avatar ------------------------------------------------------------------------
export const HERO_ROLES = Object.freeze({
  h: {fill: '#3c2a27', ink: '#86604e'}, s: {fill: '#e9b487', ink: '#4a2a1a'},
  c: {fill: '#9a4b3c', ink: '#e09a7c'}, m: {fill: '#6e3128', ink: '#b0604a'},
  g: {fill: '#5a6640', ink: '#a9b67a'}, y: {fill: '#a37a48', ink: '#f0d38a'},
  p: {fill: '#34443b', ink: '#7d9282'}, o: {fill: '#5a4736', ink: '#b29270'}});
// Heads are three rows of a person's ten or eleven: hair, eyes, chin.
const HEAD_SOUTH = [['    hhhh    ', '    /;;\\    '], ['    hssh    ', '    (oo)    '], ['     ss     ', '     ~~     ']];
const HEAD_NORTH = [['    hhhh    ', '    /;;\\    '], ['    hhhh    ', '    |;;|    '], ['     hh     ', '     ;;     ']];
const HEAD_EAST = [['    hhhh    ', '    /;;\\    '], ['    hhss    ', "    ;'o>    "], ['     hs     ', '     ;\\    ']];
const rows = list => [list.map(r => r[0]), list.map(r => r[1])];
function hero(head, body) {
  const [hp, hg] = rows(head), [bp, bg] = rows(body);
  return fine([...hp, ...bp], [...hg, ...bg], HERO_ROLES);
}
const LEGS_FRONT = {
  0: [['   pp  pp   ', '   ||  ||   '], ['  ooo  ooo  ', '  [_]  [_]  ']],
  1: [['   pp  ooo  ', '   ||  [_]  '], ['  ooo       ', '  [_]       ']],
  '-1': [['  ooo  pp   ', '  [_]  ||   '], ['       ooo  ', '       [_]  ']]};
const LEGS_EAST = {
  0: [['     pp     ', '     ||     '], ['     ooo    ', '     [_>    ']],
  1: [['    p  pp   ', '    /   \\   '], ['   oo   ooo ', '   [>   [_> ']],
  '-1': [['    pp  p   ', '    /   \\   '], ['   ooo   oo ', '   [_>   [> ']]};
/** Standing frames by facing ('south' | 'north' | 'east') and stride (-1 | 0 | 1). */
function standing(facing, stride) {
  const legs = (facing === 'east' ? LEGS_EAST : LEGS_FRONT)[stride];
  if (facing === 'east') {
    const swing = stride === 0 ? ['   mgggs    ', '   |::|o    '] : stride > 0 ? ['   mggggs   ', '   |:::/o   '] : ['  smgggg    ', '  o|:::|    '];
    return hero(HEAD_EAST, [['    mccc    ', '    ~==\\    '], ['   mgggg    ', '   |(::)    '], ['   mgggg    ', '   |(:|)    '],
      swing, ['   mggyg    ', '   |:#=\\    '], ...legs]);
  }
  if (facing === 'north') return hero(HEAD_NORTH, [['   cccccc   ', '   ~====~   '], ['  gccccccg  ', '  |\\||||/|  '], ['  gccccccg  ', '  | |||| |  '],
    ['  sccccccs  ', '  o ||||  o '], ['   cccccc   ', '   \\||||/   '], ...legs]);
  return hero(HEAD_SOUTH, [['   cccccc   ', '   ~====~   '], [' mgggggggm  ', ' |/(:||:)\\| '], [' mgggggggm  ', ' ||(::::)|| '],
    [' msyyyyysm  ', ' |o[=##]o|  '], ['  mggggggm  ', '  \\/::::\\/  '], ...legs]);
}
/** Crouching at work (crouch, sit and kneel share it). */
function crouching(facing) {
  if (facing === 'east') return hero(HEAD_EAST, [['   mcccs    ', '   ~==\\o    '], ['  mgggggs   ', '  |(:::)o   '], ['  oppppp    ', '  [/~~~\\    '], ['  ooo  oo   ', '  [_>  [>   ']]);
  if (facing === 'north') return hero(HEAD_NORTH, [['  scccccs   ', '  o~====~o  '], [' ppccccccpp ', ' (|||||||) '], [' ooo    ooo ', ' [_]    [_] ']]);
  return hero(HEAD_SOUTH, [['  scccccs   ', '  o~====~o  '], [' ppggggggpp ', ' (|(::::)|) '], [' ooo    ooo ', ' [_]    [_] ']]);
}
const MIRROR = {'/': '\\', '\\': '/', '(': ')', ')': '(', '<': '>', '>': '<', '[': ']', ']': '[', "'": "'"};
const flip = s => Object.freeze({...s, paint: s.paint.map(r => [...r].reverse().join('')),
  glyph: s.glyph.map(r => [...r].reverse().map(c => MIRROR[c] ?? c).join(''))});
const HERO_FRAMES = new Map();
/** The avatar's sprite for a facing, stride and pose. */
export function heroSprite(facing, stride = 0, compact = false) {
  const key = `${facing}|${stride}|${compact}`;
  if (!HERO_FRAMES.has(key)) {
    const side = facing === 'west' ? 'east' : facing;
    const base = compact ? crouching(side) : standing(side, stride);
    HERO_FRAMES.set(key, facing === 'west' ? flip(base) : base);
  }
  return HERO_FRAMES.get(key);
}

// --- enemies ------------------------------------------------------------------------------
const BOAR_ROLES = Object.freeze({
  f: {fill: '#5a3036', ink: '#a8606a'}, d: {fill: '#3e1f24', ink: '#8a4a52'}, n: {fill: '#9a6a6a', ink: '#3a1a1c'},
  t: {fill: '#efe6cf', ink: '#9d8f70'}, e: {fill: '#2a0b10', ink: '#ffb43c'}, v: {fill: '#33502a', ink: '#8fbf5a'},
  r: {fill: '#b8323f', ink: '#ffb0a0'}, o: {fill: '#1a0f0c', ink: '#6a5040'}});
/** Wild boar, side-on (east): bristled withers with brambles in the mane, a long snout, tusks. */
export const BOAR = fine([
  '     vvrvvrvv      ',
  '   dddddddddddd    ',
  '  dfffffffffffdd   ',
  'ddffffffffffffefnn ',
  ' dffffffffffffftnn ',
  '  ff ff    ff ff   ',
  '  oo oo    oo oo   '], [
  '     ^^*^^*^^      ',
  "   /\\/\\/\\/\\/\\/\\    ",
  '  (;;;;;;;;;;;;\\   ',
  "~(;;;;;;;;;;;;o;=o ",
  " \\;;;;;;;;;;;;;v=) ",
  "  || ||    || ||   ",
  "  '' ''    '' ''   "], BOAR_ROLES);
const WOLF_ROLES = Object.freeze({
  x: {fill: '#6a6f76', ink: '#b4bac2'}, z: {fill: '#3e4147', ink: '#80858c'}, w: {fill: '#a8adb3', ink: '#4a4e53'},
  E: {fill: '#20160a', ink: '#ffe066'}, k: {fill: '#101114', ink: '#55585e'}, o: {fill: '#2a2c30', ink: '#6a6e74'}});
/** Wolf, side-on (east): long and low, ears up, a long muzzle and a brushy tail. */
export const WOLF_FINE = fine([
  '                x  x ',
  '               xxxxx ',
  ' x   zzzzzzzzzzxxEwwk',
  'xx xxxxxxxxxxxxxxwww ',
  ' xxxxxxxxxxxxxxxx    ',
  '   xx  x     x  xx   ',
  '   oo  o     o  oo   '], [
  '                ^  ^ ',
  '               /;;;\\ ',
  ' ~   ~~~~~~~~~~;;o==o',
  "~/ ;;;;;;;;;;;;;;vvv ",
  ' \\;;;;;;;;;;;;;;;    ',
  '   ||  |     |  ||   ',
  "   ''  '     '  ''   "], WOLF_ROLES);
const BONE_ROLES = Object.freeze({
  g: {fill: '#d8d2bc', ink: '#5e584a'}, o: {fill: '#3a362e', ink: '#b9b29a'}, i: {fill: '#14100c', ink: '#8fe3ff'},
  j: {fill: '#8a8c82', ink: '#e4e6dc'}, u: {fill: '#5a3a22', ink: '#c39a62'}});
/** Restless bones: a person's frame with a small skull, raising a pitted old blade. */
export const BONES = fine([
  '   ggg    j ',
  '   igi    j ',
  '   ggg    j ',
  '    g     j ',
  '  ggggg   j ',
  ' g gog g uu ',
  ' g gog  g   ',
  ' g ggg      ',
  '   g g      ',
  '   g g      ',
  '  gg gg     '], [
  '   /^\\    | ',
  '   o-o    | ',
  '   ###    | ',
  '    |     | ',
  '  =(=)=   | ',
  ' / (=) \\ o+ ',
  ' | (=)  \\   ',
  ' o \\Y/      ',
  '   | |      ',
  '   | |      ',
  '  _| |_     '], BONE_ROLES);
const LURKER_ROLES = Object.freeze({
  l: {fill: '#2f5f57', ink: '#6fa898'}, n: {fill: '#9fbf8a', ink: '#5c7a4a'}, y: {fill: '#e8d84a', ink: '#2a2a10'},
  r: {fill: '#1b3d37', ink: '#7fc9b8'}, t: {fill: '#f1ecd2', ink: '#8a8670'}});
/** River lurker: low and wide, eyes up on top, a long toothed jaw, splayed legs. */
export const LURKER_FINE = fine([
  '    yl      ly    ',
  '  llllllllllllll  ',
  ' llllllllllllllll ',
  'rllttttttttttttllr',
  'rr  nnnnnnnnnn  rr'], [
  '    O,      ,O    ',
  '  (;;;;;;;;;;;;)  ',
  ' <::::::::::::::> ',
  '/(vvvvvvvvvvvvvv)\\',
  '<<  ~~~~~~~~~~  >>'], LURKER_ROLES);
const WISP_ROLES = Object.freeze({
  q: {fill: '#eaf6ff', ink: '#5b7fb8'}, u: {fill: '#7e9ad0', ink: '#e2eeff'}, v: {fill: '#3e4f86', ink: '#a9bcf2'}});
/** Pale wisp: a small cold light with a face, trailing wisps. */
export const WISP_FINE = fine([
  '  uuu  ',
  ' uqqqu ',
  ' uqqqu ',
  '  uqu  ',
  '  vuv  ',
  ' v v v ',
  ' v   v '], [
  '  .-.  ',
  ' (o o) ',
  ' ( o ) ',
  '  \\_/  ',
  '  )|(  ',
  ' ( | ) ',
  " '   ' "], WISP_ROLES);
export const ENEMY_FINE = Object.freeze({boar: BOAR, wolf: WOLF_FINE, skeleton: BONES, lurker: LURKER_FINE, wisp: WISP_FINE});
/** Side-on enemies turn to face the avatar. */
export const SIDE_ON = Object.freeze(new Set(['boar', 'wolf']));
const WEST = new Map();
export function enemySprite(kind, west = false) {
  const base = ENEMY_FINE[kind] || BOAR;
  if (!west || !SIDE_ON.has(kind)) return base;
  if (!WEST.has(kind)) WEST.set(kind, flip(base));
  return WEST.get(kind);
}

// --- the old man --------------------------------------------------------------------------
const ELDER_FINE_ROLES = Object.freeze({h: {fill: '#6b6457', ink: '#a39a86'}, r: {fill: '#57594f', ink: '#8d8f80'},
  s: {fill: '#d8b48c', ink: '#3a2618'}, w: {fill: '#ece6d6', ink: '#b9b19c'}, o: {fill: '#7b5a36', ink: '#b88c58'},
  g: {fill: '#f1d27a', ink: '#fff6cf'}, b: {fill: '#3a2c20', ink: '#76604a'}});
/** The old man, the avatar's height, stooped over his staff (held west), hood up, white beard. */
export const ELDER_FINE = fine([
  ' g   hhh   ',
  ' o  hhhhh  ',
  ' o hhsssh  ',
  ' o hswwwh  ',
  ' o swwwwrr ',
  ' o rrwwrrr ',
  ' o rrrrrrr ',
  ' o rrbbbrr ',
  ' o rrrrrrr ',
  ' o rrrrrrr ',
  ' o  bb bb  '], [
  ' *   /^\\   ',
  ' |  /:::\\  ',
  " | /('o.\\  ",
  ' | (;;;;)  ',
  ' |-;;;;;:\\ ',
  ' | |:;;::| ',
  ' | |:::::| ',
  ' | |-===-| ',
  ' | |:::::| ',
  ' | /:::::\\ ',
  ' |  -- --  '], ELDER_FINE_ROLES);
export const elderSprite = facing => facing === 'east' ? (WEST.get('elder-east') || (WEST.set('elder-east', flip(ELDER_FINE)), WEST.get('elder-east'))) : ELDER_FINE;

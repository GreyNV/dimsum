/** Browser adapter: snapshots in, character art out. Python owns all game rules. */
import {TILE_W, TILE_H, ZOOM, clamp, residentBounds, cameraView, follow, glide, retainResident, tileAt, visualHash, stickDirection, Controls} from './view.js';
import {PALETTE, OBJECT_PAD, paintChunk, treeAt, treeKind, drawObjects, canopyFade, pathCover, trailFade, put, putSwayed, setResolution} from './art.js';
import {drawPlayer, drawEnemy, drawEffect, drawPunchLines, drawUnarmedReach, drawDamage, drawFloat, drawReveal, drawSpot, drawSpotCompletion, drawCamp, drawBuildings, drawCampfire, drawAmbushSite, drawElder, occludingTreeTiles, hiddenBehind, TORSO_LIFT} from './actors.js';
import {PAGES, needsDetail, pageModel, PANELS, COLLAPSE_KEY, loadCollapsed, toggleCollapsed, defaultCollapsed, subtabsOf} from './pages.js';
import {debugText, ExpeditionHud, activityText, newRewards, prologueView, rewardTexts, reportIsFresh, reportStorageKey} from './hud.js';
import {clockText, regionCue, skillSlots, worldMode} from './world_ui.js';
import {locationAction, renderLocationContext} from './location_ui.js';
import {$, el, readUi, writeUi} from './dom.js';
import {hosted, request, releaseInput} from './transport.js';
import {drawMinimap, visibleAt} from './minimap.js';
import {anchorAction, renderAnchor} from './anchor_ui.js';
import {buildTabs, journalAction, renderSection, renderSubtabs} from './page_ui.js';
import {dayGrade, drawDayGrade, drawNight, nightAlpha, drawEdgeMarker, drawEyelids, drawPossessionAura, drawPossessionGround, drawPossessionTint, drawVignette, edgePoint, possessionGlow, tintPicture} from './scene_fx.js';
import {drawMotes, drawReflection, drawWaterGlints, isWater} from './nature_art.js';
import {drawBlownLeaves, swayKind, windShear} from './wind.js';
import {ACTOR_FOOT} from './sprites.js';
import {SOUND_KEY, SoundEngine, VOLUMES, loadSettings, soundEvents, surfaceOf} from './sound.js';

const canvas = $('scene'), ctx = canvas.getContext('2d'), mini = $('minimap'), map = mini.getContext('2d');
const chunks = new Map(), pictures = new Map(), controls = new Controls();
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
/* Design debug overlay: ?debug in the URL or the backquote key. Asks the server for its
 * debug block (seed, region, buckets, windows, pity, screening) on every poll. */
let debugOn = new URLSearchParams(location.search).has('debug');
let state = null, paused = true, zoom = ZOOM.initial, width = 0, height = 0, dpr = 1;
let camera = null, actor = null, lastFrame = 0, connection = 'connecting';
let mapDirty = true, polling = false, stopped = false, resolution = 0;
/* Cosmetic combat feedback derived from consecutive snapshots. Client clocks only
 * fade these marks; damage, timing and hits always come from the server. */
const hpSeen = new Map(), hits = new Map(), deaths = new Map();
/* Boars chase on the server; the client glides them between cells and plays a lunge
 * whenever a target's `strikes` counter rises (each one is a bite the avatar took). */
const enemyPos = new Map(), strikesSeen = new Map(), lunges = new Map();
const LUNGE_MS = 320;
let swing = {serial: 0, active: false, slashAt: null, lastMs: -1, effects: []};
/* Expedition presentation: reward popups and fading completed spots (cosmetic). */
const hud = new ExpeditionHud(), rewards = [], fadingSpots = new Map();
let lastRewardSeq = null, spotsSeen = new Map(), reportSeen = null, reportTimer = 0, pendingAction = null;
/* Prologue: where the old man stands, and his walk away once he has spoken (cosmetic). */
let elder = null, elderLeaving = null;
const ELDER_LEAVE_MS = 2200;
/* Synthesized sound (sound.js): events from snapshot diffs, ambience from the scene. */
const sound = new SoundEngine({settings: loadSettings(readUi(SOUND_KEY))});
let soundScene = {water: 0, fire: 0}, lastVolume = sound.settings.volume || 2;
function setSound(settings) {
  if (settings.volume > 0) lastVolume = settings.volume;
  sound.apply(settings); writeUi(SOUND_KEY, JSON.stringify(sound.settings));
  if (page === 'settings') renderPage(true);
}
/** How close water and fire are to the avatar (0..1), for the ambience beds. */
function listen(next) {
  const all = [...chunks.values()], {x, y} = next.player;
  let water = 0;
  for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
    const glyph = tileAt(all, x + dx, y + dy)?.glyph;
    if (glyph === 'w' || glyph === '%') water += 1 / (1 + Math.abs(dx) + Math.abs(dy));
  }
  const fires = [next.expedition?.campfire, next.expedition?.anchor].filter(Boolean);
  const fire = Math.max(0, ...fires.map(f => 1 - (Math.abs(f.x - x) + Math.abs(f.y - y)) / 7));
  return {water: Math.min(1, water / 4), fire};
}
const SEEN_REPORT_KEY = 'dimsum.report.seen';
const seenReport = () => readUi(SEEN_REPORT_KEY);
const markReport = (worldSeed, report) => writeUi(SEEN_REPORT_KEY, reportStorageKey(worldSeed, report));
/* Pages (tabs) and collapsible HUD panels. The detail block is requested at most twice a
 * second while a page that needs it is open, so ordinary polling stays small. */
let page = 'world', lastDetail = null, lastDetailAt = 0, pageSignature = '', armed = null, armTimer = 0;
const subpage = {};   // last subtab per page; the first subtab is each page's main view
const closedSections = new Set();
const isMobile = () => matchMedia('(max-width: 720px)').matches;
let collapsed = loadCollapsed(readUi(COLLAPSE_KEY), isMobile());
let controlMode = 'auto', bagOpen = false, pendingInteract = false;
let contextOpen = false, contextPaused = false;
/* Possession (manual control) comes from the server; the client only times its glow. */
let possessedSince = null;
let stickPointer = null;
const STICK_KEY = 'touch:stick';
const manualAllowed = () => !state?.expedition || controlMode === 'active';

function resetStick() {
  stickPointer = null;
  controls.steer(STICK_KEY, null);
  $('stick-thumb').style.transform = 'translate(-50%,-50%)';
}
function moveStick(event) {
  const rect = $('move-stick').getBoundingClientRect();
  const dx = event.clientX - (rect.left + rect.width / 2);
  const dy = event.clientY - (rect.top + rect.height / 2);
  const distance = Math.hypot(dx, dy), scale = distance ? Math.min(30, distance) / distance : 0;
  $('stick-thumb').style.transform = `translate(calc(-50% + ${Math.round(dx * scale)}px),calc(-50% + ${Math.round(dy * scale)}px))`;
  controls.steer(STICK_KEY, stickDirection(dx, dy));
}

function status(message) { if ($('status').textContent !== message) $('status').textContent = message; }
/** A short message that clears itself (skill hints, sound toggles). */
let toastTimer = 0;
function toast(message, ms = 3200) {
  status(message); clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { if ($('status').textContent === message) status(''); }, ms);
}
function resize() {
  width = innerWidth; height = innerHeight; dpr = Math.min(devicePixelRatio || 1, 3);
  // Paint the world as dense as the screen shows it (device pixels x a typical zoom).
  const res = setResolution(dpr >= 1.5 ? 3 : 2);
  if (res !== resolution) { resolution = res; pictures.clear(); }
  canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
  mini.width = Math.round(180 * dpr); mini.height = Math.round(130 * dpr);
  mapDirty = true;
}
function setPause(value) {
  paused = value;
  controls.reset();
  resetStick();
  $('pause-overlay').hidden = !paused;
  $('pause').setAttribute('aria-pressed', String(paused));
  $('pause').setAttribute('aria-label', paused ? 'Resume exploration' : 'Pause exploration');
  $('pause').innerHTML = (paused ? 'Resume' : 'Pause') + ' <span class="shortcut">P</span>';
  updateActivity();
}
function closeContext() {
  contextOpen = false;
  document.body.classList.remove('context-open');
  renderLocationContext(state?.expedition?.location_context, false);
  if (contextPaused) setPause(false);
  contextPaused = false;
}
function updateActivity() {
  if (!state) return;
  const tile = tileAt([...chunks.values()], state.player.x, state.player.y);
  const near = state.targets.find(t => t.hp > 0 && Math.abs(t.x - state.player.x) + Math.abs(t.y - state.player.y) <= 2);
  const surface = near ? `${near.name || 'Something'} nearby - ${near.hp} HP` : tile?.glyph === '%' ? 'Fording the river' : tile?.glyph === 'H' ? 'On an old bridge' : tile?.blocked ? 'Obstructed ground' : tile?.glyph === '=' ? 'On the old forest trail' : 'Among the trees';
  const auto = activityText(state, paused);
  const text = auto ?? (paused ? 'Paused - the forest can wait' : state.player.animation === 'attack' ? (state.expedition?.weapon?.item ? 'Weapon up' : 'Fists up') : surface);
  if ($('activity').textContent !== text) $('activity').textContent = text;
}
function changeZoom(delta) {
  zoom = clamp(Math.round((zoom + delta) * 10) / 10, ZOOM.min, ZOOM.max);
}
function adopt(next, sentControl = null) {
  const firstSnapshot = state === null;
  for (const chunk of next.chunks) {
    chunks.set(chunk.id, chunk);
    pictures.delete(chunk.id);   // painted lazily: visible now, others one per frame
  }
  retainResident(chunks, next.resident); retainResident(pictures, next.resident);
  if (state && !window.DIMSUM_FASTFORWARD)
    for (const event of soundEvents(state, next, (x, y) => surfaceOf(tileAt([...chunks.values()], x, y)?.glyph))) sound.play(event);
  soundScene = listen(next);
  observeCombat(next);
  observeExpedition(next);
  if (next.expedition?.anchor_space && !state?.expedition?.anchor_space) {
    if (page !== 'world') openPage('world');
    hud.hideReport();
    setPause(false);
  }
  state = next; mapDirty = true;
  controlMode = next.expedition?.anchor_space || next.expedition?.prologue ? 'auto' : worldMode(next.expedition);
  const active = controlMode === 'active';
  if (active && possessedSince === null) possessedSince = performance.now();
  if (!active) { possessedSince = null; resetStick(); }
  document.body.classList.toggle('active-control', active);
  document.body.classList.toggle('manual-unlocked', active);
  const possession = next.expedition?.possession;
  $('possess-clock').textContent = active ? clockText(possession?.remaining_ms || 0) : '';
  $('attack-state').textContent = next.expedition?.auto_target ? 'TARGET IN REACH' : 'AUTO STRIKE';
  $('region-tip').textContent = regionCue(next.expedition?.region);
  const progress = next.expedition?.activity;
  $('action-name').textContent = progress?.name || (active ? 'Choose your path' : 'Exploring');
  $('action-percent').textContent = progress ? `${Math.floor(progress.progress / 10)}%` : '';
  $('action-fill').style.width = `${progress ? progress.progress / 10 : 0}%`;
  for (const [index, slot] of skillSlots(next.expedition).entries()) {
    const button = document.querySelector(`[data-skill-slot="${index}"]`);
    button.dataset.state = slot.state;
    button.disabled = false;   // a tap on a skill that can't run explains why instead
    button.setAttribute('aria-disabled', String(!slot.usable));
    button.dataset.note = slot.note;
    button.querySelector('span').textContent = slot.name;
    let note = button.querySelector('small');
    if (!note) { note = document.createElement('small'); button.append(note); }
    note.textContent = slot.note;
    button.style.setProperty('--charge', String(slot.charge));
    button.title = slot.hint + (slot.usable ? '' : slot.note ? ` (${slot.note})` : '');
    button.setAttribute('aria-label', `Skill ${index + 1}: ${slot.name}. ${slot.note}. ${slot.hint}`);
  }
  if (firstSnapshot && $('report').hidden) setPause(false);
  hud.update(next);
  renderAnchor(next.expedition);
  if (next.expedition?.anchor_space && contextOpen) closeContext();
  renderLocationContext(next.expedition?.location_context, contextOpen);
  if (next.expedition?.detail) lastDetail = next.expedition.detail;
  if (page !== 'world') renderPage();
  const position = {x:(next.player.x + .5) * TILE_W, y:(next.player.y + .5) * TILE_H};
  if (!actor || Math.abs(actor.x - position.x) + Math.abs(actor.y - position.y) > TILE_W * 5) {
    actor = {...position}; camera = {...position};
  }
  const here = [...chunks.values()].find(c => c.x === Math.floor(next.player.x / c.width) && c.y === Math.floor(next.player.y / c.height));
  const biome = (here?.biome || 'Unknown').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  const site = next.expedition?.region?.site;
  const condition = next.expedition?.region?.condition;
  const region = site ? `${site}${condition ? ` (${condition.name.toLowerCase()})` : ''} · ${next.expedition.region.name}`
    : next.expedition?.region?.name || biome;
  if ($('biome').textContent !== region) $('biome').textContent = region;
  const line = `Dimensional Summoner - ${biome}`;
  if ($('biome-line').textContent !== line) $('biome-line').textContent = line;
  const debugPanel = $('debug-panel');
  debugPanel.hidden = !debugOn;
  if (debugOn) debugPanel.textContent = debugText(next.expedition?.debug);
  updateActivity();
}
function observeCombat(next) {
  const now = performance.now();
  for (const target of next.targets) {
    const before = hpSeen.get(target.id);
    if (before !== undefined && target.hp < before) {
      hits.set(target.id, {at: now, amount: before - target.hp});
      if (target.hp === 0) deaths.set(target.id, {at: now, target: {...target}});
    }
    hpSeen.set(target.id, target.hp);
    const struck = strikesSeen.get(target.id);
    if (struck !== undefined && (target.strikes || 0) > struck && next.expedition?.life === state?.expedition?.life
        && !window.DIMSUM_FASTFORWARD) {
      lunges.set(target.id, {at: now});
      const lost = Math.round(((state?.expedition?.vitals?.health ?? 0) - (next.expedition?.vitals?.health ?? 0)) / 100);
      const fed = Math.round(((state?.expedition?.vitals?.hunger ?? 0) - (next.expedition?.vitals?.hunger ?? 0)) / 100);
      if (lost <= 0 && fed > 0) rewards.push({text: `-${fed} hunger`, color: '#b9cfff', at: now});
      else rewards.push({text: lost > 0 ? `-${lost} health` : 'Struck!', color: '#ff7a63', at: now});
    }
    strikesSeen.set(target.id, target.strikes || 0);
  }
  const p = next.player;
  if (p.animation === 'attack') {
    if (swing.lastMs < 0 || p.animation_ms < swing.lastMs) swing = {serial: swing.serial + 1, active: false, slashAt: null, lastMs: 0, effects: []};
    if (p.active && !swing.active) { swing.active = true; swing.slashAt = now; swing.facing = p.facing; swing.effects = next.effects.map(e => ({...e})); }
    swing.lastMs = p.animation_ms;
  } else swing.lastMs = -1;
}
function observeExpedition(next) {
  const now = performance.now();
  if (!next.expedition) return;
  const seq = Math.max(0, ...next.expedition.log.map(e => e.seq));
  // No reward popups while host.js fast-forwards offline time: they would pile up unreadably.
  if (lastRewardSeq !== null && next.expedition.life === state?.expedition?.life && !window.DIMSUM_FASTFORWARD)
    for (const entry of newRewards(next, lastRewardSeq))
      rewardTexts(entry, next.expedition.item_colors, next.expedition.item_glints)
        .forEach((r, i) => rewards.push({...r, at: now + i * 180}));
  lastRewardSeq = Math.max(lastRewardSeq ?? 0, seq);
  const prologue = next.expedition.prologue;
  if (prologue) { elder = {...prologue.elder}; elderLeaving = null; }
  else if (elder) { elderLeaving = {...elder, at: now}; elder = null; }
  const report = next.expedition.report;
  // An empty report is the prologue's placeholder: the opening is told in the world.
  if (report && report.lines.length && report.seq !== reportSeen && !next.expedition.anchor_space) {
    const already = seenReport() === reportStorageKey(next.world_seed, report);
    if (!already && (report.life === 0 || reportSeen !== null || reportIsFresh(next.expedition))) {
      markReport(next.world_seed, report);
      setPause(true);
      hud.showReport(report);
      $('pause-overlay').hidden = true;
      clearTimeout(reportTimer);
    }
    reportSeen = report.seq;
  }
  if (next.expedition.anchor_space && report) reportSeen = report.seq;
  if (state?.expedition && next.expedition.life !== state.expedition.life) {
    actor = null; hits.clear(); deaths.clear(); hpSeen.clear(); enemyPos.clear(); lunges.clear(); rewards.length = 0; fadingSpots.clear();
  }
  const current = new Map((next.spots || []).map(s => [s.id, s]));
  for (const [id, spot] of spotsSeen) {
    const coordinates = `:${Math.floor(spot.x / next.chunk_width)}:${Math.floor(spot.y / next.chunk_height)}`;
    if (!current.has(id) && next.expedition.life === state?.expedition?.life && next.resident.some(chunk => chunk.endsWith(coordinates)))
      fadingSpots.set(id, {at: now, spot});
  }
  spotsSeen = current;
}
function attackPhase(player) {
  if (player.animation !== 'attack') return null;
  return player.active ? 'strike' : swing.active ? 'recover' : 'windup';
}
/** Canopies south of an actor are repainted over it; over the avatar they are see-through,
 * so it never vanishes into the leaves while walking behind a tree. */
let canopyLayer = null;
/** Repaint the canopies that stand in front of an actor at tile (tx, ty), only over `box`
 * (the actor's own picture, world px [x0, y0, x1, y1]; default: around the tile). */
function repaintCanopies(tx, ty, resident, alpha = 1, box = null) {
  const cx = (tx + .5) * TILE_W, cy = (ty + .5) * TILE_H;
  const [bx0, by0, bx1, by1] = box || [cx - 22, cy - 48, cx + 22, cy + 14];
  const trees = [];
  for (const tile of occludingTreeTiles(tx, ty)) {
    const chunk = resident.find(c => Math.floor(tile.x / c.width) === c.x && Math.floor(tile.y / c.height) === c.y);
    if (!chunk) continue;
    const lx = tile.x - chunk.x * chunk.width, ly = tile.y - chunk.y * chunk.height;
    if (chunk.tiles[ly][lx] !== 'T') continue;
    const t = treeAt(tile.x * TILE_W, tile.y * TILE_H, visualHash(tile.x, tile.y, chunk.seed), undefined, treeKind(chunk, lx, ly));
    const ax = actor ? actor.x / TILE_W - .5 : 0, ay = actor ? actor.y / TILE_H - .5 : 0;
    t.shear = reducedMotion ? 0 : windShear(tile.x, tile.y, frameNow, 'tree');   // same wind as the ground pass
    t.fade = actor && !state?.expedition?.anchor_space   // same rule as the ground pass
      ? Math.min(canopyFade(tile.x - ax, tile.y - ay), trailFade(pathCover(chunk, lx, ly), ax, ay)) : 1;
    if (t.x < bx1 && t.x + t.canvas.lw > bx0 && t.y < by1 && t.y + t.canvas.lh > by0) trees.push(t);
  }
  if (!trees.length) return;
  if (alpha >= 1) { for (const t of trees) { ctx.globalAlpha = t.fade; putSwayed(ctx, t.canvas, t.x, t.y, t.shear); } ctx.globalAlpha = 1; return; }
  // See-through leaves: the overlapping trees are composed at full strength off-screen (so
  // nearer canopies still hide farther trunks), then laid over the actor at `alpha`.
  const m = ctx.getTransform();
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const t of trees) {
    x0 = Math.min(x0, t.x); y0 = Math.min(y0, t.y); x1 = Math.max(x1, t.x + t.canvas.lw); y1 = Math.max(y1, t.y + t.canvas.lh);
  }
  x0 = Math.max(x0, bx0); y0 = Math.max(y0, by0); x1 = Math.min(x1, bx1); y1 = Math.min(y1, by1);   // only over the actor
  const X0 = Math.max(0, Math.floor(m.a * x0 + m.e)), Y0 = Math.max(0, Math.floor(m.d * y0 + m.f));
  const X1 = Math.min(canvas.width, Math.ceil(m.a * x1 + m.e)), Y1 = Math.min(canvas.height, Math.ceil(m.d * y1 + m.f));
  if (X1 <= X0 || Y1 <= Y0) return;
  canopyLayer ||= document.createElement('canvas');
  if (canopyLayer.width < X1 - X0) canopyLayer.width = X1 - X0;
  if (canopyLayer.height < Y1 - Y0) canopyLayer.height = Y1 - Y0;
  const g = canopyLayer.getContext('2d');
  g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, X1 - X0, Y1 - Y0);
  g.setTransform(m.a, 0, 0, m.d, m.e - X0, m.f - Y0);
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'low';
  for (const t of trees) { g.globalAlpha = t.fade; putSwayed(g, t.canvas, t.x, t.y, t.shear); }
  g.globalAlpha = 1;
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = alpha;
  ctx.drawImage(canopyLayer, 0, 0, X1 - X0, Y1 - Y0, X0, Y0, X1 - X0, Y1 - Y0);
  ctx.restore();
}
/** Exactly one request in flight. Server fixed ticks and input lease own timing. */
async function poll() {
  if (polling || stopped) return;
  polling = true;
  const started = performance.now();
  try {
    const body = controls.payload(paused, [...chunks.keys()]);
    if (pendingInteract) body.interact = true;
    if (pendingAction) body.action = pendingAction;
    if (debugOn) body.debug = true;
    if (needsDetail(page) && (!lastDetail || started - lastDetailAt > 500)) { body.detail = true; lastDetailAt = started; }
    const attackRevision = controls.attackRevision;
    const next = await request('/api/input', body);
    controls.acknowledge(body, attackRevision);
    // Clear only what this request carried: a click made while it was in flight is sent next.
    if (pendingAction === body.action) pendingAction = null;
    if (body.interact) pendingInteract = false;
    adopt(next);
    if (connection !== 'connected') { connection = 'connected'; status(''); }
  } catch {
    connection = 'disconnected';
    controls.reset(); setPause(true);
    status('Connection interrupted. Reconnecting with the world paused...');
  } finally {
    polling = false;
    if (!stopped) setTimeout(poll, Math.max(0, 50 - (performance.now() - started)));
  }
}
/** Where to draw a target now: glides toward its cell, plus a short lunge at the avatar. */
function enemyXY(t, now, dt = 0) {
  const tx = (t.x + .5) * TILE_W, ty = (t.y + .5) * TILE_H;
  let p = enemyPos.get(t.id);
  if (!p || Math.abs(p.x - tx) + Math.abs(p.y - ty) > TILE_W * 4 || reducedMotion) p = {x: tx, y: ty};
  else if (dt) p = {x: follow(p.x, tx, dt, 90), y: follow(p.y, ty, dt, 90)};
  if (dt || !enemyPos.has(t.id)) enemyPos.set(t.id, p);
  let x = p.x, y = p.y;
  const lunge = lunges.get(t.id);
  if (lunge && state) {
    const age = now - lunge.at;
    if (age >= LUNGE_MS) lunges.delete(t.id);
    else if (!reducedMotion) {
      const k = age < 110 ? age / 110 : 1 - (age - 110) / (LUNGE_MS - 110);
      const dx = state.player.x - t.x, dy = state.player.y - t.y, len = Math.hypot(dx, dy) || 1;
      x += dx / len * 8 * k; y += dy / len * 6 * k;
    }
  }
  return {x, y};
}
/** Global coordinates of a chunk's water tiles, cached on its painted picture. */
function waterTiles(chunk) {
  const picture=pictures.get(chunk.id);
  if(picture.water) return picture.water;
  picture.water=[];
  chunk.tiles.forEach((row,y)=>[...row].forEach((glyph,x)=>{
    if(isWater(glyph)) picture.water.push([chunk.x*chunk.width+x,chunk.y*chunk.height+y]);
  }));
  return picture.water;
}
let frameNow = 0;   // this frame's clock, shared by every wind-swayed pass
function render(now) {
  frameNow = now;
  const dt=Math.min(100,now-lastFrame || 16); lastFrame=now;
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.fillStyle=PALETTE.void; ctx.fillRect(0,0,width,height);
  if (state?.expedition?.anchor_space && state.expedition.anchor_space.kind !== 'contact') {
    const scale=Math.min(2.6,width/240,height/340);
    ctx.translate(width/2,height*.38);ctx.scale(scale,scale);
    drawCamp(ctx,-48,-15,{clock:state.expedition.total_ms,reducedMotion});
    drawPlayer(ctx,state.player,59,-11,null,{clock:state.expedition.total_ms});
    if(!stopped)requestAnimationFrame(render);
    return;
  }
  if (state && actor && camera) {
    const tx=(state.player.x+.5)*TILE_W, ty=(state.player.y+.5)*TILE_H;
    if (reducedMotion) { actor.x=tx; actor.y=ty; }
    else Object.assign(actor, glide(actor, {x:tx, y:ty}, dt, state.movement_interval_ms));
    camera.x=reducedMotion ? actor.x : follow(camera.x,actor.x,dt,140);
    camera.y=reducedMotion ? actor.y : follow(camera.y,actor.y,dt,140);
    const resident=[...chunks.values()].sort((a,b)=>a.y-b.y || a.x-b.x);
    const view=cameraView(camera,width,height,zoom,residentBounds(resident));
    // Same transform as translate(w/2,h/2) scale(s) translate(-x,-y), with the offset
    // rounded to whole device pixels so stamps and cell edges never land between pixels.
    const ds=view.scale*dpr;
    ctx.setTransform(ds,0,0,ds,Math.round(dpr*width/2-ds*view.x),Math.round(dpr*height/2-ds*view.y));
    ctx.imageSmoothingEnabled=false;
    const visible=resident.filter(c=>(c.x+1)*c.width*TILE_W+OBJECT_PAD>view.x-width/view.scale/2 &&
      c.x*c.width*TILE_W-OBJECT_PAD<view.x+width/view.scale/2 &&
      (c.y+1)*c.height*TILE_H+OBJECT_PAD>view.y-height/view.scale/2 &&
      c.y*c.height*TILE_H-OBJECT_PAD<view.y+height/view.scale/2);
    const fog = state.fog || {};
    const revealed = visible.filter(c => fog[`${c.x}:${c.y}`]);
    const inSight = (x, y) => visibleAt(fog, x, y, state.chunk_width, state.chunk_height);
    // Paint any visible chunk that is still missing, then at most one off-screen
    // chunk per frame, so a border crossing never paints 3-5 chunks in one frame.
    for(const chunk of revealed) if(!pictures.has(chunk.id)) pictures.set(chunk.id, paintChunk(chunk));
    const pending=resident.find(c=>fog[`${c.x}:${c.y}`] && !pictures.has(c.id));
    if(pending) pictures.set(pending.id, paintChunk(pending));
    // Clip the painted world to contiguous revealed tile runs. This also keeps tall
    // props rooted in hidden cells from spilling into explored ground.
    ctx.save(); ctx.beginPath();
    for(const chunk of revealed) {
      const rows=fog[`${chunk.x}:${chunk.y}`];
      for(let ry=0;ry<chunk.height;ry++) {
        const row=rows[ry] || '';
        for(let rx=0;rx<chunk.width;) {
          if(row[rx] !== '1') { rx++; continue; }
          const start=rx;
          while(rx<chunk.width && row[rx] === '1') rx++;
          ctx.rect((chunk.x*chunk.width+start)*TILE_W,(chunk.y*chunk.height+ry)*TILE_H,
            (rx-start)*TILE_W,TILE_H);
        }
      }
    }
    ctx.clip();
    for(const chunk of revealed) put(ctx,pictures.get(chunk.id).ground,chunk.x*chunk.width*TILE_W,chunk.y*chunk.height*TILE_H);
    // Region tint: a flat, low-alpha wash per chunk so regions read at a glance (VISUAL_STYLE.md effects pass).
    // Organic regions (generator v3) send one tint code per tile; the wash is cached per chunk.
    for(const chunk of revealed) if(chunk.tint) {
      ctx.globalAlpha=.28;
      const tint = chunk.tint_rows ? tintPicture(chunk, pictures.get(chunk.id)) : null;
      if (tint) ctx.drawImage(tint, chunk.x*chunk.width*TILE_W, chunk.y*chunk.height*TILE_H);
      else {
        ctx.fillStyle=chunk.tint;
        ctx.fillRect(chunk.x*chunk.width*TILE_W,chunk.y*chunk.height*TILE_H,chunk.width*TILE_W,chunk.height*TILE_H);
      }
      ctx.globalAlpha=1;
    }
    if(!reducedMotion) for(const chunk of revealed) drawWaterGlints(ctx, waterTiles(chunk), state.clock_ms);
    // The avatar mirrored in water just south of it (under the objects layer's canopies).
    const pool=[];
    for(let dy=1;dy<=2;dy++) for(let dx=-1;dx<=1;dx++) {
      const tile=tileAt(resident,state.player.x+dx,state.player.y+dy);
      if(tile && isWater(tile.glyph)) pool.push([(state.player.x+dx)*TILE_W,(state.player.y+dy)*TILE_H,TILE_W,TILE_H]);
    }
    if(pool.length && !state.expedition?.prologue) drawReflection(ctx,pool,actor.y+ACTOR_FOOT,c=>drawPlayer(c,state.player,actor.x,actor.y,
      attackPhase(state.player),{clock:state.clock_ms,reducedMotion,weapon:state.expedition?.weapon}),.38);
    // Enemies standing by water are mirrored in it too.
    for(const t of state.targets) {
      if(t.hp<=0 || !inSight(t.x,t.y)) continue;
      const wet=[];
      for(let dy=1;dy<=2;dy++) for(let dx=-1;dx<=1;dx++) {
        const tile=tileAt(resident,t.x+dx,t.y+dy);
        if(tile && isWater(tile.glyph)) wet.push([(t.x+dx)*TILE_W,(t.y+dy)*TILE_H,TILE_W,TILE_H]);
      }
      if(!wet.length) continue;
      const at=enemyXY(t,now);
      drawReflection(ctx,wet,at.y+ACTOR_FOOT,c=>drawEnemy(c,t,at.x,at.y,{clock:state.clock_ms,reducedMotion,reflection:true,west:actor.x<at.x}),.32);
    }
    ctx.restore();
    // Hidden ground stays dark (under the objects, so canopies of explored trees reach over it).
    ctx.fillStyle='#101b17';
    for(const chunk of visible) {
      const x=chunk.x*chunk.width*TILE_W, y=chunk.y*chunk.height*TILE_H;
      const rows=fog[`${chunk.x}:${chunk.y}`];
      for(let row=0;row<chunk.height;row++) {
        const mask=rows?.[row] || '';
        for(let col=0;col<chunk.width;) {
          if(mask[col] === '1') { col++; continue; }
          const start=col;
          while(col<chunk.width && mask[col] !== '1') col++;
          ctx.fillRect(x+start*TILE_W,y+row*TILE_H,(col-start)*TILE_W,TILE_H);
        }
      }
    }
    // Trees, rocks and structures rooted in explored tiles draw whole - a tall canopy reaches
    // over the dark beyond instead of being cut off at the fog line.
    ctx.imageSmoothingEnabled=true; ctx.imageSmoothingQuality='low';   // trees and actors: resampled smoothly
    for(const chunk of revealed) {
      const rows=fog[`${chunk.x}:${chunk.y}`];
      const ax=actor.x/TILE_W-.5, ay=actor.y/TILE_H-.5;
      drawObjects(ctx,pictures.get(chunk.id),chunk.x*chunk.width*TILE_W,chunk.y*chunk.height*TILE_H,(tx,ty)=>rows?.[ty]?.[tx]==='1',
        (tx,ty,item)=>chunk.tiles[ty][tx]==='T' && !state.expedition?.anchor_space
          ? Math.min(canopyFade(chunk.x*chunk.width+tx-ax, chunk.y*chunk.height+ty-ay), trailFade(item.cover, ax, ay)) : 1,
        reducedMotion ? null : (tx,ty,item)=>windShear(chunk.x*chunk.width+tx, chunk.y*chunk.height+ty, now, swayKind(item, chunk.tiles[ty][tx])));
    }
    const anchor = state.expedition?.anchor;
    if (anchor && inSight(anchor.x,anchor.y)) {
      drawAmbushSite(ctx, (anchor.x+.5)*TILE_W, (anchor.y+.5)*TILE_H);
      drawCamp(ctx, (anchor.x+.5)*TILE_W, (anchor.y+.5)*TILE_H, {clock: state.clock_ms, reducedMotion});
      drawBuildings(ctx, (anchor.x+.5)*TILE_W, (anchor.y+.5)*TILE_H, state.expedition?.camp?.buildings, {clock: state.clock_ms});
      // the wreckage and camp lie on the ground: trees standing south of them stay in front
      for (let dx = -7; dx <= 7; dx++) repaintCanopies(anchor.x + dx, anchor.y + 1, revealed, 1,
        [(anchor.x + dx) * TILE_W, (anchor.y - 3) * TILE_H, (anchor.x + dx + 1) * TILE_W, (anchor.y + 3) * TILE_H]);
    }
    const fire = state.expedition?.campfire;
    if (fire && inSight(fire.x, fire.y))
      drawCampfire(ctx, (fire.x+.5)*TILE_W, (fire.y+.5)*TILE_H, {clock: state.clock_ms, reducedMotion});
    if (fire && inSight(fire.x, fire.y)) repaintCanopies(fire.x, fire.y, revealed, 1);
    const goal = state.expedition?.goal;
    // Spots sit on the ground: canopies south of them cover them too, see-through so they still read.
    const spots = (state.spots || []).filter(spot => inSight(spot.x, spot.y)).sort((a, b) => a.y - b.y);
    for (const spot of spots) {
      drawSpot(ctx, spot, (spot.x+.5)*TILE_W, (spot.y+.5)*TILE_H, {clock: state.clock_ms, goal: !!goal && goal.x === spot.x && goal.y === spot.y});
      repaintCanopies(spot.x, spot.y, revealed, .55);
    }
    for (const [id, f] of fadingSpots) {
      const age = now - f.at;
      if (age >= 650) { fadingSpots.delete(id); continue; }
      if (!inSight(f.spot.x,f.spot.y)) continue;
      drawSpot(ctx, f.spot, (f.spot.x+.5)*TILE_W, (f.spot.y+.5)*TILE_H, {fade: Math.min(1, age / 500)});
      drawSpotCompletion(ctx, f.spot, (f.spot.x+.5)*TILE_W, (f.spot.y+.5)*TILE_H, age, reducedMotion);
    }
    // Actors are depth-sorted by feet row; canopies south of each actor are repainted over it.
    const actors=state.targets.filter(t=>inSight(t.x,t.y) && (t.hp>0 || (deaths.has(t.id) && now-deaths.get(t.id).at<600)))
      .map(t=>({kind:'enemy',row:t.y,tx:t.x,ty:t.y,target:t}));
    actors.push({kind:'player',row:actor.y/TILE_H-.5,tx:state.player.x,ty:state.player.y});
    const prologue = state.expedition?.prologue ?? null;
    if (elder && inSight(elder.x,elder.y)) actors.push({kind:'elder',row:elder.y,tx:elder.x,ty:elder.y,alpha:1,shift:0,
      facing:state.player.x < elder.x ? 'west' : 'east',talking:prologue?.stage === 'listen'});
    else if (elderLeaving && inSight(elderLeaving.x,elderLeaving.y)) {
      const age = now - elderLeaving.at;
      if (age >= ELDER_LEAVE_MS) elderLeaving = null;
      else actors.push({kind:'elder',row:elderLeaving.y,tx:elderLeaving.x,ty:elderLeaving.y,
        alpha:1 - age / ELDER_LEAVE_MS,shift:reducedMotion ? 0 : age / ELDER_LEAVE_MS * TILE_W * 2.5,facing:'east',talking:false});
    }
    // Prologue poses: kneeling while waking, rising, then standing to listen.
    let activity = state.expedition?.activity ?? null;
    if (prologue) activity = prologue.stage === 'listen' ? null
      : {...activity, kind: prologue.stage === 'awaken' || prologue.progress < 650 ? 'kneel' : 'stand'};
    actors.sort((a,b)=>a.row-b.row || (a.kind==='player')-(b.kind==='player'));
    for(const item of actors) {
      if(item.kind==='player') {
        const glow = possessionGlow(state.expedition?.possession, possessedSince === null ? Infinity : now - possessedSince);
        if (glow) drawPossessionGround(ctx, actor.x, actor.y, {clock: now, glow, foot: ACTOR_FOOT, reducedMotion});
        drawPlayer(ctx,state.player,actor.x,actor.y,attackPhase(state.player),
          {activity, clock:state.clock_ms, reducedMotion, weapon: state.expedition?.weapon});
        if (glow) drawPossessionAura(ctx, actor.x, actor.y, {clock: now, glow, lift: TORSO_LIFT, reducedMotion,
          sinceMs: possessedSince === null ? Infinity : now - possessedSince});
      }
      else if(item.kind==='elder') drawElder(ctx,(item.tx+.5)*TILE_W+item.shift,(item.ty+.5)*TILE_H,
        {clock:state.clock_ms,facing:item.facing,alpha:item.alpha,talking:item.talking,reducedMotion});
      else {
        const t=item.target, hit=hits.get(t.id), death=deaths.get(t.id);
        const at=enemyXY(t,now,dt);
        drawEnemy(ctx,t,at.x,at.y,{clock:state.clock_ms,reducedMotion,west:actor.x<at.x,
          hit:hit?now-hit.at:Infinity,dying:t.hp===0&&death?Math.min(1,(now-death.at)/600):null});
      }
      // the avatar's own trees are already thinned (canopyFade); others' leaves are see-through
      if(item.kind!=='player') repaintCanopies(item.tx,item.ty,revealed,.6);   // leaves over actors are see-through
    }
    for(const t of state.targets) if(inSight(t.x,t.y) && hiddenBehind(t,state.player)) {
      const hit=hits.get(t.id);
      const at=enemyXY(t,now);
      drawEnemy(ctx,t,at.x,at.y,{clock:state.clock_ms,reducedMotion,west:actor.x<at.x,ghost:true,hit:hit?now-hit.at:Infinity});
    }
    if (state.expedition?.control === 'manual' && !prologue) {
      const target = state.targets.find(t=>t.id===state.expedition.auto_target && t.hp>0 && inSight(t.x,t.y));
      drawUnarmedReach(ctx,actor.x,actor.y,target ? [(target.x+.5)*TILE_W,(target.y+.5)*TILE_H] : null,
        state.player.animation === 'attack', state.expedition?.attack_radius || 1);
    }
    // Combat marks draw above canopies so a swing is never hidden by leaves.
    if(swing.slashAt!==null) {
      const age=now-swing.slashAt;
      if(!reducedMotion) drawPunchLines(ctx,actor.x,actor.y,swing.facing,age);
      if(age<220) for(const e of swing.effects) if(inSight(e.x,e.y))
        drawEffect(ctx,(e.x+.5)*TILE_W,(e.y+.5)*TILE_H-TORSO_LIFT,age);
    }
    for(const t of state.targets) {
      const hit=hits.get(t.id);
      if(hit && now-hit.at<600 && inSight(t.x,t.y)) {
        const at=enemyXY(t,now); drawDamage(ctx,at.x,at.y-44,hit.amount,reducedMotion?0:now-hit.at);
      }
    }
    if(!reducedMotion && !state.expedition?.anchor_space) drawBlownLeaves(ctx,view.x-width/view.scale/2,view.y-height/view.scale/2,
      view.x+width/view.scale/2,view.y+height/view.scale/2,now,{tileW:TILE_W,tileH:TILE_H});
    if(!reducedMotion) drawMotes(ctx,view.x-width/view.scale/2,view.y-height/view.scale/2,
      view.x+width/view.scale/2,view.y+height/view.scale/2,state.clock_ms,
      ...(state.expedition?.region?.shimmer ? [2.4, ['#b493ff', '#efe4ff']] : []));
    for (let i = rewards.length - 1; i >= 0; i--) {
      const age = now - rewards[i].at;
      if (age > 1600) { rewards.splice(i, 1); continue; }
      if (age < 0) continue;
      if (rewards[i].glint) drawReveal(ctx, actor.x, actor.y - 30, rewards[i].glint, age, reducedMotion);
      drawFloat(ctx, actor.x, actor.y - 62 - (i % 4) * 11, rewards[i].text, reducedMotion ? 0 : age,
        {color: rewards[i].color, duration: 1600, size: rewards[i].glint ? 11 : 9});
    }
    ctx.setTransform(dpr,0,0,dpr,0,0);
    // The colour of the day: rose dawn warming into daylight, golden afternoon, red sunset, violet dusk.
    if (!state.expedition?.anchor_space && !prologue) drawDayGrade(ctx, width, height, dayGrade(state.expedition?.clock));
    // Night: darkness with holes of light around the avatar, the anchor camp and a campfire.
    const dark = nightAlpha(state.expedition?.clock);
    if (dark > 0) {
      const toScreen = (wx, wy) => ({x: width / 2 + (wx - view.x) * view.scale, y: height / 2 + (wy - view.y) * view.scale});
      const tileLight = (place, r, warm) => place && {...toScreen((place.x + .5) * TILE_W, (place.y + .5) * TILE_H), r: r * view.scale, warm};
      const me = toScreen(actor.x, actor.y);
      const possessed = state.expedition?.possession?.active;
      drawNight(ctx, width, height, dark, [
        {...me, r: (possessed ? 120 : 84) * view.scale, warm: false},
        tileLight(state.expedition.anchor, 150, true),
        tileLight(state.expedition.campfire, 110, true),
      ].filter(Boolean), {clock: now, reducedMotion});
    }
    // Off-screen guides: the anchor camp (always) and this life's campfire, at the screen edge.
    if (!prologue && state.expedition) {
      const inset = isMobile() ? {top: 120, right: 24, bottom: 230, left: 24} : {top: 170, right: 260, bottom: 140, left: 340};
      const guides = [[state.expedition.anchor, 'Camp', '#f1d38a'], [state.expedition.campfire, 'Fire', '#ff9a4a']];
      for (const [place, name, color] of guides) {
        if (!place) continue;
        const sx = width / 2 + ((place.x + .5) * TILE_W - view.x) * view.scale;
        const sy = height / 2 + ((place.y + .5) * TILE_H - view.y) * view.scale;
        const at = edgePoint(sx, sy, width, height, inset);
        const steps = Math.abs(place.x - state.player.x) + Math.abs(place.y - state.player.y);
        if (at) drawEdgeMarker(ctx, at, `${name} · ${steps} steps`, color);
      }
    }
    drawEyelids(ctx, prologueView(prologue), width, height, reducedMotion);
    drawVignette(ctx, width, height);
    drawPossessionTint(ctx, width, height, possessionGlow(state.expedition?.possession,
      possessedSince === null ? Infinity : now - possessedSince));
    $('zoom').textContent=Math.round(view.scale*100)+'%';
    $('zoom-out').disabled=zoom<=ZOOM.min; $('zoom-in').disabled=zoom>=ZOOM.max;
    if(mapDirty && state) { drawMinimap(map, state, chunks, dpr); mapDirty = false; }
  }
  if(state) sound.update({now, paused, work: state.expedition?.activity?.kind ?? null, ...soundScene,
    outdoors: !state.expedition?.anchor_space && !state.expedition?.prologue});
  if(!stopped) requestAnimationFrame(render);
}
const directions={KeyW:'north',ArrowUp:'north',KeyD:'east',ArrowRight:'east',KeyS:'south',ArrowDown:'south',KeyA:'west',ArrowLeft:'west'};
addEventListener('keydown', event=>{
  if (!$('report').hidden) return;
  if(event.ctrlKey || event.metaKey || event.altKey) return;
  if(event.target instanceof HTMLButtonElement && (event.code==='Space' || event.code==='Enter')) return;
  if(directions[event.code]) { event.preventDefault(); if(!paused && manualAllowed()) controls.press(event.code,directions[event.code]); }
  else if(event.code==='Space') { event.preventDefault(); if(!paused && manualAllowed()) controls.attack(true); }
  else if(event.code==='KeyE' && !event.repeat) { event.preventDefault(); if(!paused && manualAllowed()) pendingInteract = true; }
  else if(event.code==='KeyP' && !event.repeat) { event.preventDefault(); setPause(!paused); }
  else if(event.code==='KeyQ' && !event.repeat) { event.preventDefault(); togglePossession(); }
  else if(event.code==='Backquote' && !event.repeat) { event.preventDefault(); toggleDebug(); }
  else if(event.code==='KeyM' && !event.repeat) {
    event.preventDefault();
    setSound({...sound.settings, volume: sound.settings.volume ? 0 : lastVolume});
    toast(sound.settings.volume ? `Sound ${sound.label.toLowerCase()}` : 'Sound off');
  }
  else if(event.code==='Escape' && page !== 'world') { event.preventDefault(); openPage('world'); }
  else if(/^Digit[1-9]$/.test(event.code) && !event.repeat) {
    const selected = PAGES[Number(event.code.slice(5)) - 1];
    if (selected) { event.preventDefault(); openPage(selected.id); }
  }
  else if((event.code==='Equal' || event.code==='NumpadAdd') && !event.repeat) changeZoom(.1);
  else if((event.code==='Minus' || event.code==='NumpadSubtract') && !event.repeat) changeZoom(-.1);
});
addEventListener('keyup',event=>{
  controls.release(event.code);
  if(event.code==='Space') controls.attack(false);
});
// Locally a hidden tab pauses the shared server. Hosted, the idle world keeps going.
addEventListener('blur',()=>{ if(hosted) controls.reset(); else setPause(true); });
// Browsers only start audio from a gesture; UI buttons click softly.
for (const name of ['pointerdown','keydown']) addEventListener(name,()=>sound.unlock(),{capture:true});
document.addEventListener('click',event=>{
  const button = event.target.closest?.('button');
  if (button && !button.disabled) sound.play(button.dataset.page || button.dataset.subpage ? 'tab' : 'click');
});
document.addEventListener('visibilitychange',()=>sound.suspend(document.hidden));
document.addEventListener('visibilitychange',()=>{ if(document.hidden){ if(hosted) controls.reset(); else setPause(true); } });
addEventListener('pagehide',()=>{
  stopped=true; controls.reset();
  releaseInput(controls.payload(true,[]));   // the server's input lease still covers abrupt closes
});
canvas.addEventListener('pointerdown',()=>canvas.focus());
$('pause').addEventListener('click',()=>setPause(!paused));
/** Possess the avatar, or hand it back early (the server times possession and its recharge). */
function togglePossession() {
  const ex = state?.expedition;
  if (!ex || pendingAction || paused) return;
  if (controlMode === 'active') { pendingAction = {type: 'release'}; controls.reset(); resetStick(); return; }
  const slot = skillSlots(ex)[1];
  if (slot.state !== 'ready') { toast(`Possess: ${slot.note || 'not available'}`); return; }
  pendingAction = {type: 'possess'}; controls.reset(); pendingInteract = false;
}
$('context-toggle').addEventListener('click', () => {
  if (contextOpen) { closeContext(); return; }
  if (!state?.expedition?.location_context) return;
  contextOpen = true;
  contextPaused = !paused;
  if (contextPaused) setPause(true);
  document.body.classList.add('context-open');
  renderLocationContext(state.expedition.location_context, true);
});
$('context-close').addEventListener('click', closeContext);
$('context-actions').addEventListener('click', event => {
  const action = locationAction(event.target);
  if (!action || pendingAction) return;
  pendingAction = action;
  closeContext();
});
function setBag(open) {
  bagOpen = open;
  document.body.classList.toggle('bag-open', bagOpen);
  $('bag-toggle').setAttribute('aria-expanded', String(bagOpen));
}
$('bag-toggle').addEventListener('click',()=>setBag(!bagOpen));
$('bag-close').addEventListener('click',()=>setBag(false));
$('touch-interact').addEventListener('click',()=>{ if (!paused && manualAllowed()) pendingInteract = true; });
// Some mobile browsers still zoom on a double tap over HUD text; touch-action covers the rest.
document.addEventListener('dblclick',event=>event.preventDefault());
$('report-close').addEventListener('click',()=>{hud.hideReport();setPause(false);canvas.focus();});
// One anchor action per request: later clicks wait until the server has answered.
for (const id of ['anchor-begin', 'anchor-shop', 'anchor-offerings']) $(id).addEventListener('click', event => {
  const action = anchorAction(event.target);
  if (action && !pendingAction) pendingAction = action;
});
$('skill-bar').addEventListener('click', event => {
  const slot = event.target.closest('button[data-skill-slot]');
  if (!slot || pendingAction) return;
  if (slot.dataset.skillSlot === '1') { togglePossession(); return; }
  if (slot.dataset.state !== 'ready') { toast(`${slot.querySelector('span').textContent}: ${slot.dataset.note || 'not available'}`); return; }
  if (slot.dataset.skillSlot === '0') pendingAction = {type: 'contact'};
});
$('resume').addEventListener('click',()=>{setPause(false);canvas.focus();});
$('zoom-in').addEventListener('click',()=>changeZoom(.1));
$('zoom-out').addEventListener('click',()=>changeZoom(-.1));
const stick = $('move-stick');
stick.addEventListener('pointerdown',event=>{
  event.preventDefault();
  if (paused || !manualAllowed() || stickPointer !== null) return;
  stickPointer = event.pointerId;
  stick.setPointerCapture(event.pointerId);
  moveStick(event);
});
stick.addEventListener('pointermove',event=>{
  if (event.pointerId === stickPointer) { event.preventDefault(); moveStick(event); }
});
for (const name of ['pointerup','pointercancel','lostpointercapture']) stick.addEventListener(name,event=>{
  if (event.pointerId === stickPointer) resetStick();
});
function toggleDebug() { debugOn = !debugOn; $('debug-panel').hidden = !debugOn; }
function applyCollapsed() {
  for (const id of PANELS) {
    const panel = document.querySelector(`[data-panel="${id}"]`);
    if (!panel) continue;
    panel.classList.toggle('collapsed', collapsed[id]);
    document.body.classList.toggle('fold-' + id, collapsed[id]);
    const button = panel.querySelector('button.fold');
    button.textContent = collapsed[id] ? '▸' : '▾';
    button.setAttribute('aria-expanded', String(!collapsed[id]));
    button.setAttribute('aria-label', `${collapsed[id] ? 'Expand' : 'Collapse'} ${id} panel`);
  }
  mapDirty = true;
}
document.addEventListener('click', event => {
  const id = event.target.closest('[data-fold]')?.dataset.fold;
  if (!id) return;
  collapsed = toggleCollapsed(collapsed, id);
  writeUi(COLLAPSE_KEY, JSON.stringify(collapsed));
  applyCollapsed();
});
function openPage(id) {
  page = id; pageSignature = ''; armed = null; lastDetailAt = 0;
  for (const button of $('tabs').querySelectorAll('button')) button.setAttribute('aria-pressed', String(button.dataset.page === page));
  document.body.classList.toggle('page-open', page !== 'world');
  $('page').hidden = page === 'world';
  if (page !== 'world') { $('page-body').scrollTop = 0; renderPage(); }
  else canvas.focus();
}
function renderPage(force = false) {
  if (page === 'world') return;
  const model = pageModel(page, {world_seed: state?.world_seed, expedition: {detail: lastDetail}},
    window.DIMSUM_HOST || null, subpage[page], {sound: {label: sound.label, ambience: sound.settings.ambience}});
  const signature = JSON.stringify([model, armed]);
  if (!force && signature === pageSignature) return;
  pageSignature = signature;
  $('page-title').textContent = model.title;
  renderSubtabs($('page-subtabs'), model.subtabs || [], model.sub);
  const body = $('page-body'), scroll = body.scrollTop, key = model.sub ? `${page}/${model.sub}` : page;
  body.replaceChildren(...(model.loading ? [el('p', 'page-loading', 'Reading the expedition...')]
    : model.sections.map(section => renderSection(section, {page: key, closed: closedSections, armed}))));
  body.scrollTop = scroll;
}
$('tabs').addEventListener('click', event => {
  const id = event.target.closest('button[data-page]')?.dataset.page;
  if (id) openPage(id === page && id !== 'world' ? 'world' : id);
});
$('page-close').addEventListener('click', () => openPage('world'));
$('page-subtabs').addEventListener('click', event => {
  const id = event.target.closest('button[data-subpage]')?.dataset.subpage;
  if (!id || !subtabsOf(page).some(t => t.id === id) || subpage[page] === id) return;
  subpage[page] = id; armed = null; $('page-body').scrollTop = 0; renderPage(true);
});
$('page-body').addEventListener('click', event => {
  const journal = journalAction(event.target);
  if (journal) { if (!pendingAction) { pendingAction = journal; lastDetailAt = 0; } return; }
  const act = event.target.closest('button[data-act]')?.dataset.act;
  if (!act) return;
  if (act === 'layout') { collapsed = defaultCollapsed(isMobile()); writeUi(COLLAPSE_KEY, JSON.stringify(collapsed)); applyCollapsed(); return; }
  if (act === 'debug') { toggleDebug(); return; }
  if (act === 'sound-volume') { setSound({...sound.settings, volume: (sound.settings.volume + 1) % VOLUMES.length}); return; }
  if (act === 'sound-ambience') { setSound({...sound.settings, ambience: !sound.settings.ambience}); return; }
  const host = window.DIMSUM_HOST;
  if (!host) return;
  clearTimeout(armTimer);
  if (armed !== act) {   // two-step confirmation without browser dialogs
    armed = act; renderPage(true);
    armTimer = setTimeout(() => { armed = null; renderPage(true); }, 5000);
    return;
  }
  armed = null; renderPage(true);
  status(act === 'rebuild' ? 'Building a new world...' : 'Starting over...');
  Promise.resolve(act === 'rebuild' ? host.rebuildWorld() : host.wipe()).catch(error => status(`Could not reset: ${error.message}`));
});
buildTabs(PAGES); openPage('world'); applyCollapsed();
addEventListener('resize',resize);
resize(); requestAnimationFrame(render); poll();

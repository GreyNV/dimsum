/** Browser adapter: snapshots in, character art out. Python owns all game rules. */
import {TILE_W, TILE_H, ZOOM, clamp, residentBounds, cameraView, follow, retainResident, tileAt, visualHash, stickDirection, Controls} from './view.js';
import {PALETTE, OBJECT_PAD, paintChunk, drawTree} from './art.js';
import {drawPlayer, drawEnemy, drawEffect, drawPunchLines, drawUnarmedReach, drawDamage, drawFloat, drawSpot, drawSpotCompletion, drawCamp, drawAmbushSite, drawElder, occludingTreeTiles, hiddenBehind, TORSO_LIFT} from './actors.js';
import {PAGES, needsDetail, pageModel, PANELS, COLLAPSE_KEY, loadCollapsed, toggleCollapsed, defaultCollapsed} from './pages.js';
import {debugText, ExpeditionHud, activityText, newRewards, prologueView, rewardTexts, reportIsFresh, reportStorageKey} from './hud.js';
import {regionCue, skillSlots, worldMode} from './world_ui.js';
import {$, el, readUi, writeUi} from './dom.js';
import {hosted, request, releaseInput} from './transport.js';
import {drawMinimap} from './minimap.js';
import {anchorAction, renderAnchor} from './anchor_ui.js';
import {buildTabs, renderSection} from './page_ui.js';
import {drawEyelids, drawVignette, tintPicture} from './scene_fx.js';

const canvas = $('scene'), ctx = canvas.getContext('2d'), mini = $('minimap'), map = mini.getContext('2d');
const chunks = new Map(), pictures = new Map(), controls = new Controls();
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
/* Design debug overlay: ?debug in the URL or the backquote key. Asks the server for its
 * debug block (seed, region, buckets, windows, pity, screening) on every poll. */
let debugOn = new URLSearchParams(location.search).has('debug');
let state = null, paused = true, zoom = ZOOM.initial, width = 0, height = 0, dpr = 1;
let camera = null, actor = null, lastFrame = 0, connection = 'connecting';
let mapDirty = true, polling = false, stopped = false;
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
const SEEN_REPORT_KEY = 'dimsum.report.seen';
const seenReport = () => readUi(SEEN_REPORT_KEY);
const markReport = (worldSeed, report) => writeUi(SEEN_REPORT_KEY, reportStorageKey(worldSeed, report));
/* Pages (tabs) and collapsible HUD panels. The detail block is requested at most twice a
 * second while a page that needs it is open, so ordinary polling stays small. */
let page = 'world', lastDetail = null, lastDetailAt = 0, pageSignature = '', armed = null, armTimer = 0;
const closedSections = new Set();
const isMobile = () => matchMedia('(max-width: 720px)').matches;
let collapsed = loadCollapsed(readUi(COLLAPSE_KEY), isMobile());
let controlMode = 'auto', bagOpen = false, pendingInteract = false;
/* A mode the player just chose; polls already in flight still carry the old mode, so the
 * server's answer is only adopted once a request with this mode has been answered. */
let requestedMode = null;
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
function resize() {
  width = innerWidth; height = innerHeight; dpr = Math.min(devicePixelRatio || 1, 3);
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
function updateActivity() {
  if (!state) return;
  const tile = tileAt([...chunks.values()], state.player.x, state.player.y);
  const near = state.targets.find(t => t.hp > 0 && Math.abs(t.x - state.player.x) + Math.abs(t.y - state.player.y) <= 2);
  const surface = near ? `Bramble boar nearby - ${near.hp} HP` : tile?.glyph === '%' ? 'Fording the river' : tile?.glyph === 'H' ? 'On an old bridge' : tile?.blocked ? 'Obstructed ground' : tile?.glyph === '=' ? 'On the old forest trail' : 'Among the trees';
  const auto = activityText(state, paused);
  const text = auto ?? (paused ? 'Paused - the forest can wait' : state.player.animation === 'attack' ? 'Fists up' : surface);
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
  observeCombat(next);
  observeExpedition(next);
  if (next.expedition?.anchor_space && !state?.expedition?.anchor_space) {
    if (page !== 'world') openPage('world');
    hud.hideReport();
    setPause(false);
  }
  state = next; mapDirty = true;
  if (requestedMode !== null && sentControl === requestedMode) requestedMode = null;
  if (next.expedition?.anchor_space || next.expedition?.prologue) { controlMode = 'auto'; requestedMode = null; }
  else if (requestedMode === null) controlMode = worldMode(next.expedition);
  const active = controlMode === 'active';
  if (!active) resetStick();
  document.body.classList.toggle('active-control', active);
  document.body.classList.toggle('manual-unlocked', active);
  $('mode-switch').textContent = active ? 'Auto explore' : 'Take control';
  $('mode-switch').setAttribute('aria-pressed', String(active));
  $('attack-state').textContent = next.expedition?.auto_target ? 'TARGET IN REACH' : 'AUTO STRIKE';
  $('mode-switch').disabled = !!next.expedition?.prologue || !!next.expedition?.anchor_space;
  $('region-tip').textContent = regionCue(next.expedition?.region);
  const progress = next.expedition?.activity;
  $('action-name').textContent = progress?.name || (active ? 'Choose your path' : 'Exploring');
  $('action-percent').textContent = progress ? `${Math.floor(progress.progress / 10)}%` : '';
  $('action-fill').style.width = `${progress ? progress.progress / 10 : 0}%`;
  for (const [index, slot] of skillSlots(next.expedition).entries()) {
    const button = document.querySelector(`[data-skill-slot="${index}"]`);
    button.dataset.state = slot.state;
    button.disabled = !slot.usable;
    button.querySelector('span').textContent = slot.name;
    button.setAttribute('aria-label', `Skill ${index + 1}: ${slot.name}, ${slot.state}`);
  }
  if (firstSnapshot && $('report').hidden) setPause(false);
  hud.update(next);
  renderAnchor(next.expedition);
  if (next.expedition?.detail) lastDetail = next.expedition.detail;
  if (page !== 'world') renderPage();
  const position = {x:(next.player.x + .5) * TILE_W, y:(next.player.y + .5) * TILE_H};
  if (!actor || Math.abs(actor.x - position.x) + Math.abs(actor.y - position.y) > TILE_W * 5) {
    actor = {...position}; camera = {...position};
  }
  const here = [...chunks.values()].find(c => c.x === Math.floor(next.player.x / c.width) && c.y === Math.floor(next.player.y / c.height));
  const biome = (here?.biome || 'dark_forest').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  const region = next.expedition?.region?.name || biome;
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
      rewards.push({text: lost > 0 ? `-${lost} health` : 'Gored!', color: '#ff7a63', at: now});
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
      rewardTexts(entry).forEach((r, i) => rewards.push({...r, at: now + i * 180}));
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
function repaintCanopies(tx, ty, resident) {
  for (const tile of occludingTreeTiles(tx, ty)) {
    const chunk = resident.find(c => Math.floor(tile.x / c.width) === c.x && Math.floor(tile.y / c.height) === c.y);
    if (!chunk) continue;
    const lx = tile.x - chunk.x * chunk.width, ly = tile.y - chunk.y * chunk.height;
    if (chunk.tiles[ly][lx] === 'T') drawTree(ctx, tile.x * TILE_W, tile.y * TILE_H, visualHash(tile.x, tile.y, chunk.seed));
  }
}
/** Exactly one request in flight. Server fixed ticks and input lease own timing. */
async function poll() {
  if (polling || stopped) return;
  polling = true;
  const started = performance.now();
  try {
    const body = controls.payload(paused, [...chunks.keys()]);
    body.control = controlMode;
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
    adopt(next, body.control);
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
function render(now) {
  const dt=Math.min(100,now-lastFrame || 16); lastFrame=now;
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.fillStyle=PALETTE.void; ctx.fillRect(0,0,width,height);
  if (state?.expedition?.anchor_space) {
    const scale=Math.min(2.6,width/240,height/340);
    ctx.translate(width/2,height*.38);ctx.scale(scale,scale);
    drawCamp(ctx,-48,-15,{clock:state.expedition.total_ms,reducedMotion});
    drawPlayer(ctx,state.player,59,-11,null,{clock:state.expedition.total_ms});
    if(!stopped)requestAnimationFrame(render);
    return;
  }
  if (state && actor && camera) {
    const tx=(state.player.x+.5)*TILE_W, ty=(state.player.y+.5)*TILE_H;
    actor.x=reducedMotion ? tx : follow(actor.x,tx,dt,55);
    actor.y=reducedMotion ? ty : follow(actor.y,ty,dt,55);
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
    // Paint any visible chunk that is still missing, then at most one off-screen
    // chunk per frame, so a border crossing never paints 3-5 chunks in one frame.
    for(const chunk of visible) if(!pictures.has(chunk.id)) pictures.set(chunk.id, paintChunk(chunk));
    const pending=resident.find(c=>!pictures.has(c.id));
    if(pending) pictures.set(pending.id, paintChunk(pending));
    for(const chunk of visible) ctx.drawImage(pictures.get(chunk.id).ground,chunk.x*chunk.width*TILE_W,chunk.y*chunk.height*TILE_H);
    // Region tint: a flat, low-alpha wash per chunk so regions read at a glance (VISUAL_STYLE.md effects pass).
    // Organic regions (generator v3) send one tint code per tile; the wash is cached per chunk.
    for(const chunk of visible) if(chunk.tint) {
      ctx.globalAlpha=.28;
      const tint = chunk.tint_rows ? tintPicture(chunk, pictures.get(chunk.id)) : null;
      if (tint) ctx.drawImage(tint, chunk.x*chunk.width*TILE_W, chunk.y*chunk.height*TILE_H);
      else {
        ctx.fillStyle=chunk.tint;
        ctx.fillRect(chunk.x*chunk.width*TILE_W,chunk.y*chunk.height*TILE_H,chunk.width*TILE_W,chunk.height*TILE_H);
      }
      ctx.globalAlpha=1;
    }
    for(const chunk of visible) ctx.drawImage(pictures.get(chunk.id).objects,chunk.x*chunk.width*TILE_W-OBJECT_PAD,chunk.y*chunk.height*TILE_H-OBJECT_PAD);
    const anchor = state.expedition?.anchor;
    if (anchor) {
      drawAmbushSite(ctx, (anchor.x+.5)*TILE_W, (anchor.y+.5)*TILE_H);
      drawCamp(ctx, (anchor.x+.5)*TILE_W, (anchor.y+.5)*TILE_H, {clock: state.clock_ms, reducedMotion});
    }
    const goal = state.expedition?.goal;
    for (const spot of state.spots || []) drawSpot(ctx, spot, (spot.x+.5)*TILE_W, (spot.y+.5)*TILE_H,
      {clock: state.clock_ms, goal: !!goal && goal.x === spot.x && goal.y === spot.y});
    for (const [id, f] of fadingSpots) {
      const age = now - f.at;
      if (age >= 650) { fadingSpots.delete(id); continue; }
      drawSpot(ctx, f.spot, (f.spot.x+.5)*TILE_W, (f.spot.y+.5)*TILE_H, {fade: Math.min(1, age / 500)});
      drawSpotCompletion(ctx, f.spot, (f.spot.x+.5)*TILE_W, (f.spot.y+.5)*TILE_H, age, reducedMotion);
    }
    // Actors are depth-sorted by feet row; canopies south of each actor are repainted over it.
    const actors=state.targets.filter(t=>t.hp>0 || (deaths.has(t.id) && now-deaths.get(t.id).at<600))
      .map(t=>({kind:'enemy',row:t.y,tx:t.x,ty:t.y,target:t}));
    actors.push({kind:'player',row:actor.y/TILE_H-.5,tx:state.player.x,ty:state.player.y});
    const prologue = state.expedition?.prologue ?? null;
    if (elder) actors.push({kind:'elder',row:elder.y,tx:elder.x,ty:elder.y,alpha:1,shift:0,
      facing:state.player.x < elder.x ? 'west' : 'east',talking:prologue?.stage === 'listen'});
    else if (elderLeaving) {
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
      if(item.kind==='player') drawPlayer(ctx,state.player,actor.x,actor.y,attackPhase(state.player),
        {activity, clock:state.clock_ms, reducedMotion});
      else if(item.kind==='elder') drawElder(ctx,(item.tx+.5)*TILE_W+item.shift,(item.ty+.5)*TILE_H,
        {clock:state.clock_ms,facing:item.facing,alpha:item.alpha,talking:item.talking,reducedMotion});
      else {
        const t=item.target, hit=hits.get(t.id), death=deaths.get(t.id);
        const at=enemyXY(t,now,dt);
        drawEnemy(ctx,t,at.x,at.y,{clock:state.clock_ms,reducedMotion,
          hit:hit?now-hit.at:Infinity,dying:t.hp===0&&death?Math.min(1,(now-death.at)/600):null});
      }
      repaintCanopies(item.tx,item.ty,resident);
    }
    for(const t of state.targets) if(hiddenBehind(t,state.player)) {
      const hit=hits.get(t.id);
      const at=enemyXY(t,now);
      drawEnemy(ctx,t,at.x,at.y,{clock:state.clock_ms,reducedMotion,ghost:true,hit:hit?now-hit.at:Infinity});
    }
    if (state.expedition?.control === 'manual' && !prologue) {
      const target = state.targets.find(t=>t.id===state.expedition.auto_target && t.hp>0);
      drawUnarmedReach(ctx,actor.x,actor.y,target ? [(target.x+.5)*TILE_W,(target.y+.5)*TILE_H] : null,
        state.player.animation === 'attack');
    }
    // Combat marks draw above canopies so a swing is never hidden by leaves.
    if(swing.slashAt!==null) {
      const age=now-swing.slashAt;
      if(!reducedMotion) drawPunchLines(ctx,actor.x,actor.y,swing.facing,age);
      if(age<220) for(const e of swing.effects) drawEffect(ctx,(e.x+.5)*TILE_W,(e.y+.5)*TILE_H-TORSO_LIFT,age);
    }
    for(const t of state.targets) {
      const hit=hits.get(t.id);
      if(hit && now-hit.at<600) { const at=enemyXY(t,now); drawDamage(ctx,at.x,at.y-44,hit.amount,reducedMotion?0:now-hit.at); }
    }
    for (let i = rewards.length - 1; i >= 0; i--) {
      const age = now - rewards[i].at;
      if (age > 1600) { rewards.splice(i, 1); continue; }
      if (age < 0) continue;
      drawFloat(ctx, actor.x, actor.y - 62 - (i % 4) * 11, rewards[i].text, reducedMotion ? 0 : age,
        {color: rewards[i].color, duration: 1600, size: 9});
    }
    ctx.setTransform(dpr,0,0,dpr,0,0);
    drawEyelids(ctx, prologueView(prologue), width, height, reducedMotion);
    drawVignette(ctx, width, height);
    $('zoom').textContent=Math.round(view.scale*100)+'%';
    $('zoom-out').disabled=zoom<=ZOOM.min; $('zoom-in').disabled=zoom>=ZOOM.max;
    if(mapDirty && state) { drawMinimap(map, state, chunks, dpr); mapDirty = false; }
  }
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
  else if(event.code==='Backquote' && !event.repeat) { event.preventDefault(); toggleDebug(); }
  else if(event.code==='Escape' && page !== 'world') { event.preventDefault(); openPage('world'); }
  else if(/^Digit[1-7]$/.test(event.code) && !event.repeat) { event.preventDefault(); openPage(PAGES[Number(event.code.slice(5)) - 1].id); }
  else if((event.code==='Equal' || event.code==='NumpadAdd') && !event.repeat) changeZoom(.1);
  else if((event.code==='Minus' || event.code==='NumpadSubtract') && !event.repeat) changeZoom(-.1);
});
addEventListener('keyup',event=>{
  controls.release(event.code);
  if(event.code==='Space') controls.attack(false);
});
// Locally a hidden tab pauses the shared server. Hosted, the idle world keeps going.
addEventListener('blur',()=>{ if(hosted) controls.reset(); else setPause(true); });
document.addEventListener('visibilitychange',()=>{ if(document.hidden){ if(hosted) controls.reset(); else setPause(true); } });
addEventListener('pagehide',()=>{
  stopped=true; controls.reset();
  releaseInput(controls.payload(true,[]));   // the server's input lease still covers abrupt closes
});
canvas.addEventListener('pointerdown',()=>canvas.focus());
$('pause').addEventListener('click',()=>setPause(!paused));
$('mode-switch').addEventListener('click',()=>{
  if ($('mode-switch').disabled) return;
  controlMode = controlMode === 'auto' ? 'active' : 'auto';
  requestedMode = controlMode;
  controls.reset(); resetStick(); pendingInteract = false;
  document.body.classList.toggle('active-control', controlMode === 'active');
  document.body.classList.toggle('manual-unlocked', controlMode === 'active');
  $('mode-switch').textContent = controlMode === 'active' ? 'Auto explore' : 'Take control';
  $('mode-switch').setAttribute('aria-pressed', String(controlMode === 'active'));
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
for (const id of ['anchor-begin', 'anchor-shop']) $(id).addEventListener('click', event => {
  const action = anchorAction(event.target, state?.expedition);
  if (action && !pendingAction) pendingAction = action;
});
$('skill-bar').addEventListener('click', event => {
  const slot = event.target.closest('button[data-skill-slot]');
  if (slot?.dataset.skillSlot === '0' && slot.dataset.state === 'ready' && !pendingAction)
    pendingAction = {type: 'return'};
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
  const model = pageModel(page, {world_seed: state?.world_seed, expedition: {detail: lastDetail}}, window.DIMSUM_HOST || null);
  const signature = JSON.stringify([model, armed]);
  if (!force && signature === pageSignature) return;
  pageSignature = signature;
  $('page-title').textContent = model.title;
  const body = $('page-body'), scroll = body.scrollTop;
  body.replaceChildren(...(model.loading ? [el('p', 'page-loading', 'Reading the expedition...')]
    : model.sections.map(section => renderSection(section, {page, closed: closedSections, armed}))));
  body.scrollTop = scroll;
}
$('tabs').addEventListener('click', event => {
  const id = event.target.closest('button[data-page]')?.dataset.page;
  if (id) openPage(id === page && id !== 'world' ? 'world' : id);
});
$('page-close').addEventListener('click', () => openPage('world'));
$('page-body').addEventListener('click', event => {
  const act = event.target.closest('button[data-act]')?.dataset.act;
  if (!act) return;
  if (act === 'layout') { collapsed = defaultCollapsed(isMobile()); writeUi(COLLAPSE_KEY, JSON.stringify(collapsed)); applyCollapsed(); return; }
  if (act === 'debug') { toggleDebug(); return; }
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

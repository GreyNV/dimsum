/** Browser adapter: snapshots in, character art out. Python owns all game rules. */
import {TILE_W, TILE_H, ZOOM, clamp, residentBounds, cameraView, follow, retainResident, tileAt, visualHash, Controls} from './view.js';
import {PALETTE, OBJECT_PAD, paintChunk, drawTree, terrainColor} from './art.js';
import {drawPlayer, drawEnemy, drawEffect, drawPunchLines, drawDamage, drawFloat, drawSpot, drawSpotCompletion, drawCamp, occludingTreeTiles, hiddenBehind, TORSO_LIFT} from './actors.js';
import {ExpeditionHud, activityText, newRewards, rewardTexts, reportIsFresh, reportStorageKey} from './hud.js';

const $ = id => document.getElementById(id);
const canvas = $('scene'), ctx = canvas.getContext('2d'), mini = $('minimap'), map = mini.getContext('2d');
const chunks = new Map(), pictures = new Map(), controls = new Controls();
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
let state = null, paused = true, zoom = ZOOM.initial, width = 0, height = 0, dpr = 1;
let camera = null, actor = null, lastFrame = 0, connection = 'connecting';
let mapDirty = true, polling = false, stopped = false;
/* Cosmetic combat feedback derived from consecutive snapshots. Client clocks only
 * fade these marks; damage, timing and hits always come from the server. */
const hpSeen = new Map(), hits = new Map(), deaths = new Map();
let swing = {serial: 0, active: false, slashAt: null, lastMs: -1, effects: []};
/* Expedition presentation: reward popups and fading completed spots (cosmetic). */
const hud = new ExpeditionHud(), rewards = [], fadingSpots = new Map();
let lastRewardSeq = null, spotsSeen = new Map(), reportSeen = null, reportTimer = 0;
const SEEN_REPORT_KEY = 'dimsum.report.seen';
const seenReport = () => { try { return localStorage.getItem(SEEN_REPORT_KEY); } catch { return null; } };
const markReport = (worldSeed, report) => { try { localStorage.setItem(SEEN_REPORT_KEY, reportStorageKey(worldSeed, report)); } catch { /* optional */ } };
const manualAllowed = () => !state?.expedition || state.expedition.skills.includes('take_control');

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
  const surface = near ? `Bramble boar nearby - ${near.hp} HP` : tile?.blocked ? 'Obstructed ground' : tile?.glyph === '=' ? 'On the old forest trail' : 'Among the trees';
  const auto = activityText(state, paused);
  const text = auto ?? (paused ? 'Paused - the forest can wait' : state.player.animation === 'attack' ? 'Fists up' : surface);
  if ($('activity').textContent !== text) $('activity').textContent = text;
}
function changeZoom(delta) {
  zoom = clamp(Math.round((zoom + delta) * 10) / 10, ZOOM.min, ZOOM.max);
}
function adopt(next) {
  const firstSnapshot = state === null;
  for (const chunk of next.chunks) {
    chunks.set(chunk.id, chunk);
    pictures.delete(chunk.id);   // painted lazily: visible now, others one per frame
  }
  retainResident(chunks, next.resident); retainResident(pictures, next.resident);
  observeCombat(next);
  observeExpedition(next);
  state = next; mapDirty = true;
  if (firstSnapshot && $('report').hidden) setPause(false);
  hud.update(next);
  const position = {x:(next.player.x + .5) * TILE_W, y:(next.player.y + .5) * TILE_H};
  if (!actor || Math.abs(actor.x - position.x) + Math.abs(actor.y - position.y) > TILE_W * 5) {
    actor = {...position}; camera = {...position};
  }
  const here = [...chunks.values()].find(c => c.x === Math.floor(next.player.x / c.width) && c.y === Math.floor(next.player.y / c.height));
  const biome = (here?.biome || 'dark_forest').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  if ($('biome').textContent !== biome) $('biome').textContent = biome;
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
  if (lastRewardSeq !== null && next.expedition.life === state?.expedition?.life)
    for (const entry of newRewards(next, lastRewardSeq))
      rewardTexts(entry).forEach((r, i) => rewards.push({...r, at: now + i * 180}));
  lastRewardSeq = Math.max(lastRewardSeq ?? 0, seq);
  const report = next.expedition.report;
  if (report && report.seq !== reportSeen) {
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
  if (state?.expedition && next.expedition.life !== state.expedition.life) {
    actor = null; hits.clear(); deaths.clear(); hpSeen.clear(); rewards.length = 0; fadingSpots.clear();
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
/* Hosted build (web/): the simulation runs in a worker and host.js installs this
 * transport. Locally, the Python server answers the same requests over HTTP. */
const transport = window.DIMSUM_TRANSPORT || null;
const hosted = !!transport?.hosted;
async function request(path, body) {
  if (transport) return transport.request(path, body);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(path, {method:body ? 'POST' : 'GET', cache:'no-store',
      headers:body ? {'Content-Type':'application/json'} : {}, body:body ? JSON.stringify(body) : undefined,
      signal:controller.signal});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return await response.json();
  } finally { clearTimeout(timeout); }
}
/** Exactly one request in flight. Server fixed ticks and input lease own timing. */
async function poll() {
  if (polling || stopped) return;
  polling = true;
  const started = performance.now();
  try {
    const body = controls.payload(paused, [...chunks.keys()]);
    const attackRevision = controls.attackRevision;
    const next = await request('/api/input', body);
    controls.acknowledge(body, attackRevision); adopt(next);
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
function drawMap() {
  if (!state) return;
  map.setTransform(dpr,0,0,dpr,0,0);
  map.fillStyle = '#0b110b'; map.fillRect(0,0,180,130);
  const entries = state.minimap;
  if (!entries.length) return;
  const minX = Math.min(...entries.map(p=>p.x)), maxX = Math.max(...entries.map(p=>p.x));
  const minY = Math.min(...entries.map(p=>p.y)), maxY = Math.max(...entries.map(p=>p.y));
  const spanX = (maxX-minX+1) * state.chunk_width, spanY = (maxY-minY+1) * state.chunk_height;
  const scale = Math.min(174/spanX,124/spanY), left=(180-spanX*scale)/2, top=(130-spanY*scale)/2;
  const coords = new Map([...chunks.values()].map(c=>[c.x+':'+c.y,c]));
  for (const entry of entries) {
    const x=left+(entry.x-minX)*state.chunk_width*scale, y=top+(entry.y-minY)*state.chunk_height*scale;
    const w=state.chunk_width*scale, h=state.chunk_height*scale;
    map.fillStyle = entry.status === 'unknown' ? '#10180f' : entry.status === 'visited' ? '#405031' : '#26331e';
    map.fillRect(x,y,w,h);
    const chunk=coords.get(entry.x+':'+entry.y);
    if (chunk && entry.status !== 'unknown') {
      map.globalAlpha = entry.status === 'visited' ? .95 : .42;
      for (let ry=0;ry<chunk.height;ry++) for(let rx=0;rx<chunk.width;rx++) {
        map.fillStyle=terrainColor(chunk.tiles[ry][rx]);
        map.fillRect(x+rx*scale,y+ry*scale,Math.max(.7,scale),Math.max(.7,scale));
      }
      map.globalAlpha=1;
    } else if (entry.status === 'unknown') {
      map.fillStyle='#26301f';
      for(let py=y+3;py<y+h;py+=5) for(let px=x+3;px<x+w;px+=5) map.fillRect(px,py,.7,.7);
    }
  }
  const px=left+(state.player.x-minX*state.chunk_width+.5)*scale;
  const py=top+(state.player.y-minY*state.chunk_height+.5)*scale;
  const mark=(gx,gy,color,r)=>{
    const mx=left+(gx-minX*state.chunk_width+.5)*scale, my=top+(gy-minY*state.chunk_height+.5)*scale;
    map.fillStyle='#070a06'; map.fillRect(mx-r-.6,my-r-.6,r*2+1.2,r*2+1.2);
    map.fillStyle=color; map.fillRect(mx-r,my-r,r*2,r*2);
  };
  for(const spot of state.spots||[]) mark(spot.x,spot.y,'#e2c066',1.1);
  for(const t of state.targets) if(t.hp>0) mark(t.x,t.y,'#e0604f',1.1);
  map.fillStyle='#fff1bc'; map.fillRect(px-1.8,py-1.8,3.6,3.6);
  map.strokeStyle='#ffe6a0'; map.lineWidth=.7; map.strokeRect(px-3.5,py-3.5,7,7);
  mapDirty=false;
}
function render(now) {
  const dt=Math.min(100,now-lastFrame || 16); lastFrame=now;
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.fillStyle=PALETTE.void; ctx.fillRect(0,0,width,height);
  if (state && actor && camera) {
    const tx=(state.player.x+.5)*TILE_W, ty=(state.player.y+.5)*TILE_H;
    actor.x=reducedMotion ? tx : follow(actor.x,tx,dt,55);
    actor.y=reducedMotion ? ty : follow(actor.y,ty,dt,55);
    camera.x=reducedMotion ? actor.x : follow(camera.x,actor.x,dt,140);
    camera.y=reducedMotion ? actor.y : follow(camera.y,actor.y,dt,140);
    const resident=[...chunks.values()].sort((a,b)=>a.y-b.y || a.x-b.x);
    const view=cameraView(camera,width,height,zoom,residentBounds(resident));
    ctx.translate(width/2,height/2); ctx.scale(view.scale,view.scale); ctx.translate(-view.x,-view.y);
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
    for(const chunk of visible) ctx.drawImage(pictures.get(chunk.id).objects,chunk.x*chunk.width*TILE_W-OBJECT_PAD,chunk.y*chunk.height*TILE_H-OBJECT_PAD);
    const anchor = state.expedition?.anchor;
    if (anchor) drawCamp(ctx, (anchor.x+.5)*TILE_W, (anchor.y+.5)*TILE_H, {clock: state.clock_ms, reducedMotion});
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
    actors.sort((a,b)=>a.row-b.row || (a.kind==='player')-(b.kind==='player'));
    for(const item of actors) {
      if(item.kind==='player') drawPlayer(ctx,state.player,actor.x,actor.y,attackPhase(state.player),
        {activity:state.expedition?.activity ?? null, clock:state.clock_ms});
      else {
        const t=item.target, hit=hits.get(t.id), death=deaths.get(t.id);
        drawEnemy(ctx,t,(t.x+.5)*TILE_W,(t.y+.5)*TILE_H,{clock:state.clock_ms,reducedMotion,
          hit:hit?now-hit.at:Infinity,dying:t.hp===0&&death?Math.min(1,(now-death.at)/600):null});
      }
      repaintCanopies(item.tx,item.ty,resident);
    }
    for(const t of state.targets) if(hiddenBehind(t,state.player)) {
      const hit=hits.get(t.id);
      drawEnemy(ctx,t,(t.x+.5)*TILE_W,(t.y+.5)*TILE_H,{clock:state.clock_ms,reducedMotion,ghost:true,hit:hit?now-hit.at:Infinity});
    }
    // Combat marks draw above canopies so a swing is never hidden by leaves.
    if(swing.slashAt!==null) {
      const age=now-swing.slashAt;
      if(!reducedMotion) drawPunchLines(ctx,actor.x,actor.y,swing.facing,age);
      if(age<220) for(const e of swing.effects) drawEffect(ctx,(e.x+.5)*TILE_W,(e.y+.5)*TILE_H-TORSO_LIFT,age);
    }
    for(const t of state.targets) {
      const hit=hits.get(t.id);
      if(hit && now-hit.at<600) drawDamage(ctx,(t.x+.5)*TILE_W,(t.y+.5)*TILE_H-44,hit.amount,reducedMotion?0:now-hit.at);
    }
    for (let i = rewards.length - 1; i >= 0; i--) {
      const age = now - rewards[i].at;
      if (age > 1600) { rewards.splice(i, 1); continue; }
      if (age < 0) continue;
      drawFloat(ctx, actor.x, actor.y - 62 - (i % 4) * 11, rewards[i].text, reducedMotion ? 0 : age,
        {color: rewards[i].color, duration: 1600, size: 9});
    }
    ctx.setTransform(dpr,0,0,dpr,0,0);
    const shade=ctx.createRadialGradient(width/2,height/2,Math.min(width,height)*.27,width/2,height/2,Math.max(width,height)*.7);
    shade.addColorStop(0,'#00000000'); shade.addColorStop(1,'#070c0755');
    ctx.fillStyle=shade; ctx.fillRect(0,0,width,height);
    $('zoom').textContent=Math.round(view.scale*100)+'%';
    $('zoom-out').disabled=zoom<=ZOOM.min; $('zoom-in').disabled=zoom>=ZOOM.max;
    if(mapDirty) drawMap();
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
  else if(event.code==='KeyP' && !event.repeat) { event.preventDefault(); setPause(!paused); }
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
  if (hosted) return;  // host.js saves; there is no server lease to release
  // Best-effort release; server input lease still protects abrupt tab closure.
  fetch('/api/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(controls.payload(true,[])),keepalive:true}).catch(()=>{});
});
canvas.addEventListener('pointerdown',()=>canvas.focus());
$('pause').addEventListener('click',()=>setPause(!paused));
// Some mobile browsers still zoom on a double tap over HUD text; touch-action covers the rest.
document.addEventListener('dblclick',event=>event.preventDefault());
$('report-close').addEventListener('click',()=>{hud.hideReport();setPause(false);canvas.focus();});
$('resume').addEventListener('click',()=>{setPause(false);canvas.focus();});
$('zoom-in').addEventListener('click',()=>changeZoom(.1));
$('zoom-out').addEventListener('click',()=>changeZoom(-.1));
for(const button of document.querySelectorAll('[data-move],#touch-attack')) {
  const key='touch:'+button.id+button.dataset.move;
  button.addEventListener('pointerdown',event=>{
    event.preventDefault(); if(paused || !manualAllowed())return;
    button.setPointerCapture(event.pointerId);
    if(button.dataset.move)controls.press(key,button.dataset.move);else controls.attack(true);
  });
  for(const name of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(name,()=>{
    controls.release(key);if(!button.dataset.move)controls.attack(false);
  });
}
addEventListener('resize',resize);
resize(); requestAnimationFrame(render); poll();

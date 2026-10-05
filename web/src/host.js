/** Hosted-mode host: boots the Pyodide worker, provides the transport the shared
 * browser client (app.js) uses instead of HTTP, and keeps local + cloud saves.
 *
 * Saves: localStorage every 10s (instant resume), Supabase every 60s and when the
 * tab is hidden. Identity is a random id + secret kept in this browser; the
 * "save code" (id.secret) moves a save to another device. No account needed.
 */
import {SUPABASE_URL, SUPABASE_KEY, LOCAL_SAVE_MS, CLOUD_SAVE_MS} from './config.js';

const LOCAL_KEY = 'dimsum.save.v1', IDENTITY_KEY = 'dimsum.identity.v1';
const store = {
  get(key) { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } },
  remove(key) { try { localStorage.removeItem(key); } catch { /* storage unavailable */ } },
};

// ---------- boot screen ----------
const boot = document.createElement('div');
boot.id = 'boot';
boot.innerHTML = '<p class="eyebrow">Dimensional Summoner</p><h2>Waking the anchor</h2>'
  + '<div class="boot-bar"><i></i></div><p class="boot-stage">Starting...</p><p class="boot-detail"></p>';
document.body.append(boot);
function bootProgress({stage, fraction, detail}) {
  boot.querySelector('.boot-stage').textContent = stage;
  boot.querySelector('.boot-detail').textContent = detail || '';
  if (fraction != null) boot.querySelector('.boot-bar i').style.width = `${Math.round(fraction * 100)}%`;
}

// ---------- worker RPC ----------
const worker = new Worker('/worker.js', {type: 'module'});
let nextId = 1;
const pending = new Map();
worker.onmessage = ({data}) => {
  if (data.type === 'progress') return bootProgress(data);
  if (data.type === 'fatal') return showFatal(data.error);
  const entry = pending.get(data.id);
  if (!entry) return;
  pending.delete(data.id);
  data.ok ? entry.resolve(data.result) : entry.reject(new Error(data.error));
};
worker.onerror = event => showFatal(event.message || 'worker failed to start');
function call(type, payload = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, {resolve, reject});
    worker.postMessage({id, type, ...payload});
  });
}
function showFatal(message) {
  boot.hidden = false;
  boot.classList.add('failed');
  bootProgress({stage: 'Something went wrong while loading the world.', fraction: null, detail: String(message).slice(0, 400)});
}

// ---------- identity + saves ----------
function randomHex(bytes) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
}
function identity() {
  let id = store.get(IDENTITY_KEY);
  if (!id || !id.id || !id.secret) {
    id = {id: crypto.randomUUID(), secret: randomHex(24)};
    store.set(IDENTITY_KEY, id);
  }
  return id;
}
async function rpc(name, args) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', apikey: SUPABASE_KEY},
    body: JSON.stringify(args),
  });
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.json();
}
const cloud = {
  status: 'not synced yet',
  async load() {
    const {id, secret} = identity();
    return rpc('dimsum_load_game', {p_id: id, p_secret: secret});
  },
  async save(text, savedAt) {
    const {id, secret} = identity();
    await rpc('dimsum_save_game', {p_id: id, p_secret: secret, p_data: JSON.parse(text), p_saved_at: new Date(savedAt).toISOString()});
    this.status = `saved ${new Date(savedAt).toLocaleTimeString()}`;
  },
};

let latest = null;  // {saved_at, data}
let resetting = false;  // set while wiping/rebuilding so no stale save is written back
async function saveLocal() {
  if (resetting) return latest;
  const data = await call('save');
  latest = {saved_at: Date.now(), data};
  store.set(LOCAL_KEY, latest);
  return latest;
}
async function saveCloud() {
  try {
    const snapshot = latest || await saveLocal();
    await cloud.save(snapshot.data, snapshot.saved_at);
  } catch (error) {
    cloud.status = `offline (${error.message})`;
  }
  renderCloudStatus();
}

// ---------- save-code UI (inside the pause overlay) ----------
function renderCloudStatus() {
  const el = document.getElementById('cloud-status');
  if (el) el.textContent = `Cloud save: ${cloud.status}`;
}
function installSavePanel() {
  const overlay = document.getElementById('pause-overlay');
  const panel = document.createElement('section');
  panel.className = 'save-panel';
  panel.innerHTML = '<p id="cloud-status">Cloud save: not synced yet</p>'
    + '<div class="save-row"><button id="copy-code" type="button">Copy save code</button></div>'
    + '<label class="save-row"><input id="code-input" placeholder="Paste a save code" autocomplete="off" spellcheck="false">'
    + '<button id="use-code" type="button">Load</button></label><p id="code-note" class="code-note"></p>';
  overlay.append(panel);
  const note = text => { document.getElementById('code-note').textContent = text; };
  document.getElementById('copy-code').addEventListener('click', async () => {
    const {id, secret} = identity();
    const code = `${id}.${secret}`;
    try { await navigator.clipboard.writeText(code); note('Save code copied. Keep it private: it unlocks this save.'); }
    catch { note(code); }
  });
  document.getElementById('use-code').addEventListener('click', async () => {
    const [id, secret] = document.getElementById('code-input').value.trim().split('.');
    if (!/^[0-9a-f-]{36}$/i.test(id || '') || !/^[0-9a-f]{32,128}$/i.test(secret || '')) return note('That does not look like a save code.');
    note('Checking the cloud...');
    try {
      const found = await rpc('dimsum_load_game', {p_id: id, p_secret: secret});
      if (!found) return note('No cloud save matches that code.');
      store.set(IDENTITY_KEY, {id, secret});
      store.set(LOCAL_KEY, {saved_at: Date.parse(found.saved_at), data: JSON.stringify(found.data)});
      location.reload();
    } catch (error) { note(`Cloud unavailable: ${error.message}`); }
  });
  renderCloudStatus();
}

function toast(text) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = text;
  document.body.append(el);
  setTimeout(() => el.remove(), 9000);
}

// ---------- start ----------
async function start() {
  identity();
  let local = store.get(LOCAL_KEY);
  try {
    const remote = await cloud.load();
    const remoteAt = remote && Date.parse(remote.saved_at);
    if (remote && (!local || remoteAt > local.saved_at)) local = {saved_at: remoteAt, data: JSON.stringify(remote.data)};
    cloud.status = remote ? 'connected' : 'connected (new save)';
  } catch (error) {
    cloud.status = `offline (${error.message})`;
  }
  const seed = crypto.getRandomValues(new Uint32Array(1))[0];
  const awayMs = local ? Math.max(0, Date.now() - local.saved_at) : 0;
  const result = await call('init', {save: local ? local.data : null, seed, awayMs});
  worker.postMessage({id: 0, type: 'visibility', active: !document.hidden});
  // Settings page actions (app.js renders the buttons; the host owns saves and identity).
  window.DIMSUM_HOST = {
    worldSeed: result.worldSeed,
    build: result.manifest && result.manifest.built,
    cloudStatus: () => cloud.status,
    async rebuildWorld() {
      const seed = crypto.getRandomValues(new Uint32Array(1))[0];
      await call('rebuild', {seed});
      await saveLocal();
      await saveCloud();
      resetting = true;
      location.reload();
    },
    wipe() {
      // A fresh identity means the old cloud save can never be restored over the new game.
      resetting = true;
      store.remove(LOCAL_KEY);
      store.remove(IDENTITY_KEY);
      store.remove('dimsum.report.seen');
      location.reload();
    },
  };
  window.DIMSUM_TRANSPORT = {
    hosted: true,
    async request(path, body) {
      return JSON.parse(await call('input', {body: body || {move: null, attack: false, paused: false, known: []}}));
    },
  };
  await import('./app.js');
  installSavePanel();
  boot.hidden = true;
  if (result.caughtUpMs >= 60000) {
    const b = result.before, a = result.after;
    const lives = a.life - b.life;
    toast(`While you were away: ${Math.round(result.caughtUpMs / 60000)} min explored`
      + (lives ? `, ${lives} life${lives > 1 ? 'ves' : ''} ended` : '')
      + `, best ring ${a.best_depth}.`);
  }
  await saveLocal();
  setInterval(() => saveLocal().catch(() => {}), LOCAL_SAVE_MS);
  setInterval(saveCloud, CLOUD_SAVE_MS);
  saveCloud();
  document.addEventListener('visibilitychange', () => {
    worker.postMessage({id: 0, type: 'visibility', active: !document.hidden});
    if (document.visibilityState === 'hidden') saveLocal().then(saveCloud).catch(() => {});
  });
  addEventListener('pagehide', () => { if (latest && !resetting) store.set(LOCAL_KEY, latest); });
}
start().catch(error => showFatal(error && error.stack || error));

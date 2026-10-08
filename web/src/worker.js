/* Simulation worker: runs the unchanged Python game (Pyodide) off the render thread.
 *
 * Messages in:  {id, type: 'init', save|null, seed, awayMs}
 *               {id, type: 'input', body}      -> frame JSON text
 *               {id, type: 'save'}             -> save JSON text
 * Messages out: {id, ok, result|error} replies, {type: 'progress', ...} while booting, and
 *               {type: 'catchup', doneMs, totalMs, done} while offline time fast-forwards. Time between messages is real time: the worker
 *               advances the expedition by measured elapsed milliseconds (the Python
 *               auto-pilot is partition-independent, so throttled timers are harmless).
 */
import {loadPyodide} from '/pyodide/pyodide.mjs';

let py = null, game = null, last = 0, loopTimer = 0, active = true;
const MAX_STEP_MS = 60000;

function progress(stage, fraction = null, detail = '') {
  postMessage({type: 'progress', stage, fraction, detail});
}

async function boot() {
  progress('Loading Python runtime', 0.05);
  py = await loadPyodide({indexURL: '/pyodide/'});
  progress('Loading the world', 0.6);
  const manifest = await (await fetch('/py/manifest.json', {cache: 'no-cache'})).json();
  const base = '/home/pyodide/game';
  const texts = await Promise.all(manifest.files.map(async file => {
    const response = await fetch(`/py/${file}?v=${encodeURIComponent(manifest.built)}`);
    if (!response.ok) throw new Error(`missing ${file}`);
    return [file, await response.text()];
  }));
  for (const [file, text] of texts) {
    const path = `${base}/${file}`;
    py.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')));
    py.FS.writeFile(path, text);
  }
  py.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(base)})\nsys.dont_write_bytecode = True`);
  py.runPython('from dimensional_sim.world.web import WebGame');
  return manifest;
}

function now() { return performance.now() / 1000; }

/* Offline time is fast-forwarded in the background after the world is shown: each tick
 * spends at most CATCH_UP_BUDGET_MS of wall time on it, so input stays responsive and the
 * player watches the expedition race through the time they were away. */
const CATCH_UP_BUDGET_MS = 30;
let owed = 0, owedTotal = 0, owedBefore = null, savedText = null, catchUpSeed = 0;

function catchUpTick() {
  if (owed <= 0) return;
  const start = performance.now();
  try {
    while (owed > 0 && performance.now() - start < CATCH_UP_BUDGET_MS) owed -= game.catch_up(Math.min(owed, 1000));
  } catch (error) {
    // Offline catch-up must never brick a save: resume exactly where it was saved instead.
    const WebGame = py.globals.get('WebGame');
    game = WebGame(savedText, catchUpSeed, false);
    owed = 0;
    postMessage({type: 'catchup', done: true, failed: String(error).slice(0, 300), totalMs: owedTotal});
    return;
  }
  if (owed > 0) postMessage({type: 'catchup', done: false, doneMs: owedTotal - owed, totalMs: owedTotal});
  else postMessage({type: 'catchup', done: true, totalMs: owedTotal, before: owedBefore, after: JSON.parse(game.summary())});
}

function loop() {
  const t = performance.now();
  const ms = Math.min(MAX_STEP_MS, Math.max(0, Math.round(t - last)));
  last = t;
  if (game && ms) {
    try { game.advance(ms, t / 1000, active); } catch (error) { postMessage({type: 'fatal', error: String(error)}); return; }
  }
  if (game && owed > 0) catchUpTick();
  loopTimer = setTimeout(loop, owed > 0 ? 0 : 50);
}

async function init({save, seed, awayMs}) {
  const manifest = await boot();
  const WebGame = py.globals.get('WebGame');
  try {
    game = save ? WebGame(save, seed, true) : WebGame(null, seed, true);
  } catch (error) {
    // A save from an incompatible build must not brick the game: start fresh, report it.
    postMessage({type: 'progress', stage: 'Save could not be loaded; starting a new life', fraction: 0.7, detail: String(error).slice(0, 300)});
    game = WebGame(null, seed, true);
    save = null;
  }
  owed = save ? WebGame.offline_ms(awayMs | 0) : 0;
  owedTotal = owed;
  owedBefore = JSON.parse(game.summary());
  savedText = save;
  catchUpSeed = seed;
  last = performance.now();
  clearTimeout(loopTimer);
  loop();
  return {manifest, owedMs: owedTotal, worldSeed: game.world_seed()};
}

const handlers = {
  init,
  visibility: ({active: visible}) => { active = visible === true; },
  input: ({body}) => game.input(JSON.stringify(body), now()),
  save: () => game.save(),
  // New world, same soul: keeps dimensional XP, currencies, unlocks, mastery and journal.
  rebuild: ({seed}) => { owed = 0; return game.rebuild(seed >>> 0); },   // unsigned: `| 0` made half of all seeds negative
};

onmessage = async ({data}) => {
  try {
    const result = await handlers[data.type](data);
    postMessage({id: data.id, ok: true, result});
  } catch (error) {
    // Name the step and keep Python's traceback tail: Safari's JS stacks carry no message.
    const text = String(error && error.message || error);
    postMessage({id: data.id, ok: false, error: `${data.type}: ${text.length > 1500 ? '...' + text.slice(-1500) : text}`});
  }
};

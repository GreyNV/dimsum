/* Simulation worker: runs the unchanged Python game (Pyodide) off the render thread.
 *
 * Messages in:  {id, type: 'init', save|null, seed, awayMs}
 *               {id, type: 'input', body}      -> frame JSON text
 *               {id, type: 'save'}             -> save JSON text
 * Messages out: {id, ok, result|error} replies, plus {type: 'progress', ...} while
 *               booting/catching up. Time between messages is real time: the worker
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

function loop() {
  const t = performance.now();
  const ms = Math.min(MAX_STEP_MS, Math.max(0, Math.round(t - last)));
  last = t;
  if (game && ms) {
    try { game.advance(ms, t / 1000, active); } catch (error) { postMessage({type: 'fatal', error: String(error)}); return; }
  }
  loopTimer = setTimeout(loop, 50);
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
  let owed = save ? WebGame.offline_ms(awayMs | 0) : 0;
  const total = owed;
  const before = JSON.parse(game.summary());
  while (owed > 0) {
    owed -= game.catch_up(owed);
    progress('Catching up while you were away', 0.7 + 0.3 * (1 - owed / total), `${Math.round((total - owed) / 60000)} of ${Math.round(total / 60000)} min`);
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  const after = JSON.parse(game.summary());
  last = performance.now();
  clearTimeout(loopTimer);
  loop();
  return {manifest, caughtUpMs: total, before, after, worldSeed: game.world_seed()};
}

const handlers = {
  init,
  visibility: ({active: visible}) => { active = visible === true; },
  input: ({body}) => game.input(JSON.stringify(body), now()),
  save: () => game.save(),
  // New world, same soul: keeps dimensional XP, currencies, unlocks, mastery and journal.
  rebuild: ({seed}) => game.rebuild(seed | 0),
};

onmessage = async ({data}) => {
  try {
    const result = await handlers[data.type](data);
    postMessage({id: data.id, ok: true, result});
  } catch (error) {
    postMessage({id: data.id, ok: false, error: String(error && error.message || error).slice(0, 2000)});
  }
};

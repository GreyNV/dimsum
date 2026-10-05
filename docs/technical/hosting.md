# Hosted build (Vercel + Supabase)

The browser build runs the unchanged Python simulation in a Web Worker through
Pyodide (CPython compiled to WebAssembly). Vercel serves static files only;
Supabase stores cloud saves. Python remains the single source of truth.

## Layout
- vercel.json: install `npm install --prefix web`, build `node web/build.mjs`,
  output `web/dist`, security headers (CSP allows only self + the Supabase project).
- web/build.mjs: copies the shared client (src/dimensional_sim/world/browser/*),
  injects web/src/host.js, copies Pyodide from node_modules to /pyodide/, and copies
  the Python package to /py/ with a manifest.
- web/src/worker.js: boots Pyodide, writes the package into its file system,
  imports dimensional_sim.world.web.WebGame, advances by real elapsed time.
  The pinned Pyodide 314.0.7 runs in a module Worker: host.js creates it with
  `{type: 'module'}` and worker.js imports `/pyodide/pyodide.mjs`.
- web/src/host.js: boot screen, worker RPC, transport for app.js, saves.
- src/dimensional_sim/world/session.py: frame snapshot, input validation and
  session logic shared with the local HTTP server (browser_server.py).
- src/dimensional_sim/world/web.py: JSON-text bridge (new/load, input, advance,
  save, offline catch-up).

## Saves
- localStorage every 10s and when the tab hides; resume on reload.
- Supabase project "dimsum" (eu-west-1): table public.dimsum_saves with RLS on and
  no policies (no direct access). RPC public.dimsum_save_game / dimsum_load_game
  (SECURITY DEFINER, search_path ''), keyed by a random id + secret (sha256 stored),
  1 MB cap, an older save never overwrites a newer one. The Supabase advisor warns
  that anon can execute these SECURITY DEFINER functions: that is intentional.
- Identity lives in the browser; Pause -> "Copy save code" moves a save to
  another device ("Paste a save code" -> Load).
- Offline progress: real time away x 0.65 (idle offline efficiency), capped at
  30 simulated minutes per return, then a "While you were away" note.

## Resetting (Settings tab)
- "New world, keep progress": the worker calls `WebGame.rebuild(seed)` (`Expedition.rebuilt`): a new random
  world seed, the next life starts there without the prologue; dimensional XP, dust, ash, blessing, unlocks,
  mastery, journal and the chosen boon carry over. Saved locally and to the cloud, then the page reloads.
- "Start over": removes the local save, the identity and the report flag, so the old cloud save is never
  restored; a brand-new game starts. Both are two-step buttons (no browser dialogs).
- `vercel.json` serves HTML/JS/CSS with `max-age=0, must-revalidate` (Pyodide stays immutable), so a new
  deploy is picked up on the next reload; the save, not the cache, is what kept the old world.

## Run the hosted build locally
```powershell
npm install --prefix web
node web/build.mjs
python -m http.server 8000 --directory web/dist
```
Open http://localhost:8000/ (module workers need http, not file://).

## Browser verification (2026-10-04)
After switching the pinned Pyodide runtime to a module Worker, the built `web/dist`
was served locally and opened in Chromium with agent-browser. The Python runtime
booted, the opening report appeared, Continue resumed exploration, attribute XP
changed, a life report appeared, and the browser reported no page errors. The
production Vercel deployment still serves the previous classic worker until the
new build is published.
The hosted Worker now starts the session paused until the browser's first
snapshot; the UI resumes automatically when no new report needs reading.
In the rebuilt hosted browser check, local save time remained at 0 while the
opening report stayed visible for more than 8 seconds. After Continue, the
report closed, the pause button returned to its running state, and the saved
expedition reached 7,728 ms with no page errors.

## Deploy
Push to GitHub main: the Vercel project "dimsum" builds from GreyNV/dimsum.
Vercel Authentication is on for the project by default; turn it off (Project ->
Settings -> Deployment Protection) or add a custom domain before sharing with
outside testers.

## Known limits
First visit downloads about 14 MB (Pyodide, cached afterwards); boot is about
3s on a desktop. Hidden tabs keep simulating at a throttled timer rate. Cloud
saves are best effort; the local save is authoritative on the device.

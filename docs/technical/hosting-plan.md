# Hosting plan: browser game on Vercel + Supabase (2026-10-04)

Goal: testers open a link (phone or desktop), play their own world, and keep their
progress. Today the game needs a local Python server ticking every 20ms, which
Vercel (short-lived functions) cannot host.

## Decision
Run the simulation in the player's browser; Vercel serves static files; Supabase
stores accounts and saves. Python stays the reference and balance lab.

| Option | Verdict |
|---|---|
| Browser simulation + Vercel + Supabase | Chosen: each tester has their own world; near-zero running cost; works offline; no server lag |
| Python server on Railway/Render | Fast to ship, but one shared world unless sessions are added; runs and bills 24/7 |
| Vercel UI + Python API | Two deployments plus per-player sessions; network latency on every tick |

## Architecture
- web/ (Vite, plain ES modules, no framework): reuses browser/art.js, actors.js,
  hud.js, view.js, index.html and style.css almost unchanged; they already
  consume the frame JSON.
- web/src/sim/: JS port of seeds (SHA-256 derive_seed; synchronous implementation,
  because WebCrypto is async), models validation, open_terrain v1, generation and
  repository streaming, animation, runtime, encounters, progression, autopilot.
- Simulation runs in a Web Worker at fixed 20ms ticks; the UI exchanges frames
  and input over postMessage instead of HTTP polling. This removes the 50ms poll
  delay and keeps border-crossing generation off the render thread.
- Parity: Python writes golden fixtures (canonical chunk JSON for 60 coordinates
  including negatives; expedition saves after 1, 6 and 30 simulated minutes with a
  death). JS tests must match them byte for byte. CI (GitHub Actions) runs the
  Python unittest suite and the node parity and renderer tests on every push.
- Offline progress: on return, the worker fast-forwards real elapsed time at the
  idle simulator's offline efficiency (0.65), capped at 8h, then shows a "while
  you were away" report.
- Saves: IndexedDB every 10s (instant resume, works offline), and Supabase every
  60s and on pagehide. Table saves(user_id uuid pk -> auth.users, schema int,
  data jsonb, sim_ms bigint, updated_at timestamptz); RLS: a user reads and writes
  only their own row. Conflict rule: higher sim_ms wins, with a prompt if both changed.
- Auth: Supabase anonymous sign-in on first visit, so testers just play; an
  optional email link keeps the same save across devices.
- Vercel: project on GitHub GreyNV/dimsum, root directory web/, build `vite build`,
  env VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (public; RLS protects data).
  Preview deployments per branch/PR; production on main. PWA manifest so phones
  can install it to the home screen.
- Performance on phones: stamp-cached terrain (done), lazy chunk painting (done),
  DPR capped at 2 on small screens, optional OffscreenCanvas painting in a worker.

## Phases
W0 Access: GitHub push access for GreyNV/dimsum in this session; Vercel and
   Supabase connectors (or a Supabase project URL + anon key). Reconcile the repo
   with the local folder.
W1 Port foundations + parity: seeds, models, open terrain, generation,
   repository; golden chunk fixtures.
W2 Port runtime, animation, encounters, progression, autopilot; golden
   expedition fixtures across a death and save/reload.
W3 Worker transport, renderer reuse, IndexedDB saves, offline progress, report.
W4 Supabase: anonymous auth, saves table + RLS, sync and conflict handling.
W5 Vercel deploy, PWA, phone QA (iOS Safari, Android Chrome), CI.
W6 Docs: run/deploy/test guide; the Python server remains for local balance work.

Estimated port: about 2.5-3k lines of JS plus tests. Risks: exact SHA-256/JSON
parity (mitigated by fixtures), floating-point speed formula (already rounded
once to per-mille integers), and mobile Safari canvas limits (smaller zoom floor).

## Border lag (fixed in the local build, 2026-10-04)
Cause: each chunk crossing streamed 3-5 chunks, and the browser repainted each
with about 12k fillText calls (~27ms per chunk on a fast desktop) in one frame,
while the server rolled encounter spots (~10ms per chunk) inside the 20ms tick.
Fix: terrain stamp cache (16 tile, 8 tree, 4 rock variants copied with
drawImage: 13ms per chunk), lazy painting (visible chunks immediately, one
off-screen chunk per frame), and encounter candidates computed once per chunk
(0.7ms). Measured over 40s with 3 crossings: worst frame 117ms -> 50ms; frames
over 50ms 3 -> 0.

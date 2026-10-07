/** How the client talks to the simulation.
 *
 * Hosted build (web/): the simulation runs in a worker and host.js installs
 * window.DIMSUM_TRANSPORT before this module loads. Locally, the Python server
 * answers the same requests over HTTP.
 */
const transport = window.DIMSUM_TRANSPORT || null;
export const hosted = !!transport?.hosted;

/** GET (no body) or POST JSON to `path`; local requests time out after 2.5 s. */
export async function request(path, body) {
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

/** Best-effort release of held input when the tab closes (local server only). */
export function releaseInput(payload) {
  if (hosted) return;   // host.js saves; there is no server lease to release
  fetch('/api/input', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload), keepalive:true}).catch(() => {});
}

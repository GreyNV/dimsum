"""Loopback-only browser adapter; authoritative fixed ticks, pure cached snapshots.

No provider imports. A single local session is intentionally shared by all tabs.
The adapter owns wall-clock/input leases; Exploration owns gameplay time. Requests
never supply elapsed time. Static assets are allowlisted packaged resources.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os
import threading
import time

from .assets import parse_json
from .models import integer
# Re-exported: the session logic lives in session.py so the hosted build can reuse it.
from .session import (INPUT_LEASE, LOG_ENTRIES, MANUAL_HOLD, TICK_MS,  # noqa: F401
                      BrowserSession as _BaseSession, chunk_id, snapshot, validate_input)
STATIC = {"/": ("index.html", "text/html"),
          "/style.css": ("style.css", "text/css"),
          "/app.js": ("app.js", "text/javascript"),
          "/art.js": ("art.js", "text/javascript"),
          "/actors.js": ("actors.js", "text/javascript"),
          "/hud.js": ("hud.js", "text/javascript"),
          "/world_ui.js": ("world_ui.js", "text/javascript"),
          "/pages.js": ("pages.js", "text/javascript"),
          "/view.js": ("view.js", "text/javascript")}



class BrowserSession(_BaseSession):
    """HTTP adapter session: the request threads and the tick thread share a lock."""
    def __init__(self, game, expedition=None, *, start_paused=False):
        super().__init__(game, expedition, start_paused=start_paused)
        self.lock = threading.RLock()


def make_server(session, port=8765):
    integer(port, "port", 0, 65535)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _local(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            return host in allowed and (origin is None or origin == f"http://{host}")

        def _send(self, code, data, content_type="application/json"):
            raw = json.dumps(data, separators=(",", ":")).encode() if content_type == "application/json" else data
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self._local():
                return self._send(403, {"error": "local same-origin requests only"})
            if self.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if self.path == "/api/state":
                return self._send(200, session.state())
            entry = STATIC.get(self.path.split("?", 1)[0])   # e.g. /?debug opens the overlay
            if entry is None:
                return self._send(404, {"error": "not found"})
            name, content_type = entry
            try:
                raw = files("dimensional_sim.world").joinpath("browser", name).read_bytes()
            except OSError:
                return self._send(503, {"error": "browser resources unavailable"})
            self._send(200, raw, content_type)

        def do_POST(self):
            if not self._local():
                return self._send(403, {"error": "local same-origin requests only"})
            if self.path != "/api/input":
                return self._send(404, {"error": "not found"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self._send(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 16384:
                    return self._send(413, {"error": "input size must be 1..16384 bytes"})
                self.connection.settimeout(2)
                data = parse_json(self.rfile.read(length), 16384)
                result = session.input(data, time.monotonic())
            except (ValueError, OSError) as exc:
                return self._send(400, {"error": str(exc)})
            self._send(200, result)

    class Server(ThreadingHTTPServer):
        # Windows SO_REUSEADDR lets a second server share a busy port, leaving a
        # stale process (with an older static allowlist) answering the browser.
        allow_reuse_address = os.name != "nt"

    return Server(("127.0.0.1", port), Handler)


def serve(game, port=8765, expedition=None):
    # The first browser snapshot decides whether to show an opening report.
    # Keep the simulation at its saved time until that snapshot is received.
    session = BrowserSession(game, expedition, start_paused=True)
    server = make_server(session, port)
    stop = threading.Event()

    def tick():
        deadline = time.monotonic()
        while not stop.is_set():
            deadline += TICK_MS / 1000
            session.step(time.monotonic())
            now = time.monotonic()
            # Bound catch-up after OS suspend; no hours of stale held input.
            if now - deadline > 0.1:
                deadline = now
            stop.wait(max(0, deadline - now))

    worker = threading.Thread(target=tick, name="world-simulation", daemon=True)
    worker.start()
    print(f"World browser: http://127.0.0.1:{server.server_port}/", flush=True)
    print("Auto explores by default; Take control switches to active movement. Ctrl+C stops the server.", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        worker.join()
        server.server_close()

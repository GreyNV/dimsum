"""Pyodide bridge for the hosted web build (web/): the same simulation, in the browser.

The browser worker (web/src/worker.js) imports this module and exchanges JSON text,
so no Python objects cross into JavaScript. Every player gets their own world. Time
comes from the caller (performance.now seconds); offline progress follows the idle
simulator's offline efficiency and is capped so a returning tab catches up quickly.
"""
import json

from ..core import GameConfig
from .autopilot import Expedition
from .models import DimensionSpec
from .open_terrain import open_assets
from .repository import WorldRepository
from .runtime import Exploration
from .seeds import canonical_json
from .session import BrowserSession

CHUNK_SIZE = (32, 16)
OFFLINE_EFFICIENCY_PERMILLE = int(round(GameConfig().offline_efficiency * 1000))
OFFLINE_CAP_MS = 30 * 60 * 1000          # at most 30 simulated minutes per return
CATCH_UP_SLICE_MS = 5_000


def new_world(seed):
    width, height = CHUNK_SIZE
    spec = DimensionSpec("forest", ("dark_forest",), width, height, 25)
    return WorldRepository(seed, (spec,), open_assets(width, height), 9)


class WebGame:
    def __init__(self, save_text=None, seed=482910, start_paused=False):
        if save_text:
            expedition = Expedition.from_dict(json.loads(save_text))
        else:
            expedition = Expedition(Exploration(new_world(int(seed)), "forest"))
        self.expedition = expedition
        self.session = BrowserSession(expedition.game, expedition, start_paused=start_paused)

    @staticmethod
    def offline_ms(real_ms):
        """Simulated milliseconds owed for real time away (efficiency, cap)."""
        return min(OFFLINE_CAP_MS, max(0, int(real_ms)) * OFFLINE_EFFICIENCY_PERMILLE // 1000)

    def catch_up(self, ms):
        """Advance one slice of offline time; returns milliseconds actually advanced."""
        step = min(int(ms), CATCH_UP_SLICE_MS)
        if step > 0:
            self.expedition.advance(step)
        return step

    def input(self, body_text, now):
        frame = self.session.input(json.loads(body_text), float(now))
        return json.dumps(frame, separators=(",", ":"))

    def advance(self, ms, now):
        self.session.advance_ms(int(ms), float(now))

    def state(self, now):
        return json.dumps(self.session.state(float(now)), separators=(",", ":"))

    def save(self):
        return canonical_json(self.expedition.to_dict())

    def summary(self):
        e = self.expedition
        return json.dumps({"life": e.life, "total_ms": e.total_ms, "depth": e.depth,
                           "best_depth": e.best_depth, "xp": sum(e.regular.values()),
                           "dimensional": sum(e.dimensional.values())})

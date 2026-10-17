"""Day and night: the world clock, nightfall, and the wolves that come to whoever walks
beyond the firelight.

The clock is simulation time (total_ms + DAY_START_MS), so it runs through lives and the
anchor alike and replays exactly. At night, every NIGHT_SPAWN_EVERY_MS of world time the
avatar may draw a wolf: only while it is out exploring (never at the anchor camp, never in
a campfire's light, never during the prologue, at the anchor or while the anchor is
contacted), never more than NIGHT_FOES_BY_RING allows. A wolf is a fight lead (catalog
`night_wolf`) that expires at dawn, so leads already give it saving, drawing, pursuit and
rewards. Steps are capped at clock ticks (night_step_cap), so any slicing of time gives the
same wolves. TESTS: tests/test_world_night.py.
"""
from ..catalog import BY_ID
from ..encounters import night_spot
from ..models import chunk_ident
from ..seeds import derive_seed
from ..tuning import (DAY_MS, DAY_START_MS, FIRE_LIGHT_RADIUS, NIGHT_FOES_BY_RING, NIGHT_MS, NIGHT_SPAWN_EVERY_MS,
                      NIGHT_SPAWN_FAR, NIGHT_SPAWN_NEAR, NIGHT_SPAWN_PERCENT, TWILIGHT_MS)

NIGHT_ACTION = next(a.id for a in BY_ID.values() if "night" in a.tags and a.category == "fight")
NIGHT_START_MS = DAY_MS - NIGHT_MS


def world_clock(total_ms):
    return total_ms + DAY_START_MS


def time_of_day(total_ms):
    """Milliseconds into the current day (0 = dawn)."""
    return world_clock(total_ms) % DAY_MS


def is_night(total_ms):
    return time_of_day(total_ms) >= NIGHT_START_MS


def darkness_permille(total_ms):
    """How dark it is, 0 (full day) .. 1000 (deep night), with a TWILIGHT_MS fade at dusk
    (the last minute of daylight going into night) and dawn (the first minute of the day)."""
    t = time_of_day(total_ms)
    if t >= NIGHT_START_MS:
        return 1000
    if t >= NIGHT_START_MS - TWILIGHT_MS:
        return (t - (NIGHT_START_MS - TWILIGHT_MS)) * 1000 // TWILIGHT_MS
    if t < TWILIGHT_MS:
        return (TWILIGHT_MS - t) * 1000 // TWILIGHT_MS
    return 0


def night_cap(ring):
    return max(n for start, n in NIGHT_FOES_BY_RING if ring >= start)


class NightMixin:
    def is_night(self):
        return is_night(self.total_ms)

    def clock_view(self):
        """The world clock for the HUD and the client's lighting."""
        t = time_of_day(self.total_ms)
        night = t >= NIGHT_START_MS
        return {"day": world_clock(self.total_ms) // DAY_MS + 1, "time_ms": t, "day_ms": DAY_MS,
                "night_at_ms": NIGHT_START_MS, "night": night,
                "phase": "night" if night else "dusk" if t >= NIGHT_START_MS - TWILIGHT_MS
                else "dawn" if t < TWILIGHT_MS else "day",
                "darkness": darkness_permille(self.total_ms),
                "until_ms": (DAY_MS - t) if night else (NIGHT_START_MS - t)}

    def _near_fire(self, gx, gy):
        """Within the light of this life's campfire."""
        fire = self.campfire
        return (fire is not None and fire["dimension"] == self.dimension
                and abs(gx - fire["fire_x"]) + abs(gy - fire["fire_y"]) <= FIRE_LIGHT_RADIUS)

    def in_firelight(self, gx, gy):
        """The anchor camp or a campfire: where night creatures never come."""
        return self._near_camp(gx, gy) or self._near_fire(gx, gy)

    def night_step_cap(self):
        """Milliseconds to the next clock tick: steps end there so night rolls replay exactly."""
        return NIGHT_SPAWN_EVERY_MS - world_clock(self.total_ms) % NIGHT_SPAWN_EVERY_MS

    def night_foes(self):
        """Live night creatures (leads) around now."""
        return [lead for lead in self.leads if "night" in BY_ID[lead["action"]].tags
                and lead["expires_ms"] > self.total_ms and lead["id"] not in self.completed]

    def _night_watch(self):
        """Zero-time check, once per clock tick: nightfall, and maybe a wolf."""
        tick = world_clock(self.total_ms) // NIGHT_SPAWN_EVERY_MS
        if tick <= self.night_tick:
            return
        self.night_tick = tick
        if not self.is_night() or self.anchor_ms is not None or self.in_prologue or self.contact:
            return
        if time_of_day(self.total_ms) // NIGHT_SPAWN_EVERY_MS == NIGHT_START_MS // NIGHT_SPAWN_EVERY_MS:
            self._entry("night", "Night falls. Wolves hunt beyond the firelight - the camp and a campfire are safe.")
        px, py = self._player()
        if self.in_firelight(px, py) or len(self.night_foes()) >= night_cap(self.ring(self.game.player.chunk)):
            return
        if derive_seed(self.game.world.world_seed, "night-spawn", self.life, tick) % 100 >= NIGHT_SPAWN_PERCENT:
            return
        key = self.game.player.chunk
        chunk = self.game.world.peek(key)
        if chunk is None:
            return
        spot = night_spot(chunk, NIGHT_ACTION, self.life, tick, (self.game.player.x, self.game.player.y),
                          NIGHT_SPAWN_NEAR, NIGHT_SPAWN_FAR)
        if spot is None or spot.id in self.completed or any(row["id"] == spot.id for row in self.leads):
            return
        sx, sy = self._global(key, spot.x, spot.y)
        if self.in_firelight(sx, sy):
            return
        lead = {"id": spot.id, "action": NIGHT_ACTION, "source": "night",
                "dimension": key.dimension, "chunk_x": key.x, "chunk_y": key.y,
                "chunk": chunk_ident(key), "x": spot.x, "y": spot.y,
                "expires_ms": self.total_ms + (DAY_MS - time_of_day(self.total_ms))}
        self.leads.append(lead)
        self._record_leads([lead], "created")
        self.admitted[spot.id] = NIGHT_ACTION
        self._entry("night", f"A {BY_ID[NIGHT_ACTION].name.lower()} howls close by.", encounter=NIGHT_ACTION)

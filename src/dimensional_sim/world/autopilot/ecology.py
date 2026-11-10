"""Local ecological exhaustion: harvesting thins out a stretch of forest for this life.

Every finished wild spot with an `ecology` (catalog.ECOLOGY: wood, berries, game, fungi,
eggs) adds one to that ecology's pressure in its region cell (REGION_CELL x REGION_CELL
chunks). New chunks rolled in that cell weigh that ecology's spots down by
PRESSURE_STEP[ecology] percent per harvest, never below PRESSURE_FLOOR percent: a worked area
keeps a trickle, and moving on finds fresh ground. Left untouched, a cell recovers: it forgets one
harvest of an ecology every PRESSURE_RECOVER_MS since that ecology was last taken there
(`pressure_at`). Pressure resets with each life
(persistent progress is knowledge, mastery and unlocks, never stockpiled ground).
Spots already rolled keep their plan, so the effect shows as you explore onward.
"""
from ..catalog import ECOLOGY, REGION_CELL
from ..tuning import PRESSURE_FLOOR, PRESSURE_RECOVER_MS, PRESSURE_STEP, SHIMMER_RARITY_PERCENT


def cell_of(key):
    return f"{key.dimension}:{key.x // REGION_CELL}:{key.y // REGION_CELL}"


def percent(harvests, ecology="wood"):
    """Spawn weight left (percent) after `harvests` of `ecology` in one cell."""
    return max(PRESSURE_FLOOR, 100 - PRESSURE_STEP[ecology] * harvests)


class EcologyMixin:
    def _deplete(self, action, key):
        if action.ecology is None or action.placement != "spot":
            return
        name = f"{cell_of(key)}:{action.ecology}"
        self.pressure[name] = self.harvests(name) + 1
        self.pressure_at[name] = self.total_ms

    def harvests(self, name):
        """Harvests of one cell's ecology that still show, after recovering untouched."""
        count = self.pressure.get(name, 0)
        if not count:
            return 0
        return max(0, count - (self.total_ms - self.pressure_at.get(name, self.total_ms)) // PRESSURE_RECOVER_MS)

    def pressure_percents(self, key):
        """{ecology: weight percent} for spots rolled in chunk `key` now (worked ecologies only)."""
        prefix = cell_of(key) + ":"
        return {name[len(prefix):]: percent(n, name[len(prefix):]) for name in self.pressure
                if name.startswith(prefix) and (n := self.harvests(name))}

    def renew(self, ecology, key):
        """Lift this life's exhaustion of `ecology` in the region cell of chunk `key`."""
        self.pressure.pop(f"{cell_of(key)}:{ecology}", None)
        self.pressure_at.pop(f"{cell_of(key)}:{ecology}", None)

    def rarity_percent(self, key):
        """Spot tier odds percent in chunk `key`: raised in a shimmering region cell."""
        shimmer = SHIMMER_RARITY_PERCENT if cell_of(key) in self.shimmer else 100
        return shimmer * self.location_rarity_percent(key) // 100

    def worked_here(self):
        """Ecologies thinned out around the avatar, most worked first (presentation)."""
        rows = self.pressure_percents(self.game.player.chunk)
        return [eco for eco, pct in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])) if pct < 100]


def valid_shimmer(data, dimension):
    """Saved shimmering region cells ["dimension:cx:cy", ...]."""
    if type(data) is not list:
        raise ValueError("invalid shimmer")
    result = set()
    for name in data:
        parts = name.split(":") if type(name) is str else ()
        if len(parts) != 3 or parts[0] != dimension or any(not p.lstrip("-").isdigit() for p in parts[1:]):
            raise ValueError("invalid shimmer")
        result.add(name)
    return result


def valid_pressure(data, dimension):
    """Saved pressure map {"dimension:cx:cy:ecology": harvests}."""
    if type(data) is not dict:
        raise ValueError("invalid ecological pressure")
    result = {}
    for name, count in data.items():
        parts = name.split(":") if type(name) is str else ()
        if len(parts) != 4 or parts[0] != dimension or parts[3] not in ECOLOGY or type(count) is not int \
                or count < 1 or any(not p.lstrip("-").isdigit() for p in parts[1:3]):
            raise ValueError("invalid ecological pressure")
        result[name] = count
    return result


def valid_pressure_at(data, pressure, total_ms):
    """Saved {pressure key: last harvest ms}, one per pressure row."""
    if type(data) is not dict or set(data) != set(pressure) \
            or any(type(v) is not int or not 0 <= v <= total_ms for v in data.values()):
        raise ValueError("invalid ecological recovery")
    return dict(data)

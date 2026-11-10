"""Worked ground around a camp (docs/design/WORKED_GROUND.md).

A camp (a campfire, or a rented bed) binds the avatar to one place and lets it farm that place.
When the camp's area has nothing left to give for CAMP_IDLE_MS, the area's rolled chunks are
rolled again: a new bucket of spots, one round more explored. Each round:

- the chunk counts DANGER_RINGS_PER_ROUND rings deeper (stronger fights, more company, more rare finds);
- fight spots weigh DANGER_FIGHT_PERCENT percent more;
- from DEN_ROUND on, every reroll opens an animal den (one fight for sure);
- worked ecologies stay thinned (ecology.py), so a farmed place gives less of what was taken.

Left untouched, ground recovers: a chunk forgets one round every EXPLORED_RECOVER_MS. At
CAMP_MAX_ROUNDS the autopilot sets out on its own; the player may set out at any time.

State this life:
- `explored`: chunk id -> [rounds, last worked ms] (decays with time; read through explored_rounds);
- `rolled`: chunk id -> [rerolls, danger] of the plan rolled there now (fixed while the plan stands,
  so fight tiers and company never shift under a fight). Chunks never rerolled have no row.
"""
from ..catalog import BY_ID, LOCATIONS
from ..models import ChunkKey, chunk_ident
from ..seeds import derive_seed
from ..tuning import CAMP_MAX_ROUNDS, DEN_ROUND, EXPLORED_NAMES, EXPLORED_RECOVER_MS


def explored_name(rounds):
    return EXPLORED_NAMES[min(rounds, len(EXPLORED_NAMES) - 1)]


class ExploredMixin:
    # ----- reading -------------------------------------------------------------------------
    def explored_rounds(self, key):
        """Rounds of exploration chunk `key` still shows (recovering with time untouched)."""
        row = self.explored.get(chunk_ident(key))
        if row is None:
            return 0
        rounds, at = row
        return max(0, rounds - (self.total_ms - at) // EXPLORED_RECOVER_MS)

    def rolled_danger(self, key):
        """Danger rounds baked into the plan rolled in chunk `key` now (0: an ordinary roll)."""
        row = self.rolled.get(chunk_ident(key))
        return 0 if row is None else row[1]

    def rerolls(self, key):
        row = self.rolled.get(chunk_ident(key))
        return 0 if row is None else row[0]

    def reroll_seed(self, base, key):
        """A chunk's roll seed: unchanged for its first roll, fresh for every reroll."""
        n = self.rerolls(key)
        return base if n == 0 else derive_seed(base, "worked-ground-v1", n)

    def has_den(self, key):
        return self.rolled_danger(key) >= DEN_ROUND

    def ground_view(self, key):
        """{"rounds", "name", "den"} of chunk `key` for the HUD, or None for untouched ground."""
        rounds = self.explored_rounds(key)
        if rounds == 0 and not self.has_den(key):
            return None
        return {"rounds": rounds, "name": explored_name(rounds), "den": self.has_den(key)}

    def camp_rounds(self):
        """The most worked chunk of the camp's area (what the camp shows and decides on)."""
        return max((self.explored_rounds(k) for k in self._camp_area_chunks(set(self.explored))), default=0)

    # ----- the camp's area -----------------------------------------------------------------
    def _camp_area_rolled(self):
        """Chunk keys of the camp's area that have been rolled this life (and not rerolled since)."""
        return self._camp_area_chunks(self.screened_chunks)

    def _camp_area_chunks(self, idents):
        if not self.camping():
            return []
        keys = []
        for ident in sorted(idents):
            dimension, x, y = ident.rsplit(":", 2)
            key = ChunkKey(dimension, int(x), int(y))
            if self.in_camp_area(key):
                keys.append(key)
        return keys

    def _live_target_in(self, key):
        prefix = f"enc:{chunk_ident(key)}:"
        return any(t.id.startswith(prefix) and t.hp > 0 for t in self.game.targets.values())

    def _reroll_camp_area(self):
        """Every rolled chunk of the camp's area with no fight under way is rolled again on entry."""
        done = 0
        for key in self._camp_area_rolled():
            ident = chunk_ident(key)
            if self._live_target_in(key) or any(BY_ID[a].placement == "story" for a in self.forced.get(ident, ())):
                continue   # a fight under way, or the story placed there: those spots must stand
            prefix = f"enc:{ident}:"
            self.screened_chunks.discard(ident)
            self.spot_plans.pop(ident, None)
            self.forced.pop(ident, None)
            self.completed = {c for c in self.completed if not c.startswith(prefix)}
            for table in (self.admitted, self.game.targets, self.hunting, self.fight_paid):
                for name in [n for n in table if n.startswith(prefix)]:
                    table.pop(name)
            rounds = self.explored_rounds(key) + 1
            self.explored[ident] = [rounds, self.total_ms]
            self.rolled[ident] = [self.rerolls(key) + 1, rounds]
            done += 1
        return done

    def _work_camp_area(self):
        """The camp's area is spent: set out when it has grown too dangerous, else roll it again."""
        name = LOCATIONS[self.camp["location"]].name
        if self.camp_rounds() + 1 > CAMP_MAX_ROUNDS:
            self.set_out(f"The ground around the camp at {name} is hunted out and dangerous now. Setting out.")
            return
        if not self._reroll_camp_area():
            return
        self.camp["idle_since"] = None
        rounds = self.camp_rounds()
        den = " Something has made a den nearby." if rounds >= DEN_ROUND else ""
        self._entry("rest", f"{name}, worked over again: {explored_name(rounds).lower()}. "
                            f"New tracks and new finds, and more danger.{den}")

    def set_out(self, text=None):
        """Leave the camp: the campfire or the bed is left behind and the avatar roams free."""
        if not self.camping():
            raise ValueError("no camp to leave")
        name = LOCATIONS[self.camp["location"]].name
        self.camp["left"] = True
        self.campfire = None
        self.goal = None
        self._entry("rest", text or f"Set out from the camp at {name}: the avatar roams free.")

    def den_encounter(self, chunk):
        """The fight an animal den in `chunk` holds (weighted by this chunk's bucket), or None."""
        from ..actions import bucket
        ctx = self.spot_context(chunk.key)
        choices = [(a, w) for a, w in bucket(ctx) if a.category == "fight" and a.placement == "spot"]
        if not choices:
            return None
        roll = derive_seed(self.game.world.world_seed, "den-v1", self.life, chunk_ident(chunk.key),
                           self.rerolls(chunk.key)) % sum(w for _, w in choices)
        for action, w in choices:
            if roll < w:
                return action.id
            roll -= w
        return None


def valid_explored(data, dimension, total_ms, name="explored"):
    """Saved {chunk id: [a, b]} rows of small non-negative integers (explored or rolled)."""
    if type(data) is not dict:
        raise ValueError(f"invalid {name}")
    result = {}
    for ident, row in data.items():
        parts = ident.split(":") if type(ident) is str else ()
        if len(parts) != 3 or parts[0] != dimension or any(not p.lstrip("-").isdigit() for p in parts[1:]) \
                or type(row) is not list or len(row) != 2 or any(type(v) is not int or v < 0 for v in row) \
                or row[0] < 1 or (name == "explored" and row[1] > total_ms):
            raise ValueError(f"invalid {name}")
        result[ident] = list(row)
    return result

"""Spot rolls, spawn windows, pity and action contexts for the current life.

A chunk is rolled once per life when the avatar first enters it (the roll is saved
as a spot plan for exact replay). Spawn windows cap how many of an encounter exist
at once; pity forces a spot of a starved category after a few empty chunks.
"""
from ..actions import Context, bucket
from ..catalog import BY_ID, ITEMS
from ..encounters import EncounterSpot, chunk_spots, forced_spot, roll_window, spot_id
from ..models import ChunkKey, chunk_ident
from ..seeds import derive_seed
from ..tuning import BOUNTY_WINDOW_BONUS, PITY_CHUNKS
from .constants import BOAR_ENCOUNTER, POINT, ROLL_LOG_LIMIT, SCREEN_LOG_LIMIT


class SpawningMixin:
    def _reset_spawns(self):
        """Roll this life's spawn windows; nothing has been screened yet."""
        seed = derive_seed(self.game.world.world_seed, "spawn-window", self.life)
        bonus = BOUNTY_WINDOW_BONUS if self.boon == "bountiful_path" else 0
        self.budget = {entry.id: limit for entry in BY_ID.values()
                       if (limit := roll_window(entry, seed, self.mastery.get(entry.id, 0),
                                                bonus if entry.feeds else 0)) is not None}
        self.spawned = {ident: 0 for ident in self.budget}   # total admitted this life
        self.admitted = {}             # spot / asset-target id -> encounter id, this life
        self.screened_chunks = set()   # chunk ids whose spots were screened
        self.spot_plans = {}           # chunk id -> immutable runtime roll, saved for replay
        self.screened_targets = set()  # asset-spawned target ids screened

    def region(self, key):
        """RegionDef of a chunk key (pure: world seed, biome, coordinates)."""
        cached = self._region_cache.get(key)
        if cached is None:
            cached = self.game.world.region_for(key)
            if len(self._region_cache) > 512:
                self._region_cache.clear()
            self._region_cache[key] = cached
        return cached

    def _progress_fields(self):
        """Persistent permission state shared by every action context."""
        return {"unlocked": frozenset(self.unlocked), "knowledge": frozenset(self.knowledge),
                "recipes": frozenset(self.recipes), "action_counts": self.journal["actions"],
                "item_counts": self.journal["items"]}

    def spot_context(self, key):
        """Context for rolling and explaining world spots in chunk `key`."""
        chunk = self.game.world.peek(key)
        region = self.region(key)
        return Context(biome=chunk.asset.biome if chunk is not None else "dark_forest",
                       region=region.id if region else None, placement="spot", region_def=region,
                       mastery=self.mastery, journal_disabled=frozenset(self.journal_disabled),
                       journal_favor=self.journal_favor, **self._progress_fields())

    def lead_context(self, key):
        """Context for temporary leads around chunk `key`."""
        spot = self.spot_context(key)
        return Context(biome=spot.biome, region=spot.region, region_def=spot.region_def, placement="lead",
                       active_leads=frozenset(lead["action"] for lead in self.leads), **self._progress_fields())

    def self_context(self, trigger=None, visible=True):
        """Context for self actions (crafting, reflection, prayer) right now."""
        return Context(placement="self", mastery=self.mastery, inventory=dict(self.inventory),
                       gear=frozenset(i for i in self.inventory if ITEMS[i].kind == "gear"),
                       hunger=self.hunger // POINT, food_carried=self._has_food(),
                       trigger=trigger, visible=visible,
                       flags=frozenset({"done:pray"} if self.prayers_this_life else ()),
                       **self._progress_fields())

    def _spots(self, chunk):
        """This life's rolled opportunities; geography itself holds no encounter map."""
        ident = chunk_ident(chunk.key)
        spots = tuple(EncounterSpot(spot_id(chunk.key, index), action, chunk.key, x, y)
                      for index, (action, x, y) in enumerate(self.spot_plans.get(ident, ())))
        extra = self.forced.get(ident)
        if not extra:
            return spots
        fkey = (chunk.key, self.life, tuple(extra), spots)
        hit = self._spot_cache.get(fkey)
        if hit is not None:
            return hit
        result = list(spots)
        for index, encounter in enumerate(extra):
            spot = forced_spot(chunk, encounter, index, taken=[(s.x, s.y) for s in result])
            if spot is not None:
                result.append(spot)
        self._spot_cache[fkey] = tuple(result)
        return self._spot_cache[fkey]

    def _live(self, chunk):
        """Spots this life's spawn windows admitted."""
        result = [spot for spot in self._spots(chunk) if spot.id in self.admitted]
        for lead in self.leads:
            if lead["chunk"] == chunk_ident(chunk.key) and lead["expires_ms"] > self.total_ms:
                result.append(EncounterSpot(lead["id"], lead["action"], chunk.key, lead["x"], lead["y"]))
        return result

    def _active(self, encounter):
        """Admitted, unfinished instances of an encounter around the avatar now."""
        count = 0
        for chunk in self._resident():
            count += sum(1 for spot in self._live(chunk)
                         if spot.encounter == encounter and spot.id not in self.completed)
        if encounter == BOAR_ENCOUNTER:
            resident = {chunk.key for chunk in self._resident()}
            count += sum(1 for t in self.game.targets.values() if not t.id.startswith("enc:")
                         and t.hp > 0 and t.chunk in resident and t.id in self.admitted)
        return count

    def _note(self, chunk_id, spot_id, encounter, result):
        self.screen_log.append({"life": self.life, "chunk": chunk_id, "spot": spot_id,
                                "action": encounter, "result": result})
        del self.screen_log[:-SCREEN_LOG_LIMIT]

    def _admit(self, ident, encounter, chunk_id="?"):
        limit = self.budget.get(encounter)
        if limit is not None:
            active = self._active(encounter)
            if active >= limit:
                self.stats["rejected"] += 1
                self._note(chunk_id, ident, encounter, f"rejected: window full ({active}/{limit} at once)")
                return False
            self.spawned[encounter] += 1
        self.admitted[ident] = encounter
        category = BY_ID[encounter].spawn_category
        if category:
            self.stats[f"{category}_spots"] += 1
        self._note(chunk_id, ident, encounter, "admitted")
        return True

    def _pity(self, chunk, chunk_id, category, taken):
        """Force one spot of a starved category into `chunk` (deterministic)."""
        ctx = self.spot_context(chunk.key)
        choices = [(a, w) for a, w in bucket(ctx) if a.spawn_category == category
                   and (self.budget.get(a.id) is None or self._active(a.id) < self.budget[a.id])]
        if not choices:
            self._note(chunk_id, None, None, f"pity {category}: nothing eligible (or its window is full)")
            return False
        roll = derive_seed(self.game.world.world_seed, "pity-v1", self.life, chunk_id, category) \
            % sum(w for _, w in choices)
        for action, w in choices:
            if roll < w:
                break
            roll -= w
        index = len(self.forced.get(chunk_id, ()))
        spot = forced_spot(chunk, action.id, index, taken=taken)
        if spot is None:
            self._note(chunk_id, None, action.id, f"pity {category}: no free cell")
            return False
        self.forced.setdefault(chunk_id, []).append(action.id)
        self.stats["pity"] += 1
        self._note(chunk_id, spot.id, action.id, f"pity {category} after {self.drought[category]} empty chunks")
        return self._admit(spot.id, action.id, chunk_id)

    def _screen(self):
        """Roll when the player enters a chunk, then apply windows and pity.
        Asset-spawned boars are always removed: enemies come only from fight spots."""
        for chunk in (self.game.current_chunk(),):
            ident = chunk_ident(chunk.key)
            if ident in self.screened_chunks:
                continue
            roll_seed = derive_seed(self.game.world.world_seed, "runtime-opportunity-v1",
                                    self.life, len(self.spot_plans), ident)
            context = self.spot_context(chunk.key)
            rolled = chunk_spots(chunk, life=self.life, context=context,
                                 roll_seed=roll_seed)
            self.spot_plans[ident] = [(s.encounter, s.x, s.y) for s in rolled]
            self.roll_log.append({"chunk": ident, "region": context.region,
                                  "bucket": [{"id": a.id, "base": a.weight,
                                              "region_percent": context.region_def.multiplier(a.id)
                                              if context.region_def else 100,
                                              "final": w} for a, w in bucket(context)],
                                  "result": [s.encounter for s in rolled]})
            del self.roll_log[:-ROLL_LOG_LIMIT]
            self.screened_chunks.add(ident)
            self.stats["chunks"] += 1
            admitted = set()
            spots = self._spots(chunk)
            for spot in spots:
                if self._admit(spot.id, spot.encounter, ident):
                    admitted.add(BY_ID[spot.encounter].spawn_category)
            taken = [(s.x, s.y) for s in spots]
            for category in PITY_CHUNKS:
                if category in admitted:
                    self.drought[category] = 0
                    continue
                self.drought[category] += 1
                if self.drought[category] >= PITY_CHUNKS[category] and self._pity(chunk, ident, category, taken):
                    self.drought[category] = 0
                    taken = [(s.x, s.y) for s in self._spots(chunk)]
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if target.id.startswith("enc:") or target.id in self.screened_targets:
                continue
            self.screened_targets.add(target.id)
            target.hp = 0

    def _spot_by_id(self, spot_id):
        if isinstance(spot_id, str) and spot_id.startswith("lead:"):
            for lead in self.leads:
                if lead["id"] == spot_id and lead["expires_ms"] > self.total_ms:
                    key = ChunkKey(lead["dimension"], lead["chunk_x"], lead["chunk_y"])
                    if self.game.world.peek(key) is not None:
                        return EncounterSpot(spot_id, lead["action"], key, lead["x"], lead["y"])
            return None
        parts = (spot_id or "").split(":")
        if len(parts) != 5 or parts[0] != "enc":
            return None
        try:
            key = ChunkKey(parts[1], int(parts[2]), int(parts[3]))
        except ValueError:
            return None
        chunk = self.game.world.peek(key)
        if chunk is None:
            return None
        return next((s for s in self._spots(chunk) if s.id == spot_id), None)

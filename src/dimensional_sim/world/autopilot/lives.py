"""Death, the anchor interlude between lives, anchor purchases and rebirth."""
from .. import economy
from ..catalog import JOURNAL_FAVOR_MASTERY, JOURNAL_GUARANTEE_MASTERY, REGIONS
from ..catalog import ATTRIBUTES, BY_ID
from ..generation import GENERATOR_VERSION
from ..journal import record_death, validate_journal
from ..repository import WorldRepository
from ..runtime import Exploration
from .constants import ANCHOR_COUNTDOWN_MS, RETURN_COOLDOWN_MS


class LivesMixin:
    def _die(self):
        """Health hit zero: write the life report, then wait at the anchor in a fresh Exploration."""
        record_death(self.journal, self.cause or "exhaustion", self.game.elapsed_ms)
        self._end_life()

    def return_to_anchor(self):
        """End a life by choice after buying the skill; uses simulation time for cooldown."""
        if "return_anchor" not in self.unlocked or self.anchor_ms is not None or self.in_prologue:
            raise ValueError("return to anchor is unavailable")
        if self.total_ms < self.return_ready_ms:
            raise ValueError("return to anchor is cooling down")
        self.return_ready_ms = self.total_ms + RETURN_COOLDOWN_MS
        self.cause = "return"
        self._end_life()

    def _end_life(self):
        gained = economy.rebirth_ash(self.inventory, self.depth, self.converted)
        self.report = self._life_report(gained)
        self.ash += gained
        for item, count in self.inventory.items():
            self.converted[item] = self.converted.get(item, 0) + count
        self.inventory.clear()
        self.equipped.clear()
        self._entry("life", f"Life {self.life} ended. The anchor gathers {gained} dimensional ash.")
        self._respawn_at_anchor()
        self.anchor_ms = ANCHOR_COUNTDOWN_MS
        self.anchor_wait = self.life == 1  # the first anchor dialogue waits to be read
        self.leads = []
        self.task = None
        self.goal = None
        self._field_cache.clear()

    def _life_report(self, gained=0):
        lived = self.game.elapsed_ms // 1000
        lines = [f"{name.capitalize()} experience gained: {self.regular[name]}"
                 f" (dimensional +{self.life_gain[name]})" for name in ATTRIBUTES]
        cause = {"starvation": "Cause: starvation", "boar": "Cause: a bramble boar",
                 "return": "Returned by choice"}.get(self.cause, "Cause: exhaustion")
        bounty = ", ".join(f"{BY_ID[i].name.lower()} {n} (max {limit} at once)" for i, n, limit in self.bounty())
        lines += [f"Forest bounty this life: {bounty}",
                  f"Spots found: {self.stats['food_spots']} food, {self.stats['enemy_spots']} boars"
                  f" ({self.stats['pity']} by pity), {self.stats['rejected']} turned away by caps",
                  f"Crafted {self.stats['crafted']}, ate {self.stats['eaten']}, prayed {self.stats['prayers']}",
                  f"Carried resources and depth became {gained} dimensional ash.",
                  f"Blessing {self.blessing} - dimensional ash {self.ash + gained}",
                  f"Encounters completed: {len(self.completed)}",
                  f"Deepest ring reached: {self.depth} (best {self.best_depth})",
                  f"Survived: {lived // 60}m {lived % 60:02d}s", cause, "Returning to anchor..."]
        return {"seq": self.sequence + 1, "life": self.life, "clock_ms": self.total_ms,
                "title": f"Life {self.life} ends", "lines": lines}

    def _respawn_at_anchor(self):
        """A new Exploration with the same settings (and world, unless it was regenerated)."""
        config = {name: getattr(self.game, name) for name in (
            "movement_interval_ms", "animation_rate_percent", "attack_rate_percent", "attack_damage")}
        press = self.game.step_on_press
        previous_world = self.game.world
        world = self._current_generator_world(self.game.world)
        self.game = Exploration(world, self.dimension, animations=self.game.animations, **config)
        self.game.step_on_press = press
        if world is not previous_world:
            self.anchor = self._anchor()
            self._entry("rebirth", "While the anchor held you, the forest grew back in a new shape.")

    def _current_generator_world(self, world):
        """Worlds pinned to an older generator (homogeneous v1 Forest) are regenerated
        from the same seed with the current region-shaped generator between lives.
        Mid-life the pinned world never changes, so a save always replays exactly."""
        if world.generator_version >= GENERATOR_VERSION:
            return world
        fresh = WorldRepository(world.world_seed, world.dimensions, world.catalog, world.cache_limit)
        self._clear_caches()
        return fresh

    # Anchor action type -> exact fields it carries (session.validate_input checks the type).
    ANCHOR_FIELDS = {"return": {"type"}, "begin_life": {"type"}, "unlock": {"type", "id"},
                     "boon": {"type", "id"}, "journal_favor": {"type", "id", "mode"},
                     "journal_guarantee": {"type", "id", "region"}}
    ANCHOR_ACTIONS = tuple(ANCHOR_FIELDS)

    def anchor_offers(self):
        """Anchor shop rows (economy.offers) for the UI and debugging."""
        return economy.offers(self)

    def anchor_action(self, action):
        """At the anchor: buy an unlock / boon, set Journal controls, or begin a life."""
        if type(action) is not dict:
            raise ValueError("anchor action requires the anchor space")
        kind = action.get("type")
        if type(kind) is not str or self.ANCHOR_FIELDS.get(kind) != set(action):
            raise ValueError("invalid anchor action")
        if kind == "return":
            self.return_to_anchor()
            return
        if self.anchor_ms is None:
            raise ValueError("anchor action requires the anchor space")
        if kind == "begin_life":
            self._begin_life()
        elif kind == "journal_favor":
            self._journal_favor(action["id"], action["mode"])
        elif kind == "journal_guarantee":
            ident, region = action["id"], action["region"]
            if ident is not None and (ident not in BY_ID or BY_ID[ident].placement != "spot"
                                      or self.mastery.get(ident, 0) < JOURNAL_GUARANTEE_MASTERY):
                raise ValueError("guarantee requires spot mastery 3")
            if (ident is None and region is not None) or (ident is not None and
                    (region not in REGIONS or REGIONS[region].biome not in BY_ID[ident].biomes or
                     (BY_ID[ident].regions is not None and region not in BY_ID[ident].regions) or
                     REGIONS[region].multiplier(ident) == 0)):
                raise ValueError("guarantee requires an eligible region")
            self.journal_guarantee = ident
            self.journal_guarantee_region = region
            self.anchor_wait = True
            self._entry("purchase", f"Journal guarantee: {BY_ID[ident].name} in {REGIONS[region].name}."
                        if ident else "Journal guarantee cleared.")
        else:
            if type(action["id"]) is not str:
                raise ValueError("invalid anchor action")
            row = economy.purchase(self, kind, action["id"])
            self.anchor_wait = True
            self._entry("purchase", f"Bought {row['name']} for {row['cost']} {row['currency']}.")

    def _journal_favor(self, ident, mode):
        if ident not in BY_ID or BY_ID[ident].placement != "spot" \
                or mode not in ("normal", "favor", "suppress") \
                or self.mastery.get(ident, 0) < JOURNAL_FAVOR_MASTERY:
            raise ValueError("journal odds require spot mastery 2")
        if mode == "normal":
            self.journal_favor.pop(ident, None)
        else:
            self.journal_favor[ident] = mode
        self.anchor_wait = True
        self._entry("purchase", f"Journal: {BY_ID[ident].name} odds set to {mode}.")

    def _begin_life(self):
        self.anchor_ms = None
        self.anchor_wait = False
        self.boon, self.boon_next = self.boon_next, None
        self.life += 1
        self._new_life_state()
        self._entry("rebirth", "The anchor sends you into another life with your new possibilities.")

    @classmethod
    def rebuilt(cls, old, game):
        """A brand-new world (`game`) for an existing expedition: keeps everything that
        persists across lives (dimensional XP, currencies, unlocks, mastery, journal,
        skills, the boon chosen for the next life) and starts the next life there,
        without the prologue. Used by the hosted "New world, keep progress" button."""
        new = cls(game, skills=old.skills, fresh=False)
        new.dimensional = dict(old.dimensional)
        for name in ("blessing", "ash", "best_depth", "total_ms", "sequence", "decisions",
                     "return_ready_ms"):
            setattr(new, name, getattr(old, name))
        if old.anchor_ms is None:
            new.ash += economy.rebirth_ash(old.inventory, old.depth, old.converted)
        new.converted = dict(old.converted)
        if old.anchor_ms is None:
            for item, count in old.inventory.items():
                new.converted[item] = new.converted.get(item, 0) + count
        new.unlocked, new.mastery = set(old.unlocked), dict(old.mastery)
        new.journal_guarantee = old.journal_guarantee
        new.journal_guarantee_region = old.journal_guarantee_region
        new.knowledge, new.recipes = set(old.knowledge), set(old.recipes)
        new.journal_disabled, new.journal_favor = set(old.journal_disabled), dict(old.journal_favor)
        new.journal = validate_journal(old.journal)
        new.log = [dict(e) for e in old.log]
        new.life = old.life + 1
        new.boon, new.boon_next = old.boon_next, None
        new._new_life_state()
        new._screen()
        new._entry("rebirth", "The world was rebuilt. A new forest, the same soul.")
        return new

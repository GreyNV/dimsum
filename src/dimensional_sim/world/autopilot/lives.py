"""Death, the anchor interlude between lives, anchor purchases and rebirth."""
from .. import economy
from ..catalog import JOURNAL_FAVOR_MASTERY, JOURNAL_TOGGLE_MASTERY
from ..catalog import ATTRIBUTES, BY_ID, ITEMS
from ..generation import GENERATOR_VERSION
from ..journal import record_death, validate_journal
from ..repository import WorldRepository
from ..runtime import Exploration
from .constants import ANCHOR_COUNTDOWN_MS


class LivesMixin:
    def _die(self):
        """Health hit zero: write the life report, then wait at the anchor in a fresh Exploration."""
        self.report = self._life_report()
        self._entry("life", f"Life {self.life} ended. The anchor pulls you back.")
        record_death(self.journal, self.cause or "exhaustion", self.game.elapsed_ms)
        self._respawn_at_anchor()
        self.anchor_ms = ANCHOR_COUNTDOWN_MS
        self.anchor_wait = False
        self.leads = []
        self.task = None
        self.goal = None
        self._field_cache.clear()

    def _life_report(self):
        lived = self.game.elapsed_ms // 1000
        lines = [f"{name.capitalize()} experience gained: {self.regular[name]}"
                 f" (dimensional +{self.life_gain[name]})" for name in ATTRIBUTES]
        cause = {"starvation": "Cause: starvation", "boar": "Cause: a bramble boar"}.get(self.cause, "Cause: exhaustion")
        bounty = ", ".join(f"{BY_ID[i].name.lower()} {n} (max {limit} at once)" for i, n, limit in self.bounty())
        carried = sum(economy.offer_value(i, n) for i, n in self.inventory.items())
        lines += [f"Forest bounty this life: {bounty}",
                  f"Spots found: {self.stats['food_spots']} food, {self.stats['enemy_spots']} boars"
                  f" ({self.stats['pity']} by pity), {self.stats['rejected']} turned away by caps",
                  f"Crafted {self.stats['crafted']}, ate {self.stats['eaten']}, prayed {self.stats['prayers']}",
                  f"Carrying items worth {carried} dust if offered, or "
                  f"{economy.rebirth_ash(self.inventory, self.depth)} ash if left to burn",
                  f"Blessing {self.blessing} - dust {self.dust} - ash {self.ash}",
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
    ANCHOR_FIELDS = {"trade": {"type", "item"}, "begin_life": {"type"}, "unlock": {"type", "id"},
                     "boon": {"type", "id"}, "mastery": {"type", "id"},
                     "journal_toggle": {"type", "id", "enabled"}, "journal_favor": {"type", "id", "mode"}}
    ANCHOR_ACTIONS = tuple(ANCHOR_FIELDS)

    def anchor_offers(self):
        """Anchor shop rows (economy.offers) for the UI and debugging."""
        return economy.offers(self)

    def anchor_action(self, action):
        """Between lives: offer an item stack, buy an unlock / boon / mastery, set Journal
        roll controls, or begin the next life. Raises ValueError for anything invalid."""
        if self.anchor_ms is None or type(action) is not dict:
            raise ValueError("anchor action requires the anchor space")
        kind = action.get("type")
        if type(kind) is not str or self.ANCHOR_FIELDS.get(kind) != set(action):
            raise ValueError("invalid anchor action")
        if kind == "begin_life":
            self._begin_life()
        elif kind == "trade":
            self._offer(action["item"])
        elif kind == "journal_toggle":
            self._journal_toggle(action["id"], action["enabled"])
        elif kind == "journal_favor":
            self._journal_favor(action["id"], action["mode"])
        else:
            if type(action["id"]) is not str:
                raise ValueError("invalid anchor action")
            row = economy.purchase(self, kind, action["id"])
            self.anchor_wait = True
            self._entry("purchase", f"Bought {row['name']} for {row['cost']} {row['currency']}.")

    def _offer(self, item):
        if item not in ITEMS:
            raise ValueError("invalid anchor action")
        count = self.inventory.pop(item, 0)
        if count:
            self.equipped = {slot: gear for slot, gear in self.equipped.items() if gear != item}
            gained = economy.offer_value(item, count)
            self.dust += gained
            self.anchor_wait = True
            self._entry("trade", f"Offered {count} {ITEMS[item].name.lower()} for {gained} dimensional dust.",
                        items=[(item, -count)])

    def _journal_toggle(self, ident, enabled):
        if ident not in BY_ID or BY_ID[ident].placement != "spot" or type(enabled) is not bool \
                or self.mastery.get(ident, 0) < JOURNAL_TOGGLE_MASTERY:
            raise ValueError("journal toggle requires spot mastery 2")
        if enabled:
            self.journal_disabled.discard(ident)
        else:
            self.journal_disabled.add(ident)
        self.anchor_wait = True
        self._entry("purchase", f"Journal: {BY_ID[ident].name} {'enabled' if enabled else 'disabled'}.")

    def _journal_favor(self, ident, mode):
        if ident not in BY_ID or BY_ID[ident].placement != "spot" \
                or mode not in ("normal", "favor", "suppress") \
                or self.mastery.get(ident, 0) < JOURNAL_FAVOR_MASTERY:
            raise ValueError("journal odds require spot mastery 3")
        if mode == "normal":
            self.journal_favor.pop(ident, None)
        else:
            self.journal_favor[ident] = mode
        self.anchor_wait = True
        self._entry("purchase", f"Journal: {BY_ID[ident].name} odds set to {mode}.")

    def _begin_life(self):
        burned = dict(self.inventory)
        ash = economy.rebirth_ash(burned, self.depth)
        self.ash += ash
        self.anchor_ms = None
        self.anchor_wait = False
        self.boon, self.boon_next = self.boon_next, None
        self.life += 1
        self._new_life_state()
        items = ", ".join(f"{n} {ITEMS[i].name.lower()}" for i, n in burned.items()) or "nothing"
        self._entry("rebirth", f"Rebirth: burned {items} and the road behind you into {ash} ash.",
                    items=[(i, -n) for i, n in burned.items()])

    @classmethod
    def rebuilt(cls, old, game):
        """A brand-new world (`game`) for an existing expedition: keeps everything that
        persists across lives (dimensional XP, currencies, unlocks, mastery, journal,
        skills, the boon chosen for the next life) and starts the next life there,
        without the prologue. Used by the hosted "New world, keep progress" button."""
        new = cls(game, skills=old.skills, fresh=False)
        new.dimensional = dict(old.dimensional)
        for name in ("blessing", "dust", "ash", "best_depth", "total_ms", "sequence", "decisions"):
            setattr(new, name, getattr(old, name))
        new.unlocked, new.mastery = set(old.unlocked), dict(old.mastery)
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

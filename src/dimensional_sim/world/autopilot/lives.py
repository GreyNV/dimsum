"""Death, the anchor interlude between lives, anchor purchases and rebirth."""
from .. import economy
from ..catalog import ATTRIBUTES, BUILDINGS, BY_ID, ENEMIES, ITEMS, UNLOCKS
from ..generation import GENERATOR_VERSION
from ..journal import record_death, validate_journal
from ..progression import dimensional_level
from ..repository import WorldRepository
from ..runtime import Exploration
from .constants import ANCHOR_COUNTDOWN_MS, CONTACT_COOLDOWN_MS, PROLOGUE_MS


def death_cause_text(cause):
    """Life-report line for a death cause (enemy causes come from the catalog)."""
    enemy = next((e for e in ENEMIES.values() if e.cause == cause), None)
    if enemy is not None:
        return f"Cause: {enemy.cause_text}"
    return {"starvation": "Cause: starvation"}.get(cause, "Cause: exhaustion")


class LivesMixin:
    def _grant_level_unlocks(self):
        """Open every unlock whose dimensional-level gate is met (they never close again)."""
        for unlock in UNLOCKS.values():
            if unlock.level is None or unlock.id in self.unlocked:
                continue
            attribute, needed = unlock.level
            if dimensional_level(self.dimensional[attribute]) >= needed:
                self.unlocked.add(unlock.id)
                self._entry("lore", f"Your {attribute} carries you further: {unlock.name}. {unlock.description}")

    def has_ability(self, ability):
        """Whether an owned unlock grants `ability` (catalog.ABILITIES)."""
        return any(UNLOCKS[u].ability == ability for u in self.unlocked)

    def _die(self):
        """Health hit zero: write the life report, then wait at the anchor in a fresh Exploration."""
        record_death(self.journal, self.cause or "exhaustion", self.game.elapsed_ms)
        self._end_life()

    def contact_block(self):
        """Why the anchor cannot be contacted now, or None."""
        if self.anchor_ms is not None or self.contact:
            return "Already at the anchor"
        if self.in_prologue:
            return "Not yet"
        if not self.has_ability("contact_anchor"):
            return "Locked"
        if self.total_ms < self.contact_ready_ms:
            return "Recharging"
        return None

    def contact_anchor(self):
        """Reach the anchor mid-life: the world waits and the shop opens; resume_life closes it."""
        reason = self.contact_block()
        if reason is not None:
            raise ValueError(f"cannot contact the anchor: {reason.lower()}")
        if self.possessing:
            self._end_possession()
        self.contact = True

    def resume_life(self):
        """Close a mid-life contact: the life goes on exactly where it stopped."""
        if not self.contact:
            raise ValueError("the anchor is not contacted")
        self.contact = False
        self.contact_ready_ms = self.total_ms + CONTACT_COOLDOWN_MS

    def offer_at_anchor(self, ident, count):
        """Convert chosen carried or stored items during this life, using lifetime diminishing returns."""
        if (not self.contact or not self.at_camp() or type(ident) is not str
                or ident not in ITEMS or type(count) is not int or count < 1):
            raise ValueError("offer resources while visiting the anchor camp")
        if self.camp_stock().get(ident, 0) < count:
            raise ValueError("not enough resources to offer")
        gained = economy.offer_value(ident, count, self.converted.get(ident, 0))
        if gained < 1:
            raise ValueError("this offer would yield no ash; offer more together")
        self._pay(((ident, count),))
        self.converted[ident] = self.converted.get(ident, 0) + count
        self.ash += gained
        self._entry("purchase", f"Offered {count} {ITEMS[ident].name.lower()} for {gained} dimensional ash.",
                    items=[(ident, -count)])

    def camp_offer_value(self, ident, count):
        return economy.offer_value(ident, count, self.converted.get(ident, 0))

    def _end_life(self):
        if self.possessing:
            self._end_possession()
        self.contact = False
        carried = self._converting()
        gained = economy.rebirth_ash(carried, self.depth, self.converted)
        self.report = self._life_report(gained)
        self.ash += gained
        for item, count in carried.items():
            self.converted[item] = self.converted.get(item, 0) + count
        if not self._chest_bound():
            self.chest = {}
        self.inventory.clear()
        self.equipped.clear()
        self._entry("life", f"Life {self.life} ended. The anchor gathers {gained} dimensional ash.")
        self._respawn_at_anchor()
        self.anchor_ms = ANCHOR_COUNTDOWN_MS
        self.anchor_wait = self.life == 1  # the first anchor dialogue waits to be read
        self.leads = []
        self.hunting = {}   # the old life's hunters are gone with its world (a save would not load)
        self.fight_paid = {}   # likewise the XP paid against them
        self.task = None
        self.goal = None
        self._field_cache.clear()

    def _chest_bound(self):
        return any(BUILDINGS[b].function == "storage" for b in self.bound_buildings)

    def _converting(self):
        """Everything that turns into ash when a life ends: the inventory, plus an unbound chest."""
        carried = dict(self.inventory)
        if not self._chest_bound():
            for item, count in self.chest.items():
                carried[item] = carried.get(item, 0) + count
        return carried

    def _life_report(self, gained=0):
        lived = self.game.elapsed_ms // 1000
        lines = [f"{name.capitalize()} experience gained: {self.regular[name]}"
                 f" (dimensional +{self.life_gain[name]})" for name in ATTRIBUTES
                 if self.regular[name] or self.life_gain[name]]   # unused disciplines stay hidden
        cause = death_cause_text(self.cause)
        bounty = ", ".join(f"{BY_ID[i].name.lower()} {n} (max {limit} at once)" for i, n, limit in self.bounty())
        lines += [f"Forest bounty this life: {bounty}",
                  f"Spots found: {self.stats['food_spots']} food, {self.stats['enemy_spots']} enemies"
                  f" ({self.stats['pity']} by pity), {self.stats['rejected']} turned away by caps",
                  f"Crafted {self.stats['crafted']}, ate {self.stats['eaten']}, prayed {self.stats['prayers']}",
                  f"Carried resources and depth became {gained} dimensional ash.",
                  f"Dimensional ash now: {self.ash + gained}",
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
        previous_seen = self.game.seen
        world = self._current_generator_world(self.game.world)
        self.game = Exploration(world, self.dimension, animations=self.game.animations, **config)
        if world is previous_world:
            for key, rows in previous_seen.items():
                current = self.game.seen.setdefault(key, [0] * len(rows))
                for y, mask in enumerate(rows):
                    current[y] |= mask
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
    ANCHOR_FIELDS = {"contact": {"type"}, "resume": {"type"}, "possess": {"type"}, "release": {"type"},
                     "campfire": {"type"}, "begin_life": {"type"}, "unlock": {"type", "id"},
                     "bind": {"type", "id"}, "keep": {"type", "id"}, "location_focus": {"type", "id", "mode"},
                     "location": {"type", "id"}, "offer": {"type", "id", "count"}}
    ANCHOR_ACTIONS = tuple(ANCHOR_FIELDS)
    # Journal controls work at any time (Journal > Places): a camp's focus there.
    JOURNAL_ACTIONS = ("location_focus",)

    def anchor_offers(self):
        """Anchor shop rows (economy.offers) for the UI and debugging."""
        return economy.offers(self)

    def anchor_action(self, action):
        """Use skills and nearby choices; at the anchor buy, offer, or resume.
        Journal controls work at any time."""
        if type(action) is not dict:
            raise ValueError("anchor action requires the anchor space")
        kind = action.get("type")
        if type(kind) is not str or self.ANCHOR_FIELDS.get(kind) != set(action):
            raise ValueError("invalid anchor action")
        if kind == "contact":
            self.contact_anchor()
            return
        if kind == "resume":
            self.resume_life()
            return
        if kind == "possess":
            self.possess()
            return
        if kind == "release":
            self.release()
            return
        if kind == "location":
            if type(action["id"]) is not str:
                raise ValueError("invalid location action")
            self.use_location_action(action["id"])
            return
        if kind == "offer":
            self.offer_at_anchor(action["id"], action["count"])
            return
        if kind == "campfire":   # a skill during a life (manual or auto): start making a fire here
            if not self.can_make_fire():
                raise ValueError("cannot make a campfire now")
            self.goal = None
            self._start_self(BY_ID["make_campfire"])
            return
        if kind not in self.JOURNAL_ACTIONS and self.anchor_ms is None and not (self.contact and kind != "begin_life"):
            raise ValueError("anchor action requires the anchor space")
        if kind == "begin_life":
            self._begin_life()
        elif kind == "location_focus":
            if type(action["id"]) is not str or type(action["mode"]) is not str:
                raise ValueError("invalid focus")
            self.set_location_focus(action["id"], action["mode"])
            self.anchor_wait = self.anchor_wait or self.anchor_ms is not None
        else:
            if type(action["id"]) is not str:
                raise ValueError("invalid anchor action")
            row = economy.purchase(self, kind, action["id"])
            self.anchor_wait = self.anchor_ms is not None
            self._entry("purchase", f"Bought {row['name']} for {row['cost']} {row['currency']}.")

    def _begin_life(self):
        self.anchor_ms = None
        self.anchor_wait = False
        if self.opening:   # a new expedition leaves the anchor for its first life: the prologue
            self.opening = False
            self._start_task("awaken", PROLOGUE_MS["awaken"])
            self._screen()
            return
        self.life += 1
        self._new_life_state()
        self._entry("rebirth", "The anchor sends you into another life with your new possibilities.")

    @classmethod
    def rebuilt(cls, old, game):
        """A brand-new world (`game`) for an existing expedition: keeps everything that
        persists across lives (dimensional XP, ash, unlocks, location mastery, journal,
        cooldowns) and starts the next life there,
        without the prologue. Used by the hosted "New world, keep progress" button."""
        new = cls(game, fresh=False)
        new.dimensional = dict(old.dimensional)
        for name in ("ash", "best_depth", "total_ms", "sequence", "decisions",
                     "contact_ready_ms"):
            setattr(new, name, getattr(old, name))
        if old.possessing:
            old._end_possession()
        new.possess_charge = old.possession_charge()
        new.possess_charge_at_ms = old.total_ms
        carried = old._converting() if old.anchor_ms is None else {}
        if old.anchor_ms is None:
            new.ash += economy.rebirth_ash(carried, old.depth, old.converted)
        new.converted = dict(old.converted)
        for item, count in carried.items():
            new.converted[item] = new.converted.get(item, 0) + count
        new.bound_buildings = set(old.bound_buildings)   # bound buildings follow the anchor
        new.chest = dict(old.chest) if old._chest_bound() else {}
        new.unlocked = set(old.unlocked)
        new.location_done, new.location_focus = dict(old.location_done), dict(old.location_focus)
        new.knowledge, new.recipes = set(old.knowledge), set(old.recipes)
        new.journal_disabled = set(old.journal_disabled)
        new.journal = validate_journal(old.journal)
        new.log = [dict(e) for e in old.log]
        new.life = old.life + 1
        new._new_life_state()
        new.life_recipes = set(old.life_recipes) if old.anchor_ms is not None else set()
        new._screen()
        new._entry("rebirth", "The world was rebuilt. A new forest, the same soul.")
        return new

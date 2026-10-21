"""Rewards, loot, leads, eating and self actions (crafting, reflection, prayer)."""
from dataclasses import replace

from .. import effects
from ..actions import bucket, outcome_chance, reasons_against
from ..catalog import BY_ID, ITEMS, RECIPE_KEEP_COST, RECIPE_NAMES, mastery_level
from ..encounters import features, lead_spot, roll_loot
from ..equipment import equip_item
from ..journal import record_action, record_items
from ..models import ChunkKey, chunk_ident
from ..progression import DIMENSIONAL_DIVISOR, scaled_ms
from ..seeds import derive_seed
from .ecology import cell_of
from .constants import (AFTER_LOCATION_REST_WEIGHT, FOOD_HEALS_DIVISOR,
                        FIRE_KIT, INVENTORY_SLOTS, LEAD_HISTORY_LIMIT, LOG_LIMIT, LOOK_RADIUS, NEED_ACTIONS,
                        PAUSE_AFTER_ACTIVITY_MS, POINT, STACK_LIMIT, VITAL_MAX)


class OutcomesMixin:
    crafting_enabled = True   # simulation policy switch (world/simulate.py "hoard"); not saved

    def _entry(self, kind, text, *, encounter=None, attribute=None, xp=0, dim_xp=0, items=()):
        self.sequence += 1
        self.log.append({"seq": self.sequence, "clock_ms": self.total_ms, "life": self.life,
                         "type": kind, "encounter": encounter, "text": text,
                         "attribute": attribute, "xp": xp, "dim_xp": dim_xp,
                         "items": [[item, count] for item, count in items]})
        del self.log[:-LOG_LIMIT]

    def _add_item(self, item, count):
        have = self.inventory.get(item)
        if have is None and len(self.inventory) >= INVENTORY_SLOTS:
            return 0
        kept = min(count, STACK_LIMIT - (have or 0))
        if kept > 0:
            self.inventory[item] = (have or 0) + kept
        return max(0, kept)

    def _remove_item(self, item, count):
        self.inventory[item] -= count
        if not self.inventory[item]:
            del self.inventory[item]
            # Gear consumed by a craft (e.g. a wrap being studded) leaves its slot empty.
            self.equipped = {slot: worn for slot, worn in self.equipped.items() if worn != item}

    def _gain_xp(self, attribute, xp):
        """Regular XP for this life plus the persistent dimensional share; returns that share."""
        dim = xp // DIMENSIONAL_DIVISOR
        if xp:
            self.regular[attribute] += xp
            self.dimensional[attribute] += dim
            self.life_gain[attribute] += dim
            if dim:
                self._grant_level_unlocks()
        return dim

    def _record_leads(self, leads, status):
        self.lead_history.extend({**lead, "status": status} for lead in leads)
        self.lead_history = self.lead_history[-LEAD_HISTORY_LIMIT:]

    def _apply_outcomes(self, action, source_id):
        """Resolve catalog outcomes after the journal count has advanced."""
        count = self.journal["actions"].get(action.id, 0)
        region = self.region(self.game.player.chunk)
        picked = {}   # group -> index of the alternative that happened (one roll per group)
        for group in dict.fromkeys(o.group for o in action.outcomes if o.group is not None):
            roll = derive_seed(self.game.world.world_seed, "action-outcome-group-v1", self.life,
                               action.id, source_id, group) % 100
            for index, outcome in enumerate(action.outcomes):
                if outcome.group != group or count < outcome.at_count:
                    continue
                chance = outcome_chance(outcome, region)
                if roll < chance:
                    picked[group] = index
                    break
                roll -= chance
        for index, outcome in enumerate(action.outcomes):
            if count < outcome.at_count:
                continue
            if outcome.group is not None:
                if picked.get(outcome.group) != index:
                    continue
            else:
                chance = outcome_chance(outcome, region)
                roll = derive_seed(self.game.world.world_seed, "action-outcome-v1", self.life,
                                   action.id, source_id, index) % 100
                if roll >= chance:
                    continue
            if outcome.text is not None:
                self._entry("lore", outcome.text, encounter=action.id)
            if outcome.kind == "knowledge":
                if outcome.id not in self.knowledge:
                    self.knowledge.add(outcome.id)
                    if action.placement != "story":   # a story step logs its own lore (story.py)
                        self._entry("lore", f"Learned {outcome.id.replace('_', ' ')}.", encounter=action.id)
            elif outcome.kind == "recipe":
                if outcome.id not in self.recipes and outcome.id not in self.life_recipes:
                    self.life_recipes.add(outcome.id)
                    self._entry("lore", f"Worked out how to make a {RECIPE_NAMES[outcome.id].lower()}. Keep it for "
                                f"later lives at the anchor ({RECIPE_KEEP_COST[outcome.id]} ash).", encounter=action.id)
            elif outcome.kind == "lead":
                self._create_lead(action, outcome, index, source_id)
            elif outcome.kind == "reveal":
                self.game.reveal_area(LOOK_RADIUS)
            elif outcome.kind in ("shimmer", "renew"):
                source = self._spot_by_id(source_id)
                key = source.chunk if source is not None else self.game.player.chunk
                if outcome.kind == "renew":
                    self.renew(outcome.id, key)
                else:
                    self.shimmer.add(cell_of(key))

    def _create_lead(self, action, outcome, index, source_id):
        """Place a temporary lead near its source spot (or the avatar), once per id.

        A lead with `lead_spread` points away: it lands in a neighbouring chunk, in a
        direction fixed by the seed. A lead whose placement rule finds no cell (e.g. it
        needs water and there is none) never appears."""
        target = BY_ID[outcome.id]
        source = self._spot_by_id(source_id)
        if source is None:
            key = self.game.player.chunk
            sx, sy = self.game.player.x, self.game.player.y
        else:
            key, sx, sy = source.chunk, source.x, source.y
        chunk = self.game.world.peek(key)
        if chunk is None:
            return
        if target.lead_spread:
            pick = derive_seed(self.game.world.world_seed, "lead-spread", self.life, source_id, index)
            around = [ChunkKey(key.dimension, key.x + dx, key.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if target.near == "w":   # a trail to the river leads toward a chunk that has one
                around = [k for k in around if "water" in features(self.game.world.get(k).asset)] or around
            key = around[pick % len(around)]
            chunk = self.game.world.get(key)
            sx, sy = chunk.asset.width // 2, chunk.asset.height // 2
        spot = lead_spot(chunk, outcome.id, self.life, source_id, index, (sx, sy))
        if spot is None or any(row["id"] == spot.id for row in self.leads):
            return
        lead = {"id": spot.id, "action": outcome.id, "source": source_id,
                "dimension": key.dimension, "chunk_x": key.x, "chunk_y": key.y,
                "chunk": chunk_ident(key), "x": spot.x, "y": spot.y,
                "expires_ms": self.total_ms + outcome.ttl_ms}
        self.leads.append(lead)
        self._record_leads([lead], "created")
        if target.category == "fight":   # a lead that turns out to be danger: a live enemy
            self.admitted[spot.id] = outcome.id
        self._entry("lore", f"New lead: {target.name.lower()}" + ("." if target.lead_spread == 0 else ", further off."),
                    encounter=action.id)

    def _expire_leads(self):
        expired = [lead for lead in self.leads if lead["expires_ms"] <= self.total_ms]
        if not expired:
            return
        self.leads = [lead for lead in self.leads if lead["expires_ms"] > self.total_ms]
        for lead in expired:
            self._record_leads([lead], "expired")
            name = BY_ID[lead["action"]].name.lower()
            if "night" in BY_ID[lead["action"]].tags:
                self._entry("lore", f"Dawn breaks. The {name} slinks back into the trees.")
            else:
                self._entry("lore", f"Lost track of the {name}.")
        gone = {lead["id"] for lead in expired}
        for ident in gone:   # an enemy that was only a lead wanders off
            target = self.game.targets.get(ident)
            if target is not None and target.hp > 0:
                del self.game.targets[ident]
        if self.task and self.task["type"] == "perform" and self.task["spot"] in gone:
            self.task = None
        if self.goal and self.goal.get("id") in gone:
            self.goal = None

    def _reward(self, ident, entry):
        self.completed.add(ident)
        dim = self._gain_xp(entry.attribute, entry.xp)
        seed = derive_seed(self.game.world.world_seed, "loot", self.life, ident)
        spot = self._spot_by_id(ident)
        condition = self.site_condition(spot.chunk) if spot is not None and entry.placement == "site" else None
        rolled = roll_loot(entry if condition is None or condition.drops else replace(entry, drops=None), seed)
        chop = effects.total(self.equipped, "wood_yield") if "wood" in entry.tags else 0
        if chop:   # an axe: more wood from every wood harvest
            rolled = [*rolled, ("stick", chop)]   # once per harvest, however many rows rolled
        items = [(item, kept) for item, count in rolled if (kept := self._add_item(item, count))]
        if entry.heal:
            self.health = min(VITAL_MAX, self.health + entry.heal * POINT)
        record_action(self.journal, entry.id)
        if spot is not None:
            self._deplete(entry, spot.chunk)
        if entry.placement == "spot":
            count = self.journal["actions"][entry.id]
            earned = mastery_level(count)
            if earned > self.mastery.get(entry.id, 0):
                self.mastery[entry.id] = earned
                self._entry("lore", f"Mastery {earned} of {entry.name} earned at {count} completions.",
                            encounter=entry.id)
        self._apply_outcomes(entry, ident)
        if entry.placement == "story":
            self._story_done(entry)
        if ident.startswith("lead:"):
            self._record_leads([lead for lead in self.leads if lead["id"] == ident], "completed")
            self.leads = [lead for lead in self.leads if lead["id"] != ident]
        record_items(self.journal, items)
        self.stats["completed"] += 1
        if entry.category == "fight":
            self.stats["fights"] += 1
        if entry.category == "pray":
            self.stats["prayers"] += 1
        self._entry("encounter", entry.log, encounter=entry.id, attribute=entry.attribute,
                    xp=entry.xp, dim_xp=dim, items=items)

    def _eat(self):
        """Eat the largest food that fits missing hunger, until no food fits."""
        ate = False
        while True:
            room = (VITAL_MAX - self.hunger) // POINT
            fitting = sorted((ITEMS[i].food, i) for i in self.inventory
                             if ITEMS[i].kind == "food" and ITEMS[i].food <= room)
            if not fitting:
                return ate
            value, item = fitting[-1]
            self._remove_item(item, 1)
            self.hunger += value * POINT
            heal = value // FOOD_HEALS_DIVISOR
            self.health = min(VITAL_MAX, self.health + heal * POINT)
            self.stats["eaten"] += 1
            self._entry("eat", f"Ate {ITEMS[item].name.lower()} (+{value} hunger, +{heal} health).",
                        items=[(item, -1)])
            ate = True

    def _start_self(self, action):
        duration = action.duration_ms if action.category in ("reflect", "pray") \
            else scaled_ms(action.duration_ms, self.speed(action.attribute))
        self._start_task(action.id, duration)

    def _need_action(self, visible=True, at_camp=None):
        """Need-driven crafting/building policy: the first eligible action whose need holds.
        `at_camp=True` asks what would be possible at the anchor camp (planning a trip)."""
        if not self.crafting_enabled:
            return None
        ctx = self.self_context("need", visible, at_camp)
        for action in NEED_ACTIONS:
            if reasons_against(action, ctx) or not self._keeps_fire_kit(action):
                continue
            return action
        return None

    def _keeps_fire_kit(self, action):
        """A gear craft leaves enough behind for an emergency campfire (builds, food crafts and
        the fire itself may spend it): a staff waits for spare sticks rather than eating the fire."""
        if action.category != "craft" or not action.effect:
            return True
        cost = dict(action.cost)
        return all(self.inventory.get(item, 0) - cost[item] >= need for item, need in FIRE_KIT.items() if item in cost)

    def _after_location(self, spot, allow_prayer):
        """Roll the after-location bucket (think, contemplate, prayer) or pause."""
        entries = bucket(self.self_context("after_location", allow_prayer))
        total = sum(w for _, w in entries) + AFTER_LOCATION_REST_WEIGHT
        roll = derive_seed(self.game.world.world_seed, "after-location-v6", self.life, spot.id) % total
        for action, w in entries:
            if roll < w:
                self._start_self(action)
                return
            roll -= w
        self._start_task("pause", PAUSE_AFTER_ACTIVITY_MS)

    def _complete_self(self, action):
        """Finish a self action: pay costs, then XP, loot, gear, log."""
        stock = self.camp_stock()
        if any(stock.get(item, 0) < count for item, count in action.cost):
            return   # the ingredients were eaten or lost meanwhile: nothing happens
        if action.workplace is not None and not self.at_camp():
            return   # camp work started at the camp only
        self._pay(action.cost)
        items = [(item, -count) for item, count in action.cost]
        if action.builds is not None:
            self._build(action)
        if action.places == "campfire":
            self._place_fire()
        if action.effect:
            if self._add_item(action.effect, 1):
                items.append((action.effect, 1))
                self.equipped = equip_item(self.equipped, self.inventory, action.effect)
        seed = derive_seed(self.game.world.world_seed, "self-loot", self.life, action.id, self.sequence)
        items += [(item, kept) for item, count in roll_loot(action, seed) if (kept := self._add_item(item, count))]
        record_action(self.journal, action.id)
        self._apply_outcomes(action, f"self:{self.sequence}")
        record_items(self.journal, [(i, n) for i, n in items if n > 0])
        dim = self._gain_xp(action.attribute, action.xp)
        if action.category == "craft":
            self.stats["crafted"] += 1
            text = action.log if len(items) > len(action.cost) else action.log + " Nothing came of it."
            self._entry("craft", text, attribute=action.attribute if action.xp else None,
                        xp=action.xp, dim_xp=dim, items=items)
        elif action.category == "build":
            self._entry("build", action.log, attribute=action.attribute, xp=action.xp, dim_xp=dim, items=items)
            self._stow()
        elif action.category == "camp":
            self._entry("build", action.log, attribute=action.attribute, xp=action.xp, dim_xp=dim, items=items)
        elif action.category == "pray":
            self.stats["prayers"] += 1
            self._entry("reflect", action.log)

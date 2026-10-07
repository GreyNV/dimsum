"""Rewards, loot, leads, eating and self actions (crafting, reflection, prayer)."""
from ..actions import bucket, outcome_chance, reasons_against
from ..catalog import BY_ID, ITEMS
from ..encounters import lead_spot, roll_loot
from ..equipment import equip_item
from ..journal import record_action, record_items
from ..models import chunk_ident
from ..progression import DIMENSIONAL_DIVISOR, scaled_ms
from ..seeds import derive_seed
from .constants import (AFTER_LOCATION_REST_WEIGHT, EAT_AT, FOOD_COOLDOWN_MS, FOOD_HEALS_DIVISOR,
                        INVENTORY_SLOTS, LEAD_HISTORY_LIMIT, LOG_LIMIT, NEED_ACTIONS, PAUSE_AFTER_ACTIVITY_MS,
                        POINT, STACK_LIMIT, VITAL_MAX)


class OutcomesMixin:
    crafting_enabled = True   # simulation policy switch (world/simulate.py "hoard"); not saved

    def _entry(self, kind, text, *, encounter=None, attribute=None, xp=0, dim_xp=0, items=(), blessing=0):
        self.sequence += 1
        self.log.append({"seq": self.sequence, "clock_ms": self.total_ms, "life": self.life,
                         "type": kind, "encounter": encounter, "text": text,
                         "attribute": attribute, "xp": xp, "dim_xp": dim_xp,
                         "items": [[item, count] for item, count in items], "blessing": blessing})
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

    def _gain_xp(self, attribute, xp):
        """Regular XP for this life plus the persistent dimensional share; returns that share."""
        dim = xp // DIMENSIONAL_DIVISOR
        if xp:
            self.regular[attribute] += xp
            self.dimensional[attribute] += dim
            self.life_gain[attribute] += dim
        return dim

    def _record_leads(self, leads, status):
        self.lead_history.extend({**lead, "status": status} for lead in leads)
        self.lead_history = self.lead_history[-LEAD_HISTORY_LIMIT:]

    def _apply_outcomes(self, action, source_id):
        """Resolve catalog outcomes after the journal count has advanced."""
        count = self.journal["actions"].get(action.id, 0)
        for index, outcome in enumerate(action.outcomes):
            if count < outcome.at_count:
                continue
            chance = outcome_chance(outcome, self.region(self.game.player.chunk))
            roll = derive_seed(self.game.world.world_seed, "action-outcome-v1", self.life,
                               action.id, source_id, index) % 100
            if roll >= chance:
                continue
            if outcome.kind == "knowledge":
                if outcome.id not in self.knowledge:
                    self.knowledge.add(outcome.id)
                    self._entry("lore", f"Learned {outcome.id.replace('_', ' ')}.", encounter=action.id)
            elif outcome.kind == "recipe":
                if outcome.id not in self.recipes:
                    self.recipes.add(outcome.id)
                    self._entry("lore", f"Discovered the {outcome.id.replace('_', ' ')} recipe.", encounter=action.id)
            elif outcome.kind == "lead":
                self._create_lead(action, outcome, index, source_id)

    def _create_lead(self, action, outcome, index, source_id):
        """Place a temporary lead beside its source spot (or the avatar), once per id."""
        source = self._spot_by_id(source_id)
        if source is None:
            key = self.game.player.chunk
            sx, sy = self.game.player.x, self.game.player.y
        else:
            key, sx, sy = source.chunk, source.x, source.y
        chunk = self.game.world.peek(key)
        if chunk is None:
            return
        spot = lead_spot(chunk, outcome.id, self.life, source_id, index, (sx, sy))
        if spot is None or any(row["id"] == spot.id for row in self.leads):
            return
        lead = {"id": spot.id, "action": outcome.id, "source": source_id,
                "dimension": key.dimension, "chunk_x": key.x, "chunk_y": key.y,
                "chunk": chunk_ident(key), "x": spot.x, "y": spot.y,
                "expires_ms": self.total_ms + outcome.ttl_ms}
        self.leads.append(lead)
        self._record_leads([lead], "created")
        self._entry("lore", f"A fresh {BY_ID[outcome.id].name.lower()} lead appeared.", encounter=action.id)

    def _expire_leads(self):
        expired = [lead for lead in self.leads if lead["expires_ms"] <= self.total_ms]
        if not expired:
            return
        self.leads = [lead for lead in self.leads if lead["expires_ms"] > self.total_ms]
        for lead in expired:
            self._record_leads([lead], "expired")
            self._entry("lore", f"The {BY_ID[lead['action']].name.lower()} lead went cold.")
        gone = {lead["id"] for lead in expired}
        if self.task and self.task["type"] == "perform" and self.task["spot"] in gone:
            self.task = None
        if self.goal and self.goal.get("id") in gone:
            self.goal = None

    def _reward(self, ident, entry):
        self.completed.add(ident)
        dim = self._gain_xp(entry.attribute, entry.xp)
        seed = derive_seed(self.game.world.world_seed, "loot", self.life, ident)
        items = [(item, kept) for item, count in roll_loot(entry, seed)
                 if (kept := self._add_item(item, count))]
        if entry.heal:
            self.health = min(VITAL_MAX, self.health + entry.heal * POINT)
        self.blessing += entry.blessing
        record_action(self.journal, entry.id)
        self._apply_outcomes(entry, ident)
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
                    xp=entry.xp, dim_xp=dim, items=items, blessing=entry.blessing)

    def _eat(self):
        """Auto-eat: the food that restores the most without wasting, else the smallest."""
        foods = sorted((ITEMS[i].food, i) for i in self.inventory if ITEMS[i].kind == "food")
        if not foods or self.food_cooldown_ms or self.hunger > EAT_AT:
            return False
        room = (VITAL_MAX - self.hunger) // POINT
        fitting = [f for f in foods if f[0] <= room]
        value, item = fitting[-1] if fitting else foods[0]
        self._remove_item(item, 1)
        self.hunger = min(VITAL_MAX, self.hunger + value * POINT)
        heal = value // FOOD_HEALS_DIVISOR
        self.health = min(VITAL_MAX, self.health + heal * POINT)
        self.food_cooldown_ms = FOOD_COOLDOWN_MS
        self.stats["eaten"] += 1
        self._entry("eat", f"Ate {ITEMS[item].name.lower()} (+{value} hunger, +{heal} health).",
                    items=[(item, -1)])
        return True

    def _start_self(self, action):
        duration = action.duration_ms if action.category in ("reflect", "pray") \
            else scaled_ms(action.duration_ms, self.speed(action.attribute))
        self._start_task(action.id, duration)

    def _need_action(self, visible=True):
        """Need-driven crafting policy: the first eligible recipe whose need holds."""
        if not self.crafting_enabled:
            return None
        ctx = self.self_context("need", visible)
        for action in NEED_ACTIONS:
            if reasons_against(action, ctx):
                continue
            return action
        return None

    def _after_location(self, spot, allow_prayer):
        """A need-driven craft, else a roll in the after-location bucket (think,
        contemplate, a rare prayer during live play) or a short pause."""
        need = self._need_action(allow_prayer)
        if need is not None:
            self._start_self(need)
            return
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
        """Finish a self action: pay costs, then XP, loot, gear, blessing, log."""
        if any(self.inventory.get(item, 0) < count for item, count in action.cost):
            return   # the ingredients were eaten or lost meanwhile: nothing happens
        for item, count in action.cost:
            self._remove_item(item, count)
        items = [(item, -count) for item, count in action.cost]
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
        elif action.category == "pray":
            self.prayers_this_life += 1
            self.stats["prayers"] += 1
            self.blessing += action.blessing
            self._entry("blessing", action.log, blessing=action.blessing)

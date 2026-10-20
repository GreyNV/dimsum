"""Read-only views of an expedition for the HUD, pages and debug overlay. Never mutate here."""
from dataclasses import replace

from ..actions import describe_bucket, explain
from ..catalog import BUILDINGS, BY_ID, ITEMS, rarity_glint
from ..equipment import is_equipped
from ..models import chunk_ident
from ..tuning import PITY_CHUNKS
from .constants import (ELDER_LINES, FOOD_COOLDOWN_MS, MEMORIES, POSSESS_COOLDOWN_MS,
                        POSSESS_SPEED_PERCENT, PROLOGUE_MS, PROLOGUE_NAMES, SELF_ACTIONS)


def _style(action):
    """Client presentation of an activity from the catalog (verb, body pose, work-mark color)."""
    style = action.style
    return {"verb": style.verb, "pose": style.pose, "color": action.color or style.color,
            "interaction": action.interaction}


class PresentationMixin:
    def prologue(self):
        """Presentation of the opening scene, or None once it is over."""
        if not self.in_prologue:
            return None
        stage = self.task["type"]
        lines = MEMORIES if stage == "awaken" else ELDER_LINES if stage == "listen" else ()
        return {"stage": stage, "progress": self.task["elapsed_ms"] * 1000 // self.task["duration_ms"],
                "elder": {"x": self.elder[0], "y": self.elder[1]}, "lines": list(lines)}

    def bounty(self):
        """This life's spawn caps: [(encounter id, spawned so far, at-once limit)]."""
        return [(ident, self.spawned[ident], self.budget[ident]) for ident in BY_ID if ident in self.budget]

    def debug_info(self):
        """Design observability: why the world looks the way it does right now."""
        key = self.game.player.chunk
        spot_ctx, self_ctx = self.spot_context(key), self.self_context("after_location")
        lead_ctx = self.lead_context(key)
        region = self.region(key)
        current = self.game.world.peek(key)
        current_spots = self._spots(current) if current is not None else ()
        rolled = {spot.encounter for spot in current_spots}
        admitted = {spot.encounter for spot in current_spots if spot.id in self.admitted}
        screened = chunk_ident(key) in self.screened_chunks
        return {"world_seed": str(self.game.world.world_seed), "life": self.life,
                "chunk": chunk_ident(key), "region": region.id if region else None,
                "generator_version": self.game.world.generator_version,
                "region_parameters": {"canopy": region.canopy, "brush": region.brush,
                                      "landmark": region.landmark} if region else None,
                "knowledge": sorted(self.knowledge), "recipes": sorted(self.recipes),
                "pressure_here": self.pressure_percents(key),
                "journal": {"disabled": sorted(self.journal_disabled), "favor": dict(self.journal_favor)},
                "states": [{"id": r["id"], "state": r["state"], "admitted": r["id"] in admitted}
                           for r in (explain(a.id, replace(spot_ctx, spawned=a.id in rolled)
                                             if a.placement == "spot" else
                                             lead_ctx if a.placement == "lead" else
                                             self.self_context("need" if a.trigger == "need" else "after_location"))
                                     for a in BY_ID.values())],
                "unlocked": sorted(self.unlocked), "mastery": dict(self.mastery),
                "spot_bucket": describe_bucket(spot_ctx),
                "spot_explanations": [explain(a.id, replace(spot_ctx, spawned=a.id in rolled,
                                                          admitted=(a.id in admitted) if screened else None))
                                      for a in BY_ID.values() if a.placement == "spot"],
                "leads": [dict(lead) for lead in self.leads],
                "lead_history": [dict(lead) for lead in self.lead_history[-12:]],
                "self_bucket": describe_bucket(self_ctx),
                "need": getattr(self._need_action(), "id", None),
                "why_not": [{"id": r["id"], "reasons": r["reasons"]}
                            for r in (explain(a.id, spot_ctx if a.placement == "spot" else
                                               lead_ctx if a.placement == "lead" else self_ctx)
                                      for a in BY_ID.values()) if not r["eligible"]],
                "windows": [{"id": i, "limit": limit, "active": self._active(i), "spawned": n}
                            for i, n, limit in self.bounty()],
                "drought": dict(self.drought), "pity_after": dict(PITY_CHUNKS),
                "screening": list(self.screen_log[-12:]), "stats": dict(self.stats),
                "recent_rolls": list(self.roll_log[-8:]),
                "currencies": {"ash": self.ash}}

    def activity(self):
        """Current activity for presentation: name/kind/progress 0..1000."""
        task = self.task
        if not task or task["type"] == "pause":
            return None
        progress = task["elapsed_ms"] * 1000 // task["duration_ms"]
        if task["type"] in PROLOGUE_MS:
            px, py = self._player()
            return {"encounter": task["type"], "name": PROLOGUE_NAMES[task["type"]], "kind": task["type"],
                    "x": px, "y": py, "progress": progress}
        if task["type"] in SELF_ACTIONS:
            px, py = self._player()
            action = BY_ID[task["type"]]
            return {"encounter": action.id, "name": action.name, "kind": action.id if action.category == "reflect"
                    else action.category, "x": px, "y": py, "progress": progress, **_style(action)}
        if task["type"] == "rest":
            if self.at_camp():
                return {"encounter": "anchor_rest", "name": "Resting at the anchor camp", "kind": "rest",
                        "x": self.anchor[0], "y": self.anchor[1], "progress": progress}
            px, py = self._player()
            return {"encounter": "campfire_rest", "name": "Resting by the campfire", "kind": "rest",
                    "x": px, "y": py, "progress": progress}
        spot = self._spot_by_id(task["spot"])
        if spot is None:
            return None
        entry = BY_ID[spot.encounter]
        gx, gy = self._global(spot.chunk, spot.x, spot.y)
        return {"encounter": entry.id, "name": entry.name, "kind": entry.kind,
                "x": gx, "y": gy, "progress": progress, **_style(entry)}

    def possession(self):
        """Possession charge and available control time for the HUD."""
        charge = self.possession_charge()
        duration = self.possess_duration_ms()
        return {"active": self.possessing, "duration_ms": duration, "cooldown_ms": POSSESS_COOLDOWN_MS,
                "charge_ms": charge, "charge_max_ms": POSSESS_COOLDOWN_MS,
                "remaining_ms": max(0, self.possess_end_ms - self.total_ms) if self.possessing else 0,
                "available_ms": 0 if self.possessing else -(-charge * duration // POSSESS_COOLDOWN_MS),
                "full_in_ms": 0 if self.possessing else POSSESS_COOLDOWN_MS - charge,
                "ready_in_ms": 0 if self.possessing or charge else 1,
                "speed_percent": POSSESS_SPEED_PERCENT}

    def mode(self):
        if self.anchor_ms is not None or self.contact:
            return "anchor"
        if self.in_prologue:
            return "prologue"
        if self.task and self.task["type"] in SELF_ACTIONS:
            return "encounter"
        if self.task and self.task["type"] == "rest":
            return "rest"
        if self.game.player.animation == "attack" or (self.goal or {}).get("kind") == "target":
            return "fight"
        if self.task and self.task["type"] == "perform":
            return "encounter"
        if self.goal and self.goal["kind"] in ("spot", "home"):
            return "travel" if self.goal["kind"] == "spot" else "home"
        return "explore"

    def vitals(self):
        return {"hunger": self.hunger // 10_000, "health": self.health // 10_000, "max": 10_000,
                "food_cooldown_ms": self.food_cooldown_ms, "food_cooldown_total_ms": FOOD_COOLDOWN_MS,
                "ash": self.ash}

    def inventory_rows(self):
        return [{"id": item, "name": ITEMS[item].name, "kind": ITEMS[item].kind,
                 "glyph": ITEMS[item].glyph, "food": ITEMS[item].food, "count": count,
                 "slot": ITEMS[item].slot, "equipped": is_equipped(self.equipped, item)
                 if ITEMS[item].kind == "gear" else False, "color": ITEMS[item].color}
                for item, count in self.inventory.items()]

    def visible_spots(self):
        """Uncompleted spots in resident chunks (fight spots appear as targets)."""
        result = []
        for chunk in self._resident():
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if spot.id in self.completed or entry.kind == "fight":
                    continue
                gx, gy = self._global(spot.chunk, spot.x, spot.y)
                result.append({"id": spot.id, "encounter": spot.encounter, "name": entry.name,
                               "kind": entry.kind, "x": gx, "y": gy, "art": entry.sprite,
                               "seal": entry.style.seal, "glint": rarity_glint(entry.rarity)})
        return result

    def camp_view(self):
        """Buildings at the anchor camp (bound or for this life) and the chest's contents."""
        return {"buildings": [{"id": b, "name": BUILDINGS[b].name, "bound": b in self.bound_buildings}
                              for b in BUILDINGS if b in self.buildings or b in self.bound_buildings],
                "chest": [{"item": i, "name": ITEMS[i].name, "count": n, "color": ITEMS[i].color}
                          for i, n in sorted(self.chest.items())],
                "at_camp": self.at_camp()}

    def opponent(self):
        """Name of the enemy the avatar is fighting (goal target), or None."""
        goal = self.goal
        if not goal or goal["kind"] != "target" or goal["id"] not in self.game.targets:
            return None
        return self.enemy_of(self.game.targets[goal["id"]]).name

    def target_kinds(self):
        """Fight-spot id behind each target (see CombatMixin.target_action)."""
        return {target_id: self.target_action(target_id).id for target_id in self.game.targets}

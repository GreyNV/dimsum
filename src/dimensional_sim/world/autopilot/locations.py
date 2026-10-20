"""Contextual choices at the anchor camp, landmarks and wilderness."""
from ..actions import reasons_against
from ..catalog import BY_ID, ITEMS


class LocationsMixin:
    def location_context(self):
        """Nearby player choices. A landmark's live actions replace the wilderness fire choice."""
        if self.anchor_ms is not None or self.contact or self.in_prologue:
            return None
        busy = self.task is not None and self.task["type"] not in ("pause", "rest")
        if self.at_camp():
            context = self.self_context()
            actions = []
            for action in BY_ID.values():
                if action.placement != "self" or action.category not in ("craft", "build"):
                    continue
                reasons = reasons_against(action, context)
                if any("unknown:" in reason or "locked:" in reason for reason in reasons):
                    continue
                actions.append({"id": action.id, "name": action.name, "description": action.description,
                                "cost": [(ITEMS[item].name, count) for item, count in action.cost],
                                "reasons": (["busy"] if busy else []) + reasons})
            return {"kind": "anchor", "name": "Anchor camp", "actions": actions,
                    "visit": True}
        player = self.game.player
        site = self.game.world.site_for(player.chunk)
        if site is not None and site.contains(player.x, player.y):
            px, py = self._player()
            chunk = self.game.current_chunk()
            actions = []
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if entry.site != site.id or spot.id in self.completed or entry.category == "fight":
                    continue
                sx, sy = self._global(spot.chunk, spot.x, spot.y)
                distance = abs(px - sx) + abs(py - sy)
                actions.append({"id": spot.id, "name": entry.name,
                                "description": entry.description, "cost": [],
                                "reasons": (["busy"] if busy else [])
                                + ([f"move {distance - 1} steps closer"] if distance > 1 else [])})
            if actions:
                return {"kind": "landmark", "name": site.site.name,
                        "actions": actions, "visit": False}
        fire = next(action for action in BY_ID.values() if action.places == "campfire")
        reasons = reasons_against(fire, self.self_context())
        if busy:
            reasons.append("busy")
        return {"kind": "wild", "name": "Here", "visit": False,
                "actions": [{"id": fire.id, "name": fire.name, "description": fire.description,
                             "cost": [(ITEMS[item].name, count) for item, count in fire.cost],
                             "reasons": reasons}]}

    def use_location_action(self, ident):
        context = self.location_context()
        if context is None:
            raise ValueError("no location action now")
        if ident == "visit_anchor":
            if context["kind"] != "anchor":
                raise ValueError("visit the anchor only at its camp")
            if self.possessing:
                self._end_possession()
            self.contact = True
            return
        row = next((row for row in context["actions"] if row["id"] == ident), None)
        if row is None or row["reasons"]:
            raise ValueError("location action unavailable")
        if context["kind"] == "landmark":
            spot = self._spot_by_id(ident)
            self.goal = {"kind": "spot", "id": spot.id, "x": self._player()[0], "y": self._player()[1]}
            self._start_perform(spot.id, BY_ID[spot.encounter])
        else:
            self.goal = None
            if self.task and self.task["type"] in ("pause", "rest"):
                self.task = None
            self._start_self(BY_ID[ident])

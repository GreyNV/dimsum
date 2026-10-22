"""The main story (docs/design/STORY.md).

Story progress is knowledge: the current step is the first catalog STORY step whose id
is not known yet, and knowledge survives every death, so a death never undoes the story.
Each life the current step is placed (a forced spot, outside the spawn windows) in the first
chunk the avatar stands in inside the step's rings, once its requirements hold. If the avatar
walks away and the placed chunk unloads, a later chunk may hold it again (at most
STORY_PLACEMENTS_PER_LIFE times), so the step can never be stranded out of reach.
"""
from dataclasses import replace

from ..actions import bucket_reasons
from ..catalog import BY_ID, STORY, STORY_BY_ACTION, STORY_CHAPTERS, STORY_NEXT, story_rings
from ..encounters import forced_spot
from ..models import chunk_ident

STORY_PLACEMENTS_PER_LIFE = 3


class StoryMixin:
    # ----- state -----------------------------------------------------------------
    def story_step(self):
        """The current StoryStepDef, or None once every written step is done."""
        return next((step for step in STORY if step.id not in self.knowledge), None)

    def story_spent(self, action):
        """A story place whose step is already done (a second placement left behind): hidden."""
        step = STORY_BY_ACTION.get(action.id)
        return step is not None and step.id in self.knowledge

    def step_rings(self, step):
        return story_rings(step)

    # ----- placement -------------------------------------------------------------------
    def _story_spots(self, step):
        """(chunk id, spot index) of this life's placements of `step`."""
        found = []
        for chunk_id, extra in self.forced.items():
            found += [(chunk_id, index) for index, encounter in enumerate(extra) if encounter == step.action]
        return found

    def story_context(self, key):
        return replace(self.spot_context(key), placement="story")

    def story_reasons(self, step, key=None):
        """Why the step cannot be placed in chunk `key` (or anywhere now, without a key)."""
        action = BY_ID[step.action]
        ctx = self.story_context(key if key is not None else self.game.player.chunk)
        reasons = [r for r in bucket_reasons(action, ctx) if not r.startswith(("biome ", "region "))]
        if key is not None:
            low, high = self.step_rings(step)
            if not low <= self.ring(key) <= high:
                reasons.append(f"ring {self.ring(key)} outside {low}-{high}")
        return reasons

    def _place_story(self, chunk):
        """Place the current story step in `chunk` if it belongs here (deterministic)."""
        step = self.story_step()
        if step is None or self.anchor_ms is not None or self.in_prologue:
            return None
        key = chunk.key
        if key == self._camp_chunk():
            return None
        low, high = self.step_rings(step)
        if not low <= self.ring(key) <= high:
            return None
        placed = self._story_spots(step)
        resident = {chunk_ident(c.key) for c in self._resident()}
        if any(chunk_id in resident for chunk_id, _ in placed) or len(placed) >= STORY_PLACEMENTS_PER_LIFE:
            return None
        if self.story_reasons(step, key):
            return None
        chunk_id = chunk_ident(key)
        taken = [(s.x, s.y) for s in self._spots(chunk)]
        index = len(self.forced.get(chunk_id, ()))
        spot = forced_spot(chunk, step.action, index, taken=taken)
        if spot is None:
            return None
        self.forced.setdefault(chunk_id, []).append(step.action)
        self.admitted[spot.id] = step.action   # outside every spawn window
        self._note(chunk_id, spot.id, step.action, "story")
        return spot

    def _story_done(self, action):
        """Log a finished step's lore (its knowledge was taught by its outcome)."""
        step = STORY_BY_ACTION.get(action.id)
        if step is None:
            return
        for line in step.lore:
            self._entry("story", line, encounter=action.id)
        if self.story_step() is None:
            self._entry("story", STORY_NEXT, encounter=action.id)

    # ----- presentation -------------------------------------------------------------------
    def story_view(self):
        """HUD and Story page: the current objective, why it waits, and the steps done."""
        step = self.story_step()
        done = [{"id": s.id, "action": s.action, "chapter": s.chapter, "name": BY_ID[s.action].name,
                 "lore": list(s.lore)}
                for s in STORY if s.id in self.knowledge]
        current = None
        if step is not None:
            low, high = self.step_rings(step)
            waits = self.story_reasons(step)
            frontier = self.frontier()
            if frontier < low:
                waits.append(f"you can safely go as far as ring {frontier}")
            live = any(spot.encounter == step.action and spot.id not in self.completed
                       for chunk in self._resident() for spot in self._live(chunk))
            current = {"id": step.id, "chapter": step.chapter, "chapter_name": STORY_CHAPTERS[step.chapter],
                       "objective": step.objective, "name": BY_ID[step.action].name,
                       "rings": [low, high], "waits": [_plain(r) for r in waits], "here": live}
        return {"current": current, "done": done, "next": STORY_NEXT if step is None else None}


def _plain(reason):
    """Engine reasons in the player's words."""
    if reason.startswith("needs willpower level") or reason.startswith("needs "):
        reason = reason.replace("level", "").replace("  ", " ")
        reason = reason.replace("needs willpower", "needs Willpower").replace("(have", "(now")
    if reason.startswith("locked: needs unlock"):
        reason = "opens with " + reason.split("'")[1]
    return reason

"""Punch damage, boar danger by ring, the exploration frontier and boar pursuit."""
from ..catalog import BY_ID
from ..equipment import is_equipped
from ..models import DELTAS, DIRECTIONS, ChunkKey
from ..progression import combined_level
from ..runtime import InputCommand
from ..tuning import (COMFORT_DAMAGE_PERCENT, IRON_SKIN_HIT_PERCENT, STAFF_PUNCH_BONUS, UNARMED_REACH,
                      WRAP_HIT_PERCENT)
from .constants import (BOAR_AGGRO_RADIUS, BOAR_HIT, BOAR_PATH_LIMIT, CAMP_SAFE_RADIUS, DANGER_RING_CAP, EAT_AT,
                        MONSTER_STEP_MS, VITAL_MAX, ceil_div)


class CombatMixin:
    def ring(self, key):
        """Danger ring: Chebyshev chunk distance from the anchor chunk."""
        return max(abs(key.x), abs(key.y))

    def punch_damage(self):
        """1 + softcapped (regular + dimensional) Strength levels / 5."""
        level = combined_level(self.regular["strength"], self.dimensional["strength"])
        return 1 + int(level) // 5 + (STAFF_PUNCH_BONUS if is_equipped(self.equipped, "walking_staff") else 0)

    def boar_hit(self, key):
        ring = min(self.ring(key), DANGER_RING_CAP)
        hit = BOAR_HIT * 3 ** ring // 2 ** ring * 1000 // self.speed("endurance")
        if is_equipped(self.equipped, "hide_wrap"):
            hit = hit * WRAP_HIT_PERCENT // 100
        if self.boon == "iron_skin":
            hit = hit * IRON_SKIN_HIT_PERCENT // 100
        return hit

    def fight_damage(self, ring):
        """Health the avatar expects to lose beating one boar in `ring` (micro-points)."""
        hp = BY_ID["bramble_boar"].hp + min(ring, DANGER_RING_CAP)
        punches = ceil_div(hp, self.punch_damage())
        return self.boar_hit(ChunkKey(self.dimension, ring, 0)) * (punches - 1)

    def frontier(self):
        """Deepest ring the auto-pilot is willing to explore: one boar fight there
        must cost at most COMFORT_DAMAGE_PERCENT of full health. Stronger lives
        (XP, gear, boons) push the frontier outward; hunger pushes one ring further."""
        ring = 1
        while ring < DANGER_RING_CAP and self.fight_damage(ring + 1) * 100 <= VITAL_MAX * COMFORT_DAMAGE_PERCENT:
            ring += 1
        if self.hunger <= EAT_AT and not self._has_food():
            ring += 1
        return ring

    def _hostile(self, target):
        """A live enemy this life admitted, in the avatar's dimension."""
        return target.hp > 0 and target.id in self.admitted and target.chunk.dimension == self.dimension

    def unarmed_target(self):
        """The nearest admitted enemy within the current unarmed hitbox reach."""
        px, py = self._player()
        candidates = []
        for target in self.game.targets.values():
            if not self._hostile(target):
                continue
            tx, ty = self._global(target.chunk, target.x, target.y)
            distance = abs(tx - px) + abs(ty - py)
            if 0 < distance <= UNARMED_REACH:
                candidates.append((distance, target.id, tx, ty))
        return min(candidates) if candidates else None

    def _manual_combat_command(self, command, auto_attack):
        if not auto_attack or command.move or command.attack or self.task:
            return command
        target = self.unarmed_target()
        if target is None:
            return command
        _, _, tx, ty = target
        px, py = self._player()
        direction = next(d for d, delta in DELTAS.items() if delta == (tx - px, ty - py))
        # Release the attack edge during the animation; a later tick can punch again.
        return InputCommand(attack=self.game.player.animation != "attack" and not self.game.attack_held,
                            face=direction)

    def _boar_strikes_back(self):
        goal = self.goal
        target = self.game.targets.get(goal["id"]) if goal and goal["kind"] == "target" else None
        if target is not None and target.hp > 0:
            self._boar_bites(target)

    def _near_camp(self, gx, gy):
        """Boars never chase into the anchor camp: it is where a hurt avatar recovers."""
        return self.anchor is not None and abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]) <= CAMP_SAFE_RADIUS

    def _boar_bites(self, target):
        """One boar attack on the avatar (its counter feeds the client's lunge animation)."""
        self.health = max(0, self.health - self.boar_hit(target.chunk))
        self.strikes[target.id] = self.strikes.get(target.id, 0) + 1
        if self.health == 0:
            self.cause = "boar"

    def _steps_to(self, target, px, py):
        tx, ty = self._global(target.chunk, target.x, target.y)
        return abs(tx - px) + abs(ty - py)

    def _pursue(self):
        """Live boars within BOAR_AGGRO_RADIUS charge the avatar one step per MONSTER_STEP_MS.
        Reaching it, a boar bites first and interrupts whatever the avatar was doing."""
        if self.monster_ms < MONSTER_STEP_MS:
            return
        self.monster_ms -= MONSTER_STEP_MS
        if self.in_prologue:
            return
        px, py = self._player()
        if self._near_camp(px, py) or not any(   # cheap check first: most steps nothing is close
                self._hostile(t) and self._steps_to(t, px, py) <= BOAR_AGGRO_RADIUS
                for t in self.game.targets.values()):
            return
        grid = self._grid()
        w, h = self._dims()
        field = self._field({(px, py)}, limit=BOAR_PATH_LIMIT)
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if not self._hostile(target):
                continue
            tx, ty = self._global(target.chunk, target.x, target.y)
            distance = abs(tx - px) + abs(ty - py)
            if distance > BOAR_AGGRO_RADIUS or self._near_camp(px, py) or self._near_camp(tx, ty):
                continue
            if distance > 1:
                choices = []
                blocked = self._blocked()
                for direction in DIRECTIONS:
                    dx, dy = DELTAS[direction]
                    nx, ny = tx + dx, ty + dy
                    key = ChunkKey(self.dimension, nx // w, ny // h)
                    if (nx, ny) != (px, py) and key in self.game.initialized_chunks and \
                            self._can_move(grid, blocked, tx, ty, direction) and (nx, ny) in field:
                        choices.append((field[nx, ny], direction, nx, ny, key))
                if choices:
                    _, _, tx, ty, key = min(choices)
                    target.chunk, target.x, target.y = key, tx % w, ty % h
                    self._field_cache.clear()
                    distance = abs(tx - px) + abs(ty - py)
            # A boar that catches a fleeing avatar gores it in passing but does not stop it;
            # retreat is safer than a losing fight, never free.
            if distance == 1 and (self.goal or {}).get("kind") == "home":
                self._boar_bites(target)
                if self.health == 0:
                    break
                continue
            # A second boar waits its turn.
            if distance == 1 and (self.goal or {}).get("kind") != "target":
                self.task = None
                self._boar_bites(target)
                if self.health > self.fight_damage(self.ring(target.chunk)):
                    self.goal = {"kind": "target", "id": target.id, "x": tx, "y": ty}
                    self._entry("ambush", "A bramble boar charges and gores you - fists up!")
                else:   # this fight would kill: outrun it to the camp (boars are slower)
                    self.goal = self._home_goal()
                    self._entry("ambush", "A bramble boar gores you - too hurt to fight, you run for the camp!")
                break

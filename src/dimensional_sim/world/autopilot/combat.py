"""Combat against catalog enemies: punch damage, danger by biome and ring, the
exploration frontier and enemy pursuit. No enemy or gear is named here:
EnemyDef/BiomeDef (catalog) and effects.py supply every number."""
from .. import effects
from ..catalog import ASSET_ENEMY_ACTION, ATTACKS, BIOMES, BY_ID, DEFAULT_ATTACK, ENEMIES, ITEMS
from ..models import DELTAS, DIRECTIONS, ChunkKey
from ..progression import combined_level
from ..runtime import InputCommand
from ..tuning import COMFORT_DAMAGE_PERCENT, STRENGTH_LEVELS_PER_PUNCH
from .constants import CAMP_SAFE_RADIUS, EAT_AT, MONSTER_STEP_MS, POINT, VITAL_MAX, ceil_div

# Chasing enemies path-find this far (steps) around obstacles.
PURSUIT_PATH_LIMIT = 2 * max(e.aggro_radius for e in ENEMIES.values()) + 2
FLEE_UNLOAD_MS = 20_000   # a frightened enemy that cannot get out of range is gone after this long


class CombatMixin:
    def ring(self, key):
        """Danger ring: Chebyshev chunk distance from the anchor chunk."""
        return max(abs(key.x), abs(key.y))

    def biome(self, key):
        """BiomeDef of a chunk key (pure: the world's pinned biome layout)."""
        return BIOMES[self.game.world.biome_for(key)]

    def punch_damage(self):
        """1 + softcapped (regular + dimensional) Strength levels / STRENGTH_LEVELS_PER_PUNCH,
        plus gear."""
        level = combined_level(self.regular["strength"], self.dimensional["strength"])
        return 1 + int(level) // STRENGTH_LEVELS_PER_PUNCH + effects.total(self.equipped, "punch_damage")

    def target_action(self, target_id):
        """The admitted fight action behind a target, even after its origin chunk is evicted."""
        return BY_ID[self.admitted.get(target_id, ASSET_ENEMY_ACTION)]

    def enemy_of(self, target):
        return ENEMIES[self.target_action(target.id).enemy]

    def enemy_hit(self, key, enemy):
        """Health one bite of `enemy` takes in chunk `key`: biome danger by ring, softened by
        Endurance and by enemy_hit_percent effects."""
        biome = self.biome(key)
        if enemy.life_depth_hit_percent:
            ring = min(self.depth, biome.ring_cap)
            hit = enemy.hit * POINT * (100 + enemy.life_depth_hit_percent * ring) // 100
        else:
            ring = min(self.ring(key), biome.ring_cap)
            hit = enemy.hit * POINT * biome.danger_num ** ring // biome.danger_den ** ring
        hit = hit * 1000 // self.speed("endurance")
        return effects.scale(hit, self.equipped, "enemy_hit_percent")

    def enemy_hp(self, action, key):
        """Hit points of the fight spot `action` placed in chunk `key`."""
        biome = self.biome(key)
        enemy = ENEMIES[action.enemy]
        if enemy.life_depth_hp_per_ring:
            return action.hp + enemy.life_depth_hp_per_ring * min(self.depth, biome.ring_cap)
        return action.hp + biome.hp_per_ring * min(self.ring(key), biome.ring_cap)

    def fight_damage(self, ring, action):
        """Health the avatar expects to lose beating one `action` enemy in `ring` (micro-points).
        Reach is not counted: a first blow from range is a bonus in the fight, not something
        the frontier plans on (measured: counting it sent lives deeper and shortened them)."""
        key = ChunkKey(self.dimension, ring, 0)
        punches = ceil_div(self.enemy_hp(action, key), self.punch_damage())
        enemy = ENEMIES[action.enemy]
        if enemy.drains != "health":
            return 0   # costs hunger, not health
        return self.enemy_hit(key, enemy) * max(0, punches - 1)

    def attack(self):
        """The AttackDef in use: the equipped weapon's, else bare fists."""
        weapon = self.equipped.get("weapon")
        return ATTACKS[ITEMS[weapon].attack if weapon else DEFAULT_ATTACK]

    def _arm(self):
        """Hand the runtime this life's blow: damage and reach (derived, never saved)."""
        self.game.attack_damage = self.punch_damage()
        self.game.attack_reach = self.attack().reach

    def _clear_line(self, px, py, tx, ty, live):
        """A straight cardinal line from the avatar to (tx, ty) with no wall and no other
        enemy in between (the runtime stops a blow at the first of either)."""
        dx, dy = (tx > px) - (tx < px), (ty > py) - (ty < py)
        x, y = px + dx, py + dy
        while (x, y) != (tx, ty):
            if (x, y) in live or self.game.wall_at(x, y):
                return False
            x, y = x + dx, y + dy
        return True

    def threats(self):
        """Fight spots that can appear in the avatar's current biome (a chain's danger lead
        reuses one of these enemies, so it adds no threat of its own)."""
        biome = self.biome(self.game.player.chunk).id
        return [a for a in BY_ID.values() if a.enemy is not None and a.placement != "lead" and biome in a.biomes]

    def frontier(self):
        """Deepest ring the auto-pilot is willing to explore: one fight with the worst
        threat there must cost at most COMFORT_DAMAGE_PERCENT of full health. Stronger lives
        (XP, gear) push the frontier outward; hunger pushes one ring further."""
        threats, cap = self.threats(), self.biome(self.game.player.chunk).ring_cap
        ring = 1
        while ring < cap and threats and max(self.fight_damage(ring + 1, a) for a in threats) * 100 \
                <= VITAL_MAX * COMFORT_DAMAGE_PERCENT:
            ring += 1
        if self.hunger <= EAT_AT and not self._has_food():
            ring += 1
        return ring

    def _hostile(self, target):
        """A live enemy this life admitted, in the avatar's dimension."""
        return target.hp > 0 and target.id in self.admitted and target.chunk.dimension == self.dimension

    def unarmed_target(self):
        """The nearest admitted enemy a blow can reach now: in a straight cardinal line
        within the weapon's reach, nothing in between (name kept from fists-only days)."""
        px, py = self._player()
        reach = self.attack().reach
        live = {}
        for target in self.game.targets.values():
            if self._hostile(target):
                live[self._global(target.chunk, target.x, target.y)] = target
        candidates = []
        for (tx, ty), target in live.items():
            distance = abs(tx - px) + abs(ty - py)
            if (tx == px or ty == py) and 0 < distance <= reach and self._clear_line(px, py, tx, ty, live):
                candidates.append((distance, target.id, tx, ty))
        return min(candidates) if candidates else None

    strike_target = unarmed_target

    def strike_cells(self, gx, gy):
        """Cells a blow can reach the enemy at (gx, gy) from (straight lines, nothing in between)."""
        reach = self.attack().reach
        cells = set()
        for dx, dy in DELTAS.values():
            for step in range(1, reach + 1):
                cell = (gx + dx * step, gy + dy * step)
                if step > 1 and self.game.wall_at(gx + dx * (step - 1), gy + dy * (step - 1)):
                    break
                cells.add(cell)
        return cells

    def _manual_combat_command(self, command, auto_attack):
        if not auto_attack or command.move or command.attack or self.task:
            return command
        target = self.unarmed_target()
        if target is None:
            return command
        _, _, tx, ty = target
        px, py = self._player()
        toward = ((tx > px) - (tx < px), (ty > py) - (ty < py))
        direction = next(d for d, delta in DELTAS.items() if delta == toward)
        # Release the attack edge during the animation; a later tick can punch again.
        return InputCommand(attack=self.game.player.animation != "attack" and not self.game.attack_held,
                            face=direction)

    def _enemy_strikes_back(self):
        goal = self.goal
        target = self.game.targets.get(goal["id"]) if goal and goal["kind"] == "target" else None
        if target is not None and target.hp > 0:
            self._enemy_bites(target)

    def _near_camp(self, gx, gy):
        """Enemies never chase into the anchor camp: it is where a hurt avatar recovers."""
        return self.anchor is not None and abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]) <= CAMP_SAFE_RADIUS

    def _enemy_bites(self, target):
        """One enemy attack on the avatar (its counter feeds the client's lunge animation)."""
        enemy = self.enemy_of(target)
        self.strikes[target.id] = self.strikes.get(target.id, 0) + 1
        if enemy.drains == "hunger":   # it feeds: hunger runs down (starving is the vitals' job)
            self.hunger = max(0, self.hunger - self.enemy_hit(target.chunk, enemy))
            return
        self.health = max(0, self.health - self.enemy_hit(target.chunk, enemy))
        if self.health == 0:
            self.cause = enemy.cause

    def _steps_to(self, target, px, py):
        tx, ty = self._global(target.chunk, target.x, target.y)
        return abs(tx - px) + abs(ty - py)

    def _steps_this_tick(self, enemy):
        """Chasing steps this monster tick: faster enemies (step_ms below MONSTER_STEP_MS)
        sometimes take two. A pure function of the clock, so any time slicing agrees."""
        tick = self.total_ms // MONSTER_STEP_MS
        return (tick + 1) * MONSTER_STEP_MS // enemy.step_ms - tick * MONSTER_STEP_MS // enemy.step_ms

    def _pursue(self):
        """Enemies hunt the avatar one step per MONSTER_STEP_MS (docs/design/PURSUIT.md).

        An enemy that notices the avatar within its aggro radius becomes a hunter:
        it chases wherever the avatar goes - no aggro limit,
        no territory - and cannot be outrun, only left behind beyond the loaded area around
        the avatar (its chunk out of the resident 3x3), where it is unloaded. If the avatar
        reaches the anchor camp or a campfire, fire-fearing hunters flee until they
        is out of range and unloaded (or, cornered, after FLEE_UNLOAD_MS it is gone anyway).
        Reaching the avatar, a hunter bites first and interrupts whatever it was doing."""
        if self.monster_ms < MONSTER_STEP_MS:
            return
        self.monster_ms -= MONSTER_STEP_MS
        if self.in_prologue:
            return
        self._unload_far_enemies()
        px, py = self._player()
        safe = self.in_firelight(px, py)
        quiet = not self.hunting and not any(
            self._hostile(t) and self._steps_to(t, px, py) <= self.enemy_of(t).aggro_radius
            and not (safe and self.enemy_of(t).fears_fire)
            for t in self.game.targets.values())
        if quiet:   # cheap check first: most steps nothing is close and nothing hunts
            return
        grid = self._grid()
        w, h = self._dims()
        field = self._field({(px, py)}, limit=PURSUIT_PATH_LIMIT)
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if not self._hostile(target):
                continue
            enemy = self.enemy_of(target)
            tx, ty = self._global(target.chunk, target.x, target.y)
            distance = abs(tx - px) + abs(ty - py)
            mode = self.hunting.get(target.id, {}).get("mode")
            if mode is None:
                if (safe and enemy.fears_fire) or distance > enemy.aggro_radius \
                        or (enemy.fears_fire and self.in_firelight(tx, ty)):
                    continue
                mode = "hunt"
                self.hunting[target.id] = {"mode": "hunt", "since": self.total_ms}
            if mode == "hunt" and safe and enemy.fears_fire:
                mode = "flee"
                self.hunting[target.id] = {"mode": "flee", "since": self.total_ms}
                self._entry("lore", f"The {enemy.name.lower()} shies from the "
                            f"{'camp' if self._near_camp(px, py) else 'fire'} and slinks away.")
            if mode == "flee":
                if self.total_ms - self.hunting[target.id]["since"] >= FLEE_UNLOAD_MS:
                    self._unload(target)
                    continue
                for _ in range(self._steps_this_tick(enemy)):
                    moved = self._enemy_step(target, grid, w, h, px, py, away=True)
                    if moved is None:
                        break
                continue
            for _ in range(self._steps_this_tick(enemy)):
                if distance <= 1:
                    break
                moved = self._enemy_step(target, grid, w, h, px, py, field=field)
                if moved is None:
                    break
                tx, ty = moved
                distance = abs(tx - px) + abs(ty - py)
            # An enemy that catches a fleeing avatar bites it in passing but does not stop it;
            # retreat is safer than a losing fight, never free.
            if distance == 1 and (self.goal or {}).get("kind") == "home":
                self._enemy_bites(target)
                if self.health == 0:
                    break
                continue
            # A second enemy waits its turn.
            if distance == 1 and (self.goal or {}).get("kind") != "target":
                self.task = None
                self._enemy_bites(target)
                name = enemy.name.lower()
                if self.health > self.fight_damage(self.ring(target.chunk), self.target_action(target.id)):
                    self.goal = {"kind": "target", "id": target.id, "x": tx, "y": ty}
                    self._entry("ambush", f"A {name} attacks you!")
                else:   # this fight would kill: retreat and seek recovery
                    self.goal = self._home_goal()
                    self._entry("ambush", f"A {name} attacks you - too hurt to fight, you retreat!")
                break

    def _enemy_step(self, target, grid, w, h, px, py, *, field=None, away=False):
        """One step of a hunter toward the avatar (down the distance field when it is near,
        otherwise any step that closes in) or of a frightened enemy away from it. Fire-fearing
        enemies avoid the camp and campfire; none step onto the avatar, only over loaded ground.
        Returns the new global cell, or None when no step helps."""
        tx, ty = self._global(target.chunk, target.x, target.y)
        here = abs(tx - px) + abs(ty - py)
        fears_fire = self.enemy_of(target).fears_fire
        blocked = self._blocked()
        choices = []
        for direction in DIRECTIONS:
            dx, dy = DELTAS[direction]
            nx, ny = tx + dx, ty + dy
            key = ChunkKey(self.dimension, nx // w, ny // h)
            if (nx, ny) == (px, py) or key not in self.game.initialized_chunks \
                    or not self._can_move(grid, blocked, tx, ty, direction) \
                    or (fears_fire and self.in_firelight(nx, ny)):
                continue
            there = abs(nx - px) + abs(ny - py)
            if away:
                if there > here:
                    choices.append((-there, direction, nx, ny, key))
            elif field is not None and (tx, ty) in field and (nx, ny) in field:
                choices.append((field[nx, ny], direction, nx, ny, key))
            elif there < here and ((tx, ty) not in (field or {})):
                choices.append((there, direction, nx, ny, key))
        if not choices:
            return None
        _, _, nx, ny, key = min(choices)
        target.chunk, target.x, target.y = key, nx % w, ny % h
        self._field_cache.clear()
        return nx, ny

    def _unload_far_enemies(self):
        """Hunting or fleeing enemies whose chunk left the loaded area around the avatar are
        unloaded: a rolled spot comes back at home when its chunk is entered again; a lead
        (a wolf) is gone."""
        resident = {chunk.key for chunk in self._resident()}
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if target.id in self.hunting and (target.chunk not in resident or target.hp == 0):
                self._unload(target)
        for ident in [i for i in self.hunting if i not in self.game.targets]:
            del self.hunting[ident]

    def _unload(self, target):
        self.hunting.pop(target.id, None)
        if target.hp == 0:
            return
        del self.game.targets[target.id]
        self._field_cache.clear()
        gone = [lead for lead in self.leads if lead["id"] == target.id]
        if gone:
            self.leads = [lead for lead in self.leads if lead["id"] != target.id]
            self._record_leads(gone, "expired")
        if (self.goal or {}).get("id") == target.id:
            self.goal = None

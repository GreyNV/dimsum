"""Combat against catalog enemies: punch damage, fixed enemy numbers per land, starred
enemies and company by ring, the exploration frontier and enemy pursuit. No enemy or gear is
named here: EnemyDef/BiomeDef/FightTier (catalog) and effects.py supply every number."""
from .. import effects
from ..catalog import ASSET_ENEMY_ACTION, ATTACKS, BIOMES, BY_ID, DEFAULT_ATTACK, ENEMIES, FIGHT_PATTERNS, FIGHT_TIERS, ITEMS
from ..models import DELTAS, DIRECTIONS, ChunkKey
from ..progression import combined_level, scaled_ms
from ..runtime import InputCommand, Target
from .navigation import MOVES_8
from ..seeds import derive_seed
from ..tuning import (COMFORT_DAMAGE_PERCENT, DODGE_BASE_PERCENT, DODGE_MAX_PERCENT, DODGE_PERCENT_PER_LEVEL,
                      STRENGTH_LEVELS_PER_PUNCH)
from .constants import CAMP_SAFE_RADIUS, EAT_AT, MONSTER_STEP_MS, PAUSE_BETWEEN_PUNCHES_MS, POINT, VITAL_MAX, ceil_div

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

    def enemy_hit(self, key, enemy, tier=None):
        """Health one bite of `enemy` takes in chunk `key`: fixed in its land (the biome's
        hit_percent), raised by its FightTier, softened by Endurance and enemy_hit_percent effects."""
        tier = tier or FIGHT_TIERS["common"]
        hit = enemy.hit * POINT * self.biome(key).hit_percent // 100 * tier.hit_percent // 100
        hit = hit * 1000 // self.speed("endurance")
        return effects.scale(hit, self.equipped, "enemy_hit_percent")

    def enemy_hp(self, action, key, tier=None):
        """Hit points of the fight spot `action` in chunk `key`: fixed in its land, raised by its tier."""
        tier = tier or FIGHT_TIERS["common"]
        return max(1, action.hp * self.biome(key).hp_percent // 100 * tier.hp_percent // 100)

    @staticmethod
    def companion_of(ident):
        """The spot id a companion ('<spot>.c1', '.c2') belongs to, or None for anything else."""
        head, _, tail = ident.rpartition(".c")
        return head if head and tail.isdecimal() else None

    @staticmethod
    def _spot_chunk(ident):
        """The chunk a spot or lead id was placed in (companions: their spot's), or None."""
        parts = (CombatMixin.companion_of(ident) or ident).split(":")
        if len(parts) < 4 or parts[0] not in ("enc", "lead"):
            return None
        try:
            return ChunkKey(parts[1], int(parts[2]), int(parts[3]))
        except ValueError:
            return None

    def _fight_odds(self, ident):
        key = self._spot_chunk(ident)
        return None if key is None else self.biome(key).odds_at(self.ring(key))

    def tier_of(self, ident):
        """The FightTier a fight rolled: pure in the world seed, the spot id and its ring, so it
        never needs saving. Company and enemies of no spot are always common."""
        odds = None if self.companion_of(ident) else self._fight_odds(ident)
        if odds is None:
            return FIGHT_TIERS["common"]
        roll = derive_seed(self.game.world.world_seed, "fight-tier-v1", ident) % 100
        return FIGHT_TIERS["elder"] if roll < odds.elder else FIGHT_TIERS["star"] if roll < odds.elder + odds.star \
            else FIGHT_TIERS["common"]

    def company(self, ident):
        """How many common companions a fight spot brings (0-2), pure like tier_of: one at the
        ring's extra chance, a second at half of it."""
        odds = None if self.companion_of(ident) else self._fight_odds(ident)
        if odds is None or not odds.extra:
            return 0
        first = derive_seed(self.game.world.world_seed, "fight-company-v1", ident, 1) % 100 < odds.extra
        second = first and derive_seed(self.game.world.world_seed, "fight-company-v1", ident, 2) % 200 < odds.extra
        return int(first) + int(second)

    def _place_company(self, spot, entry):
        """Companions stand on the nearest open cells around their spot (ids '<spot>.c1', '.c2');
        each is a common enemy of the same fight, admitted under it and rewarded like it."""
        chunk = self.game.world.peek(spot.chunk)
        if chunk is None:
            return
        asset = chunk.asset
        taken = {(t.x, t.y) for t in self.game.targets.values() if t.chunk == spot.chunk} | \
                {(s.x, s.y) for s in self._spots(chunk)}
        cells = [(spot.x + dx, spot.y + dy) for r in (1, 2) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
                 if max(abs(dx), abs(dy)) == r]
        for k in range(1, self.company(spot.id) + 1):
            ident = f"{spot.id}.c{k}"
            if ident in self.game.targets or ident in self.completed:
                continue
            free = next(((x, y) for x, y in cells if 0 <= x < asset.width and 0 <= y < asset.height
                         and not asset.collision[y][x] and (x, y) not in taken), None)
            if free is None:
                return
            taken.add(free)
            self.admitted[ident] = entry.id
            self.game.targets[ident] = Target(ident, spot.chunk, *free, self.enemy_hp(entry, spot.chunk))

    def punch_cycle_ms(self):
        """One blow and the pause after it (the attack clip at its rate, then a Strength-scaled pause)."""
        clip = ceil_div(self.game.animations["attack"].duration_ms * 100, self.game.attack_rate_percent)
        return clip + scaled_ms(PAUSE_BETWEEN_PUNCHES_MS, self.speed("strength"))

    def _strikes_taken(self, enemy, hp):
        """How many strikes `enemy` gets in before `hp` worth of blows bring it down: the first
        after its wind-up, then one each pattern cycle (wind-up, strike, recovery, backing off)."""
        pattern = FIGHT_PATTERNS[enemy.pattern]
        # blows take half as long again as the bare punch cycle: a hunter backs off and must be followed
        fight_ms = ceil_div(hp, self.punch_damage()) * self.punch_cycle_ms() * 3 // 2
        if fight_ms <= pattern.windup_ms:
            return 0
        # a charger strikes again from where it backed off to; a biter must walk back in first
        back = pattern.retreat * enemy.step_ms * (1 if pattern.strike == "charge" else 2)
        cycle = pattern.windup_ms + MONSTER_STEP_MS + pattern.recover_ms + back
        return 1 + (fight_ms - pattern.windup_ms) // cycle

    def dodge_percent(self):
        """The autopilot's chance to step out of a strike it sees coming: Agility and Perception
        together (softcapped levels), DODGE_BASE_PERCENT + DODGE_PERCENT_PER_LEVEL a level, at most
        DODGE_MAX_PERCENT. Possession dodges by hand."""
        skill = combined_level(self.regular["agility"], self.dimensional["agility"]) + \
            combined_level(self.regular["perception"], self.dimensional["perception"])
        return min(DODGE_MAX_PERCENT, DODGE_BASE_PERCENT + int(skill * DODGE_PERCENT_PER_LEVEL))

    def fight_damage(self, ring, action, tier=None):
        """Health the avatar expects to lose beating `action` in `ring` (micro-points). With a
        `tier`, one enemy of that tier; without, the ring's mix: tier odds and expected company.
        Reach is not counted: a first blow from range is a bonus in the fight, not something
        the frontier plans on (measured: counting it sent lives deeper and shortened them)."""
        key = ChunkKey(self.dimension, ring, 0)
        enemy = ENEMIES[action.enemy]
        if enemy.drains != "health":
            return 0   # costs hunger, not health

        def one(t):
            return self._strikes_taken(enemy, self.enemy_hp(action, key, t)) * self.enemy_hit(key, enemy, t) \
                * (100 - self.dodge_percent()) // 100
        if tier is not None:
            return one(tier)
        odds = self.biome(key).odds_at(ring)
        if odds is None:
            return one(FIGHT_TIERS["common"])
        common = 100 - odds.star - odds.elder
        mixed = (one(FIGHT_TIERS["common"]) * common + one(FIGHT_TIERS["star"]) * odds.star
                 + one(FIGHT_TIERS["elder"]) * odds.elder) // 100
        company = odds.extra + odds.extra // 2 * odds.extra // 100   # expected companions, percent
        return mixed + one(FIGHT_TIERS["common"]) * company // 100

    def attack(self):
        """The AttackDef in use: the equipped weapon's, else bare fists."""
        weapon = self.equipped.get("weapon")
        return ATTACKS[ITEMS[weapon].attack if weapon else DEFAULT_ATTACK]

    def _arm(self):
        """Hand the runtime this life's blow: damage and reach (derived, never saved)."""
        self.game.attack_damage = self.punch_damage()
        self.game.attack_reach = self.attack().reach

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

    def in_reach(self, px, py, tx, ty):
        """A blow from (px, py) reaches (tx, ty): inside the circle of the weapon's reach plus half
        a cell (fists: all eight neighbours), any direction, no wall in between (runtime._strike)."""
        reach2 = (2 * self.attack().reach + 1) ** 2
        return (tx, ty) != (px, py) and 4 * ((tx - px) ** 2 + (ty - py) ** 2) <= reach2 \
            and self.game._open_line(px, py, tx, ty)

    def unarmed_target(self):
        """The admitted enemy the next blow lands on: the nearest one in reach, in any direction
        (the same choice runtime._strike makes; name kept from fists-only days)."""
        px, py = self._player()
        candidates = []
        for target in self.game.targets.values():
            if self._hostile(target):
                tx, ty = self._global(target.chunk, target.x, target.y)
                if self.in_reach(px, py, tx, ty):
                    candidates.append(((tx - px) ** 2 + (ty - py) ** 2, target.id, tx, ty))
        return min(candidates) if candidates else None

    strike_target = unarmed_target

    def strike_cells(self, gx, gy):
        """Cells a blow can reach the enemy at (gx, gy) from: the circle of reach round it."""
        r = self.attack().reach
        return {(gx + dx, gy + dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
                if self.in_reach(gx + dx, gy + dy, gx, gy)}

    def _manual_combat_command(self, command, auto_attack):
        if not auto_attack or command.move or command.attack or self.task:
            return command
        target = self.unarmed_target()
        if target is None:
            return command
        _, _, tx, ty = target
        px, py = self._player()
        dx, dy = tx - px, ty - py   # face the cardinal side it is on (the blow itself lands any way)
        direction = ("east" if dx > 0 else "west") if abs(dx) >= abs(dy) else ("south" if dy > 0 else "north")
        # Release the attack edge during the animation; a later tick can punch again.
        return InputCommand(attack=self.game.player.animation != "attack" and not self.game.attack_held,
                            face=direction)

    def _near_camp(self, gx, gy):
        """Enemies never chase into the anchor camp: it is where a hurt avatar recovers."""
        return self.anchor is not None and abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]) <= CAMP_SAFE_RADIUS

    def _enemy_bites(self, target):
        """One enemy attack on the avatar (its counter feeds the client's lunge animation)."""
        enemy = self.enemy_of(target)
        self.strikes[target.id] = self.strikes.get(target.id, 0) + 1
        self.strike_serial += 1
        self.last_strike = {"serial": self.strike_serial, "profile": enemy.sound_profile}
        if self.task and self.task["type"] == "rest":
            self.task = None   # nobody rests through a bite: healing stops while something bites
        if enemy.drains == "hunger":   # it feeds: hunger runs down (starving is the vitals' job)
            self._hunger_bite(self.enemy_hit(target.chunk, enemy, self.tier_of(target.id)))
            return
        self._hurt(self.enemy_hit(target.chunk, enemy, self.tier_of(target.id)), enemy.cause)

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
        if self._pursuit_quiet(px, py, safe):   # cheap check first: most steps nothing is close
            return
        grid = self._grid()
        w, h = self._dims()
        field = self._field({(px, py)}, limit=PURSUIT_PATH_LIMIT)
        for target in sorted(self.game.targets.values(), key=lambda t: t.id):
            if not self._hostile(target):
                continue
            enemy = self.enemy_of(target)
            mode = self._hunt_mode(target, enemy, px, py, safe)
            if mode == "flee":
                self._flee(target, enemy, grid, w, h, px, py)
            elif mode is not None:
                self._fight_tick(target, enemy, mode, grid, w, h, px, py, field)
                if self.health == 0:
                    break

    # ----- fight patterns (catalog FightPattern) ----------------------------------------------
    def _row(self, target, mode, **extra):
        row = {"mode": mode, "since": self.total_ms, "ax": 0, "ay": 0, "ox": 0, "oy": 0, "left": 0}
        row.update(extra)
        self.hunting[target.id] = row
        return row

    def _fight_tick(self, target, enemy, mode, grid, w, h, px, py, field):
        """One monster tick of a hunter's pattern: hunt (close in) -> windup (the tell) -> strike
        (a bite, or a charge that may last a few ticks) -> recover (open to blows) -> retreat."""
        pattern, row = FIGHT_PATTERNS[enemy.pattern], self.hunting[target.id]
        held = self.total_ms - row["since"]
        if mode == "hunt":
            tx, ty, _ = self._close_in(target, enemy, grid, w, h, px, py, field)
            if self._can_strike(pattern, tx, ty, px, py):
                self._row(target, "windup", ax=px, ay=py, ox=tx, oy=ty)
                self._wind_up(target, enemy, pattern, tx, ty, px, py)
        elif mode == "windup" and held >= pattern.windup_ms:
            tx, ty = self._global(target.chunk, target.x, target.y)
            if pattern.strike == "bite":
                if max(abs(tx - px), abs(ty - py)) <= pattern.reach:
                    self._enemy_bites(target)
                self._row(target, "recover")
            else:
                self._row(target, "charge", ax=row["ax"], ay=row["ay"], ox=tx, oy=ty)
                self._charge(target, pattern, w, h, px, py)
        elif mode == "charge":
            self._charge(target, pattern, w, h, px, py)
        elif mode == "recover" and held >= pattern.recover_ms * (2 if row["left"] else 1):   # left: stunned on a wall
            if pattern.retreat:
                self._row(target, "retreat", left=pattern.retreat)
            else:
                self._row(target, "hunt")
        elif mode == "retreat":
            for _ in range(self._steps_this_tick(enemy)):
                if row["left"] <= 0 or self._enemy_step(target, grid, w, h, px, py, away=True) is None:
                    row["left"] = 0
                    break
                row["left"] -= 1
            if row["left"] <= 0:
                self._row(target, "hunt")

    def _can_strike(self, pattern, tx, ty, px, py):
        """Close enough to start a wind-up: a bite within its reach; a charge within its dash and
        with a clear run at the avatar."""
        reach = max(abs(tx - px), abs(ty - py))
        if pattern.strike == "bite":
            return reach <= pattern.reach
        return 1 <= reach < pattern.reach and all(not self.game.wall_at(*cell) for cell in self._dash_cells(tx, ty, px, py, reach))

    @staticmethod
    def _dash_cells(ox, oy, ax, ay, count):
        """The first `count` cells of a straight 8-connected run from (ox, oy) toward (ax, ay)."""
        dx, dy = ax - ox, ay - oy
        m = max(abs(dx), abs(dy))
        if m == 0:
            return []
        return [(ox + (2 * k * dx + m) // (2 * m), oy + (2 * k * dy + m) // (2 * m)) for k in range(1, count + 1)]

    def _charge(self, target, pattern, w, h, px, py):
        """Dash along the line fixed at the wind-up: a hit if it reaches the avatar's cell (it stops
        beside it), a stun if it runs into a wall, else on to the end of the dash."""
        row = self.hunting[target.id]
        path = self._dash_cells(row["ox"], row["oy"], row["ax"], row["ay"], pattern.reach)
        steps = max(1, MONSTER_STEP_MS // pattern.dash_step_ms)
        blocked = self._blocked() - {self._global(target.chunk, target.x, target.y)}
        while steps and row["left"] < len(path):
            nx, ny = path[row["left"]]
            if (nx, ny) == (px, py):
                self._enemy_bites(target)
                self._row(target, "recover")
                return
            key = ChunkKey(self.dimension, nx // w, ny // h)
            chunk = self.game.world.peek(key)
            if chunk is None or key not in self.game.initialized_chunks or chunk.asset.collision[ny % h][nx % w] \
                    or (nx, ny) in blocked:
                self._row(target, "recover", left=1)   # slammed into a tree or a rock: stunned
                return
            target.chunk, target.x, target.y = key, nx % w, ny % h
            self._field_cache.clear()
            row["left"] += 1
            steps -= 1
        if row["left"] >= len(path):
            self._row(target, "recover")

    def _wind_up(self, target, enemy, pattern, tx, ty, px, py):
        """A hunter shows its tell. The avatar answers: it turns to fight or runs (as before), and
        - not possessed - may see the strike coming and step out of it (dodge_percent)."""
        goal_kind = (self.goal or {}).get("kind")
        cornered = self.at_rest_place()   # running home gains nothing once home: turn and decide
        if goal_kind not in ("target", "dodge") and (goal_kind != "home" or cornered):
            self.task = None
            name = enemy.name.lower()
            expected = self.fight_damage(self.ring(target.chunk), self.target_action(target.id), self.tier_of(target.id))
            if self.health - expected >= VITAL_MAX // 4:   # fight only with a quarter of full health to spare
                self.goal = {"kind": "target", "id": target.id, "x": tx, "y": ty}
                self._entry("ambush", f"A {name} attacks you!")
            elif cornered:   # already at the camp or the fire: running gains nothing, so fight
                self.goal = {"kind": "target", "id": target.id, "x": tx, "y": ty}
                self._entry("ambush", f"A {name} corners you by the "
                            f"{'camp' if self.at_camp() else 'fire'} - you fight back!")
            else:   # this fight would kill: retreat and seek recovery
                self.goal = self._home_goal()
                self._entry("ambush", f"A {name} attacks you - too hurt to fight, you retreat!")
        if self.possessing or self.game.player.animation == "attack" or (self.goal or {}).get("kind") != "target":
            return   # possessed: the player dodges; running for home, it does not stop to sidestep
        roll = derive_seed(self.game.world.world_seed, "dodge", target.id, self.total_ms) % 100
        if roll >= self.dodge_percent():
            return
        cell = self._dodge_cell(pattern, tx, ty, px, py)
        if cell is not None:
            self.task = None
            self.goal = {"kind": "dodge", "id": target.id, "x": cell[0], "y": cell[1]}

    def _dodge_cell(self, pattern, tx, ty, px, py):
        """A neighbouring cell out of the coming strike, as close to the enemy as is safe (so the
        avatar can hit back while it recovers); None if there is none."""
        grid, blocked = self._grid(), self._blocked()
        danger = set(self._dash_cells(tx, ty, px, py, pattern.reach)) if pattern.strike == "charge" else None
        options = []
        for (mx, my), name in MOVES_8:
            cell = (px + mx, py + my)
            if mx and my:
                if not (self._can_move(grid, blocked, px, py, self._cardinal_toward(mx, 0))
                        and self._can_move(grid, blocked, px, py, self._cardinal_toward(0, my))
                        and self._walkable(grid, *cell) and cell not in blocked):
                    continue
            elif not self._can_move(grid, blocked, px, py, name):
                continue
            reach = max(abs(cell[0] - tx), abs(cell[1] - ty))
            if (danger is not None and cell in danger) or (danger is None and reach <= pattern.reach):
                continue
            options.append((abs(reach - pattern.reach - 1), name, cell))
        return min(options)[2] if options else None

    def _pursuit_quiet(self, px, py, safe):
        """Nothing hunts and no hostile enemy is within its aggro radius of the avatar."""
        return not self.hunting and not any(
            self._hostile(t) and self._steps_to(t, px, py) <= self.enemy_of(t).aggro_radius
            and not (safe and self.enemy_of(t).fears_fire)
            for t in self.game.targets.values())

    def _hunt_mode(self, target, enemy, px, py, safe):
        """This enemy's mode after this tick: None (unaware), "hunt" or "flee". Noticing the
        avatar starts a hunt; firelight turns a fire-fearing hunter to flight."""
        tx, ty = self._global(target.chunk, target.x, target.y)
        mode = self.hunting.get(target.id, {}).get("mode")
        if mode is None:
            if (safe and enemy.fears_fire) or abs(tx - px) + abs(ty - py) > enemy.aggro_radius \
                    or (enemy.fears_fire and self.in_firelight(tx, ty)):
                return None
            mode = "hunt"
            self._row(target, "hunt")
        if mode not in ("flee", None) and safe and enemy.fears_fire:
            mode = "flee"
            self._row(target, "flee")
            self._entry("lore", f"The {enemy.name.lower()} shies from the "
                        f"{'camp' if self._near_camp(px, py) else 'fire'} and slinks away.")
        return mode

    def _flee(self, target, enemy, grid, w, h, px, py):
        """A frightened enemy steps away, and is gone after FLEE_UNLOAD_MS even if cornered."""
        if self.total_ms - self.hunting[target.id]["since"] >= FLEE_UNLOAD_MS:
            self._unload(target)
            return
        for _ in range(self._steps_this_tick(enemy)):
            if self._enemy_step(target, grid, w, h, px, py, away=True) is None:
                break

    def _close_in(self, target, enemy, grid, w, h, px, py, field):
        """A hunter's steps this tick toward the avatar; returns its cell and distance."""
        tx, ty = self._global(target.chunk, target.x, target.y)
        distance = abs(tx - px) + abs(ty - py)
        for _ in range(self._steps_this_tick(enemy)):
            if distance <= 1:
                break
            moved = self._enemy_step(target, grid, w, h, px, py, field=field)
            if moved is None:
                break
            tx, ty = moved
            distance = abs(tx - px) + abs(ty - py)
        return tx, ty, distance

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
        self.fight_paid.pop(target.id, None)   # it comes back unhurt: the next fight pays from scratch
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

"""The Expedition: life state, the settle step and the deterministic advance loops.

advance() is the auto-pilot; advance_manual() lets a player steer while the
expedition still owns time, spots, vitals and enemies. Both cut time into steps that
end at every event (vitals rate change, task end, monster step, lead expiry, attack
impact), so any slicing of the same total time gives the same state.
"""
from ..catalog import BUILDINGS, BY_ID
from ..journal import new_journal
from ..models import DELTAS, DIRECTIONS, integer
from ..progression import scaled_ms, speed_permille
from ..runtime import InputCommand, Target
from ..tuning import PITY_CHUNKS
from .camp import CampMixin
from .combat import CombatMixin
from .ecology import EcologyMixin
from .constants import (ANCHOR_COUNTDOWN_MS, MAX_EVENTS_PER_ADVANCE, MONSTER_STEP_MS, PAUSE_BETWEEN_PUNCHES_MS,
                        POSSESS_COOLDOWN_MS, POSSESS_MS, POSSESS_SPEED_PERCENT, PROLOGUE_MS, PROLOGUE_NEXT,
                        REST_MS, RETREAT_BELOW, SELF_ACTIONS, STAT_KEYS, VITAL_MAX, attribute_table, ceil_div)
from .lives import LivesMixin
from .navigation import NavigationMixin
from .night import NightMixin
from .outcomes import OutcomesMixin
from .planning import PlanningMixin
from .presentation import PresentationMixin
from .saves import SavesMixin
from .spawning import SpawningMixin
from .vitals import VitalsMixin


class Expedition(PlanningMixin, SpawningMixin, NavigationMixin, CombatMixin, OutcomesMixin, VitalsMixin,
                 LivesMixin, SavesMixin, PresentationMixin, CampMixin, EcologyMixin, NightMixin):
    def __init__(self, game, *, fresh=True, opening=False):
        """fresh=True starts a new expedition (prologue first); loaders pass False.
        opening=True (new games in the browser) starts at the anchor: the player meets
        it and its shop before the first life, then the prologue plays."""
        self.game = game
        self.dimension = game.player.chunk.dimension
        # Persistent across lives.
        self.dimensional = attribute_table()
        self.life = 1
        self.total_ms = 0
        self.log = []
        self.sequence = 0
        self.decisions = 0
        self.best_depth = 0
        self.ash = 0
        self.converted = {}       # item id -> lifetime count converted into ash
        self.unlocked = set()      # UnlockDef ids: opened by dimensional level or bought with ash
        self.mastery = {}          # action id -> level earned from lifetime completions
        self.journal_guarantee = None  # one selected mastered encounter, placed once per life
        self.journal_guarantee_region = None
        self.contact_ready_ms = 0  # contact-the-anchor cooldown deadline (simulation time)
        self.contact = False       # the anchor is contacted mid-life: the world waits (not saved)
        self.possess_end_ms = None # possession (manual control) ends at this simulation time
        self.possess_ready_ms = 0  # possession recharges until this simulation time
        self.opening = False       # a new expedition waiting at the anchor before its first life
        self.night_tick = 0        # last world-clock tick the night watch looked at (autopilot/night.py)
        self.knowledge = set()     # discoveries persist across lives
        self.recipes = set()       # recipes kept with ash: known in every later life
        self.life_recipes = set()  # recipes found this life (lost at rebirth unless kept)
        self.journal_disabled = set()
        self.journal_favor = {}
        self.journal = new_journal()   # lifetime counts (journal.py); persists across lives
        self.bound_buildings = set()   # BuildingDef ids made permanent with ash
        self.chest = {}                # storage chest contents (item -> count); kept only if bound
        self.screen_log = []       # debug only, not saved: recent admissions/rejections
        self.roll_log = []         # debug only: bucket at the instant of each new roll
        self.monster_ms = 0
        self.anchor_ms = None
        self.anchor_wait = False
        # No pop-up opening: the prologue tells the story in the world itself.
        self.report = {"seq": 0, "life": 0, "clock_ms": 0, "title": "", "lines": []}
        self._clear_caches()
        self.step_cell = None      # manual control: last cell checked for a spot underfoot (not saved)
        self.auto_hold = None      # manual control: the held key that stepped onto a running spot (not saved)
        self.strikes = {}          # presentation only, not saved: boar attacks landed per target id
        self._new_life_state()
        self.anchor = self._anchor()
        self.elder = self._elder_cell()
        if fresh and opening:
            self.opening = True
            self.anchor_ms = ANCHOR_COUNTDOWN_MS
            self.anchor_wait = True
        elif fresh:
            self._start_task("awaken", PROLOGUE_MS["awaken"])
            self._screen()

    def _new_life_state(self):
        self.regular = attribute_table()
        self.life_gain = attribute_table()     # dimensional XP gained this life (report)
        self.completed = set()
        self.inventory = {}
        self.equipped = {}
        self.leads = []
        self.lead_history = []
        self.hunger = VITAL_MAX
        self.health = VITAL_MAX
        self.food_cooldown_ms = 0
        self.monster_ms = 0
        self.cause = None
        self.depth = 0
        self.task = None   # {"type": TASK_TYPES, "spot", "elapsed_ms", "duration_ms"}
        self.goal = None   # {"kind": "spot"|"target"|"wander"|"home", "id", "x", "y"}
        self.stats = {key: 0 for key in STAT_KEYS}
        self.drought = {category: 0 for category in PITY_CHUNKS}
        self.forced = {}   # chunk id -> [encounter id, ...] pity spots, in order
        self.guarantee_used = False
        self.buildings = set(self.bound_buildings)   # what stands at the camp this life
        self.pressure = {}     # "dimension:cx:cy:ecology" -> harvests this life (autopilot/ecology.py)
        self.shimmer = set()   # "dimension:cx:cy" region cells where rare spots roll more often this life
        self.life_recipes = set()   # recipes found this life: kept with ash at the anchor, or lost
        self.campfire = None   # {"dimension", "x", "y", "fire_x", "fire_y"}: this life's campfire (global cells)
        if not any(BUILDINGS[b].function == "storage" for b in self.bound_buildings):
            self.chest = {}   # an unbound chest does not outlast its life
        self._reset_spawns()

    # ----- public state -------------------------------------------------
    @property
    def possessing(self):
        """The player's god is steering the avatar (manual control)."""
        return self.possess_end_ms is not None

    @property
    def manual_control(self):
        return self.possessing

    def possess_block(self):
        """Why possession cannot start now, or None."""
        if self.anchor_ms is not None or self.contact:
            return "Not at the anchor"
        if self.in_prologue:
            return "Not yet"
        if self.possessing:
            return "Already possessed"
        if self.total_ms < self.possess_ready_ms:
            return "Recharging"
        return None

    def possess(self):
        """Take the avatar's hands for POSSESS_MS of simulation time."""
        reason = self.possess_block()
        if reason is not None:
            raise ValueError(f"cannot possess: {reason.lower()}")
        self.interrupt()
        self.possess_end_ms = self.total_ms + POSSESS_MS
        self._entry("possess", "You reach into the avatar and take its hands. It moves quicker with you.")

    def release(self):
        """End possession early; the auto-pilot takes over and possession recharges."""
        if not self.possessing:
            raise ValueError("the avatar is not possessed")
        self._end_possession()

    def _end_possession(self):
        self.possess_end_ms = None
        self.possess_ready_ms = self.total_ms + POSSESS_COOLDOWN_MS
        self.auto_hold = None
        self.goal = None
        if self.task and self.task["type"] in ("pause", "rest"):
            self.task = None

    def interrupt(self):
        """Hand over steering without erasing an already-started encounter."""
        if self.task and self.task["type"] in ("pause", "rest"):
            self.task = None
        self.goal = None

    def begin_interaction(self, reach=1):
        """Use the nearest admitted opportunity beside the player (`reach` steps; 0 = the cell
        the player stands on) in either control mode."""
        if self.anchor_ms is not None or self.in_prologue or self.task:
            return False
        px, py = self._player()
        choices = []
        for chunk in self._resident():
            for spot in self._live(chunk):
                if spot.id in self.completed or BY_ID[spot.encounter].category == "fight":
                    continue
                sx, sy = self._global(spot.chunk, spot.x, spot.y)
                distance = abs(px - sx) + abs(py - sy)
                if distance <= reach:
                    choices.append((distance, spot.id, spot))
        if not choices:
            return False
        spot = min(choices)[2]
        action = BY_ID[spot.encounter]
        self.goal = {"kind": "spot", "id": spot.id, "x": px, "y": py}
        self._start_perform(spot.id, action)
        return True

    @property
    def in_prologue(self):
        return bool(self.task) and self.task["type"] in PROLOGUE_MS

    def speed(self, attribute):
        speed = speed_permille(self.regular[attribute], self.dimensional[attribute])
        return speed * POSSESS_SPEED_PERCENT // 100 if self.possessing else speed

    # ----- tasks ---------------------------------------------------------
    def _start_task(self, kind, duration_ms, spot=None):
        """Begin a timed task: perform | pause | rest | a self action | a prologue stage."""
        self.task = {"type": kind, "spot": spot, "elapsed_ms": 0, "duration_ms": duration_ms}

    def _start_perform(self, spot_id, action):
        duration = scaled_ms(action.duration_ms, self.speed(action.attribute))
        spot = self._spot_by_id(spot_id) if action.placement == "site" else None
        if spot is not None:   # an overgrown site is slow going
            duration = duration * self.site_condition(spot.chunk).duration_percent // 100
        self._start_task("perform", max(1, duration), spot_id)

    # ----- settle --------------------------------------------------------
    def _settle(self):
        """Zero-time bookkeeping before each step. Returns True if a life ended."""
        if self.health == 0:
            self._die()
            return True
        here = self.ring(self.game.player.chunk)
        if here > self.depth:
            self.depth = here
            self.best_depth = max(self.best_depth, here)
        self._night_watch()
        self._screen()
        for chunk in self._resident():
            if chunk.key not in self.game.initialized_chunks:
                continue
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if entry.category == "fight" and spot.id not in self.game.targets and spot.id not in self.completed:
                    hp = self.enemy_hp(entry, spot.chunk)
                    self.game.targets[spot.id] = Target(spot.id, spot.chunk, spot.x, spot.y, hp)
        kinds = None
        for t in sorted(self.game.targets.values(), key=lambda t: t.id):
            if t.hp == 0 and t.id not in self.completed and t.id in self.admitted:
                kinds = kinds or self.target_kinds()
                self._reward(t.id, BY_ID[kinds[t.id]])
        self._pursue()
        self._eat()
        if not self._goal_valid():
            self.goal = None
        if self.goal and self.goal["kind"] == "wander" and not self.task and self._candidates():
            found = self._best_candidate(self._candidate_field())
            if found:
                self.goal = found
        return False

    def _run(self, ms, command):
        self.game.load_percent = self.load_percent()
        self._arm()
        self.game.advance(ms, command)
        self._apply_vitals(ms)
        self.monster_ms += ms

    def _step_cap(self, remaining):
        """Longest step from now that crosses no vitals, monster or lead event."""
        cap = min(remaining, self._vitals_limit(), MONSTER_STEP_MS - self.monster_ms, self.night_step_cap())
        if self.possessing:
            cap = min(cap, self.possess_end_ms - self.total_ms)
        if self.leads:
            cap = min(cap, min(lead["expires_ms"] - self.total_ms for lead in self.leads))
        return cap

    # ----- manual control ------------------------------------------------
    def _abandon_for(self, command):
        """Walking away abandons a running task (unrewarded; the spot stays usable).
        Without this, a move during a task froze the player for the whole task. The key that
        carried the player onto a spot (auto_hold) does not count until it is released or
        another direction is pressed: stepping onto something starts it, moving again leaves."""
        if self.auto_hold is not None and command.move != self.auto_hold:
            self.auto_hold = None
        if command.move and self.task and self.auto_hold is None:
            self.task = None
            self.goal = None

    def _step_onto(self, command):
        """Manual control: arriving on a spot's cell starts it (once per arrival)."""
        cell = self._player()
        if cell == self.step_cell:
            return
        self.step_cell = cell
        if self.task is None and self.begin_interaction(reach=0):
            self.auto_hold = command.move

    def advance_manual(self, milliseconds, command=InputCommand(), *, auto_attack=False):
        """Player chooses movement; expedition still owns time, spots, vitals and enemies."""
        integer(milliseconds, "elapsed milliseconds", 0)
        if self.contact:
            return   # the world waits while the anchor is contacted
        if self.anchor_ms is not None or self.in_prologue or not self.possessing:
            return self.advance(milliseconds)
        self.game.load_percent = self.load_percent()
        if milliseconds == 0:
            self._settle()
            self._abandon_for(command)
            self._arm()
            # no steps while working (a held key that carried the player onto a spot keeps it)
            self.game.advance(0, InputCommand() if self.task else self._manual_combat_command(command, auto_attack))
            if not self.task:
                self._step_onto(command)
            return
        remaining = milliseconds
        while remaining:
            if self.possessing and self.total_ms >= self.possess_end_ms:
                self._end_possession()
            if self.anchor_ms is not None or not self.possessing:
                self.advance(remaining)   # death or the end of possession: the auto-pilot carries on
                return
            self._expire_leads()
            if self._settle():
                continue
            self._abandon_for(command)
            if (self.task is None and not command.move and not command.attack
                    and self.at_rest_place() and self._wants_rest()):
                self._start_task("rest", REST_MS)   # standing still at the camp or a fire rests
            cap = self._step_cap(remaining)
            task = self.task
            if task:
                cap = min(cap, task["duration_ms"] - task["elapsed_ms"])
            self._run(cap, InputCommand() if task else self._manual_combat_command(command, auto_attack))
            if not task:
                self._step_onto(command)
            remaining -= cap
            if task:
                task["elapsed_ms"] += cap
                if task["elapsed_ms"] == task["duration_ms"]:
                    self.task = None
                    self._finish_manual_task(task)
        if self.possessing and self.total_ms >= self.possess_end_ms:
            self._end_possession()
        self._settle()

    def _finish_manual_task(self, task):
        """A finished task under manual control: reward a spot, finish a self action, stop."""
        if task["type"] == "perform":
            spot = self._spot_by_id(task["spot"])
            if spot is not None and spot.id not in self.completed:
                self._reward(spot.id, BY_ID[spot.encounter])
                self._after_location(spot, True)
        elif task["type"] in SELF_ACTIONS:
            self._complete_self(BY_ID[task["type"]])
        self.goal = None

    # ----- auto-pilot ----------------------------------------------------
    def _face(self, gx, gy):
        px, py = self._player()
        toward = ((gx > px) - (gx < px), (gy > py) - (gy < py))
        direction = next((d for d, delta in DELTAS.items() if delta == toward), None)
        if direction and self.game.player.facing != direction:
            self.game.advance(0, InputCommand(direction))
        self.game.advance(0, InputCommand())

    def advance(self, milliseconds, *, allow_prayer=True):
        """Let the auto-pilot live for `milliseconds` (partition-independent).
        allow_prayer=False is offline catch-up: visible-only actions never start."""
        integer(milliseconds, "elapsed milliseconds", 0)
        if type(allow_prayer) is not bool:
            raise ValueError("allow_prayer must be boolean")
        if self.contact:
            return   # the world waits while the anchor is contacted
        if self.possessing:
            self._end_possession()   # the auto-pilot drives: nobody holds the avatar (e.g. offline)
        self.game.load_percent = self.load_percent()
        saved_press = self.game.step_on_press
        self.game.step_on_press = False  # auto-pilot steps on interval boundaries only
        try:
            remaining, events = milliseconds, 0
            while True:
                events += 1
                if events > MAX_EVENTS_PER_ADVANCE:
                    raise RuntimeError("auto-pilot made no progress")
                if self.anchor_ms is not None:
                    if remaining == 0 or self.anchor_wait:
                        break
                    remaining -= self._anchor_step(remaining)
                    continue
                self._expire_leads()
                if self._settle():
                    self.game.step_on_press = False   # the next life's Exploration
                    continue
                if remaining == 0:
                    break
                remaining -= self._auto_step(self._step_cap(remaining), allow_prayer)
        finally:
            self.game.step_on_press = saved_press

    def _anchor_step(self, remaining):
        """Count down the anchor interlude; the next life begins when it runs out."""
        step = min(remaining, self.anchor_ms)
        self.anchor_ms -= step
        self.total_ms += step
        if self.anchor_ms == 0:
            self._begin_life()
        return step

    def _auto_step(self, cap, allow_prayer):
        """One auto-pilot decision or step of at most `cap` ms; returns the ms used."""
        if self.game.player.animation == "attack":
            return self._punch_step(cap)
        if (not self.task and self.attack().reach > 1 and (self.goal or {}).get("kind") not in ("home", "target")
                and self.health >= RETREAT_BELOW):
            ahead = self.strike_target()   # a weapon with reach strikes first as an enemy closes in
            if ahead is not None:
                self.goal = {"kind": "target", "id": ahead[1], "x": ahead[2], "y": ahead[3]}
        if self.task:
            return self._task_step(cap, allow_prayer)
        if self.goal is None:
            need = self._need_action(allow_prayer)
            if need is not None:
                self._start_self(need)
                return 0
            self.goal = self._choose_goal()
            if self.goal is None:
                self._run(cap, InputCommand())
                return cap
        return self._travel_step(cap)

    def _punch_step(self, cap):
        """Run the attack clip, stopping where damage lands (same clock for any slicing)."""
        game = self.game
        clip = game.animations["attack"].duration_ms * 100
        done = game.player.animation_elapsed_ms * game.attack_rate_percent
        left = ceil_div(clip - done, game.attack_rate_percent)
        for start, _, _ in game.animations["attack"].active_intervals():
            if done < start * 100:
                left = min(left, ceil_div(start * 100 - done, game.attack_rate_percent))
                break
        step = max(1, min(cap, left))
        self._run(step, InputCommand(attack=True))
        if game.player.animation != "attack":
            self._enemy_strikes_back()
            self._start_task("pause", scaled_ms(PAUSE_BETWEEN_PUNCHES_MS, self.speed("strength")))
        return step

    def _task_step(self, cap, allow_prayer):
        step = min(cap, self.task["duration_ms"] - self.task["elapsed_ms"])
        self._run(step, InputCommand())
        self.task["elapsed_ms"] += step
        if self.task["elapsed_ms"] >= self.task["duration_ms"]:
            done, self.task = self.task, None
            self._finish_auto_task(done, allow_prayer)
        return step

    def _finish_auto_task(self, done, allow_prayer):
        kind = done["type"]
        if kind == "perform":
            spot = self._spot_by_id(done["spot"])
            if spot is not None and spot.id not in self.completed:
                self._reward(spot.id, BY_ID[spot.encounter])
            self.goal = None
            if spot is not None:
                self._after_location(spot, allow_prayer)
        elif kind in SELF_ACTIONS:
            self._complete_self(BY_ID[kind])
        elif kind in PROLOGUE_MS:
            stage = PROLOGUE_NEXT.get(kind)
            if stage == "listen":
                self._face(*self.elder)   # turn to the old man
            if stage:
                self._start_task(stage, PROLOGUE_MS[stage])
            else:
                self._entry("lore", "The old man walks off down the road. The forest is yours to explore.")
        elif kind == "rest":
            if self._wants_rest() and self.at_rest_place():
                self._start_task("rest", REST_MS)   # keep resting
            else:
                self.goal = None
                self._entry("rest", "Rested at the anchor camp." if self.at_camp() else "Rested by the campfire.")

    def _travel_step(self, cap):
        """Act on arrival at the goal, else take one step down its distance field."""
        game, here, goal = self.game, self._player(), self.goal
        goals = self._goal_cells(goal)
        if here in goals and (goal["kind"] != "home" or here == (goal["x"], goal["y"])):
            self._arrive(goal)
            return 0
        field = self._field(goals, until=here)
        grid, blocked = self._grid(), self._blocked()
        best = None
        for direction in DIRECTIONS:
            dx, dy = DELTAS[direction]
            nxt = (here[0] + dx, here[1] + dy)
            if nxt in field and self._can_move(grid, blocked, *here, direction):
                if best is None or field[nxt] < best[0]:
                    best = (field[nxt], direction)
        if best is None or best[0] >= field.get(here, 1 << 30):
            self.goal = None  # unreachable now: wait one interval, then replan
            step = min(cap, game.step_interval_ms)
            self._run(step, InputCommand())
            return step
        direction = best[1]
        left = (max(1, game.step_interval_ms - game.move_elapsed_ms)   # a lighter load may shorten it
                if game.last_move == direction else game.step_interval_ms)
        step = min(cap, left)
        self._run(step, InputCommand(direction))
        return step

    def _arrive(self, goal):
        if goal["kind"] == "wander":
            self.goal = None
        elif goal["kind"] == "home":
            self._stow()
            self._start_task("rest", REST_MS)
        elif goal["kind"] == "spot":
            self._face(goal["x"], goal["y"])
            self._start_perform(goal["id"], BY_ID[self._spot_by_id(goal["id"]).encounter])
        else:
            self._face(goal["x"], goal["y"])
            self._arm()
            self.game.advance(0, InputCommand(attack=True))  # rising edge: punch

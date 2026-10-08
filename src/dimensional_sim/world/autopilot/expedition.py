"""The Expedition: life state, the settle step and the deterministic advance loops.

advance() is the auto-pilot; advance_manual() lets a player steer while the
expedition still owns time, spots, vitals and enemies. Both cut time into steps that
end at every event (vitals rate change, task end, monster step, lead expiry, attack
impact), so any slicing of the same total time gives the same state.
"""
from ..catalog import BY_ID
from ..journal import new_journal
from ..models import DELTAS, DIRECTIONS, integer
from ..progression import scaled_ms, speed_permille
from ..runtime import InputCommand, Target
from ..tuning import PITY_CHUNKS
from .combat import CombatMixin
from .constants import (DANGER_RING_CAP, MAX_EVENTS_PER_ADVANCE, MONSTER_STEP_MS, PAUSE_BETWEEN_PUNCHES_MS,
                        PROLOGUE_MS, PROLOGUE_NEXT, REST_MS, RESTED_AT, SELF_ACTIONS, SKILLS, STAT_KEYS,
                        VITAL_MAX, attribute_table, ceil_div)
from .lives import LivesMixin
from .navigation import NavigationMixin
from .outcomes import OutcomesMixin
from .planning import PlanningMixin
from .presentation import PresentationMixin
from .saves import SavesMixin
from .spawning import SpawningMixin
from .vitals import VitalsMixin


class Expedition(PlanningMixin, SpawningMixin, NavigationMixin, CombatMixin, OutcomesMixin, VitalsMixin,
                 LivesMixin, SavesMixin, PresentationMixin):
    def __init__(self, game, *, skills=(), fresh=True):
        """fresh=True starts a new expedition (prologue first); loaders pass False."""
        self.game = game
        self.dimension = game.player.chunk.dimension
        self.skills = set()
        for skill in skills:
            self.unlock(skill)
        # Persistent across lives.
        self.dimensional = attribute_table()
        self.life = 1
        self.total_ms = 0
        self.log = []
        self.sequence = 0
        self.decisions = 0
        self.best_depth = 0
        self.blessing = 0
        self.ash = 0
        self.converted = {}       # item id -> lifetime count converted into ash
        self.unlocked = set()      # UnlockDef ids bought with ash/blessing
        self.mastery = {}          # action id -> level earned from lifetime completions
        self.journal_guarantee = None  # one selected mastered encounter, placed once per life
        self.journal_guarantee_region = None
        self.return_ready_ms = 0  # persistent cooldown deadline in simulation time
        self.knowledge = set()     # discoveries persist across lives
        self.recipes = set()       # learned recipes persist across lives
        self.journal_disabled = set()
        self.journal_favor = {}
        self.boon_next = None      # BoonDef id for the next life
        self.boon = None           # BoonDef id active this life
        self.journal = new_journal()   # lifetime counts (journal.py); persists across lives
        self.screen_log = []       # debug only, not saved: recent admissions/rejections
        self.roll_log = []         # debug only: bucket at the instant of each new roll
        self.monster_ms = 0
        self.anchor_ms = None
        self.anchor_wait = False
        # No pop-up opening: the prologue tells the story in the world itself.
        self.report = {"seq": 0, "life": 0, "clock_ms": 0, "title": "", "lines": []}
        self._clear_caches()
        self.strikes = {}          # presentation only, not saved: boar attacks landed per target id
        self._new_life_state()
        self.anchor = self._anchor()
        self.elder = self._elder_cell()
        if fresh:
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
        self.prayers_this_life = 0
        self.monster_ms = 0
        self.cause = None
        self.depth = 0
        self.task = None   # {"type": TASK_TYPES, "spot", "elapsed_ms", "duration_ms"}
        self.goal = None   # {"kind": "spot"|"target"|"wander"|"home", "id", "x", "y"}
        self.stats = {key: 0 for key in STAT_KEYS}
        self.drought = {category: 0 for category in PITY_CHUNKS}
        self.forced = {}   # chunk id -> [encounter id, ...] pity spots, in order
        self.guarantee_used = False
        self._reset_spawns()

    # ----- public state -------------------------------------------------
    def unlock(self, skill):
        if skill not in SKILLS:
            raise ValueError("unknown skill")
        self.skills.add(skill)

    @property
    def manual_control(self):
        return "take_control" in self.skills

    def interrupt(self):
        """Hand over steering without erasing an already-started encounter."""
        if self.task and self.task["type"] in ("pause", "rest"):
            self.task = None
        self.goal = None

    def begin_interaction(self):
        """Use the nearest admitted opportunity beside the player in either control mode."""
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
                if distance <= 1:
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
        return speed_permille(self.regular[attribute], self.dimensional[attribute])

    # ----- tasks ---------------------------------------------------------
    def _start_task(self, kind, duration_ms, spot=None):
        """Begin a timed task: perform | pause | rest | a self action | a prologue stage."""
        self.task = {"type": kind, "spot": spot, "elapsed_ms": 0, "duration_ms": duration_ms}

    def _start_perform(self, spot_id, action):
        self._start_task("perform", scaled_ms(action.duration_ms, self.speed(action.attribute)), spot_id)

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
        self._screen()
        for chunk in self._resident():
            if chunk.key not in self.game.initialized_chunks:
                continue
            for spot in self._live(chunk):
                entry = BY_ID[spot.encounter]
                if entry.category == "fight" and spot.id not in self.game.targets and spot.id not in self.completed:
                    hp = entry.hp + min(self.ring(spot.chunk), DANGER_RING_CAP)
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
        self.game.advance(ms, command)
        self._apply_vitals(ms)
        self.monster_ms += ms

    def _step_cap(self, remaining):
        """Longest step from now that crosses no vitals, monster or lead event."""
        cap = min(remaining, self._vitals_limit(), MONSTER_STEP_MS - self.monster_ms)
        if self.leads:
            cap = min(cap, min(lead["expires_ms"] - self.total_ms for lead in self.leads))
        return cap

    # ----- manual control ------------------------------------------------
    def _abandon_for(self, command):
        """Walking away abandons a running task (unrewarded; the spot stays usable).
        Without this, a move during a task froze the player for the whole task."""
        if command.move and self.task:
            self.task = None
            self.goal = None

    def advance_manual(self, milliseconds, command=InputCommand(), *, auto_attack=False):
        """Player chooses movement; expedition still owns time, spots, vitals and enemies."""
        integer(milliseconds, "elapsed milliseconds", 0)
        if self.anchor_ms is not None or self.in_prologue:
            return self.advance(milliseconds)
        if milliseconds == 0:
            self._settle()
            self._abandon_for(command)
            self.game.advance(0, self._manual_combat_command(command, auto_attack))
            return
        remaining = milliseconds
        while remaining:
            self._expire_leads()
            if self._settle():
                continue
            if self.anchor_ms is not None:
                self.advance(remaining)
                return
            self._abandon_for(command)
            cap = self._step_cap(remaining)
            task = self.task
            if task:
                cap = min(cap, task["duration_ms"] - task["elapsed_ms"])
            self._run(cap, InputCommand() if task else self._manual_combat_command(command, auto_attack))
            remaining -= cap
            if task:
                task["elapsed_ms"] += cap
                if task["elapsed_ms"] == task["duration_ms"]:
                    self.task = None
                    self._finish_manual_task(task)
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
            self._boar_strikes_back()
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
                self._entry("lore", "The old man walks off down the road. Explore - and don't forget to pray.")
        elif kind == "rest":
            if self.health < RESTED_AT and (self.hunger > 0 or self._has_food()):
                self._start_task("rest", REST_MS)   # keep resting
            else:
                self.goal = None
                self._entry("rest", "Rested at the anchor camp.")

    def _travel_step(self, cap):
        """Act on arrival at the goal, else take one step down its distance field."""
        game, here, goal = self.game, self._player(), self.goal
        goals = self._goal_cells(goal)
        if here in goals and (goal["kind"] != "home" or here == self.anchor):
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
            step = min(cap, game.movement_interval_ms)
            self._run(step, InputCommand())
            return step
        direction = best[1]
        left = (game.movement_interval_ms - game.move_elapsed_ms
                if game.last_move == direction else game.movement_interval_ms)
        step = min(cap, left)
        self._run(step, InputCommand(direction))
        return step

    def _arrive(self, goal):
        if goal["kind"] == "wander":
            self.goal = None
        elif goal["kind"] == "home":
            self._start_task("rest", REST_MS)
        elif goal["kind"] == "spot":
            self._face(goal["x"], goal["y"])
            self._start_perform(goal["id"], BY_ID[self._spot_by_id(goal["id"]).encounter])
        else:
            self._face(goal["x"], goal["y"])
            self.game.attack_damage = self.punch_damage()
            self.game.advance(0, InputCommand(attack=True))  # rising edge: punch

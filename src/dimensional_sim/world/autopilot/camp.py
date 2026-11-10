"""The anchor camp: buildings, the storage chest, camp work and carry load.

Buildings (catalog.BUILDINGS) are built at the camp by build actions from carried
resources. They stand until the life ends; bound ones (ash, at the anchor) are
permanent. A crafting station is the workplace of every craft. A storage chest takes
the materials brought to the camp; crafting and building there draw on it too. An
unbound chest's contents become ash with the inventory when the life ends.

Carry load: every carried unit beyond CARRY_FREE slows walking, softened by
Endurance and Strength. The movement interval is a pure function of state, set on the
runtime before each step, so any slicing of time moves the same.
"""
from ..catalog import BUILDINGS, CAMP_GRADE, FARM_GROW_MS, ITEMS
from ..models import DELTAS
from ..tuning import CAMPFIRE_AWAY, CARRY_FREE, CARRY_MAX_PERCENT, CARRY_PERCENT_PER_ITEM, CHEST_SLOTS, STOW_TRIP_AT
from .constants import CAMP_SAFE_RADIUS, FIRE_KIT, NEED_ACTIONS, POSSESS_SPEED_PERCENT, RESTED_AT, RETREAT_BELOW, STACK_LIMIT
HARVEST_BELOW_FOOD = 80   # vital points of food carried below which the avatar harvests a ripe farm

STATION_FUNCTION = "crafting"


class CampMixin:
    # ----- where -------------------------------------------------------------
    def at_camp(self):
        """In the anchor camp during a life (where buildings stand and camp work happens)."""
        if self.anchor is None or self.anchor_ms is not None:
            return False
        gx, gy = self._player()
        return abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]) <= CAMP_SAFE_RADIUS

    def has_chest(self):
        return any(BUILDINGS[b].function == "storage" for b in self.buildings)

    # ----- resources at hand ---------------------------------------------------
    def camp_stock(self):
        """What the avatar can use right now: the inventory, plus the chest at the camp."""
        stock = dict(self.inventory)
        if self.at_camp():
            for item, count in self.chest.items():
                stock[item] = stock.get(item, 0) + count
        return stock

    def _pay(self, cost):
        """Consume `cost` from the inventory first, then (at the camp) from the chest."""
        for item, count in cost:
            take = min(count, self.inventory.get(item, 0))
            if take:
                self._remove_item(item, take)
            rest = count - take
            if rest:
                self.chest[item] -= rest
                if not self.chest[item]:
                    del self.chest[item]

    def _stow(self):
        """At the camp with a chest: carried materials go into the chest (deterministic order)."""
        if not self.has_chest() or not self.at_camp():
            return []
        moved = []
        for item in sorted(self.inventory):
            if ITEMS[item].kind != "material":
                continue
            have = self.chest.get(item)
            if have is None and len(self.chest) >= CHEST_SLOTS:
                continue
            count = min(self.inventory[item], STACK_LIMIT - (have or 0))
            if count <= 0:
                continue
            self.chest[item] = (have or 0) + count
            self._remove_item(item, count)
            moved.append((item, -count))
        if moved:
            self._entry("stow", "Stowed materials in the storage chest.", items=moved)
        return moved

    # ----- buildings -------------------------------------------------------------
    def _build(self, action):
        building = BUILDINGS[action.builds]
        self.buildings.add(building.id)
        self.stats["built"] += 1

    # ----- camp work (planning) ----------------------------------------------------
    def _camp_work_ready(self):
        """A full material pack can still take an automatic storage trip."""
        if self.at_camp() or self.health < RETREAT_BELOW:
            return False
        if self.has_chest() and sum(n for i, n in self.inventory.items()
                                    if ITEMS[i].kind == "material") >= STOW_TRIP_AT:
            return True
        return False

    # ----- campfire ------------------------------------------------------------------
    # One per life, anywhere: resting by it heals like resting at the anchor camp (the
    # "rest" task adds REST_REGEN wherever it runs). It is not a sanctuary: enemies still
    # chase there. A new fire replaces the old one.
    def _fire_seat(self):
        """The cell beside this life's campfire where the avatar rests, or None."""
        fire = self.campfire
        if fire is None or fire["dimension"] != self.dimension:
            return None
        return fire["x"], fire["y"]

    def _hurt_far(self):
        """Badly hurt, far from the anchor camp and from any campfire: time to make one."""
        if self.anchor is None or self.anchor_ms is not None or self.health >= RETREAT_BELOW:
            return False
        if self.hunger == 0 and self._has_food():
            return False   # eat first
        gx, gy = self._player()
        far = lambda cell: abs(gx - cell[0]) + abs(gy - cell[1]) > CAMPFIRE_AWAY
        seat = self._fire_seat()
        return far(self.anchor) and (seat is None or far(seat))

    def _rest_goal(self):
        """Where a hurt avatar goes to rest: its campfire when nearer than the anchor."""
        gx, gy = self._player()
        seat = self._fire_seat()
        if seat is not None and abs(gx - seat[0]) + abs(gy - seat[1]) < abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]):
            return {"kind": "home", "id": "campfire", "x": seat[0], "y": seat[1]}
        return self._home_goal()

    def at_rest_place(self):
        """Standing where resting heals faster: the anchor camp or beside this life's fire."""
        if self.at_camp():
            return True
        seat = self._fire_seat()
        gx, gy = self._player()
        return seat is not None and abs(gx - seat[0]) + abs(gy - seat[1]) <= 1

    def can_make_fire(self):
        return (self.anchor_ms is None and not self.in_prologue and self.task is None and not self.contact
                and self.grade_of(self.location_here()) >= CAMP_GRADE
                and all(self.inventory.get(item, 0) >= n for item, n in FIRE_KIT.items()))

    def _place_fire(self):
        """Set this life's campfire down beside the avatar (the avatar keeps its cell)."""
        gx, gy = self._player()
        grid = self._grid()
        fire = (gx, gy)
        for direction in ("east", "west", "south", "north"):
            if self._can_move(grid, frozenset(), gx, gy, direction):
                dx, dy = DELTAS[direction]
                fire = (gx + dx, gy + dy)
                break
        self.campfire = {"dimension": self.dimension, "x": gx, "y": gy, "fire_x": fire[0], "fire_y": fire[1]}
        self.goal = None

    def farm_ripe(self):
        """A farm stands at the camp and its crops are ready (FARM_GROW_MS since the last harvest)."""
        return any(BUILDINGS[b].function == "farm" for b in self.buildings) \
            and self.total_ms - self.farm_harvest_ms >= FARM_GROW_MS

    def _harvest_wanted(self):
        """At the camp with a ripe farm and short of food: the farm's harvest action, else None."""
        if not (self.at_camp() and self.farm_ripe() and not self.task) or self._food_carried() >= HARVEST_BELOW_FOOD:
            return None
        from ..actions import reasons_against
        ctx = self.self_context("need")
        return next((a for a in NEED_ACTIONS if a.need_flag == "farm_ripe" and not reasons_against(a, ctx)), None)

    def _food_carried(self):
        return sum(n * ITEMS[i].food for i, n in self.inventory.items() if ITEMS[i].kind == "food")

    def _rent_bed(self):
        """A bed rented at a village inn: this life's rest place (like a campfire, no fire), and a
        camp there that holds the avatar to the village and the road around it."""
        self._place_fire()
        self.campfire["bed"] = True
        self._pitch_camp(force=True)

    def _wants_rest(self):
        return self.health < RESTED_AT and (self.hunger > 0 or self._has_food())

    # ----- carry load ----------------------------------------------------------------
    def carried_units(self):
        return sum(self.inventory.values())

    def load_percent(self):
        """Movement interval in percent of normal: 100 + the carry penalty (capped), shortened by
        Agility and possession."""
        extra = max(0, self.carried_units() - CARRY_FREE)
        load = 100
        if extra:
            relief = (self.speed("endurance") + self.speed("strength")) // 2   # permille, >= 1000
            load += min(CARRY_MAX_PERCENT, extra * CARRY_PERCENT_PER_ITEM * 1000 // relief)
        load = load * 1000 // (1000 + self.move_bonus_permille())   # Agility: faster steps (training.py)
        return load * 100 // POSSESS_SPEED_PERCENT if self.possessing else load

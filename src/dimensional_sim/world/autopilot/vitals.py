"""Hunger and health as exact integer rates; every rate change ends a simulation step."""
from ..catalog import ITEMS
from ..tuning import ENDURANCE_HARD_HUNGER
from .constants import (EAT_AT, HUNGER_DRAIN, POINT, REGEN, REGEN_ABOVE, REST_REGEN, STARVATION, VITAL_MAX, ceil_div)


class VitalsMixin:
    # Hunger, health and the cause of death change only here (and when a life begins).
    def _heal(self, points):
        self.health = min(VITAL_MAX, self.health + points * POINT)

    def _feed(self, points):
        self.hunger = min(VITAL_MAX, self.hunger + points * POINT)

    def _hurt(self, amount, cause):
        """Lose `amount` health (micro-points); at 0 the life ends of `cause`."""
        self.health = max(0, self.health - amount)
        if self.health == 0:
            self.cause = cause

    def _hunger_bite(self, amount):
        """An enemy that feeds takes hunger, not health (starving is the clock's job)."""
        self.hunger = max(0, self.hunger - amount)

    def _drain(self):
        return HUNGER_DRAIN * 1000 // self.speed("endurance")

    def _health_rate(self):
        rate = 0
        if self.hunger == 0:
            rate -= STARVATION
        elif self.hunger > REGEN_ABOVE:
            rate += REGEN
        if self.task and self.task["type"] == "rest":
            rate += REST_REGEN
        return rate

    def _vitals_limit(self):
        """Milliseconds until the next vitals event (rate change, eating, death)."""
        limits = []
        drain = self._drain()
        if self.hunger > 0:
            limits.append(ceil_div(self.hunger, drain))
            if self.hunger > REGEN_ABOVE:
                limits.append(ceil_div(self.hunger - REGEN_ABOVE, drain))
            if self.hunger > EAT_AT:
                limits.append(ceil_div(self.hunger - EAT_AT, drain))
            if self.hunger > ENDURANCE_HARD_HUNGER * POINT:   # walking hungry trains Endurance faster
                limits.append(ceil_div(self.hunger - ENDURANCE_HARD_HUNGER * POINT, drain))
            foods = [ITEMS[item].food for item in self.inventory if ITEMS[item].kind == "food"]
            if foods:
                first_fit = VITAL_MAX - min(foods) * POINT
                if self.hunger > first_fit:
                    limits.append(ceil_div(self.hunger - first_fit, drain))
        if self.food_cooldown_ms:
            limits.append(self.food_cooldown_ms)
        rate = self._health_rate()
        if rate < 0 and self.health > 0:
            limits.append(ceil_div(self.health, -rate))
        elif rate > 0 and self.health < VITAL_MAX:
            limits.append(ceil_div(VITAL_MAX - self.health, rate))
        return max(1, min(limits)) if limits else 1 << 40

    def _apply_vitals(self, ms):
        rate = self._health_rate()
        if self.hunger == 0:
            self.cause = "starvation"
        self.hunger = max(0, self.hunger - self._drain() * ms)
        self.health = max(0, min(VITAL_MAX, self.health + rate * ms))
        self.food_cooldown_ms = max(0, self.food_cooldown_ms - ms)
        self.total_ms += ms

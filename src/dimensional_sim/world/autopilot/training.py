"""Training: XP the avatar earns on the way, not from finishing an action (docs/design/STATS_AND_ENEMIES_AUDIT.md).

- Walking pays per tile stepped, never per second: Agility, Endurance (twice as fast when hungry or
  heavily loaded) and Perception for newly seen ground, so exploring pays and pacing does not.
- Fights pay per landed hit (FIGHT_XP_PER_HP per hit point taken off); the finishing blow adds
  FINISH_XP_PERCENT of the enemy's whole worth (outcomes._reward).
- Movement: the whole Agility multiplier shortens the step interval on a log curve.

Remainders of walking XP are saved (`walk`), so how time is sliced never changes the XP earned.
"""
import math

from ..catalog import BY_ID
from ..progression import speed_permille
from ..tuning import (AGILITY_TILES_PER_XP, ENDURANCE_HARD_HUNGER, ENDURANCE_TILES_PER_XP, FIGHT_XP_PER_HP,
                      FINISH_XP_PERCENT, MOVE_BONUS_PER_DECADE, PERCEPTION_CELLS_PER_XP)
from .constants import POINT

WALK_KEYS = ("agility", "endurance", "perception")   # the saved remainders, in tiles or cells
WALK_RATES = {"agility": AGILITY_TILES_PER_XP, "endurance": ENDURANCE_TILES_PER_XP,
              "perception": PERCEPTION_CELLS_PER_XP}


class TrainingMixin:
    def move_bonus_permille(self):
        """+10% x log10(Agility multiplier), in permille: 30 at x2, 100 at x10, 200 at x100."""
        speed = speed_permille(self.regular["agility"], self.dimensional["agility"])
        return int(round(MOVE_BONUS_PER_DECADE * math.log10(speed / 1000))) if speed > 1000 else 0

    def _advance_game(self, ms, command, *, pay=True):
        """game.advance, then what the avatar earned on the way: landed hits and walking. With
        pay=False the caller pays (_pay_training) after the step's vitals, so XP gained in a step
        never changes the rates that step was lived at (any time slicing agrees)."""
        game = self.game
        before = {t.id: t.hp for t in game.targets.values() if t.hp > 0 and t.id in self.admitted}
        hard = self.hunger <= ENDURANCE_HARD_HUNGER * POINT or self.load_percent() > 100   # at the step's start
        game.advance(ms, command)
        hits = [(game.targets[i], hp - game.targets[i].hp) for i, hp in sorted(before.items())
                if i in game.targets and game.targets[i].hp < hp]
        earned = (hits, game.moved_tiles, game.revealed_cells, hard)
        game.moved_tiles = game.revealed_cells = 0
        if pay:
            self._pay_training(earned)
        return earned

    def _pay_training(self, earned):
        hits, tiles, cells, hard = earned
        for target, damage in hits:
            self._landed(target, damage)
        if self.anchor_ms is None and (tiles or cells):
            self._walk_xp("agility", tiles)
            self._walk_xp("endurance", tiles * (2 if hard else 1))
            self._walk_xp("perception", cells)

    def _walk_xp(self, attribute, amount):
        if amount:
            total = self.walk[attribute] + amount
            self.walk[attribute] = total % WALK_RATES[attribute]
            self._gain_xp(attribute, total // WALK_RATES[attribute])

    def _landed(self, target, damage):
        """A blow took `damage` hit points off an admitted enemy: XP for the fight's attribute,
        plus the finishing blow's share when it falls."""
        action = BY_ID[self.admitted[target.id]]
        if action.category != "fight":
            return
        xp = damage * FIGHT_XP_PER_HP
        if target.hp == 0:
            whole = self.enemy_hp(action, target.chunk, self.tier_of(target.id)) * FIGHT_XP_PER_HP
            xp += whole * FINISH_XP_PERCENT // 100
        dim = self._gain_xp(action.attribute, xp)
        paid = self.fight_paid.setdefault(target.id, [0, 0])   # shown on the kill's log line
        paid[0] += xp
        paid[1] += dim

"""A test-only weapon with a fists' reach, so tests about the weapon slot and punch_damage keep
their meaning whatever the real weapons (catalog) become; tests patch this item in."""
from contextlib import contextmanager
from unittest.mock import patch

from dimensional_sim.world.catalog import ITEMS, Effect, ItemDef

TEST_STAFF = ItemDef("test_staff", "Test staff", "gear", glyph="|", ash_value=2, slot="weapon",
                     effects=(Effect("punch_damage", 1),), attack="fists", color="#d6b27a")


@contextmanager
def test_weapon():
    with patch.dict(ITEMS, test_staff=TEST_STAFF):
        yield TEST_STAFF

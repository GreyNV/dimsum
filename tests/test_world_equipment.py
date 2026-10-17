"""World gear is owned in inventory but has an explicit, validated slot."""

import unittest

from dimensional_sim.world.catalog import ITEMS
from gear_fixture import TEST_STAFF
from unittest.mock import patch
from dimensional_sim.world.equipment import (
    EQUIPMENT_SLOTS, equip_item, is_equipped, item_in_slot, unequip_slot, validate_equipped,
)


@patch.dict(ITEMS, test_staff=TEST_STAFF)
class WorldEquipmentTests(unittest.TestCase):
    def test_catalog_gear_has_distinct_slots(self):
        self.assertIn("weapon", EQUIPMENT_SLOTS)
        self.assertEqual(ITEMS["test_staff"].slot, "weapon")
        self.assertEqual(ITEMS["hide_wrap"].slot, "body")
        self.assertIsNone(ITEMS["stick"].slot)

    def test_equipping_preserves_inventory_and_selects_slots(self):
        inventory = {"test_staff": 1, "hide_wrap": 1, "stick": 3}
        weapon = equip_item({}, inventory, "test_staff")
        equipped = equip_item(weapon, inventory, "hide_wrap")
        self.assertEqual(weapon, {"weapon": "test_staff"})
        self.assertEqual(equipped, {"body": "hide_wrap", "weapon": "test_staff"})
        self.assertEqual(inventory, {"test_staff": 1, "hide_wrap": 1, "stick": 3})
        self.assertEqual(item_in_slot(equipped, "weapon"), ITEMS["test_staff"])
        self.assertIsNone(item_in_slot(weapon, "body"))
        self.assertTrue(is_equipped(equipped, "test_staff"))
        self.assertEqual(unequip_slot(equipped, inventory, "weapon"), {"body": "hide_wrap"})

    def test_invalid_equipment_and_stale_inventory_are_rejected(self):
        inventory = {"test_staff": 1, "hide_wrap": 1, "stick": 3}
        invalid = (
            {"weapon": "stick"},
            {"weapon": "hide_wrap"},
            {"unknown": "test_staff"},
            {"weapon": "missing_gear"},
        )
        for equipped in invalid:
            with self.subTest(equipped=equipped), self.assertRaises(ValueError):
                validate_equipped(equipped, inventory)
        with self.assertRaises(ValueError):
            validate_equipped({"weapon": "test_staff"}, {})
        with self.assertRaises(ValueError):
            validate_equipped({"weapon": "test_staff"}, {"test_staff": True})
        with self.assertRaises(ValueError):
            equip_item({}, inventory, "stick")
        with self.assertRaises(ValueError):
            equip_item({}, {}, "test_staff")
        with self.assertRaises(ValueError):
            item_in_slot({}, "unknown")


if __name__ == "__main__":
    unittest.main()

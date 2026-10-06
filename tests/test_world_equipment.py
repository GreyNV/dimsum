"""World gear is owned in inventory but has an explicit, validated slot."""

import unittest

from dimensional_sim.world.catalog import ITEMS
from dimensional_sim.world.equipment import (
    EQUIPMENT_SLOTS, equip_item, is_equipped, item_in_slot, unequip_slot, validate_equipped,
)


class WorldEquipmentTests(unittest.TestCase):
    def test_catalog_gear_has_distinct_slots(self):
        self.assertIn("weapon", EQUIPMENT_SLOTS)
        self.assertEqual(ITEMS["walking_staff"].slot, "weapon")
        self.assertEqual(ITEMS["hide_wrap"].slot, "body")
        self.assertIsNone(ITEMS["stick"].slot)

    def test_equipping_preserves_inventory_and_selects_slots(self):
        inventory = {"walking_staff": 1, "hide_wrap": 1, "stick": 3}
        weapon = equip_item({}, inventory, "walking_staff")
        equipped = equip_item(weapon, inventory, "hide_wrap")
        self.assertEqual(weapon, {"weapon": "walking_staff"})
        self.assertEqual(equipped, {"body": "hide_wrap", "weapon": "walking_staff"})
        self.assertEqual(inventory, {"walking_staff": 1, "hide_wrap": 1, "stick": 3})
        self.assertEqual(item_in_slot(equipped, "weapon"), ITEMS["walking_staff"])
        self.assertIsNone(item_in_slot(weapon, "body"))
        self.assertTrue(is_equipped(equipped, "walking_staff"))
        self.assertEqual(unequip_slot(equipped, inventory, "weapon"), {"body": "hide_wrap"})

    def test_invalid_equipment_and_stale_inventory_are_rejected(self):
        inventory = {"walking_staff": 1, "hide_wrap": 1, "stick": 3}
        invalid = (
            {"weapon": "stick"},
            {"weapon": "hide_wrap"},
            {"unknown": "walking_staff"},
            {"weapon": "missing_gear"},
        )
        for equipped in invalid:
            with self.subTest(equipped=equipped), self.assertRaises(ValueError):
                validate_equipped(equipped, inventory)
        with self.assertRaises(ValueError):
            validate_equipped({"weapon": "walking_staff"}, {})
        with self.assertRaises(ValueError):
            validate_equipped({"weapon": "walking_staff"}, {"walking_staff": True})
        with self.assertRaises(ValueError):
            equip_item({}, inventory, "stick")
        with self.assertRaises(ValueError):
            equip_item({}, {}, "walking_staff")
        with self.assertRaises(ValueError):
            item_in_slot({}, "unknown")


if __name__ == "__main__":
    unittest.main()

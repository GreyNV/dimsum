"""Current-life equipment slots for the world expedition.

Inventory owns items and their quantities. Equipment only records which owned
gear item occupies each slot; callers must validate after inventory changes and
when loading a save. This is separate from persistent summoned idle equipment.
"""

from .catalog import EQUIPMENT_SLOTS, ITEMS


def _gear(item_id):
    item = ITEMS.get(item_id) if type(item_id) is str else None
    if item is None or item.kind != "gear" or getattr(item, "slot", None) not in EQUIPMENT_SLOTS:
        raise ValueError("item is not slotted world equipment")
    return item


def validate_equipped(equipped, inventory):
    """Return a stable copy of a slot map, rejecting gear not currently owned."""
    if type(equipped) is not dict or type(inventory) is not dict:
        raise ValueError("equipment and inventory must be dictionaries")
    for slot, item_id in equipped.items():
        if slot not in EQUIPMENT_SLOTS or _gear(item_id).slot != slot:
            raise ValueError("item does not fit equipment slot")
        count = inventory.get(item_id)
        if type(count) is not int or count < 1:
            raise ValueError("equipped item is not in inventory")
    return {slot: equipped[slot] for slot in EQUIPMENT_SLOTS if slot in equipped}


def equip_item(equipped, inventory, item_id):
    """Equip owned gear, replacing its slot; return a new validated slot map."""
    current = validate_equipped(equipped, inventory)
    item = _gear(item_id)
    count = inventory.get(item_id)
    if type(count) is not int or count < 1:
        raise ValueError("equipment must be in inventory before it can be worn")
    current[item.slot] = item_id
    return validate_equipped(current, inventory)


def unequip_slot(equipped, inventory, slot):
    """Clear one slot without removing its item from inventory."""
    if slot not in EQUIPMENT_SLOTS:
        raise ValueError("unknown equipment slot")
    current = validate_equipped(equipped, inventory)
    current.pop(slot, None)
    return current


def item_in_slot(equipped, slot):
    """Return the catalog definition currently assigned to a valid slot."""
    if slot not in EQUIPMENT_SLOTS:
        raise ValueError("unknown equipment slot")
    item_id = equipped.get(slot)
    if item_id is None:
        return None
    item = _gear(item_id)
    if item.slot != slot:
        raise ValueError("item does not fit equipment slot")
    return item


def is_equipped(equipped, item_id):
    """Whether the given gear item occupies its catalog slot."""
    item = _gear(item_id)
    return equipped.get(item.slot) == item_id

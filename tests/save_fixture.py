"""Test support: the schema-17 shape of a current save, so migration tests can keep
building older saves by removing the fields each later schema added."""
from dimensional_sim.world.autopilot import saves


def v17(data):
    """`data` (a current to_dict()) as schema 17 wrote it: blessing, boons, the random
    prayer counter, skills and the return cooldown; no contact, possession or opening."""
    old = {k: v for k, v in data.items() if k not in saves.V18_FIELDS + saves.V19_FIELDS}
    old.update(schema_version=17, blessing=0, boon=None, boon_next=None, prayers_this_life=0, skills=[],
               return_ready_ms=0, unlocked=[u for u in data["unlocked"] if u != "campfire"],
               log=[{**entry, "blessing": 0} for entry in data["log"]])
    return old

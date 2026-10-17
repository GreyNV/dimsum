"""The Journal's encounter tree (details.encounter_tree): branches by what you do, landmarks
by site, trails under whatever opens them, the night apart; unfound follow-ups stay unnamed."""
import unittest

from dimensional_sim.world.catalog import ACTIONS, BY_ID, JOURNAL_GROUPS, SITES
from dimensional_sim.world.details import encounter_tree


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n["children"])


class JournalTreeTests(unittest.TestCase):
    def test_every_encounter_has_exactly_one_home_when_everything_is_known(self):
        everything = {a.id for a in ACTIONS if a.placement in ("spot", "site", "lead")}
        tree = encounter_tree(everything)
        roots = []
        for branch in tree:
            roots += [n["id"] for n in branch["nodes"]]
            for group in branch["groups"]:
                roots += [n["id"] for n in group["nodes"]]
        spots = {a.id for a in ACTIONS if a.placement in ("spot", "site")}
        self.assertEqual(spots - set(roots), set(), "every spot and site encounter is a root")
        placed = {n["id"] for b in tree for n in walk(b["nodes"] + [m for g in b["groups"] for m in g["nodes"]])}
        self.assertEqual(everything - placed, set(), "every lead hangs somewhere")
        self.assertEqual([b["title"] for b in tree][:len(JOURNAL_GROUPS)], [g[1] for g in JOURNAL_GROUPS])
        landmarks = next(b for b in tree if b["id"] == "landmarks")
        self.assertEqual(len(landmarks["groups"]), len(SITES))

    def test_trails_nest_under_their_source_and_unfound_ones_are_only_counted(self):
        source = next(a for a in ACTIONS if a.placement == "spot" and any(o.kind == "lead" for o in a.outcomes))
        lead = next(o.id for o in source.outcomes if o.kind == "lead")
        tree = encounter_tree({source.id, lead})
        node = next(n for b in tree for n in b["nodes"] if n["id"] == source.id)
        self.assertIn(lead, [c["id"] for c in node["children"]])
        alone = encounter_tree({source.id})
        node = next(n for b in alone for n in b["nodes"] if n["id"] == source.id)
        self.assertEqual(node["children"], [])
        self.assertGreaterEqual(node["hidden"], 1)
        counts = next(b for b in alone if any(n["id"] == source.id for n in b["nodes"]))
        self.assertEqual(counts["known"], 1)
        self.assertGreater(counts["total"], 1)

    def test_the_night_has_its_own_branch(self):
        night = next(b for b in encounter_tree({"night_wolf"}) if b["id"] == "night")
        self.assertEqual([n["id"] for n in night["nodes"]], ["night_wolf"])
        self.assertIn("night", BY_ID["night_wolf"].tags)


if __name__ == "__main__":
    unittest.main()

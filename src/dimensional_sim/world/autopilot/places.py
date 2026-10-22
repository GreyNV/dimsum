"""Location mastery and camps (docs/design/LOCATIONS.md).

A location is a kind of place (catalog LOCATIONS): a forest region or a kind of landmark.
Every encounter finished in one adds to its lifetime mastery (`location_done`, kept across
lives: every past life shapes the next). At CAMP_GRADE a camp - the campfire - can be made
there, by the avatar on its own or by the player while possessing it. While a camp stands,
the avatar keeps to that place: it only goes after what lies in the camp's area and fits the
place's focus (LOCATION_FOCUS, chosen on the Journal's Places page), and spot rolls there lean
towards the focus. When the area has nothing left to give for CAMP_IDLE_MS, it breaks camp.
"""
from ..tuning import CAMPFIRE_AWAY
from .constants import EAT_AT, POINT

CAMP_ROAM_HUNGER = EAT_AT + 25 * POINT   # below this, with no food carried, the camp lets the avatar roam
from ..catalog import (BY_ID, CAMP_GRADE, CAMP_IDLE_MS, LOCATION_DEEP_RARITY_PERCENT, LOCATION_FOCUS,
                       LOCATION_GRADE_NAMES, LOCATION_OF_REGION, LOCATION_OF_SITE, LOCATIONS, REGION_CELL,
                       location_grade, location_thresholds)


class PlacesMixin:
    # ----- where things are ------------------------------------------------------------
    def location_of_chunk(self, key):
        """The region location of chunk `key` (wild spots and leads count there), or None."""
        region = self.region(key)
        return LOCATION_OF_REGION.get(region.id) if region else None

    def location_of_spot(self, entry, spot):
        """Where a finished encounter counts: its landmark for site encounters, else its chunk's region."""
        if entry.placement == "site":
            return LOCATION_OF_SITE.get(entry.site)
        return self.location_of_chunk(spot.chunk) if spot is not None else None

    def location_here(self):
        """The location the avatar stands in: a landmark's clearing, else the region."""
        player = self.game.player
        site = self.game.world.site_for(player.chunk)
        if site is not None and site.contains(player.x, player.y):
            return LOCATION_OF_SITE.get(site.site.id)
        return self.location_of_chunk(player.chunk)

    def grade_of(self, location_id):
        return 0 if location_id is None else location_grade(location_id, self.location_done.get(location_id, 0))

    # ----- mastery -----------------------------------------------------------------------
    def _record_location(self, entry, spot):
        """One finished encounter counts towards its location; log each grade reached."""
        if entry.placement not in ("spot", "lead", "site"):
            return
        location = self.location_of_spot(entry, spot) if spot is not None or entry.placement == "site" \
            else self.location_of_chunk(self.game.player.chunk)   # a spot already gone: where the avatar is
        if location is None:
            return
        before = self.grade_of(location)
        self.location_done[location] = self.location_done.get(location, 0) + 1
        after = self.grade_of(location)
        if after > before:
            name = LOCATIONS[location].name
            tail = {1: "The Journal now shows what is found there.",
                    2: "A camp can be made there now: the avatar keeps to the place while it stands.",
                    3: "Rare finds come more often there."}[after]
            self._entry("lore", f"{name}: {LOCATION_GRADE_NAMES[after].lower()}. {tail}")

    def location_rarity_percent(self, key):
        """Deep mastery of the region or its landmark improves wild spot tiers here."""
        site = self.game.world.site_for(key)
        site_location = LOCATION_OF_SITE.get(site.id) if site is not None else None
        deep = (self.grade_of(self.location_of_chunk(key)) >= 3 or self.grade_of(site_location) >= 3)
        return LOCATION_DEEP_RARITY_PERCENT if deep else 100

    # ----- the camp ----------------------------------------------------------------------
    def _pitch_camp(self):
        """A campfire was just made: it holds the avatar to the place it stands in."""
        location = self.location_here()
        if location is None or self.grade_of(location) < CAMP_GRADE:
            self.camp = None
            return
        key = self.game.player.chunk
        site = LOCATIONS[location].kind == "site"
        self.camp = {"location": location, "dimension": key.dimension,
                     "cx": key.x if site else key.x // REGION_CELL, "cy": key.y if site else key.y // REGION_CELL,
                     "idle_since": None, "left": False}
        self._entry("rest", f"Made camp: {LOCATIONS[location].name}, focus on {self.camp_focus_name().lower()}.")

    def camp_focus(self):
        return self.location_focus.get(self.camp["location"], "all") if self.camping() else None

    def camping(self):
        return self.camp is not None and not self.camp.get("left")

    def camp_holds(self):
        """The camp keeps the avatar in its place - except when it runs low on food with none
        carried: then it may roam for food (a camp's region cell is also where its food gets picked
        over; holding a hungry avatar there nearly doubled deaths by starvation)."""
        return self.camping() and not (self.hunger <= CAMP_ROAM_HUNGER and not self._has_food())

    def _wants_camp(self):
        """The avatar makes camp on its own: in a mastered place whose focus the player chose, away
        from the anchor camp, not camped yet (and not back in a place it already left this life)."""
        if self.camping() or self.anchor_ms is not None or self.at_camp():
            return False
        here = self.location_here()
        if here is None or here not in self.location_focus or self.grade_of(here) < CAMP_GRADE:
            return False
        if self.camp is not None and self.camp["location"] == here:
            return False   # broke camp here already this life
        gx, gy = self._player()
        return abs(gx - self.anchor[0]) + abs(gy - self.anchor[1]) > CAMPFIRE_AWAY

    def camp_focus_name(self):
        return LOCATION_FOCUS[self.camp_focus() or "all"][0]

    def in_camp_area(self, key):
        """Chunk `key` lies in the camp's place: the landmark's chunk and its neighbours, or the
        camp's region cell where it is that region."""
        camp = self.camp
        if not self.camping() or key.dimension != camp["dimension"]:
            return False
        if LOCATIONS[camp["location"]].kind == "site":
            return abs(key.x - camp["cx"]) <= 1 and abs(key.y - camp["cy"]) <= 1
        return (key.x // REGION_CELL, key.y // REGION_CELL) == (camp["cx"], camp["cy"]) \
            and self.location_of_chunk(key) == camp["location"]

    def camp_wants(self, entry, chunk_key):
        """Whether the camped avatar goes after this encounter (always true without a camp)."""
        if not self.camp_holds() or entry.placement == "story":
            return True
        if not self.in_camp_area(chunk_key):
            return False
        categories = LOCATION_FOCUS[self.camp_focus()][1]
        return categories is None or entry.category in categories or entry.placement == "site" and \
            self.camp_focus() == "searching"

    def _camp_idle(self, found_work):
        """Track how long the camp's area has had nothing to give; break camp after CAMP_IDLE_MS."""
        if not self.camping():
            return
        if found_work:
            self.camp["idle_since"] = None
            return
        if self.camp["idle_since"] is None:
            self.camp["idle_since"] = self.total_ms
        elif self.total_ms - self.camp["idle_since"] >= CAMP_IDLE_MS:
            self._entry("rest", f"Nothing more around the camp at {LOCATIONS[self.camp['location']].name}. Moving on.")
            self.camp["left"] = True

    def set_location_focus(self, location, mode):
        if location not in LOCATIONS or mode not in LOCATION_FOCUS and mode != "none":
            raise ValueError("unknown location or focus")
        if self.grade_of(location) < CAMP_GRADE:
            raise ValueError("a focus needs a mastered location")
        if mode == "none":
            self.location_focus.pop(location, None)
            self._entry("purchase", f"{LOCATIONS[location].name}: the avatar makes no camp there on its own.")
        else:
            self.location_focus[location] = mode
            self._entry("purchase", f"{LOCATIONS[location].name}: the avatar makes camp there and goes after "
                                    f"{LOCATION_FOCUS[mode][0].lower()}.")

    # ----- presentation ------------------------------------------------------------------
    def places_view(self):
        """Every location: grade, progress to the next grade, focus, and whether a camp holds it."""
        here = self.location_here()
        rows = []
        for location in LOCATIONS.values():
            done = self.location_done.get(location.id, 0)
            grade = self.grade_of(location.id)
            needs = location_thresholds(location.id)
            rows.append({"id": location.id, "name": location.name, "kind": location.kind, "text": location.text,
                         "done": done, "grade": grade, "grade_name": LOCATION_GRADE_NAMES[grade],
                         "next": needs[grade] if grade < len(needs) else None,
                         "camp_at": needs[CAMP_GRADE - 1], "can_camp": grade >= CAMP_GRADE,
                         "focus": self.location_focus.get(location.id, "none"), "here": location.id == here,
                         "camped": self.camping() and self.camp["location"] == location.id})
        return {"places": rows, "focus_modes": [{"id": "none", "name": "No camp"}]
                + [{"id": k, "name": v[0]} for k, v in LOCATION_FOCUS.items()],
                "here": here, "camp": None if not self.camping() else {
                    "location": self.camp["location"], "name": LOCATIONS[self.camp["location"]].name,
                    "focus": self.camp_focus_name()}}


def home_location(action_id):
    """For save upgrades: the location an encounter's old lifetime count most likely belongs to."""
    from ..catalog import ORIGIN_REGION, REGIONS
    action = BY_ID.get(action_id)
    if action is None or action.placement not in ("spot", "lead", "site"):
        return None
    if action.placement == "site":
        return LOCATION_OF_SITE.get(action.site)
    regions = [r for r in REGIONS.values() if r.biome in action.biomes
               and (action.regions is None or r.id in action.regions)]
    if not regions:
        return LOCATION_OF_REGION.get(ORIGIN_REGION)
    best = max(regions, key=lambda r: (r.multiplier(action.id), r.id == ORIGIN_REGION, r.id))
    return LOCATION_OF_REGION.get(best.id)

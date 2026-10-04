"""Provisional, versioned phase-one content shared by runtime and balance runs."""
from .core import Action, Encounter, GameConfig, GameState, SoulboundItem, Stage


def new_demo_game(seed: int = 1) -> GameState:
    def action(id: str, name: str, discipline: str, seconds: float, vitality: float, xp: float = 1.0) -> Action:
        return Action(id, name, discipline, seconds, vitality, xp, xp * 0.35)

    village = Stage(
        id="act1_village",
        name="Village Awakening",
        act=1,
        guaranteed_actions=(
            action("talk_father", "Talk to Father", "willpower", 30, 1.0, 1.2),
            action("practice_movement", "Practice Movement", "agility", 45, 1.5),
        ),
        encounters=(
            Encounter("village_mystery", "A Village Mystery", "common", 0.18, action("village_mystery_action", "Investigate the Village", "intelligence", 60, 3, 1.5), 0.0, 0.0, "A detail in the village does not fit the story."),
        ),
        summon_weights={"common": 90, "uncommon": 10},
        summon_level_caps={"common": 20},
    )
    forest = Stage(
        id="act1_forest",
        name="Forest Edge",
        act=1,
        guaranteed_actions=(action("walk_forest", "Walk the Forest Edge", "endurance", 90, 3, 1.0),),
        encounters=(
            Encounter("forest_tracks", "Tracks in the Leaves", "common", 0.25, action("observe_tracks", "Observe Tracks", "perception", 75, 3, 1.2), 0, 0, "Something large passed through the forest.") ,
            Encounter("recovery_spring", "A Hidden Spring", "uncommon", 0.10, action("drink_spring", "Drink from the Spring", "endurance", 45, 1, 0.8), 18, 0.0, "The water carries a faint dimensional taste."),
            Encounter("rift_glimpse", "A Glimpse of the Rift", "rare", 0.03, action("sense_rift", "Sense the Rift", "perception", 120, 8, 1.0), -4, 2.0, "The world folds for an instant.")
        ),
        summon_weights={"common": 75, "uncommon": 20, "rare": 5},
        summon_level_caps={"common": 50, "uncommon": 20},
    )
    old_trail = Stage(
        id="act2_old_trail",
        name="The Old Trail",
        act=2,
        guaranteed_actions=(action("old_trail", "Walk the Old Trail", "endurance", 180, 7, 1.0),),
        encounters=(
            Encounter("trail_echo", "An Echo of Another Life", "uncommon", 0.12, action("read_echo", "Read the Echo", "intelligence", 150, 6, 1.0), 4, 1.0, "The anchor remembers a path you have not yet walked."),
            Encounter("trail_fight", "A Predatory Shade", "rare", 0.05, action("fight_shade", "Fight the Shade", "strength", 210, 14, 1.1), -12, 2.0, "The thing hunting the trail is not native to this world."),
        ),
        summon_weights={"common": 60, "uncommon": 30, "rare": 10},
        summon_level_caps={"common": 100, "uncommon": 50, "rare": 20},
    )
    items = [
        SoulboundItem("lens_of_attention", "Lens of Attention", "common", discipline="perception", slot="head"),
        SoulboundItem("training_band", "Training Band", "common", discipline="endurance", slot="body"),
        SoulboundItem("echo_bead", "Echo Bead", "common", discipline="willpower"),
        SoulboundItem("worn_gauntlets", "Worn Gauntlets", "common", discipline="strength", slot="hands"),
        SoulboundItem("soft_boots", "Soft Boots", "common", discipline="agility", slot="feet"),
        SoulboundItem("scribe_charm", "Scribe Charm", "common", discipline="intelligence"),
        SoulboundItem("surveyor_wraps", "Surveyor Wraps", "common", discipline="perception", slot="hands"),
        SoulboundItem("anchor_thread", "Anchor Thread", "uncommon", speed_bonus=0.03, shard_rate_bonus=0.20, discipline="willpower"),
        SoulboundItem("old_gauntlet", "Old Gauntlet", "rare", speed_bonus=0.10, softcap_bonus=5, discipline="strength", slot="hands"),
    ]
    return GameState(
        config=GameConfig(),
        stages=[village, forest, old_trail],
        soulbound_items=items,
        seed=seed,
    )

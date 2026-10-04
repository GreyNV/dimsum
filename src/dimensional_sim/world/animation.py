"""Reusable player clips, authored facing north; simulation timing is explicit metadata.

Frames carry independent graphics, anchors, optional effects and active hitboxes.
Animation rates are positive integer percentages; integer numerator clocks avoid
partition-dependent rounding. No location, renderer or provider imports belong here.
"""
from dataclasses import asdict, dataclass
import json

from .models import Cell, DIRECTIONS, fields, integer

ANIMATION_NAMES = ("idle", "walk", "attack", "hit", "death")


def _point(value, name):
    if type(value) is not tuple or len(value) != 2:
        raise ValueError(f"invalid {name}")
    for coordinate in value:
        integer(coordinate, name, -128, 128)


@dataclass(frozen=True)
class Frame:
    duration_ms: int
    cell: Cell
    anchor: tuple[int, int] = (0, 0)
    active: bool = False
    hitbox: tuple[tuple[int, int], ...] = ()
    effect_origin: tuple[int, int] | None = None

    def __post_init__(self):
        integer(self.duration_ms, "frame duration", 1, 60000)
        if not isinstance(self.cell, Cell):
            raise ValueError("invalid frame cell")
        _point(self.anchor, "anchor")
        if self.anchor != (0, 0):
            raise ValueError("single-cell graphics require anchor (0, 0)")
        if type(self.active) is not bool or type(self.hitbox) is not tuple:
            raise ValueError("invalid active/hitbox metadata")
        for point in self.hitbox:
            _point(point, "hitbox offset")
        if len(set(self.hitbox)) != len(self.hitbox) or self.active != bool(self.hitbox):
            raise ValueError("active frames require a nonempty unique hitbox")
        if self.effect_origin is not None:
            _point(self.effect_origin, "effect origin")


@dataclass(frozen=True)
class Animation:
    name: str
    frames: tuple[Frame, ...]
    loop: bool = True

    def __post_init__(self):
        if self.name not in ANIMATION_NAMES or type(self.frames) is not tuple or not self.frames:
            raise ValueError("invalid animation name/frames")
        if any(not isinstance(frame, Frame) for frame in self.frames) or type(self.loop) is not bool:
            raise ValueError("invalid animation frame/loop")
        if self.name == "attack" and (self.loop or not any(f.active for f in self.frames)):
            raise ValueError("attack must be non-looping with an active frame")
        if self.name != "attack" and any(f.active for f in self.frames):
            raise ValueError("only attack clips may contain damage metadata")

    @property
    def duration_ms(self):
        return sum(frame.duration_ms for frame in self.frames)

    def sample(self, elapsed_ms: int, rate_percent: int = 100) -> Frame:
        integer(elapsed_ms, "animation time", 0)
        integer(rate_percent, "animation rate", 1, 10000)
        tick = elapsed_ms * rate_percent // 100
        tick = tick % self.duration_ms if self.loop else min(tick, self.duration_ms - 1)
        for frame in self.frames:
            if tick < frame.duration_ms:
                return frame
            tick -= frame.duration_ms
        raise AssertionError("validated animation has no frame")

    def active_intervals(self):
        """Yield (start_ms, end_ms, frame), using half-open authored intervals."""
        elapsed = 0
        for frame in self.frames:
            if frame.active:
                yield elapsed, elapsed + frame.duration_ms, frame
            elapsed += frame.duration_ms


def rotate(point, facing):
    """Rotate north-authored offset clockwise; never infer gameplay from glyphs."""
    if facing not in DIRECTIONS:
        raise ValueError("invalid facing")
    x, y = point
    return {"north": (x, y), "east": (-y, x), "south": (-x, -y), "west": (y, -x)}[facing]


def default_animations():
    normal = Cell("@", "#eee4ce", "#17211b")
    return {
        "idle": Animation("idle", (Frame(600, normal), Frame(600, Cell("@", "#c6ba9f")))),
        "walk": Animation("walk", (Frame(120, normal), Frame(120, Cell("@", "#ffffff")))),
        "attack": Animation("attack", (
            Frame(120, Cell("@", "#dbac76")),
            Frame(80, Cell("@", "#ffffff"), active=True, hitbox=((0, -1),), effect_origin=(0, -1)),
            Frame(160, normal)), loop=False),
        "hit": Animation("hit", (Frame(100, Cell("@", "#ee7777")), Frame(100, normal)), loop=False),
        "death": Animation("death", (Frame(200, Cell("%", "#988577")),), loop=False),
    }


def validate_animations(animations):
    if not isinstance(animations, dict) or set(animations) != set(ANIMATION_NAMES):
        raise ValueError("all five named animations required")
    if any(not isinstance(clip, Animation) or name != clip.name for name, clip in animations.items()):
        raise ValueError("invalid animation catalog")


def animations_to_dict(animations):
    validate_animations(animations)
    return json.loads(json.dumps({name: asdict(clip) for name, clip in sorted(animations.items())}))


def animations_from_dict(raw):
    if not isinstance(raw, dict):
        raise ValueError("invalid animation catalog")
    result = {}
    try:
        for name, clip in raw.items():
            fields(clip, ("name", "frames", "loop"))
            if not isinstance(clip["frames"], list):
                raise ValueError("frames must be JSON arrays")
            frames = []
            for item in clip["frames"]:
                fields(item, ("duration_ms", "cell", "anchor", "active", "hitbox", "effect_origin"))
                fields(item["cell"], ("glyph", "fg", "bg"))
                if not isinstance(item["hitbox"], list):
                    raise ValueError("hitbox must be JSON array")
                frames.append(Frame(item["duration_ms"], Cell(**item["cell"]), tuple(item["anchor"]),
                    item["active"], tuple(tuple(p) for p in item["hitbox"]),
                    None if item["effect_origin"] is None else tuple(item["effect_origin"])))
            result[name] = Animation(clip["name"], tuple(frames), clip["loop"])
        validate_animations(result)
        return result
    except (TypeError, KeyError) as exc:
        raise ValueError("malformed animation data") from exc


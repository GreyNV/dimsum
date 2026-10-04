"""Pure character-grid rendering. No clock, generation, input or provider dependencies.

render() only reads resident chunks and actual discovery metadata. A Frame is a
snapshot: encoding it repeatedly cannot move entities, change damage or discover tiles.
Layer order: environment < object < entity < player < effect < UI/minimap.
"""
from dataclasses import dataclass
from .models import Cell, Grid, integer

VOID = Cell(" ", "#c6c8bb", "#101714")
LAYER_ORDER = ("environment", "object", "entity", "player", "effect", "ui")


@dataclass(frozen=True)
class Camera:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Frame:
    cells: Grid
    camera: Camera

    @property
    def width(self):
        return self.camera.width

    @property
    def height(self):
        return self.camera.height


def camera_for(x: int, y: int, world_width: int, world_height: int,
               width: int, height: int) -> Camera:
    """Clamp a player-following viewport inside one resident chunk."""
    for name, value in (("world width", world_width), ("world height", world_height),
                        ("view width", width), ("view height", height)):
        integer(value, name, 1)
    integer(x, "camera target x", 0, world_width - 1)
    integer(y, "camera target y", 0, world_height - 1)
    w, h = min(width, world_width), min(height, world_height)
    return Camera(max(0, min(x - w // 2, world_width - w)),
                  max(0, min(y - h // 2, world_height - h)), w, h)


def compose_layers(*layers: Grid) -> Grid:
    """Overlay equally sized immutable grids; None is transparent, even over a space."""
    if not layers or not layers[0] or not layers[0][0]:
        raise ValueError("at least one nonempty grid required")
    h, w = len(layers[0]), len(layers[0][0])
    result = [[VOID for _ in range(w)] for _ in range(h)]
    for grid in layers:
        if len(grid) != h or any(len(row) != w for row in grid):
            raise ValueError("layer dimensions differ")
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is not None:
                    if not isinstance(cell, Cell):
                        raise ValueError("layer cells must be Cell or None")
                    result[y][x] = cell
    return tuple(tuple(row) for row in result)


def _overlay(width, height, positions):
    return tuple(tuple(positions.get((x, y)) for x in range(width)) for y in range(height))


def minimap_cells(world, center, radius=2) -> Grid:
    """Unknown does not imply absent: querying this view NEVER creates a chunk."""
    integer(radius, "map radius", 0, 20)
    side = radius * 2 + 1
    palette = {
        "unknown": Cell("?", "#67756e", "#101714"),
        "generated": Cell(".", "#a4b3a8", "#101714"),
        "visited": Cell("o", "#9bdd9b", "#101714"),
    }
    cells = {}
    for point in world.minimap(center, radius):
        x, y = point["x"] - center.x + radius, point["y"] - center.y + radius
        cell = palette[point["status"]]
        if point["x"] == center.x and point["y"] == center.y:
            cell = Cell("@", "#ffe0a3", "#101714")
        cells[x, y] = cell
    return _overlay(side, side, cells)


def render(exploration, *, width=32, height=16, show_map=True) -> Frame:
    """Read the current resident chunk and place transient layers separately."""
    chunk = exploration.current_chunk()
    asset, player = chunk.asset, exploration.player
    camera = camera_for(player.x, player.y, asset.width, asset.height, width, height)
    entities = {(t.x, t.y): Cell("g", "#df876b", "#17211b")
                for t in exploration.targets.values() if t.chunk == player.chunk and t.hp > 0}
    environment = compose_layers(
        asset.environment, asset.objects,
        _overlay(asset.width, asset.height, entities),
        _overlay(asset.width, asset.height, {(player.x, player.y): exploration.player_cell()}),
        _overlay(asset.width, asset.height, exploration.effect_cells()),
    )
    clipped = tuple(tuple(environment[y][camera.x:camera.x + camera.width])
                    for y in range(camera.y, camera.y + camera.height))
    if show_map and camera.width >= 7 and camera.height >= 5:
        mini = minimap_cells(exploration.world, player.chunk)
        positions = {(camera.width - len(mini[0]) + x, y): cell
                     for y, row in enumerate(mini) for x, cell in enumerate(row)}
        clipped = compose_layers(clipped, _overlay(camera.width, camera.height, positions))
    return Frame(clipped, camera)


def to_text(frame: Frame) -> str:
    return "\n".join("".join(cell.glyph for cell in row) for row in frame.cells)


def to_ansi(frame: Frame) -> str:
    """Truecolor terminal output; validated ASCII prevents injected terminal commands."""
    lines = []
    for row in frame.cells:
        parts, last_colors = [], None
        for cell in row:
            colors = (cell.fg, cell.bg)
            if colors != last_colors:
                fg = ";".join(str(int(cell.fg[i:i+2], 16)) for i in (1, 3, 5))
                bg = ";".join(str(int(cell.bg[i:i+2], 16)) for i in (1, 3, 5))
                parts.append(f"\x1b[38;2;{fg}m\x1b[48;2;{bg}m")
                last_colors = colors
            parts.append(cell.glyph)
        lines.append("".join(parts) + "\x1b[0m")
    return "\n".join(lines)

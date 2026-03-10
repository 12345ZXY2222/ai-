from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal


class WorldAgentPlacement(BaseModel):
    agent_id: str
    x: int
    y: int


class WorldCreateRequest(BaseModel):
    name: str
    width: int = Field(ge=1, le=1000)
    height: int = Field(ge=1, le=1000)
    preset: Optional[str] = None  # e.g. "basketball_court"


class WorldUpdateRequest(BaseModel):
    name: Optional[str] = None
    # Legacy support (small worlds only). Prefer /worlds/{id}/draw for edits.
    grid: Optional[List[List[str]]] = None
    agent_placements: Optional[List[WorldAgentPlacement]] = None
    pois: Optional[List["WorldPOI"]] = None
    identities: Optional[List["WorldIdentity"]] = None
    agent_identities: Optional[Dict[str, str]] = None


WorldPOIKind = Literal[
    "custom",
    "cafeteria",
    "dorm",
    "classroom",
    "library",
    "office",
    "sports",
]


class WorldPOI(BaseModel):
    id: str
    name: str
    kind: WorldPOIKind = "custom"
    label: Optional["WorldColorLabel"] = None
    # Area definition
    shape: Literal["point", "rect", "cells"] = "point"
    # Anchor cell (also used for point POIs)
    x: int
    y: int
    # rect
    w: Optional[int] = None
    h: Optional[int] = None
    # cells
    cells: Optional[List["PathPoint"]] = None
    description: Optional[str] = None


class WorldPOICreateRequest(BaseModel):
    name: str
    kind: WorldPOIKind = "custom"
    label: Optional["WorldColorLabel"] = None
    shape: Literal["point", "rect", "cells"] = "point"
    x: int
    y: int
    w: Optional[int] = None
    h: Optional[int] = None
    cells: Optional[List["PathPoint"]] = None
    description: Optional[str] = None


class WorldPOIUpdateRequest(BaseModel):
    name: Optional[str] = None
    kind: Optional[WorldPOIKind] = None
    label: Optional["WorldColorLabel"] = None
    shape: Optional[Literal["point", "rect", "cells"]] = None
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None
    cells: Optional[List["PathPoint"]] = None
    description: Optional[str] = None


class WorldPOIsResponse(BaseModel):
    pois: List[WorldPOI]


class PlanPathToPOIRequest(BaseModel):
    agent_id: str
    poi_id: str
    max_radius: int = Field(default=8, ge=0, le=50)


class PlanPathToPOIResponse(BaseModel):
    poi: WorldPOI
    target: "PathPoint"
    path: List["PathPoint"]


WorldIdentityKind = Literal["student", "teacher", "custom"]


class WorldIdentityScheduleItem(BaseModel):
    # inclusive start hour, exclusive end hour
    start_hour: int = Field(ge=0, le=24)
    end_hour: int = Field(ge=0, le=24)
    activity: str
    # Preferred POI kinds for this activity
    poi_kinds: List[WorldPOIKind] = []


class WorldIdentity(BaseModel):
    id: str
    name: str
    kind: WorldIdentityKind = "custom"
    description: Optional[str] = None
    schedule: List[WorldIdentityScheduleItem] = []


class WorldIdentitiesResponse(BaseModel):
    identities: List[WorldIdentity]


class WorldIdentityCreateRequest(BaseModel):
    name: str
    kind: WorldIdentityKind = "custom"
    description: Optional[str] = None
    schedule: List[WorldIdentityScheduleItem] = []


class WorldIdentityUpdateRequest(BaseModel):
    name: Optional[str] = None
    kind: Optional[WorldIdentityKind] = None
    description: Optional[str] = None
    schedule: Optional[List[WorldIdentityScheduleItem]] = None


class SetWorldAgentIdentityRequest(BaseModel):
    agent_id: str
    identity_id: str


class PathPoint(BaseModel):
    x: int
    y: int


WorldLayer = Literal["wall", "color"]
WorldShape = Literal["cell", "cells", "rect", "line"]
WorldColorLabel = Literal["none", "neutral", "primary", "success", "warning", "error", "info"]


WorldScriptCommandType = Literal[
    "fill_rect",
    "border_walls",
    "checkerboard",
    "random_choice",
]


class WorldScriptCommand(BaseModel):
    type: WorldScriptCommandType

    # optional region (absolute world coords). If omitted, uses current viewport.
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None

    # parameters
    color: Optional[WorldColorLabel] = None
    wall: Optional[bool] = None
    thickness: Optional[int] = Field(default=1, ge=1, le=10)

    # checkerboard
    color_a: Optional[WorldColorLabel] = None
    color_b: Optional[WorldColorLabel] = None
    cell_size: Optional[int] = Field(default=1, ge=1, le=20)

    # random_choice
    palette: Optional[List[WorldColorLabel]] = None
    probabilities: Optional[List[float]] = None
    seed: Optional[int] = None


class WorldDrawOp(BaseModel):
    layer: WorldLayer
    shape: WorldShape

    # cell/line start
    x: Optional[int] = None
    y: Optional[int] = None

    # rect/line end
    x2: Optional[int] = None
    y2: Optional[int] = None

    # cells list
    cells: Optional[List[PathPoint]] = None

    # wall settings
    wall: Optional[bool] = None

    # color settings
    color: Optional[WorldColorLabel] = None


class WorldDrawRequest(BaseModel):
    ops: List[WorldDrawOp]
    view_x: Optional[int] = None
    view_y: Optional[int] = None
    view_w: Optional[int] = None
    view_h: Optional[int] = None


class WorldViewResponse(BaseModel):
    x: int
    y: int
    width: int
    height: int
    walls: List[List[bool]]
    colors: List[List[Optional[WorldColorLabel]]]
    agent_placements: List[WorldAgentPlacement] = []


class WorldAIScriptRequest(BaseModel):
    prompt: str
    x: int
    y: int
    w: int
    h: int
    max_commands: int = Field(default=50, ge=1, le=200)
    max_cells: int = Field(default=20000, ge=100, le=200000)


class WorldAIScriptResponse(BaseModel):
    commands: List[WorldScriptCommand]
    view: WorldViewResponse


class WorldAIDrawRequest(BaseModel):
    prompt: str
    x: int
    y: int
    w: int
    h: int
    max_ops: int = Field(default=200, ge=1, le=2000)


class WorldAIDrawResponse(BaseModel):
    ops: List[WorldDrawOp]
    view: WorldViewResponse


WorldAIGenerateMode = Literal["auto", "script", "ops"]


class WorldAIGenerateRequest(BaseModel):
    prompt: str
    x: int
    y: int
    w: int
    h: int
    mode: WorldAIGenerateMode = "auto"
    max_commands: int = Field(default=40, ge=1, le=200)
    max_cells: int = Field(default=20000, ge=100, le=200000)
    max_ops: int = Field(default=400, ge=1, le=2000)


class WorldAIGenerateResponse(BaseModel):
    mode: WorldAIGenerateMode
    commands: List[WorldScriptCommand] = []
    ops: List[WorldDrawOp] = []
    view: WorldViewResponse


class WorldAIImageRequest(BaseModel):
    prompt: str
    x: int
    y: int
    w: int
    h: int
    # Optional: specify an agent id to use for image generation.
    agent_id: Optional[str] = None


class WorldAIImageResponse(BaseModel):
    agent_id: str
    image_url: str
    ops: List[WorldDrawOp] = []
    view: WorldViewResponse


class PlaceAgentRequest(BaseModel):
    agent_id: str
    x: int
    y: int


class MoveAgentRequest(BaseModel):
    agent_id: str
    to_x: int
    to_y: int


class PlanPathRequest(BaseModel):
    agent_id: str
    target_x: int
    target_y: int


class PlanPathResponse(BaseModel):
    path: List[PathPoint]


class PickPOIPathRequest(BaseModel):
    agent_id: str
    # Prefer these labels as POI seeds (e.g. cafeteria/classroom/library zones).
    labels: List[WorldColorLabel] = []
    # How to pick among multiple POIs.
    strategy: Literal["nearest", "random"] = "nearest"
    # Limit scanning/attempts to keep requests fast on large maps.
    max_seed_cells: int = Field(default=800, ge=1, le=20000)
    max_attempts: int = Field(default=60, ge=1, le=500)
    # If POI cells are blocked (e.g. buildings), search nearby walkable cells.
    max_radius: int = Field(default=8, ge=0, le=50)


class PickPOIPathResponse(BaseModel):
    label: Optional[WorldColorLabel] = None
    poi: Optional[PathPoint] = None
    target: PathPoint
    path: List[PathPoint]


class WorldResponse(BaseModel):
    id: str
    name: str
    width: int
    height: int
    # Sparse representation metadata.
    walls_count: int = 0
    colors_count: int = 0
    agent_placements: List[WorldAgentPlacement] = []
    pois: List["WorldPOI"] = []
    identities: List["WorldIdentity"] = []
    agent_identities: Dict[str, str] = {}


def _coord_key(x: int, y: int) -> str:
    return f"{x},{y}"


def _campus_layout(width: int, height: int):
    campus_w = min(140, width)
    campus_h = min(96, height)
    ox = max(0, (width - campus_w) // 2)
    oy = max(0, (height - campus_h) // 2)

    x0, y0 = ox, oy
    x1, y1 = ox + campus_w - 1, oy + campus_h - 1
    cx = ox + campus_w // 2
    cy = oy + campus_h // 2

    buildings = [
        # North-west academic zone
        {"id": "poi_library", "name": "图书馆", "kind": "library", "label": "primary", "x": ox + 8, "y": oy + 10, "w": 24, "h": 16, "door": "e"},
        {"id": "poi_office", "name": "行政/办公楼", "kind": "office", "label": "primary", "x": ox + 10, "y": oy + 30, "w": 22, "h": 14, "door": "e"},

        # North-east teaching buildings
        {"id": "poi_teach_1", "name": "一教", "kind": "classroom", "label": "info", "x": ox + campus_w - 34, "y": oy + 10, "w": 26, "h": 14, "door": "w"},
        {"id": "poi_teach_2", "name": "二教", "kind": "classroom", "label": "info", "x": ox + campus_w - 34, "y": oy + 28, "w": 26, "h": 14, "door": "w"},
        {"id": "poi_teach_3", "name": "实验/教学楼", "kind": "classroom", "label": "info", "x": ox + campus_w - 40, "y": oy + 46, "w": 32, "h": 14, "door": "w"},

        # South-west dorm blocks
        {"id": "poi_dorm_a", "name": "宿舍A", "kind": "dorm", "label": "error", "x": ox + 8, "y": oy + campus_h - 34, "w": 26, "h": 16, "door": "e"},
        {"id": "poi_dorm_b", "name": "宿舍B", "kind": "dorm", "label": "error", "x": ox + 8, "y": oy + campus_h - 18, "w": 26, "h": 12, "door": "e"},

        # South-east life zone
        {"id": "poi_cafe", "name": "食堂", "kind": "cafeteria", "label": "warning", "x": ox + campus_w - 40, "y": oy + campus_h - 30, "w": 32, "h": 16, "door": "w"},
        {"id": "poi_store", "name": "生活服务区", "kind": "custom", "label": "warning", "x": ox + campus_w - 40, "y": oy + campus_h - 12, "w": 18, "h": 10, "door": "w"},
    ]

    sports = {"id": "poi_sports", "name": "操场", "kind": "sports", "label": "success", "x": cx - 20, "y": y0 + 6, "w": 40, "h": 20}

    return {
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "cx": cx,
        "cy": cy,
        "buildings": buildings,
        "sports": sports,
    }


def make_campus_default_pois(width: int, height: int) -> List[Dict]:
    """Default campus POIs (rect areas) with stable ids & names."""
    layout = _campus_layout(width, height)
    out: List[Dict] = []
    for b in layout["buildings"]:
        out.append(
            {
                "id": b["id"],
                "name": b["name"],
                "kind": b["kind"],
                "label": b.get("label"),
                "shape": "rect",
                "x": int(b["x"]),
                "y": int(b["y"]),
                "w": int(b["w"]),
                "h": int(b["h"]),
                "description": None,
            }
        )
    s = layout["sports"]
    out.append(
        {
            "id": s["id"],
            "name": s["name"],
            "kind": s["kind"],
            "label": s.get("label"),
            "shape": "rect",
            "x": int(s["x"]),
            "y": int(s["y"]),
            "w": int(s["w"]),
            "h": int(s["h"]),
            "description": None,
        }
    )
    return out


def make_preset_layers(width: int, height: int, preset: Optional[str]):
    """Return (walls, colors) where walls is a list of "x,y" strings and colors is a dict key->label."""
    walls = set()
    colors: Dict[str, WorldColorLabel] = {}

    if preset == "basketball_court":
        # Court roughly ~80 tiles wide, centered.
        court_w = min(80, width)
        court_h = min(50, height)
        ox = max(0, (width - court_w) // 2)
        oy = max(0, (height - court_h) // 2)
        # Fill color
        for yy in range(oy, oy + court_h):
            for xx in range(ox, ox + court_w):
                colors[_coord_key(xx, yy)] = "neutral"
        # Boundary walls
        for xx in range(ox, ox + court_w):
            walls.add(_coord_key(xx, oy))
            walls.add(_coord_key(xx, oy + court_h - 1))
        for yy in range(oy, oy + court_h):
            walls.add(_coord_key(ox, yy))
            walls.add(_coord_key(ox + court_w - 1, yy))

    if preset == "soccer_field":
        # Soccer field: green fill + visible markings + goal openings/posts.
        # Notes:
        # - We use the color layer for field + lines (better visual contrast than walls).
        # - We use walls only for goal posts (so they stand out and also block pathing).
        field_w = min(100, width)
        field_h = min(64, height)
        ox = max(0, (width - field_w) // 2)
        oy = max(0, (height - field_h) // 2)

        x0, y0 = ox, oy
        x1, y1 = ox + field_w - 1, oy + field_h - 1
        cx, cy = ox + field_w // 2, oy + field_h // 2

        line: WorldColorLabel = "info"
        grass: WorldColorLabel = "success"

        # Fill grass
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                colors[_coord_key(xx, yy)] = grass

        # Goal openings
        goal_gap = max(6, min(12, field_h // 6))
        g_top = max(y0 + 2, cy - goal_gap // 2)
        g_bot = min(y1 - 2, g_top + goal_gap)

        # Boundary lines (skip goal gaps on left/right)
        for xx in range(x0, x1 + 1):
            colors[_coord_key(xx, y0)] = line
            colors[_coord_key(xx, y1)] = line
        for yy in range(y0, y1 + 1):
            if not (g_top <= yy <= g_bot):
                colors[_coord_key(x0, yy)] = line
                colors[_coord_key(x1, yy)] = line

        # Center line
        for yy in range(y0 + 1, y1):
            colors[_coord_key(cx, yy)] = line

        # Center circle (outline)
        r = max(6, min(12, min(field_w, field_h) // 6))
        x = r
        y = 0
        d = 1 - r

        def plot_circle_points(px: int, py: int):
            pts = [
                (cx + px, cy + py),
                (cx - px, cy + py),
                (cx + px, cy - py),
                (cx - px, cy - py),
                (cx + py, cy + px),
                (cx - py, cy + px),
                (cx + py, cy - px),
                (cx - py, cy - px),
            ]
            for ax, ay in pts:
                if x0 <= ax <= x1 and y0 <= ay <= y1:
                    colors[_coord_key(ax, ay)] = line

        while x >= y:
            plot_circle_points(x, y)
            y += 1
            if d <= 0:
                d += 2 * y + 1
            else:
                x -= 1
                d += 2 * (y - x) + 1

        # Penalty boxes + goal areas (outline rectangles)
        def draw_rect_outline(rx0: int, ry0: int, rx1: int, ry1: int):
            rx0 = max(x0 + 1, min(rx0, x1 - 1))
            rx1 = max(x0 + 1, min(rx1, x1 - 1))
            ry0 = max(y0 + 1, min(ry0, y1 - 1))
            ry1 = max(y0 + 1, min(ry1, y1 - 1))
            if rx0 > rx1:
                rx0, rx1 = rx1, rx0
            if ry0 > ry1:
                ry0, ry1 = ry1, ry0
            for xx in range(rx0, rx1 + 1):
                colors[_coord_key(xx, ry0)] = line
                colors[_coord_key(xx, ry1)] = line
            for yy in range(ry0, ry1 + 1):
                colors[_coord_key(rx0, yy)] = line
                colors[_coord_key(rx1, yy)] = line

        # Sizes tuned for our ~100x64 field
        pen_depth = max(14, min(20, field_w // 5))
        pen_w = max(28, min(44, field_h - 10))
        goal_depth = max(6, min(10, field_w // 10))
        goal_w = max(14, min(22, field_h - 14))

        py0 = cy - pen_w // 2
        py1 = py0 + pen_w

        gy0 = cy - goal_w // 2
        gy1 = gy0 + goal_w

        # Left side
        draw_rect_outline(x0 + 1, py0, x0 + pen_depth, py1)
        draw_rect_outline(x0 + 1, gy0, x0 + goal_depth, gy1)
        # Right side
        draw_rect_outline(x1 - pen_depth, py0, x1 - 1, py1)
        draw_rect_outline(x1 - goal_depth, gy0, x1 - 1, gy1)

        # Goal posts as walls at the gap corners
        walls.add(_coord_key(x0, g_top))
        walls.add(_coord_key(x0, g_bot))
        walls.add(_coord_key(x1, g_top))
        walls.add(_coord_key(x1, g_bot))

    if preset == "campus":
        # Campus: richer top-down layout with multiple building types + roads/plaza.
        layout = _campus_layout(width, height)
        x0, y0, x1, y1 = layout["x0"], layout["y0"], layout["x1"], layout["y1"]
        cx, cy = layout["cx"], layout["cy"]

        road: WorldColorLabel = "neutral"
        outline: WorldColorLabel = "info"

        # Main cross roads + a light ring road
        road_w = 6
        for yy in range(y0, y1 + 1):
            for xx in range(cx - road_w // 2, cx + road_w // 2 + 1):
                if x0 <= xx <= x1:
                    colors[_coord_key(xx, yy)] = road
        for xx in range(x0, x1 + 1):
            for yy in range(cy - road_w // 2, cy + road_w // 2 + 1):
                if y0 <= yy <= y1:
                    colors[_coord_key(xx, yy)] = road

        for xx in range(x0, x1 + 1):
            colors[_coord_key(xx, y0)] = road
            colors[_coord_key(xx, y1)] = road
        for yy in range(y0, y1 + 1):
            colors[_coord_key(x0, yy)] = road
            colors[_coord_key(x1, yy)] = road

        def add_building_rect(rx0: int, ry0: int, rw: int, rh: int, fill: WorldColorLabel, door: str = "e"):
            bx0 = max(x0 + 2, min(int(rx0), x1 - 2))
            by0 = max(y0 + 2, min(int(ry0), y1 - 2))
            bx1 = max(x0 + 2, min(int(rx0 + rw - 1), x1 - 2))
            by1 = max(y0 + 2, min(int(ry0 + rh - 1), y1 - 2))
            if bx0 > bx1:
                bx0, bx1 = bx1, bx0
            if by0 > by1:
                by0, by1 = by1, by0

            # Fill interior with semantic color (walkable)
            for yy in range(by0 + 1, by1):
                for xx in range(bx0 + 1, bx1):
                    colors[_coord_key(xx, yy)] = fill

            # Walls on border with a simple door opening
            door_x, door_y = None, None
            if door == "e":
                door_x, door_y = bx1, (by0 + by1) // 2
            elif door == "w":
                door_x, door_y = bx0, (by0 + by1) // 2
            elif door == "n":
                door_x, door_y = (bx0 + bx1) // 2, by0
            elif door == "s":
                door_x, door_y = (bx0 + bx1) // 2, by1

            for xx in range(bx0, bx1 + 1):
                if not (door_x == xx and door_y == by0):
                    walls.add(_coord_key(xx, by0))
                if not (door_x == xx and door_y == by1):
                    walls.add(_coord_key(xx, by1))
                colors[_coord_key(xx, by0)] = outline
                colors[_coord_key(xx, by1)] = outline
            for yy in range(by0, by1 + 1):
                if not (door_x == bx0 and door_y == yy):
                    walls.add(_coord_key(bx0, yy))
                if not (door_x == bx1 and door_y == yy):
                    walls.add(_coord_key(bx1, yy))
                colors[_coord_key(bx0, yy)] = outline
                colors[_coord_key(bx1, yy)] = outline

            # Ensure door cell is walkable road
            if door_x is not None and door_y is not None:
                walls.discard(_coord_key(door_x, door_y))
                colors[_coord_key(door_x, door_y)] = road

        # Buildings
        for b in layout["buildings"]:
            fill = (b.get("label") or "neutral")
            add_building_rect(b["x"], b["y"], b["w"], b["h"], fill, b.get("door") or "e")

        # Sports field (open, semantic)
        s = layout["sports"]
        sfx0, sfy0 = int(s["x"]), int(s["y"])
        sfx1, sfy1 = sfx0 + int(s["w"]) - 1, sfy0 + int(s["h"]) - 1
        for yy in range(sfy0, sfy1 + 1):
            for xx in range(sfx0, sfx1 + 1):
                if x0 <= xx <= x1 and y0 <= yy <= y1:
                    colors[_coord_key(xx, yy)] = "success"
                    walls.discard(_coord_key(xx, yy))

        # Central plaza
        plaza_w, plaza_h = 22, 14
        px0 = cx - plaza_w // 2
        py0 = cy - plaza_h // 2
        px1 = px0 + plaza_w - 1
        py1 = py0 + plaza_h - 1
        for yy in range(py0, py1 + 1):
            for xx in range(px0, px1 + 1):
                if x0 <= xx <= x1 and y0 <= yy <= y1:
                    colors[_coord_key(xx, yy)] = road
                    walls.discard(_coord_key(xx, yy))

    return sorted(walls), colors

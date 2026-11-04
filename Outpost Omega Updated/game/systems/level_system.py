"""LevelSystem: tile map, enemy routes and the A* grid for one sector.

Level files live in data/levels/<id>.json. "tiles" is a list of 20 strings,
40 characters each (legend in settings.py). Enemy waypoints are NOT written
by hand: A* walks the painted path tiles from each S (spawn) to C (core)
and the corners become waypoints, so editing the map changes the routes.

Several S tiles = several lanes (Sector 2). Lanes are numbered top-to-bottom,
then left-to-right, and wave groups pick one with "lane": 0 / 1 / ...

"wall_events" (Sector 3) grow or clear hive walls during a wave:
    {"wave": 3, "time": 6, "grow": [[13, 10]], "clear": [], "message": "..."}
Grown walls block path tiles; A* recomputes every lane's route and the
EnemySystem reroutes aliens that are already walking. An event that would
cut a lane off from the Core entirely is skipped.
"""
import json
import math
import os
import random

import pygame

from .. import settings as S
from . import procgen
from ..core.pathfinding import astar, compress_path

SOLID_TILES = {S.T_BLOCK, S.T_CORE, S.T_WALL, S.T_CRYSTAL}
BUILDABLE_TILES = {S.T_BUILD, S.T_ICE, S.T_HIGH, S.T_RESOURCE}
PATH_TILES = {S.T_PATH, S.T_SPAWN}

# Colors per sector theme: (ground, ground speckle dark, speckle light, grid,
#                           path, path dark, rock, rock dark)
THEMES = {
    "desert": dict(ground=S.SAND, dark=S.SAND_DARK, light=S.SAND_LIGHT, grid=S.SAND_DARK,
                   path=S.PATH, path_dark=S.PATH_DARK, rock=S.ROCK, rock_dark=S.ROCK_DARK),
    "frozen": dict(ground=(218, 230, 240), dark=(190, 206, 222), light=(245, 250, 255),
                   grid=(196, 212, 228), path=(108, 122, 146), path_dark=(84, 96, 120),
                   rock=(120, 132, 150), rock_dark=(84, 94, 112)),
    "hive":   dict(ground=(74, 58, 72), dark=(60, 46, 60), light=(96, 120, 70),
                   grid=(62, 48, 62), path=(120, 70, 96), path_dark=(92, 50, 74),
                   rock=(104, 84, 98), rock_dark=(66, 52, 64)),
    "magma":  dict(ground=(58, 44, 44), dark=(44, 32, 32), light=(120, 64, 40),
                   grid=(72, 54, 52), path=(96, 76, 66), path_dark=(66, 50, 44),
                   rock=(84, 64, 58), rock_dark=(52, 40, 36), hazard="lava"),
    "orbital": dict(ground=(70, 78, 96), dark=(58, 64, 80), light=(96, 104, 124),
                   grid=(84, 92, 112), path=(46, 52, 66), path_dark=(34, 38, 50),
                   rock=(120, 110, 90), rock_dark=(80, 72, 60), wall_style="door"),
    "derelict": dict(ground=(48, 52, 60), dark=(38, 40, 48), light=(70, 76, 66),
                     grid=(58, 62, 72), path=(78, 72, 66), path_dark=(56, 52, 48),
                     rock=(90, 84, 80), rock_dark=(60, 56, 52)),
    "twin":   dict(ground=(84, 76, 108), dark=(70, 62, 92), light=(110, 100, 140),
                   grid=(76, 68, 100), path=(126, 108, 90), path_dark=(98, 84, 70),
                   rock=(104, 96, 120), rock_dark=(70, 64, 84)),
    "jungle": dict(ground=(46, 92, 52), dark=(34, 72, 40), light=(80, 130, 60),
                   grid=(40, 82, 46), path=(104, 84, 56), path_dark=(80, 62, 40),
                   rock=(70, 88, 64), rock_dark=(44, 58, 40)),
    "crystal": dict(ground=(52, 50, 78), dark=(40, 38, 62), light=(90, 110, 150),
                    grid=(60, 58, 90), path=(86, 80, 100), path_dark=(64, 58, 78),
                    rock=(96, 90, 110), rock_dark=(62, 58, 74)),
    "ruins":  dict(ground=(110, 104, 96), dark=(90, 84, 78), light=(132, 126, 116),
                   grid=(98, 92, 86), path=(70, 68, 66), path_dark=(52, 50, 48),
                   rock=(128, 112, 96), rock_dark=(90, 78, 66), wall_style="door"),
    "gas":    dict(ground=(120, 92, 70), dark=(100, 74, 56), light=(170, 130, 96),
                   grid=(110, 84, 64), path=(70, 76, 92), path_dark=(52, 56, 70),
                   rock=(140, 120, 100), rock_dark=(96, 82, 66)),
    "plains": dict(ground=(98, 142, 74), dark=(82, 122, 62), light=(126, 168, 92),
                   grid=(88, 130, 68), path=(150, 128, 86), path_dark=(122, 102, 66),
                   rock=(110, 108, 100), rock_dark=(76, 74, 70)),
}


CUSTOM_LEVEL_DIR = os.path.join(S.ROOT_DIR, "mods", "levels")   # maps made in the Map Editor


def level_path(level_id):
    path = os.path.join(S.LEVEL_DIR, f"{level_id}.json")
    if not os.path.exists(path):
        custom = os.path.join(CUSTOM_LEVEL_DIR, f"{level_id}.json")
        if os.path.exists(custom):
            return custom
    return path


def level_exists(level_id):
    return level_id.startswith("proc_") or os.path.exists(level_path(level_id))


def load_level_data(level_id):
    """A level file, or a procedural sector for ids like "proc_12345"."""
    if level_id.startswith("proc_"):
        return procgen.generate(int(level_id[5:]))
    with open(level_path(level_id), "r", encoding="utf-8") as f:
        return json.load(f)


class LevelSystem:
    def __init__(self, events, level_id):
        self.events = events
        self.data = load_level_data(level_id)
        self.id = level_id
        self.name = self.data.get("name", level_id)
        self.theme = THEMES.get(self.data.get("theme", "desert"), THEMES["desert"])
        rows = self.data["tiles"]
        self.height = len(rows)
        self.width = len(rows[0])
        if (self.width, self.height) != (S.GRID_W, S.GRID_H):
            raise ValueError(f"{level_id}: map must be {S.GRID_W}x{S.GRID_H} tiles")
        self.tiles = [list(r) for r in rows]
        # Enemies may only walk on path tiles unless the level allows
        # free movement across open ground.
        self.free_path = self.data.get("free_path", False)
        self.weather_ice = False    # Blizzard weather makes every tile slippery
        self.occupied = {}   # (tx, ty) -> Tower
        self.digs = 0        # shortcuts dug by Pathcutters / the Architect
        self.spawn_tiles = sorted(self._find_all(S.T_SPAWN), key=lambda t: (t[1], t[0]))
        self.core_tiles = sorted(self._find_all(S.T_CORE), key=lambda t: (t[1], t[0]))
        if not self.spawn_tiles or not self.core_tiles:
            raise ValueError(f"{level_id}: needs at least one 'S' spawn and one 'C' core")
        self.core_tile = self.core_tiles[0]
        # Which Core each lane heads for (Twin Cores). Default: the nearest one.
        lane_cores = self.data.get("lane_cores")
        self.lane_goals = []
        for i, sp in enumerate(self.spawn_tiles):
            if lane_cores and i < len(lane_cores):
                self.lane_goals.append(self.core_tiles[lane_cores[i] % len(self.core_tiles)])
            else:
                self.lane_goals.append(min(self.core_tiles,
                                           key=lambda c: abs(c[0] - sp[0]) + abs(c[1] - sp[1])))
        self.dark = self.data.get("dark", False)          # Derelict Ship: only lit areas are visible
        self.conveyors = {}                               # (tx, ty) -> (dx, dy)
        for belt in self.data.get("conveyors", []):
            for t in belt["tiles"]:
                self.conveyors[tuple(t)] = tuple(belt["dir"])
        self.wall_events = [dict(e, done=False) for e in self.data.get("wall_events", [])]
        # Phase 5 map features (MapFeatures drives them): gates Vance can flip, teleporters
        self.gates = [{"tiles": [tuple(t) for t in g["tiles"]], "switch": tuple(g["switch"]),
                       "open": g.get("open", True)} for g in self.data.get("gates", [])]
        for g in self.gates:
            for tx, ty in g["tiles"]:
                self.tiles[ty][tx] = S.T_PATH if g["open"] else S.T_WALL
        self.teleporters = [(tuple(a), tuple(b)) for a, b in self.data.get("teleporters", [])]
        self.routes = []          # one waypoint list per lane
        self.route_tiles = []     # one tile list per lane (for debug drawing)
        self.recompute_path(announce=False)
        self.surface = None
        self.rebuild_surface()

    # ---- lookups ---------------------------------------------------------
    def _find_all(self, ch):
        return [(x, y) for y, row in enumerate(self.tiles) for x, c in enumerate(row) if c == ch]

    def in_bounds(self, tx, ty):
        return 0 <= tx < self.width and 0 <= ty < self.height

    def tile_at(self, tx, ty):
        if not self.in_bounds(tx, ty):
            return S.T_BLOCK
        return self.tiles[ty][tx]

    @staticmethod
    def world_to_tile(x, y):
        return int(x // S.TILE), int(y // S.TILE)

    @staticmethod
    def tile_center(tx, ty):
        return (tx * S.TILE + S.TILE / 2, ty * S.TILE + S.TILE / 2)

    @property
    def lane_count(self):
        return len(self.routes)

    @property
    def waypoints(self):
        """Lane 0's route (kept for code that only needs one route)."""
        return self.routes[0]

    @property
    def spawn_pos(self):
        return self.routes[0][0]

    def route_for(self, lane):
        return self.routes[lane % len(self.routes)]

    @property
    def core_pos(self):
        return self.tile_center(*self.core_tile)

    @property
    def core_positions(self):
        return [self.tile_center(*t) for t in self.core_tiles]

    def nearest_core_pos(self, x, y):
        return min(self.core_positions, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)

    def conveyor_at(self, x, y):
        """Belt direction under a world position, or None."""
        return self.conveyors.get(self.world_to_tile(x, y)) if self.conveyors else None

    def is_buildable(self, tx, ty):
        return self.tile_at(tx, ty) in BUILDABLE_TILES and (tx, ty) not in self.occupied

    def blocked_by_tower(self, tx, ty):
        """A tower stands here that can't be walked over (Tar Pits can)."""
        obj = self.occupied.get((tx, ty))
        return obj is not None and not getattr(obj, "walkable", False)

    def is_solid(self, tx, ty):
        """Solid for the Commander: rocks, walls, the Core and towers."""
        return self.tile_at(tx, ty) in SOLID_TILES or self.blocked_by_tower(tx, ty)

    def is_ice(self, tx, ty):
        return self.weather_ice or self.tile_at(tx, ty) == S.T_ICE

    def is_hazard(self, tx, ty):
        return self.tile_at(tx, ty) == S.T_HAZARD

    def enemy_walkable(self, tx, ty, extra_blocked=None):
        if extra_blocked and (tx, ty) in extra_blocked:
            return False
        ch = self.tile_at(tx, ty)
        if self.free_path:
            return ch not in SOLID_TILES and not self.blocked_by_tower(tx, ty)
        return ch in PATH_TILES

    # ---- pathing ---------------------------------------------------------
    def find_route(self, start, extra_blocked=None, goal=None):
        return astar(start, goal or self.core_tile,
                     lambda x, y: self.enemy_walkable(x, y, extra_blocked),
                     self.width, self.height)

    def _route_points(self, tiles, offscreen_start):
        pts = [self.tile_center(*t) for t in compress_path(tiles)]
        if offscreen_start and len(pts) > 1:
            # Start one tile off-screen so enemies walk in from the edge.
            sx, sy = pts[0]
            nx, ny = pts[1]
            dx = (sx - nx) and (1 if sx > nx else -1)
            dy = (sy - ny) and (1 if sy > ny else -1)
            pts.insert(0, (sx + dx * S.TILE, sy + dy * S.TILE))
        return pts

    def recompute_path(self, announce=True):
        routes, tiles_per_lane = [], []
        for spawn, goal in zip(self.spawn_tiles, self.lane_goals):
            tiles = self.find_route(spawn, goal=goal)
            if tiles is None:
                raise ValueError(f"{self.id}: no route from spawn {spawn} to the core")
            tiles_per_lane.append(tiles)
            routes.append(self._route_points(tiles, offscreen_start=True))
        self.routes = routes
        self.route_tiles = tiles_per_lane
        if announce:
            self.events.publish("path_changed", routes=routes)

    def route_from(self, x, y):
        """Fresh waypoints from a world position to the Core (for rerouting
        an enemy that is already on the path). None if it's cut off."""
        cx, cy = self.nearest_core_pos(x, y)
        tiles = self.find_route(self.world_to_tile(x, y), goal=self.world_to_tile(cx, cy))
        if tiles is None:
            return None
        pts = self._route_points(tiles, offscreen_start=False)
        return [(x, y)] + pts[1:] if len(pts) > 1 else [(x, y), self.core_pos]

    def all_lanes_connected(self, extra_blocked=None):
        return all(self.find_route(s, extra_blocked, goal=g) is not None
                   for s, g in zip(self.spawn_tiles, self.lane_goals))

    def placement_blocks_route(self, tx, ty):
        """True if putting something on (tx, ty) would cut enemies off."""
        if not self.enemy_walkable(tx, ty):
            return False
        return not self.all_lanes_connected(extra_blocked={(tx, ty)})

    def occupy(self, tx, ty, obj):
        self.occupied[(tx, ty)] = obj
        if self.free_path:
            self.recompute_path()

    def vacate(self, tx, ty):
        self.occupied.pop((tx, ty), None)
        if self.free_path:
            self.recompute_path()

    # ---- Pathcutter / Architect ----------------------------------------------
    @staticmethod
    def _between(a, b):
        """Tiles strictly between two tiles on the same row or column, else None."""
        (ax, ay), (bx, by) = a, b
        if ax == bx:
            step = 1 if by > ay else -1
            return [(ax, y) for y in range(ay + step, by, step)]
        if ay == by:
            step = 1 if bx > ax else -1
            return [(x, ay) for x in range(ax + step, bx, step)]
        return None

    def dig_shortcut(self, from_tile=None, fill=False, max_digs=3, min_saving=4):
        """Turn a straight run of open ground between two points of the route into path,
        if that skips at least min_saving tiles. fill=True also turns the stretch it
        bypassed back into buildable ground (the Architect). Returns True if dug."""
        if self.free_path or self.digs >= max_digs:
            return False
        best = None
        for lane, tiles in enumerate(self.route_tiles):
            if from_tile is None:
                i0 = 0
            else:
                i0 = min(range(len(tiles)), key=lambda i: abs(tiles[i][0] - from_tile[0])
                         + abs(tiles[i][1] - from_tile[1]))
            for i in range(i0, min(len(tiles), i0 + 30)):
                for j in range(i + min_saving + 2, len(tiles)):
                    mid = self._between(tiles[i], tiles[j])
                    if not mid:
                        continue
                    if any(self.tile_at(*t) not in BUILDABLE_TILES or t in self.occupied for t in mid):
                        continue
                    saving = (j - i) - (len(mid) + 1)
                    if saving >= min_saving and (best is None or saving > best[0]):
                        best = (saving, lane, i, j, mid)
        if best is None:
            return False
        _saving, lane, i, j, mid = best
        old = {}
        for tx, ty in mid:
            old[(tx, ty)] = self.tiles[ty][tx]
            self.tiles[ty][tx] = S.T_PATH
        if fill:
            others = {t for k, tiles in enumerate(self.route_tiles) if k != lane for t in tiles}
            for tx, ty in self.route_tiles[lane][i + 1:j]:
                if (tx, ty) not in others and (tx, ty) not in self.occupied and self.tiles[ty][tx] == S.T_PATH:
                    old[(tx, ty)] = self.tiles[ty][tx]
                    self.tiles[ty][tx] = S.T_BUILD
        if not self.all_lanes_connected():
            for (tx, ty), ch in old.items():
                self.tiles[ty][tx] = ch
            return False
        self.digs += 1
        self.rebuild_surface()
        self.recompute_path(announce=True)
        return True

    def architect_rebuild(self, from_tile):
        """Architect boss phase: reroute the path (fixed maps) or raise rock walls (Open Plains)."""
        if not self.free_path:
            return self.dig_shortcut(from_tile, fill=True, max_digs=99, min_saving=3) or \
                self.dig_shortcut(None, fill=True, max_digs=99, min_saving=3)
        spots = [t for tiles in self.route_tiles for t in tiles[3:-3]]
        random.shuffle(spots)
        placed = 0
        for tx, ty in spots:
            if placed >= 5:
                break
            if self.tile_at(tx, ty) not in BUILDABLE_TILES or (tx, ty) in self.occupied:
                continue
            old = self.tiles[ty][tx]
            self.tiles[ty][tx] = S.T_BLOCK   # a rock wall right where the aliens were walking
            if self.all_lanes_connected():
                placed += 1
            else:
                self.tiles[ty][tx] = old
        if placed:
            self.rebuild_surface()
            self.recompute_path(announce=True)
        return placed > 0

    # ---- hive walls (Sector 3) ---------------------------------------------
    def apply_wall_event(self, event):
        grow = [tuple(t) for t in event.get("grow", [])]
        clear = [tuple(t) for t in event.get("clear", [])]
        old = {t: self.tile_at(*t) for t in grow + clear}
        for tx, ty in clear:
            if self.tile_at(tx, ty) == S.T_WALL:
                self.tiles[ty][tx] = S.T_PATH
        for tx, ty in grow:
            if self.tile_at(tx, ty) in PATH_TILES:
                self.tiles[ty][tx] = S.T_WALL
        if not self.all_lanes_connected():
            for (tx, ty), ch in old.items():   # would trap the aliens: undo
                self.tiles[ty][tx] = ch
            return False
        self.rebuild_surface()
        self.recompute_path(announce=True)
        self.events.publish("walls_changed", grown=grow, cleared=clear,
                            message=event.get("message", "Hive walls are shifting!"))
        return True

    def on_update(self, dt, waves):
        """Fire any wall events that are due (checked against the wave clock)."""
        for ev in self.wall_events:
            if ev["done"]:
                continue
            due = (waves.wave_number > ev["wave"] or
                   (waves.wave_number == ev["wave"] and waves.phase == "wave"
                    and waves.wave_time >= ev.get("time", 0)))
            if due:
                ev["done"] = True
                self.apply_wall_event(ev)

    # ---- rendering -------------------------------------------------------
    def rebuild_surface(self):
        """Draw the whole tile map once into a cached Surface."""
        th = self.theme
        surf = pygame.Surface((S.MAP_W, S.MAP_H))
        rng = random.Random(sum(map(ord, self.id)))  # same look every run
        T = S.TILE
        for ty in range(self.height):
            for tx in range(self.width):
                ch = self.tiles[ty][tx]
                rect = pygame.Rect(tx * T, ty * T, T, T)
                if ch in PATH_TILES:
                    self._draw_path(surf, rect, tx, ty, rng)
                    continue
                surf.fill(th["ground"], rect)
                for _ in range(4):
                    px = rect.x + rng.randrange(T)
                    py = rect.y + rng.randrange(T)
                    shade = th["dark"] if rng.random() < 0.6 else th["light"]
                    surf.fill(shade, (px, py, 2, 2))
                if ch == S.T_ICE:
                    self._draw_ice(surf, rect, rng)
                elif ch == S.T_HIGH:   # raised plateau / rooftop
                    surf.fill(th["light"], rect.inflate(-2, -2))
                    pygame.draw.line(surf, th["rock_dark"], rect.bottomleft, rect.bottomright, 3)
                    pygame.draw.line(surf, th["rock_dark"], rect.topright, rect.bottomright, 2)
                elif ch == S.T_RESOURCE:
                    pygame.draw.circle(surf, th["dark"], rect.center, 11)
                    for k in range(3):
                        cx, cy = rect.centerx - 6 + k * 6, rect.centery + (k % 2) * 4 - 2
                        pygame.draw.polygon(surf, S.ENERGY, [(cx, cy - 6), (cx + 3, cy), (cx, cy + 4), (cx - 3, cy)])
                elif ch == S.T_CRYSTAL:
                    cx, cy = rect.center
                    for k, (dx, h) in enumerate(((-7, 16), (0, 24), (7, 14))):
                        col = ((120, 200, 255), (190, 230, 255), (150, 120, 255))[k]
                        pygame.draw.polygon(surf, (30, 30, 60), [(cx + dx - 5, cy + 12), (cx + dx, cy + 12 - h - 1),
                                                                 (cx + dx + 5, cy + 12)])
                        pygame.draw.polygon(surf, col, [(cx + dx - 4, cy + 11), (cx + dx, cy + 12 - h),
                                                        (cx + dx + 4, cy + 11)])
                if ch in BUILDABLE_TILES:
                    pygame.draw.rect(surf, th["grid"], rect, 1)
                elif ch == S.T_BLOCK:
                    self._draw_rock(surf, rect, rng)
                elif ch == S.T_HAZARD:
                    if th.get("hazard") == "lava":
                        self._draw_lava(surf, rect, rng)
                    else:
                        self._draw_acid(surf, rect, rng)
                elif ch == S.T_WALL and th.get("wall_style") == "door":
                    self._draw_door(surf, rect)
                elif ch == S.T_WALL:
                    self._draw_hive_wall(surf, rect, tx, ty, rng)
        # Conveyor belts (Orbital Platform): chevrons pointing the way they push.
        for (tx, ty), (dx, dy) in self.conveyors.items():
            cx, cy = self.tile_center(tx, ty)
            for k in (-7, 5):
                px, py = cx + dx * k, cy + dy * k
                pts = [(px - dx * 4 - dy * 6, py - dy * 4 - dx * 6), (px + dx * 4, py + dy * 4),
                       (px - dx * 4 + dy * 6, py - dy * 4 + dx * 6)]
                pygame.draw.lines(surf, S.ENERGY, False, pts, 2)
        # Core landing pads.
        for core in self.core_tiles:
            cx, cy = self.tile_center(*core)
            pygame.draw.circle(surf, S.STEEL_DARK, (int(cx), int(cy)), 34)
            pygame.draw.circle(surf, S.STEEL, (int(cx), int(cy)), 34, 2)
        self.surface = surf

    def _draw_path(self, surf, rect, tx, ty, rng):
        th = self.theme
        surf.fill(th["path"], rect)
        for _ in range(3):
            surf.fill(th["path_dark"], (rect.x + rng.randrange(30), rect.y + rng.randrange(30), 3, 2))
        # Darker edge where the path meets ground.
        for dx, dy, edge in ((-1, 0, (rect.left, rect.top, 2, rect.h)),
                             (1, 0, (rect.right - 2, rect.top, 2, rect.h)),
                             (0, -1, (rect.left, rect.top, rect.w, 2)),
                             (0, 1, (rect.left, rect.bottom - 2, rect.w, 2))):
            n = self.tile_at(tx + dx, ty + dy) if self.in_bounds(tx + dx, ty + dy) else S.T_PATH
            if n not in PATH_TILES and n not in (S.T_CORE, S.T_WALL):
                surf.fill(th["path_dark"], edge)

    def _draw_rock(self, surf, rect, rng):
        cx, cy = rect.center
        pts = []
        for i in range(7):
            ang = i / 7 * 6.283
            r = rng.uniform(10, 14)
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        pygame.draw.polygon(surf, self.theme["rock_dark"], [(x + 1, y + 2) for x, y in pts])
        pygame.draw.polygon(surf, self.theme["rock"], pts)
        pygame.draw.circle(surf, S.STEEL_LIGHT, (cx - 4, cy - 4), 2)

    @staticmethod
    def _draw_ice(surf, rect, rng):
        surf.fill(S.ICE, rect)
        for _ in range(2):   # glints
            x = rect.x + rng.randrange(4, 26)
            y = rect.y + rng.randrange(4, 26)
            pygame.draw.line(surf, S.WHITE, (x, y), (x + 5, y - 5), 1)

    @staticmethod
    def _draw_lava(surf, rect, rng):
        pygame.draw.ellipse(surf, (90, 30, 16), rect.inflate(-2, -6))
        pygame.draw.ellipse(surf, S.ORANGE, rect.inflate(-6, -10))
        for _ in range(2):
            pygame.draw.circle(surf, S.ENERGY,
                               (rect.x + rng.randrange(8, 24), rect.y + rng.randrange(10, 22)), 2)

    @staticmethod
    def _draw_acid(surf, rect, rng):
        pygame.draw.ellipse(surf, (40, 90, 30), rect.inflate(-2, -6))
        pygame.draw.ellipse(surf, S.ACID, rect.inflate(-6, -10))
        for _ in range(2):
            pygame.draw.circle(surf, (200, 255, 150),
                               (rect.x + rng.randrange(8, 24), rect.y + rng.randrange(10, 22)), 2)

    @staticmethod
    def _draw_door(surf, rect):
        """A closed airlock (Orbital Platform)."""
        pygame.draw.rect(surf, (22, 22, 34), rect)
        pygame.draw.rect(surf, S.STEEL_DARK, rect.inflate(-2, -2))
        for i in range(0, rect.w, 8):
            pygame.draw.line(surf, S.ENERGY, (rect.x + i, rect.bottom - 3), (rect.x + i + 6, rect.y + 3), 3)
        pygame.draw.rect(surf, S.RED, (rect.centerx - 2, rect.y + 2, 4, 4))

    @staticmethod
    def _draw_hive_wall(surf, rect, tx, ty, rng):
        pygame.draw.rect(surf, (40, 10, 40), rect.inflate(-1, -1), border_radius=8)
        pygame.draw.rect(surf, S.MAGENTA_DARK, rect.inflate(-4, -4), border_radius=8)
        for _ in range(3):   # organic bumps
            c = (rect.x + rng.randrange(6, 26), rect.y + rng.randrange(6, 26))
            pygame.draw.circle(surf, S.MAGENTA, c, rng.randrange(3, 6))
        pygame.draw.circle(surf, S.ALIEN_GREEN, (rect.centerx, rect.centery), 2)

    def on_render(self, screen, offset=(0, 0)):
        screen.blit(self.surface, offset)

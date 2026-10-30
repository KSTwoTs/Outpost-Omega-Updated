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
from ..core.pathfinding import astar, compress_path

SOLID_TILES = {S.T_BLOCK, S.T_CORE, S.T_WALL}
BUILDABLE_TILES = {S.T_BUILD, S.T_ICE}
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
}


def level_path(level_id):
    return os.path.join(S.LEVEL_DIR, f"{level_id}.json")


def level_exists(level_id):
    return os.path.exists(level_path(level_id))


class LevelSystem:
    def __init__(self, events, level_id):
        self.events = events
        with open(level_path(level_id), "r", encoding="utf-8") as f:
            self.data = json.load(f)
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
        self.occupied = {}   # (tx, ty) -> Tower
        self.spawn_tiles = sorted(self._find_all(S.T_SPAWN), key=lambda t: (t[1], t[0]))
        found_core = self._find_all(S.T_CORE)
        if not self.spawn_tiles or len(found_core) != 1:
            raise ValueError(f"{level_id}: needs at least one 'S' spawn and exactly one 'C' core")
        self.core_tile = found_core[0]
        self.wall_events = [dict(e, done=False) for e in self.data.get("wall_events", [])]
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

    def is_buildable(self, tx, ty):
        return self.tile_at(tx, ty) in BUILDABLE_TILES and (tx, ty) not in self.occupied

    def is_solid(self, tx, ty):
        """Solid for the Commander: rocks, walls, the Core and towers."""
        return self.tile_at(tx, ty) in SOLID_TILES or (tx, ty) in self.occupied

    def is_ice(self, tx, ty):
        return self.tile_at(tx, ty) == S.T_ICE

    def is_hazard(self, tx, ty):
        return self.tile_at(tx, ty) == S.T_HAZARD

    def enemy_walkable(self, tx, ty, extra_blocked=None):
        if extra_blocked and (tx, ty) in extra_blocked:
            return False
        ch = self.tile_at(tx, ty)
        if self.free_path:
            return ch not in SOLID_TILES and (tx, ty) not in self.occupied
        return ch in PATH_TILES

    # ---- pathing ---------------------------------------------------------
    def find_route(self, start, extra_blocked=None):
        return astar(start, self.core_tile,
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
        for spawn in self.spawn_tiles:
            tiles = self.find_route(spawn)
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
        tiles = self.find_route(self.world_to_tile(x, y))
        if tiles is None:
            return None
        pts = self._route_points(tiles, offscreen_start=False)
        return [(x, y)] + pts[1:] if len(pts) > 1 else [(x, y), self.core_pos]

    def all_lanes_connected(self, extra_blocked=None):
        return all(self.find_route(s, extra_blocked) is not None for s in self.spawn_tiles)

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
                if ch in BUILDABLE_TILES:
                    pygame.draw.rect(surf, th["grid"], rect, 1)
                elif ch == S.T_BLOCK:
                    self._draw_rock(surf, rect, rng)
                elif ch == S.T_HAZARD:
                    self._draw_acid(surf, rect, rng)
                elif ch == S.T_WALL:
                    self._draw_hive_wall(surf, rect, tx, ty, rng)
        # Core landing pad.
        cx, cy = self.tile_center(*self.core_tile)
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
    def _draw_acid(surf, rect, rng):
        pygame.draw.ellipse(surf, (40, 90, 30), rect.inflate(-2, -6))
        pygame.draw.ellipse(surf, S.ACID, rect.inflate(-6, -10))
        for _ in range(2):
            pygame.draw.circle(surf, (200, 255, 150),
                               (rect.x + rng.randrange(8, 24), rect.y + rng.randrange(10, 22)), 2)

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

"""CollisionSystem: spatial hash broad phase + circle/AABB narrow phase.

The hash is rebuilt once per frame from every targetable enemy, then
towers, projectiles and the Commander ask it for nearby enemies.
"""
import math

from .. import settings as S
from ..core.spatial_hash import SpatialHash, circles_overlap, dist_sq


class CollisionSystem:
    def __init__(self):
        self.hash = SpatialHash(S.HASH_CELL)
        self.enemies = []

    def rebuild(self, enemies):
        self.hash.clear()
        self.enemies = [e for e in enemies if e.targetable]
        for e in self.enemies:
            self.hash.insert(e, e.pos.x, e.pos.y, e.radius)

    # ---- enemy queries -----------------------------------------------------
    def enemies_touching(self, x, y, r, include_air=True):
        """Enemies touching the circle (x, y, r). Each enemy does its own
        narrow-phase test: circle-vs-circle for most, pygame.mask for the boss."""
        out = []
        for e in self.hash.query(x, y, r + 48):
            if e.flying and not include_air:
                continue
            if e.hit_test_circle(x, y, r):
                out.append(e)
        return out

    def enemies_in_range(self, x, y, rng, include_air=True):
        """Enemies whose center is within `rng` (squared distance, no sqrt)."""
        r2 = rng * rng
        out = []
        for e in self.hash.query(x, y, rng):
            if e.flying and not include_air:
                continue
            if dist_sq(x, y, e.pos.x, e.pos.y) <= r2:
                out.append(e)
        return out

    def nearest_enemy(self, x, y, rng, include_air=True):
        best, best_d = None, rng * rng
        for e in self.enemies_in_range(x, y, rng, include_air):
            d = dist_sq(x, y, e.pos.x, e.pos.y)
            if d <= best_d:
                best, best_d = e, d
        return best

    # ---- Commander vs tiles --------------------------------------------------
    @staticmethod
    def _box_hits(x, y, half, is_solid):
        T = S.TILE
        x0, x1 = int(math.floor((x - half) / T)), int(math.floor((x + half - 0.001) / T))
        y0, y1 = int(math.floor((y - half) / T)), int(math.floor((y + half - 0.001) / T))
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                if is_solid(tx, ty):
                    return (tx, ty)
        return None

    def move_box(self, x, y, half, dx, dy, is_solid):
        """Axis-separated AABB movement. Returns (x, y, hit_x, hit_y).

        Move on X, push out of any solid tile, then the same on Y. Doing the
        axes separately lets the Commander slide along walls.
        """
        T = S.TILE
        hit_x = hit_y = False
        x += dx
        tile = self._box_hits(x, y, half, is_solid)
        if tile:
            hit_x = True
            if dx > 0:
                x = tile[0] * T - half
            elif dx < 0:
                x = (tile[0] + 1) * T + half
        y += dy
        tile = self._box_hits(x, y, half, is_solid)
        if tile:
            hit_y = True
            if dy > 0:
                y = tile[1] * T - half
            elif dy < 0:
                y = (tile[1] + 1) * T + half
        return x, y, hit_x, hit_y

    @staticmethod
    def box_overlaps_tile(x, y, half, tx, ty):
        T = S.TILE
        return (x + half > tx * T and x - half < (tx + 1) * T and
                y + half > ty * T and y - half < (ty + 1) * T)

"""Broad-phase collision: a uniform grid of buckets (64 px cells).

Rebuilt every frame: clear(), insert() everything, then query() near a
point to get only the nearby candidates for the narrow-phase test.
"""
from collections import defaultdict


class SpatialHash:
    def __init__(self, cell_size=64):
        self.cell = cell_size
        self.buckets = defaultdict(list)

    def clear(self):
        self.buckets.clear()

    def _cells(self, x, y, r):
        c = self.cell
        x0, x1 = int((x - r) // c), int((x + r) // c)
        y0, y1 = int((y - r) // c), int((y + r) // c)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                yield (cx, cy)

    def insert(self, obj, x, y, r=0):
        for key in self._cells(x, y, r):
            self.buckets[key].append(obj)

    def query(self, x, y, r):
        """All objects whose cells overlap the circle's bounding box (no dupes)."""
        seen = set()
        out = []
        for key in self._cells(x, y, r):
            for obj in self.buckets.get(key, ()):
                oid = id(obj)
                if oid not in seen:
                    seen.add(oid)
                    out.append(obj)
        return out

    def occupied_cells(self):
        return [k for k, v in self.buckets.items() if v]


def circles_overlap(ax, ay, ar, bx, by, br):
    """Narrow phase: distance^2 < (r1 + r2)^2, no sqrt."""
    dx, dy = ax - bx, ay - by
    rr = ar + br
    return dx * dx + dy * dy < rr * rr


def dist_sq(ax, ay, bx, by):
    dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy

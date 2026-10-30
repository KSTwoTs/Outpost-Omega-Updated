"""A* pathfinding on the tile grid (Manhattan heuristic, 4-directional).

Sector 1 uses it to turn the painted path tiles into an ordered route and
to make sure a tower never fully blocks the route. Sector 3 will call it
again whenever hive walls grow.
"""
import heapq

NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(start, goal, is_walkable, width, height):
    """Return a list of (tx, ty) tiles from start to goal, or None.

    is_walkable(tx, ty) -> bool decides which tiles can be entered.
    The goal tile is always allowed so the Core can be "solid".
    """
    if start == goal:
        return [start]
    open_heap = [(manhattan(start, goal), 0, start)]
    came_from = {start: None}
    g_cost = {start: 0}
    counter = 0  # tie-breaker so heapq never compares tuples of equal f

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            return path[::-1]
        for dx, dy in NEIGHBORS:
            nx, ny = current[0] + dx, current[1] + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            nxt = (nx, ny)
            if nxt != goal and not is_walkable(nx, ny):
                continue
            new_g = g_cost[current] + 1
            if new_g < g_cost.get(nxt, 1 << 30):
                g_cost[nxt] = new_g
                came_from[nxt] = current
                counter += 1
                heapq.heappush(open_heap, (new_g + manhattan(nxt, goal), counter, nxt))
    return None


def compress_path(tiles):
    """Keep only the tiles where direction changes (corner waypoints)."""
    if len(tiles) <= 2:
        return list(tiles)
    out = [tiles[0]]
    for prev, cur, nxt in zip(tiles, tiles[1:], tiles[2:]):
        d1 = (cur[0] - prev[0], cur[1] - prev[1])
        d2 = (nxt[0] - cur[0], nxt[1] - cur[1])
        if d1 != d2:
            out.append(cur)
    out.append(tiles[-1])
    return out

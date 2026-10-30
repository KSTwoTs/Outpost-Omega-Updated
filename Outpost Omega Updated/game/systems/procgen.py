"""Procedural sectors for Endless, Siege Run and the Daily Challenge.

generate(seed) returns a level dict in the same format as data/levels/*.json.
The path is a random walk from the left edge to the Core on the right:
horizontal runs of 3-8 tiles alternate with vertical moves, always moving
right, so the path never crosses itself. Rocks, hazard pools and (on magma
maps) vents are scattered on open ground afterwards. Same seed, same map.
"""
import random

W, H = 40, 20
THEMES = ["desert", "frozen", "hive", "magma"]
NAMES = {"desert": "Dune Wastes", "frozen": "Ice Shelf", "hive": "Hive Tunnels", "magma": "Cinder Fields"}


def _carve(tiles, a, b):
    (x0, y0), (x1, y1) = a, b
    dx, dy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
    x, y = x0, y0
    while True:
        if tiles[y][x] == ".":
            tiles[y][x] = "#"
        if (x, y) == (x1, y1):
            return
        x, y = x + dx, y + dy


def _try(seed):
    rng = random.Random(seed)
    tiles = [["."] * W for _ in range(H)]
    y = rng.randint(3, H - 4)
    x = 0
    pts = [(0, y)]
    while x < 31:
        nx = min(33, x + rng.randint(3, 8))
        pts.append((nx, y))
        x = nx
        if x < 31:
            ny = y
            while abs(ny - y) < 4:
                ny = rng.randint(2, H - 3)
            pts.append((x, ny))
            y = ny
    pts.append((36, y))
    for a, b in zip(pts, pts[1:]):
        _carve(tiles, a, b)
    tiles[pts[0][1]][0] = "S"
    cy = y
    tiles[cy][37] = "C"
    for yy in range(cy - 2, cy + 3):
        for xx in range(36, 40):
            if 0 <= yy < H and tiles[yy][xx] == ".":
                tiles[yy][xx] = "X"
    path_len = sum(row.count("#") for row in tiles)
    theme = rng.choice(THEMES)

    def open_spot():
        for _ in range(200):
            px, py = rng.randrange(1, 35), rng.randrange(H)
            if tiles[py][px] == ".":
                return px, py
        return None

    for _ in range(rng.randint(14, 24)):      # rocks
        p = open_spot()
        if p:
            tiles[p[1]][p[0]] = "X"
    for _ in range(rng.randint(2, 4)):        # hazard pools
        p = open_spot()
        if p:
            for ddx, ddy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                qx, qy = p[0] + ddx, p[1] + ddy
                if qx < 35 and qy < H and tiles[qy][qx] == ".":
                    tiles[qy][qx] = "~"
    vents = []
    if theme == "magma":                       # vents next to path bends
        bends = pts[1:-1]
        rng.shuffle(bends)
        for bx, by in bends[:4]:
            for ddx, ddy in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
                qx, qy = bx + ddx, by + ddy
                if 0 < qx < 35 and 0 <= qy < H and tiles[qy][qx] == ".":
                    tiles[qy][qx] = "X"
                    vents.append({"tile": [qx, qy], "interval": 14, "offset": len(vents) * 3})
                    break
    return tiles, theme, path_len, vents


def generate(seed):
    s = seed
    for _ in range(20):
        tiles, theme, path_len, vents = _try(s)
        if path_len >= 55:
            break
        s += 7919
    waves = [{"groups": [{"enemy": "skitter", "count": 8 + 2 * i, "interval": 0.8, "delay": 0}],
              "boss": None} for i in range(10)]
    return {
        "name": f"Uncharted - {NAMES[theme]} #{seed % 10000:04d}",
        "id": f"proc_{seed}",
        "theme": theme,
        "core_hp": 100,
        "start_energy": 280,
        "build_time": 15,
        "enemy_hp_mult": 1.2,
        "tiles": ["".join(r) for r in tiles],
        "vents": vents,
        "waves": waves,
    }

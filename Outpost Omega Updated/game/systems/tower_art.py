"""Placeholder art for upgraded towers and the things towers spawn.

Every tower has a look per upgrade level plus one per tier-4 branch:
    turret_<kind>         tier 1 (the original art, drawn in asset_manager)
    turret_<kind>_t1      tier 2
    turret_<kind>_t2      tier 3
    turret_<kind>_b0/_b1  tier-4 branches (Siege Run)
    tower_base_t1/_t2/_b  matching base plates
    drone_t0/_t1/_t2      Drone Bay drones, by the bay's tier
Mines (draw_mine) and mortar shells change with the launching tower's tier too;
they're drawn straight to the screen so their lights can blink.

Like the rest of the placeholders, any of these can be replaced by dropping a
PNG with the same name into assets/sprites/. Turrets point right (+x) on a
40x40 canvas; the game rotates them.

Visual language: tier 2 adds cyan trim and extra hardware, tier 3 goes gold
and heavier, branches are magenta and change the silhouette outright.
"""
import math

import pygame

from .. import settings as S

K = (22, 22, 34)                 # outline
VOID = (8, 6, 18)
TRIM = {1: S.CYAN, 2: S.ENERGY, "b": S.MAGENTA}


# ---- tiny drawing helpers -----------------------------------------------------------
def _c(s, col, c, r, w=0):
    pygame.draw.circle(s, col, (int(c[0]), int(c[1])), int(r), w)


def _r(s, col, rect, br=0, w=0):
    pygame.draw.rect(s, col, rect, w, border_radius=br)


def _p(s, col, pts, w=0):
    pygame.draw.polygon(s, col, pts, w)


def _l(s, col, a, b, w=1):
    pygame.draw.line(s, col, a, b, w)


def _ngon(c, r, n, rot=0.0):
    return [(c[0] + r * math.cos(rot + i * math.tau / n), c[1] + r * math.sin(rot + i * math.tau / n))
            for i in range(n)]


def _star(c, r_out, r_in, n, rot=0.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return pts


def _polar(c, r, deg):
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def _hub(s, c, r, body, trim, core=None, core_r=4):
    """The round turret housing most towers share."""
    _c(s, K, c, r + 1)
    _c(s, body, c, r)
    if trim:
        _c(s, trim, c, r, 1)
    if core:
        _c(s, core, c, core_r)


def _canvas(size=40):
    return pygame.Surface((size, size), pygame.SRCALPHA)


C = (20, 20)


# ---- base plates ------------------------------------------------------------------------
def tower_base(level):
    """level: 1, 2 or 'b'."""
    s = _canvas(32)
    trim = TRIM[level]
    _r(s, K, (0, 0, 32, 32), 7)
    _r(s, S.STEEL_DARK if level != 2 else (58, 64, 82), (2, 2, 28, 28), 6)
    _r(s, S.STEEL if level == 1 else (96, 104, 124), (5, 5, 22, 22), 4)
    if level == 1:
        _r(s, trim, (4, 4, 24, 24), 5, 1)
        for b in ((7, 7), (24, 7), (7, 24), (24, 24)):
            _c(s, trim, b, 2)
    elif level == 2:
        for x, y, dx, dy in ((2, 2, 1, 1), (29, 2, -1, 1), (2, 29, 1, -1), (29, 29, -1, -1)):
            _l(s, trim, (x, y), (x + 7 * dx, y), 2)        # gold corner brackets
            _l(s, trim, (x, y), (x, y + 7 * dy), 2)
        for vx in (11, 15, 19):                              # side vents
            _l(s, K, (vx, 3), (vx, 5), 1)
            _l(s, K, (vx, 26), (vx, 28), 1)
        for b in ((8, 8), (23, 8), (8, 23), (23, 23)):
            _c(s, K, b, 3)
            _c(s, trim, b, 2)
    else:   # branch
        _r(s, trim, (1, 1, 30, 30), 7, 1)
        _r(s, trim, (4, 4, 24, 24), 5, 1)
        for b in ((5, 5), (26, 5), (5, 26), (26, 26)):
            _p(s, trim, [(b[0], b[1] - 3), (b[0] + 3, b[1]), (b[0], b[1] + 3), (b[0] - 3, b[1])])
    return s


# ---- turrets ------------------------------------------------------------------------------
def _pulse(s, v):
    if v == "t1":
        for y in (13, 21):
            _r(s, K, (18, y, 20, 6))
            _r(s, S.STEEL_LIGHT, (19, y + 1, 18, 4))
            _r(s, S.ORANGE, (34, y + 1, 4, 4))
        _hub(s, C, 10, S.STEEL, S.CYAN, S.CYAN, 4)
    elif v == "t2":
        _r(s, K, (16, 10, 12, 20), 2)
        for y in (12, 22):
            _r(s, K, (20, y, 20, 6))
            _r(s, S.STEEL_LIGHT, (21, y + 1, 18, 4))
            _r(s, S.ENERGY, (36, y + 1, 4, 4))
        for y in (6, 29):
            _r(s, K, (10, y, 14, 5), 2)
            _r(s, S.ENERGY, (11, y + 1, 12, 3), 1)
        _hub(s, C, 11, S.STEEL_LIGHT, S.ENERGY, S.ENERGY, 5)
        _c(s, S.WHITE, C, 2)
    elif v == "b0":   # Minigun: barrel cluster + ammo drum
        _r(s, K, (16, 10, 24, 20), 3)
        for dy in (-6, -2, 2, 6):
            _r(s, S.STEEL_LIGHT, (18, 20 + dy - 1, 21, 2))
        _r(s, K, (31, 9, 3, 22))
        _r(s, S.MAGENTA, (31, 10, 3, 20))
        _c(s, K, (9, 20), 8)
        _c(s, S.ORANGE, (9, 20), 7)
        _c(s, K, (9, 20), 3)
        _hub(s, C, 8, S.STEEL, S.MAGENTA, S.MAGENTA, 3)
    else:             # Marksman: long barrel, muzzle brake, scope
        _r(s, K, (16, 17, 24, 6))
        _r(s, S.STEEL_LIGHT, (17, 18, 23, 4))
        _r(s, K, (34, 14, 6, 12), 1)
        _r(s, S.STEEL, (35, 15, 4, 10))
        _r(s, K, (12, 9, 16, 6), 2)
        _r(s, S.STEEL_DARK, (13, 10, 14, 4), 2)
        _c(s, S.CYAN, (26, 12), 2)
        _hub(s, C, 9, S.STEEL_DARK, S.MAGENTA, S.RED, 3)


def _tesla(s, v):
    if v == "t1":
        _c(s, K, C, 12)
        _c(s, S.STEEL_DARK, C, 11)
        for deg in (45, 135, 225, 315):
            _l(s, K, _polar(C, 6, deg), _polar(C, 16, deg), 5)
            _l(s, S.ORANGE, _polar(C, 7, deg), _polar(C, 15, deg), 2)
        _c(s, S.ORANGE, C, 8, 2)
        _c(s, S.CYAN, C, 11, 1)
        _c(s, S.CYAN, C, 3)
    elif v == "t2":
        _c(s, K, C, 13)
        _c(s, S.STEEL_DARK, C, 12)
        for i, deg in enumerate(range(0, 360, 45)):
            r = 18 if i % 2 == 0 else 15
            _l(s, K, _polar(C, 6, deg), _polar(C, r, deg), 5)
            _l(s, S.ENERGY, _polar(C, 7, deg), _polar(C, r - 1, deg), 2)
            if i % 2 == 0:
                _c(s, S.CYAN, _polar(C, r, deg), 2)
        for r in (10, 7):
            _c(s, S.ORANGE, C, r, 2)
        _c(s, S.ENERGY, C, 12, 1)
        _c(s, S.CYAN, C, 5)
        _c(s, S.WHITE, C, 2)
    elif v == "b0":   # Storm Spire
        _p(s, K, _star(C, 19, 8, 6))
        _p(s, S.STEEL_DARK, _star(C, 17, 7, 6))
        for deg in range(0, 360, 60):
            _c(s, S.CYAN, _polar(C, 16, deg), 2)
        pygame.draw.arc(s, S.CYAN, (8, 8, 24, 24), 0.3, 2.4, 2)
        pygame.draw.arc(s, S.CYAN, (8, 8, 24, 24), 3.4, 5.5, 2)
        _c(s, S.MAGENTA, C, 7, 1)
        _c(s, S.CYAN, C, 5)
        _c(s, S.WHITE, C, 3)
    else:             # Arc Battery
        _r(s, K, (6, 6, 28, 28), 4)
        _r(s, S.STEEL_DARK, (7, 7, 26, 26), 4)
        for x, y in ((9, 9), (22, 9), (9, 22), (22, 22)):
            _r(s, K, (x, y, 9, 9), 2)
            _r(s, S.CYAN, (x + 1, y + 1, 7, 7), 2)
            _r(s, S.WHITE, (x + 2, y + 2, 2, 5))
        _r(s, S.MAGENTA, (6, 6, 28, 28), 4, 1)
        _c(s, K, C, 5)
        _c(s, S.ORANGE, C, 4)


def _cryo(s, v):
    if v == "t1":
        for deg in (0, 120, 240):
            _p(s, K, [_polar(C, 17, deg), _polar(C, 9, deg - 22), _polar(C, 9, deg + 22)])
            _p(s, S.CRYO, [_polar(C, 15, deg), _polar(C, 10, deg - 16), _polar(C, 10, deg + 16)])
        _p(s, K, _ngon(C, 12, 6))
        _p(s, S.STEEL_LIGHT, _ngon(C, 10, 6))
        _p(s, S.CYAN, _ngon(C, 10, 6), 1)
        _p(s, S.CRYO, [(20, 12), (26, 20), (20, 28), (14, 20)])
        _p(s, S.WHITE, [(20, 15), (22, 20), (20, 23), (18, 20)])
    elif v == "t2":
        for deg in range(30, 390, 60):
            tip, l, r = _polar(C, 18, deg), _polar(C, 12, deg - 10), _polar(C, 12, deg + 10)
            _p(s, K, [tip, l, _polar(C, 9, deg), r])
            _p(s, S.CRYO, [_polar(C, 16, deg), _polar(C, 12, deg - 6), _polar(C, 10, deg), _polar(C, 12, deg + 6)])
        _p(s, K, _ngon(C, 13, 6))
        _p(s, S.ENERGY, _ngon(C, 12, 6), 2)
        _p(s, S.STEEL_LIGHT, _ngon(C, 10, 6))
        for deg in range(0, 180, 60):
            _l(s, S.CRYO, _polar(C, 8, deg), _polar(C, 8, deg + 180), 2)
        _c(s, S.WHITE, C, 3)
    elif v == "b0":   # Absolute Zero: snowflake
        for deg in range(0, 360, 60):
            _l(s, K, C, _polar(C, 18, deg), 6)
        for deg in range(0, 360, 60):
            _l(s, S.WHITE, C, _polar(C, 17, deg), 2)
            mid = _polar(C, 11, deg)
            _l(s, S.CRYO, mid, _polar(mid, 5, deg + 50), 2)
            _l(s, S.CRYO, mid, _polar(mid, 5, deg - 50), 2)
        _c(s, K, C, 7)
        _c(s, S.CRYO, C, 6)
        _c(s, S.MAGENTA, C, 6, 1)
        _c(s, S.WHITE, C, 3)
    else:             # Frost Nova: ring of emitters
        _c(s, K, C, 16)
        _c(s, (40, 70, 110), C, 15)
        _c(s, S.CYAN, C, 15, 2)
        for deg in range(0, 360, 60):
            p = _polar(C, 11, deg)
            _c(s, K, p, 4)
            _c(s, S.CRYO, p, 3)
            _c(s, S.WHITE, p, 1)
        _c(s, S.MAGENTA, C, 7, 1)
        _c(s, S.WHITE, C, 5)


def _railgun(s, v):
    if v == "t1":
        _r(s, K, (12, 14, 28, 12))
        _r(s, S.STEEL_DARK, (13, 15, 27, 3))
        _r(s, S.STEEL_DARK, (13, 22, 27, 3))
        _r(s, S.CYAN, (15, 19, 25, 2))
        for x in (24, 32):
            _r(s, S.CYAN, (x, 13, 2, 14))
        _hub(s, C, 9, S.STEEL, S.CYAN)
    elif v == "t2":
        _r(s, K, (10, 11, 30, 18), 2)
        _r(s, S.STEEL_LIGHT, (11, 12, 29, 4))
        _r(s, S.STEEL_LIGHT, (11, 24, 29, 4))
        _r(s, S.CYAN, (13, 17, 27, 6))
        _r(s, S.WHITE, (13, 19, 27, 2))
        for x in (24, 30, 36):
            _r(s, K, (x - 1, 9, 4, 22))
            _r(s, S.ENERGY, (x, 10, 2, 20))
        _hub(s, C, 10, S.STEEL, S.ENERGY, S.ENERGY, 4)
    elif v == "b0":   # Overpenetrator: three very long rails
        _r(s, K, (4, 12, 36, 16), 2)
        for y in (13, 19, 25):
            _r(s, S.STEEL_LIGHT, (5, y, 35, 2))
        for y in (16, 22):
            _r(s, S.CYAN, (8, y, 32, 2))
        _r(s, S.MAGENTA, (36, 12, 4, 16))
        _hub(s, (14, 20), 7, S.STEEL, S.MAGENTA, S.CYAN, 2)
    else:             # Executioner: heavy bore + red sight
        _r(s, K, (12, 9, 28, 22), 3)
        _r(s, S.STEEL_DARK, (13, 10, 26, 20), 3)
        _r(s, K, (30, 14, 10, 12), 2)
        _r(s, S.MAGENTA, (13, 10, 26, 20), 3, 1)
        _l(s, S.RED, (18, 20), (39, 20), 1)
        _hub(s, C, 10, S.STEEL, None, S.RED, 3)


def _missile(s, v):
    def pod(x, y, r, col=S.RED, tip=S.ORANGE):
        _c(s, K, (x, y), r + 1)
        _c(s, col, (x, y), r)
        _c(s, tip, (x, y), max(1, r - 2))
    if v == "t1":
        _r(s, K, (6, 7, 28, 26), 3)
        _r(s, S.STEEL, (7, 8, 26, 24), 3)
        _r(s, S.CYAN, (6, 7, 28, 26), 3, 1)
        for x in (13, 20, 27):
            for y in (15, 25):
                pod(x, y, 3)
    elif v == "t2":
        _r(s, K, (4, 4, 32, 32), 4)
        _r(s, S.STEEL_DARK, (5, 5, 30, 30), 4)
        _r(s, S.STEEL, (7, 7, 26, 26), 3)
        for x, y in ((5, 5), (30, 5), (5, 30), (30, 30)):
            _r(s, S.ENERGY, (x, y, 5, 5), 1)
        for x in (12, 20, 28):
            for y in (12, 20, 28):
                pod(x, y, 3, S.RED, S.ENERGY)
    elif v == "b0":   # Cluster Swarm
        _r(s, K, (5, 5, 30, 30), 3)
        _r(s, S.STEEL, (6, 6, 28, 28), 3)
        _r(s, S.MAGENTA, (5, 5, 30, 30), 3, 1)
        for x in (11, 17, 23, 29):
            for y in (11, 17, 23, 29):
                pod(x, y, 2, S.RED, S.ENERGY)
    else:             # Hunter-Killer: two big guided missiles
        _r(s, K, (6, 6, 22, 28), 3)
        _r(s, S.STEEL_DARK, (7, 7, 20, 26), 3)
        for y in (13, 27):
            _p(s, K, [(6, y - 7), (10, y - 4), (10, y + 4), (6, y + 7)])
            _r(s, K, (8, y - 5, 26, 10), 3)
            _r(s, S.STEEL_LIGHT, (9, y - 4, 23, 8), 3)
            _r(s, S.MAGENTA, (15, y - 4, 3, 8))
            _p(s, S.RED, [(31, y - 4), (38, y), (31, y + 4)])


def _flamer(s, v):
    if v == "t1":
        _r(s, K, (3, 12, 11, 16), 3)
        _r(s, S.ORANGE, (4, 13, 9, 14), 3)
        _p(s, K, [(18, 12), (38, 9), (38, 31), (18, 28)])
        _p(s, S.STEEL_DARK, [(19, 13), (36, 11), (36, 29), (19, 27)])
        for y in (12, 22):
            _r(s, S.ORANGE, (34, y, 4, 6))
        _hub(s, C, 9, S.RED, S.CYAN, S.ENERGY, 4)
    else:   # t2
        for y in (7, 23):
            _r(s, K, (2, y, 12, 10), 3)
            _r(s, S.ORANGE, (3, y + 1, 10, 8), 3)
            _r(s, S.ENERGY, (5, y + 2, 2, 6))
        _p(s, K, [(18, 9), (40, 6), (40, 34), (18, 31)])
        _p(s, S.STEEL_DARK, [(19, 10), (38, 8), (38, 32), (19, 30)])
        for x in (24, 29):
            _l(s, S.ORANGE, (x, 12), (x, 28), 1)
        _r(s, S.ORANGE, (35, 10, 4, 20))
        _r(s, S.ENERGY, (37, 13, 2, 14))
        _hub(s, C, 10, S.RED, S.ENERGY, S.ENERGY, 5)
        _c(s, S.WHITE, C, 2)


def _mortar(s, v):
    if v == "t1":
        for deg in (120, 240, 0):
            _l(s, K, C, _polar(C, 18, deg), 5)
            _l(s, S.STEEL, C, _polar(C, 17, deg), 3)
        _c(s, K, C, 14)
        _c(s, S.STEEL_DARK, C, 13)
        _c(s, S.CYAN, C, 13, 1)
        _c(s, K, (26, 20), 9)
        _c(s, S.STEEL, (26, 20), 8)
        _c(s, K, (28, 20), 5)
    else:   # t2: twin tubes
        _c(s, K, C, 16)
        _c(s, S.STEEL_DARK, C, 15)
        _c(s, S.ENERGY, C, 15, 1)
        for y in (13, 27):
            _c(s, K, (26, y), 7)
            _c(s, S.STEEL, (26, y), 6)
            _c(s, K, (27, y), 3)
        _c(s, K, (14, 20), 5)
        _c(s, S.ENERGY, (14, 20), 4)


def _gravity(s, v):
    if v == "t1":
        _c(s, K, C, 15)
        _c(s, S.MAGENTA_DARK, C, 14)
        pygame.draw.arc(s, S.MAGENTA, (6, 6, 28, 28), 1.0, 4.0, 2)
        pygame.draw.arc(s, S.MAGENTA, (10, 10, 20, 20), 0, 3.6, 3)
        pygame.draw.arc(s, S.MAGENTA, (14, 14, 12, 12), 3.1, 6.3, 2)
        _c(s, S.CYAN, C, 15, 1)
        _c(s, S.WHITE, C, 3)
    else:   # t2: black hole
        _c(s, K, C, 17)
        _c(s, S.MAGENTA_DARK, C, 16)
        for r, a0 in ((14, 0.0), (11, 2.1), (8, 4.2)):
            pygame.draw.arc(s, S.MAGENTA, (20 - r, 20 - r, r * 2, r * 2), a0, a0 + 3.4, 2)
        _c(s, S.ENERGY, C, 17, 1)
        _c(s, VOID, C, 5)
        _c(s, S.WHITE, C, 6, 1)


def _harvester(s, v):
    def gem(x, y, w, h):
        _p(s, K, [(x, y - h - 1), (x + w + 1, y), (x, y + h + 1), (x - w - 1, y)])
        _p(s, S.ENERGY, [(x, y - h), (x + w, y), (x, y + h), (x - w, y)])
        _p(s, S.WHITE, [(x, y - h + 2), (x + 1, y - 1), (x, y), (x - 1, y - 1)])
    if v == "t1":
        _r(s, K, (6, 7, 28, 26), 6)
        _r(s, S.STEEL, (7, 8, 26, 24), 6)
        _r(s, S.CYAN, (6, 7, 28, 26), 6, 1)
        gem(14, 20, 4, 7)
        gem(26, 20, 4, 7)
    else:   # t2
        for deg in (45, 135, 225, 315):
            _l(s, K, _polar(C, 9, deg), _polar(C, 18, deg), 4)
            _c(s, S.ENERGY, _polar(C, 17, deg), 2)
        _p(s, K, _ngon(C, 15, 8, math.pi / 8))
        _p(s, S.STEEL, _ngon(C, 13, 8, math.pi / 8))
        _p(s, S.ENERGY, _ngon(C, 13, 8, math.pi / 8), 1)
        gem(20, 20, 5, 9)
        gem(12, 20, 2, 4)
        gem(28, 20, 2, 4)


def _radar(s, v):
    if v == "t1":
        pygame.draw.arc(s, K, (4, 1, 32, 30), 3.5, 5.9, 7)
        pygame.draw.arc(s, S.GREEN, (4, 1, 32, 30), 3.5, 5.9, 4)
        _l(s, K, C, (31, 31), 4)
        _l(s, S.STEEL_LIGHT, C, (30, 30), 2)
        _c(s, S.GREEN, (31, 31), 3)
        _hub(s, C, 9, S.STEEL, S.CYAN)
        _l(s, S.GREEN, C, (20, 6), 2)
        _c(s, S.GREEN, C, 3)
    else:   # t2: twin dishes
        for box, a0, a1 in (((4, 0, 32, 28), 3.5, 5.9), ((4, 12, 32, 28), 0.4, 2.8)):
            pygame.draw.arc(s, K, box, a0, a1, 7)
            pygame.draw.arc(s, S.GREEN, box, a0, a1, 4)
        _hub(s, C, 10, S.STEEL, S.ENERGY)
        _l(s, S.GREEN, (20, 6), (20, 34), 2)
        _c(s, S.ENERGY, C, 4)
        _c(s, S.GREEN, C, 2)


def _drone(s, v):
    if v == "t1":
        _r(s, K, (5, 7, 30, 26), 4)
        _r(s, S.STEEL_DARK, (6, 8, 28, 24), 4)
        _r(s, S.CYAN, (5, 7, 30, 26), 4, 1)
        _r(s, K, (9, 13, 22, 14), 2)
        for y in (11, 28):
            _r(s, S.STEEL_LIGHT, (9, y, 22, 2))
        for px in (13, 18, 23, 28):
            _c(s, S.GREEN, (px, 20), 2)
    else:   # t2: hex hangar with landing pad
        _p(s, K, _ngon(C, 18, 6, math.pi / 6))
        _p(s, S.STEEL_DARK, _ngon(C, 16, 6, math.pi / 6))
        _p(s, S.ENERGY, _ngon(C, 16, 6, math.pi / 6), 1)
        for deg in range(0, 360, 60):
            _c(s, S.GREEN, _polar(C, 12, deg), 2)
        _c(s, K, C, 8)
        _c(s, S.GREEN, C, 8, 1)
        _l(s, S.ENERGY, (17, 16), (17, 24), 2)
        _l(s, S.ENERGY, (23, 16), (23, 24), 2)
        _l(s, S.ENERGY, (17, 20), (23, 20), 2)


def _barricade(s, v):
    _r(s, K, (4, 6, 32, 28), 3)
    _r(s, S.STEEL if v == "t1" else (96, 104, 124), (5, 7, 30, 26), 3)
    for i in range(4):
        col = S.ENERGY if v == "t1" else S.ORANGE
        _p(s, col, [(5 + i * 8, 33), (9 + i * 8, 33), (17 + i * 8, 7), (13 + i * 8, 7)])
    _r(s, K, (5, 7, 30, 26), 3, 1)
    if v == "t1":
        for x, y in ((3, 5), (31, 5), (3, 29), (31, 29)):
            _r(s, K, (x, y, 7, 7), 1)
            _r(s, S.STEEL_LIGHT, (x + 1, y + 1, 5, 5), 1)
            _c(s, S.CYAN, (x + 3, y + 3), 1)
    else:   # t2: spiked armor
        for x in (8, 16, 24, 32):
            _p(s, K, [(x - 4, 6), (x, 0), (x + 4, 6)])
            _p(s, S.STEEL_LIGHT, [(x - 2, 6), (x, 2), (x + 2, 6)])
            _p(s, K, [(x - 4, 34), (x, 40), (x + 4, 34)])
            _p(s, S.STEEL_LIGHT, [(x - 2, 34), (x, 38), (x + 2, 34)])
        _r(s, S.ENERGY, (4, 6, 32, 28), 3, 1)


def _mines(s, v):
    if v == "t1":
        _c(s, K, C, 14)
        _c(s, S.STEEL_DARK, C, 13)
        _c(s, S.CYAN, C, 13, 1)
        _r(s, K, (17, 10, 21, 10))
        _r(s, S.STEEL, (18, 11, 19, 8))
        for p in ((13, 12), (13, 28)):
            _c(s, K, p, 3)
            _c(s, S.RED, p, 2)
        _c(s, S.RED, C, 5)
        _c(s, S.ENERGY, C, 2)
    else:   # t2: twin launchers
        _c(s, K, C, 15)
        _c(s, S.STEEL_DARK, C, 14)
        _c(s, S.ENERGY, C, 14, 1)
        for y in (9, 25):
            _r(s, K, (17, y, 22, 7))
            _r(s, S.STEEL, (18, y + 1, 20, 5))
            _r(s, S.RED, (35, y + 1, 3, 5))
        _c(s, K, C, 6)
        _c(s, S.RED, C, 5)
        _c(s, S.ENERGY, C, 2)


TURRETS = {"pulse": _pulse, "tesla": _tesla, "cryo": _cryo, "railgun": _railgun,
           "missile": _missile, "flamer": _flamer, "mortar": _mortar, "gravity": _gravity,
           "harvester": _harvester, "radar": _radar, "drone": _drone, "barricade": _barricade,
           "mines": _mines}
BRANCHED = {"pulse", "tesla", "cryo", "railgun", "missile"}


def turret(kind, variant):
    """variant: 't1', 't2', 'b0', 'b1'. None if this kind has no art for it."""
    draw = TURRETS.get(kind)
    if draw is None or (variant[0] == "b" and kind not in BRANCHED):
        return None
    s = _canvas()
    draw(s, variant)
    return s


def variant_names():
    names = ["tower_base_t1", "tower_base_t2", "tower_base_b",
             "drone_t0", "drone_t1", "drone_t2"]
    for kind in TURRETS:
        names += [f"turret_{kind}_t1", f"turret_{kind}_t2"]
        if kind in BRANCHED:
            names += [f"turret_{kind}_b0", f"turret_{kind}_b1"]
    return names


# ---- spawned units ---------------------------------------------------------------------
def drone(level):
    """Drone Bay drones, pointing right."""
    s = _canvas(22)
    c = (11, 11)
    if level == 0:
        _p(s, K, [(18, 11), (6, 5), (6, 17)])
        _c(s, S.GREEN, c, 2)
    elif level == 1:
        _p(s, K, [(20, 11), (4, 3), (8, 11), (4, 19)])
        _p(s, S.STEEL_DARK, [(17, 11), (6, 6), (9, 11), (6, 16)])
        for y in (4, 18):
            _c(s, K, (7, y), 3)
            _c(s, S.CYAN, (7, y), 2)
        _c(s, S.GREEN, (11, 11), 2)
    else:   # quad-rotor
        for p in ((4, 4), (18, 4), (4, 18), (18, 18)):
            _l(s, K, c, p, 3)
        for p in ((4, 4), (18, 4), (4, 18), (18, 18)):
            _c(s, K, p, 4)
            _c(s, S.STEEL_DARK, p, 3)
            _c(s, S.ENERGY, p, 3, 1)
        _p(s, K, [(19, 11), (12, 6), (12, 16)])
        _c(s, K, c, 5)
        _c(s, S.ENERGY, c, 4)
        _c(s, S.GREEN, c, 2)
    return s


def draw_mine(screen, pos, level, blink):
    """Mines are drawn straight to the screen so the warning light can blink."""
    x, y = int(pos[0]), int(pos[1])
    if level == 0:
        _c(screen, K, (x, y), 6)
        _c(screen, S.STEEL_DARK, (x, y), 5)
        _c(screen, S.RED if blink else (110, 20, 20), (x, y), 2)
    elif level == 1:
        for deg in (45, 135, 225, 315):
            _l(screen, K, (x, y), _polar((x, y), 9, deg), 3)
        _c(screen, K, (x, y), 7)
        _c(screen, S.STEEL_DARK, (x, y), 6)
        _c(screen, S.CYAN, (x, y), 6, 1)
        _c(screen, S.RED if blink else (110, 20, 20), (x, y), 3)
    else:
        _p(screen, K, _ngon((x, y), 9, 6))
        _p(screen, S.STEEL, _ngon((x, y), 8, 6))
        _p(screen, S.ENERGY, _ngon((x, y), 8, 6), 1)
        _c(screen, K, (x, y), 4)
        _c(screen, S.ENERGY if blink else S.RED, (x, y), 3)

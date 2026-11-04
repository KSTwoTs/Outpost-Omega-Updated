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

The four newer towers (laser, acid, repair, sonic) draw their tier-1 look here
too. Like the rest of the placeholders, any of these can be replaced by dropping a
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
BRANCHED = {"pulse", "tesla", "cryo", "railgun", "missile"}   # extended below


def turret(kind, variant):
    """variant: 't0' (new towers only), 't1', 't2', 'b0', 'b1'. None if there's no art for it."""
    draw = TURRETS.get(kind)
    if variant[0] == "b" and kind in BRANCH_ART:
        draw = BRANCH_ART[kind]
    if draw is None or (variant[0] == "b" and kind not in BRANCHED) or (variant == "t0" and kind not in NEW_TOWERS):
        return None
    s = _canvas()
    draw(s, variant)
    return s


def variant_names():
    names = ["tower_base_t1", "tower_base_t2", "tower_base_b",
             "drone_t0", "drone_t1", "drone_t2"]
    for kind in TURRETS:
        if kind in NEW_TOWERS:
            names.append(f"turret_{kind}")
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


# ---- tier-4 branch looks for towers that got branches later ---------------------------
def _flamer_b(s, v):
    if v == "b0":   # Dragon's Breath: huge flared jaws
        _p(s, K, [(16, 12), (40, 1), (40, 39), (16, 28)])
        _p(s, S.STEEL_DARK, [(17, 13), (38, 4), (38, 36), (17, 27)])
        _p(s, S.MAGENTA, [(30, 6), (40, 1), (36, 12)])
        _p(s, S.MAGENTA, [(30, 34), (40, 39), (36, 28)])
        _r(s, S.ORANGE, (35, 11, 4, 18))
        _r(s, S.ENERGY, (37, 14, 2, 12))
        _hub(s, (15, 20), 10, S.RED, S.MAGENTA, S.ENERGY, 5)
    else:           # Napalm Sprayer: big napalm tank, long nozzle
        _c(s, K, (11, 20), 10)
        _c(s, (200, 110, 20), (11, 20), 9)
        _c(s, S.ENERGY, (8, 17), 3)
        _c(s, S.MAGENTA, (11, 20), 9, 1)
        _r(s, K, (18, 16, 22, 8), 2)
        _r(s, S.STEEL_DARK, (19, 17, 20, 6), 2)
        _r(s, S.ORANGE, (36, 17, 4, 6))
        for x in (24, 30):
            _c(s, (200, 110, 20), (x, 26), 2)
        _hub(s, (20, 20), 6, S.RED, None, S.ENERGY, 2)


def _mortar_b(s, v):
    _c(s, K, C, 17)
    _c(s, S.STEEL_DARK, C, 16)
    _c(s, S.MAGENTA, C, 16, 1)
    if v == "b0":   # Siege Cannon: one enormous barrel
        _c(s, K, (24, 20), 13)
        _c(s, S.STEEL, (24, 20), 12)
        _c(s, S.STEEL_LIGHT, (24, 20), 12, 2)
        _c(s, K, (26, 20), 8)
        _c(s, VOID, (27, 20), 6)
    else:           # Rapid Battery: three small tubes
        for p in ((25, 11), (25, 29), (32, 20)):
            _c(s, K, p, 6)
            _c(s, S.STEEL, p, 5)
            _c(s, K, (p[0] + 1, p[1]), 3)
        _c(s, S.MAGENTA, (14, 20), 4)


def _gravity_b(s, v):
    if v == "b0":   # Singularity: black hole with an accretion disk
        _c(s, K, C, 18)
        _c(s, S.MAGENTA_DARK, C, 17)
        pygame.draw.ellipse(s, S.MAGENTA, (2, 13, 36, 14), 3)
        pygame.draw.ellipse(s, S.WHITE, (6, 16, 28, 8), 1)
        _c(s, VOID, C, 7)
        _c(s, S.MAGENTA, C, 8, 1)
    else:           # Stasis Field: hexagonal cage around a frozen core
        _p(s, K, _ngon(C, 18, 6))
        _p(s, (30, 40, 70), _ngon(C, 17, 6))
        for i, p in enumerate(_ngon(C, 17, 6)):
            _l(s, S.CYAN, C, p, 1)
        _p(s, S.MAGENTA, _ngon(C, 17, 6), 2)
        _c(s, S.CRYO, C, 6)
        _c(s, S.WHITE, C, 3)


def _harvester_b(s, v):
    def gem(x, y, w, h, col=S.ENERGY):
        _p(s, K, [(x, y - h - 1), (x + w + 1, y), (x, y + h + 1), (x - w - 1, y)])
        _p(s, col, [(x, y - h), (x + w, y), (x, y + h), (x - w, y)])
        _p(s, S.WHITE, [(x, y - h + 2), (x + 1, y - 1), (x, y), (x - 1, y - 1)])
    _p(s, K, _ngon(C, 17, 8, math.pi / 8))
    _p(s, S.STEEL_DARK, _ngon(C, 15, 8, math.pi / 8))
    _p(s, S.MAGENTA, _ngon(C, 15, 8, math.pi / 8), 1)
    if v == "b0":   # Energy Refinery: a crystal cluster on pipes
        for deg in (0, 90, 180, 270):
            _l(s, S.STEEL_LIGHT, _polar(C, 8, deg), _polar(C, 15, deg), 3)
        gem(20, 20, 5, 10)
        gem(13, 22, 3, 6)
        gem(27, 22, 3, 6)
        gem(20, 11, 2, 4)
    else:           # Overflow Core: crystal over a healing core
        _c(s, S.CYAN, C, 11, 2)
        _r(s, S.GREEN, (18, 8, 4, 24))
        _r(s, S.GREEN, (8, 18, 24, 4))
        gem(20, 20, 4, 7)


def _radar_b(s, v):
    if v == "b0":   # Targeting Uplink: dish with a red crosshair
        pygame.draw.arc(s, K, (3, 0, 34, 32), 3.4, 6.0, 8)
        pygame.draw.arc(s, S.MAGENTA, (3, 0, 34, 32), 3.4, 6.0, 5)
        _hub(s, C, 10, S.STEEL, S.MAGENTA)
        _c(s, S.RED, C, 6, 1)
        _l(s, S.RED, (20, 12), (20, 28), 1)
        _l(s, S.RED, (12, 20), (28, 20), 1)
        _c(s, S.RED, C, 2)
    else:           # Overwatch Array: tall mast with signal rings
        for r in (17, 13):
            _c(s, S.GREEN, C, r, 1)
        _c(s, S.MAGENTA, C, 18, 1)
        _hub(s, C, 8, S.STEEL_DARK, None)
        for deg in (0, 120, 240):
            _l(s, S.STEEL_LIGHT, C, _polar(C, 15, deg), 2)
            _c(s, S.GREEN, _polar(C, 15, deg), 2)
        _c(s, S.ENERGY, C, 3)


def _drone_b(s, v):
    if v == "b0":   # Drone Swarm: honeycomb hangar
        _p(s, K, _ngon(C, 19, 6, math.pi / 6))
        _p(s, S.STEEL_DARK, _ngon(C, 17, 6, math.pi / 6))
        _p(s, S.MAGENTA, _ngon(C, 17, 6, math.pi / 6), 1)
        for dx, dy in ((-8, -5), (0, -9), (8, -5), (-8, 5), (0, 0), (8, 5), (0, 9)):
            _p(s, K, _ngon((20 + dx, 20 + dy), 4, 6, math.pi / 6))
            _c(s, S.GREEN, (20 + dx, 20 + dy), 2)
    else:           # Gunship Wing: runway with a heavy gunship
        _r(s, K, (3, 6, 34, 28), 4)
        _r(s, S.STEEL_DARK, (4, 7, 32, 26), 4)
        _r(s, S.MAGENTA, (3, 6, 34, 28), 4, 1)
        for x in (7, 14, 21, 28):
            _r(s, S.ENERGY, (x, 30, 4, 2))
        _p(s, K, [(34, 20), (12, 9), (16, 20), (12, 31)])
        _p(s, S.STEEL_LIGHT, [(31, 20), (14, 12), (17, 20), (14, 28)])
        _c(s, S.GREEN, (22, 20), 3)


def _barricade_b(s, v):
    _r(s, K, (2, 4, 36, 32), 3)
    _r(s, (84, 92, 112), (3, 5, 34, 30), 3)
    if v == "b0":   # Bulwark Wall: thick riveted plates
        for y in (5, 15, 25):
            _r(s, S.STEEL, (4, y + 1, 32, 8), 1)
            _l(s, K, (4, y + 9), (36, y + 9), 1)
            for x in (8, 20, 32):
                _c(s, S.STEEL_LIGHT, (x, y + 5), 1)
        _r(s, S.MAGENTA, (2, 4, 36, 32), 3, 2)
    else:           # Shock Barricade: plating with coils and a bolt
        for x in (8, 32):
            for y in (10, 16, 22, 28):
                _r(s, S.CYAN, (x - 3, y, 6, 2))
        _p(s, K, [(22, 6), (14, 21), (20, 21), (17, 34), (27, 17), (21, 17), (25, 6)])
        _p(s, S.CYAN, [(22, 8), (16, 20), (21, 20), (19, 30), (25, 18), (19, 18), (23, 8)])
        _r(s, S.MAGENTA, (2, 4, 36, 32), 3, 2)


def _mines_b(s, v):
    _c(s, K, C, 16)
    _c(s, S.STEEL_DARK, C, 15)
    _c(s, S.MAGENTA, C, 15, 1)
    if v == "b0":   # Minefield: four launch tubes
        for deg in (0, 90, 180, 270):
            p = _polar(C, 10, deg)
            _c(s, K, p, 5)
            _c(s, S.STEEL, p, 4)
            _c(s, S.RED, p, 2)
        _c(s, S.ENERGY, C, 3)
    else:           # Cluster Charges: one big cluster bomb
        _r(s, K, (18, 12, 22, 16), 3)
        _r(s, S.STEEL, (19, 13, 20, 14), 3)
        _c(s, K, (14, 20), 9)
        _c(s, S.RED, (14, 20), 8)
        for p in ((11, 17), (17, 17), (11, 23), (17, 23), (14, 20)):
            _c(s, S.ENERGY, p, 2)


# ---- new towers -------------------------------------------------------------------------
def _laser(s, v):
    if v == "t0":
        _r(s, K, (16, 17, 22, 6))
        _r(s, S.STEEL_LIGHT, (17, 18, 20, 4))
        _r(s, S.RED, (35, 18, 4, 4))
        _hub(s, C, 9, S.STEEL, None, S.RED, 4)
    elif v == "t1":
        _r(s, K, (16, 16, 24, 8))
        _r(s, S.STEEL_LIGHT, (17, 17, 22, 6))
        for x in (22, 27, 32):
            _r(s, K, (x, 13, 2, 14))
        _r(s, S.RED, (36, 17, 4, 6))
        _hub(s, C, 10, S.STEEL, S.CYAN, S.RED, 4)
        _c(s, S.WHITE, C, 1)
    elif v == "t2":
        _r(s, K, (14, 15, 26, 10))
        _r(s, S.STEEL_LIGHT, (15, 16, 24, 8))
        for x in (24, 32):
            _c(s, K, (x, 20), 7, 0)
            _c(s, S.ENERGY, (x, 20), 6, 2)
        _r(s, S.RED, (37, 17, 3, 6))
        _hub(s, C, 11, S.STEEL, S.ENERGY, S.RED, 5)
        _c(s, S.WHITE, C, 2)
    elif v == "b0":   # Prism Lance
        tri = [_polar(C, 17, d) for d in (0, 120, 240)]
        _p(s, K, [_polar(C, 19, d) for d in (0, 120, 240)])
        _p(s, (120, 200, 255), tri)
        _p(s, S.MAGENTA, tri, 2)
        for p in tri:
            _c(s, K, p, 4)
            _c(s, S.CYAN, p, 3)
        _c(s, S.WHITE, C, 4)
    else:             # Annihilator
        _r(s, K, (10, 12, 30, 16), 3)
        _r(s, S.STEEL_DARK, (11, 13, 28, 14), 3)
        for x in (16, 22, 28):
            _r(s, S.MAGENTA, (x, 11, 3, 18))
        _r(s, S.WHITE, (34, 17, 6, 6))
        _hub(s, (12, 20), 9, S.STEEL, S.MAGENTA, S.RED, 4)


def _acid(s, v):
    def tank(c, r, col=S.ACID):
        _c(s, K, c, r + 1)
        _c(s, (40, 90, 30), c, r)
        _c(s, col, (c[0], c[1] + 2), r - 3)
        _c(s, S.WHITE, (c[0] - r // 3, c[1] - r // 3), 2)
    if v == "t0":
        _r(s, K, (20, 16, 16, 8))
        _r(s, S.STEEL, (21, 17, 14, 6))
        tank(C, 10)
    elif v == "t1":
        _r(s, K, (20, 15, 18, 10))
        _r(s, S.STEEL, (21, 16, 16, 8))
        tank((14, 13), 7)
        tank((14, 27), 7)
        _c(s, S.CYAN, (14, 13), 8, 1)
        _c(s, S.CYAN, (14, 27), 8, 1)
    elif v == "t2":
        _r(s, K, (20, 13, 20, 14), 2)
        _r(s, S.STEEL, (21, 14, 18, 12), 2)
        _r(s, S.ACID, (35, 16, 4, 8))
        tank(C, 12)
        _c(s, S.ENERGY, C, 13, 2)
    elif v == "b0":   # Corrosive Bath: bubbling cauldron with drip spikes
        for deg in range(0, 360, 45):
            _p(s, K, [_polar(C, 19, deg), _polar(C, 12, deg - 12), _polar(C, 12, deg + 12)])
        tank(C, 13, (70, 160, 40))
        for p in ((16, 18), (23, 23), (21, 15)):
            _c(s, S.ACID, p, 2)
        _c(s, S.MAGENTA, C, 14, 2)
    else:             # Toxic Flood: three-nozzle sprinkler
        for deg in (-30, 0, 30):
            _l(s, K, C, _polar(C, 19, deg), 7)
            _l(s, S.STEEL, C, _polar(C, 18, deg), 4)
            _c(s, S.ACID, _polar(C, 18, deg), 3)
        tank(C, 10)
        _c(s, S.MAGENTA, C, 11, 2)


def _repair(s, v):
    def cross(c, n, col=S.GREEN):
        _r(s, K, (c[0] - n // 3 - 1, c[1] - n - 1, n // 3 * 2 + 2, n * 2 + 2))
        _r(s, K, (c[0] - n - 1, c[1] - n // 3 - 1, n * 2 + 2, n // 3 * 2 + 2))
        _r(s, col, (c[0] - n // 3, c[1] - n, n // 3 * 2, n * 2))
        _r(s, col, (c[0] - n, c[1] - n // 3, n * 2, n // 3 * 2))
    if v == "t0":
        _r(s, K, (7, 7, 26, 26), 4)
        _r(s, S.STEEL, (8, 8, 24, 24), 4)
        cross(C, 8)
    elif v == "t1":
        _r(s, K, (6, 6, 28, 28), 4)
        _r(s, S.STEEL, (7, 7, 26, 26), 4)
        _r(s, S.CYAN, (6, 6, 28, 28), 4, 1)
        cross(C, 9)
        _l(s, K, (30, 30), (38, 38), 4)
        _c(s, S.CYAN, (36, 36), 3)
    elif v == "t2":
        _p(s, K, _ngon(C, 18, 8, math.pi / 8))
        _p(s, S.STEEL, _ngon(C, 16, 8, math.pi / 8))
        _p(s, S.ENERGY, _ngon(C, 16, 8, math.pi / 8), 2)
        cross(C, 10)
        for p in ((6, 6), (34, 34)):
            _c(s, K, p, 4)
            _c(s, S.ENERGY, p, 3)
    elif v == "b0":   # Nanite Forge: swirl of nanites
        _p(s, K, _ngon(C, 18, 6))
        _p(s, S.STEEL_DARK, _ngon(C, 16, 6))
        _p(s, S.MAGENTA, _ngon(C, 16, 6), 2)
        for i in range(12):
            _c(s, S.GREEN, _polar(C, 6 + i * 0.8, i * 47), 1)
        cross(C, 5, S.WHITE)
    else:             # Overclock Station: gear with a power core
        _p(s, K, _star(C, 19, 14, 10))
        _p(s, S.STEEL, _star(C, 17, 13, 10))
        _c(s, S.MAGENTA, C, 12, 2)
        _c(s, K, C, 8)
        _c(s, S.ORANGE, C, 7)
        _p(s, S.ENERGY, [(21, 14), (16, 21), (20, 21), (18, 27), (24, 19), (20, 19), (22, 14)])


def _sonic(s, v):
    def speaker(c, r, ring=S.STEEL_LIGHT):
        _c(s, K, c, r + 1)
        _c(s, S.STEEL_DARK, c, r)
        for rr in range(r - 2, 2, -3):
            _c(s, ring, c, rr, 1)
        _c(s, K, c, 3)
    if v == "t0":
        speaker(C, 12)
    elif v == "t1":
        for deg in (0, 180):
            p = _polar(C, 14, deg)
            _c(s, K, p, 5)
            _c(s, S.CYAN, p, 4)
        speaker(C, 12)
        _c(s, S.CYAN, C, 13, 1)
    elif v == "t2":
        for p in ((12, 20), (28, 20)):
            speaker(p, 9, S.ENERGY)
        _r(s, K, (14, 6, 12, 28), 3)
        _r(s, S.STEEL, (15, 7, 10, 26), 3)
        _c(s, S.ENERGY, C, 4)
    elif v == "b0":   # Earthshaker: piston hammer
        _r(s, K, (4, 4, 32, 32), 4)
        _r(s, S.STEEL_DARK, (5, 5, 30, 30), 4)
        _r(s, S.MAGENTA, (4, 4, 32, 32), 4, 2)
        for x, y in ((9, 9), (31, 9), (9, 31), (31, 31)):
            _c(s, S.STEEL_LIGHT, (x, y), 2)
        _c(s, K, C, 11)
        _c(s, S.STEEL, C, 10)
        _c(s, S.STEEL_LIGHT, C, 6)
        _c(s, K, C, 2)
    else:             # Resonance Cannon: tuning fork prongs
        for y in (11, 29):
            _r(s, K, (14, y - 3, 26, 6), 2)
            _r(s, S.STEEL_LIGHT, (15, y - 2, 24, 4), 2)
        _r(s, K, (10, 8, 8, 24), 2)
        _r(s, S.MAGENTA, (11, 9, 6, 22), 2)
        for x in (24, 30, 36):
            pygame.draw.arc(s, S.CYAN, (x - 4, 14, 8, 12), -1.2, 1.2, 1)
        _c(s, S.WHITE, (14, 20), 2)



# ---- Phase 5 towers ------------------------------------------------------------------------
CHRONO = (170, 130, 255)          # Chrono Spire violet
OLIVE = (96, 110, 70)
TAR = (34, 26, 22)


def _flak(s, v):
    def barrels(ys, length, col=S.STEEL_LIGHT, w=4):
        for y in ys:
            _r(s, K, (18, y - w // 2 - 1, length + 2, w + 2))
            _r(s, col, (19, y - w // 2, length, w))
            _r(s, K, (18 + length - 1, y - w // 2 - 2, 4, w + 4))     # muzzle brake
    if v == "t0":
        barrels((16, 24), 18)
        _hub(s, (15, 20), 9, OLIVE, None, S.STEEL_DARK, 4)
        _c(s, S.ORANGE, (15, 20), 2)
    elif v == "t1":
        barrels((13, 20, 27), 18)
        _hub(s, (14, 20), 10, OLIVE, S.CYAN, S.STEEL_DARK, 4)
        _c(s, S.ORANGE, (14, 20), 2)
    elif v == "t2":
        barrels((12, 17, 23, 28), 19, w=3)
        _r(s, K, (1, 12, 8, 16), 2)                      # ammo drum
        _r(s, S.ENERGY, (2, 13, 6, 14), 2)
        _hub(s, (15, 20), 10, OLIVE, S.ENERGY, S.STEEL_DARK, 5)
        _c(s, S.ORANGE, (15, 20), 3)
    elif v == "b0":   # Skyburst: one huge flared barrel
        _p(s, K, [(16, 13), (36, 7), (40, 7), (40, 33), (36, 33), (16, 27)])
        _p(s, S.STEEL_LIGHT, [(17, 14), (36, 9), (38, 9), (38, 31), (36, 31), (17, 26)])
        _l(s, S.MAGENTA, (36, 9), (36, 31), 2)
        _hub(s, C, 12, OLIVE, S.MAGENTA, S.STEEL_DARK, 5)
        _p(s, S.ORANGE, _star(C, 5, 2, 5))
    else:             # Hailstorm: rotary six-barrel
        _r(s, K, (14, 10, 26, 20), 3)
        _r(s, S.STEEL_DARK, (15, 11, 24, 18), 3)
        for y in (13, 17, 21, 25):
            _l(s, S.STEEL_LIGHT, (18, y + 1), (39, y + 1), 2)
        _r(s, S.MAGENTA, (31, 10, 3, 20))
        _hub(s, C, 10, OLIVE, S.MAGENTA, S.ORANGE, 4)


def _ion(s, v):
    def coil(x, h, col):
        _r(s, K, (x - 1, 20 - h - 1, 5, h * 2 + 2), 2)
        _r(s, col, (x, 20 - h, 3, h * 2), 2)
    if v == "t0":
        _r(s, K, (12, 16, 28, 8))
        _r(s, S.STEEL, (13, 17, 26, 6))
        for x in (20, 28):
            coil(x, 6, S.CYAN)
        _hub(s, C, 9, S.STEEL_DARK, None, S.CYAN, 4)
    elif v == "t1":
        _r(s, K, (12, 15, 28, 10))
        _r(s, S.STEEL, (13, 16, 26, 8))
        for x in (19, 25, 31):
            coil(x, 7, S.CYAN)
        _r(s, S.WHITE, (37, 18, 3, 4))
        _hub(s, C, 10, S.STEEL_DARK, S.CYAN, S.CYAN, 5)
    elif v == "t2":
        _r(s, K, (10, 14, 30, 12), 2)
        _r(s, S.STEEL, (11, 15, 28, 10), 2)
        for x in (18, 24, 30):
            coil(x, 9, S.ENERGY)
        _r(s, S.CYAN, (36, 17, 4, 6))
        _hub(s, (11, 20), 10, S.STEEL_DARK, S.ENERGY, S.CYAN, 6)
        _c(s, S.WHITE, (11, 20), 2)
    elif v == "b0":   # Orbital Lance: slim, long, ringed
        _l(s, K, (8, 20), (40, 20), 6)
        _l(s, S.STEEL_LIGHT, (8, 20), (39, 20), 3)
        for x in (16, 24, 32):
            _c(s, K, (x, 20), 6, 0)
            _c(s, S.MAGENTA, (x, 20), 5, 2)
        _hub(s, (10, 20), 7, S.STEEL_DARK, S.MAGENTA, S.CYAN, 3)
    else:             # Planet Cracker: split twin barrel with a glowing core
        for y in (11, 29):
            _r(s, K, (12, y - 4, 28, 8), 2)
            _r(s, S.STEEL, (13, y - 3, 26, 6), 2)
        _p(s, S.MAGENTA, [(18, 14), (38, 18), (38, 22), (18, 26)])
        _p(s, S.WHITE, [(20, 18), (38, 19), (38, 21), (20, 22)])
        _hub(s, (12, 20), 11, S.STEEL_DARK, S.MAGENTA, S.CYAN, 6)
        _c(s, S.WHITE, (12, 20), 3)


def _shield(s, v):
    orb = (110, 190, 255)
    def emitter(c, r, trim):
        _c(s, K, c, r + 1)
        _c(s, orb, c, r)
        _c(s, S.WHITE, (c[0] - r // 3, c[1] - r // 3), max(1, r // 3))
        if trim:
            _c(s, trim, c, r + 1, 1)
    if v == "t0":
        _p(s, K, _ngon(C, 14, 6))
        _p(s, S.STEEL, _ngon(C, 12, 6))
        emitter(C, 6, None)
    elif v == "t1":
        for deg in (90, 210, 330):
            p = _polar(C, 14, deg)
            _l(s, K, C, p, 4)
            _c(s, K, p, 4)
            _c(s, S.CYAN, p, 3)
        _p(s, K, _ngon(C, 12, 6))
        _p(s, S.STEEL, _ngon(C, 10, 6))
        emitter(C, 6, S.CYAN)
    elif v == "t2":
        for deg in (45, 135, 225, 315):
            p = _polar(C, 15, deg)
            _l(s, K, C, p, 4)
            _c(s, K, p, 4)
            _c(s, S.ENERGY, p, 3)
        _p(s, K, _ngon(C, 13, 6))
        _p(s, S.STEEL, _ngon(C, 11, 6))
        emitter(C, 7, S.ENERGY)
    elif v == "b0":   # Aegis Dome: big segmented dome
        _c(s, K, C, 18)
        _c(s, (60, 110, 170), C, 17)
        for r in (17, 11):
            _p(s, orb, _ngon(C, r, 6), 1)
        for deg in range(0, 360, 60):
            _l(s, orb, C, _polar(C, 17, deg), 1)
        _c(s, S.MAGENTA, C, 18, 2)
        emitter(C, 5, None)
    else:             # Rapid Recharge: orb wrapped in charging arcs
        _p(s, K, _ngon(C, 13, 6))
        _p(s, S.STEEL, _ngon(C, 11, 6))
        for start in (0.3, 2.4, 4.5):
            pygame.draw.arc(s, S.MAGENTA, (3, 3, 34, 34), start, start + 1.4, 3)
        emitter(C, 7, None)
        _r(s, S.GREEN, (18, 15, 4, 10))
        _r(s, S.GREEN, (15, 18, 10, 4))


def _tar(s, v):
    def blob(r, col=TAR):
        _p(s, K, _star(C, r + 2, r - 1, 7, 0.3))
        _p(s, col, _star(C, r, r - 3, 7, 0.3))
        _c(s, (70, 56, 46), (16, 15), 3)
    def bubbles(col, n=3):
        for i, p in enumerate(((14, 24), (25, 14), (26, 25))[:n]):
            _c(s, col, p, 3 - (i % 2))
            _c(s, S.WHITE, (p[0] - 1, p[1] - 1), 1)
    if v == "t0":
        blob(13)
        bubbles((80, 64, 52), 2)
    elif v == "t1":
        blob(14)
        _r(s, K, (17, 1, 6, 12), 2)            # feed pipe
        _r(s, S.STEEL, (18, 2, 4, 10), 2)
        bubbles(S.CYAN)
    elif v == "t2":
        blob(16)
        _c(s, S.ENERGY, C, 17, 1)
        _r(s, K, (17, 0, 6, 12), 2)
        _r(s, S.ENERGY, (18, 1, 4, 10), 2)
        bubbles((120, 96, 70))
    elif v == "b0":   # Napalm Bog: tar shot through with flame
        blob(16, (60, 26, 16))
        _p(s, S.ORANGE, _star(C, 10, 4, 6))
        _p(s, S.ENERGY, _star(C, 5, 2, 6))
        _c(s, S.MAGENTA, C, 18, 1)
    else:             # Deep Tar: a dark whirlpool
        blob(17, (20, 14, 14))
        for r, a in ((13, 0.0), (9, 1.6), (5, 3.2)):
            pygame.draw.arc(s, (90, 70, 60), (20 - r, 20 - r, r * 2, r * 2), a, a + 3.6, 2)
        _c(s, S.MAGENTA, C, 18, 1)
        _c(s, VOID, C, 2)


def _chrono(s, v):
    def glass(c, h, frame, sand=S.ENERGY):
        w = h * 2 // 3
        top = [(c[0] - w, c[1] - h), (c[0] + w, c[1] - h), (c[0], c[1])]
        bot = [(c[0] - w, c[1] + h), (c[0] + w, c[1] + h), (c[0], c[1])]
        _p(s, K, [(x * 1.0, y) for x, y in top], 0)
        _p(s, K, bot)
        _p(s, (200, 220, 255), [(top[0][0] + 2, top[0][1] + 1), (top[1][0] - 2, top[1][1] + 1), (c[0], c[1] - 1)])
        _p(s, (200, 220, 255), [(bot[0][0] + 2, bot[0][1] - 1), (bot[1][0] - 2, bot[1][1] - 1), (c[0], c[1] + 1)])
        _p(s, sand, [(c[0] - w + 4, c[1] + h - 1), (c[0] + w - 4, c[1] + h - 1), (c[0], c[1] + 3)])
        _l(s, frame, (c[0] - w - 1, c[1] - h - 1), (c[0] + w + 1, c[1] - h - 1), 2)
        _l(s, frame, (c[0] - w - 1, c[1] + h + 1), (c[0] + w + 1, c[1] + h + 1), 2)
    if v == "t0":
        _c(s, K, C, 13)
        _c(s, (60, 50, 100), C, 12)
        glass(C, 8, S.STEEL_LIGHT)
    elif v == "t1":
        _c(s, K, C, 15)
        _c(s, (60, 50, 100), C, 14)
        _c(s, S.CYAN, C, 14, 1)
        for deg in range(0, 360, 30):
            _l(s, S.CYAN, _polar(C, 12, deg), _polar(C, 14, deg), 1)
        glass(C, 9, S.CYAN)
    elif v == "t2":
        _p(s, K, _star(C, 19, 15, 12))
        _p(s, (80, 64, 130), _star(C, 17, 14, 12))
        _c(s, S.ENERGY, C, 15, 2)
        glass(C, 10, S.ENERGY, CHRONO)
    elif v == "b0":   # Time Loop: four glasses circling a ring
        _c(s, K, C, 17, 3)
        _c(s, CHRONO, C, 16, 2)
        _c(s, S.MAGENTA, C, 19, 1)
        for deg in (0, 90, 180, 270):
            glass(_polar(C, 13, deg), 5, S.STEEL_LIGHT)
        _c(s, S.WHITE, C, 2)
    else:             # Stasis Lock: frozen crystal clock
        _p(s, K, _ngon(C, 19, 4, math.pi / 4))
        _p(s, (120, 200, 255), _ngon(C, 17, 4, math.pi / 4))
        _p(s, S.MAGENTA, _ngon(C, 17, 4, math.pi / 4), 2)
        _c(s, K, C, 9)
        _c(s, S.WHITE, C, 8)
        _l(s, K, C, (20, 14), 2)
        _l(s, K, C, (25, 20), 2)
        _c(s, CHRONO, C, 2)



# ---- Phase 5 batch 2 ------------------------------------------------------------------------
HACK = (90, 255, 140)             # Hacker Spire terminal green
HOLO = (120, 230, 255)
PLASMA = (255, 110, 220)


def _decoy(s, v):
    """A pad projecting a little hologram of Vance."""
    def pad(r, trim):
        _c(s, K, C, r + 1)
        _c(s, S.STEEL_DARK, C, r)
        _c(s, HOLO, C, r - 3, 1)
        if trim:
            _c(s, trim, C, r, 1)
    def holo(scale=1.0, col=HOLO):
        def r(x, y, w, h):
            _r(s, col, (20 + x * scale, 20 + y * scale, max(2, w * scale), max(2, h * scale)))
        _p(s, (70, 140, 170), [(20, 30), (12, 34), (28, 34)])               # projector cone
        _c(s, col, (20, 20 - 9 * scale), max(2, int(3 * scale)))           # head
        r(-4, -5, 8, 9)                                                     # torso
        r(-7, -4, 2, 7)                                                     # arms
        r(5, -4, 2, 7)
        r(-4, 4, 3, 6)                                                      # legs
        r(1, 4, 3, 6)
        _l(s, S.WHITE, (20 - 3 * scale, 20 - 3 * scale), (20 + 2 * scale, 20 - 3 * scale), 1)
    if v == "t0":
        pad(12, None)
        holo(1.0)
    elif v == "t1":
        pad(14, S.CYAN)
        for deg in (45, 135, 225, 315):
            _c(s, S.CYAN, _polar(C, 12, deg), 2)
        holo(1.15)
    elif v == "t2":
        _p(s, K, _ngon(C, 18, 8, math.pi / 8))
        _p(s, S.STEEL_DARK, _ngon(C, 16, 8, math.pi / 8))
        _p(s, S.ENERGY, _ngon(C, 16, 8, math.pi / 8), 2)
        holo(1.3)
    elif v == "b0":   # Mirage Field: three overlapping holograms
        pad(17, S.MAGENTA)
        for dx in (-6, 6):
            _c(s, (60, 120, 150), (20 + dx, 15), 3)
            _r(s, (60, 120, 150), (17 + dx, 18, 6, 9))
        holo(1.2)
    else:             # Booby Trap: hologram over a charge
        pad(17, S.MAGENTA)
        for deg in range(0, 360, 60):
            _r(s, S.RED, (*_polar(C, 13, deg), 3, 3))
        holo(1.1, (255, 170, 170))
        _c(s, S.RED, (20, 31), 2)


def _fence(s, v):
    """A pylon with a plasma emitter on top."""
    def pylon(r, trim, core=PLASMA):
        _p(s, K, _ngon(C, r + 2, 4, math.pi / 4))
        _p(s, S.STEEL, _ngon(C, r, 4, math.pi / 4))
        if trim:
            _p(s, trim, _ngon(C, r, 4, math.pi / 4), 2)
        _c(s, K, C, 6)
        _c(s, core, C, 5)
        _c(s, S.WHITE, C, 2)
    if v == "t0":
        pylon(11, None)
    elif v == "t1":
        for deg in (0, 90, 180, 270):
            _l(s, K, C, _polar(C, 17, deg), 4)
            _c(s, PLASMA, _polar(C, 16, deg), 2)
        pylon(12, S.CYAN)
    elif v == "t2":
        for deg in (0, 90, 180, 270):
            _l(s, K, C, _polar(C, 18, deg), 5)
            _l(s, S.ENERGY, C, _polar(C, 17, deg), 2)
        pylon(13, S.ENERGY)
    elif v == "b0":   # Arc Wall: tall coil
        _c(s, K, C, 17)
        _c(s, S.STEEL_DARK, C, 16)
        for r in (14, 10):
            _c(s, PLASMA, C, r, 2)
        _c(s, S.MAGENTA, C, 17, 1)
        _c(s, S.WHITE, C, 4)
    else:             # Overload Grid: node with many emitters
        _p(s, K, _ngon(C, 18, 6))
        _p(s, S.STEEL, _ngon(C, 16, 6))
        _p(s, S.MAGENTA, _ngon(C, 16, 6), 2)
        for deg in range(0, 360, 60):
            _c(s, PLASMA, _polar(C, 11, deg), 3)
        _c(s, S.WHITE, C, 4)


def _mirror(s, v):
    """A tilting mirror panel; it turns toward whatever it's bouncing beams at."""
    glass = (190, 230, 255)
    def panel(w, h, trim, x=18):
        _r(s, K, (x - 1, 20 - h - 1, w + 2, h * 2 + 2), 2)
        _r(s, glass, (x, 20 - h, w, h * 2), 2)
        _l(s, S.WHITE, (x + 1, 20 - h + 2), (x + 1, 20 + h - 6), 1)
        if trim:
            _r(s, trim, (x - 1, 20 - h - 1, w + 2, h * 2 + 2), 2, 1)
    if v == "t0":
        _hub(s, (14, 20), 8, S.STEEL, None, None)
        panel(5, 11, None, 22)
    elif v == "t1":
        _hub(s, (13, 20), 9, S.STEEL, S.CYAN, None)
        panel(5, 13, S.CYAN, 22)
    elif v == "t2":
        _hub(s, (12, 20), 10, S.STEEL, S.ENERGY, None)
        panel(6, 15, S.ENERGY, 22)
        _c(s, S.ENERGY, (12, 20), 3)
    elif v == "b0":   # Prism Splitter: triangular prism
        _hub(s, (11, 20), 8, S.STEEL, S.MAGENTA, None)
        tri = [(18, 6), (18, 34), (36, 20)]
        _p(s, K, [(16, 4), (16, 36), (38, 20)])
        _p(s, glass, tri)
        for col, dy in ((S.RED, -5), (S.ENERGY, 0), (S.CYAN, 5)):
            _l(s, col, (24, 20), (36, 20 + dy), 1)
        _p(s, S.MAGENTA, tri, 1)
    else:             # Focusing Lens: big convex lens
        _hub(s, (11, 20), 8, S.STEEL, S.MAGENTA, None)
        _r(s, K, (20, 3, 12, 34), 6)
        _r(s, glass, (21, 4, 10, 32), 5)
        _r(s, S.MAGENTA, (20, 3, 12, 34), 6, 1)
        _l(s, S.WHITE, (24, 8), (24, 30), 1)


def _hacker(s, v):
    """A terminal mast with a signal dish."""
    def screen(x, y, w, h, trim):
        _r(s, K, (x - 1, y - 1, w + 2, h + 2), 2)
        _r(s, (10, 30, 16), (x, y, w, h), 2)
        for i in range(1, h // 3):
            _l(s, HACK, (x + 2, y + i * 3), (x + 2 + (i * 5) % (w - 3), y + i * 3), 1)
        if trim:
            _r(s, trim, (x - 1, y - 1, w + 2, h + 2), 2, 1)
    def dish(r, col=S.STEEL_LIGHT):
        cx = 38 - r
        pygame.draw.arc(s, K, (cx - r, 20 - r, r * 2, r * 2), -1.3, 1.3, 4)
        pygame.draw.arc(s, col, (cx - r, 20 - r, r * 2, r * 2), -1.3, 1.3, 2)
        _l(s, K, (22, 20), (cx + r - 2, 20), 2)
        _c(s, HACK, (cx + r - 2, 20), 2)
    if v == "t0":
        screen(6, 12, 14, 16, None)
        dish(8)
    elif v == "t1":
        screen(5, 10, 15, 20, S.CYAN)
        dish(10)
    elif v == "t2":
        screen(4, 8, 16, 24, S.ENERGY)
        dish(12, S.ENERGY)
    elif v == "b0":   # Virus: skull glyph on the screen
        screen(4, 8, 18, 24, S.MAGENTA)
        _c(s, HACK, (13, 18), 5)
        _c(s, K, (11, 17), 1)
        _c(s, K, (15, 17), 1)
        _r(s, HACK, (10, 22, 7, 3))
        dish(11, S.MAGENTA)
    else:             # Botnet: three linked nodes
        for p in ((10, 9), (10, 31), (28, 20)):
            _c(s, K, p, 6)
            _c(s, (10, 30, 16), p, 5)
            _c(s, HACK, p, 2)
        for a, b in (((10, 9), (10, 31)), ((10, 9), (28, 20)), ((10, 31), (28, 20))):
            _l(s, S.MAGENTA, a, b, 1)
        _c(s, S.MAGENTA, (28, 20), 7, 1)


def _magnet(s, v):
    """A horseshoe magnet over a coil (spins slowly)."""
    def horseshoe(r, w, tip=S.STEEL_LIGHT, body=S.RED):
        rect = (20 - r, 20 - r, r * 2, r * 2)
        pygame.draw.arc(s, K, rect, math.pi * 0.15, math.pi * 1.85, w + 2)
        pygame.draw.arc(s, body, rect, math.pi * 0.2, math.pi * 1.8, w)
        for deg in (-30, 30):
            p = _polar(C, r - w // 2, deg)
            _r(s, K, (p[0] - 3, p[1] - 3, 7, 7))
            _r(s, tip, (p[0] - 2, p[1] - 2, 5, 5))
    if v == "t0":
        horseshoe(12, 5)
        _c(s, S.STEEL_DARK, C, 4)
    elif v == "t1":
        horseshoe(14, 5)
        _c(s, S.CYAN, C, 5, 1)
        _c(s, S.STEEL_DARK, C, 4)
    elif v == "t2":
        horseshoe(16, 6, S.ENERGY)
        for r in (5, 8):
            _c(s, S.ENERGY, C, r, 1)
    elif v == "b0":   # Demagnetizer: broken field lines
        horseshoe(16, 6, S.STEEL_LIGHT, (150, 60, 180))
        for deg in range(0, 360, 45):
            _l(s, S.MAGENTA, _polar(C, 4, deg), _polar(C, 8, deg), 1)
    else:             # Maglock: double magnet
        horseshoe(17, 4)
        horseshoe(10, 4, S.STEEL_LIGHT, S.MAGENTA)



# ---- Phase 5 batch 3 ------------------------------------------------------------------------
BIO = (140, 230, 90)
FLESH = (196, 110, 120)


def _lightning(s, v):
    """A conductor spire seen from above: rings around a glowing tip."""
    def spire(r, ring, tip=S.ENERGY, n=3):
        _c(s, K, C, r + 1)
        _c(s, S.STEEL_DARK, C, r)
        for i in range(n):
            _c(s, ring, C, r - 3 - i * 3, 1)
        _c(s, K, C, 4)
        _c(s, tip, C, 3)
        _c(s, S.WHITE, C, 1)
    if v == "t0":
        spire(11, S.STEEL_LIGHT, n=2)
    elif v == "t1":
        for deg in (45, 225):
            _l(s, K, C, _polar(C, 18, deg), 3)
            _c(s, S.CYAN, _polar(C, 17, deg), 2)
        spire(13, S.CYAN)
    elif v == "t2":
        for deg in (0, 90, 180, 270):
            _l(s, K, C, _polar(C, 18, deg), 3)
            _c(s, S.ENERGY, _polar(C, 17, deg), 3)
        spire(14, S.ENERGY)
    elif v == "b0":   # Storm Caller: cloud swirl around the tip
        for deg in range(0, 360, 60):
            _c(s, (150, 160, 190), _polar(C, 12, deg), 6)
        for deg in range(30, 390, 60):
            _c(s, (110, 120, 150), _polar(C, 13, deg), 4)
        _c(s, S.MAGENTA, C, 18, 1)
        _p(s, S.ENERGY, [(21, 10), (16, 21), (20, 21), (18, 30), (25, 18), (21, 18), (23, 10)])
    else:             # Capacitor Bank: banks of cells
        _r(s, K, (4, 4, 32, 32), 4)
        _r(s, S.STEEL_DARK, (5, 5, 30, 30), 4)
        for x, y in ((8, 8), (22, 8), (8, 22), (22, 22)):
            _r(s, K, (x, y, 10, 10), 2)
            _r(s, S.ENERGY, (x + 1, y + 1, 8, 8), 2)
            _r(s, S.WHITE, (x + 3, y + 2, 2, 3))
        _r(s, S.MAGENTA, (4, 4, 32, 32), 4, 2)
        _c(s, S.WHITE, C, 3)


def _biolab(s, v):
    """A round vat of green goo with feed tubes."""
    def vat(r, trim, goo=BIO):
        _c(s, K, C, r + 1)
        _c(s, (60, 70, 80), C, r)
        _c(s, goo, C, r - 3)
        _c(s, (220, 255, 200), (17, 17), 2)
        _c(s, (220, 255, 200), (23, 22), 1)
        if trim:
            _c(s, trim, C, r, 1)
    if v == "t0":
        _l(s, K, (20, 20), (36, 20), 4)
        vat(11, None)
    elif v == "t1":
        for deg in (0, 180):
            _l(s, K, C, _polar(C, 19, deg), 4)
            _l(s, BIO, C, _polar(C, 18, deg), 2)
        vat(12, S.CYAN)
    elif v == "t2":
        for deg in (0, 90, 180, 270):
            _l(s, K, C, _polar(C, 19, deg), 4)
            _l(s, BIO, C, _polar(C, 18, deg), 2)
        vat(14, S.ENERGY)
    elif v == "b0":   # Rendering Plant: crushers around the vat
        for deg in (45, 135, 225, 315):
            p = _polar(C, 14, deg)
            _r(s, K, (p[0] - 5, p[1] - 5, 10, 10), 2)
            _r(s, S.STEEL, (p[0] - 4, p[1] - 4, 8, 8), 2)
        vat(12, S.MAGENTA, (110, 200, 70))
    else:             # Mutagen Lab: purple mutagen with a helix
        vat(15, S.MAGENTA, (170, 90, 210))
        for i in range(7):
            y = 10 + i * 3
            dx = int(5 * math.sin(i * 0.9))
            _c(s, BIO, (20 + dx, y), 2)
            _c(s, S.WHITE, (20 - dx, y), 1)


def _overclock(s, v):
    """A cog with heat vents (spins slowly)."""
    def cog(r, body, trim, core=S.ORANGE):
        _p(s, K, _star(C, r + 2, r - 2, 8))
        _p(s, body, _star(C, r, r - 3, 8))
        if trim:
            _p(s, trim, _star(C, r, r - 3, 8), 1)
        _c(s, K, C, 6)
        _c(s, core, C, 5)
        _c(s, S.ENERGY, C, 2)
    if v == "t0":
        cog(13, S.STEEL, None)
    elif v == "t1":
        cog(15, S.STEEL, S.CYAN)
    elif v == "t2":
        cog(17, (150, 140, 120), S.ENERGY, S.RED)
    elif v == "b0":   # Turbo Core: double cog, red-hot
        cog(18, (120, 90, 90), S.MAGENTA, S.RED)
        _p(s, S.ORANGE, _star(C, 9, 6, 6, 0.3))
        _c(s, S.ENERGY, C, 3)
    else:             # Cryo-Cooled: frosty cog with coolant ring
        cog(17, (150, 190, 220), S.MAGENTA, S.CRYO)
        _c(s, S.CRYO, C, 11, 2)
        for deg in range(0, 360, 60):
            _l(s, S.WHITE, _polar(C, 9, deg), _polar(C, 13, deg), 1)


def _uplink(s, v):
    """A satellite dish seen from above."""
    def dish(r, trim, rim=S.STEEL_LIGHT):
        _c(s, K, C, r + 1)
        _c(s, rim, C, r)
        _c(s, (200, 210, 225), C, r - 2)
        for rr in (r - 5, r - 9):
            if rr > 2:
                _c(s, S.STEEL, C, rr, 1)
        if trim:
            _c(s, trim, C, r + 1, 1)
        for deg in (90, 210, 330):        # feed arms
            _l(s, K, _polar(C, r - 1, deg), C, 2)
        _c(s, K, C, 3)
        _c(s, S.RED, C, 2)
    if v == "t0":
        dish(12, None)
    elif v == "t1":
        dish(14, S.CYAN)
    elif v == "t2":
        dish(16, S.ENERGY, S.ENERGY)
    elif v == "b0":   # Twin Strike: two dishes
        for c in ((12, 14), (28, 26)):
            _c(s, K, c, 10)
            _c(s, (200, 210, 225), c, 9)
            _c(s, S.MAGENTA, c, 9, 1)
            _c(s, S.RED, c, 2)
        _l(s, S.MAGENTA, (12, 14), (28, 26), 1)
    else:             # Targeting Array: dish with crosshair
        dish(17, S.MAGENTA)
        _l(s, S.RED, (20, 4), (20, 36), 1)
        _l(s, S.RED, (4, 20), (36, 20), 1)
        _c(s, S.RED, C, 9, 1)


def _bait(s, v):
    """A fleshy alien-attracting pod with a bullseye."""
    def pod(r, col=FLESH, trim=None):
        _p(s, K, _ngon(C, r + 2, 10))
        _p(s, col, _ngon(C, r, 10))
        _c(s, (240, 220, 200), C, r - 4, 2)
        _c(s, S.RED, C, r - 8 if r > 10 else 3)
        _c(s, (240, 220, 200), C, 2)
        if trim:
            _p(s, trim, _ngon(C, r, 10), 2)
    if v == "t0":
        pod(12)
    elif v == "t1":
        pod(14, trim=S.CYAN)
    elif v == "t2":
        for deg in range(0, 360, 45):
            _r(s, K, (*[int(c) - 2 for c in _polar(C, 16, deg)], 5, 5))
            _r(s, S.ENERGY, (*[int(c) - 1 for c in _polar(C, 16, deg)], 3, 3))
        pod(15, trim=S.ENERGY)
    elif v == "b0":   # Spore Pod: spore bulbs
        for deg in range(0, 360, 60):
            p = _polar(C, 15, deg)
            _c(s, K, p, 4)
            _c(s, (170, 220, 90), p, 3)
        pod(13, (180, 120, 110), S.MAGENTA)
    else:             # Regenerator: pod wrapped in a green heal ring
        pod(16, (200, 130, 140), S.MAGENTA)
        _c(s, S.GREEN, C, 18, 2)
        _r(s, S.GREEN, (18, 14, 4, 12))
        _r(s, S.GREEN, (14, 18, 12, 4))


def _generator(s, v):
    """A reactor drum with power coils (spins slowly)."""
    def drum(r, trim, core=S.ENERGY):
        _p(s, K, _ngon(C, r + 2, 8, math.pi / 8))
        _p(s, (70, 76, 92), _ngon(C, r, 8, math.pi / 8))
        if trim:
            _p(s, trim, _ngon(C, r, 8, math.pi / 8), 2)
        _c(s, K, C, r - 5)
        _c(s, core, C, r - 6)
        _c(s, S.WHITE, C, max(2, r // 4))
    if v == "t0":
        drum(12, None)
    elif v == "t1":
        for deg in (0, 120, 240):
            _c(s, K, _polar(C, 16, deg), 4)
            _c(s, S.CYAN, _polar(C, 16, deg), 3)
        drum(13, S.CYAN)
    elif v == "t2":
        for deg in (0, 90, 180, 270):
            _c(s, K, _polar(C, 16, deg), 4)
            _c(s, S.ENERGY, _polar(C, 16, deg), 3)
        drum(14, S.ENERGY, S.ORANGE)
    elif v == "b0":   # Fusion Reactor: torus with a plasma core
        _c(s, K, C, 19)
        _c(s, (70, 76, 92), C, 18)
        _c(s, S.MAGENTA, C, 18, 2)
        _c(s, S.CYAN, C, 13, 3)
        _c(s, S.WHITE, C, 6)
        _c(s, S.MAGENTA, C, 3)
    else:             # Grid Hub: node with cable sockets
        for deg in range(0, 360, 45):
            _l(s, K, C, _polar(C, 19, deg), 3)
            _c(s, S.ENERGY, _polar(C, 18, deg), 2)
        drum(12, S.MAGENTA)


def _brood(s, v):
    """An alien egg cluster (it's an alien tower, after all)."""
    trim = {"t0": None, "t1": S.CYAN, "t2": S.ENERGY, "b0": S.MAGENTA, "b1": S.MAGENTA}[v]
    n = {"t0": 3, "t1": 4, "t2": 5, "b0": 3, "b1": 7}[v]
    _c(s, K, C, 17)
    _c(s, (74, 58, 72), C, 16)
    if trim:
        _c(s, trim, C, 16, 2)
    for i in range(n):
        p = _polar(C, 8 if n > 1 else 0, i * 360 / n)
        r = 6 if v != "b0" else 8
        _c(s, K, p, r + 1)
        _c(s, (190, 80, 180) if v != "b0" else (120, 140, 100), p, r)
        _c(s, S.ALIEN_GREEN, (p[0] - 1, p[1] - 1), 2)


BRANCH_ART = {"flamer": _flamer_b, "mortar": _mortar_b, "gravity": _gravity_b, "harvester": _harvester_b,
              "radar": _radar_b, "drone": _drone_b, "barricade": _barricade_b, "mines": _mines_b}
NEW_TOWERS = {"laser": _laser, "acid": _acid, "repair": _repair, "sonic": _sonic,
              "flak": _flak, "ion": _ion, "shield": _shield, "tar": _tar, "chrono": _chrono,
              "decoy": _decoy, "fence": _fence, "mirror": _mirror, "hacker": _hacker, "magnet": _magnet,
              "lightning": _lightning, "biolab": _biolab, "overclock": _overclock, "uplink": _uplink,
              "bait": _bait, "generator": _generator, "brood": _brood}
TURRETS.update(NEW_TOWERS)
BRANCHED.update(BRANCH_ART)
BRANCHED.update(NEW_TOWERS)


# ---- beams and pools ---------------------------------------------------------------------
BEAM_COLORS = {None: S.RED, 0: (120, 200, 255), 1: S.MAGENTA}


def draw_beam(screen, start, end, heat, branch=None):
    """Laser Lance beam. heat 0..1 = how far the damage ramp has climbed."""
    heat = max(0.0, min(1.0, heat))
    color = BEAM_COLORS.get(branch, S.RED)
    width = 2 + int(heat * (5 if branch == 1 else 3))
    pygame.draw.line(screen, color, start, end, width + 2)
    pygame.draw.line(screen, S.WHITE, start, end, max(1, width - 2))
    pygame.draw.circle(screen, S.WHITE, (int(end[0]), int(end[1])), 2 + int(heat * 3))


_POOL_CACHE = {}


def draw_puddle(screen, pos, radius, fade, level):
    """Acid pool. fade 0..1 (fades out over its last moments)."""
    radius = int(radius)
    alpha = int(150 * max(0.0, min(1.0, fade)))
    key = (radius, level, alpha // 15)
    surf = _POOL_CACHE.get(key)
    if surf is None:
        col = ((120, 220, 60), (100, 210, 50), (70, 170, 40))[level]
        surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        a = (alpha // 15) * 15
        pygame.draw.circle(surf, (*col, a // 2), (radius + 1, radius + 1), radius)
        pygame.draw.circle(surf, (*col, a), (radius + 1, radius + 1), radius, 2)
        for i in range(5):
            p = _polar((radius + 1, radius + 1), radius * 0.55, i * 72 + level * 20)
            pygame.draw.circle(surf, (200, 255, 140, a), (int(p[0]), int(p[1])), 2)
        _POOL_CACHE[key] = surf
    screen.blit(surf, surf.get_rect(center=(int(pos[0]), int(pos[1]))))


# ---- Phase 5 effects -------------------------------------------------------------------
_MAP_SURF = {}


def _map_layer():
    surf = _MAP_SURF.get("layer")
    if surf is None:
        surf = pygame.Surface((S.MAP_W, S.MAP_H), pygame.SRCALPHA)
        _MAP_SURF["layer"] = surf
    surf.fill((0, 0, 0, 0))
    return surf


ION_COLORS = {None: (120, 220, 255), 0: (200, 140, 255), 1: (255, 120, 230)}


def draw_ion(screen, routes, origin, fade, branch, offset):
    """Ion Cannon blast: a glowing column down every lane, fading out. fade 1 -> 0."""
    layer = _map_layer()
    col = ION_COLORS.get(branch, ION_COLORS[None])
    a = int(255 * max(0.0, min(1.0, fade)))
    width = 6 + int(18 * fade) + (8 if branch == 1 else 0)
    for route in routes:
        pts = [(int(x), int(y)) for x, y in route]
        if len(pts) < 2:
            continue
        pygame.draw.lines(layer, (*col, a // 3), False, pts, width + 10)
        pygame.draw.lines(layer, (*col, a), False, pts, width)
        pygame.draw.lines(layer, (255, 255, 255, a), False, pts, max(2, width // 3))
        for p in pts:
            pygame.draw.circle(layer, (*col, a), p, width // 2)
    ox, oy = int(origin[0]), int(origin[1])
    pygame.draw.line(layer, (*col, a), (ox, oy), (ox, 0), 4 + int(6 * fade))   # uplink to orbit
    pygame.draw.circle(layer, (255, 255, 255, a), (ox, oy), 6 + int(10 * fade))
    screen.blit(layer, (offset[0], offset[1]))


_BUBBLE_CACHE = {}


def draw_bubble(screen, pos, frac, t):
    """Shield Projector bubble over a tower. frac = shield left (0..1)."""
    level = max(1, int(frac * 8))
    surf = _BUBBLE_CACHE.get(level)
    if surf is None:
        surf = pygame.Surface((44, 44), pygame.SRCALPHA)
        a = 30 + level * 12
        pygame.draw.circle(surf, (110, 190, 255, a // 3), (22, 22), 20)
        pygame.draw.circle(surf, (150, 210, 255, a), (22, 22), 20, 2)
        _BUBBLE_CACHE[level] = surf
    screen.blit(surf, surf.get_rect(center=(int(pos[0]), int(pos[1]))))
    ang = t * 2.0
    pygame.draw.arc(screen, (220, 240, 255), (pos[0] - 20, pos[1] - 20, 40, 40), ang, ang + 0.6, 1)


_TAR_CACHE = {}
TAR_TINTS = ((48, 36, 30), (44, 34, 30), (40, 30, 28), (30, 22, 20))


def draw_tar(screen, pos, radius, level, burning, t):
    """Tar Pit pool. level 0-2 = tier, 3 = branch."""
    radius = max(12, int(radius * 0.8))
    key = (radius, level)
    surf = _TAR_CACHE.get(key)
    if surf is None:
        size = radius * 2 + 4
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        col = TAR_TINTS[level]
        n = 24
        pts = [(c[0] + radius * (0.9 + 0.1 * math.sin(i * 2.3)) * math.cos(i * math.tau / n),
                c[1] + radius * (0.9 + 0.1 * math.sin(i * 2.3)) * math.sin(i * math.tau / n))
               for i in range(n)]
        pygame.draw.polygon(surf, (*col, 200), pts)
        pygame.draw.polygon(surf, (16, 12, 10, 230), pts, 2)
        inner = [(c[0] + (x - c[0]) * 0.6, c[1] + (y - c[1]) * 0.6) for x, y in pts]
        pygame.draw.polygon(surf, (*[max(0, v - 14) for v in col], 220), inner)
        pygame.draw.ellipse(surf, (150, 130, 110, 90), (c[0] - radius * 0.55, c[1] - radius * 0.6,
                                                        radius * 0.7, radius * 0.25))   # sheen
        _TAR_CACHE[key] = surf
    screen.blit(surf, surf.get_rect(center=(int(pos[0]), int(pos[1]))))
    if burning:
        for i in range(6):
            a = t * 3 + i * 1.05
            r = radius * (0.25 + 0.5 * ((i * 37) % 10) / 10)
            fx = pos[0] + math.cos(a) * r
            fy = pos[1] + math.sin(a) * r
            h = 4 + 3 * math.sin(t * 12 + i)
            pygame.draw.polygon(screen, S.ORANGE, [(fx - 3, fy), (fx + 3, fy), (fx, fy - h - 4)])
            pygame.draw.polygon(screen, S.ENERGY, [(fx - 1.5, fy), (fx + 1.5, fy), (fx, fy - h)])


FENCE_COLORS = {0: PLASMA, 1: (255, 140, 230), 2: (255, 190, 120), 3: S.MAGENTA}


def draw_fence(screen, a, b, level):
    """Plasma Fence beam between two pylons: a jittery glowing line."""
    import random
    col = FENCE_COLORS.get(level, PLASMA)
    pts = [a]
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 14))
    for i in range(1, n):
        t = i / n
        pts.append((a[0] + (b[0] - a[0]) * t + random.uniform(-2, 2),
                    a[1] + (b[1] - a[1]) * t + random.uniform(-2, 2)))
    pts.append(b)
    pygame.draw.lines(screen, col, False, pts, 4 if level >= 2 else 3)
    pygame.draw.lines(screen, S.WHITE, False, pts, 1)


def draw_hack(screen, pos, radius, frac):
    """Green bracket marker on a hacked alien. frac = hack time left (0..1)."""
    r = int(radius + 6)
    x, y = int(pos[0]), int(pos[1])
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy = x + sx * r, y + sy * r
        pygame.draw.line(screen, HACK, (cx, cy), (cx - sx * 5, cy), 2)
        pygame.draw.line(screen, HACK, (cx, cy), (cx, cy - sy * 5), 2)
    pygame.draw.arc(screen, HACK, (x - r, y - r - 6, r * 2, r * 2), math.pi / 2,
                    math.pi / 2 + math.tau * max(0.0, min(1.0, frac)), 2)

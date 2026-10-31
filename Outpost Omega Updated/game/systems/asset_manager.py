"""AssetManager: loads and caches sprites and fonts.

image("skitter_0") first looks for assets/sprites/skitter_0.png. If that
file doesn't exist it builds a placeholder in code (pixel maps below), so
the game always runs and you can drop real art in later without changing
any other code. Sprite names are listed in SPRITE_NAMES.
"""
import math
import os

import pygame

from .. import settings as S
from . import tower_art

# Pixel-map palette: one character = one pixel.
PALETTE = {
    "k": (22, 22, 34),          # outline
    "s": S.STEEL, "S": S.STEEL_LIGHT, "d": S.STEEL_DARK,
    "c": S.CYAN, "o": S.ORANGE, "y": S.ENERGY, "w": S.WHITE,
    "g": S.ALIEN_GREEN, "G": S.ALIEN_DARK,
    "m": S.MAGENTA, "M": S.MAGENTA_DARK,
    "r": S.RED, "b": S.CRYO, "e": (12, 12, 12),
    "n": (150, 104, 64), "N": (96, 64, 40), "a": S.ACID, "W": (255, 255, 255),
}

# ---- Phase 3 aliens --------------------------------------------------------------
MENDER = [
    "....kkkk....", "...kggggk...", "..kgWWWWgk..", ".kggWrrWggk.",
    ".kgWWrrWWgk.", ".kgWrrrrWgk.", ".kggWrrWggk.", "..kgWWWWgk..",
    "..kGggggGk..", "..kg.kk.gk..", ".kk......kk.", "............",
]
JUGGERNAUT = [
    "....kkkkkkkk....", "...kddddddddk...", "..kdSSssssSSdk..", ".kdSsmmssmmsSdk.",
    ".kdssssssssssdk.", "kddSSddddddSSddk", "kdsdSssssssSdsdk", "kdsdssGGGGssdsdk",
    "kdsdsGggggGsdsdk", "kddsssGGGGsssddk", ".kdddssssssdddk.", ".kdSdddddddddSdk",
    "..kddk.kk.kddk..", "..kSSk....kSSk..", ".kddddk..kddddk.", ".kkkkkk..kkkkkk.",
]
CLOAKER = [
    "....kkkk....", "...kMMMMk...", "..kMmmmmMk..", "..kMcMMcMk..",
    ".kkMmmmmMkk.", "k.kMMmmMMk.k", "..kMmmmmMk..", "..kMM..MMk..",
    ".kMk....kMk.", ".kk......kk.",
]
BURROWER = [
    "....kkkkkk....", "...kNnnnnNk...", "..kNnSSSSnNk..", ".kNnSddddSnNk.",
    "kNnnSdyydSnnNk", "kNnnnSSSSnnnNk", "kNnmnnnnnnmnNk", ".kNnnnnnnnnNk.",
    "..kNNk..kNNk..", ".kNk......kNk.",
]
SPITTER = [
    "....kkkk....", "...kggggk...", "..kgmggmgk..", "..kgggggGk..",
    ".kgkaaaakgk.", ".kgaaaaaagk.", "..kGaaaaGk..", "..kgggggGk..",
    "..kgk..kgk..", ".kk......kk.",
]
HIVE_EGG = [
    "...kkkk...", "..kmmmmk..", ".kmMmmMmk.", ".kmmggmmk.", "kmmgaagmmk",
    "kmMgaagMmk", "kmmmggmmmk", ".kmMmmMmk.", "..kmmmmk..", "...kkkk...",
]
SIEGE_TITAN = [
    "......kkkkkkkkkk......", "....kkddddddddddkk....", "...kddSSSSSSSSSSddk...",
    "..kdSSddmmddmmddSSdk..", ".kdSdddrrdddrrdddSdk..", "kddSddddddddddddSddk..",
    "kdSSdssssssssssdSSdk..", "kdSdsGGGGGGGGGGsdSdk..", "kdSdsGggggggggGsdSdk..",
    "kdSdsGGGGGGGGGGsdSdk..", "kddSdssssssssssdSddk..", ".kdSSddddddddddSSdk...",
    "..kddkkddddddkkddk....", "..kSSk.kSSSSk.kSSk....", ".kddddkkddddkkddddk...",
    ".kkkkkk.kkkk.kkkkkk...",
]
SHIELD_DRONE = [
    "....kkkk....", "..kkccccKk..".replace("K", "k"), ".kcSSSSSSck.", "kcSdddddSSck",
    "kcSdccccdSck", "kcSdcwwcdSck", "kcSdccccdSck", "kcSSddddSSck",
    ".kcSSSSSSck.", "..kkcccckk..", "....kkkk....", "............",
]
HUNTER = [
    "k..........k", ".kk.kkkk.kk.", "..krrrrrrk..", ".krryrryrrk.",
    "kkrrrrrrrrkk", "..krGrrGrk..", ".krrrrrrrrk.", "kk.krrrrk.kk",
    "...kr..rk...", "..kk....kk..",
]
MIMIC = [
    "....kkkk....", "...kyyyyk...", "..kyWyyyyk..", ".kyyyyyyyyk.",
    "kyykwkwkwyyk", "kyrrrrrrrryk", "kyykwkwkwyyk", ".kyyyyyyyyk.",
    "..kgk..kgk..", ".kk......kk.",
]
CARRIER = [
    "kk..................kk", "mmkk....kkkkkk....kkmm", "mMmmkkkkmmmmmmkkkkmmMm",
    ".mMMmmmmggggggmmmmMMm.", "..mMMMmgGggggGgmMMMm..", "...mmmmggmmmmggmmmm...",
    "....kkmggggggggmkk....", "......kmGGGGGGmk......", ".......kkggggkk.......",
    ".........kkkk.........",
]
BURROW_WYRM = [
    "........kkkkkk........", "......kknnnnnnkk......", ".....knnSSSSSSnnk.....",
    "....knSSdrrrrdSSnk....", "...knnSdryyyyrdSnnk...", "..knnnSdrrrrrrdSnnnk..",
    ".knNnnnSSddddSSnnnNnk.", "knNNnnnnnnnnnnnnnnNNnk", "knNnnNnnNnnNnnNnnNnnNk",
    ".kNnnNnnNnnNnnNnnNnNk.", "..kNNkkNNkkNNkkNNkNk..", "...kk..kk..kk..kk.k...",
]
HIVE_QUEEN = [
    "kk....kkkkkkkkkk....kk", "mmk.kkmmmmmmmmmmkk.kmm", "mMmkmmMMmmmmmmMMmmkmMm",
    ".mMmmMggggggggggMmmMm.", ".kmMggmmggyyggmmggMmk.", "kmMggmeemggggmeemggMmk",
    "kmmMgggmmggggmmgggMmmk", "kmMggggggggggggggggMmk", "kmMgggaaggggggaagggMmk",
    "kmMggggaaaaaaaaggggMmk", ".kmMggggggggggggggMmk.", "..kmmMMMggggggMMMmmk..",
    "...kmmmmMMMMMMmmmmk...", "..kmMk.kmmk.kmmk.kMmk.", ".kmmk..kmk...kmk..kmmk",
    ".kkk...kkk...kkk...kkk",
]

COMMANDER_TOP = [
    "................",
    "......kkkk......",
    ".....kSSSSk.....",
    "....kSccccSk....",
    "....kScwccSk....",
    "....kdSSSSdk....",
    "..kkkkkddkkkkk..",
    ".kSSskooooksSSk.",
    ".kSdskoyyoksdSk.",
    ".kSdsskooksdsSk.",
    ".kkkskssssskkkk.",
    "....kdssssdk....",
]
COMMANDER_LEGS = [
    ["....kSdkkdSk....", "....kSk..kSk....", "...kSSk..kSSk...", "...kkkk..kkkk..."],
    ["....kSdkkdSk....", ".....kSkkSk.....", "....kSSk.kSSk...", "....kkkk.kkkk..."],
]
COMMANDER_DOWN = [
    "................", "................", "................", "................",
    "................", "................", "..kkkkkkkkkkkk..", ".kSSsdddddsoSSk.",
    "kSccSsskooossSdk", "kScwSssoyyossSdk", ".kSSsdddddsoSSk.", "..kkkkkkkkkkkk..",
    "................", "................", "................", "................",
]

SKITTER = [
    [
        "k..........k", ".k..kkkk..k.", "..kkggggkk..", "...kgmmgk...",
        "kkkggggggkkk", "..kgGggGgk..", "..kgggggGk..", "kkkgGggggkkk",
        "...kggggk...", "..kk.kk.kk..", ".k........k.", "k..........k",
    ],
    [
        "............", "kk..kkkk..kk", "..kkggggkk..", "...kgmmgk...",
        ".kkggggggkk.", "k.kgGggGgk.k", "..kgggggGk..", ".kkgGggggkk.",
        "k..kggggk..k", "...k.kk.k...", "..k......k..", "............",
    ],
]

BRUTE = [
    "....kkkkkkkk....", "...kGGGGGGGGk...", "..kGddddddddGk..", ".kGdssssssssdGk.",
    ".kGdsmmssmmsdGk.", "kgGdssssssssdGgk", "kgGGddddddddGGgk", "kggGGGggggGGGggk",
    "kggggGGGGGGggggk", "kgGggggggggggGgk", ".kgGggggggggGgk.", ".kggGGggggGGggk.",
    "..kgggkkkkgggk..", "..kGGk....kGGk..", ".kGGGk....kGGGk.", ".kkkkk....kkkkk.",
]
BRUTE_STEP = BRUTE[:12] + [
    "..kgggkkkkgggk..", "...kGGk..kGGk...", "..kGGGk..kGGGk..", "..kkkkk..kkkkk..",
]

GLIDER = [
    [
        "k..............k", "mk............km", "mmk....kk....kmm", "mMmk..kggk..kmMm",
        ".mMmkkgmmgkkmMm.", ".mMMmmggggmmMMm.", "..mMMmggggmMMm..", "...mmMggggMmm...",
        "....kmggggmk....", ".....kgGGgk.....", "......kggk......", ".......kk.......",
    ],
    [
        "................", "................", ".......kk.......", "kk....kggk....kk",
        "mMkkkkgmmgkkkkMm", "mMMMmmggggmmMMMm", ".mmMMmggggmMMmm.", "...mmMggggMmm...",
        "....kmggggmk....", ".....kgGGgk.....", "......kggk......", ".......kk.......",
    ],
]

BROOD_SAC = [
    "....kkkkkk....", "..kkmmmmmmkk..", ".kmmMmmmmMmmk.", ".kmgmmMMmmgmk.",
    "kmmmggmmggmmmk", "kmMmmmmmmmmMmk", "kmmgmmMMmmgmmk", "kmmmmggggmmmmk",
    ".kmMmmmmmmMmk.", ".kkmmgmmgmmkk.", "..k.kkkkkk.k..", ".k..........k.",
]

SABOTEUR = [
    "....kkkk....", "...kggggk...", "..kgccccgk..", "..kgggggGk..",
    ".kkGgyygGkk.", "k.kgggggGk.k", "..kGgggGGk..", "..kgg..ggk..",
    ".kgk....kgk.", ".kk......kk.",
]

OVERSEER = [
    "......kkkkkkkkkk......", "....kkmmmmmmmmmmkk....", "...kmmMMmmmmmmMMmmk...",
    "..kmmMggggggggggMmmk..", ".kmmMggmmggggmmggMmmk.", ".kmMggmeemggmeemggMmk.",
    "kmmMgggmmggggmmgggMmmk", "kmMggggggggggggggggMmk", "kmMgggGGggggggGGgggMmk",
    "kmMggggGGGGGGGGggggMmk", ".kmMggggggggggggggMmk.", ".kmmMMggggggggggMMmmk.",
    "..kmmmMMMMMMMMMMmmmk..", "...kkmmk.kmmk.kmmkk...", "..kmmk..kmmk..kmmk....",
    "..kkk...kkk...kkk.....",
]

SPRITE_NAMES = [
    "commander_0", "commander_1", "commander_down",
    "skitter_0", "skitter_1", "brute_0", "brute_1", "glider_0", "glider_1",
    "brood_sac_0", "saboteur_0", "hive_overseer_0",
    "mender_0", "juggernaut_0", "cloaker_0", "burrower_0", "spitter_0", "hive_egg_0",
    "siege_titan_0", "hive_queen_0", "shield_drone_0", "hunter_0", "mimic_0", "carrier_0",
    "burrow_wyrm_0",
    "tower_base", "turret_pulse", "turret_tesla", "turret_cryo",
    "turret_railgun", "turret_missile", "turret_flamer", "turret_mortar", "turret_gravity",
    "turret_harvester", "turret_radar", "turret_drone", "turret_barricade", "turret_mines", "core",
    "energy_crystal", "repair_kit", "overcharge", "shield_battery",
] + tower_art.variant_names()   # upgraded tower looks, branches, drones


def from_pixels(rows, scale=2):
    width = max(len(r) for r in rows)
    surf = pygame.Surface((width * scale, len(rows) * scale), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row.ljust(width, ".")):
            color = PALETTE.get(ch)
            if color:
                surf.fill(color, (x * scale, y * scale, scale, scale))
    return surf


def _tower_base():
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.rect(s, (22, 22, 34), (1, 1, 30, 30), border_radius=6)
    pygame.draw.rect(s, S.STEEL_DARK, (3, 3, 26, 26), border_radius=5)
    pygame.draw.rect(s, S.STEEL, (5, 5, 22, 22), border_radius=4)
    for bx, by in ((7, 7), (24, 7), (7, 24), (24, 24)):
        pygame.draw.circle(s, S.STEEL_LIGHT, (bx, by), 2)
    return s


def _turret(kind):
    s = pygame.Surface((40, 40), pygame.SRCALPHA)
    c = (20, 20)
    k = (22, 22, 34)
    if kind == "pulse":
        pygame.draw.rect(s, k, (18, 16, 20, 8))
        pygame.draw.rect(s, S.STEEL_LIGHT, (19, 17, 18, 6))
        pygame.draw.rect(s, S.ORANGE, (33, 17, 4, 6))
        pygame.draw.circle(s, k, c, 10)
        pygame.draw.circle(s, S.STEEL, c, 9)
        pygame.draw.circle(s, S.CYAN, c, 4)
    elif kind == "cryo":
        pts = [(c[0] + 11 * math.cos(a), c[1] + 11 * math.sin(a))
               for a in [i * math.pi / 3 for i in range(6)]]
        pygame.draw.polygon(s, k, pts)
        inner = [(c[0] + 9 * math.cos(a), c[1] + 9 * math.sin(a))
                 for a in [i * math.pi / 3 for i in range(6)]]
        pygame.draw.polygon(s, S.STEEL_LIGHT, inner)
        pygame.draw.polygon(s, S.CRYO, [(20, 13), (25, 20), (20, 27), (15, 20)])
        pygame.draw.polygon(s, S.WHITE, [(20, 15), (22, 20), (20, 22), (18, 20)])
    elif kind == "tesla":
        pygame.draw.circle(s, k, c, 11)
        pygame.draw.circle(s, S.STEEL_DARK, c, 10)
        for r in (8, 5):
            pygame.draw.circle(s, S.ORANGE, c, r, 2)
        pygame.draw.circle(s, S.CYAN, c, 3)
    elif kind == "railgun":
        pygame.draw.rect(s, k, (14, 15, 26, 10))
        pygame.draw.rect(s, S.STEEL_DARK, (15, 16, 24, 3))
        pygame.draw.rect(s, S.STEEL_DARK, (15, 21, 24, 3))
        pygame.draw.rect(s, S.CYAN, (17, 19, 22, 2))
        pygame.draw.circle(s, k, c, 9)
        pygame.draw.circle(s, S.STEEL, c, 8)
    elif kind == "missile":
        pygame.draw.rect(s, k, (9, 9, 22, 22), border_radius=3)
        pygame.draw.rect(s, S.STEEL, (10, 10, 20, 20), border_radius=3)
        for mx, my in ((15, 15), (25, 15), (15, 25), (25, 25)):
            pygame.draw.circle(s, S.RED, (mx, my), 3)
    elif kind == "flamer":
        pygame.draw.polygon(s, k, [(18, 14), (38, 11), (38, 29), (18, 26)])
        pygame.draw.polygon(s, S.STEEL_DARK, [(19, 15), (36, 13), (36, 27), (19, 25)])
        pygame.draw.rect(s, S.ORANGE, (34, 15, 4, 10))
        pygame.draw.circle(s, k, c, 10)
        pygame.draw.circle(s, S.RED, c, 9)
        pygame.draw.circle(s, S.ENERGY, c, 4)
    elif kind == "mortar":
        pygame.draw.circle(s, k, c, 13)
        pygame.draw.circle(s, S.STEEL_DARK, c, 12)
        pygame.draw.circle(s, k, (26, 20), 8)
        pygame.draw.circle(s, S.STEEL, (26, 20), 7)
        pygame.draw.circle(s, (22, 22, 34), (28, 20), 4)
    elif kind == "gravity":
        pygame.draw.circle(s, k, c, 12)
        pygame.draw.circle(s, S.MAGENTA_DARK, c, 11)
        pygame.draw.arc(s, S.MAGENTA, (10, 10, 20, 20), 0, 3.6, 3)
        pygame.draw.arc(s, S.MAGENTA, (14, 14, 12, 12), 3.1, 6.3, 2)
        pygame.draw.circle(s, S.WHITE, c, 3)
    elif kind == "harvester":
        pygame.draw.rect(s, k, (9, 9, 22, 22), border_radius=5)
        pygame.draw.rect(s, S.STEEL, (10, 10, 20, 20), border_radius=5)
        pygame.draw.polygon(s, k, [(20, 11), (27, 20), (20, 29), (13, 20)])
        pygame.draw.polygon(s, S.ENERGY, [(20, 13), (25, 20), (20, 27), (15, 20)])
        pygame.draw.polygon(s, S.WHITE, [(20, 15), (22, 19), (20, 21), (18, 19)])
    elif kind == "drone":
        pygame.draw.rect(s, k, (8, 10, 24, 20), border_radius=4)
        pygame.draw.rect(s, S.STEEL_DARK, (9, 11, 22, 18), border_radius=4)
        pygame.draw.rect(s, (22, 22, 34), (12, 15, 16, 10), border_radius=2)
        for px in (15, 20, 25):
            pygame.draw.circle(s, S.GREEN, (px, 20), 2)
    elif kind == "barricade":
        pygame.draw.rect(s, k, (5, 7, 30, 26), border_radius=3)
        pygame.draw.rect(s, S.STEEL, (6, 8, 28, 24), border_radius=3)
        for i in range(4):
            pygame.draw.polygon(s, S.ENERGY, [(6 + i * 8, 32), (10 + i * 8, 32), (18 + i * 8, 8), (14 + i * 8, 8)])
        pygame.draw.rect(s, k, (6, 8, 28, 24), 1, border_radius=3)
    elif kind == "mines":
        pygame.draw.circle(s, k, c, 12)
        pygame.draw.circle(s, S.STEEL_DARK, c, 11)
        pygame.draw.rect(s, k, (18, 11, 18, 8))
        pygame.draw.rect(s, S.STEEL, (19, 12, 16, 6))
        pygame.draw.circle(s, S.RED, c, 4)
        pygame.draw.circle(s, S.ENERGY, c, 2)
    elif kind == "radar":
        pygame.draw.circle(s, k, c, 9)
        pygame.draw.circle(s, S.STEEL, c, 8)
        pygame.draw.arc(s, k, (8, 4, 24, 24), 3.6, 5.8, 5)
        pygame.draw.arc(s, S.GREEN, (8, 4, 24, 24), 3.6, 5.8, 3)
        pygame.draw.line(s, S.GREEN, c, (20, 9), 2)
        pygame.draw.circle(s, S.GREEN, c, 3)
    return s


def _core():
    s = pygame.Surface((56, 56), pygame.SRCALPHA)
    c = (28, 28)
    hexa = lambda r: [(c[0] + r * math.cos(a), c[1] + r * math.sin(a))
                      for a in [math.pi / 6 + i * math.pi / 3 for i in range(6)]]
    pygame.draw.polygon(s, (22, 22, 34), hexa(27))
    pygame.draw.polygon(s, S.STEEL_DARK, hexa(25))
    pygame.draw.polygon(s, S.STEEL, hexa(20))
    pygame.draw.circle(s, (22, 22, 34), c, 12)
    pygame.draw.circle(s, S.CYAN, c, 10)
    pygame.draw.circle(s, S.WHITE, c, 4)
    return s


def _item(kind):
    s = pygame.Surface((20, 20), pygame.SRCALPHA)
    k = (22, 22, 34)
    if kind == "energy_crystal":
        pts = [(10, 1), (17, 9), (10, 19), (3, 9)]
        pygame.draw.polygon(s, k, pts)
        pygame.draw.polygon(s, S.ENERGY, [(10, 3), (15, 9), (10, 17), (5, 9)])
        pygame.draw.polygon(s, S.WHITE, [(10, 4), (12, 8), (10, 10), (8, 8)])
    elif kind == "repair_kit":
        pygame.draw.rect(s, k, (2, 4, 16, 13), border_radius=2)
        pygame.draw.rect(s, S.WHITE, (3, 5, 14, 11), border_radius=2)
        pygame.draw.rect(s, S.GREEN, (8, 7, 4, 7))
        pygame.draw.rect(s, S.GREEN, (6, 9, 8, 3))
    elif kind == "overcharge":
        pygame.draw.rect(s, k, (5, 2, 10, 16), border_radius=2)
        pygame.draw.rect(s, S.ORANGE, (6, 3, 8, 14), border_radius=2)
        pygame.draw.polygon(s, S.ENERGY, [(11, 4), (7, 11), (10, 11), (9, 16), (13, 9), (10, 9)])
    elif kind == "shield_battery":
        pygame.draw.polygon(s, k, [(10, 1), (18, 4), (16, 14), (10, 19), (4, 14), (2, 4)])
        pygame.draw.polygon(s, S.CYAN, [(10, 3), (16, 5), (14, 13), (10, 17), (6, 13), (4, 5)])
        pygame.draw.rect(s, S.WHITE, (9, 6, 2, 8))
    return s


def build_placeholder(name):
    if name == "commander_0":
        return from_pixels(COMMANDER_TOP + COMMANDER_LEGS[0])
    if name == "commander_1":
        return from_pixels(COMMANDER_TOP + COMMANDER_LEGS[1])
    if name == "commander_down":
        return from_pixels(COMMANDER_DOWN)
    if name.startswith("skitter_"):
        return from_pixels(SKITTER[int(name[-1]) % 2])
    if name == "brute_0":
        return from_pixels(BRUTE)
    if name == "brute_1":
        return from_pixels(BRUTE_STEP)
    if name.startswith("glider_"):
        return from_pixels(GLIDER[int(name[-1]) % 2])
    if name.startswith("brood_sac"):
        return from_pixels(BROOD_SAC)
    if name.startswith("saboteur"):
        return from_pixels(SABOTEUR, 2)
    if name.startswith("hive_overseer"):
        return from_pixels(OVERSEER, 3)
    phase3 = {"mender": (MENDER, 2), "juggernaut": (JUGGERNAUT, 3), "cloaker": (CLOAKER, 2),
              "burrower": (BURROWER, 2), "spitter": (SPITTER, 2), "hive_egg": (HIVE_EGG, 2),
              "siege_titan": (SIEGE_TITAN, 3), "hive_queen": (HIVE_QUEEN, 3),
              "shield_drone": (SHIELD_DRONE, 2), "hunter": (HUNTER, 2), "mimic": (MIMIC, 2),
              "carrier": (CARRIER, 3), "burrow_wyrm": (BURROW_WYRM, 3)}
    for key, (rows, scale) in phase3.items():
        if name.startswith(key + "_"):
            return from_pixels(rows, scale)
    if name == "tower_base":
        return _tower_base()
    if name.startswith("tower_base_"):
        level = name[len("tower_base_"):]
        return tower_art.tower_base("b" if level == "b" else int(level[1]))
    if name.startswith("drone_t"):
        return tower_art.drone(int(name[-1]))
    if name.startswith("turret_"):
        kind = name[len("turret_"):]
        if kind[-3:-2] == "_" and kind[-2] in "tb":   # turret_<kind>_t1 / _b0 ...
            art = tower_art.turret(kind[:-3], kind[-2:])
            return art if art is not None else _turret(kind[:-3])
        return _turret(kind)
    if name == "core":
        return _core()
    if name in ("energy_crystal", "repair_kit", "overcharge", "shield_battery"):
        return _item(name)
    # Unknown name: an obvious magenta square so missing art is easy to spot.
    surf = pygame.Surface((24, 24), pygame.SRCALPHA)
    surf.fill(S.MAGENTA)
    return surf


class AssetManager:
    ANGLE_STEP = 5   # cache rotated sprites in 5-degree buckets

    def __init__(self):
        self._images = {}
        self._rotated = {}
        self._fonts = {}
        self._masks = {}

    def image(self, name):
        img = self._images.get(name)
        if img is None:
            path = os.path.join(S.SPRITE_DIR, name + ".png")
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
            else:
                img = build_placeholder(name)
            self._images[name] = img
        return img

    def get(self, name, angle=0.0, flip=False, tint=None):
        """A cached variant of a sprite.

        angle: counter-clockwise degrees (pygame convention), bucketed to 5 deg
        flip:  mirror horizontally (e.g. walking left)
        tint:  None, "white" (hit flash) or "cryo" (slowed)
        """
        bucket = int(round(angle / self.ANGLE_STEP)) * self.ANGLE_STEP % 360
        key = (name, bucket, flip, tint)
        img = self._rotated.get(key)
        if img is None:
            img = self.image(name)
            if flip:
                img = pygame.transform.flip(img, True, False)
            if tint == "white":
                img = img.copy()
                img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGB_MAX)
            elif tint == "cryo":
                img = img.copy()
                img.fill((150, 200, 255, 255), special_flags=pygame.BLEND_RGBA_MULT)
                img.fill((20, 40, 80, 0), special_flags=pygame.BLEND_RGB_ADD)
            if bucket:
                img = pygame.transform.rotate(img, bucket)
            self._rotated[key] = img
        return img

    def blit_centered(self, screen, name, pos, offset=(0, 0), **variant):
        img = self.get(name, **variant)
        rect = img.get_rect(center=(int(pos[0] + offset[0]), int(pos[1] + offset[1])))
        screen.blit(img, rect)
        return rect

    def mask(self, name, flip=False):
        """Cached pygame.mask for a sprite (pixel-perfect collision)."""
        key = (name, flip)
        m = self._masks.get(key)
        if m is None:
            m = pygame.mask.from_surface(self.get(name, flip=flip))
            self._masks[key] = m
        return m

    def circle_mask(self, radius):
        """Cached solid-circle mask, used to test a round shot against a sprite mask."""
        radius = max(1, int(radius))
        key = ("__circle__", radius)
        m = self._masks.get(key)
        if m is None:
            surf = pygame.Surface((radius * 2 + 1, radius * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 255, 255), (radius, radius), radius)
            m = pygame.mask.from_surface(surf)
            self._masks[key] = m
        return m

    def font(self, size, bold=False):
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
            self._fonts[key] = f
        return f

    def text(self, msg, size, color=S.WHITE, bold=False):
        return self.font(size, bold).render(str(msg), True, color)

    def preload(self):
        for name in SPRITE_NAMES:
            self.image(name)

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

# Pixel-map palette: one character = one pixel.
PALETTE = {
    "k": (22, 22, 34),          # outline
    "s": S.STEEL, "S": S.STEEL_LIGHT, "d": S.STEEL_DARK,
    "c": S.CYAN, "o": S.ORANGE, "y": S.ENERGY, "w": S.WHITE,
    "g": S.ALIEN_GREEN, "G": S.ALIEN_DARK,
    "m": S.MAGENTA, "M": S.MAGENTA_DARK,
    "r": S.RED, "b": S.CRYO, "e": (12, 12, 12),
}

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
    "tower_base", "turret_pulse", "turret_tesla", "turret_cryo",
    "turret_railgun", "turret_missile", "core",
    "energy_crystal", "repair_kit", "overcharge", "shield_battery",
]


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
    if name == "tower_base":
        return _tower_base()
    if name.startswith("turret_"):
        return _turret(name[len("turret_"):])
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

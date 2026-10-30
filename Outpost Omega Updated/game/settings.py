"""Global constants for Outpost Omega: Alien Siege.

Gameplay numbers that designers tune (tower stats, enemy stats, waves) live in
the JSON files under data/. This file only holds engine-level constants.
"""
import os

# --- Paths ---------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
LEVEL_DIR = os.path.join(DATA_DIR, "levels")
ASSET_DIR = os.path.join(ROOT_DIR, "assets")
SPRITE_DIR = os.path.join(ASSET_DIR, "sprites")
SOUND_DIR = os.path.join(ASSET_DIR, "sounds")
SAVE_PATH = os.path.join(ROOT_DIR, "save.json")

# --- Window / timing -----------------------------------------------------
TITLE = "Outpost Omega: Alien Siege"
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60                    # render cap
FIXED_DT = 1.0 / 60.0       # logic step (fixed-step update)
MAX_FRAME_TIME = 0.25       # clamp after a lag spike so we don't spiral

# --- Map grid ------------------------------------------------------------
TILE = 32
GRID_W, GRID_H = 40, 20
MAP_W, MAP_H = GRID_W * TILE, GRID_H * TILE      # 1280 x 640
HUD_H = SCREEN_H - MAP_H                         # 80 px HUD bar at the bottom
HUD_Y = MAP_H

# Tile characters used in levels/*.json
T_BUILD = "."     # buildable ground
T_PATH = "#"      # enemy path (walkable, not buildable)
T_SPAWN = "S"     # enemy spawn (part of the path)
T_CORE = "C"      # Omega Core
T_BLOCK = "X"     # rocks / crates: blocks building and the Commander
T_HAZARD = "~"    # acid pool (Sector 3)
T_ICE = "I"       # ice: buildable, Commander slides (Sector 2)
T_WALL = "W"      # hive wall (Sector 3, can appear mid-level)

# --- Gameplay constants ----------------------------------------------------
START_ENERGY = 200
SELL_REFUND = 0.70
BUILD_PHASE_TIME = 15.0
WAVE_HP_SCALE = 0.15        # enemy HP x (1 + 0.15 * wave)
STAR_THRESHOLDS = (0.8, 0.5)  # >80% core HP = 3 stars, >50% = 2, else 1

DIFFICULTIES = {
    "Easy":   {"hp": 0.80, "reward": 1.20, "speed": 0.90},
    "Normal": {"hp": 1.00, "reward": 1.00, "speed": 1.00},
    "Hard":   {"hp": 1.20, "reward": 0.85, "speed": 1.10},
}
DEFAULT_DIFFICULTY = "Normal"

# Commander
CMD_MAX_HP = 120
CMD_ACCEL = 1800.0
CMD_MAX_SPEED = 180.0
CMD_FRICTION = 10.0         # higher = stops faster
CMD_ICE_FRICTION = 1.5
CMD_SIZE = 20               # collision box (px)
CMD_RESPAWN = 5.0
BLASTER_RANGE = 160
BLASTER_RATE = 4.0          # shots per second
BLASTER_DAMAGE = 5
BLASTER_SPEED = 560
REPAIR_RANGE = 52
REPAIR_TIME = 2.0           # seconds to restore a tower to full
ORBITAL_COOLDOWN = 45.0
ORBITAL_DELAY = 1.0
ORBITAL_RADIUS = 96
ORBITAL_DAMAGE = 160

# Items
ITEM_RADIUS = 10
ITEM_CLICK_PAD = 14         # extra click area around a drop (px)
ITEM_WARN_TIME = 3.0        # drops blink this many seconds before the next wave
# Drops stay on the map until the next wave starts (see entities/item.py).

# Collision
HASH_CELL = 64

# --- Colors (Outpost Omega palette) ---------------------------------------
BLACK = (0, 0, 0)
WHITE = (240, 244, 255)
SPACE = (10, 12, 28)
HUD_BG = (16, 20, 38)
HUD_EDGE = (40, 52, 90)
PANEL = (26, 32, 58)
PANEL_HI = (44, 56, 96)
TEXT_DIM = (140, 150, 180)

SAND = (196, 160, 106)
SAND_DARK = (176, 140, 90)
SAND_LIGHT = (214, 182, 128)
PATH = (124, 94, 64)
PATH_DARK = (104, 78, 52)
ROCK = (92, 82, 76)
ROCK_DARK = (62, 56, 54)
ICE = (170, 214, 240)
ACID = (120, 220, 60)

STEEL = (140, 152, 168)
STEEL_DARK = (78, 88, 104)
STEEL_LIGHT = (196, 206, 220)
CYAN = (0, 229, 255)
ORANGE = (255, 140, 40)
ENERGY = (255, 214, 60)
ALIEN_GREEN = (110, 230, 60)
ALIEN_DARK = (40, 120, 30)
MAGENTA = (220, 50, 200)
MAGENTA_DARK = (120, 20, 110)
RED = (235, 60, 60)
GREEN = (80, 220, 110)
CRYO = (120, 200, 255)

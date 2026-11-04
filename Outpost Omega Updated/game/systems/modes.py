"""Phase 5 game modes, as variants of PlayScene (variant=...):

    boss_rush        campaign-style: every boss back to back, 800 starting Energy
    puzzle:<id>      fixed Energy, a fixed tower set, scripted waves (data/puzzles.json)
    last_stand       Endless with no towers: just Vance, her kit and Core upgrades
    weekly           Endless on the week's map with two odd rules (same for everyone that week)
    reverse          you send the aliens, an AI builds the towers (systems/reverse.py)
    sandbox          unlimited Energy, waves only when you start them, Y opens an alien spawn menu
Hardcore (Vance's death ends the game) and Ascension (Siege Run difficulty levels) are
flags on the GameManager set from the Modes screen.
"""
import datetime
import random

from .. import settings as S

BOSSES = ["hive_overseer", "siege_titan", "hive_queen", "burrow_wyrm", "mothership", "hive_mind",
          "fallen_commander", "acid_leviathan", "nest_heart", "architect"]

WEEKLY_RULES = {
    "tesla_only":  {"name": "Tesla Only",       "desc": "The only tower you can build is the Tesla Coil"},
    "double_speed": {"name": "Double Time",     "desc": "The game runs at 2x speed"},
    "no_repairs":  {"name": "No Repairs",       "desc": "Vance can't repair towers"},
    "pricey":      {"name": "Inflation",        "desc": "Towers cost 50% more"},
    "glass_core":  {"name": "Glass Core",       "desc": "The Core has 25 HP"},
    "elite_storm": {"name": "Elite Storm",      "desc": "Every alien has a 30% chance to be an elite"},
    "rich":        {"name": "Trust Fund",       "desc": "Start with 1000 Energy, kills pay nothing"},
}

ASCENSION = [
    "Aliens +10% HP",
    "Core max HP -15",
    "Supply Cache prices +20%",
    "Elites more common",
    "Aliens +10% speed",
    "One fewer draft choice",
]


def week_key():
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def weekly_setup():
    rng = random.Random(week_key())
    rules = rng.sample(sorted(WEEKLY_RULES), 2)
    if "tesla_only" in rules and "rich" in rules:
        rules = ["tesla_only", "glass_core"]
    sector = rng.choice(["sector1", "sector2", "sector3", "sector4", "sector6", "sector9", "sector10", "sector11"])
    return sector, rules, rng.randrange(1 << 30)


def ascension_effects(level):
    eff = []
    if level >= 2:
        eff.append({"type": "core_max", "add": -15})
    if level >= 3:
        eff.append({"type": "shop_discount", "mult": 1.2})
    if level >= 6:
        eff.append({"type": "draft_choices", "add": -1})
    return eff


def boss_rush_waves():
    waves = []
    escort = ["skitter", "brute", "glider", "spitter", "hunter", "phaser", "reflector", "jammer", "bomber", "blob"]
    for i, b in enumerate(BOSSES):
        waves.append({"groups": [{"enemy": escort[i], "count": 6 + i, "interval": 1.0, "delay": 0, "lane": 0}],
                      "boss": b})
    return waves


def prepare(play, variant, data, lvl):
    """Called by PlayScene before WaveSystem exists. Returns a wave list (or None to keep the default)."""
    play.variant = variant
    play.rules = []
    if not variant:
        return None
    kind, _, arg = variant.partition(":")
    s = play.session
    if kind == "boss_rush":
        s.energy = 800
        return boss_rush_waves()
    if kind == "puzzle":
        pz = data["puzzles"][arg]
        play.puzzle_id = arg
        s.energy = pz["energy"]
        s.core_hp = s.core_max = pz.get("core_hp", 1)
        return pz["waves"]
    if kind == "weekly":
        _sector, rules, _seed = weekly_setup()
        play.rules = rules
        if "glass_core" in rules:
            s.core_hp = s.core_max = 25
        if "rich" in rules:
            s.energy = 1000
    if kind == "sandbox":
        s.energy = 999999
    return None


def apply(play, variant):
    """Called at the end of PlayScene.__init__, once every system exists."""
    if not variant:
        return
    kind, _, arg = variant.partition(":")
    towers = play.towers
    if kind == "puzzle":
        allowed = set(play.game.data["puzzles"][arg]["towers"])
        for k, d in towers.data.items():
            d["enabled"] = k in allowed
        play.kill_mult = 0.0
        play.ui = type(play.ui)(play.assets, towers.data)
    elif kind == "last_stand":
        for d in towers.data.values():
            d["enabled"] = False
        kit = play.player.kit
        kit.grenades = {"frag": 5, "cryo": 3, "emp": 2}
        kit.data = dict(kit.data, mech=dict(kit.data["mech"], charge=30))
        play.session.energy += 300   # for Core upgrades
        play.ui = type(play.ui)(play.assets, towers.data)
    elif kind == "weekly":
        rules = play.rules
        if "tesla_only" in rules:
            for k, d in towers.data.items():
                d["enabled"] = k == "tesla"
        if "pricey" in rules:
            for d in towers.data.values():
                d["cost"] = int(d["cost"] * 1.5)
        if "double_speed" in rules:
            play.speed = 2
            play.SPEEDS = (2, 3)
        if "no_repairs" in rules:
            play.player.commander.repair_time = 1e9
        if "elite_storm" in rules:
            play.force_elite = 0.3
        if "rich" in rules:
            play.kill_mult = 0.0
        play.ui = type(play.ui)(play.assets, towers.data)
    elif kind == "reverse":
        from .reverse import Reverse
        play.reverse = Reverse(play, play.game.data["reverse"])
    elif kind == "sandbox":
        play.waves.build_time = 1e9
        play.waves.countdown = 1e9


def describe(variant):
    if not variant:
        return None
    kind, _, arg = variant.partition(":")
    if kind == "weekly":
        _s, rules, _seed = weekly_setup()
        return "WEEKLY  -  " + "  +  ".join(WEEKLY_RULES[r]["name"] for r in rules)
    return {"boss_rush": "BOSS RUSH  -  every boss, back to back", "last_stand": "LAST STAND  -  no towers",
            "sandbox": "SANDBOX  -  Y: spawn aliens, Space: start a wave",
            "reverse": "REVERSE  -  you are the hive: break the Core",
            "puzzle": f"PUZZLE  -  {arg}"}.get(kind)


# ---- Sandbox spawn menu ------------------------------------------------------------
def _sandbox_rects(play):
    import pygame
    kinds = sorted(play.game.data["enemies"])
    rects = []
    for i, k in enumerate(kinds):
        col, row = divmod(i, 18)
        rects.append((k, pygame.Rect(10 + col * 134, 40 + row * 30, 128, 26)))
    return rects


def sandbox_click(play, pos):
    for kind, rect in _sandbox_rects(play):
        if rect.collidepoint(pos):
            play.enemies.spawn(kind, max(1, play.waves.wave_number))
            play.audio.play("click")
            return True
    return False


def render_sandbox(screen, play, mouse):
    import pygame
    a = play.assets
    for kind, rect in _sandbox_rects(play):
        hover = rect.collidepoint(mouse)
        pygame.draw.rect(screen, S.PANEL_HI if hover else S.HUD_BG, rect, border_radius=4)
        pygame.draw.rect(screen, S.HUD_EDGE, rect, 1, border_radius=4)
        name = play.game.data["enemies"][kind].get("name", kind)
        t = a.text(name, 14, S.WHITE if hover else S.TEXT_DIM, True)
        screen.blit(t, t.get_rect(midleft=(rect.x + 6, rect.centery)))
    hint = a.text("SANDBOX: click an alien to spawn it.  Y hides this menu.", 16, S.ENERGY, True)
    screen.blit(hint, (10, 14))

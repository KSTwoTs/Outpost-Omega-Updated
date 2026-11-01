"""In-sector progression: Commander levels/perks and Omega Core upgrades.

CommanderProgress: every kill gives XP (the alien's score / 10). Each level
queues a choice of 3 perks from data/perks.json; the HUD shows the choice
and PlayScene applies the pick. In a Siege Run, level, XP and perks carry
over between sectors (stored on the RunState).

CoreUpgrades: three upgrade tracks bought with Energy by clicking the Core:
a defense turret on every Core, a shield that soaks Core damage each wave,
and regeneration after each wave.
"""
import math
import random

from .. import settings as S


class CommanderProgress:
    def __init__(self, perk_data, level=1, xp=0, perks=None, rng=None):
        self.perk_data = {k: v for k, v in perk_data.items() if not k.startswith("_")}
        self.level = level
        self.xp = xp
        self.perks = list(perks or [])
        self.choices = []          # queued level-ups: each a list of 3 perk ids
        self.rng = rng or random.Random()

    def xp_needed(self):
        return 30 + 25 * (self.level - 1)

    def add_xp(self, amount):
        """Returns how many levels were gained."""
        self.xp += amount
        gained = 0
        while self.xp >= self.xp_needed():
            self.xp -= self.xp_needed()
            self.level += 1
            gained += 1
            self.choices.append(self.rng.sample(list(self.perk_data), 3))
        return gained

    @property
    def current_choice(self):
        return self.choices[0] if self.choices else None

    def pick(self, index):
        perk = self.choices.pop(0)[index]
        self.perks.append(perk)
        return perk


def apply_perk(play, perk):
    """Make one perk take effect on the running PlayScene."""
    cmd = play.player.commander
    if perk == "sharpshooter":
        cmd.blaster_damage *= 1.3
    elif perk == "rapid_fire":
        cmd.blaster.duration /= 1.3
    elif perk == "long_barrel":
        cmd.blaster_range *= 1.25
    elif perk == "tough":
        cmd.health.max_hp += 30
        cmd.health.hp = cmd.health.max_hp
    elif perk == "sprinter":
        cmd.max_speed *= 1.15
    elif perk == "field_tech":
        cmd.repair_time /= 1.5
    elif perk == "uplink":
        play.player.orbital.duration *= 0.8
    elif perk == "salvager":
        play.kill_bonus += 2
    elif perk == "second_wind":
        cmd.respawn_time *= 0.6
    elif perk == "kinetic":
        play.player.orbital_damage *= 1.4
    elif perk == "wide_strike":
        play.player.orbital_radius *= 1.3
    elif perk == "supply_run":
        play.session.energy += 60
    elif perk == "core_medic":
        s = play.session
        s.core_hp = min(s.core_max, s.core_hp + 15)
    elif perk == "plating":
        cmd.damage_taken *= 0.75
    elif perk == "tuning":
        _scale_tower_stats(play, ("damage", "dps", "burn_dps"), 1.08)
    elif perk == "calibration":
        _scale_tower_stats(play, ("range",), 1.06)
    elif perk == "hollow_point":
        cmd.blaster_damage *= 1.15
        cmd.blaster_range *= 1.1
    elif perk == "coolant":
        cmd.blaster.duration /= 1.1
        play.player.orbital.duration *= 0.9


def _scale_tower_stats(play, stats, mult):
    """Perks that buff every tower patch this sector's copy of the tower data
    (built towers share it, so they update immediately)."""
    for d in play.towers.data.values():
        for tier in d["tiers"] + [br["stats"] for br in d.get("branches", [])]:
            for stat in stats:
                if stat in tier:
                    tier[stat] = round(tier[stat] * mult, 2)


class CoreUpgrades:
    COSTS = [120, 200, 300]
    KIND_COSTS = {"reactor": [100, 160, 240], "nova": [150, 240, 340], "plating": [90, 150, 220]}
    TURRET_DAMAGE = [0, 8, 14, 22]
    TURRET_RATE = 2.0
    TURRET_RANGE = 170
    SHIELD = [0, 10, 20, 35]      # Core damage soaked per wave
    REGEN = [0, 3, 6, 10]         # Core HP restored after each wave
    REACTOR = [0, 15, 30, 50]     # Energy after each wave
    NOVA = [0, 25, 50, 90]        # shockwave damage around the Core every NOVA_EVERY seconds
    NOVA_EVERY = 10.0
    NOVA_RANGE = 130
    PLATING = [0, 20, 40, 70]     # extra Core max HP (this sector)
    ORDER = ("turret", "shield", "regen", "reactor", "nova", "plating")
    NAMES = {"turret": "Gun", "shield": "Shield", "regen": "Regen",
             "reactor": "Reactor", "nova": "Nova", "plating": "Plating"}

    def __init__(self, play):
        self.play = play
        self.levels = {k: 0 for k in self.ORDER}
        self.nova_timer = self.NOVA_EVERY
        self.bonus_shield = 0       # free shield every wave (augments)
        self.shield_hp = 0.0
        self.cooldowns = [0.0 for _ in play.level.core_positions]
        self.angles = [0.0 for _ in play.level.core_positions]
        play.events.subscribe("wave_started", self.on_wave_started)
        play.events.subscribe("wave_cleared", self.on_wave_cleared)

    def cost(self, kind):
        lvl = self.levels[kind]
        costs = self.KIND_COSTS.get(kind, self.COSTS)
        return costs[lvl] if lvl < len(costs) else None

    def upgrade(self, kind):
        cost = self.cost(kind)
        s = self.play.session
        if cost is None:
            self.play.ui.toast("Already maxed", S.TEXT_DIM)
            return False
        if s.energy < cost:
            self.play.ui.toast("Not enough Energy", S.RED)
            self.play.audio.play("error")
            return False
        s.energy -= cost
        self.levels[kind] += 1
        if kind == "shield":
            self.shield_hp = max(self.shield_hp, self.SHIELD[self.levels["shield"]])
        if kind == "plating":
            lvl = self.levels["plating"]
            gain = self.PLATING[lvl] - self.PLATING[lvl - 1]
            s.core_max += gain
            s.core_hp += gain
        for x, y in self.play.level.core_positions:
            self.play.effects.ring(x, y, 40, S.CYAN, 0.5, width=4)
        self.play.audio.play("upgrade")
        return True

    def on_wave_started(self, **_):
        self.shield_hp = self.SHIELD[self.levels["shield"]] + self.bonus_shield

    def on_wave_cleared(self, **_):
        heal = self.REGEN[self.levels["regen"]]
        s = self.play.session
        energy = self.REACTOR[self.levels["reactor"]]
        if energy and not self.play.result:
            s.energy += energy
            self.play.ui.toast(f"Core reactor: +{energy} Energy", S.ENERGY)
        if heal and s.core_hp < s.core_max:
            s.core_hp = min(s.core_max, s.core_hp + heal)
            self.play.ui.toast(f"Core regenerated {heal} HP", S.GREEN)

    def absorb(self, damage):
        """Core shield takes the hit first. Returns the damage left over."""
        soaked = min(self.shield_hp, damage)
        self.shield_hp -= soaked
        return damage - soaked

    def update_nova(self, dt):
        lvl = self.levels["nova"]
        if not lvl:
            return
        self.nova_timer -= dt
        if self.nova_timer > 0:
            return
        play = self.play
        hit = False
        for x, y in play.level.core_positions:
            for e in play.collision.enemies_in_range(x, y, self.NOVA_RANGE, True):
                play.enemies.damage(e, self.NOVA[lvl])
                e.apply_stun(0.5)
                hit = True
            if hit:
                play.effects.ring(x, y, self.NOVA_RANGE, S.CYAN, 0.45, width=4)
        if hit:
            play.audio.play("shield")
            self.nova_timer = self.NOVA_EVERY
        else:
            self.nova_timer = 0.5   # wait for something to come close

    def on_update(self, dt):
        self.update_nova(dt)
        lvl = self.levels["turret"]
        if not lvl:
            return
        play = self.play
        for i, (x, y) in enumerate(play.level.core_positions):
            self.cooldowns[i] -= dt
            target = play.collision.nearest_enemy(x, y, self.TURRET_RANGE)
            if target is None:
                continue
            self.angles[i] = math.atan2(target.pos.y - y, target.pos.x - x)
            if self.cooldowns[i] <= 0:
                self.cooldowns[i] = 1.0 / self.TURRET_RATE
                play.projectiles.fire_at(x, y, target, 620, self.TURRET_DAMAGE[lvl], color=S.CYAN,
                                         hits_air=True, radius=3)

    def on_render(self, screen, offset):
        import pygame
        for i, (x, y) in enumerate(self.play.level.core_positions):
            x, y = x + offset[0], y + offset[1]
            if self.shield_hp > 0:
                pygame.draw.circle(screen, S.CYAN, (int(x), int(y)), 38, 2)
            if self.levels["turret"]:
                a = self.angles[i]
                pygame.draw.line(screen, (22, 22, 34), (x, y), (x + math.cos(a) * 26, y + math.sin(a) * 26), 6)
                pygame.draw.line(screen, S.STEEL_LIGHT, (x, y), (x + math.cos(a) * 25, y + math.sin(a) * 25), 3)

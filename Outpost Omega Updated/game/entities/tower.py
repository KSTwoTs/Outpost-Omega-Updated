"""Tower entity: stats per tier, targeting, HP, cooldown and status timers.

How a tower attacks depends on its "behavior" in towers.json
(projectile / aura / chain / pierce / missile); TowerSystem holds those
functions so all towers share one implementation per behavior.
"""
import math

import pygame

from .. import settings as S
from ..core import Cooldown, Health, State, StateMachine
from ..core.spatial_hash import dist_sq
from ..systems.tower_art import draw_bubble, draw_tar

TARGETING_MODES = ("first", "last", "strongest", "closest")
INT_STATS = {"chain", "burst", "drones", "targets", "max_mines", "beams", "income", "splits"}
VET_RANKS = (10, 30, 75)    # kills needed for veterancy ranks 1-3
VET_BONUS = 0.06            # +6% damage per rank


class TowerHealth(Health):
    """Tower HP plus an optional Shield Projector bubble that soaks damage first."""

    def __init__(self, max_hp):
        super().__init__(max_hp)
        self.shield = 0.0
        self.since_hit = 99.0     # seconds since the last hit (shields wait before regenerating)

    def damage(self, amount, ignore_armor=False):
        if self.is_dead or amount <= 0:
            return 0
        self.since_hit = 0.0
        if self.shield > 0:
            soaked = min(self.shield, amount)
            self.shield -= soaked
            amount -= soaked
            if amount <= 0:
                return 0
        return super().damage(amount, ignore_armor)


class Active(State):
    def update(self, tower, dt):
        if tower.disabled_timer > 0 or tower.health.is_dead:
            return "disabled"
        if tower.corrupted:   # Infector: shoots our own towers until fully repaired
            tower.system.run_corrupted(tower, dt)
        else:
            tower.system.run_behavior(tower, dt)
        return None


class Disabled(State):
    """EMP'd by a Saboteur, or broken (0 HP) until the Commander repairs it."""

    def update(self, tower, dt):
        if tower.disabled_timer <= 0 and not tower.health.is_dead:
            return "active"
        return None


class Tower:
    def __init__(self, kind, data, tx, ty, system):
        self.kind = kind
        self.data = data
        self.name = data["name"]
        self.behavior = data["behavior"]
        self.tx, self.ty = tx, ty
        self.x = tx * S.TILE + S.TILE / 2
        self.y = ty * S.TILE + S.TILE / 2
        self.system = system
        self.tier = 0
        self.branch = None               # tier-4 branch index (Siege Run only)
        self.range_buff = 0.0            # from nearby Radar Relays, refreshed every frame
        self.damage_buff = 0.0           # Targeting Uplink relays
        self.haste = 0.0                 # Overclock Station repair bays
        self.kills = 0                   # veterancy
        # Phase 5 tower systems (see data/tower_systems.json and TowerSystem.refresh_mods)
        self.mod_sources = {}            # name -> {"mods": {stat: [mult, add]}, "rate": x, ...}
        self.mods = {}                   # combined stat mods
        self.mods_version = 0
        self._stats_key = None
        self._stats_cache = None
        self.rate_bonus = 0.0            # chips / veteran trait
        self.power = 0.0                 # Generator (refreshed every frame)
        self.kill_energy = 0             # Salvage chip / Lucky trait
        self.synergies = []              # text lines for the HUD
        self.chips = []                  # socketed chip ids
        self.stance = None               # None, "focus" or "suppress"
        self.vet_name = None             # named veteran (rank 3)
        self.vet_trait = None
        self.fusion = None               # fusion id once fused
        self.wave_damage = 0.0           # post-wave report (reset when a wave starts)
        self.wave_kills = 0
        self.spent = data["cost"]
        self.health = TowerHealth(data.get("hp", 100))
        self.shield_max = 0.0            # from nearby Shield Projectors, refreshed every frame
        self.walkable = data.get("walkable", False)
        self.corrupted = False           # Infector   # Tar Pit: aliens and Vance walk over it
        self.can_target_air = data.get("can_target_air", True)
        self.targeting = "first"
        self.angle = 0.0                 # screen-space radians the head faces
        self.cooldown = Cooldown(self._interval(), ready=True)
        self.disabled_timer = 0.0
        self.overcharge_timer = 0.0
        self.muzzle_timer = 0.0
        self.pulse_t = 0.0               # visual timer for aura towers
        self.target = None
        self.fsm = StateMachine(self, {"active": Active(), "disabled": Disabled()}, "active")

    # ---- stats -------------------------------------------------------------
    @property
    def base_stats(self):
        if self.branch is not None:
            return self.data["branches"][self.branch]["stats"]
        return self.data["tiers"][self.tier]

    @property
    def stats(self):
        base = self.base_stats
        if not self.mods:
            return base
        key = (self.tier, self.branch, self.mods_version, id(self.data))
        if self._stats_key != key:
            st = dict(base)
            for k, (mult, add) in self.mods.items():
                v = st.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    nv = v * mult + add
                    st[k] = int(round(nv)) if isinstance(v, int) and k in INT_STATS else nv
            self._stats_cache, self._stats_key = st, key
        return self._stats_cache

    def refresh_mods(self):
        """Combine every mod source (synergies, chips, stance, veteran trait)."""
        mods, rate, kill_energy = {}, 0.0, 0
        for src in self.mod_sources.values():
            for k, (mult, add) in src.get("mods", {}).items():
                m = mods.setdefault(k, [1.0, 0.0])
                m[0] *= mult
                m[1] += add
            rate += src.get("rate", 0.0)
            kill_energy += src.get("kill_energy", 0)
        self.mods = mods
        self.rate_bonus = rate
        self.kill_energy = kill_energy
        self.mods_version += 1

    @property
    def range(self):
        return (self.stats.get("range", 0) * getattr(self.system, "range_mult", 1.0)
                * getattr(self.system, "env_range_mult", 1.0) * (1 + self.range_buff))

    @property
    def vet_rank(self):
        return sum(self.kills >= k for k in VET_RANKS)

    @property
    def vet_mult(self):
        return 1.0 + VET_BONUS * getattr(self.system, "vet_bonus_mult", 1.0) * self.vet_rank

    def record_kill(self):
        before = self.vet_rank
        self.kills += 1
        self.wave_kills += 1
        if getattr(self.system, "on_tower_kill", None):
            self.system.on_tower_kill(self)
        if self.kill_energy and getattr(self.system, "session", None) is not None:
            self.system.session.energy += self.kill_energy
        if self.vet_rank > before:
            if self.vet_rank == len(VET_RANKS):
                self.system.promote_veteran(self)
            fx = self.system.effects
            fx.floating_text(self.x, self.y - 22, f"VETERAN {self.vet_rank}", S.ENERGY, 18)
            fx.ring(self.x, self.y, 22, S.ENERGY, 0.4)

    @property
    def branch_name(self):
        return self.data["branches"][self.branch]["name"] if self.branch is not None else None

    @property
    def branch_available(self):
        sysm = self.system
        allowed = getattr(sysm, "allow_branches", False) or (
            getattr(sysm, "mastery_branches", False) and getattr(sysm, "mastery", {}).get(self.kind, 0) >= 3)
        return (allowed and self.data.get("branches")
                and self.tier == self.max_tier and self.branch is None)

    def choose_branch(self, index):
        cost = self.data["branches"][index]["cost"]
        self.branch = index
        self.spent += cost
        self.cooldown.duration = self._interval()
        return cost

    @property
    def max_tier(self):
        return len(self.data["tiers"]) - 1

    @property
    def can_upgrade(self):
        return self.tier < self.max_tier

    @property
    def upgrade_cost(self):
        if not self.can_upgrade:
            return None
        return self.data["tiers"][self.tier + 1]["upgrade_cost"]

    @property
    def sell_value(self):
        bonus = sum(self.mod_sources.get(f"chip{i}", {}).get("sell_bonus", 0) for i in range(3))
        return int(self.spent * (getattr(self.system, "sell_refund", S.SELL_REFUND) + bonus))

    @property
    def chip_slots(self):
        return 2 if (self.tier >= 2 or self.branch is not None or self.fusion) else 1

    @property
    def display_name(self):
        name = self.branch_name or self.name
        return f'"{self.vet_name}" {name}' if self.vet_name else name

    @property
    def fire_rate_mult(self):
        return ((2.0 if self.overcharge_timer > 0 else 1.0) * (1.0 + self.haste)
                * (1.0 + self.rate_bonus + self.power) * (0.5 if getattr(self, "vined", False) else 1.0))

    def _interval(self):
        rate = self.stats.get("fire_rate", 1.0)
        return 1.0 / rate if rate else 1.0

    def upgrade(self):
        cost = self.upgrade_cost
        self.tier += 1
        self.spent += cost
        self.cooldown.duration = self._interval()
        return cost

    def cycle_targeting(self):
        i = TARGETING_MODES.index(self.targeting)
        self.targeting = TARGETING_MODES[(i + 1) % len(TARGETING_MODES)]
        return self.targeting

    def disable(self, seconds):
        self.disabled_timer = max(self.disabled_timer, seconds)

    def overcharge(self, seconds):
        self.overcharge_timer = max(self.overcharge_timer, seconds)

    def in_range(self, x, y):
        return dist_sq(self.x, self.y, x, y) <= self.range * self.range

    def aim_at(self, x, y):
        self.angle = math.atan2(y - self.y, x - self.x)

    # ---- per frame ---------------------------------------------------------
    def update(self, dt):
        self.disabled_timer = max(0.0, self.disabled_timer - dt)
        self.overcharge_timer = max(0.0, self.overcharge_timer - dt)
        self.muzzle_timer = max(0.0, self.muzzle_timer - dt)
        self.health.since_hit += dt
        dead = self.health.is_dead
        if dead and not getattr(self, "_was_dead", False) and self.system.on_broken:
            self.system.on_broken(self)
        self._was_dead = dead
        if self.corrupted and self.health.ratio >= 0.999:
            self.corrupted = False
            self.system.effects.floating_text(self.x, self.y - 22, "CLEANSED", S.GREEN, 18)
        self.pulse_t += dt
        self.cooldown.update(dt, self.fire_rate_mult)
        self.fsm.update(dt)

    @property
    def look(self):
        """Art suffix for the current upgrade: '' (tier 1), '_t1', '_t2' or '_b0' / '_b1'."""
        if self.branch is not None:
            return f"_b{self.branch}"
        return f"_t{min(self.tier, 2)}" if self.tier > 0 else ""

    def render(self, screen, assets, offset):
        x, y = self.x + offset[0], self.y + offset[1]
        look = self.look
        if self.behavior == "tar":   # a pool on the path, no base plate
            draw_tar(screen, (x, y), self.range, min(self.tier, 2) if self.branch is None else 3,
                     getattr(self, "ignite_timer", 0) > 0 or self.stats.get("always_burning", False),
                     self.pulse_t)
        else:
            base = "tower_base_b" if self.fusion else "tower_base" + ("_b" if look.startswith("_b") else look)
            assets.blit_centered(screen, base, (x, y))
        if self.behavior in ("aura", "gravity", "income", "support", "repair", "shockwave", "shield", "chrono", "magnet",
                             "biolab", "overclock", "uplink", "generator", "brood"):
            angle = (self.pulse_t * 40) % 360   # slow spin
        else:
            angle = -math.degrees(self.angle)
        assets.blit_centered(screen, f"turret_{self.kind}{look}", (x, y), angle=angle)
        if self.behavior in ("ion", "lightning") and self.fsm.name == "active":   # charge meter
            if self.behavior == "ion":
                frac, col = self.cooldown.fraction, S.CYAN
            else:
                frac = getattr(self, "charge", 0.0) / max(1, self.stats["max_charge"])
                col = S.ENERGY
            rect = (x - 17, y - 17, 34, 34)
            pygame.draw.arc(screen, col if frac < 1 else S.WHITE, rect,
                            math.pi / 2, math.pi / 2 + math.tau * min(1.0, frac), 2)
        # Tier pips
        for i in range(self.tier + 1):
            pygame.draw.rect(screen, S.ENERGY, (x - 10 + i * 8, y + 11, 5, 3))
        if self.branch is not None:
            pygame.draw.rect(screen, S.MAGENTA, (x + 14, y + 11, 5, 3))
            pygame.draw.circle(screen, S.MAGENTA, (int(x), int(y)), 15, 1)
        if self.fusion:   # rainbow-ish ring for hybrids
            for i, col in enumerate((S.MAGENTA, S.CYAN, S.ENERGY)):
                a = self.pulse_t * 2 + i * 2.1
                pygame.draw.arc(screen, col, (x - 17, y - 17, 34, 34), a, a + 1.6, 2)
        for i, chip in enumerate(self.chips):   # socket pips
            col = tuple(self.system.systems["chips"][chip]["color"])
            pygame.draw.rect(screen, col, (x + 11, y - 3 + i * 5, 4, 4))
        if self.stance == "suppress":
            pygame.draw.circle(screen, S.CRYO, (int(x - 12), int(y + 12)), 3)
        elif self.stance == "focus":
            pygame.draw.circle(screen, S.RED, (int(x - 12), int(y + 12)), 3)
        if self.vet_name:
            pygame.draw.polygon(screen, S.ENERGY, [(x - 4, y - 21), (x, y - 25), (x + 4, y - 21), (x, y - 17)])
        for i in range(self.vet_rank):   # veterancy chevrons
            cx, cy = x - 13, y - 12 + i * 4
            pygame.draw.lines(screen, S.ENERGY, False, [(cx - 3, cy), (cx, cy + 3), (cx + 3, cy)], 2)
        if self.range_buff > 0 and self.behavior != "support":
            pygame.draw.circle(screen, S.GREEN, (int(x + 12), int(y - 12)), 2)
        if self.overcharge_timer > 0:
            pygame.draw.circle(screen, S.ORANGE, (int(x), int(y)), 17, 2)
        if self.corrupted:
            pygame.draw.circle(screen, (200, 110, 240), (int(x), int(y)), 16, 2)
            pygame.draw.circle(screen, (120, 40, 160), (int(x), int(y)), 4)
        if self.fsm.name == "disabled":
            pygame.draw.line(screen, S.RED, (x - 10, y - 10), (x + 10, y + 10), 3)
            pygame.draw.line(screen, S.RED, (x + 10, y - 10), (x - 10, y + 10), 3)
        if self.health.shield > 0 and self.shield_max > 0:
            draw_bubble(screen, (x, y), self.health.shield / self.shield_max, self.pulse_t)
        if self.health.ratio < 1:
            pygame.draw.rect(screen, (30, 0, 0), (x - 14, y - 19, 28, 3))
            pygame.draw.rect(screen, S.CYAN, (x - 14, y - 19, int(28 * self.health.ratio), 3))

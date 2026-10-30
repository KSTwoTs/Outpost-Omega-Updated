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

TARGETING_MODES = ("first", "last", "strongest", "closest")


class Active(State):
    def update(self, tower, dt):
        if tower.disabled_timer > 0 or tower.health.is_dead:
            return "disabled"
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
        self.spent = data["cost"]
        self.health = Health(data.get("hp", 100))
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
    def stats(self):
        return self.data["tiers"][self.tier]

    @property
    def range(self):
        return self.stats["range"]

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
        return int(self.spent * S.SELL_REFUND)

    @property
    def fire_rate_mult(self):
        return 2.0 if self.overcharge_timer > 0 else 1.0

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
        self.pulse_t += dt
        self.cooldown.update(dt, self.fire_rate_mult)
        self.fsm.update(dt)

    def render(self, screen, assets, offset):
        x, y = self.x + offset[0], self.y + offset[1]
        assets.blit_centered(screen, "tower_base", (x, y))
        if self.behavior == "aura":
            angle = (self.pulse_t * 40) % 360   # slow spin
        else:
            angle = -math.degrees(self.angle)
        assets.blit_centered(screen, f"turret_{self.kind}", (x, y), angle=angle)
        # Tier pips
        for i in range(self.tier + 1):
            pygame.draw.rect(screen, S.ENERGY, (x - 10 + i * 8, y + 11, 5, 3))
        if self.overcharge_timer > 0:
            pygame.draw.circle(screen, S.ORANGE, (int(x), int(y)), 17, 2)
        if self.fsm.name == "disabled":
            pygame.draw.line(screen, S.RED, (x - 10, y - 10), (x + 10, y + 10), 3)
            pygame.draw.line(screen, S.RED, (x + 10, y - 10), (x - 10, y + 10), 3)
        if self.health.ratio < 1:
            pygame.draw.rect(screen, (30, 0, 0), (x - 14, y - 19, 28, 3))
            pygame.draw.rect(screen, S.CYAN, (x - 14, y - 19, int(28 * self.health.ratio), 3))

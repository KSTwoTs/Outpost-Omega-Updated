"""PlayerSystem: Commander control and abilities (blaster, repair, Orbital Strike).

PlayerSystem is also the Commander's link to the rest of the world: the
Commander reads system.level / collision / projectiles / towers through it.
"""
from collections import deque

import pygame

from .. import settings as S
from ..core import Cooldown
from ..entities.commander import Commander


class PlayerSystem:
    def __init__(self, events, level, inp, collision, projectiles, enemies, towers,
                 effects, audio):
        self.events = events
        self.level = level
        self.input = inp
        self.collision = collision
        self.projectiles = projectiles
        self.enemies = enemies
        self.towers = towers
        self.effects = effects
        self.audio = audio
        self.commander = Commander(self, self.find_spawn())
        self.partner = None    # local co-op Player 2 (add_partner)
        self.kit = None        # CommanderKit, created by PlayScene
        self.items = None      # ItemManager (kit drops), set by PlayScene
        self.orbital = Cooldown(S.ORBITAL_COOLDOWN, ready=True)
        self.orbital_damage = S.ORBITAL_DAMAGE   # Siege Run augments can raise this
        self.orbital_radius = S.ORBITAL_RADIUS
        self.aiming_orbital = False
        self.strikes = []   # [x, y, time_left]
        # Uplink Dish (TowerSystem refreshes these every frame)
        self.uplink_damage_mult = 1.0
        self.uplink_radius_mult = 1.0
        self.spare_charges = 0         # Twin Strike: a second stored strike
        self.spare_progress = 0.0

    def find_spawn(self):
        """Nearest open tile to the Core (breadth-first search)."""
        start = self.level.core_tile
        seen = {start}
        queue = deque([start])
        while queue:
            tx, ty = queue.popleft()
            if not self.level.is_solid(tx, ty) and self.level.tile_at(tx, ty) not in (S.T_HAZARD,):
                return self.level.tile_center(tx, ty)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (tx + dx, ty + dy)
                if n not in seen and self.level.in_bounds(*n):
                    seen.add(n)
                    queue.append(n)
        return self.level.tile_center(*start)

    def add_partner(self):
        """Local co-op: a second Commander with Player 1's stats, spawning next to her."""
        c1 = self.commander
        tx, ty = self.level.world_to_tile(c1.spawn.x, c1.spawn.y)
        spot = c1.spawn
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (2, 0), (-2, 0)):
            if self.level.in_bounds(tx + dx, ty + dy) and not self.level.is_solid(tx + dx, ty + dy):
                spot = self.level.tile_center(tx + dx, ty + dy)
                break
        c2 = Commander(self, spot)
        c2.player_no = 2
        for attr in ("blaster_damage", "max_speed", "repair_time", "blaster_range", "damage_taken", "respawn_time"):
            setattr(c2, attr, getattr(c1, attr))
        c2.health.reset(c1.health.max_hp)
        c2.skin = "skin_p2"
        self.partner = c2
        return c2

    @property
    def commanders(self):
        return [self.commander] + ([self.partner] if self.partner is not None else [])

    # ---- Orbital Strike -----------------------------------------------------
    def begin_orbital(self):
        if self.commander.jammed > 0:
            self.events.publish("toast", text="Orbital link jammed!", color=S.ORANGE)
            self.audio.play("error")
            return False
        if not self.orbital.ready and self.spare_charges <= 0:
            self.events.publish("toast", text=f"Orbital Strike in {self.orbital.remaining:.0f}s",
                                color=S.TEXT_DIM)
            self.audio.play("error")
            return False
        self.aiming_orbital = not self.aiming_orbital
        if self.aiming_orbital:
            self.towers.cancel_build()
        return True

    def confirm_orbital(self, pos):
        if not self.aiming_orbital:
            return False
        self.aiming_orbital = False
        if self.spare_charges > 0:   # Twin Strike: spend the stored charge, keep the main one
            self.spare_charges -= 1
        else:
            self.orbital.trigger()
        self.strikes.append([pos[0], pos[1], S.ORBITAL_DELAY])
        self.events.publish("toast", text="Orbital Strike inbound!", color=S.ORANGE)
        return True

    def _detonate(self, x, y):
        radius = self.orbital_radius * self.uplink_radius_mult
        self.enemies.splash(x, y, radius, self.orbital_damage * self.uplink_damage_mult,
                            include_air=True, knockback=24)
        for _ in range(3):
            self.effects.explosion(x, y, S.ORANGE, count=30)
        self.effects.ring(x, y, radius, S.WHITE, 0.5, width=4)
        self.effects.shake(0.7)
        self.effects.flash(S.WHITE, 0.15)
        self.audio.play("explode")

    # ---- loop -----------------------------------------------------------------
    def drop_item(self, kind, x, y):
        if self.items is not None:
            return self.items.drop(kind, x, y)

    def on_update(self, dt):
        self.orbital.update(dt)
        if self.commander.disabled:      # Reverse mode
            return
        if self.kit is not None:
            self.kit.update(dt)
        self.commander.update(dt, self.input.move_vector(1), self.input.repair_held(1))
        if self.partner is not None:
            self.partner.update(dt, self.input.move_vector(2), self.input.repair_held(2))
        for s in self.strikes:
            s[2] -= dt
            if s[2] <= 0:
                self._detonate(s[0], s[1])
        self.strikes = [s for s in self.strikes if s[2] > 0]

    def on_render(self, screen, assets, offset):
        if self.commander.disabled:
            return
        if self.kit is not None:
            self.kit.render(screen, assets, offset)
        self.commander.render(screen, assets, offset)
        if self.partner is not None:
            self.partner.render(screen, assets, offset)
        for x, y, t in self.strikes:
            # Shrinking targeting circle while the strike charges.
            frac = t / S.ORBITAL_DELAY
            r = int(self.orbital_radius * (0.3 + 0.7 * frac))
            pygame.draw.circle(screen, S.RED, (int(x + offset[0]), int(y + offset[1])), r, 2)
            pygame.draw.line(screen, S.RED, (x - 8, y), (x + 8, y), 2)
            pygame.draw.line(screen, S.RED, (x, y - 8), (x, y + 8), 2)

    def render_aim(self, screen, mouse):
        if not self.aiming_orbital or mouse[1] >= S.MAP_H:
            return
        size = self.orbital_radius * 2 + 4
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(surf, (*S.RED, 50), (c, c), self.orbital_radius)
        pygame.draw.circle(surf, (*S.RED, 200), (c, c), self.orbital_radius, 2)
        screen.blit(surf, (mouse[0] - c, mouse[1] - c))

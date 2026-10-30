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
        self.orbital = Cooldown(S.ORBITAL_COOLDOWN, ready=True)
        self.aiming_orbital = False
        self.strikes = []   # [x, y, time_left]

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

    # ---- Orbital Strike -----------------------------------------------------
    def begin_orbital(self):
        if not self.orbital.ready:
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
        self.orbital.trigger()
        self.strikes.append([pos[0], pos[1], S.ORBITAL_DELAY])
        self.events.publish("toast", text="Orbital Strike inbound!", color=S.ORANGE)
        return True

    def _detonate(self, x, y):
        self.enemies.splash(x, y, S.ORBITAL_RADIUS, S.ORBITAL_DAMAGE, include_air=True, knockback=24)
        for _ in range(3):
            self.effects.explosion(x, y, S.ORANGE, count=30)
        self.effects.ring(x, y, S.ORBITAL_RADIUS, S.WHITE, 0.5, width=4)
        self.effects.shake(0.7)
        self.effects.flash(S.WHITE, 0.15)
        self.audio.play("explode")

    # ---- loop -----------------------------------------------------------------
    def on_update(self, dt):
        self.orbital.update(dt)
        self.commander.update(dt, self.input.move_vector(), self.input.repair_held())
        for s in self.strikes:
            s[2] -= dt
            if s[2] <= 0:
                self._detonate(s[0], s[1])
        self.strikes = [s for s in self.strikes if s[2] > 0]

    def on_render(self, screen, assets, offset):
        self.commander.render(screen, assets, offset)
        for x, y, t in self.strikes:
            # Shrinking targeting circle while the strike charges.
            frac = t / S.ORBITAL_DELAY
            r = int(S.ORBITAL_RADIUS * (0.3 + 0.7 * frac))
            pygame.draw.circle(screen, S.RED, (int(x + offset[0]), int(y + offset[1])), r, 2)
            pygame.draw.line(screen, S.RED, (x - 8, y), (x + 8, y), 2)
            pygame.draw.line(screen, S.RED, (x, y - 8), (x, y + 8), 2)

    def render_aim(self, screen, mouse):
        if not self.aiming_orbital or mouse[1] >= S.MAP_H:
            return
        size = S.ORBITAL_RADIUS * 2 + 4
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(surf, (*S.RED, 50), (c, c), S.ORBITAL_RADIUS)
        pygame.draw.circle(surf, (*S.RED, 200), (c, c), S.ORBITAL_RADIUS, 2)
        screen.blit(surf, (mouse[0] - c, mouse[1] - c))

"""Projectile: a pooled bullet / missile. ProjectileSystem owns the pool."""
import math

import pygame


class Projectile:
    def __init__(self):
        self.active = False
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.speed = 0.0
        self.damage = 0
        self.radius = 3
        self.life = 0.0
        self.color = (255, 255, 255)
        self.hits_air = True
        self.ignore_armor = False
        self.splash = 0           # > 0 = area damage on impact
        self.homing_target = None  # enemy for missiles
        self.turn_rate = 0.0       # radians per second
        self.trail = []

    def spawn(self, x, y, dx, dy, speed, damage, color, radius=3, life=1.5,
              hits_air=True, ignore_armor=False, splash=0, homing_target=None,
              turn_rate=0.0):
        length = math.hypot(dx, dy) or 1.0
        self.x, self.y = x, y
        self.vx, self.vy = dx / length * speed, dy / length * speed
        self.speed = speed
        self.damage = damage
        self.color = color
        self.radius = radius
        self.life = life
        self.hits_air = hits_air
        self.ignore_armor = ignore_armor
        self.splash = splash
        self.homing_target = homing_target
        self.turn_rate = turn_rate
        self.trail = []
        return self

    def steer(self, dt):
        """Homing with a turn-rate limit (missiles)."""
        t = self.homing_target
        if t is None or not t.targetable:
            return
        want = math.atan2(t.pos.y - self.y, t.pos.x - self.x)
        have = math.atan2(self.vy, self.vx)
        diff = (want - have + math.pi) % (2 * math.pi) - math.pi
        max_turn = self.turn_rate * dt
        have += max(-max_turn, min(max_turn, diff))
        self.vx, self.vy = math.cos(have) * self.speed, math.sin(have) * self.speed

    def update(self, dt):
        if self.turn_rate:
            self.steer(dt)
        self.trail.append((self.x, self.y))
        if len(self.trail) > 4:
            self.trail.pop(0)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.active = False

    def render(self, screen, offset):
        ox, oy = offset
        if len(self.trail) >= 2:
            pts = [(int(px + ox), int(py + oy)) for px, py in self.trail] + \
                  [(int(self.x + ox), int(self.y + oy))]
            pygame.draw.lines(screen, self.color, False, pts, 2)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x + ox), int(self.y + oy)), self.radius)
        pygame.draw.circle(screen, self.color, (int(self.x + ox), int(self.y + oy)), self.radius, 1)

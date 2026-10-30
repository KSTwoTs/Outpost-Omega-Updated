"""ProjectileSystem: pooled bullets/missiles, lead targeting and hit tests."""
import math

from .. import settings as S
from ..core import ObjectPool
from ..entities.projectile import Projectile


def intercept_point(sx, sy, target_pos, target_vel, speed):
    """Lead targeting: where to aim so a shot at `speed` meets the target.

    Solve |P + V t - S| = speed * t for the smallest positive t:
        (V.V - s^2) t^2 + 2 (D.V) t + D.D = 0,   D = P - S
    Falls back to the current position if there is no solution.
    """
    px, py = target_pos
    vx, vy = target_vel
    dx, dy = px - sx, py - sy
    a = vx * vx + vy * vy - speed * speed
    b = 2 * (dx * vx + dy * vy)
    c = dx * dx + dy * dy
    t = None
    if abs(a) < 1e-6:
        if abs(b) > 1e-6:
            t = -c / b
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            root = math.sqrt(disc)
            candidates = [x for x in ((-b - root) / (2 * a), (-b + root) / (2 * a)) if x > 0]
            if candidates:
                t = min(candidates)
    if t is None or t <= 0:
        return (px, py), 0.0
    return (px + vx * t, py + vy * t), t


class ProjectileSystem:
    def __init__(self, events, collision, enemy_system, effects, audio):
        self.events = events
        self.collision = collision
        self.enemies = enemy_system
        self.effects = effects
        self.audio = audio
        self.pool = ObjectPool(Projectile, prealloc=128, max_size=600)

    def fire_at(self, x, y, target, speed, damage, color, hits_air=True, radius=3,
                lead=True, **kwargs):
        """Fire at an enemy, aiming ahead of it. Returns the aim point."""
        aim = (target.pos.x, target.pos.y)
        if lead:
            aim, t = intercept_point(x, y, aim, (target.vel.x, target.vel.y), speed)
            # Path enemies turn corners, so refine using their real future spot.
            if t > 0:
                aim = target.future_position(t)
        p = self.pool.acquire()
        p.spawn(x, y, aim[0] - x, aim[1] - y, speed, damage, color, radius=radius,
                hits_air=hits_air, **kwargs)
        return aim

    def on_update(self, dt):
        for p in self.pool.active:
            if not p.active:
                continue
            p.update(dt)
            if not (-40 < p.x < S.MAP_W + 40 and -40 < p.y < S.MAP_H + 40):
                p.active = False
                continue
            hits = self.collision.enemies_touching(p.x, p.y, p.radius, include_air=p.hits_air)
            hits = [e for e in hits if e.targetable]
            if hits:
                self.on_hit(p, hits[0])
        self.pool.sweep()

    def on_hit(self, p, enemy):
        p.active = False
        if p.splash > 0:
            self.enemies.splash(p.x, p.y, p.splash, p.damage, include_air=True)
            self.effects.explosion(p.x, p.y, S.ORANGE, count=18)
            self.audio.play("explode")
        else:
            self.enemies.damage(enemy, p.damage, ignore_armor=p.ignore_armor)
            self.effects.sparks(p.x, p.y, p.color)

    def on_render(self, screen, offset):
        for p in self.pool.active:
            p.render(screen, offset)

    def clear(self):
        self.pool.clear()

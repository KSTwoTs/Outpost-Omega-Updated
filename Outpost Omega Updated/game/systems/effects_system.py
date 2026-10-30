"""EffectsSystem: pooled particles, rings, floating numbers, lightning,
screen shake and full-screen flashes. Purely visual, no gameplay state."""
import math
import random

import pygame

from .. import settings as S
from ..core import ObjectPool


class Particle:
    __slots__ = ("active", "x", "y", "vx", "vy", "life", "max_life", "color", "size", "drag", "gravity")

    def __init__(self):
        self.active = False

    def spawn(self, x, y, vx, vy, life, color, size, drag=3.0, gravity=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.drag, self.gravity = color, size, drag, gravity


class EffectsSystem:
    def __init__(self, assets):
        self.assets = assets
        self.particles = ObjectPool(Particle, prealloc=400, max_size=1500)
        self.texts = []       # [x, y, surface, life, max_life]
        self.rings = []       # [x, y, radius, color, life, max_life, width]
        self.bolts = []       # [points, life, color]
        self.beams = []       # [x1, y1, x2, y2, color, life, max_life]
        self.trauma = 0.0     # screen shake amount 0..1
        self.flash_color = None
        self.flash_time = 0.0
        self.flash_max = 0.0
        self.enabled_numbers = True

    # ---- emitters ---------------------------------------------------------------
    def burst(self, x, y, color, count, speed, life, size, drag=3.0, gravity=0.0):
        for _ in range(count):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.3, 1.0) * speed
            p = self.particles.acquire()
            p.spawn(x, y, math.cos(a) * s, math.sin(a) * s,
                    random.uniform(0.5, 1.0) * life, color, size, drag, gravity)

    def explosion(self, x, y, color=S.ORANGE, count=24):
        self.burst(x, y, color, count, 220, 0.5, 4)
        self.burst(x, y, S.ENERGY, count // 2, 120, 0.3, 3)
        self.ring(x, y, 28, color, 0.25)

    def sparks(self, x, y, color=S.ORANGE):
        self.burst(x, y, color, 5, 160, 0.18, 2, drag=6)

    def goo(self, x, y):
        """Alien death splat."""
        self.burst(x, y, S.ALIEN_GREEN, 14, 140, 0.45, 3, drag=5)
        self.burst(x, y, S.MAGENTA, 6, 90, 0.35, 3, drag=5)

    def muzzle(self, x, y, angle):
        for _ in range(3):
            a = angle + random.uniform(-0.3, 0.3)
            p = self.particles.acquire()
            p.spawn(x, y, math.cos(a) * 200, math.sin(a) * 200, 0.08, S.ENERGY, 2, 8)

    def ring(self, x, y, radius, color, life, width=3):
        self.rings.append([x, y, radius, color, life, life, width])

    def number(self, x, y, value, color=S.WHITE):
        if not self.enabled_numbers:
            return
        txt = str(int(round(value))) if isinstance(value, (int, float)) else str(value)
        surf = self.assets.text(txt, 18, color, bold=True)
        self.texts.append([x + random.uniform(-6, 6), y, surf, 0.6, 0.6])

    def floating_text(self, x, y, text, color, size=22):
        surf = self.assets.text(text, size, color, bold=True)
        self.texts.append([x, y, surf, 1.0, 1.0])

    def lightning(self, points, color=S.CYAN, life=0.12):
        """Jittered polyline between points (for the Tesla Coil)."""
        jittered = []
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            for i in range(6):
                t = i / 6
                jittered.append((ax + (bx - ax) * t + random.uniform(-5, 5),
                                 ay + (by - ay) * t + random.uniform(-5, 5)))
        jittered.append(points[-1])
        self.bolts.append([jittered, life, color])

    def beam(self, x1, y1, x2, y2, color=S.CYAN, life=0.15):
        """Straight railgun beam that fades out."""
        self.beams.append([x1, y1, x2, y2, color, life, life])

    def shake(self, amount):
        self.trauma = min(1.0, self.trauma + amount)

    def flash(self, color, duration=0.2):
        self.flash_color, self.flash_time, self.flash_max = color, duration, duration

    @property
    def offset(self):
        if self.trauma <= 0:
            return (0, 0)
        mag = 10 * self.trauma * self.trauma
        return (random.uniform(-mag, mag), random.uniform(-mag, mag))

    # ---- loop ---------------------------------------------------------------------
    def on_update(self, dt):
        self.trauma = max(0.0, self.trauma - dt * 1.8)
        self.flash_time = max(0.0, self.flash_time - dt)
        for p in self.particles.active:
            p.life -= dt
            if p.life <= 0:
                p.active = False
                continue
            k = math.exp(-p.drag * dt)
            p.vx *= k
            p.vy = p.vy * k + p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.particles.sweep()
        for t in self.texts:
            t[1] -= 30 * dt
            t[3] -= dt
        self.texts = [t for t in self.texts if t[3] > 0]
        for r in self.rings:
            r[4] -= dt
        self.rings = [r for r in self.rings if r[4] > 0]
        for b in self.bolts:
            b[1] -= dt
        self.bolts = [b for b in self.bolts if b[1] > 0]
        for b in self.beams:
            b[5] -= dt
        self.beams = [b for b in self.beams if b[5] > 0]

    def on_render(self, screen, offset):
        ox, oy = offset
        for r in self.rings:
            x, y, radius, color, life, max_life, width = r
            grow = 1 - life / max_life
            rad = int(radius * (0.4 + 0.6 * grow))
            if rad > width:
                pygame.draw.circle(screen, color, (int(x + ox), int(y + oy)), rad, width)
        for p in self.particles.active:
            size = max(1, int(p.size * (p.life / p.max_life) + 0.5))
            screen.fill(p.color, (int(p.x + ox), int(p.y + oy), size, size))
        for pts, life, color in self.bolts:
            shifted = [(x + ox, y + oy) for x, y in pts]
            pygame.draw.lines(screen, S.WHITE, False, shifted, 3)
            pygame.draw.lines(screen, color, False, shifted, 1)
        for x1, y1, x2, y2, color, life, max_life in self.beams:
            w = max(1, int(6 * life / max_life))
            pygame.draw.line(screen, color, (x1 + ox, y1 + oy), (x2 + ox, y2 + oy), w + 2)
            pygame.draw.line(screen, S.WHITE, (x1 + ox, y1 + oy), (x2 + ox, y2 + oy), max(1, w // 2))
        for x, y, surf, life, max_life in self.texts:
            surf.set_alpha(int(255 * min(1.0, life / max_life * 2)))
            screen.blit(surf, surf.get_rect(center=(int(x + ox), int(y + oy))))

    def render_flash(self, screen):
        if self.flash_time > 0 and self.flash_color:
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            alpha = int(120 * self.flash_time / self.flash_max)
            overlay.fill((*self.flash_color, alpha))
            screen.blit(overlay, (0, 0))

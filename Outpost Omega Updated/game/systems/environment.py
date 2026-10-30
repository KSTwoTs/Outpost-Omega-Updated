"""Environment: volcanic vents (Sector 4) and weather (Endless / Siege Run).

Vents come from the level file: {"tile": [x, y], "interval": 14, "offset": 0}.
Each one glows for WARN seconds, then erupts: towers within RADIUS are
disabled and damaged, and Vance gets burned if he's standing there.
Vents only tick during a wave, so the build phase is always safe.

Weather is one of WEATHER below. PlayScene rolls it for Endless and Siege
Run sectors (or a level can force one with "weather": "sandstorm").
"""
import math
import random

import pygame

from .. import settings as S

WEATHER = {
    "sandstorm": {"name": "Sandstorm", "desc": "Towers have 20% less range", "color": (214, 182, 128)},
    "blizzard": {"name": "Blizzard", "desc": "Aliens 15% slower, the ground is icy", "color": (235, 245, 255)},
    "acid_rain": {"name": "Acid Rain", "desc": "Towers slowly corrode during waves", "color": S.ACID},
}


class VentSystem:
    WARN = 2.0
    RADIUS = 60
    DISABLE = 4.0
    TOWER_DAMAGE = 20
    COMMANDER_DAMAGE = 25

    def __init__(self, level, towers, player, effects, audio, events):
        self.towers, self.player, self.effects, self.audio, self.events = towers, player, effects, audio, events
        self.vents = []
        for v in level.data.get("vents", []):
            x, y = level.tile_center(*v["tile"])
            interval = v.get("interval", 14)
            self.vents.append({"x": x, "y": y, "interval": interval,
                               "timer": interval - v.get("offset", 0) % interval})
        self.t = 0.0
        self.announced = False

    def on_update(self, dt, wave_active):
        self.t += dt
        if not wave_active:
            return
        for v in self.vents:
            v["timer"] -= dt
            if v["timer"] <= 0:
                v["timer"] += v["interval"]
                self.erupt(v)

    def erupt(self, v):
        x, y, r = v["x"], v["y"], self.RADIUS
        for t in self.towers.towers:
            if (t.x - x) ** 2 + (t.y - y) ** 2 <= r * r:
                t.disable(self.DISABLE)
                t.health.damage(self.TOWER_DAMAGE, ignore_armor=True)
        c = self.player.commander
        if c.alive and c.pos.distance_squared_to((x, y)) <= r * r:
            c.take_damage(self.COMMANDER_DAMAGE)
        self.effects.burst(x, y, S.ORANGE, 30, 220, 0.7, 4, gravity=300)
        self.effects.burst(x, y, S.RED, 16, 140, 0.6, 3)
        self.effects.ring(x, y, r, S.ORANGE, 0.45, width=4)
        self.effects.shake(0.2)
        self.audio.play("explode")
        if not self.announced:
            self.announced = True
            self.events.publish("toast", text="Vent eruption! Towers nearby are knocked offline", color=S.ORANGE)

    def on_render(self, screen, offset):
        for v in self.vents:
            x, y = int(v["x"] + offset[0]), int(v["y"] + offset[1])
            warn = v["timer"] <= self.WARN
            glow = 0.5 + 0.5 * math.sin(self.t * (14 if warn else 3))
            pygame.draw.circle(screen, (60, 24, 16), (x, y), 13)
            pygame.draw.circle(screen, S.ORANGE if warn else (150, 60, 30), (x, y), int(6 + 4 * glow))
            if warn:
                surf = pygame.Surface((self.RADIUS * 2 + 4,) * 2, pygame.SRCALPHA)
                c = self.RADIUS + 2
                pygame.draw.circle(surf, (*S.ORANGE, int(30 + 40 * glow)), (c, c), self.RADIUS)
                pygame.draw.circle(surf, (*S.RED, 180), (c, c), self.RADIUS, 2)
                screen.blit(surf, (x - c, y - c))


class WeatherSystem:
    """Applies one weather effect for the whole sector and draws its particles."""
    ACID_DPS = 0.6

    def __init__(self, kind, towers, enemies, level):
        self.kind = kind
        self.info = WEATHER[kind]
        self.towers, self.enemies, self.level = towers, enemies, level
        rng = random.Random(7)
        count = {"sandstorm": 140, "blizzard": 160, "acid_rain": 130}[kind]
        self.parts = [[rng.uniform(0, S.MAP_W), rng.uniform(0, S.MAP_H), rng.uniform(0.6, 1.4)]
                      for _ in range(count)]
        if kind == "sandstorm":
            towers.env_range_mult = 0.8
        elif kind == "blizzard":
            enemies.env_speed_mult = 0.85
            level.weather_ice = True

    def on_update(self, dt, wave_active):
        if self.kind == "acid_rain" and wave_active:
            for t in self.towers.towers:
                t.health.damage(self.ACID_DPS * dt, ignore_armor=True)
        for p in self.parts:
            if self.kind == "sandstorm":
                p[0] += 420 * p[2] * dt
                p[1] += 30 * math.sin(p[0] * 0.01) * dt
            elif self.kind == "blizzard":
                p[0] += 60 * p[2] * dt
                p[1] += 110 * p[2] * dt
            else:
                p[0] -= 40 * dt
                p[1] += 520 * p[2] * dt
            p[0] %= S.MAP_W
            p[1] %= S.MAP_H

    def on_render(self, screen, offset):
        color = self.info["color"]
        tint = pygame.Surface((S.MAP_W, S.MAP_H), pygame.SRCALPHA)
        tint.fill((*color, 26))
        screen.blit(tint, offset)
        for x, y, k in self.parts:
            x, y = x + offset[0], y + offset[1]
            if self.kind == "sandstorm":
                pygame.draw.line(screen, color, (x, y), (x - 14 * k, y), 2)
            elif self.kind == "blizzard":
                pygame.draw.circle(screen, color, (int(x), int(y)), 2 if k > 1 else 1)
            else:
                pygame.draw.line(screen, color, (x, y), (x + 3, y - 12 * k), 1)

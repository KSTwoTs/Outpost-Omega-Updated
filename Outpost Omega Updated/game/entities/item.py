"""Items dropped by aliens, plus the weighted loot table and ItemManager.

Items bob and glow and stay on the map until the next wave starts (they
blink during the last 3 s of the build countdown as a warning). Picked up
when the Commander walks over one (circle overlap) or when the player
clicks it (with a generous click area). The pickup publishes
"item_collected"; PlayScene applies the effect, so this file doesn't need
to know about Energy or the Core.
"""
import math
import random

import pygame

from .. import settings as S
from ..core.spatial_hash import circles_overlap

ITEM_COLORS = {
    "energy_crystal": S.ENERGY,
    "repair_kit": S.GREEN,
    "overcharge": S.ORANGE,
    "shield_battery": S.CYAN,
}


class LootTable:
    """Weighted random choice: weights 60/15/15/10 -> 60% crystal, etc."""

    def __init__(self, data, rng=None):
        self.drop_chance = data.get("drop_chance", 0.2)
        self.items = data["items"]
        self.kinds = list(self.items.keys())
        self.weights = [self.items[k]["weight"] for k in self.kinds]
        self.rng = rng or random.Random()

    def roll(self):
        if self.rng.random() > self.drop_chance:
            return None
        return self.rng.choices(self.kinds, weights=self.weights, k=1)[0]


class Item(pygame.sprite.Sprite):
    def __init__(self, kind, info, x, y):
        super().__init__()
        self.kind = kind
        self.info = info
        self.x, self.y = x, y
        self.age = 0.0
        self.remove = False
        self.expiring = False      # True near the end of the build phase
        self.phase = random.random() * math.tau

    def update(self, dt):
        self.age += dt

    def render(self, screen, assets, offset):
        if self.expiring and int(self.age * 8) % 2 == 0:
            return  # blink: about to vanish when the next wave starts
        bob = math.sin(self.age * 4 + self.phase) * 3
        x, y = self.x + offset[0], self.y + offset[1] + bob
        glow = 10 + 3 * math.sin(self.age * 6)
        surf = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*ITEM_COLORS.get(self.kind, S.WHITE), 70), (20, 20), int(glow))
        screen.blit(surf, (x - 20, y - 20))
        assets.blit_centered(screen, self.kind, (x, y))


class ItemManager:
    def __init__(self, events, data, assets):
        self.events = events
        self.data = data
        self.assets = assets
        self.loot = LootTable(data)
        self.items = []
        events.subscribe("enemy_killed", self.on_enemy_killed)
        events.subscribe("wave_started", self.on_wave_started)

    def on_enemy_killed(self, enemy, **_):
        kind = self.loot.roll()
        if kind:
            self.drop(kind, enemy.pos.x, enemy.pos.y)

    def on_wave_started(self, **_):
        """Uncollected drops from earlier waves vanish when a new wave begins."""
        for item in self.items:
            self.events.publish("item_expired", item=item)
        self.items = []

    def drop(self, kind, x, y):
        x = max(12, min(S.MAP_W - 12, x))
        y = max(12, min(S.MAP_H - 12, y))
        self.items.append(Item(kind, self.data["items"][kind], x, y))

    def collect(self, item):
        if not item.remove:
            item.remove = True
            self.events.publish("item_collected", item=item)

    def try_click(self, pos):
        for item in self.items:
            if circles_overlap(pos[0], pos[1], 4, item.x, item.y, S.ITEM_RADIUS + S.ITEM_CLICK_PAD):
                self.collect(item)
                return True
        return False

    def on_update(self, dt, commander, waves=None):
        warn = (waves is not None and waves.phase == "build"
                and waves.countdown <= S.ITEM_WARN_TIME)
        for item in self.items:
            item.expiring = warn
            item.update(dt)
            if commander.alive and circles_overlap(commander.pos.x, commander.pos.y, commander.radius,
                                                   item.x, item.y, S.ITEM_RADIUS):
                self.collect(item)
        self.items = [i for i in self.items if not i.remove]

    def on_render(self, screen, offset):
        for item in self.items:
            item.render(screen, self.assets, offset)

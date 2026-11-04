"""Wild ideas: a tameable alien pet, the Living Core, and tower sacrifice.

    H        tame a weakened alien (under 35% HP, next to Vance, not a boss): it follows her
             and bites nearby aliens for the rest of the sector (the rest of the run in a
             Siege Run)
    Delete   sacrifice the selected tower: it's destroyed, and an Orbital Strike lands on it
             (bigger the more you'd spent on it)
    Living Core (Endless / Siege Run): aliens killed near the Core feed it. After 40 and 120
             it evolves down the path of what it ate most: armored aliens -> Carapace (takes
             less damage), flyers -> Spore Launcher (shoots flyers), the rest -> Regrowth
             (heals after every wave).
The Brood Turret ("alien tower") lives in TowerSystem._behavior_brood.
"""
import math
import random

import pygame

from .. import settings as S

CORE_PATHS = {"carapace": ("Carapace", (150, 160, 180), "Core takes {}% less damage"),
              "spores": ("Spore Launcher", (170, 220, 90), "Core shoots flyers for {} damage"),
              "regrowth": ("Regrowth", S.GREEN, "Core heals {} HP after each wave")}


class Wild:
    def __init__(self, play):
        self.play = play
        self.pet = None
        run = play.run
        if run is not None and getattr(run, "pet", None):
            self.pet = {"kind": run.pet, "x": 0.0, "y": 0.0, "cd": 0.0, "a": 0.0}
        self.living = play.endless or run is not None
        self.fed = {"armored": 0, "flyer": 0, "other": 0}
        self.stage = 0
        self.path = None
        self.spore_cd = 0.0
        play.events.subscribe("enemy_killed", self.on_kill)
        play.events.subscribe("wave_cleared", self.on_wave_cleared)

    # ---- pet -----------------------------------------------------------------------------
    def tame(self):
        play = self.play
        c = play.player.commander
        if not c.alive:
            return False
        cands = [e for e in play.enemies.enemies if e.targetable and not e.is_boss and not e.flying
                 and e.health.ratio < 0.35 and e.pos.distance_squared_to(c.pos) < 60 * 60
                 and not getattr(e, "tame", False)]
        if not cands:
            play.ui.toast("Get Vance next to an alien under 35% HP to tame it", S.TEXT_DIM)
            return False
        e = min(cands, key=lambda e: e.pos.distance_squared_to(c.pos))
        e.remove = True
        self.pet = {"kind": e.kind, "x": e.pos.x, "y": e.pos.y, "cd": 0.0, "a": 0.0}
        if play.run is not None:
            play.run.pet = e.kind
        play.effects.ring(e.pos.x, e.pos.y, 26, (255, 120, 180), 0.5, width=3)
        play.ui.toast(f"Tamed a {e.stats.get('name', e.kind)}! It fights for Vance now.", (255, 120, 180))
        play.audio.play("pickup")
        if hasattr(play, "meta"):
            play.meta.count("tamed")
        return True

    # ---- Living Core ----------------------------------------------------------------------
    def on_kill(self, enemy, **_):
        if not self.living or getattr(enemy, "tame", False):
            return
        cores = self.play.level.core_positions
        if not any((enemy.pos.x - x) ** 2 + (enemy.pos.y - y) ** 2 <= 220 ** 2 for x, y in cores):
            return
        if enemy.flying:
            self.fed["flyer"] += 1
        elif enemy.health.armor >= 3 or enemy.kind in ("brute", "juggernaut"):
            self.fed["armored"] += 1
        else:
            self.fed["other"] += 1
        total = sum(self.fed.values())
        if (self.stage == 0 and total >= 40) or (self.stage == 1 and total >= 120):
            self.stage += 1
            if self.path is None:
                top = max(self.fed, key=self.fed.get)
                self.path = {"armored": "carapace", "flyer": "spores", "other": "regrowth"}[top]
            name, col, _d = CORE_PATHS[self.path]
            x, y = cores[0]
            self.play.effects.ring(x, y, 70, col, 0.8, width=5)
            self.play.ui.toast(f"The Core evolved: {name} {self.stage}  ({self.describe()})", col)
            self.play.audio.play("upgrade")

    @property
    def damage_mult(self):
        return 1.0 - 0.2 * self.stage if self.path == "carapace" else 1.0

    def describe(self):
        if self.path is None:
            return f"Living Core: fed {sum(self.fed.values())}/40"
        n = {"carapace": 20 * self.stage, "spores": 30 * self.stage, "regrowth": 3 * self.stage}[self.path]
        return CORE_PATHS[self.path][2].format(n)

    def on_wave_cleared(self, **_):
        if self.path == "regrowth":
            s = self.play.session
            s.core_hp = min(s.core_max, s.core_hp + 3 * self.stage)

    # ---- per frame ------------------------------------------------------------------------
    def update(self, dt):
        play = self.play
        c = play.player.commander
        p = self.pet
        if p is not None:
            p["a"] += dt * 1.5
            tx = c.pos.x - 22 * math.cos(p["a"] * 0.3)
            ty = c.pos.y + 18
            target = None
            near = [e for e in play.collision.enemies_in_range(p["x"], p["y"], 90, False)]
            if near:
                target = min(near, key=lambda e: (e.pos.x - p["x"]) ** 2 + (e.pos.y - p["y"]) ** 2)
                tx, ty = target.pos.x, target.pos.y
            dx, dy = tx - p["x"], ty - p["y"]
            d = math.hypot(dx, dy)
            step = 140 * dt
            if d > step:
                p["x"] += dx / d * step
                p["y"] += dy / d * step
            p["cd"] -= dt
            if target is not None and d < 22 and p["cd"] <= 0:
                p["cd"] = 0.7
                play.enemies.damage(target, 10 + 2 * play.progress.level, quiet=True)
                play.effects.burst(target.pos.x, target.pos.y, (255, 120, 180), 4, 60, 0.2, 2)
        if self.path == "spores":
            self.spore_cd -= dt
            if self.spore_cd <= 0:
                for x, y in play.level.core_positions:
                    fly = [e for e in play.collision.enemies_in_range(x, y, 240, True) if e.flying]
                    if fly:
                        e = random.choice(fly)
                        play.enemies.damage(e, 30 * self.stage)
                        play.effects.beam(x, y, e.pos.x, e.pos.y, (170, 220, 90), 0.15)
                self.spore_cd = 1.5

    def render(self, screen, assets, offset):
        p = self.pet
        if p is not None:
            img = assets.get(f"{p['kind']}_0")
            x, y = int(p["x"] + offset[0]), int(p["y"] + offset[1])
            screen.blit(img, img.get_rect(center=(x, y)))
            pygame.draw.polygon(screen, (255, 120, 180), [(x - 4, y - 16), (x, y - 12), (x + 4, y - 16),
                                                         (x + 2, y - 19), (x, y - 17), (x - 2, y - 19)])
        if self.path:
            _n, col, _d = CORE_PATHS[self.path]
            t = pygame.time.get_ticks() / 400
            for x, y in self.play.level.core_positions:
                for k in range(3 * self.stage):
                    a = t + k * math.tau / (3 * self.stage)
                    px, py = x + math.cos(a) * 40 + offset[0], y + math.sin(a) * 40 + offset[1]
                    pygame.draw.circle(screen, col, (int(px), int(py)), 4)


def sacrifice(play, tower):
    """Delete key: destroy the selected tower for an Orbital Strike on its spot."""
    if tower is None or tower not in play.towers.towers:
        return False
    towers = play.towers
    pl = play.player
    dmg = pl.orbital_damage * (0.6 + tower.spent / 400)
    towers.towers.remove(tower)
    play.level.vacate(tower.tx, tower.ty)
    towers.selected = None
    for c in tower.chips:
        play.session.chips[c] = play.session.chips.get(c, 0) + 1
    play.enemies.splash(tower.x, tower.y, pl.orbital_radius, dmg, include_air=True, knockback=24)
    for _ in range(3):
        play.effects.explosion(tower.x, tower.y, S.ORANGE, count=30)
    play.effects.ring(tower.x, tower.y, pl.orbital_radius, S.WHITE, 0.5, width=4)
    play.effects.flash(S.WHITE, 0.2)
    play.effects.shake(0.7)
    play.audio.play("explode")
    play.ui.toast(f"{tower.name} sacrificed: Orbital Strike for {int(dmg)}!", S.ORANGE)
    towers.refresh_topology()
    return True

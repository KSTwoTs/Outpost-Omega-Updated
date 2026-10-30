"""EnemySystem: spawns enemies, applies damage, reports kills and Core hits."""
import math
import random

from .. import settings as S
from ..entities.enemy import ENEMY_CLASSES


class EnemySystem:
    def __init__(self, events, level, enemy_data, difficulty, audio, effects, assets=None):
        self.events = events
        self.level = level
        self.data = enemy_data
        self.diff = S.DIFFICULTIES[difficulty]
        self.audio = audio
        self.effects = effects
        self.assets = assets       # the boss builds its collision mask from its sprite
        self.enemies = []
        self.commander = None      # set by PlayScene after PlayerSystem exists
        self.towers = None         # set by PlayScene (Saboteurs look for towers)
        events.subscribe("spawn_enemy", self.on_spawn_enemy)
        events.subscribe("path_changed", self.on_path_changed)
        # Later sectors are tougher: level files can scale enemy HP.
        self.level_hp_mult = level.data.get("enemy_hp_mult", 1.0)

    @property
    def alive_count(self):
        return len(self.enemies)

    def on_spawn_enemy(self, enemy_type, wave, lane=0, **_):
        self.spawn(enemy_type, wave, lane=lane)

    def on_path_changed(self, **_):
        """Hive walls moved: every ground alien re-plans from where it stands."""
        for e in self.enemies:
            if e.targetable and not e.flying:
                e.reroute(self.level.route_from(e.pos.x, e.pos.y))

    def spawn(self, kind, wave, start_distance=0.0, pos=None, route=None, lane=0):
        if kind not in self.data:
            raise KeyError(f"Wave asks for unknown enemy '{kind}' (check enemies.json)")
        stats = self.data[kind]
        cls = ENEMY_CLASSES[kind]
        hp_mult = (1 + S.WAVE_HP_SCALE * wave) * self.diff["hp"] * self.level_hp_mult
        e = cls(kind, stats, self, hp_mult=hp_mult, speed_mult=self.diff["speed"],
                reward_mult=self.diff["reward"], start_distance=start_distance,
                route=route, lane=lane)
        e.wave = wave
        if e.is_boss:
            self.events.publish("boss_spawned", enemy=e)
        if pos is not None and not e.flying:
            e.pos.update(pos)
        self.enemies.append(e)
        return e

    # ---- damage --------------------------------------------------------------
    def damage(self, enemy, amount, ignore_armor=False, quiet=False):
        if not enemy.targetable:
            return 0
        if enemy.invulnerable:
            if not quiet and random.random() < 0.3:
                self.effects.number(enemy.pos.x, enemy.pos.y - enemy.radius, "SHIELD", S.MAGENTA)
            return 0
        dealt = enemy.health.damage(amount, ignore_armor=ignore_armor)
        if dealt and not quiet:
            enemy.flash_timer = 0.08
            self.effects.number(enemy.pos.x, enemy.pos.y - enemy.radius, dealt)
        if enemy.health.is_dead:
            self.kill(enemy)
        return dealt

    def splash(self, x, y, radius, damage, include_air=True, knockback=10):
        """Area damage with linear falloff (100% at center, 40% at the edge)."""
        for e in list(self.enemies):
            if not e.targetable or (e.flying and not include_air):
                continue
            d = math.hypot(e.pos.x - x, e.pos.y - y)
            if e.hit_test_circle(x, y, radius):
                falloff = 1.0 - 0.6 * min(1.0, d / radius)
                if knockback and d > 0:
                    e.knockback(knockback * falloff, ((e.pos.x - x) / d, (e.pos.y - y) / d))
                self.damage(e, damage * falloff)

    def kill(self, enemy):
        enemy.fsm.change("dying")
        self.events.publish("enemy_killed", enemy=enemy)
        spawn = enemy.stats.get("spawn_on_death")
        if spawn:  # Brood Sac
            for i in range(spawn["count"]):
                back = max(0.0, enemy.follower.distance - i * 10)
                self.spawn(spawn["enemy"], getattr(enemy, "wave", 1), start_distance=back,
                           route=enemy.follower.waypoints)

    def enemy_reached_core(self, enemy):
        if enemy.reached_core:
            return
        enemy.reached_core = True
        enemy.remove = True
        self.events.publish("enemy_reached_core", enemy=enemy)

    # ---- loop ------------------------------------------------------------------
    def on_update(self, dt):
        for e in list(self.enemies):
            e.update(dt)
        self.enemies = [e for e in self.enemies if not e.remove]

    def on_render(self, screen, assets, offset):
        # Ground first, flyers on top.
        for e in sorted(self.enemies, key=lambda en: (en.flying, en.pos.y)):
            e.render(screen, assets, offset)

"""EnemySystem: spawns enemies, applies damage, reports kills and Core hits.

Endless mode: each wave can carry "mods" (HP / speed / armor multipliers from
mutators and endless scaling, plus an elite chance). Enemies spawned by the
wave roll for an elite affix from endless.json; children (Brood Sac Skitters,
boss summons) get the wave mods but never an affix.
"""
import math
import random

from .. import settings as S
from ..entities.enemy import ENEMY_CLASSES


class EnemySystem:
    def __init__(self, events, level, enemy_data, difficulty, audio, effects, assets=None,
                 elite_data=None):
        self.events = events
        self.level = level
        self.data = enemy_data
        self.diff = S.DIFFICULTIES[difficulty]
        self.audio = audio
        self.effects = effects
        self.assets = assets       # the boss builds its collision mask from its sprite
        self.enemies = []
        self.commander = None      # set by PlayScene after PlayerSystem exists
        self.partner = None        # local co-op Player 2
        self.towers = None         # set by PlayScene (Saboteurs look for towers)
        self.elite_data = elite_data or {}
        self.mods = {}             # current wave's endless modifiers
        self.slowed_damage_mult = 1.0   # Siege Run "Brittle Shells" augment
        self.boss_damage_mult = 1.0     # augments / heroes (see Modifiers in systems/run.py)
        self.elite_damage_mult = 1.0
        self.crit_chance = 0.0          # tower hits only
        self.crit_mult = 2.0
        self.execute = 0.0              # non-boss aliens below this HP fraction die to tower hits
        self.env_speed_mult = 1.0       # Blizzard weather
        self.session = None             # set by PlayScene (Thieves steal Energy)
        self.corpses = []               # recent deaths a Necro-Spore can raise
        self.terrain_blast = None       # MapFeatures.blast: splash breaks rocks (Endless / Siege Run)
        self.force_elite = 0.0          # Weekly "Elite Storm" / Ascension
        events.subscribe("spawn_enemy", self.on_spawn_enemy)
        events.subscribe("wave_started", self.on_wave_started)
        events.subscribe("path_changed", self.on_path_changed)
        # Later sectors are tougher: level files can scale enemy HP.
        self.level_hp_mult = level.data.get("enemy_hp_mult", 1.0)

    @property
    def alive_count(self):
        return len(self.enemies)

    def on_wave_started(self, mods=None, **_):
        self.mods = mods or {}

    def on_spawn_enemy(self, enemy_type, wave, lane=0, **_):
        e = self.spawn(enemy_type, wave, lane=lane)
        chance = max(self.mods.get("elite_chance", 0.0), self.force_elite)
        affixes = self.elite_data.get("affixes", {})
        if not e.is_boss and affixes and chance > 0 and random.random() < chance:
            self.make_elite(e, random.choice(list(affixes)))

    def make_elite(self, e, affix):
        cfg = self.elite_data["affixes"][affix]
        hp_mult = self.elite_data.get("hp_mult", 2.0)
        e.health.max_hp *= hp_mult
        e.health.hp = e.health.max_hp
        e.reward = round(e.reward * self.elite_data.get("reward_mult", 2.0))
        e.score = round(e.score * self.elite_data.get("reward_mult", 2.0))
        e.affix = affix
        e.affix_cfg = cfg
        e.base_speed *= cfg.get("speed_mult", 1.0)
        e.health.armor += cfg.get("armor_add", 0)
        e.regen = cfg.get("regen", 0.0)
        e.lifesteal = cfg.get("lifesteal", 0.0)
        e.shield = e.max_shield = e.health.max_hp * cfg.get("shield", 0.0)

    def on_path_changed(self, **_):
        """Hive walls moved: every ground alien re-plans from where it stands."""
        for e in self.enemies:
            if e.targetable and not e.flying:
                e.reroute(self.level.route_from(e.pos.x, e.pos.y))

    def spawn(self, kind, wave, start_distance=0.0, pos=None, route=None, lane=0, announce=True):
        if kind not in self.data:
            raise KeyError(f"Wave asks for unknown enemy '{kind}' (check enemies.json)")
        stats = self.data[kind]
        cls = ENEMY_CLASSES[kind]
        m = self.mods
        hp_mult = ((1 + S.WAVE_HP_SCALE * wave) * self.diff["hp"] * self.level_hp_mult
                   * m.get("hp_mult", 1.0))
        speed_mult = self.diff["speed"] * m.get("speed_mult", 1.0) * self.env_speed_mult
        e = cls(kind, stats, self, hp_mult=hp_mult, speed_mult=speed_mult,
                reward_mult=self.diff["reward"], start_distance=start_distance,
                route=route, lane=lane)
        e.wave = wave
        e.health.armor += m.get("armor_add", 0)
        if e.is_boss:
            boss_mult = m.get("boss_hp_mult", 1.0)
            e.health.max_hp *= boss_mult
            e.health.hp = e.health.max_hp
            if announce:
                self.events.publish("boss_spawned", enemy=e)
        if pos is not None and not e.flying:
            e.pos.update(pos)
        self.enemies.append(e)
        return e

    # ---- damage --------------------------------------------------------------
    def damage(self, enemy, amount, ignore_armor=False, quiet=False, source=None):
        """source = the tower that dealt it (veterancy bonus + kill credit), or None."""
        if not enemy.targetable:
            return 0
        crit = False
        if source is not None:
            amount *= getattr(source, "vet_mult", 1.0) * (1.0 + getattr(source, "damage_buff", 0.0))
            if self.crit_chance and random.random() < self.crit_chance:
                amount *= self.crit_mult
                crit = True
        if enemy.is_boss:
            amount *= self.boss_damage_mult
        elif enemy.affix:
            amount *= self.elite_damage_mult
        if enemy.aura_shield > 0:   # under a Shield Drone's bubble
            amount *= 0.5
        if enemy.invulnerable:
            if not quiet and random.random() < 0.3:
                self.effects.number(enemy.pos.x, enemy.pos.y - enemy.radius, "SHIELD", S.MAGENTA)
            return 0
        if enemy.slow > 0:
            amount *= self.slowed_damage_mult
        if enemy.aura_dr:   # Swarm Mind / Queenlet
            amount *= 1.0 - enemy.aura_dr
        if source is not None and hasattr(enemy, "damage_type_mult"):   # Adaptive
            amount *= enemy.damage_type_mult(source)
            enemy.note_damage(source, amount)
        vuln = getattr(enemy, "vuln", 0.0)   # Mutagen Lab
        if vuln:
            amount *= 1.0 + vuln
        if enemy.shield > 0:   # Shielded elites soak damage before HP
            absorbed = min(enemy.shield, amount)
            enemy.shield -= absorbed
            amount -= absorbed
            if amount <= 0:
                enemy.flash_timer = 0.05
                if source is not None and hasattr(source, "wave_damage"):
                    source.wave_damage += absorbed
                return absorbed
        dealt = enemy.health.damage(amount, ignore_armor=ignore_armor)
        if source is not None and getattr(source, "stance", None) == "suppress":
            enemy.apply_slow(0.25, 0.8)
        if source is not None and hasattr(source, "wave_damage"):   # post-wave report
            source.wave_damage += dealt
        if dealt and not quiet:
            enemy.flash_timer = 0.08
            self.effects.number(enemy.pos.x, enemy.pos.y - enemy.radius, dealt,
                                *((S.ENERGY,) if crit else ()))
        if (self.execute and source is not None and not enemy.is_boss and not enemy.health.is_dead
                and enemy.health.ratio < self.execute):
            enemy.health.damage(enemy.health.hp + 1, ignore_armor=True)
            self.effects.floating_text(enemy.pos.x, enemy.pos.y - 24, "EXECUTED", S.RED, 16)
        if enemy.health.is_dead:
            if hasattr(enemy, "intercept_death") and enemy.intercept_death():
                return dealt   # Hive Mind body went dormant instead
            if source is not None and hasattr(source, "record_kill"):
                source.record_kill()
            self.kill(enemy)
        return dealt

    def splash(self, x, y, radius, damage, include_air=True, knockback=10, source=None):
        """Area damage with linear falloff (100% at center, 40% at the edge)."""
        if self.terrain_blast is not None and damage >= 20:
            self.terrain_blast(x, y, radius, damage)
        for e in list(self.enemies):
            if not e.targetable or e.hidden or (e.flying and not include_air):
                continue
            d = math.hypot(e.pos.x - x, e.pos.y - y)
            if e.hit_test_circle(x, y, radius):
                falloff = 1.0 - 0.6 * min(1.0, d / radius)
                if knockback and d > 0:
                    e.knockback(knockback * falloff, ((e.pos.x - x) / d, (e.pos.y - y) / d))
                self.damage(e, damage * falloff, source=source)

    def kill(self, enemy):
        enemy.fsm.change("dying")
        self.events.publish("enemy_killed", enemy=enemy)
        carrying = getattr(enemy, "carrying", 0)
        if carrying and self.session is not None:   # caught a Thief: Energy back plus a bonus
            back = int(carrying * 1.25)
            self.session.energy += back
            self.effects.floating_text(enemy.pos.x, enemy.pos.y - 20, f"+{back} E RECOVERED", S.ENERGY, 20)
        if not enemy.is_boss and not enemy.flying and not enemy.zombie:   # Necro-Spore fodder
            self.corpses.append({"kind": enemy.kind, "x": enemy.pos.x, "y": enemy.pos.y,
                                 "distance": enemy.follower.distance, "route": enemy.follower.waypoints,
                                 "wave": getattr(enemy, "wave", 1), "t": 3.0})
        if enemy.affix == "volatile":
            self.volatile_blast(enemy)
        spawn = enemy.stats.get("spawn_on_death")
        if spawn:  # Brood Sac
            for i in range(spawn["count"]):
                back = max(0.0, enemy.follower.distance - i * 10)
                self.spawn(spawn["enemy"], getattr(enemy, "wave", 1), start_distance=back,
                           route=enemy.follower.waypoints)

    def volatile_blast(self, enemy):
        cfg = enemy.affix_cfg
        r = cfg.get("blast_radius", 70)
        self.effects.explosion(enemy.pos.x, enemy.pos.y, S.ORANGE, count=18)
        self.effects.ring(enemy.pos.x, enemy.pos.y, r, S.ORANGE, 0.35, width=3)
        self.effects.shake(0.15)
        if self.towers is None:
            return
        for t in self.towers.towers:
            if enemy.pos.distance_squared_to((t.x, t.y)) <= r * r:
                t.health.damage(cfg.get("blast_damage", 25), ignore_armor=True)

    def enemy_reached_core(self, enemy):
        if enemy.reached_core:
            return
        enemy.reached_core = True
        enemy.remove = True
        self.events.publish("enemy_reached_core", enemy=enemy)

    # ---- loop ------------------------------------------------------------------
    def update_reveals(self):
        """Cloakers and Burrowers show up when Vance or a Radar Relay is close."""
        relays = []
        if self.towers is not None:
            relays = [(t.x, t.y, t.stats["range"]) for t in self.towers.towers
                      if t.behavior == "support" and t.fsm.name == "active"]
        cmds = [c for c in self.all_commanders() if c is not None and c.alive]
        for e in self.enemies:
            if not hasattr(e, "revealed"):
                continue
            r = e.stats.get("reveal_range", 140)
            seen = any(e.pos.distance_squared_to(c.pos) <= r * r for c in cmds)
            if not seen:
                seen = any((e.pos.x - x) ** 2 + (e.pos.y - y) ** 2 <= rr * rr for x, y, rr in relays)
            e.revealed = seen

    def all_commanders(self):
        return (self.commander, self.partner) if self.partner is not None else (self.commander,)

    def light_sources(self):
        """(x, y, radius) of everything that lights up a dark sector."""
        lights = [(x, y, 150) for x, y in self.level.core_positions]
        if self.towers is not None:
            lights += [(t.x, t.y, 120 + 40 * (t.behavior == "support")) for t in self.towers.towers]
        for cmd in self.all_commanders():
            if cmd is not None and cmd.alive:
                lights.append((cmd.pos.x, cmd.pos.y, 160))
        return lights

    def update_lighting(self):
        if not self.level.dark:
            return
        lights = self.light_sources()
        for e in self.enemies:
            e.in_dark = not e.is_boss and not any(
                (e.pos.x - x) ** 2 + (e.pos.y - y) ** 2 <= r * r for x, y, r in lights)

    def update_auras(self, dt):
        """Swarm Mind and Swarm Queenlet buffs; also ages the corpse list."""
        for e in self.enemies:
            e.aura_speed = 0.0
            e.aura_dr = 0.0
        for e in self.enemies:
            if getattr(e, "aura_source", False) and e.targetable:
                e.apply_aura(self.enemies)
        for c in self.corpses:
            c["t"] -= dt
        self.corpses = [c for c in self.corpses if c["t"] > 0]

    def on_update(self, dt):
        self.update_reveals()
        self.update_lighting()
        self.update_auras(dt)
        for e in list(self.enemies):
            e.update(dt)
        self.enemies = [e for e in self.enemies if not e.remove]

    def on_render(self, screen, assets, offset):
        # Ground first, flyers on top.
        for e in sorted(self.enemies, key=lambda en: (en.flying, en.pos.y)):
            e.render(screen, assets, offset)

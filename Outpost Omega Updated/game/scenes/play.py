"""PlayScene: one run of one sector. Creates and wires every gameplay system.

Systems talk through this scene's EventBus:
    enemy_killed       -> +Energy, score, goo particles, loot drop
    enemy_reached_core -> Core damage, screen shake, red flash
    item_collected     -> apply the item's effect
    wave_started / wave_cleared / all_waves_cleared -> banners, win check
"""
import math
import random
from dataclasses import dataclass

import pygame

from .. import settings as S
from ..core import Cooldown, EventBus
from ..entities.item import ItemManager
from ..systems.collision_system import CollisionSystem
from ..systems.effects_system import EffectsSystem
from ..systems.input_system import Command
from ..systems.endless import EndlessWaveGenerator
from ..systems.environment import WEATHER, VentSystem, WeatherSystem
from ..systems.progression import CommanderProgress, CoreUpgrades, apply_perk
from ..systems.run import Modifiers, hero_allowed
from ..systems.enemy_system import EnemySystem
from ..systems.level_system import LevelSystem
from ..systems.player_system import PlayerSystem
from ..systems.projectile_system import ProjectileSystem
from ..systems.tower_system import TowerSystem
from ..systems.ui_system import UISystem
from ..systems.wave_system import WaveSystem
from .scene_manager import Scene


@dataclass
class Session:
    level_id: str
    difficulty: str
    energy: int
    core_hp: float
    core_max: int
    score: int = 0
    kills: int = 0
    chips: dict = None      # augment chip inventory {chip id: count}
    gear: dict = None       # Commander gear {slot: tier}
    biomass: int = 0        # second resource (kills, Bio-Labs); pays for research

    @property
    def core_ratio(self):
        return max(0.0, self.core_hp / self.core_max)

    def stars(self):
        hi, mid = S.STAR_THRESHOLDS
        if self.core_ratio > hi:
            return 3
        if self.core_ratio > mid:
            return 2
        return 1

    def final_score(self):
        return self.score + self.energy


class PlayScene(Scene):
    END_DELAY = 2.0
    SPEEDS = (1, 2, 3)

    def __init__(self, game, level_id="sector1", difficulty=S.DEFAULT_DIFFICULTY, mode="campaign",
                 daily=None, seed=None, tutorial=False, variant=None, **kwargs):
        super().__init__(game, **kwargs)
        # Everything needed to restart this exact sector (Retry / Restart).
        self.launch = dict(level_id=level_id, difficulty=difficulty, mode=mode, daily=daily, seed=seed,
                           variant=variant)
        self.force_elite = 0.0
        self.daily = daily       # date key ("2026-10-30") for the Daily Challenge, else None
        self.seed = seed
        data = game.data
        self.level_id = level_id
        self.difficulty = difficulty
        self.mode = mode
        self.endless = mode == "endless"
        self.run = game.run if mode == "run" else None   # Siege Run state (systems/run.py)
        # Commander class + (in a Siege Run) augments, relics and tech all become one effect list.
        self.commander_class = (self.run.commander if self.run and self.run.commander
                                else game.commander_class)
        hero = data["commanders"].get(self.commander_class, {})
        if mode == "campaign" and not hero_allowed(hero, "campaign"):   # heroes are Endless / Siege Run only
            self.commander_class = next(c for c, h in data["commanders"].items() if hero_allowed(h, "campaign"))
            hero = data["commanders"][self.commander_class]
        cls_effects = hero.get("effects", [])
        mods = Modifiers((self.run.effects if self.run else []) + cls_effects)
        owned = self.run.towers if self.run else list(data["towers"])
        tower_data = mods.tower_data(data["towers"], owned)
        items_data = mods.items_data(data["items"])
        self.kill_mult = mods.mult("kill_reward")
        self.interest = mods.interest()
        self.wave_energy = int(mods.add("wave_energy"))
        self.wave_heal = mods.add("wave_heal")
        build_bonus = mods.add("build_time")
        self.crystal_every = mods.crystal_every()
        self.speed = 1           # simulation steps per frame step (F cycles 1x/2x/3x)
        self.new_best = False
        self.events = ev = EventBus()
        self.level = LevelSystem(ev, level_id)
        lvl = self.level.data
        if self.run:
            self.session = Session(level_id, difficulty,
                                   energy=lvl.get("start_energy", S.START_ENERGY) + int(mods.add("start_energy")),
                                   core_hp=self.run.core_hp, core_max=self.run.core_max)
        else:
            self.session = Session(level_id, difficulty,
                                   energy=lvl.get("start_energy", S.START_ENERGY),
                                   core_hp=lvl.get("core_hp", 100), core_max=lvl.get("core_hp", 100))
        self.effects = EffectsSystem(self.assets)
        self.effects.configure(game.settings)
        self.collision = CollisionSystem()
        self.enemies = EnemySystem(ev, self.level, data["enemies"], difficulty, self.audio,
                                   self.effects, self.assets,
                                   elite_data=data["endless"].get("elites") if (self.endless or self.run) else None)
        self.projectiles = ProjectileSystem(ev, self.collision, self.enemies, self.effects, self.audio)
        self.towers = TowerSystem(ev, self.level, tower_data, self.session, self.collision,
                                  self.projectiles, self.enemies, self.effects, self.audio)
        self.player = PlayerSystem(ev, self.level, self.input, self.collision, self.projectiles,
                                   self.enemies, self.towers, self.effects, self.audio)
        self.enemies.commander = self.player.commander
        self.towers.commander = self.player.commander
        self.towers.player = self.player
        self.enemies.towers = self.towers
        self.enemies.session = self.session
        self.items = ItemManager(ev, items_data, self.assets)
        kit = data["kit"]
        self.items.subtypes = {"chip": list(data["systems"]["chips"]), "weapon": list(kit["weapons"]),
                               "grenade": list(kit["grenades"]), "gear": list(kit["gear"])}
        self.player.items = self.items
        # Modifiers are identity values (x1, +0) when nothing changes them.
        cmd = self.player.commander
        cmd.health.reset(S.CMD_MAX_HP * mods.mult("cmd_hp"))
        cmd.max_speed = S.CMD_MAX_SPEED * mods.mult("cmd_speed")
        cmd.repair_time = S.REPAIR_TIME / mods.mult("repair_speed")
        self.player.orbital = Cooldown(S.ORBITAL_COOLDOWN * mods.mult("orbital_cooldown"), ready=True)
        self.player.orbital_damage = S.ORBITAL_DAMAGE * mods.mult("orbital_damage")
        self.player.commander.blaster_damage = S.BLASTER_DAMAGE * mods.mult("blaster_damage")
        self.towers.sell_refund = mods.set("sell_refund", S.SELL_REFUND)
        self.enemies.slowed_damage_mult = mods.mult("slowed_damage")
        self.towers.allow_branches = self.run is not None
        self.towers.allow_fusion = self.run is not None or self.endless
        self.towers.systems = data["systems"]
        from ..systems.commander_kit import CommanderKit
        if self.run is not None:   # gear carries over between Siege Run fights
            self.run.gear = getattr(self.run, "gear", None) or {}
            self.session.gear = self.run.gear
        else:
            self.session.gear = {}
        self.player.kit = CommanderKit(self.player, data["kit"], self.session, ev)
        from ..systems.economy import Economy
        from ..systems.juice import Juice
        from ..systems.tutorial import Tutorial
        self.economy = Economy(self, data["economy"])
        self.towers.economy = self.economy
        self.juice = Juice(self)
        self.towers.on_broken = self.on_tower_broken
        self.tutorial = Tutorial() if tutorial else None
        from ..systems.meta import MetaTracker
        from ..systems.wild import Wild
        self.meta = MetaTracker(self)
        self.wild = Wild(self)
        self.sandbox_menu = False
        if self.run is not None:   # chips carry over between Siege Run fights
            self.run.chips = getattr(self.run, "chips", None) or {}
            self.session.chips = self.run.chips
        else:
            self.session.chips = {}
        cmd.blaster_range = S.BLASTER_RANGE * mods.mult("blaster_range")
        cmd.damage_taken = mods.mult("cmd_armor")
        cmd.respawn_time = S.CMD_RESPAWN * mods.mult("respawn_time")
        cmd.skin = self.commander_class if hero.get("palette") else None
        skin = game.settings.get("skin", "classic")
        if cmd.skin is None and skin != "classic":   # unlocked Commander skins (Settings)
            cmd.skin = "skin_" + skin
        self.hero_name = hero.get("callsign", "VANCE")
        self.player.orbital_radius = S.ORBITAL_RADIUS * mods.mult("orbital_radius")
        self.enemies.boss_damage_mult = mods.mult("boss_damage")
        self.enemies.elite_damage_mult = mods.mult("elite_damage")
        self.enemies.crit_chance = mods.add("crit_chance")
        self.enemies.crit_mult = 2.0 + mods.add("crit_damage")
        self.enemies.execute = max([e.get("set", 0) for e in mods.of("execute")] + [0])
        self.towers.vet_bonus_mult = mods.mult("vet_bonus")
        generator = None
        if self.endless:
            generator = EndlessWaveGenerator(data["endless"], data["enemies"],
                                             lanes=self.level.lane_count, seed=seed)
        waves = lvl.get("waves")
        if not waves:   # custom maps from the editor: ten generated waves, a boss on the last
            gen = EndlessWaveGenerator(data["endless"], data["enemies"], lanes=self.level.lane_count, seed=7)
            waves = [gen.wave(n) for n in range(1, 11)]
        from ..systems import modes as game_modes
        waves = game_modes.prepare(self, variant, data, lvl) or waves
        if self.run:
            waves = self.run.node_waves(self.run.node, data["endless"], data["enemies"],
                                        lanes=self.level.lane_count)
        self.waves = WaveSystem(ev, waves, max(3.0, lvl.get("build_time", S.BUILD_PHASE_TIME) + build_bonus),
                                generator=generator)
        self.ui = UISystem(self.assets, tower_data)
        self.core = CoreUpgrades(self)
        self.core.bonus_shield = mods.add("core_shield")
        self.kill_bonus = 0
        r = self.run
        self.progress = CommanderProgress(data["perks"],
                                          level=(r.cmd_level or 1) if r else 1,
                                          xp=(r.cmd_xp or 0) if r else 0,
                                          perks=(r.cmd_perks or []) if r else [],
                                          rng=random.Random(seed))
        for perk in self.progress.perks:   # perks earned earlier in a Siege Run
            apply_perk(self, perk)
        self.vents = VentSystem(self.level, self.towers, self.player, self.effects, self.audio, ev)
        self.weather = None
        kind = lvl.get("weather") or self.roll_weather(data)
        if kind in WEATHER:
            self.weather = WeatherSystem(kind, self.towers, self.enemies, self.level)
            self.towers.weather_kind = kind
        from ..systems.map_features import MapFeatures
        self.features = MapFeatures(self)
        self.towers.features = self.features
        self.enemies.terrain_blast = self.features.blast
        self.reverse = None
        game_modes.apply(self, variant)
        self.enemies.force_elite = self.force_elite
        if self.run is not None:   # Siege Run Ascension
            asc = getattr(self.run, "ascension", 0) or 0
            if asc >= 1:
                self.enemies.level_hp_mult *= 1.1
            if asc >= 4:
                self.enemies.force_elite = max(self.enemies.force_elite, 0.15)
            if asc >= 5:
                self.enemies.env_speed_mult *= 1.1
        self.hardcore = getattr(game, "hardcore", False) and not self.tutorial
        # Local co-op: a second Commander (arrows / controller), shared Energy and towers
        self.coop = getattr(game, "coop", False) and not self.tutorial and self.variant != "reverse"
        if self.coop:
            self.enemies.partner = self.player.add_partner()
        from ..systems.input_system import InputSystem as _IS
        _IS.coop = self.coop
        # Story campaign: radio lines during the sector, debrief after a win (scenes/story.py)
        from .story import StoryRadio, story_on
        self.story = None
        if (story_on(game, level_id, mode) and not self.variant and not self.daily and self.run is None
                and not self.tutorial):
            self.story = StoryRadio(self, data["story"]["sectors"][level_id])
        self.debug = False
        self.core_flash = 0.0
        self.t = 0.0
        self.result = None       # "win" / "lose" once the run is over
        self.end_timer = 0.0

        ev.subscribe("enemy_killed", self.on_enemy_killed)
        ev.subscribe("enemy_reached_core", self.on_enemy_reached_core)
        ev.subscribe("item_collected", self.on_item_collected)
        ev.subscribe("wave_started", self.on_wave_started)
        ev.subscribe("wave_cleared", self.on_wave_cleared)
        ev.subscribe("all_waves_cleared", lambda **_: self.finish("win"))
        ev.subscribe("toast", lambda text, color=S.WHITE, **_: self.ui.toast(text, color))
        ev.subscribe("commander_downed", self.on_commander_downed)
        ev.subscribe("boss_spawned", self.on_boss_spawned)
        ev.subscribe("walls_changed", self.on_walls_changed)
        ev.subscribe("tower_emp", lambda **_: self.ui.toast("EMP! Towers disabled - repair them with E", S.CYAN))
        ev.subscribe("commander_respawned",
                     lambda **_: self.ui.toast(f"Commander {self.hero_name.title()} is back online", S.CYAN))

    def roll_weather(self, data):
        """Endless and Siege Run sectors sometimes get weather; the campaign never does."""
        if not (self.endless or self.run):
            return None
        chance = data["endless"].get("weather_chance", 0.35)
        seed = self.seed
        if self.run:
            node = self.run.node
            seed = self.run.seed * 13 + self.run.act * 97 + node["floor"] * 11 + node["index"]
        rng = random.Random(seed)
        return rng.choice(sorted(WEATHER)) if rng.random() < chance else None

    # ---- lifecycle -------------------------------------------------------------
    def on_start(self):
        if self.daily:
            sub = f"DAILY CHALLENGE  -  {self.daily}"
        elif self.run:
            kind = self.run.node["type"].upper()
            sub = f"SIEGE RUN  -  ACT {self.run.act}  -  {kind}  -  {self.waves.total_waves} waves"
        elif self.endless:
            best = self.game.save.get("endless", {}).get(self.record_key, {}).get("wave", 0)
            sub = f"ENDLESS  -  {self.difficulty}" + (f"  -  best wave {best}" if best else "")
        else:
            sub = f"{self.difficulty}  -  {self.waves.total_waves} waves"
        from ..systems.modes import describe
        sub = describe(self.variant) or sub
        self.ui.show_banner(self.level.name, sub, 2.5)
        self.ui.toast("Build towers, then press Space to start the wave", S.ENERGY)
        if self.weather:
            info = self.weather.info
            self.ui.toast(f"Weather: {info['name']} - {info['desc']}", info["color"])
        if self.vents.vents:
            self.ui.toast("Volcanic vents erupt during waves - don't build too close", S.ORANGE)
        self.audio.play_music()
        if not self.audio.has_music():
            self.game.music.start(self.audio.music_volume)

    def on_exit(self):
        self.events.clear()
        if not self.audio.has_music():
            self.game.music.stop()

    def finish(self, result):
        if self.result:
            return
        if self.reverse is not None:   # you are the hive: a broken Core is your win
            result = "lose" if result == "win" else "win"
            self.result = result
            self.meta.finish(result)
            self.end_timer = self.END_DELAY
            if result == "win":
                self.ui.show_banner("THE HIVE WINS", "The Core is broken", self.END_DELAY)
                self.effects.flash(S.ALIEN_GREEN, 0.6)
            else:
                self.ui.show_banner("THE OUTPOST HELD", "Time ran out", self.END_DELAY)
            return
        self.result = result
        self.meta.finish(result)
        self.end_timer = self.END_DELAY
        if result == "win" and self.run:
            self.ui.show_banner("SECTOR SECURED", "Choose your reward", self.END_DELAY)
        elif result == "win":
            self.ui.show_banner("SECTOR SECURED", f"{self.session.stars()} stars", self.END_DELAY)
            self.game.record_result(self.level_id, self.session.stars(), self.session.final_score())
        else:
            sub = "The shield has fallen..."
            if self.daily:
                self.new_best = self.game.record_daily(self.daily, self.waves.wave_number,
                                                       self.session.final_score())
                sub = f"Reached wave {self.waves.wave_number}" + ("  -  NEW BEST!" if self.new_best else "")
            elif self.endless:
                self.new_best = self.game.record_endless(self.record_key, self.waves.wave_number,
                                                         self.session.final_score())
                sub = f"Reached wave {self.waves.wave_number}" + ("  -  NEW BEST!" if self.new_best else "")
            self.ui.show_banner("CORE DESTROYED", sub, self.END_DELAY)
            self.effects.flash(S.RED, 0.6)

    def end_summary(self):
        """Win/Lose screen text for modes that need their own (Reverse, Story)."""
        r = self.reverse
        if r is not None:
            used = r.data["time_limit"] - max(0, r.time_left)
            m, sec = divmod(int(used), 60)
            return {"title": "HIVE VICTORIOUS" if self.result == "win" else "OUTPOST HELD",
                    "color": S.ALIEN_GREEN if self.result == "win" else S.RED,
                    "lines": [f"Packs sent {r.sent}", f"Core left {int(max(0, self.session.core_hp))}",
                              f"Time {m}:{sec:02d}", f"Towers the outpost built {len(self.towers.towers)}"]}
        return None

    # ---- event handlers -------------------------------------------------------------
    @property
    def record_key(self):
        """Endless best-wave key: every generated map shares one 'procedural' record."""
        return "procedural" if self.level_id.startswith("proc_") else self.level_id

    def drop_chips(self, enemy):
        """Elites sometimes drop an augment chip; bosses always drop a couple."""
        sysd = self.towers.systems
        n = 0
        if enemy.is_boss:
            n = sysd.get("chip_drop_boss", 2)
        elif enemy.affix and random.random() < sysd.get("chip_drop_elite", 0.2):
            n = 1
        for i in range(n):
            self.items.drop("chip", enemy.pos.x + i * 18, enemy.pos.y)

    def on_enemy_killed(self, enemy, **_):
        self.drop_chips(enemy)
        reward = (max(1, round(enemy.reward * self.kill_mult)) + self.kill_bonus) if self.kill_mult > 0 else 0
        if self.progress.add_xp(max(1, enemy.score // 10)):
            c = self.player.commander
            self.effects.ring(c.pos.x, c.pos.y, 30, S.CYAN, 0.6, width=3)
            self.ui.toast(f"{self.hero_name.title()} reached level {self.progress.level}! Pick a perk", S.CYAN)
            self.audio.play("upgrade")
        self.session.energy += reward
        self.session.score += enemy.score
        self.session.kills += 1
        self.effects.goo(enemy.pos.x, enemy.pos.y)
        self.effects.floating_text(enemy.pos.x, enemy.pos.y - 14, f"+{reward}", S.ENERGY, 18)
        if self.crystal_every and self.session.kills % self.crystal_every == 0:
            self.items.drop("energy_crystal", enemy.pos.x, enemy.pos.y)
        self.audio.play("hit")

    def on_enemy_reached_core(self, enemy, **_):
        if self.result:
            return
        damage = self.core.absorb(enemy.core_damage) * self.wild.damage_mult
        if damage <= 0:
            x, y = self.level.nearest_core_pos(enemy.pos.x, enemy.pos.y)
            self.effects.ring(x, y, 40, S.CYAN, 0.3, width=4)
            return
        self.session.core_hp = max(0, self.session.core_hp - damage)
        self.core_flash = 0.3
        self.effects.shake(0.25 + 0.04 * enemy.core_damage)
        self.effects.flash(S.RED, 0.2)
        cx, cy = self.level.nearest_core_pos(enemy.pos.x, enemy.pos.y)
        self.effects.explosion(cx, cy, S.MAGENTA, count=12)
        self.audio.play("core_hit")
        if self.session.core_hp <= 0:
            self.finish("lose")

    def on_item_collected(self, item, **_):
        info, kind = item.info, item.kind
        msg = info["name"]
        kit = self.player.kit
        if kind == "weapon":
            kit.equip_weapon(item.sub)
            msg = kit.data["weapons"][item.sub]["name"]
        elif kind == "grenade":
            kit.give_grenade(item.sub)
            msg = f"+1 {kit.data['grenades'][item.sub]['name']} grenade"
        elif kind == "gear":
            w = self.waves.wave_number
            tier = 1 + (random.random() < w / 25) + (random.random() < w / 50)
            kit.give_gear(item.sub, min(3, tier))
            msg = "Gear!"
        if kind == "chip":
            chip = getattr(item, "sub", "damage")
            self.session.chips[chip] = self.session.chips.get(chip, 0) + 1
            msg = self.towers.systems["chips"][chip]["name"] + " (select a tower, K to socket)"
        if kind == "energy_crystal":
            self.session.energy += info["energy"]
            msg = f"+{info['energy']} Energy"
        elif kind == "repair_kit":
            tower = min((t for t in self.towers.towers), default=None,
                        key=lambda t: t.health.ratio)
            if tower:
                tower.health.heal(tower.health.max_hp * info["tower_heal"])
                self.effects.ring(tower.x, tower.y, 26, S.GREEN, 0.4)
        elif kind == "overcharge":
            tower = self.towers.nearest_tower(item.x, item.y)
            if tower:
                tower.overcharge(info["duration"])
                self.effects.ring(tower.x, tower.y, 26, S.ORANGE, 0.4)
                msg = f"{tower.name} overcharged!"
        elif kind == "shield_battery":
            s = self.session
            s.core_hp = min(s.core_max, s.core_hp + info["core_hp"])
            msg = f"+{info['core_hp']} Core HP"
        self.effects.floating_text(item.x, item.y - 12, msg, S.WHITE, 20)
        self.audio.play("pickup")

    def on_wave_started(self, number, total, mods=None, mutator=None, **_):
        mods = mods or {}
        for t in self.towers.towers:   # fresh numbers for the post-wave report
            t.wave_damage, t.wave_kills = 0.0, 0
        self.ui.report_visible = False
        self.towers.range_mult = mods.get("tower_range_mult", 1.0)
        sub = "Final wave!" if number == total else ""
        wave = self.waves.current_wave or {}
        if mutator:
            m = self.game.data["endless"]["mutators"][mutator]
            sub = f"{m['name']}: {m['desc']}"
        elif wave.get("boss") and self.endless:
            sub = "Boss wave!"
        self.ui.show_banner(f"WAVE {number}", sub, 1.6 if not mutator else 2.4)
        self.audio.play("wave")

    def on_wave_cleared(self, number, **_):
        self.towers.range_mult = 1.0
        self.ui.stats_report = self.ui.build_report(number, self.towers.towers)
        self.ui.report_visible = bool(self.game.settings.get("wave_report", True))
        rate, cap = self.interest
        if rate and not self.result:
            gain = min(cap, int(self.session.energy * rate))
            if gain > 0:
                self.session.energy += gain
                self.ui.toast(f"Energy Bonds: +{gain} Energy", S.ENERGY)
        if self.wave_energy and not self.result:
            self.session.energy += self.wave_energy
            self.ui.toast(f"Supply drop: +{self.wave_energy} Energy", S.ENERGY)
        s = self.session
        if self.wave_heal and not self.result and s.core_hp < s.core_max:
            s.core_hp = min(s.core_max, s.core_hp + self.wave_heal)
            self.ui.toast(f"Core repaired +{self.wave_heal:g} HP", S.GREEN)
        if self.endless or number < self.waves.total_waves:
            self.ui.toast(f"Wave {number} cleared - build phase", S.GREEN)

    def on_walls_changed(self, grown, cleared, message, **_):
        self.ui.toast(message, S.MAGENTA)
        self.effects.shake(0.35)
        self.audio.play("shield")
        for tx, ty in grown:
            x, y = self.level.tile_center(tx, ty)
            self.effects.burst(x, y, S.MAGENTA, 16, 140, 0.5, 4)
        for tx, ty in cleared:
            x, y = self.level.tile_center(tx, ty)
            self.effects.burst(x, y, S.ALIEN_GREEN, 10, 120, 0.4, 3)

    def on_boss_spawned(self, enemy, **_):
        self.ui.show_banner(enemy.stats.get("name", "BOSS").upper(), enemy.stats.get("intro", ""), 2.5)
        self.effects.shake(0.5)
        self.audio.play("boss")

    def on_commander_downed(self, commander=None, **_):
        if self.coop:
            other = self.player.partner if commander is self.player.commander else self.player.commander
            who = "Player 2" if commander is self.player.partner else "Player 1"
            if self.hardcore and not other.alive:
                self.ui.toast("HARDCORE: both Commanders down. Game over.", S.RED)
                self.finish("lose")
                return
            if not self.hardcore:
                self.ui.toast(f"{who} down! Respawning at the Core...", S.RED)
            else:
                self.ui.toast(f"{who} down for good! Hold on, partner.", S.RED)
                commander.respawn_timer = 1e9
            self.audio.play("downed")
            return
        if self.hardcore:
            self.ui.toast("HARDCORE: Commander down. Game over.", S.RED)
            self.finish("lose")
            return
        self.ui.toast("Commander down! Respawning at the Core...", S.RED)
        self.audio.play("downed")

    # ---- input -------------------------------------------------------------------------
    def handle_command(self, cmd):
        n = cmd.name
        if n == "pause":
            self.game.scenes.push("pause")
            return
        if self.reverse is not None and not self.result and self.reverse.handle_command(cmd):
            return
        if self.result:
            return
        if n == "toggle_debug":
            self.debug = not self.debug
        elif n == "cycle_speed":
            i = self.SPEEDS.index(self.speed)
            self.speed = self.SPEEDS[(i + 1) % len(self.SPEEDS)]
            self.ui.toast(f"Game speed {self.speed}x", S.CYAN)
        elif n == "start_wave":
            self.waves.start_next_wave()
        elif n == "select_slot":
            kind = self.ui.slot_kind(cmd.value)
            if kind is not None:
                self.handle_command(Command("select_tower", value=self.towers.data[kind]["key"]))
        elif n == "select_tower":
            self.player.aiming_orbital = False
            self.ui.core_selected = False
            self.towers.select_build(cmd.value)
            if self.towers.build_kind:
                self.ui.show_tab_of(self.towers.build_kind)
        elif n == "next_tab":
            self.ui.set_tab(self.ui.tab + 1)
            self.audio.play("click")
        elif n == "set_tab":
            self.ui.set_tab(cmd.value)
            self.audio.play("click")
        elif n == "move_tower":
            t = self.towers.selected
            if t is None:
                pass
            elif self.waves.phase != "build":
                self.ui.toast("Towers can only be moved between waves", S.TEXT_DIM)
            else:
                self.towers.start_relocate(t)
        elif n == "stance":
            self.towers.toggle_stance(self.towers.selected)
        elif n == "socket":
            t = self.towers.selected
            if t is not None:
                self.ui.open_chip_picker(t, self.session.chips, self.towers.systems["chips"])
        elif n == "fuse":
            t = self.towers.selected
            opts = self.towers.fusion_options(t)
            if not self.towers.allow_fusion:
                self.ui.toast("Fusion is available in Endless and Siege Run", S.TEXT_DIM)
            elif not opts:
                self.ui.toast("Fusion needs two maxed towers from a recipe side by side", S.TEXT_DIM)
            else:
                self.ui.open_fusion_picker(t, opts, self.towers.systems)
        elif n == "pick":
            self.on_pick(cmd.value)
        elif n == "tame":
            self.wild.tame()
        elif n == "sacrifice":
            from ..systems.wild import sacrifice
            sacrifice(self, self.towers.selected)
        elif n == "sandbox_menu":
            if (self.variant or "").startswith("sandbox"):
                self.sandbox_menu = not self.sandbox_menu
        elif n == "undo":
            if self.waves.phase == "build":
                self.towers.undo_last()
        elif n == "insure":
            self.economy.toggle_insurance()
        elif n == "research":
            if self.economy.current is not None:
                self.ui.toast(f"Researching {self.economy.status}", S.TEXT_DIM)
            else:
                self.ui.open_research_picker(self.economy, self.session.biomass)
        elif n == "grenade_auto":   # controller: throw at the nearest alien
            c = self.player.commander
            e = self.collision.nearest_enemy(c.pos.x, c.pos.y, 220)
            if e is not None:
                self.player.kit.throw((e.pos.x, e.pos.y))
        elif n == "orbital_auto":   # controller: strike the strongest alien in sight
            live = [e for e in self.enemies.enemies if e.targetable and not e.hidden]
            if live and self.player.begin_orbital():
                e = max(live, key=lambda e: e.health.hp)
                self.player.confirm_orbital((e.pos.x, e.pos.y))
        elif n == "dash":
            self.player.kit.dash()
        elif n == "dash2" and self.player.partner is not None:
            self.player.kit.dash(self.player.partner)
        elif n == "grenade":
            self.player.kit.throw(self.input.mouse_pos())
        elif n == "cycle_grenade":
            self.player.kit.cycle_grenade()
        elif n == "mech":
            self.player.kit.activate_mech()
        elif n == "toggle_report":
            self.ui.report_visible = not self.ui.report_visible and self.ui.stats_report is not None
        elif n == "orbital_strike":
            self.player.begin_orbital()
        elif n == "upgrade":
            self.try_upgrade(self.towers.selected)
        elif n == "choose_perk":
            if self.progress.current_choice:
                perk = self.progress.pick(cmd.value)
                apply_perk(self, perk)
                self.ui.toast(f"Perk: {self.game.data['perks'][perk]['name']}", S.CYAN)
                self.audio.play("upgrade")
        elif n == "core_upgrade":
            self.core.upgrade(cmd.value)
        elif n == "choose_branch":
            if self.towers.choose_branch(self.ui.branch_tower, cmd.value):
                self.ui.branch_tower = None
        elif n == "sell":
            self.towers.sell()
        elif n == "cycle_targeting":
            self.towers.cycle_targeting()
        elif n == "click":
            self.on_left_click(cmd.pos)
        elif n == "right_click":
            self.on_right_click(cmd.pos)

    def on_pick(self, index):
        p = self.ui.picker
        self.ui.picker = None
        if p is None or index is None:
            return
        if p["kind"] == "research":
            self.economy.start(p["values"][index])
        elif p["kind"] == "chip":
            self.towers.socket_chip(p["tower"], p["values"][index])
        elif p["kind"] == "fusion":
            fid, partner = p["values"][index]
            self.towers.fuse(p["tower"], fid, partner)

    def on_left_click(self, pos):
        if self.sandbox_menu:
            from ..systems.modes import sandbox_click
            if sandbox_click(self, pos):
                return
        if self.towers.relocating is not None and pos[1] < S.HUD_Y:
            self.towers.try_relocate(*self.level.world_to_tile(*pos))
            return
        hud_cmd = self.ui.handle_click(pos, self)
        if hud_cmd:
            if hud_cmd.name != "hud_click":
                self.handle_command(hud_cmd)
            return
        if self.player.aiming_orbital:
            self.player.confirm_orbital(pos)
            return
        if self.items.try_click(pos):
            return
        if not self.towers.build_kind and any((pos[0] - x) ** 2 + (pos[1] - y) ** 2 <= 34 * 34
                                              for x, y in self.level.core_positions):
            self.towers.select(None)
            self.ui.core_selected = True
            return
        self.ui.core_selected = False
        tx, ty = self.level.world_to_tile(*pos)
        existing = self.towers.tower_at(tx, ty)
        if self.towers.build_kind and existing is None:
            if self.towers.try_place(tx, ty) and not self.input.shift_held():
                self.towers.cancel_build()   # hold Shift to keep placing
        else:
            self.towers.select(self.towers.tower_at(tx, ty))

    def try_upgrade(self, tower):
        """Normal upgrade, or open the tier-4 branch picker when a run tower is maxed."""
        if tower is not None and tower.branch_available:
            self.ui.branch_tower = tower
        else:
            self.towers.upgrade(tower)

    def on_right_click(self, pos):
        if self.towers.relocating is not None:
            self.towers.relocating = None
            return
        if self.ui.picker is not None:
            self.ui.picker = None
            return
        if self.ui.branch_tower is not None:
            self.ui.branch_tower = None
            return
        if self.player.aiming_orbital:
            self.player.aiming_orbital = False
            return
        if self.towers.build_kind:
            self.towers.cancel_build()
            return
        if pos[1] >= S.HUD_Y:
            return
        tower = self.towers.tower_at(*self.level.world_to_tile(*pos))
        if tower:
            self.towers.select(tower)
            self.try_upgrade(tower)
        else:
            self.towers.select(None)

    # ---- update ------------------------------------------------------------------------
    def on_update(self, dt):
        self.ui.on_update(dt)
        if self.result:
            self.t += dt
            self.effects.on_update(dt)
            self.end_timer -= dt
            if self.end_timer <= 0:
                s = self.session
                if self.run:
                    p = self.progress
                    self.run.cmd_level, self.run.cmd_xp, self.run.cmd_perks = p.level, p.xp, list(p.perks)
                    if self.result == "win":
                        reward = self.run.complete_node(core_hp=s.core_hp, kills=s.kills, score=s.score)
                        self.game.scenes.change("run_reward", reward=reward)
                    else:
                        self.run.fail(kills=s.kills, score=s.score)
                        self.game.scenes.change("run_end")
                    return
                end_kwargs = dict(launch=self.launch, level_id=self.level_id,
                                  difficulty=self.difficulty, mode=self.mode, daily=self.daily,
                                  stars=s.stars(), score=s.final_score(),
                                  kills=s.kills, core=s.core_ratio, waves=self.waves.wave_number,
                                  new_best=self.new_best, custom=self.end_summary())
                if self.story is not None and self.result == "win":
                    self.game.scenes.change("story", level_id=self.level_id, phase="debrief",
                                            then=(self.result, end_kwargs))
                else:
                    self.game.scenes.change(self.result, **end_kwargs)
            return
        # Game speed: run the fixed step several times, so physics stays identical at 2x/3x.
        for _ in range(self.speed):
            self.step(dt)
            if self.result:
                break

    def on_tower_broken(self, tower):
        self.juice.tower_broken(tower)
        if self.waves.phase == "wave":
            self.economy.note_broken(tower)

    def step(self, dt):
        self.juice.update(dt)
        if self.reverse is not None:
            self.reverse.update(dt)
        self.meta.update(dt)
        self.wild.update(dt)
        self.features.update(dt)
        if self.game._music is not None:
            alive = self.enemies.alive_count
            boss = any(e.is_boss for e in self.enemies.enemies)
            threat = 0.0 if self.waves.phase != "wave" else min(1.0, 0.25 + alive / 40 + (0.5 if boss else 0))
            self.game._music.set_threat(threat, dt, self.audio.music_volume)
        if self.tutorial:
            self.tutorial.update(self, dt)
        dt *= self.juice.time_scale
        self.t += dt
        self.player.kit.level = self.progress.level
        self.core_flash = max(0.0, self.core_flash - dt)
        self.effects.on_update(dt)
        self.core.on_update(dt)
        self.collision.rebuild(self.enemies.enemies)
        self.player.on_update(dt)
        self.towers.on_update(dt)
        self.enemies.on_update(dt)
        self.collision.rebuild(self.enemies.enemies)
        self.projectiles.on_update(dt)
        self.items.on_update(dt, self.player.commander, self.waves, self.player.partner)
        self.waves.on_update(dt, self.enemies.alive_count)
        self.level.on_update(dt, self.waves)
        wave_active = self.waves.phase == "wave"
        self.vents.on_update(dt, wave_active)
        if self.weather:
            self.weather.on_update(dt, wave_active)

    # ---- render ------------------------------------------------------------------------
    def render_core(self, screen, offset):
        for cx, cy in self.level.core_positions:
            x, y = cx + offset[0], cy + offset[1]
            r = 30 + 3 * math.sin(self.t * 3)
            glow = pygame.Surface((90, 90), pygame.SRCALPHA)
            color = S.RED if self.core_flash > 0 else S.CYAN
            pygame.draw.circle(glow, (*color, 60), (45, 45), int(r))
            screen.blit(glow, (x - 45, y - 45))
            self.assets.blit_centered(screen, "core", (x, y), tint="white" if self.core_flash > 0.2 else None)

    def render_darkness(self, screen, offset):
        """Derelict Ship: everything outside tower, Vance and Core light is pitch black."""
        if not self.level.dark:
            return
        shade = pygame.Surface((S.MAP_W, S.MAP_H), pygame.SRCALPHA)
        shade.fill((4, 5, 14, 225))
        lights = self.enemies.light_sources()
        for x, y, r in lights:   # soft edge first, then the clear centre
            pygame.draw.circle(shade, (4, 5, 14, 120), (int(x), int(y)), int(r + 18))
        for x, y, r in lights:
            pygame.draw.circle(shade, (0, 0, 0, 0), (int(x), int(y)), int(r))
        screen.blit(shade, offset)

    def on_render(self, screen):
        offset = self.effects.offset
        mouse = self.input.mouse_pos()
        screen.fill(S.SPACE)
        self.level.on_render(screen, offset)
        self.juice.render_splats(screen, offset)
        self.features.render_ground(screen, offset)
        self.wild.render(screen, self.assets, offset)
        self.vents.on_render(screen, offset)
        self.render_core(screen, offset)
        self.core.on_render(screen, offset)
        self.items.on_render(screen, offset)
        self.towers.on_render(screen, self.assets, offset)
        self.enemies.on_render(screen, self.assets, offset)
        self.towers.render_overlays(screen, offset)
        self.player.on_render(screen, self.assets, offset)
        self.projectiles.on_render(screen, offset)
        self.render_darkness(screen, offset)
        self.features.render_night(screen, offset)
        self.effects.on_render(screen, offset)
        if self.weather:
            self.weather.on_render(screen, offset)
        self.towers.render_preview(screen, self.assets, mouse)
        self.player.render_aim(screen, mouse)
        if self.debug:
            self.ui.render_debug(screen, self, self.game.clock.get_fps())
        self.effects.render_flash(screen)
        self.ui.render_hud(screen, self, mouse)
        if self.reverse is not None:   # Reverse mode: the hive's panel replaces the HUD
            self.reverse.render(screen, self.assets, mouse)
        else:
            self.ui.render_wave_preview(screen, self, self.game.settings.get("timeline", True))
        self.ui.render_report(screen, self, mouse)
        self.ui.render_branch_menu(screen, self, mouse)
        self.ui.render_perk_menu(screen, self, mouse)
        boss = next((e for e in self.enemies.enemies if e.is_boss and e.targetable), None)
        self.ui.render_overlays(screen, mouse, boss)
        self.juice.render_overlay(screen, self.assets)
        if self.tutorial:
            self.tutorial.render(screen, self.assets)
        extra = self.features.status()
        if self.wild.living:
            extra = (extra + "  " + self.wild.describe()).strip()
        if self.hardcore:
            extra = "HARDCORE  " + extra
        if self.coop:
            p2 = self.player.partner
            state = f"{int(p2.health.hp)} HP" if p2.alive else (
                "OUT" if p2.respawn_timer > 1e8 else f"back in {p2.respawn_timer:.0f}s")
            extra = f"P2 {state}  " + extra
        if self.reverse is None:
            self.player.kit.render_status(screen, self.assets, extra)
        if self.sandbox_menu:
            from ..systems.modes import render_sandbox
            render_sandbox(screen, self, mouse)
        self.ui.render_tower_actions(screen, self, mouse)
        self.ui.render_picker(screen, self, mouse)
        self.ui.render_tooltip(screen, self, mouse)

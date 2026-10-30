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
from ..systems.endless import EndlessWaveGenerator
from ..systems.environment import WEATHER, VentSystem, WeatherSystem
from ..systems.progression import CommanderProgress, CoreUpgrades, apply_perk
from ..systems.run import Modifiers
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
                 daily=None, seed=None, **kwargs):
        super().__init__(game, **kwargs)
        # Everything needed to restart this exact sector (Retry / Restart).
        self.launch = dict(level_id=level_id, difficulty=difficulty, mode=mode, daily=daily, seed=seed)
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
        cls_effects = data["commanders"].get(self.commander_class, {}).get("effects", [])
        mods = Modifiers((self.run.effects if self.run else []) + cls_effects)
        owned = self.run.towers if self.run else list(data["towers"])
        tower_data = mods.tower_data(data["towers"], owned)
        items_data = mods.items_data(data["items"])
        self.kill_mult = mods.mult("kill_reward")
        self.interest = mods.interest()
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
        self.enemies.towers = self.towers
        self.items = ItemManager(ev, items_data, self.assets)
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
        generator = None
        if self.endless:
            generator = EndlessWaveGenerator(data["endless"], data["enemies"],
                                             lanes=self.level.lane_count, seed=seed)
        waves = lvl["waves"]
        if self.run:
            waves = self.run.node_waves(self.run.node, data["endless"], data["enemies"],
                                        lanes=self.level.lane_count)
        self.waves = WaveSystem(ev, waves, lvl.get("build_time", S.BUILD_PHASE_TIME),
                                generator=generator)
        self.ui = UISystem(self.assets, tower_data)
        self.core = CoreUpgrades(self)
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
                     lambda **_: self.ui.toast("Commander Vance is back online", S.CYAN))

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
        self.ui.show_banner(self.level.name, sub, 2.5)
        self.ui.toast("Build towers, then press Space to start the wave", S.ENERGY)
        if self.weather:
            info = self.weather.info
            self.ui.toast(f"Weather: {info['name']} - {info['desc']}", info["color"])
        if self.vents.vents:
            self.ui.toast("Volcanic vents erupt during waves - don't build too close", S.ORANGE)
        self.audio.play_music()

    def on_exit(self):
        self.events.clear()

    def finish(self, result):
        if self.result:
            return
        self.result = result
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

    # ---- event handlers -------------------------------------------------------------
    @property
    def record_key(self):
        """Endless best-wave key: every generated map shares one 'procedural' record."""
        return "procedural" if self.level_id.startswith("proc_") else self.level_id

    def on_enemy_killed(self, enemy, **_):
        reward = max(1, round(enemy.reward * self.kill_mult)) + self.kill_bonus
        if self.progress.add_xp(max(1, enemy.score // 10)):
            c = self.player.commander
            self.effects.ring(c.pos.x, c.pos.y, 30, S.CYAN, 0.6, width=3)
            self.ui.toast(f"Vance reached level {self.progress.level}! Pick a perk", S.CYAN)
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
        damage = self.core.absorb(enemy.core_damage)
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
        rate, cap = self.interest
        if rate and not self.result:
            gain = min(cap, int(self.session.energy * rate))
            if gain > 0:
                self.session.energy += gain
                self.ui.toast(f"Energy Bonds: +{gain} Energy", S.ENERGY)
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

    def on_commander_downed(self, **_):
        self.ui.toast("Commander down! Respawning at the Core...", S.RED)
        self.audio.play("downed")

    # ---- input -------------------------------------------------------------------------
    def handle_command(self, cmd):
        n = cmd.name
        if n == "pause":
            self.game.scenes.push("pause")
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
        elif n == "select_tower":
            self.player.aiming_orbital = False
            self.ui.core_selected = False
            self.towers.select_build(cmd.value)
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

    def on_left_click(self, pos):
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
                self.game.scenes.change(self.result, launch=self.launch, level_id=self.level_id,
                                        difficulty=self.difficulty, mode=self.mode, daily=self.daily,
                                        stars=s.stars(), score=s.final_score(),
                                        kills=s.kills, core=s.core_ratio, waves=self.waves.wave_number,
                                        new_best=self.new_best)
            return
        # Game speed: run the fixed step several times, so physics stays identical at 2x/3x.
        for _ in range(self.speed):
            self.step(dt)
            if self.result:
                break

    def step(self, dt):
        self.t += dt
        self.core_flash = max(0.0, self.core_flash - dt)
        self.effects.on_update(dt)
        self.core.on_update(dt)
        self.collision.rebuild(self.enemies.enemies)
        self.player.on_update(dt)
        self.towers.on_update(dt)
        self.enemies.on_update(dt)
        self.collision.rebuild(self.enemies.enemies)
        self.projectiles.on_update(dt)
        self.items.on_update(dt, self.player.commander, self.waves)
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
        self.vents.on_render(screen, offset)
        self.render_core(screen, offset)
        self.core.on_render(screen, offset)
        self.items.on_render(screen, offset)
        self.towers.on_render(screen, self.assets, offset)
        self.enemies.on_render(screen, self.assets, offset)
        self.player.on_render(screen, self.assets, offset)
        self.projectiles.on_render(screen, offset)
        self.render_darkness(screen, offset)
        self.effects.on_render(screen, offset)
        if self.weather:
            self.weather.on_render(screen, offset)
        self.towers.render_preview(screen, self.assets, mouse)
        self.player.render_aim(screen, mouse)
        if self.debug:
            self.ui.render_debug(screen, self, self.game.clock.get_fps())
        self.effects.render_flash(screen)
        self.ui.render_hud(screen, self, mouse)
        self.ui.render_wave_preview(screen, self)
        self.ui.render_branch_menu(screen, self, mouse)
        self.ui.render_perk_menu(screen, self, mouse)
        boss = next((e for e in self.enemies.enemies if e.is_boss and e.targetable), None)
        self.ui.render_overlays(screen, mouse, boss)

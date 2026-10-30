"""PlayScene: one run of one sector. Creates and wires every gameplay system.

Systems talk through this scene's EventBus:
    enemy_killed       -> +Energy, score, goo particles, loot drop
    enemy_reached_core -> Core damage, screen shake, red flash
    item_collected     -> apply the item's effect
    wave_started / wave_cleared / all_waves_cleared -> banners, win check
"""
import math
from dataclasses import dataclass

import pygame

from .. import settings as S
from ..core import EventBus
from ..entities.item import ItemManager
from ..systems.collision_system import CollisionSystem
from ..systems.effects_system import EffectsSystem
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

    def __init__(self, game, level_id="sector1", difficulty=S.DEFAULT_DIFFICULTY, **kwargs):
        super().__init__(game, **kwargs)
        data = game.data
        self.level_id = level_id
        self.difficulty = difficulty
        self.events = ev = EventBus()
        self.level = LevelSystem(ev, level_id)
        lvl = self.level.data
        self.session = Session(level_id, difficulty,
                               energy=lvl.get("start_energy", S.START_ENERGY),
                               core_hp=lvl.get("core_hp", 100), core_max=lvl.get("core_hp", 100))
        self.effects = EffectsSystem(self.assets)
        self.collision = CollisionSystem()
        self.enemies = EnemySystem(ev, self.level, data["enemies"], difficulty, self.audio,
                                   self.effects, self.assets)
        self.projectiles = ProjectileSystem(ev, self.collision, self.enemies, self.effects, self.audio)
        self.towers = TowerSystem(ev, self.level, data["towers"], self.session, self.collision,
                                  self.projectiles, self.enemies, self.effects, self.audio)
        self.player = PlayerSystem(ev, self.level, self.input, self.collision, self.projectiles,
                                   self.enemies, self.towers, self.effects, self.audio)
        self.enemies.commander = self.player.commander
        self.towers.commander = self.player.commander
        self.enemies.towers = self.towers
        self.items = ItemManager(ev, data["items"], self.assets)
        self.waves = WaveSystem(ev, lvl["waves"], lvl.get("build_time", S.BUILD_PHASE_TIME))
        self.ui = UISystem(self.assets, data["towers"])
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

    # ---- lifecycle -------------------------------------------------------------
    def on_start(self):
        self.ui.show_banner(self.level.name, f"{self.difficulty}  -  {self.waves.total_waves} waves", 2.5)
        self.ui.toast("Build towers, then press Space to start the wave", S.ENERGY)
        self.audio.play_music()

    def on_exit(self):
        self.events.clear()

    def finish(self, result):
        if self.result:
            return
        self.result = result
        self.end_timer = self.END_DELAY
        if result == "win":
            self.ui.show_banner("SECTOR SECURED", f"{self.session.stars()} stars", self.END_DELAY)
            self.game.record_result(self.level_id, self.session.stars(), self.session.final_score())
        else:
            self.ui.show_banner("CORE DESTROYED", "The shield has fallen...", self.END_DELAY)
            self.effects.flash(S.RED, 0.6)

    # ---- event handlers -------------------------------------------------------------
    def on_enemy_killed(self, enemy, **_):
        self.session.energy += enemy.reward
        self.session.score += enemy.score
        self.session.kills += 1
        self.effects.goo(enemy.pos.x, enemy.pos.y)
        self.effects.floating_text(enemy.pos.x, enemy.pos.y - 14, f"+{enemy.reward}", S.ENERGY, 18)
        self.audio.play("hit")

    def on_enemy_reached_core(self, enemy, **_):
        if self.result:
            return
        self.session.core_hp = max(0, self.session.core_hp - enemy.core_damage)
        self.core_flash = 0.3
        self.effects.shake(0.25 + 0.04 * enemy.core_damage)
        self.effects.flash(S.RED, 0.2)
        cx, cy = self.level.core_pos
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

    def on_wave_started(self, number, total, **_):
        sub = "Final wave!" if number == total else ""
        self.ui.show_banner(f"WAVE {number}", sub, 1.6)
        self.audio.play("wave")

    def on_wave_cleared(self, number, **_):
        if number < self.waves.total_waves:
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
        self.ui.show_banner("HIVE OVERSEER", "The brood-mother has arrived", 2.5)
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
        elif n == "start_wave":
            self.waves.start_next_wave()
        elif n == "select_tower":
            self.player.aiming_orbital = False
            self.towers.select_build(cmd.value)
        elif n == "orbital_strike":
            self.player.begin_orbital()
        elif n == "upgrade":
            self.towers.upgrade()
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
        tx, ty = self.level.world_to_tile(*pos)
        existing = self.towers.tower_at(tx, ty)
        if self.towers.build_kind and existing is None:
            if self.towers.try_place(tx, ty) and not self.input.shift_held():
                self.towers.cancel_build()   # hold Shift to keep placing
        else:
            self.towers.select(self.towers.tower_at(tx, ty))

    def on_right_click(self, pos):
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
            self.towers.upgrade(tower)
        else:
            self.towers.select(None)

    # ---- update ------------------------------------------------------------------------
    def on_update(self, dt):
        self.t += dt
        self.core_flash = max(0.0, self.core_flash - dt)
        self.effects.on_update(dt)
        self.ui.on_update(dt)
        if self.result:
            self.end_timer -= dt
            if self.end_timer <= 0:
                s = self.session
                self.game.scenes.change(self.result, level_id=self.level_id, difficulty=self.difficulty,
                                        stars=s.stars(), score=s.final_score(), kills=s.kills,
                                        core=s.core_ratio, waves=self.waves.wave_number)
            return
        self.collision.rebuild(self.enemies.enemies)
        self.player.on_update(dt)
        self.towers.on_update(dt)
        self.enemies.on_update(dt)
        self.collision.rebuild(self.enemies.enemies)
        self.projectiles.on_update(dt)
        self.items.on_update(dt, self.player.commander, self.waves)
        self.waves.on_update(dt, self.enemies.alive_count)
        self.level.on_update(dt, self.waves)

    # ---- render ------------------------------------------------------------------------
    def render_core(self, screen, offset):
        cx, cy = self.level.core_pos
        x, y = cx + offset[0], cy + offset[1]
        r = 30 + 3 * math.sin(self.t * 3)
        glow = pygame.Surface((90, 90), pygame.SRCALPHA)
        color = S.RED if self.core_flash > 0 else S.CYAN
        pygame.draw.circle(glow, (*color, 60), (45, 45), int(r))
        screen.blit(glow, (x - 45, y - 45))
        self.assets.blit_centered(screen, "core", (x, y), tint="white" if self.core_flash > 0.2 else None)

    def on_render(self, screen):
        offset = self.effects.offset
        mouse = self.input.mouse_pos()
        screen.fill(S.SPACE)
        self.level.on_render(screen, offset)
        self.render_core(screen, offset)
        self.items.on_render(screen, offset)
        self.towers.on_render(screen, self.assets, offset)
        self.enemies.on_render(screen, self.assets, offset)
        self.player.on_render(screen, self.assets, offset)
        self.projectiles.on_render(screen, offset)
        self.effects.on_render(screen, offset)
        self.towers.render_preview(screen, self.assets, mouse)
        self.player.render_aim(screen, mouse)
        if self.debug:
            self.ui.render_debug(screen, self, self.game.clock.get_fps())
        self.effects.render_flash(screen)
        self.ui.render_hud(screen, self, mouse)
        boss = next((e for e in self.enemies.enemies if e.is_boss and e.targetable), None)
        self.ui.render_overlays(screen, mouse, boss)

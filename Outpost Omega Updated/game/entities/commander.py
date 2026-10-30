"""Commander Rhea Vance: the playable hero unit.

StateMachine: Idle, Move, Shoot, Repair, Downed.
Physics: Vector2 velocity with acceleration, max speed and friction (lower
on ice), axis-separated AABB collision against rocks, towers and the Core.
"""
import math
import random

import pygame

from .. import settings as S
from ..core import Cooldown, Health, State, StateMachine

Vec = pygame.math.Vector2


class _ActiveState(State):
    """Shared logic for Idle / Move / Shoot: move, maybe shoot, pick next state."""

    def update(self, c, dt):
        c.apply_physics(dt, c.move_input)
        if c.repair_input and c.find_repair_target():
            return "repair"
        fired = c.try_fire_blaster()
        if fired or c.blaster.remaining > c.blaster.duration * 0.5:
            nxt = "shoot"
        elif c.vel.length_squared() > 100:
            nxt = "move"
        else:
            nxt = "idle"
        return nxt if nxt != self.name else None


class Idle(_ActiveState):
    pass


class Move(_ActiveState):
    pass


class Shoot(_ActiveState):
    pass


class Repair(State):
    def update(self, c, dt):
        c.apply_physics(dt, (0, 0))      # stand still while repairing
        t = c.repair_target
        if (not c.repair_input or t is None or t.health.ratio >= 1
                or c.pos.distance_squared_to((t.x, t.y)) > S.REPAIR_RANGE ** 2):
            c.repair_target = None
            return "idle"
        t.health.heal(t.health.max_hp / S.REPAIR_TIME * dt)
        return None


class Downed(State):
    def enter(self, c):
        c.vel.update(0, 0)
        c.respawn_timer = S.CMD_RESPAWN
        c.system.events.publish("commander_downed", commander=c)

    def update(self, c, dt):
        c.respawn_timer -= dt
        if c.respawn_timer <= 0:
            c.respawn()
            return "idle"
        return None


class Commander(pygame.sprite.Sprite):
    def __init__(self, system, spawn_pos):
        super().__init__()
        self.system = system
        self.spawn = Vec(spawn_pos)
        self.pos = Vec(spawn_pos)
        self.vel = Vec()
        self.radius = 11
        self.half = S.CMD_SIZE / 2
        self.health = Health(S.CMD_MAX_HP)
        self.blaster = Cooldown(1.0 / S.BLASTER_RATE)
        self.respawn_timer = 0.0
        self.hurt_timer = 0.0
        self.facing_left = False
        self.anim_t = 0.0
        self.aim_angle = 0.0
        self.repair_target = None
        self.move_input = (0.0, 0.0)
        self.repair_input = False
        self.fsm = StateMachine(self, {
            "idle": Idle(), "move": Move(), "shoot": Shoot(),
            "repair": Repair(), "downed": Downed(),
        }, "idle")

    @property
    def alive(self):
        return self.fsm.name != "downed"

    @property
    def state(self):
        return self.fsm.name

    # ---- actions -------------------------------------------------------------
    def take_damage(self, amount):
        if not self.alive or amount <= 0:
            return
        self.health.damage(amount, ignore_armor=True)
        self.hurt_timer = 0.15
        if self.health.is_dead:
            self.fsm.change("downed")

    def respawn(self):
        self.pos.update(self.spawn)
        self.vel.update(0, 0)
        self.health.reset()
        self.system.events.publish("commander_respawned", commander=self)

    def find_repair_target(self):
        tower = self.system.towers.nearest_damaged_tower(self.pos.x, self.pos.y, S.REPAIR_RANGE)
        self.repair_target = tower
        return tower

    def try_fire_blaster(self):
        if not self.blaster.ready:
            return False
        target = self.system.collision.nearest_enemy(self.pos.x, self.pos.y, S.BLASTER_RANGE)
        if target is None:
            return False
        self.blaster.trigger()
        aim = self.system.projectiles.fire_at(
            self.pos.x, self.pos.y, target, S.BLASTER_SPEED, S.BLASTER_DAMAGE,
            color=S.CYAN, hits_air=True, radius=2)
        self.aim_angle = math.atan2(aim[1] - self.pos.y, aim[0] - self.pos.x)
        self.facing_left = math.cos(self.aim_angle) < 0
        self.system.audio.play("blaster")
        return True

    # ---- physics -------------------------------------------------------------
    def apply_physics(self, dt, move):
        level = self.system.level
        tile = level.world_to_tile(self.pos.x, self.pos.y)
        friction = S.CMD_ICE_FRICTION if level.is_ice(*tile) else S.CMD_FRICTION
        accel = Vec(move) * S.CMD_ACCEL
        self.vel += accel * dt
        # Friction: exponential decay, frame-rate independent.
        self.vel *= math.exp(-friction * dt)
        if self.vel.length_squared() > S.CMD_MAX_SPEED ** 2:
            self.vel.scale_to_length(S.CMD_MAX_SPEED)
        if self.vel.length_squared() < 4 and not any(move):
            self.vel.update(0, 0)
        nx, ny, hit_x, hit_y = self.system.collision.move_box(
            self.pos.x, self.pos.y, self.half, self.vel.x * dt, self.vel.y * dt, level.is_solid)
        self.pos.update(nx, ny)
        if hit_x:
            self.vel.x = 0
        if hit_y:
            self.vel.y = 0
        if move[0]:
            self.facing_left = move[0] < 0
        if self.vel.length_squared() > 100:
            self.anim_t += dt * 8
        if level.is_hazard(*tile):
            self.take_damage(12 * dt)

    # ---- per frame -----------------------------------------------------------
    def update(self, dt, move=(0, 0), repair_held=False):
        self.move_input = move
        self.repair_input = repair_held
        self.blaster.update(dt)
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.fsm.update(dt)

    def render(self, screen, assets, offset):
        x, y = self.pos.x + offset[0], self.pos.y + offset[1]
        if not self.alive:
            assets.blit_centered(screen, "commander_down", (x, y))
            t = max(0.0, self.respawn_timer)
            label = assets.text(f"{t:.1f}s", 18, S.WHITE)
            screen.blit(label, label.get_rect(center=(x, y - 20)))
            return
        pygame.draw.ellipse(screen, (90, 70, 50), (x - 10, y + 10, 20, 7))
        frame = f"commander_{int(self.anim_t) % 2}"
        tint = "white" if self.hurt_timer > 0 else None
        assets.blit_centered(screen, frame, (x, y), flip=self.facing_left, tint=tint)
        if self.fsm.name == "shoot":
            mx = x + math.cos(self.aim_angle) * 14
            my = y + math.sin(self.aim_angle) * 14
            pygame.draw.circle(screen, S.CYAN, (int(mx), int(my)), 3)
        if self.fsm.name == "repair" and self.repair_target:
            t = self.repair_target
            pts = []
            for i in range(7):
                f = i / 6
                px = x + (t.x + offset[0] - x) * f + random.uniform(-3, 3)
                py = y + (t.y + offset[1] - y) * f + random.uniform(-3, 3)
                pts.append((px, py))
            pygame.draw.lines(screen, S.GREEN, False, pts, 2)
        # HP bar
        pygame.draw.rect(screen, (30, 0, 0), (x - 14, y - 22, 28, 4))
        pygame.draw.rect(screen, S.CYAN, (x - 14, y - 22, int(28 * self.health.ratio), 4))

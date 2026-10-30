"""Enemies: Enemy base class + one subclass per alien type.

Stats come from data/enemies.json. Every enemy runs a StateMachine:
    Walk -> Attack (Commander in the way) -> Stunned -> Dying
Subclasses add their own states through build_states() / special_action():
the Saboteur adds "emp", the Hive Overseer adds "shielded".
Ground enemies follow the level's waypoints with a PathFollower. Gliders
use a seek steering behavior straight at the Core instead.
"""
import math
import random

import pygame

from .. import settings as S
from ..core import Health, PathFollower, State, StateMachine, Timer
from ..core.spatial_hash import circles_overlap


def _segment_hits_circle(x1, y1, x2, y2, cx, cy, r):
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy or 1.0
    t = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / length_sq))
    px, py = x1 + dx * t, y1 + dy * t
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


# ---- states ---------------------------------------------------------------
class Walk(State):
    def update(self, e, dt):
        if e.stun_timer > 0:
            return "stunned"
        if e.can_attack_commander():
            return "attack"
        special = e.special_action(dt)
        if special:
            return special
        e.move(dt)
        if e.at_core():
            e.system.enemy_reached_core(e)
        return None


class Attack(State):
    """Stop and hit the Commander while she blocks the route."""

    def update(self, e, dt):
        if e.stun_timer > 0:
            return "stunned"
        if not e.can_attack_commander():
            return "walk"
        e.vel.update(0, 0)
        e.system.commander.take_damage(e.attack_dps * dt)
        return None


class Stunned(State):
    def update(self, e, dt):
        e.vel.update(0, 0)
        if e.stun_timer <= 0:
            return "walk"
        return None


class Dying(State):
    DURATION = 0.25

    def enter(self, e):
        e.vel.update(0, 0)

    def update(self, e, dt):
        if e.fsm.time_in_state >= self.DURATION:
            e.remove = True
        return None


# ---- base class -----------------------------------------------------------
class Enemy(pygame.sprite.Sprite):
    sprite = "skitter"
    frame_count = 2
    anim_fps = 8
    is_boss = False

    def __init__(self, kind, stats, system, hp_mult=1.0, speed_mult=1.0,
                 reward_mult=1.0, start_distance=0.0, route=None, lane=0):
        super().__init__()
        self.kind = kind
        self.stats = stats
        self.system = system
        self.health = Health(stats["hp"] * hp_mult, stats.get("armor", 0))
        self.base_speed = stats["speed"] * speed_mult * random.uniform(0.95, 1.05)
        self.radius = stats.get("radius", 10)
        self.reward = max(1, round(stats.get("reward", 1) * reward_mult))
        self.score = stats.get("score", 0)
        self.core_damage = stats.get("core_damage", 1)
        self.flying = stats.get("flying", False)
        self.attack_dps = stats.get("attack_dps", 0)

        self.lane = lane
        self.follower = PathFollower(route or system.level.route_for(lane), start_distance)
        self.pos = pygame.math.Vector2(self.follower.pos)
        self.vel = pygame.math.Vector2()
        # Status effects stored as timers
        self.slow = 0.0
        self.slow_timer = 0.0
        self.stun_timer = 0.0
        self.burn_dps = 0.0
        self.burn_timer = 0.0
        self.flash_timer = 0.0
        self.anim_t = random.random()
        self.facing_left = False
        self.remove = False
        self.reached_core = False
        self.invulnerable = False
        self.wave = 1
        self.fsm = StateMachine(self, self.build_states(), "walk")

    def build_states(self):
        """Subclasses extend this dict to add their own states."""
        return {"walk": Walk(), "attack": Attack(), "stunned": Stunned(), "dying": Dying()}

    def special_action(self, dt):
        """Checked every Walk update; return a state name to switch to it."""
        return None

    # ---- queries ---------------------------------------------------------
    @property
    def targetable(self):
        return not self.remove and not self.reached_core and self.fsm.name != "dying"

    @property
    def speed(self):
        return self.base_speed * (1.0 - self.slow)

    @property
    def progress(self):
        """Higher = closer to the Core (minus the distance still to walk).
        Towers use it for first/last targeting; it stays correct when an
        enemy is rerouted or two lanes merge."""
        return -(self.follower.total_length - self.follower.distance)

    def reroute(self, waypoints):
        """Hive walls moved: follow a fresh route from where we stand now."""
        if waypoints and len(waypoints) > 1:
            self.follower = PathFollower(waypoints)
            self.pos.update(self.follower.pos)

    def at_core(self):
        return self.follower.finished

    def can_attack_commander(self):
        cmd = self.system.commander
        if self.flying or self.attack_dps <= 0 or cmd is None or not cmd.alive:
            return False
        reach = self.radius + cmd.radius + 4
        return self.pos.distance_squared_to(cmd.pos) < reach * reach

    # ---- hit tests (narrow phase) ------------------------------------------------
    def hit_test_circle(self, x, y, r):
        """Does a circle (bullet, blast) touch this enemy? Circle-vs-circle."""
        return circles_overlap(x, y, r, self.pos.x, self.pos.y, self.radius)

    def hit_test_segment(self, x1, y1, x2, y2, pad=4):
        """Does a line (railgun beam) touch this enemy? Closest point on the
        segment to our center, compared against our radius."""
        return _segment_hits_circle(x1, y1, x2, y2, self.pos.x, self.pos.y, self.radius + pad)

    def future_position(self, t):
        """Where this enemy will be in t seconds (used for lead targeting)."""
        if self.fsm.name != "walk":
            return (self.pos.x, self.pos.y)
        return self.follower.position_ahead(self.speed * t)

    # ---- status effects ----------------------------------------------------
    def apply_slow(self, amount, duration):
        self.slow = max(self.slow, amount)
        self.slow_timer = max(self.slow_timer, duration)

    def apply_stun(self, duration):
        self.stun_timer = max(self.stun_timer, duration)

    def apply_burn(self, dps, duration):
        self.burn_dps = max(self.burn_dps, dps)
        self.burn_timer = max(self.burn_timer, duration)

    def knockback(self, amount, direction=None):
        """Small push back along the path (or away from a blast for flyers)."""
        if self.flying and direction is not None:
            self.pos += pygame.math.Vector2(direction) * amount
        else:
            back = max(0.0, self.follower.distance - amount)
            self.follower = PathFollower(self.follower.waypoints, back)
            self.pos.update(self.follower.pos)

    def update_status(self, dt):
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.stun_timer = max(0.0, self.stun_timer - dt)
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow = 0.0
        if self.burn_timer > 0:
            self.burn_timer -= dt
            self.system.damage(self, self.burn_dps * dt, ignore_armor=True, quiet=True)

    # ---- movement ----------------------------------------------------------
    def move(self, dt):
        self.follower.advance(self.speed * dt)
        new = pygame.math.Vector2(self.follower.pos)
        self.vel = (new - self.pos) / dt if dt else pygame.math.Vector2()
        self.pos = new
        if abs(self.vel.x) > 1:
            self.facing_left = self.vel.x < 0

    def update(self, dt):
        if self.fsm.name != "dying":
            self.update_status(dt)
        moving = self.vel.length_squared() > 1
        if moving:
            self.anim_t += dt * self.anim_fps * (1 - self.slow)
        self.fsm.update(dt)

    # ---- drawing -----------------------------------------------------------
    def frame_name(self):
        return f"{self.sprite}_{int(self.anim_t) % self.frame_count}"

    def sprite_angle(self):
        return 0.0

    def render(self, screen, assets, offset):
        tint = None
        if self.flash_timer > 0:
            tint = "white"
        elif self.slow > 0:
            tint = "cryo"
        img = assets.get(self.frame_name(), angle=self.sprite_angle(),
                         flip=self.facing_left and not self.flying, tint=tint)
        if self.fsm.name == "dying":
            t = 1 - self.fsm.time_in_state / Dying.DURATION
            w, h = img.get_size()
            img = pygame.transform.scale(img, (max(1, int(w * t)), max(1, int(h * t))))
        x, y = self.pos.x + offset[0], self.pos.y + offset[1]
        if self.flying:  # shadow so flyers read as "in the air"
            pygame.draw.ellipse(screen, (60, 50, 40), (x - 8, y + 10, 16, 6))
            y -= 4 + math.sin(self.anim_t) * 2
        screen.blit(img, img.get_rect(center=(int(x), int(y))))
        if self.health.ratio < 1 and self.targetable:
            w = max(16, self.radius * 2)
            bx, by = int(x - w / 2), int(y - self.radius - 8)
            pygame.draw.rect(screen, (30, 0, 0), (bx, by, w, 4))
            pygame.draw.rect(screen, S.GREEN if self.health.ratio > 0.4 else S.RED,
                             (bx, by, int(w * self.health.ratio), 4))
        if self.stun_timer > 0:
            pygame.draw.circle(screen, S.ENERGY, (int(x), int(y - self.radius - 4)), 3)


# ---- subclasses -----------------------------------------------------------
class Skitter(Enemy):
    sprite = "skitter"
    anim_fps = 12


class Brute(Enemy):
    sprite = "brute"
    anim_fps = 4


class Glider(Enemy):
    """Flies straight at the Core with a seek steering behavior."""
    sprite = "glider"
    anim_fps = 6
    MAX_FORCE = 220.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lvl = self.system.level
        # Enter from the same map edge as this wave's lane, spread along it.
        sx, sy = self.follower.waypoints[0]
        if sx < 0 or sx > S.MAP_W:      # left/right edge -> spread vertically
            sx = -20 if sx < 0 else S.MAP_W + 20
            sy = min(S.MAP_H - 40, max(40, sy + random.uniform(-160, 160)))
        else:                            # top/bottom edge -> spread horizontally
            sy = -20 if sy < 0 else S.MAP_H + 20
            sx = min(S.MAP_W - 40, max(40, sx + random.uniform(-160, 160)))
        self.pos = pygame.math.Vector2(sx, sy)
        self.target = pygame.math.Vector2(lvl.core_pos)
        self.start_dist = max(1.0, self.pos.distance_to(self.target))
        self.vel = (self.target - self.pos).normalize() * self.base_speed

    @property
    def progress(self):
        return -self.pos.distance_to(self.target)

    def reroute(self, waypoints):
        pass   # flyers ignore the path

    def at_core(self):
        return self.pos.distance_squared_to(self.target) < 18 * 18

    def move(self, dt):
        # Seek: steer = desired_velocity - velocity, limited by MAX_FORCE.
        desired = self.target - self.pos
        if desired.length_squared() > 0:
            desired.scale_to_length(self.speed)
        steer = desired - self.vel
        if steer.length() > self.MAX_FORCE * dt:
            steer.scale_to_length(self.MAX_FORCE * dt)
        self.vel += steer
        self.pos += self.vel * dt

    def future_position(self, t):
        p = self.pos + self.vel * t
        return (p.x, p.y)

    def sprite_angle(self):
        # Sprite art faces down (+y); rotate it to face the velocity.
        if self.vel.length_squared() < 1:
            return 0.0
        return 90 - math.degrees(math.atan2(self.vel.y, self.vel.x))


class BroodSac(Enemy):
    """Bursts into Skitters on death (EnemySystem reads 'spawn_on_death')."""
    sprite = "brood_sac"
    frame_count = 1


class EmpCharge(State):
    """Saboteur stops next to a tower, charges for 1 s, then releases an EMP."""
    CHARGE = 1.0

    def enter(self, e):
        e.vel.update(0, 0)
        e.system.audio.play("emp")

    def update(self, e, dt):
        if e.stun_timer > 0:
            return "stunned"
        if e.fsm.time_in_state >= self.CHARGE:
            e.emp_burst()
            return "walk"
        return None


class Saboteur(Enemy):
    """Hunts towers: when one is within emp_range it stops and EMPs every
    tower in range (disabled for emp_duration s and damaged)."""
    sprite = "saboteur"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emp_cooldown = 0.5

    def build_states(self):
        states = super().build_states()
        states["emp"] = EmpCharge()
        return states

    def update(self, dt):
        self.emp_cooldown -= dt
        super().update(dt)

    def towers_in_range(self):
        towers = self.system.towers
        if towers is None:
            return []
        r2 = self.stats.get("emp_range", 70) ** 2
        return [t for t in towers.towers
                if self.pos.distance_squared_to((t.x, t.y)) <= r2 and t.fsm.name == "active"]

    def special_action(self, dt):
        if self.emp_cooldown <= 0 and self.towers_in_range():
            return "emp"
        return None

    def emp_burst(self):
        self.emp_cooldown = self.stats.get("emp_cooldown", 6.0)
        for t in self.towers_in_range():
            t.disable(self.stats.get("emp_duration", 3.0))
            t.health.damage(self.stats.get("emp_damage", 20), ignore_armor=True)
        fx = self.system.effects
        fx.ring(self.pos.x, self.pos.y, self.stats.get("emp_range", 70), S.CYAN, 0.4, width=3)
        fx.burst(self.pos.x, self.pos.y, S.CYAN, 16, 180, 0.3, 3)
        self.system.events.publish("tower_emp", enemy=self)

    def render(self, screen, assets, offset):
        super().render(screen, assets, offset)
        if self.fsm.name == "emp":
            t = self.fsm.time_in_state / EmpCharge.CHARGE
            r = int(6 + t * self.stats.get("emp_range", 70))
            pygame.draw.circle(screen, S.CYAN,
                               (int(self.pos.x + offset[0]), int(self.pos.y + offset[1])), r, 1)


class Shielded(State):
    """Boss phase: stops, raises an invulnerable shield and calls in Skitters."""
    DURATION = 4.0

    def enter(self, e):
        e.vel.update(0, 0)
        e.invulnerable = True
        e.summon()
        e.system.effects.ring(e.pos.x, e.pos.y, 60, S.MAGENTA, 0.5, width=4)
        e.system.audio.play("shield")
        e.system.events.publish("toast", text="The Overseer raises its shield!", color=S.MAGENTA)

    def exit(self, e):
        e.invulnerable = False

    def update(self, e, dt):
        if e.fsm.time_in_state >= self.DURATION:
            return "walk"
        return None


class HiveOverseer(Enemy):
    """Boss. Summons Skitters every summon_interval seconds and raises a shield
    at each HP threshold in shield_phases (e.g. 66% and 33%).

    Collision is pixel-perfect: shots are tested against a pygame.mask of
    the boss's current sprite frame, so its wide arms can be hit and the gaps
    between its legs can't. While shielded, the round bubble blocks shots.
    """
    sprite = "hive_overseer"
    frame_count = 1
    is_boss = True
    SHIELD_RADIUS = 50
    BEAM_THICKNESS = 3     # railgun beam half-width when testing against the mask

    # ---- pixel-perfect hit tests (pygame.mask) --------------------------------
    def mask_and_origin(self):
        """The mask of the frame we're drawing and its top-left in world space
        (matches how render() centers the sprite on our position)."""
        mask = self.system.assets.mask(self.frame_name(), flip=self.facing_left)
        w, h = mask.get_size()
        return mask, int(self.pos.x) - w // 2, int(self.pos.y) - h // 2

    def hit_test_circle(self, x, y, r):
        if self.invulnerable:
            return circles_overlap(x, y, r, self.pos.x, self.pos.y, self.SHIELD_RADIUS)
        mask, ox, oy = self.mask_and_origin()
        w, h = mask.get_size()
        if x + r < ox or x - r > ox + w or y + r < oy or y - r > oy + h:
            return False                      # quick bounding-box reject
        probe = self.system.assets.circle_mask(r)
        # overlap() takes the probe's top-left relative to the boss mask's top-left
        return mask.overlap(probe, (int(x - r) - ox, int(y - r) - oy)) is not None

    def hit_test_segment(self, x1, y1, x2, y2, pad=4):
        if self.invulnerable:
            return _segment_hits_circle(x1, y1, x2, y2, self.pos.x, self.pos.y, self.SHIELD_RADIUS)
        # Cheap reject first: the beam must pass within the sprite's bounding circle.
        mask, ox, oy = self.mask_and_origin()
        w, h = mask.get_size()
        if not _segment_hits_circle(x1, y1, x2, y2, self.pos.x, self.pos.y, math.hypot(w, h) / 2):
            return False
        # Walk along the beam in small steps, testing a thin circle against the mask.
        r = self.BEAM_THICKNESS
        probe = self.system.assets.circle_mask(r)
        steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / r))
        for i in range(steps + 1):
            t = i / steps
            px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            if ox - r <= px <= ox + w + r and oy - r <= py <= oy + h + r:
                if mask.overlap(probe, (int(px - r) - ox, int(py - r) - oy)) is not None:
                    return True
        return False

    def mask_outline(self):
        """World-space outline points of the mask (for the F1 debug overlay)."""
        mask, ox, oy = self.mask_and_origin()
        return [(ox + x, oy + y) for x, y in mask.outline()]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.summon_timer = Timer(self.stats.get("summon_interval", 8.0), repeat=True)
        self.phases = sorted(self.stats.get("shield_phases", []), reverse=True)

    def build_states(self):
        states = super().build_states()
        states["shielded"] = Shielded()
        return states

    def special_action(self, dt):
        if self.phases and self.health.ratio <= self.phases[0]:
            self.phases.pop(0)
            return "shielded"
        return None

    def summon(self):
        spec = self.stats.get("summon", {"enemy": "skitter", "count": 4})
        for i in range(spec["count"]):
            back = max(0.0, self.follower.distance - 24 - i * 14)
            self.system.spawn(spec["enemy"], self.wave, start_distance=back,
                              route=self.follower.waypoints)

    def update(self, dt):
        if self.targetable and self.fsm.name == "walk" and self.summon_timer.update(dt):
            self.summon()
        super().update(dt)

    def apply_stun(self, duration):
        pass   # bosses can't be stunned

    def knockback(self, amount, direction=None):
        pass   # ...or pushed around

    def render(self, screen, assets, offset):
        super().render(screen, assets, offset)
        if self.invulnerable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            bubble = pygame.Surface((110, 110), pygame.SRCALPHA)
            pygame.draw.circle(bubble, (*S.MAGENTA, 60), (55, 55), 50)
            pygame.draw.circle(bubble, (*S.MAGENTA, 200), (55, 55), 50, 3)
            screen.blit(bubble, (x - 55, y - 55))


ENEMY_CLASSES = {
    "skitter": Skitter,
    "brute": Brute,
    "glider": Glider,
    "brood_sac": BroodSac,
    "saboteur": Saboteur,
    "hive_overseer": HiveOverseer,
}

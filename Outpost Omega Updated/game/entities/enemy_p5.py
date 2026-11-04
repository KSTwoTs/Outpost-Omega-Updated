"""Phase 5 aliens and bosses.

Each one counters a strategy (see DESIGN.md). They plug into the same Enemy base
class as everything else; enemy.py registers them in ENEMY_CLASSES at import time.

Hooks used elsewhere:
    damage_type_mult(source)   Adaptive resistances (EnemySystem.damage)
    intercept_death()          Hive Mind bodies cheat death (EnemySystem.damage)
    reflects                   Reflector bounces projectiles (ProjectileSystem.on_hit)
    carrying                   Thief returns stolen Energy when killed (EnemySystem.kill)
    bar_ratio                  combined boss bar (UISystem.render_overlays)
"""
import math
import random

import pygame

from .. import settings as S
from ..core import PathFollower, Timer
from .enemy import Enemy, Glider, Spitter, BurrowWyrm, _BossBase

# Damage types for the Adaptive alien, by tower behavior.
DAMAGE_TYPES = {
    "kinetic": {"projectile", "pierce", "missile", "mortar", "flak", "drones", "mines", "shockwave",
                "barricade", "bait"},
    "energy": {"chain", "beam", "lightning", "fence", "ion", "hacker", "aura", "decoy"},
    "fire": {"cone", "tar"},
    "chem": {"acid", "magnet", "gravity"},
}
TYPE_OF = {b: t for t, bs in DAMAGE_TYPES.items() for b in bs}
TYPE_COLORS = {"kinetic": S.STEEL_LIGHT, "energy": S.CYAN, "fire": S.ORANGE, "chem": S.ACID}


def route_distance(route, x, y):
    """Distance along a waypoint route to the point closest to (x, y)."""
    best, best_d, walked = 0.0, None, 0.0
    for (x1, y1), (x2, y2) in zip(route, route[1:]):
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1.0
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (L * L)))
        px, py = x1 + dx * t, y1 + dy * t
        d = (px - x) ** 2 + (py - y) ** 2
        if best_d is None or d < best_d:
            best, best_d = walked + L * t, d
        walked += L
    return best


# ---- regular aliens ---------------------------------------------------------------------
class Adaptive(Enemy):
    """Builds resistance to whichever damage type hits it most (up to 60%)."""
    sprite = "adaptive"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.taken = {}   # damage type -> damage received

    def resist(self, kind):
        cap = self.stats.get("max_resist", 0.6)
        return min(cap, self.taken.get(kind, 0.0) / self.health.max_hp * self.stats.get("adapt", 0.8))

    def damage_type_mult(self, source):
        kind = TYPE_OF.get(getattr(source, "behavior", None))
        return 1.0 if kind is None else 1.0 - self.resist(kind)

    def note_damage(self, source, amount):
        kind = TYPE_OF.get(getattr(source, "behavior", None))
        if kind:
            self.taken[kind] = self.taken.get(kind, 0.0) + amount

    @property
    def top_type(self):
        return max(self.taken, key=self.taken.get) if self.taken else None

    def render(self, screen, assets, offset):
        super().render(screen, assets, offset)
        top = self.top_type
        if top and self.targetable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            frac = self.resist(top)
            pygame.draw.circle(screen, TYPE_COLORS[top], (x, y), int(self.radius + 3), 1 + int(frac * 4))


class Thief(Enemy):
    """Runs for the Core, grabs Energy instead of hurting it, and runs back to its spawn.
    Kill it on the way back to get the Energy (plus a bonus) back."""
    sprite = "thief"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.carrying = 0
        self.returning = False

    def at_core(self):
        if self.returning or not self.follower.finished:
            return False
        session = self.system.session
        take = min(self.stats.get("steal", 40), session.energy if session else 0)
        if session is not None:
            session.energy -= take
        self.carrying = take
        self.returning = True
        fx = self.system.effects
        fx.floating_text(self.pos.x, self.pos.y - 18, f"-{take} E STOLEN", S.RED, 20)
        fx.burst(self.pos.x, self.pos.y, S.ENERGY, 12, 120, 0.4, 3)
        self.system.events.publish("toast", text="A Thief stole Energy! Catch it!", color=S.RED)
        return False

    def move(self, dt):
        if not self.returning:
            super().move(dt)
            return
        self.follower = PathFollower(self.follower.waypoints,
                                     max(0.0, self.follower.distance - self.speed * dt))
        new = pygame.math.Vector2(self.follower.pos)
        if abs(new.x - self.pos.x) > 0.01:
            self.facing_left = new.x < self.pos.x
        self.vel = (new - self.pos) / dt if dt else pygame.math.Vector2()
        self.pos = new
        if self.follower.distance <= 0:
            self.remove = True
            self.system.events.publish("toast", text=f"The Thief escaped with {self.carrying} Energy",
                                       color=S.RED)

    @property
    def progress(self):
        if self.returning:   # towers should still chase it hard
            return 0.0
        return super().progress

    def render(self, screen, assets, offset):
        super().render(screen, assets, offset)
        if self.carrying and self.targetable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            assets.blit_centered(screen, "energy_crystal", (x + 8, y - 10))


class Leech(Enemy):
    """Latches onto a tower and drains it until Vance walks up and knocks it off."""
    sprite = "leech"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.latched = None
        self.latch_cooldown = 1.0

    def update(self, dt):
        if self.fsm.name == "dying" or not self.targetable:
            super().update(dt)
            return
        self.latch_cooldown -= dt
        towers = self.system.towers
        if self.latched is None and self.latch_cooldown <= 0 and towers is not None:
            r2 = self.stats.get("latch_range", 60) ** 2
            near = [t for t in towers.towers if not t.health.is_dead and not t.walkable
                    and self.pos.distance_squared_to((t.x, t.y)) <= r2]
            if near:
                self.latched = min(near, key=lambda t: self.pos.distance_squared_to((t.x, t.y)))
                self.system.effects.burst(self.pos.x, self.pos.y, S.RED, 8, 90, 0.3, 3)
        t = self.latched
        if t is not None:
            self.update_status(dt)
            if t.health.is_dead or t not in towers.towers or self.stun_timer > 0:
                self.unlatch()
            else:
                self.pos.update(t.x + 9, t.y - 9)
                self.vel.update(0, 0)
                t.health.damage(self.stats.get("drain_dps", 10) * dt, ignore_armor=True)
                self.health.heal(self.stats.get("drain_dps", 10) * dt * 0.5)
                cmd = self.system.commander
                if cmd is not None and cmd.alive and cmd.pos.distance_squared_to(self.pos) <= 46 * 46:
                    self.unlatch()
                    self.apply_stun(1.5)
                    self.system.damage(self, self.stats.get("knock_damage", 30), ignore_armor=True)
                    self.system.effects.floating_text(self.pos.x, self.pos.y - 18, "KNOCKED OFF", S.CYAN, 18)
                return
        super().update(dt)

    def unlatch(self):
        self.latched = None
        self.latch_cooldown = self.stats.get("relatch", 4.0)
        self.pos.update(self.follower.pos)

    def can_attack_commander(self):
        return self.latched is None and super().can_attack_commander()


class Phaser(Enemy):
    """Blinks a few tiles ahead along the path every few seconds."""
    sprite = "phaser"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.blink = Timer(self.stats.get("blink_interval", 3.0) * random.uniform(0.6, 1.0), repeat=True)

    def update(self, dt):
        if self.targetable and self.fsm.name == "walk" and self.blink.update(dt):
            before = (self.pos.x, self.pos.y)
            f = self.follower
            jump = min(self.stats.get("blink_dist", 96), max(0.0, f.total_length - f.distance - 40))
            if jump > 8:
                f.advance(jump)
                self.pos.update(f.pos)
                fx = self.system.effects
                fx.ring(before[0], before[1], 14, S.MAGENTA, 0.3, width=2)
                fx.ring(self.pos.x, self.pos.y, 18, S.MAGENTA, 0.3, width=2)
                fx.beam(before[0], before[1], self.pos.x, self.pos.y, (200, 120, 255), 0.12)
        super().update(dt)


class Reflector(Enemy):
    """Mirror-plated: bullets and missiles bounce back at whoever fired them.
    Beams, lightning, splash and fire get through."""
    sprite = "reflector"
    frame_count = 1
    reflects = True

    def render(self, screen, assets, offset):
        super().render(screen, assets, offset)
        if self.targetable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            a = self.anim_t * 2
            pygame.draw.arc(screen, S.WHITE, (x - 14, y - 14, 28, 28), a, a + 1.2, 2)


class SwarmMind(Enemy):
    """Gets tougher for every alien around it (damage reduction) and hurries them along."""
    sprite = "swarm_mind"
    frame_count = 1
    aura_source = True

    def apply_aura(self, enemies):
        r2 = self.stats.get("aura", 110) ** 2
        allies = 0
        for e in enemies:
            if e is not self and e.targetable and self.pos.distance_squared_to(e.pos) <= r2:
                allies += 1
                e.aura_speed = max(e.aura_speed, self.stats.get("speed_buff", 0.15))
        self.aura_dr = max(self.aura_dr, min(self.stats.get("max_dr", 0.6), allies * self.stats.get("dr_per", 0.06)))

    def render(self, screen, assets, offset):
        if self.targetable and self.aura_dr > 0:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            pygame.draw.circle(screen, (200, 90, 230), (x, y), int(self.radius + 4 + self.aura_dr * 10), 2)
        super().render(screen, assets, offset)


class NecroSpore(Enemy):
    """Raises aliens that died nearby a moment ago as weaker zombies."""
    sprite = "necro_spore"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raise_timer = Timer(self.stats.get("raise_interval", 4.0), repeat=True)

    def update(self, dt):
        if self.targetable and self.raise_timer.update(dt):
            sys = self.system
            r2 = self.stats.get("raise_range", 110) ** 2
            raised = 0
            for c in list(sys.corpses):
                if raised >= self.stats.get("raise_count", 2):
                    break
                if (c["x"] - self.pos.x) ** 2 + (c["y"] - self.pos.y) ** 2 <= r2:
                    sys.corpses.remove(c)
                    z = sys.spawn(c["kind"], c["wave"], start_distance=c["distance"], route=c["route"])
                    z.health.max_hp *= self.stats.get("zombie_hp", 0.4)
                    z.health.hp = z.health.max_hp
                    z.reward, z.score, z.zombie = 0, 0, True
                    sys.effects.lightning([(self.pos.x, self.pos.y), (z.pos.x, z.pos.y)], (170, 90, 220), 0.25)
                    sys.effects.burst(z.pos.x, z.pos.y, (170, 90, 220), 10, 90, 0.4, 3)
                    raised += 1
        super().update(dt)


class Infector(Enemy):
    """Corrupts a tower it passes: the tower shoots your own towers until it's fully repaired."""
    sprite = "infector"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cooldown = 1.5

    def update(self, dt):
        self.cooldown -= dt
        towers = self.system.towers
        if self.targetable and self.cooldown <= 0 and towers is not None:
            r2 = self.stats.get("infect_range", 50) ** 2
            near = [t for t in towers.towers if not t.health.is_dead and not getattr(t, "corrupted", False)
                    and not t.walkable and self.pos.distance_squared_to((t.x, t.y)) <= r2]
            if near:
                t = min(near, key=lambda t: self.pos.distance_squared_to((t.x, t.y)))
                t.corrupted = True
                t.health.hp = min(t.health.hp, t.health.max_hp * 0.6)
                self.cooldown = self.stats.get("infect_cooldown", 8.0)
                fx = self.system.effects
                fx.lightning([(self.pos.x, self.pos.y), (t.x, t.y)], (170, 90, 220), 0.3)
                fx.floating_text(t.x, t.y - 22, "CORRUPTED", (200, 110, 240), 18)
                self.system.events.publish("toast", text="A tower was corrupted! Repair it with E",
                                           color=(200, 110, 240))
        super().update(dt)


class Blob(Enemy):
    """Absorbs the aliens it touches and keeps growing (and slowing down)."""
    sprite = "blob"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_radius = self.radius

    def update(self, dt):
        if self.targetable and self.radius < self.stats.get("max_radius", 26):
            for o in self.system.enemies:
                if (o is self or not o.targetable or o.is_boss or o.flying or isinstance(o, Blob)
                        or getattr(o, "hacked", 0) > 0):
                    continue
                reach = self.radius + o.radius
                if self.pos.distance_squared_to(o.pos) <= reach * reach:
                    gain = self.stats.get("absorb", 0.8)
                    self.health.max_hp += o.health.max_hp * gain
                    self.health.hp += o.health.hp * gain
                    self.reward += o.reward
                    self.radius = min(self.stats.get("max_radius", 26), self.radius + 1.5)
                    self.base_speed *= 0.97
                    o.remove = True
                    self.system.effects.burst(o.pos.x, o.pos.y, S.ALIEN_GREEN, 10, 80, 0.3, 3)
                    break
        super().update(dt)

    def render(self, screen, assets, offset):
        scale = self.radius / self.base_radius
        if scale <= 1.01 or self.fsm.name == "dying":
            super().render(screen, assets, offset)
            return
        img = assets.get(self.frame_name(), flip=self.facing_left,
                         tint="white" if self.flash_timer > 0 else ("cryo" if self.slow > 0 else None))
        w, h = img.get_size()
        img = pygame.transform.scale(img, (int(w * scale), int(h * scale)))
        x, y = self.pos.x + offset[0], self.pos.y + offset[1]
        screen.blit(img, img.get_rect(center=(int(x), int(y))))
        if self.health.ratio < 1:
            w = self.radius * 2
            bx, by = int(x - w / 2), int(y - self.radius - 8)
            pygame.draw.rect(screen, (30, 0, 0), (bx, by, w, 4))
            pygame.draw.rect(screen, S.GREEN if self.health.ratio > 0.4 else S.RED,
                             (bx, by, int(w * self.health.ratio), 4))


class Bomber(Glider):
    """Flyer that bombs towers instead of heading for the Core (until no towers are left)."""
    sprite = "bomber"
    frame_count = 1
    MAX_FORCE = 160.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bomb_cd = 1.0
        self.prey = None

    def update(self, dt):
        if self.targetable:
            towers = self.system.towers
            live = [t for t in towers.towers if not t.health.is_dead] if towers is not None else []
            if self.prey not in live:
                self.prey = min(live, key=lambda t: self.pos.distance_squared_to((t.x, t.y))) if live else None
            if self.prey is not None:
                self.target = pygame.math.Vector2(self.prey.x, self.prey.y)
            else:
                self.target = pygame.math.Vector2(self.system.level.nearest_core_pos(self.pos.x, self.pos.y))
            self.bomb_cd -= dt
            if self.prey is not None and self.bomb_cd <= 0 and \
                    self.pos.distance_squared_to(self.target) <= 34 * 34:
                self.bomb_cd = self.stats.get("bomb_interval", 2.5)
                self.prey.health.damage(self.stats.get("bomb_damage", 35), ignore_armor=True)
                fx = self.system.effects
                fx.explosion(self.prey.x, self.prey.y, S.ORANGE, count=10)
                self.system.audio.play("explode")
        super().update(dt)

    def at_core(self):
        return self.prey is None and super().at_core()


class Jammer(Enemy):
    """Scrambles Vance nearby: no blaster, repairs or Orbital Strike while she's in range."""
    sprite = "jammer"
    frame_count = 1

    def update(self, dt):
        cmd = self.system.commander
        r = self.stats.get("jam_range", 150)
        if self.targetable and cmd is not None and cmd.alive and cmd.pos.distance_squared_to(self.pos) <= r * r:
            cmd.jammed = 0.25
        super().update(dt)

    def render(self, screen, assets, offset):
        if self.targetable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            r = self.stats.get("jam_range", 150)
            for i in range(12):   # dashed static ring
                a = i / 12 * math.tau + self.anim_t * 0.5
                pygame.draw.arc(screen, (230, 120, 60), (x - r, y - r, r * 2, r * 2), a, a + 0.18, 1)
        super().render(screen, assets, offset)


class ArtilleryGrub(Spitter):
    """Slow armored grub that lobs shells at towers from well outside their range."""
    sprite = "artillery_grub"

    def spit(self):
        self.spit_cooldown = self.stats.get("spit_cooldown", 4.0)
        t = self.target_tower()
        if t is None:
            return
        t.health.damage(self.stats.get("spit_damage", 30), ignore_armor=True)
        fx = self.system.effects
        fx.lightning([(self.pos.x, self.pos.y), ((self.pos.x + t.x) / 2, min(self.pos.y, t.y) - 50),
                      (t.x, t.y)], S.ORANGE, 0.25)
        fx.explosion(t.x, t.y, S.ORANGE, count=12)
        fx.ring(t.x, t.y, 24, S.ORANGE, 0.3)


class Pathcutter(Enemy):
    """Once it's partway along, digs a new shortcut through the terrain. The new path stays
    for the rest of the sector (on Open Plains it just tunnels straight at the Core)."""
    sprite = "pathcutter"
    frame_count = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dug = False

    def update(self, dt):
        lvl = self.system.level
        if (self.targetable and not self.dug and not lvl.free_path
                and self.follower.progress > self.stats.get("dig_at", 0.15)):
            self.dug = True
            tile = lvl.world_to_tile(self.pos.x, self.pos.y)
            if lvl.dig_shortcut(tile, fill=False, max_digs=self.stats.get("max_digs", 3)):
                self.system.effects.burst(self.pos.x, self.pos.y, (150, 110, 70), 30, 200, 0.6, 4)
                self.system.events.publish("toast", text="A Pathcutter dug a shortcut!", color=S.ORANGE)
        super().update(dt)


class SwarmQueenlet(Enemy):
    """Mini-boss. Arrives with an escort; every alien near her is faster and tougher."""
    sprite = "swarm_queenlet"
    frame_count = 1
    aura_source = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.escorted = False

    def update(self, dt):
        if not self.escorted:
            self.escorted = True
            spec = self.stats.get("escort", {"enemy": "skitter", "count": 6})
            for i in range(spec["count"]):
                self.system.spawn(spec["enemy"], self.wave,
                                  start_distance=max(0.0, self.follower.distance - 14 - i * 10),
                                  route=self.follower.waypoints)
        super().update(dt)

    def apply_aura(self, enemies):
        r2 = self.stats.get("aura", 150) ** 2
        for e in enemies:
            if e is not self and e.targetable and self.pos.distance_squared_to(e.pos) <= r2:
                e.aura_speed = max(e.aura_speed, self.stats.get("speed_buff", 0.3))
                e.aura_dr = max(e.aura_dr, self.stats.get("dr", 0.25))

    def render(self, screen, assets, offset):
        if self.targetable:
            r = self.stats.get("aura", 150)
            surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*S.ENERGY, 18), (r + 2, r + 2), r)
            pygame.draw.circle(surf, (*S.ENERGY, 90), (r + 2, r + 2), r, 1)
            screen.blit(surf, (self.pos.x + offset[0] - r - 2, self.pos.y + offset[1] - r - 2))
        super().render(screen, assets, offset)
        if self.targetable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1] - self.radius - 16)
            crown = [(x - 7, y + 5), (x - 7, y - 1), (x - 3, y + 2), (x, y - 3), (x + 3, y + 2),
                     (x + 7, y - 1), (x + 7, y + 5)]
            pygame.draw.polygon(screen, S.ENERGY, crown)


# ---- bosses ---------------------------------------------------------------------------------
class Mothership(Glider):
    """Boss. Floats slowly across the map toward the Core and drops a wave of aliens at
    75%, 50% and 25% HP."""
    sprite = "mothership"
    frame_count = 1
    is_boss = True
    MAX_FORCE = 30.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.phases = sorted(self.stats.get("drop_phases", [0.75, 0.5, 0.25]), reverse=True)

    def apply_stun(self, duration):
        pass

    def knockback(self, amount, direction=None):
        pass

    def apply_slow(self, amount, duration):
        super().apply_slow(amount * 0.5, duration)

    def sprite_angle(self):
        return 0.0

    def update(self, dt):
        if self.targetable and self.phases and self.health.ratio <= self.phases[0]:
            self.phases.pop(0)
            self.drop()
        super().update(dt)

    def drop(self):
        sys = self.system
        spec = self.stats.get("drop", {"skitter": 6, "brute": 2, "glider": 3})
        route = sys.level.route_for(0)
        d = route_distance(route, self.pos.x, self.pos.y)
        n = 0
        for kind, count in spec.items():
            for _ in range(count):
                if sys.data[kind].get("flying"):
                    g = sys.spawn(kind, self.wave)
                    g.pos = pygame.math.Vector2(self.pos.x + random.uniform(-30, 30),
                                                self.pos.y + random.uniform(-20, 20))
                else:
                    sys.spawn(kind, self.wave, start_distance=max(0.0, d - n * 12), route=route)
                    n += 1
        sys.effects.ring(self.pos.x, self.pos.y, 60, S.MAGENTA, 0.6, width=4)
        sys.effects.burst(self.pos.x, self.pos.y, S.MAGENTA, 30, 200, 0.6, 4)
        sys.events.publish("toast", text="The Mothership drops reinforcements!", color=S.MAGENTA)
        sys.audio.play("boss")

    def render(self, screen, assets, offset):
        x, y = self.pos.x + offset[0], self.pos.y + offset[1]
        pygame.draw.ellipse(screen, (60, 50, 40), (x - 30, y + 26, 60, 14))   # big shadow
        img = assets.get(self.frame_name(), tint="white" if self.flash_timer > 0 else None)
        if self.fsm.name == "dying":
            t = 1 - self.fsm.time_in_state / 0.25
            w, h = img.get_size()
            img = pygame.transform.scale(img, (max(1, int(w * t)), max(1, int(h * t))))
        bob = math.sin(self.anim_t) * 3
        screen.blit(img, img.get_rect(center=(int(x), int(y - 6 + bob))))
        for i in range(5):   # running lights
            on = int(self.anim_t * 3 + i) % 5 == 0
            pygame.draw.circle(screen, S.ENERGY if on else S.MAGENTA_DARK,
                               (int(x - 24 + i * 12), int(y + 6 + bob)), 2)


class HiveMindBody(_BossBase):
    """Boss in three bodies. A body that's killed while another still stands goes dormant
    and comes back at half HP after revive_time. Kill all three close together."""
    sprite = "hive_mind"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = [self]
        self.linked = False
        self.dormant = 0.0       # seconds until revival, 0 = awake

    @property
    def targetable(self):
        return super().targetable and self.dormant <= 0

    @property
    def hidden(self):
        return self.dormant > 0 or super().hidden

    @property
    def bar_ratio(self):
        hp = sum(max(0.0, b.health.hp) for b in self.group if not b.remove and b.fsm.name != "dying")
        return hp / max(1.0, sum(b.health.max_hp for b in self.group))

    def link(self):
        self.linked = True
        sys = self.system
        for i in (1, 2):
            b = sys.spawn(self.kind, self.wave, start_distance=max(0.0, self.follower.distance - 40 * i),
                          route=self.follower.waypoints, announce=False)
            b.linked = True
            self.group.append(b)
        for b in self.group:
            b.group = self.group

    def intercept_death(self):
        awake = [b for b in self.group if b is not self and b.dormant <= 0
                 and b.fsm.name != "dying" and not b.remove]
        if not awake:   # last one standing: the whole Hive Mind dies
            for b in self.group:
                if b is not self and b.dormant > 0:
                    b.dormant = 0.0
                    b.health.hp = 0
                    self.system.kill(b)
            return False
        self.dormant = self.stats.get("revive_time", 6.0)
        self.health.hp = 1.0
        self.system.effects.burst(self.pos.x, self.pos.y, (170, 90, 220), 20, 140, 0.5, 4)
        self.system.effects.floating_text(self.pos.x, self.pos.y - 30, "DORMANT", (200, 110, 240), 20)
        return True

    def update(self, dt):
        if not self.linked:
            self.link()
        if self.dormant > 0 and self.fsm.name != "dying":
            self.dormant -= dt
            self.update_status(dt)
            if self.dormant <= 0:
                self.health.hp = self.health.max_hp * self.stats.get("revive_hp", 0.5)
                self.system.effects.ring(self.pos.x, self.pos.y, 40, (200, 110, 240), 0.5, width=4)
            return
        super().update(dt)

    def render(self, screen, assets, offset):
        if self.dormant > 0:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            img = assets.get(self.frame_name()).copy()
            img.set_alpha(80)
            screen.blit(img, img.get_rect(center=(x, y)))
            frac = self.dormant / self.stats.get("revive_time", 6.0)
            pygame.draw.arc(screen, (200, 110, 240), (x - 24, y - 24, 48, 48), 0, math.tau * frac, 3)
            return
        super().render(screen, assets, offset)
        if self.targetable and len(self.group) > 1:   # psychic links between the bodies
            for b in self.group:
                if b is not self and b.targetable and id(b) > id(self):
                    pygame.draw.line(screen, (170, 90, 220), (self.pos.x + offset[0], self.pos.y + offset[1]),
                                     (b.pos.x + offset[0], b.pos.y + offset[1]), 1)


class FallenCommander(_BossBase):
    """Boss. An infected copy of Vance: shoots towers, dodge-rolls ahead when hurt and calls
    down her own Orbital Strikes on tower clusters."""
    sprite = "fallen_commander"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shot = Timer(1.0 / self.stats.get("fire_rate", 3.0), repeat=True)
        self.roll_cd = 0.0
        self.strike = Timer(self.stats.get("strike_interval", 14.0), repeat=True)
        self.strikes = []   # [x, y, t_left]
        self.last_hp = None

    def update(self, dt):
        towers = self.system.towers
        fx = self.system.effects
        if self.targetable and towers is not None:
            if self.shot.update(dt):
                r2 = self.stats.get("shoot_range", 160) ** 2
                near = [t for t in towers.towers if not t.health.is_dead
                        and self.pos.distance_squared_to((t.x, t.y)) <= r2]
                if near:
                    t = min(near, key=lambda t: self.pos.distance_squared_to((t.x, t.y)))
                    t.health.damage(self.stats.get("shoot_damage", 12), ignore_armor=True)
                    fx.beam(self.pos.x, self.pos.y, t.x, t.y, (200, 110, 240), 0.08)
            self.roll_cd -= dt
            if self.last_hp is not None and self.health.hp < self.last_hp - 1 and self.roll_cd <= 0 \
                    and self.fsm.name == "walk":
                self.roll_cd = self.stats.get("roll_cooldown", 4.0)
                before = (self.pos.x, self.pos.y)
                f = self.follower
                f.advance(min(self.stats.get("roll_dist", 70), max(0.0, f.total_length - f.distance - 60)))
                self.pos.update(f.pos)
                fx.beam(before[0], before[1], self.pos.x, self.pos.y, (200, 110, 240), 0.2)
                fx.burst(self.pos.x, self.pos.y, (150, 110, 70), 12, 100, 0.3, 3)
            self.last_hp = self.health.hp
            if self.strike.update(dt) and towers.towers:
                def cluster(t):
                    return sum(1 for o in towers.towers if (o.x - t.x) ** 2 + (o.y - t.y) ** 2 <= 80 * 80)
                t = max(towers.towers, key=cluster)
                self.strikes.append([t.x, t.y, 1.5])
                self.system.events.publish("toast", text="Incoming enemy Orbital Strike!", color=S.RED)
        for s in self.strikes:
            s[2] -= dt
            if s[2] <= 0 and towers is not None:
                r = self.stats.get("strike_radius", 80)
                for t in towers.towers:
                    if (t.x - s[0]) ** 2 + (t.y - s[1]) ** 2 <= r * r:
                        t.health.damage(self.stats.get("strike_damage", 60), ignore_armor=True)
                fx.explosion(s[0], s[1], (200, 110, 240), count=30)
                fx.ring(s[0], s[1], r, S.WHITE, 0.5, width=4)
                fx.shake(0.4)
                self.system.audio.play("explode")
        self.strikes = [s for s in self.strikes if s[2] > 0]
        super().update(dt)

    def render(self, screen, assets, offset):
        super().render(screen, assets, offset)
        for x, y, t in self.strikes:
            r = int(self.stats.get("strike_radius", 80) * (0.3 + 0.7 * t / 1.5))
            pygame.draw.circle(screen, (200, 110, 240), (int(x + offset[0]), int(y + offset[1])), r, 2)


class AcidLeviathan(BurrowWyrm):
    """Boss. Swims under the path and erupts from an acid pool, dragging the nearest tower
    under (disabled and badly hurt) and splashing acid on everything around it."""
    sprite = "acid_leviathan"

    def emerge(self):
        super().emerge()
        towers = self.system.towers
        if towers is None or not towers.towers:
            return
        t = min(towers.towers, key=lambda t: self.pos.distance_squared_to((t.x, t.y)))
        reach = self.stats.get("drag_range", 140)
        if self.pos.distance_squared_to((t.x, t.y)) <= reach * reach:
            t.health.damage(t.health.max_hp * self.stats.get("drag_damage", 0.5), ignore_armor=True)
            t.disable(self.stats.get("drag_time", 6.0))
            fx = self.system.effects
            fx.lightning([(self.pos.x, self.pos.y), (t.x, t.y)], S.ACID, 0.4)
            fx.burst(t.x, t.y, S.ACID, 24, 160, 0.5, 4)
            fx.floating_text(t.x, t.y - 22, "DRAGGED UNDER", S.ACID, 18)

    def render(self, screen, assets, offset):
        if self.underground and self.targetable:
            x, y = int(self.pos.x + offset[0]), int(self.pos.y + offset[1])
            pygame.draw.ellipse(screen, (60, 120, 40), (x - 26, y - 10, 52, 20))
            pygame.draw.ellipse(screen, S.ACID, (x - 18, y - 6, 36, 12))
            return
        super().render(screen, assets, offset)


class NestHeart(_BossBase):
    """Boss. A stationary hive heart part-way down the path. It never moves; it keeps
    birthing aliens until you push out and destroy it."""
    sprite = "nest_heart"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        f = self.follower
        self.follower = PathFollower(f.waypoints, f.total_length * self.stats.get("position", 0.3))
        self.pos.update(self.follower.pos)
        self.spawn_timer = Timer(self.stats.get("spawn_interval", 2.5), repeat=True)
        self.n = 0

    def can_attack_commander(self):
        return False

    def at_core(self):
        return False

    def move(self, dt):
        self.vel.update(0, 0)

    def update(self, dt):
        if self.targetable and self.spawn_timer.update(dt):
            pool = self.stats.get("spawns", ["skitter", "skitter", "brute"])
            kind = pool[self.n % len(pool)]
            self.n += 1
            self.system.spawn(kind, self.wave, start_distance=self.follower.distance + 20,
                              route=self.follower.waypoints)
            self.system.effects.burst(self.pos.x, self.pos.y, S.MAGENTA, 8, 90, 0.3, 3)
        self.anim_t += dt
        super().update(dt)

    def render(self, screen, assets, offset):
        pulse = 1.0 + 0.06 * math.sin(self.anim_t * 5)
        img = assets.get(self.frame_name(), tint="white" if self.flash_timer > 0 else None)
        w, h = img.get_size()
        if self.fsm.name == "dying":
            pulse *= 1 - self.fsm.time_in_state / 0.25
        img = pygame.transform.scale(img, (max(1, int(w * pulse)), max(1, int(h * pulse))))
        x, y = self.pos.x + offset[0], self.pos.y + offset[1]
        screen.blit(img, img.get_rect(center=(int(x), int(y))))


class Architect(_BossBase):
    """Boss. At 66% and 33% HP it rebuilds the path: digs a new route through the terrain
    and fills in the stretch it bypassed (on Open Plains it raises rock walls instead)."""
    sprite = "architect"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.phases = sorted(self.stats.get("rebuild_phases", [0.66, 0.33]), reverse=True)

    def update(self, dt):
        if self.targetable and self.phases and self.health.ratio <= self.phases[0]:
            self.phases.pop(0)
            lvl = self.system.level
            tile = lvl.world_to_tile(self.pos.x, self.pos.y)
            changed = lvl.architect_rebuild(tile)
            fx = self.system.effects
            fx.ring(self.pos.x, self.pos.y, 90, S.CYAN, 0.6, width=5)
            fx.shake(0.4)
            self.system.audio.play("boss")
            self.system.events.publish("toast", text="The Architect rebuilds the path!" if changed
                                       else "The Architect's rebuild failed", color=S.CYAN)
        super().update(dt)


P5_CLASSES = {
    "adaptive": Adaptive, "thief": Thief, "leech": Leech, "phaser": Phaser, "reflector": Reflector,
    "swarm_mind": SwarmMind, "necro_spore": NecroSpore, "infector": Infector, "blob": Blob,
    "bomber": Bomber, "jammer": Jammer, "artillery_grub": ArtilleryGrub, "pathcutter": Pathcutter,
    "swarm_queenlet": SwarmQueenlet,
    "mothership": Mothership, "hive_mind": HiveMindBody, "fallen_commander": FallenCommander,
    "acid_leviathan": AcidLeviathan, "nest_heart": NestHeart, "architect": Architect,
}

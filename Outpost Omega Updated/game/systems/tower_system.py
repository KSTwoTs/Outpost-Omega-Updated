"""TowerSystem: placement, targeting, upgrades, selling and tower behaviors."""
import math

import pygame

from .. import settings as S
from ..core.spatial_hash import dist_sq
from ..entities.tower import Tower


# ---- targeting strategies --------------------------------------------------
def pick_target(tower, candidates):
    if not candidates:
        return None
    mode = tower.targeting
    if mode == "first":
        return max(candidates, key=lambda e: e.progress)
    if mode == "last":
        return min(candidates, key=lambda e: e.progress)
    if mode == "strongest":
        return max(candidates, key=lambda e: e.health.hp)
    return min(candidates, key=lambda e: dist_sq(tower.x, tower.y, e.pos.x, e.pos.y))


class TowerSystem:
    def __init__(self, events, level, tower_data, session, collision, projectiles,
                 enemies, effects, audio):
        self.events = events
        self.level = level
        self.data = tower_data
        self.session = session
        self.collision = collision
        self.projectiles = projectiles
        self.enemies = enemies
        self.effects = effects
        self.audio = audio
        self.towers = []
        self.build_kind = None      # tower type being placed (build mode)
        self.selected = None        # tower whose info panel is open
        self.commander = None
        self.by_key = {d["key"]: k for k, d in tower_data.items()}
        self.behaviors = {
            "projectile": self._behavior_projectile,
            "aura": self._behavior_aura,
            "chain": self._behavior_chain,
            "pierce": self._behavior_pierce,
            "missile": self._behavior_missile,
        }

    # ---- build mode ------------------------------------------------------------
    def select_build(self, key):
        kind = self.by_key.get(key)
        if kind is None:
            return False
        if not self.data[kind].get("enabled", True):
            self.events.publish("toast", text=f"{self.data[kind]['name']} unlocks later", color=S.TEXT_DIM)
            self.audio.play("error")
            return False
        self.build_kind = None if self.build_kind == kind else kind
        self.selected = None
        return True

    def cancel_build(self):
        self.build_kind = None

    def placement_problem(self, tx, ty):
        """None if the tile is OK, else a short reason."""
        if not self.level.in_bounds(tx, ty):
            return "Out of bounds"
        if not self.level.is_buildable(tx, ty):
            return "Can't build there"
        c = self.commander
        if c and c.alive and self.collision.box_overlaps_tile(c.pos.x, c.pos.y, c.half, tx, ty):
            return "Commander is in the way"
        if self.level.placement_blocks_route(tx, ty):
            return "Would block the path"
        return None

    def try_place(self, tx, ty):
        kind = self.build_kind
        if kind is None:
            return False
        cost = self.data[kind]["cost"]
        problem = self.placement_problem(tx, ty)
        if problem is None and self.session.energy < cost:
            problem = "Not enough Energy"
        if problem:
            self.events.publish("toast", text=problem, color=S.RED)
            self.audio.play("error")
            return False
        self.session.energy -= cost
        tower = Tower(kind, self.data[kind], tx, ty, self)
        self.towers.append(tower)
        self.level.occupy(tx, ty, tower)
        self.effects.ring(tower.x, tower.y, 24, S.CYAN, 0.3)
        self.audio.play("build")
        self.events.publish("tower_built", tower=tower)
        return True

    # ---- selection / management -----------------------------------------------
    def tower_at(self, tx, ty):
        t = self.level.occupied.get((tx, ty))
        return t if isinstance(t, Tower) else None

    def select(self, tower):
        self.selected = tower
        self.build_kind = None

    def upgrade(self, tower=None):
        tower = tower or self.selected
        if tower is None:
            return False
        if not tower.can_upgrade:
            self.events.publish("toast", text="Already max tier", color=S.TEXT_DIM)
            return False
        cost = tower.upgrade_cost
        if self.session.energy < cost:
            self.events.publish("toast", text="Not enough Energy", color=S.RED)
            self.audio.play("error")
            return False
        self.session.energy -= cost
        tower.upgrade()
        self.effects.ring(tower.x, tower.y, 30, S.ENERGY, 0.4)
        self.audio.play("upgrade")
        self.events.publish("tower_upgraded", tower=tower)
        return True

    def sell(self, tower=None):
        tower = tower or self.selected
        if tower is None:
            return False
        self.session.energy += tower.sell_value
        self.towers.remove(tower)
        self.level.vacate(tower.tx, tower.ty)
        self.effects.explosion(tower.x, tower.y, S.STEEL_LIGHT, count=12)
        self.audio.play("sell")
        if self.selected is tower:
            self.selected = None
        self.events.publish("tower_sold", tower=tower)
        return True

    def cycle_targeting(self, tower=None):
        tower = tower or self.selected
        if tower:
            mode = tower.cycle_targeting()
            self.events.publish("toast", text=f"Targeting: {mode}", color=S.CYAN)

    def nearest_damaged_tower(self, x, y, rng):
        best, best_d = None, rng * rng
        for t in self.towers:
            if t.health.ratio < 1:
                d = dist_sq(x, y, t.x, t.y)
                if d <= best_d:
                    best, best_d = t, d
        return best

    def nearest_tower(self, x, y):
        if not self.towers:
            return None
        return min(self.towers, key=lambda t: dist_sq(x, y, t.x, t.y))

    # ---- behaviors (one per "behavior" in towers.json) ---------------------------
    def run_behavior(self, tower, dt):
        self.behaviors[tower.behavior](tower, dt)

    def _behavior_projectile(self, tower, dt):
        """Pulse Turret: single target, lead-aimed bullets."""
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        if tower.cooldown.ready:
            tower.cooldown.trigger()
            st = tower.stats
            muzzle = (tower.x + math.cos(tower.angle) * 16, tower.y + math.sin(tower.angle) * 16)
            aim = self.projectiles.fire_at(muzzle[0], muzzle[1], target, st["projectile_speed"],
                                           st["damage"], color=S.ORANGE,
                                           hits_air=tower.can_target_air)
            tower.aim_at(*aim)
            tower.muzzle_timer = 0.1
            self.effects.muzzle(muzzle[0], muzzle[1], tower.angle)
            self.audio.play("shoot")

    def _behavior_aura(self, tower, dt):
        """Cryo Emitter: slows (and at tier 3 chills for damage) everything in range."""
        st = tower.stats
        for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air):
            e.apply_slow(st["slow"], 0.25)
            if st.get("dps"):
                self.enemies.damage(e, st["dps"] * dt * tower.fire_rate_mult, ignore_armor=True, quiet=True)
        if int(tower.pulse_t * 1.5) != int((tower.pulse_t - dt) * 1.5):
            self.effects.ring(tower.x, tower.y, tower.range, S.CRYO, 0.6, width=2)

    def _behavior_chain(self, tower, dt):
        """Tesla Coil: zap the target, then jump to the nearest enemy not yet hit
        (within chain_range), up to `chain` enemies. Each jump does 85% damage."""
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None or not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        st = tower.stats
        hit = [target]
        while len(hit) < st["chain"]:
            last = hit[-1]
            near = [e for e in self.collision.enemies_in_range(last.pos.x, last.pos.y, st["chain_range"],
                                                               tower.can_target_air) if e not in hit]
            if not near:
                break
            hit.append(min(near, key=lambda e: dist_sq(last.pos.x, last.pos.y, e.pos.x, e.pos.y)))
        points = [(tower.x, tower.y - 6)] + [(e.pos.x, e.pos.y) for e in hit]
        damage = st["damage"]
        for e in hit:
            self.enemies.damage(e, damage)
            e.apply_stun(0.1)
            damage *= 0.85
        self.effects.lightning(points, S.CYAN)
        self.audio.play("zap")

    def _behavior_pierce(self, tower, dt):
        """Railgun: a beam from the tower through the target out to full range.
        Every ground enemy whose circle touches the line takes full damage,
        ignoring armor (that's why Brutes are weak to it)."""
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        if not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        dx, dy = math.cos(tower.angle), math.sin(tower.angle)
        x2, y2 = tower.x + dx * tower.range, tower.y + dy * tower.range
        for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range + 20, tower.can_target_air):
            # Segment test (circle for most aliens, pixel mask for the boss).
            if e.hit_test_segment(tower.x, tower.y, x2, y2):
                self.enemies.damage(e, tower.stats["damage"], ignore_armor=True)
        self.effects.beam(tower.x + dx * 16, tower.y + dy * 16, x2, y2, S.CYAN)
        self.effects.shake(0.08)
        self.audio.play("rail")

    def _behavior_missile(self, tower, dt):
        """Missile Battery: homing missiles (turn-rate limited) with splash damage."""
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        if not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        st = tower.stats
        self.projectiles.fire_at(tower.x, tower.y, target, st["projectile_speed"], st["damage"],
                                 color=S.RED, hits_air=True, radius=4, lead=False, life=3.0,
                                 homing_target=target, turn_rate=st["turn_rate"], splash=st["splash"])
        self.audio.play("missile")

    # ---- loop ----------------------------------------------------------------------
    def on_update(self, dt):
        for t in self.towers:
            t.update(dt)

    def on_render(self, screen, assets, offset):
        for t in self.towers:
            t.render(screen, assets, offset)
        if self.selected:
            self.draw_range(screen, self.selected.x + offset[0], self.selected.y + offset[1],
                            self.selected.range, S.CYAN)

    @staticmethod
    def draw_range(screen, x, y, rng, color):
        size = int(rng * 2 + 4)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(surf, (*color, 40), (c, c), int(rng))
        pygame.draw.circle(surf, (*color, 140), (c, c), int(rng), 2)
        screen.blit(surf, (x - c, y - c))

    def render_preview(self, screen, assets, mouse):
        """Green/red tile preview plus range circle while in build mode."""
        if self.build_kind is None or mouse[1] >= S.MAP_H:
            return
        tx, ty = self.level.world_to_tile(*mouse)
        ok = self.placement_problem(tx, ty) is None and \
            self.session.energy >= self.data[self.build_kind]["cost"]
        color = S.GREEN if ok else S.RED
        rect = pygame.Rect(tx * S.TILE, ty * S.TILE, S.TILE, S.TILE)
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        surf.fill((*color, 90))
        screen.blit(surf, rect)
        pygame.draw.rect(screen, color, rect, 2)
        rng = self.data[self.build_kind]["tiers"][0]["range"]
        self.draw_range(screen, rect.centerx, rect.centery, rng, color)
        ghost = assets.get(f"turret_{self.build_kind}")
        ghost = ghost.copy()
        ghost.set_alpha(150)
        screen.blit(ghost, ghost.get_rect(center=rect.center))

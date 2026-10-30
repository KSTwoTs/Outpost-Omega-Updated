"""TowerSystem: placement, targeting, upgrades, selling and tower behaviors."""
import math
import random

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
        self.range_mult = 1.0       # endless "Blackout" mutator shrinks every tower's range
        self.sell_refund = S.SELL_REFUND   # a Siege Run relic can set this to 0
        self.env_range_mult = 1.0   # weather (sandstorm)
        self.allow_branches = False # tier-4 branches are a Siege Run feature
        self.shells = []            # mortar shells in flight: [x, y, t_left, t_total, sx, sy, damage, splash, owner]
        self.mines = []             # armed mines: [x, y, damage, splash, owner]
        self.barricades = []        # active barricades (enemies stop and chew), refreshed every frame
        events.subscribe("wave_cleared", self.on_wave_cleared)
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
            "cone": self._behavior_cone,
            "mortar": self._behavior_mortar,
            "gravity": self._behavior_gravity,
            "income": self._behavior_none,
            "drones": self._behavior_drones,
            "mines": self._behavior_mines,
            "barricade": self._behavior_none,
            "support": self._behavior_none,
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
        kind = self.build_kind
        if kind and self.data[kind]["behavior"] == "barricade" and not self.level.free_path:
            # Barricades sit ON the path and don't change routing: aliens stop and chew.
            if self.level.tile_at(tx, ty) != S.T_PATH or (tx, ty) in self.level.occupied:
                return "Barricades go on the path"
            c = self.commander
            if c and c.alive and self.collision.box_overlaps_tile(c.pos.x, c.pos.y, c.half, tx, ty):
                return "Commander is in the way"
            return None
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
        if "max_hp" in tower.stats:   # Barricades get tougher
            tower.health.max_hp = tower.stats["max_hp"]
            tower.health.hp = tower.health.max_hp
        self.effects.ring(tower.x, tower.y, 30, S.ENERGY, 0.4)
        self.audio.play("upgrade")
        self.events.publish("tower_upgraded", tower=tower)
        return True

    def choose_branch(self, tower, index):
        if tower is None or not tower.branch_available:
            return False
        cost = tower.data["branches"][index]["cost"]
        if self.session.energy < cost:
            self.events.publish("toast", text="Not enough Energy", color=S.RED)
            self.audio.play("error")
            return False
        self.session.energy -= cost
        tower.choose_branch(index)
        self.effects.ring(tower.x, tower.y, 36, S.MAGENTA, 0.5, width=4)
        self.effects.burst(tower.x, tower.y, S.MAGENTA, 20, 160, 0.5, 3)
        self.audio.play("upgrade")
        self.events.publish("toast", text=f"{tower.name}: {tower.branch_name}", color=S.MAGENTA)
        return True

    def on_wave_cleared(self, **_):
        """Harvesters pay out after every wave."""
        total = 0
        for t in self.towers:
            if t.behavior == "income" and not t.health.is_dead:
                gain = t.stats.get("income", 0)
                total += gain
                self.effects.floating_text(t.x, t.y - 18, f"+{gain}", S.ENERGY, 20)
        if total:
            self.session.energy += total
            self.events.publish("toast", text=f"Harvesters: +{total} Energy", color=S.ENERGY)

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
                                           hits_air=tower.can_target_air, source=tower)
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
                self.enemies.damage(e, st["dps"] * dt * tower.fire_rate_mult, ignore_armor=True, quiet=True,
                                    source=tower)
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
        chain = st["chain"]
        if target.slow > 0:    # combo: Conduct (Tesla jumps further through chilled aliens)
            chain += 2
            if random.random() < 0.25:
                self.effects.floating_text(target.pos.x, target.pos.y - 24, "CONDUCT", S.CYAN, 18)
        while len(hit) < chain:
            last = hit[-1]
            near = [e for e in self.collision.enemies_in_range(last.pos.x, last.pos.y, st["chain_range"],
                                                               tower.can_target_air) if e not in hit]
            if not near:
                break
            hit.append(min(near, key=lambda e: dist_sq(last.pos.x, last.pos.y, e.pos.x, e.pos.y)))
        points = [(tower.x, tower.y - 6)] + [(e.pos.x, e.pos.y) for e in hit]
        damage = st["damage"]
        for e in hit:
            self.enemies.damage(e, damage, source=tower)
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
                st = tower.stats
                damage = st["damage"]
                if e.slow > 0:   # combo: Shatter (Railgun crits chilled aliens)
                    damage *= 2
                    self.effects.floating_text(e.pos.x, e.pos.y - 24, "SHATTER", S.CRYO, 18)
                self.enemies.damage(e, damage, ignore_armor=True, source=tower)
                if (st.get("execute") and e.targetable and not e.is_boss
                        and e.health.ratio < st["execute"]):
                    self.enemies.damage(e, e.health.hp + 1, ignore_armor=True, quiet=True, source=tower)
                    self.effects.floating_text(e.pos.x, e.pos.y - 24, "EXECUTED", S.RED, 18)
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
                                 homing_target=target, turn_rate=st["turn_rate"], splash=st["splash"],
                                 source=tower)
        self.audio.play("missile")

    def _behavior_none(self, tower, dt):
        """Harvester and Radar Relay don't attack (see on_wave_cleared / update_buffs)."""
        tower.target = None

    def _behavior_cone(self, tower, dt):
        """Flamer: damages and burns every ground alien inside a cone toward its target."""
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
        half = st.get("cone", 0.5)
        for e in candidates:
            ang = math.atan2(e.pos.y - tower.y, e.pos.x - tower.x)
            diff = (ang - tower.angle + math.pi) % math.tau - math.pi
            if abs(diff) <= half:
                self.enemies.damage(e, st["damage"], quiet=True, source=tower)
                e.apply_burn(st["burn_dps"], st["burn_time"])
        for _ in range(4):
            a = tower.angle + random.uniform(-half, half)
            sp = random.uniform(0.6, 1.0) * tower.range * 2.2
            p = self.effects.particles.acquire()
            p.spawn(tower.x + math.cos(a) * 14, tower.y + math.sin(a) * 14,
                    math.cos(a) * sp, math.sin(a) * sp, 0.4,
                    random.choice((S.ORANGE, S.ENERGY, S.RED)), 4, drag=2.0)
        if random.random() < 0.15:
            self.audio.play("shoot")

    def _behavior_mortar(self, tower, dt):
        """Mortar: lobs a shell at where the target will be; big splash, minimum range."""
        st = tower.stats
        r2min = st.get("min_range", 0) ** 2
        candidates = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
                      if dist_sq(tower.x, tower.y, e.pos.x, e.pos.y) >= r2min]
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        if not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        t = st.get("flight_time", 1.0)
        x, y = target.future_position(t)
        self.shells.append([x, y, t, t, tower.x, tower.y, st["damage"], st["splash"], tower])
        self.effects.muzzle(tower.x, tower.y, tower.angle)
        self.audio.play("missile")

    def _behavior_gravity(self, tower, dt):
        """Gravity Well: every few seconds, drags ground aliens in range back along the path."""
        candidates = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)]
        tower.target = candidates[0] if candidates else None
        if not candidates or not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        pull = tower.stats["pull"]
        for e in candidates:
            e.knockback(pull)
            e.apply_slow(0.3, 1.0)
        self.effects.ring(tower.x, tower.y, tower.range, S.MAGENTA, 0.5, width=4)
        self.effects.ring(tower.x, tower.y, tower.range * 0.5, S.MAGENTA, 0.4, width=2)
        self.audio.play("shield")

    def _behavior_drones(self, tower, dt):
        """Drone Bay: drones swarm the target anywhere in range and shoot it up close."""
        st = tower.stats
        drones = tower.__dict__.setdefault("drones", [])
        while len(drones) < st["drones"]:
            drones.append({"x": tower.x, "y": tower.y, "cd": 0.0, "a": random.random() * math.tau})
        target = pick_target(tower, self.collision.enemies_in_range(tower.x, tower.y, tower.range, True))
        tower.target = target
        for i, d in enumerate(drones):
            d["cd"] -= dt * tower.fire_rate_mult
            d["a"] += dt * 2.5
            if target is not None:
                gx = target.pos.x + math.cos(d["a"] + i * 2.1) * 30
                gy = target.pos.y + math.sin(d["a"] + i * 2.1) * 30
            else:
                gx = tower.x + math.cos(d["a"] + i * 2.1) * 22
                gy = tower.y + math.sin(d["a"] + i * 2.1) * 22
            dx, dy = gx - d["x"], gy - d["y"]
            dist = math.hypot(dx, dy)
            step = st["speed"] * dt
            if dist > step:
                d["x"] += dx / dist * step
                d["y"] += dy / dist * step
            else:
                d["x"], d["y"] = gx, gy
            if (target is not None and d["cd"] <= 0
                    and dist_sq(d["x"], d["y"], target.pos.x, target.pos.y) < 70 * 70):
                d["cd"] = 1.0 / st["fire_rate"]
                self.enemies.damage(target, st["damage"], quiet=True, source=tower)
                self.effects.beam(d["x"], d["y"], target.pos.x, target.pos.y, S.GREEN, 0.06)

    def _behavior_mines(self, tower, dt):
        """Mine Layer: drops a mine on a random path tile in range, up to max_mines at once."""
        st = tower.stats
        tower.target = None
        mine_count = sum(1 for m in self.mines if m[4] is tower)
        if mine_count >= st["max_mines"] or not tower.cooldown.ready:
            return
        r2 = tower.range * tower.range
        spots = [self.level.tile_center(*t) for tiles in self.level.route_tiles for t in tiles]
        spots = [p for p in spots if dist_sq(tower.x, tower.y, p[0], p[1]) <= r2
                 and all(dist_sq(p[0], p[1], m[0], m[1]) > 24 * 24 for m in self.mines)]
        if not spots:
            return
        tower.cooldown.trigger()
        x, y = random.choice(spots)
        x += random.uniform(-8, 8)
        y += random.uniform(-8, 8)
        self.mines.append([x, y, st["damage"], st["splash"], tower])
        self.effects.ring(x, y, 10, S.RED, 0.25, width=2)

    def update_mines(self):
        live = []
        for m in self.mines:
            x, y, damage, splash, owner = m
            if owner not in self.towers:
                continue   # sold: its mines are disarmed
            if self.collision.enemies_touching(x, y, 12, include_air=False):
                self.enemies.splash(x, y, splash, damage, include_air=False, knockback=12, source=owner)
                self.effects.explosion(x, y, S.ORANGE, count=16)
                self.audio.play("explode")
            else:
                live.append(m)
        self.mines = live

    def update_barricades(self):
        self.barricades = [t for t in self.towers if t.behavior == "barricade" and t.fsm.name == "active"]

    def update_buffs(self):
        """Radar Relays raise the range of towers around them (strongest relay wins)."""
        relays = [t for t in self.towers if t.behavior == "support" and t.fsm.name == "active"]
        for t in self.towers:
            best = 0.0
            if t.behavior != "support":
                for r in relays:
                    if dist_sq(t.x, t.y, r.x, r.y) <= r.stats["range"] ** 2:
                        best = max(best, r.stats.get("buff", 0.0))
            t.range_buff = best

    def update_shells(self, dt):
        for s in self.shells:
            s[2] -= dt
            if s[2] <= 0:
                x, y, damage, splash, owner = s[0], s[1], s[6], s[7], s[8]
                burning = any(e.burn_timer > 0 for e in self.collision.enemies_in_range(x, y, splash, False))
                if burning:   # combo: Detonate (burning aliens make blasts bigger)
                    splash *= 1.5
                    damage *= 1.5
                    self.effects.floating_text(x, y - 20, "DETONATE", S.ORANGE, 20)
                self.enemies.splash(x, y, splash, damage, include_air=False, knockback=14, source=owner)
                self.effects.explosion(x, y, S.ORANGE, count=26)
                self.effects.ring(x, y, splash, S.ORANGE, 0.35, width=3)
                self.effects.shake(0.12)
                self.audio.play("explode")
        self.shells = [s for s in self.shells if s[2] > 0]

    # ---- loop ----------------------------------------------------------------------
    def on_update(self, dt):
        self.update_buffs()
        self.update_barricades()
        for t in self.towers:
            t.update(dt)
        self.update_shells(dt)
        self.update_mines()

    def on_render(self, screen, assets, offset):
        blink = (pygame.time.get_ticks() // 300) % 2
        for x, y, _d, _s, _o in self.mines:
            p = (int(x + offset[0]), int(y + offset[1]))
            pygame.draw.circle(screen, (22, 22, 34), p, 6)
            pygame.draw.circle(screen, S.STEEL_DARK, p, 5)
            pygame.draw.circle(screen, S.RED if blink else (110, 20, 20), p, 2)
        for t in self.towers:
            t.render(screen, assets, offset)
            for d in t.__dict__.get("drones", []):
                x, y = d["x"] + offset[0], d["y"] + offset[1]
                a = d["a"]
                pts = [(x + math.cos(a) * 7, y + math.sin(a) * 7),
                       (x + math.cos(a + 2.4) * 5, y + math.sin(a + 2.4) * 5),
                       (x + math.cos(a - 2.4) * 5, y + math.sin(a - 2.4) * 5)]
                pygame.draw.polygon(screen, (22, 22, 34), pts)
                pygame.draw.circle(screen, S.GREEN, (int(x), int(y)), 2)
        for x, y, left, total, sx, sy, _d, splash, _owner in self.shells:
            k = 1 - left / total
            px = sx + (x - sx) * k + offset[0]
            py = sy + (y - sy) * k - math.sin(k * math.pi) * 90 + offset[1]
            pygame.draw.circle(screen, (40, 30, 30), (int(x + offset[0]), int(y + offset[1])),
                               int(4 + 8 * k), 1)
            pygame.draw.circle(screen, (22, 22, 34), (int(px), int(py)), 6)
            pygame.draw.circle(screen, S.ORANGE, (int(px), int(py)), 4)
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
        rng = self.data[self.build_kind]["tiers"][0].get("range", 0)
        self.draw_range(screen, rect.centerx, rect.centery, rng, color)
        ghost = assets.get(f"turret_{self.build_kind}")
        ghost = ghost.copy()
        ghost.set_alpha(150)
        screen.blit(ghost, ghost.get_rect(center=rect.center))

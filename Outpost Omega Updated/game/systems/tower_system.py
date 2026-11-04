"""TowerSystem: placement, targeting, upgrades, selling and tower behaviors."""
import math
import random

import pygame

from .. import settings as S
from ..core.spatial_hash import dist_sq
from ..entities.tower import Tower
from .tower_art import CHRONO, HACK, draw_beam, draw_fence, draw_hack, draw_ion, draw_mine, draw_puddle


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
        self.puddles = []           # acid pools: [x, y, radius, dps, t_left, t_total, shred, owner]
        self.barricades = []        # active barricades (enemies stop and chew), refreshed every frame
        self.flak_volleys = []      # queued flak shells: [delay, tower, target, damage, splash]
        self.ion_blasts = []        # fading Ion Cannon blasts: [routes, t_left, branch]
        self.fence_links = []       # Plasma Fence beams: (pylon_a, pylon_b), refreshed every frame
        self.hacked = []            # aliens currently hacked by a Hacker Spire
        events.subscribe("wave_cleared", self.on_wave_cleared)
        events.subscribe("enemy_killed", self.on_enemy_killed)
        self.player = None          # PlayerSystem (Uplink Dish), set by PlayScene
        self.systems = {}           # data/tower_systems.json, set by PlayScene
        self.allow_fusion = False   # Endless and Siege Run
        self.relocating = None      # tower being moved (build phase)
        self.research_source = {}   # Economy research mods applied to every tower
        self.mastery = {}           # tower kind -> mastery level 0-3 (systems/meta.py)
        self.mastery_branches = False   # Endless: mastery level 3 unlocks that tower's tier-4 branches
        self.research_hp = 1.0
        self.economy = None         # Economy (Bio-Lab Biomass), set by PlayScene
        self.features = None        # MapFeatures (terrain bonuses), set by PlayScene
        self.on_broken = None       # callback(tower) when a tower hits 0 HP (Juice / insurance)
        self.on_tower_kill = None   # callback(tower) on every kill credited to a tower (mastery)
        self.placed_this_build = [] # undo stack, cleared when a wave starts
        events.subscribe("wave_started", lambda **_: self.placed_this_build.clear())
        self.weather_kind = None    # set by PlayScene when weather rolls (Lightning Rod)
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
            "barricade": self._behavior_barricade,
            "support": self._behavior_none,
            "beam": self._behavior_beam,
            "acid": self._behavior_acid,
            "repair": self._behavior_repair,
            "shockwave": self._behavior_shockwave,
            "flak": self._behavior_flak,
            "ion": self._behavior_ion,
            "shield": self._behavior_none,
            "tar": self._behavior_tar,
            "chrono": self._behavior_chrono,
            "decoy": self._behavior_decoy,
            "fence": self._behavior_none,
            "mirror": self._behavior_none,
            "hacker": self._behavior_hacker,
            "magnet": self._behavior_magnet,
            "lightning": self._behavior_lightning,
            "biolab": self._behavior_none,
            "overclock": self._behavior_none,
            "uplink": self._behavior_none,
            "bait": self._behavior_none,
            "generator": self._behavior_none,
            "brood": self._behavior_brood,
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
        on_path = kind and self.data[kind]["behavior"] in ("barricade", "tar")
        if on_path and not self.level.free_path:
            # Barricades and Tar Pits sit ON the path and don't change routing.
            if self.level.tile_at(tx, ty) != S.T_PATH or (tx, ty) in self.level.occupied:
                return f"{self.data[kind]['name']}s go on the path"
            c = self.commander
            if c and c.alive and self.collision.box_overlaps_tile(c.pos.x, c.pos.y, c.half, tx, ty):
                return "Commander is in the way"
            return None
        if not self.level.is_buildable(tx, ty):
            return "Can't build there"
        c = self.commander
        if c and c.alive and self.collision.box_overlaps_tile(c.pos.x, c.pos.y, c.half, tx, ty):
            return "Commander is in the way"
        if not self.data[kind].get("walkable") and self.level.placement_blocks_route(tx, ty):
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
        if self.research_hp != 1.0:
            tower.health.reset(tower.health.max_hp * self.research_hp)
        self.towers.append(tower)
        self.placed_this_build.append((tower, cost))
        self.level.occupy(tx, ty, tower)
        self.effects.ring(tower.x, tower.y, 24, S.CYAN, 0.3)
        self.audio.play("build")
        self.events.publish("tower_built", tower=tower)
        self.refresh_topology()
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
        self.refresh_topology()
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
        if "max_hp" in tower.stats:   # Barricade branches
            tower.health.max_hp = tower.stats["max_hp"]
            tower.health.hp = tower.health.max_hp
        self.effects.ring(tower.x, tower.y, 36, S.MAGENTA, 0.5, width=4)
        self.effects.burst(tower.x, tower.y, S.MAGENTA, 20, 160, 0.5, 3)
        self.audio.play("upgrade")
        self.events.publish("toast", text=f"{tower.name}: {tower.branch_name}", color=S.MAGENTA)
        self.refresh_topology()
        return True

    def on_wave_cleared(self, **_):
        """Harvesters pay out after every wave."""
        total = 0
        for t in self.towers:
            if t.behavior == "income" and not t.health.is_dead:
                gain = int(round(t.stats.get("income", 0)))
                total += gain
                self.effects.floating_text(t.x, t.y - 18, f"+{gain}", S.ENERGY, 20)
                heal = t.stats.get("core_heal", 0)   # Overflow Core branch
                s = self.session
                if heal and s.core_hp < s.core_max:
                    s.core_hp = min(s.core_max, s.core_hp + heal)
        if total:
            self.session.energy += total
            self.events.publish("toast", text=f"Harvesters: +{total} Energy", color=S.ENERGY)

    def undo_last(self):
        """Backspace in the build phase: take back the last tower placed, full refund."""
        while self.placed_this_build:
            tower, cost = self.placed_this_build.pop()
            if tower in self.towers and tower.tier == 0 and tower.branch is None and not tower.fusion:
                self.towers.remove(tower)
                self.level.vacate(tower.tx, tower.ty)
                self.session.energy += cost
                for c in tower.chips:
                    self.session.chips[c] = self.session.chips.get(c, 0) + 1
                if self.selected is tower:
                    self.selected = None
                self.effects.ring(tower.x, tower.y, 20, S.TEXT_DIM, 0.3)
                self.audio.play("sell")
                self.events.publish("toast", text=f"Undid {tower.name} (+{cost} E)", color=S.TEXT_DIM)
                self.refresh_topology()
                return True
        self.events.publish("toast", text="Nothing to undo", color=S.TEXT_DIM)
        return False

    def sell(self, tower=None):
        tower = tower or self.selected
        if tower is None:
            return False
        self.session.energy += tower.sell_value
        for c in tower.chips:   # socketed chips go back to the inventory
            self.session.chips[c] = self.session.chips.get(c, 0) + 1
        self.towers.remove(tower)
        self.level.vacate(tower.tx, tower.ty)
        if self.relocating is tower:
            self.relocating = None
        self.effects.explosion(tower.x, tower.y, S.STEEL_LIGHT, count=12)
        self.audio.play("sell")
        if self.selected is tower:
            self.selected = None
        self.events.publish("tower_sold", tower=tower)
        self.refresh_topology()
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

    def run_corrupted(self, tower, dt):
        """An Infector got to this tower: it zaps the nearest other tower in range."""
        tower.target = None
        rng = max(tower.range, 90)
        near = [t for t in self.towers if t is not tower and not t.health.is_dead
                and dist_sq(t.x, t.y, tower.x, tower.y) <= rng * rng]
        if not near:
            return
        t = min(near, key=lambda o: dist_sq(o.x, o.y, tower.x, tower.y))
        tower.aim_at(t.x, t.y)
        t.health.damage(8 * dt, ignore_armor=True)
        if random.random() < dt * 5:
            self.effects.lightning([(tower.x, tower.y), (t.x, t.y)], (200, 110, 240), 0.1)

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
            if st.get("slow"):   # Frost Arc
                e.apply_slow(st["slow"], 1.5)
            damage *= 0.85
        self.effects.lightning(points, S.CYAN)
        self.audio.play("zap")

    def _behavior_pierce(self, tower, dt):
        """Railgun: a beam from the tower through the target out to full range.
        Every ground enemy whose circle touches the line takes full damage,
        ignoring armor (that's why Brutes are weak to it). Mirror Arrays in range
        bounce the shot at aliens around them, so a Railgun can shoot round corners."""
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        target = pick_target(tower, candidates)
        tower.target = target
        mirrors = self.mirror_targets(tower)
        if target is not None:
            tower.aim_at(target.pos.x, target.pos.y)
        elif mirrors:
            tower.aim_at(mirrors[0][0].x, mirrors[0][0].y)
        else:
            return
        if not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        st = tower.stats
        if target is not None:
            dx, dy = math.cos(tower.angle), math.sin(tower.angle)
            x2, y2 = tower.x + dx * tower.range, tower.y + dy * tower.range
            self._rail_line(tower, tower.x, tower.y, x2, y2, st["damage"])
            self.effects.beam(tower.x + dx * 16, tower.y + dy * 16, x2, y2, S.CYAN)
        for m, targets in mirrors:   # bounce: tower -> mirror -> each of the mirror's targets
            self.effects.beam(tower.x, tower.y, m.x, m.y, S.CYAN, 0.12)
            for e in targets:
                m.aim_at(e.pos.x, e.pos.y)
                rr = m.stats["reflect_range"]
                ux, uy = math.cos(m.angle), math.sin(m.angle)
                x2, y2 = m.x + ux * rr, m.y + uy * rr
                self._rail_line(tower, m.x, m.y, x2, y2, st["damage"] * m.stats["reflect"])
                self.effects.beam(m.x, m.y, x2, y2, (190, 240, 255), 0.18)
        self.effects.shake(0.08)
        self.audio.play("rail")

    def _rail_line(self, tower, x1, y1, x2, y2, damage):
        """Railgun damage along one segment (Shatter and Executioner included)."""
        st = tower.stats
        length = math.hypot(x2 - x1, y2 - y1)
        for e in self.collision.enemies_in_range((x1 + x2) / 2, (y1 + y2) / 2, length / 2 + 20,
                                                 tower.can_target_air):
            # Segment test (circle for most aliens, pixel mask for the boss).
            if e.hit_test_segment(x1, y1, x2, y2):
                hit = damage
                if e.slow > 0:   # combo: Shatter (Railgun crits chilled aliens)
                    hit *= 2
                    self.effects.floating_text(e.pos.x, e.pos.y - 24, "SHATTER", S.CRYO, 18)
                self.enemies.damage(e, hit, ignore_armor=True, source=tower)
                if (st.get("execute") and e.targetable and not e.is_boss
                        and e.health.ratio < st["execute"]):
                    self.enemies.damage(e, e.health.hp + 1, ignore_armor=True, quiet=True, source=tower)
                    self.effects.floating_text(e.pos.x, e.pos.y - 24, "EXECUTED", S.RED, 18)

    def mirror_targets(self, tower):
        """[(mirror, [aliens])] for every active Mirror Array within reach of a beam tower."""
        out = []
        for m in self.towers:
            if m.behavior != "mirror" or m.fsm.name != "active":
                continue
            if dist_sq(tower.x, tower.y, m.x, m.y) > m.range * m.range:
                continue
            pool = self.collision.enemies_in_range(m.x, m.y, m.stats["reflect_range"], tower.can_target_air)
            if not pool:
                continue
            pool.sort(key=lambda e: -e.progress)
            out.append((m, pool[:int(m.stats.get("splits", 1))]))
        return out

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
                if st.get("shred"):   # Napalm Spitter
                    e.corrode(st["shred"], 2.0)
        for pit in self.tar_pits:   # combo: Flamer sets Tar Pits ablaze
            if tower.in_range(pit.x, pit.y):
                ang = math.atan2(pit.y - tower.y, pit.x - tower.x)
                if abs((ang - tower.angle + math.pi) % math.tau - math.pi) <= half:
                    self.ignite(pit)
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
        st = tower.stats
        pull = st["pull"]
        for e in candidates:
            e.knockback(pull)
            e.apply_slow(0.3, 1.0)
            if st.get("stun"):      # Stasis Field
                e.apply_stun(st["stun"])
            if st.get("damage"):    # Singularity
                self.enemies.damage(e, st["damage"], quiet=True, source=tower)
        self.effects.ring(tower.x, tower.y, tower.range, S.MAGENTA, 0.5, width=4)
        self.effects.ring(tower.x, tower.y, tower.range * 0.5, S.MAGENTA, 0.4, width=2)
        self.audio.play("shield")

    def _behavior_barricade(self, tower, dt):
        """Barricade: just sits on the path. Shock Barricade zaps whatever is chewing it."""
        tower.target = None
        thorns = tower.stats.get("thorns", 0)
        if thorns:
            for e in self.collision.enemies_in_range(tower.x, tower.y, 26, False):
                self.enemies.damage(e, thorns * dt, ignore_armor=True, quiet=True, source=tower)
            if random.random() < dt * 3:
                self.effects.lightning([(tower.x, tower.y), (tower.x + random.uniform(-18, 18),
                                                             tower.y + random.uniform(-18, 18))], S.CYAN)

    def _behavior_beam(self, tower, dt):
        """Laser Lance: continuous beam(s). Damage ramps from dps up to dps x ramp while
        the beam stays on the same alien; switching targets resets the ramp."""
        st = tower.stats
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        beams = int(st.get("beams", 1))
        locks = tower.__dict__.setdefault("locks", {})     # enemy -> seconds held
        targets = []
        first = pick_target(tower, candidates)
        if first is not None:
            targets.append(first)
            rest = sorted((e for e in candidates if e is not first),
                          key=lambda e: dist_sq(first.pos.x, first.pos.y, e.pos.x, e.pos.y))
            targets += rest[:beams - 1]
        tower.target = first
        tower.beam_targets = targets
        for e in list(locks):
            if e not in targets:
                del locks[e]
        if first is not None:
            tower.aim_at(first.pos.x, first.pos.y)
        ramp_time = max(0.1, st.get("ramp_time", 3.0))
        for e in targets:
            held = locks.get(e, 0.0) + dt
            locks[e] = held
            mult = 1.0 + (st.get("ramp", 1.0) - 1.0) * min(1.0, held / ramp_time)
            self.enemies.damage(e, st["dps"] * mult * dt * tower.fire_rate_mult, ignore_armor=True,
                                quiet=True, source=tower)
        tower.mirror_beams = []
        for m, mtargets in self.mirror_targets(tower):   # beams bent by Mirror Arrays
            for e in mtargets:
                m.aim_at(e.pos.x, e.pos.y)
                tower.mirror_beams.append((m, e))
                self.enemies.damage(e, st["dps"] * m.stats["reflect"] * dt * tower.fire_rate_mult,
                                    ignore_armor=True, quiet=True, source=tower)
        if (targets or tower.mirror_beams) and random.random() < dt * 6:
            self.audio.play("zap")

    def _behavior_acid(self, tower, dt):
        """Acid Spitter: lobs acid at the target's feet; the pool damages and strips armor."""
        st = tower.stats
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        if not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        x, y = target.future_position(0.4)
        self.puddles.append([x, y, st["radius"], st["dps"], st["duration"], st["duration"],
                             st.get("shred", 0), tower])
        self.effects.burst(x, y, S.ACID, 10, 120, 0.35, 3)
        self.effects.muzzle(tower.x, tower.y, tower.angle)
        self.audio.play("shoot")

    # ---- Phase 5 towers ----------------------------------------------------------------
    def _behavior_flak(self, tower, dt):
        """Flak Cannon: a burst of shells that burst near flyers and splash every flyer
        around them. Hailstorm can also hit ground aliens."""
        st = tower.stats
        hits_ground = bool(st.get("hits_ground"))
        candidates = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, True)
                      if e.flying or hits_ground]
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        if not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        for i in range(int(st.get("burst", 1))):
            self.flak_volleys.append([i * 0.12, tower, target, st["damage"], st["splash"]])

    def update_flak(self, dt):
        live = []
        for v in self.flak_volleys:
            v[0] -= dt
            if v[0] > 0:
                live.append(v)
                continue
            _d, tower, target, damage, splash = v
            if tower not in self.towers:
                continue
            st = tower.stats
            hits_ground = bool(st.get("hits_ground"))
            if not target.targetable:   # target died mid-burst: pick another
                pool = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, True)
                        if e.flying or hits_ground]
                target = pick_target(tower, pool)
                if target is None:
                    continue
            tower.aim_at(target.pos.x, target.pos.y)
            x = target.pos.x + random.uniform(-10, 10)
            y = target.pos.y + random.uniform(-10, 10)
            r2 = splash * splash
            for e in list(self.enemies.enemies):
                if not e.targetable or e.hidden or not (e.flying or hits_ground):
                    continue
                if dist_sq(x, y, e.pos.x, e.pos.y) <= r2 + e.radius * e.radius:
                    self.enemies.damage(e, damage, quiet=True, source=tower)
                    if st.get("stun"):
                        e.apply_stun(st["stun"])
            self.effects.muzzle(tower.x + math.cos(tower.angle) * 16, tower.y + math.sin(tower.angle) * 16,
                                tower.angle)
            self.effects.burst(x, y, S.STEEL_LIGHT, 8, 140, 0.35, 3)
            self.effects.burst(x, y, S.ORANGE, 5, 90, 0.25, 3)
            self.effects.ring(x, y, splash, (90, 90, 100), 0.25, width=2)
            self.audio.play("shoot")
        self.flak_volleys = live

    def _behavior_ion(self, tower, dt):
        """Ion Cannon: charges for a long time, then fires one blast down every lane of the
        path. Fires as soon as it's charged and an alien is in range."""
        st = tower.stats
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
        tower.target = candidates[0] if candidates else None
        if not candidates or not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        hits_air = bool(st.get("hits_air"))
        width2 = 26 * 26
        hit = 0
        for e in list(self.enemies.enemies):
            if not e.targetable or e.hidden or (e.flying and not hits_air):
                continue
            if e.flying or self._near_route(e.pos.x, e.pos.y, width2):
                self.enemies.damage(e, st["damage"], ignore_armor=True, source=tower)
                if st.get("stun"):
                    e.apply_stun(st["stun"])
                hit += 1
        routes = [list(r) for r in self.level.routes]
        self.ion_blasts.append([routes, 0.6, 0.6, tower.branch, (tower.x, tower.y)])
        self.effects.flash((180, 230, 255), 0.15)
        self.effects.shake(0.25)
        self.effects.ring(tower.x, tower.y, 40, S.CYAN, 0.4, width=4)
        if hit:
            self.effects.floating_text(tower.x, tower.y - 26, f"ION x{hit}", S.CYAN, 22)
        self.audio.play("rail")

    def _near_route(self, x, y, width2):
        for route in self.level.routes:
            for (x1, y1), (x2, y2) in zip(route, route[1:]):
                dx, dy = x2 - x1, y2 - y1
                L = dx * dx + dy * dy
                t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L))
                if dist_sq(x, y, x1 + dx * t, y1 + dy * t) <= width2:
                    return True
        return False

    @property
    def tar_pits(self):
        return [t for t in self.towers if t.behavior == "tar" and t.fsm.name == "active"]

    def ignite(self, pit):
        if getattr(pit, "ignite_timer", 0) <= 0:
            self.effects.burst(pit.x, pit.y, S.ORANGE, 14, 120, 0.5, 4)
        pit.ignite_timer = pit.stats.get("ignite_time", 4.0)

    def _behavior_tar(self, tower, dt):
        """Tar Pit: slows ground aliens standing in it. A burning alien or a Flamer
        sets it on fire, burning everything in it. Deep Tar roots aliens now and then."""
        st = tower.stats
        tower.target = None
        inside = self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
        tower.ignite_timer = max(0.0, getattr(tower, "ignite_timer", 0.0) - dt)
        burning = tower.ignite_timer > 0 or st.get("always_burning")
        root = st.get("root") and tower.cooldown.ready and inside
        if root:
            tower.cooldown.trigger()
            self.effects.ring(tower.x, tower.y, tower.range, (60, 50, 40), 0.4, width=3)
        for e in inside:
            e.apply_slow(st["slow"], 0.3)
            if root:
                e.apply_stun(st["root"])
            if not burning and e.burn_timer > 0:
                self.ignite(tower)
                burning = True
            if burning:
                self.enemies.damage(e, st["burn_dps"] * dt, ignore_armor=True, quiet=True, source=tower)
        if burning and random.random() < dt * 14:
            a = random.random() * math.tau
            r = random.random() * tower.range * 0.8
            p = self.effects.particles.acquire()
            p.spawn(tower.x + math.cos(a) * r, tower.y + math.sin(a) * r, random.uniform(-10, 10),
                    random.uniform(-60, -30), 0.5, random.choice((S.ORANGE, S.ENERGY, S.RED)), 3, drag=1.0)

    def _behavior_chrono(self, tower, dt):
        """Chrono Spire: every few seconds, rewinds the lead alien(s) back along the path
        by the distance they'd walk in `rewind` seconds. Bosses and Juggernauts can't be
        moved, so they're slowed instead. Stasis Lock also freezes its target."""
        st = tower.stats
        candidates = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range,
                                                                 tower.can_target_air)
                      if not getattr(e, "rewound", 0) > 0]
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None or not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        picked = [target] + sorted((e for e in candidates if e is not target),
                                   key=lambda e: -e.progress)[:int(st.get("targets", 1)) - 1]
        for e in picked:
            before = (e.pos.x, e.pos.y)
            dist = e.base_speed * st["rewind"]
            if e.flying:
                v = pygame.math.Vector2(e.vel)
                if v.length_squared() > 1:
                    e.knockback(dist, tuple(-v.normalize()))
            else:
                e.knockback(dist)
            moved = dist_sq(before[0], before[1], e.pos.x, e.pos.y) > 4
            if not moved:   # immune to being moved: slow it hard instead
                e.apply_slow(0.5, st["rewind"])
            if st.get("stasis"):
                e.apply_stun(st["stasis"])
            e.rewound = 1.0   # don't grab the same alien twice in a row
            self.effects.beam(before[0], before[1], e.pos.x, e.pos.y, CHRONO, 0.35)
            self.effects.ring(e.pos.x, e.pos.y, 18, CHRONO, 0.4, width=2)
            self.effects.ring(before[0], before[1], 12, CHRONO, 0.3, width=1)
            self.effects.lightning([(tower.x, tower.y - 8), before], CHRONO)
        self.effects.ring(tower.x, tower.y, tower.range, CHRONO, 0.45, width=2)
        self.audio.play("shield")

    def update_rewound(self, dt):
        for e in self.enemies.enemies:
            if getattr(e, "rewound", 0) > 0:
                e.rewound -= dt

    def update_shields(self, dt):
        """Shield Projectors give every tower in range (themselves included) a shield pool.
        The strongest projector covering a tower sets its size and recharge speed."""
        projectors = [t for t in self.towers if t.behavior == "shield" and t.fsm.name == "active"]
        for t in self.towers:
            best = None
            for p in projectors:
                if dist_sq(t.x, t.y, p.x, p.y) <= p.range ** 2:
                    if best is None or p.stats["shield"] > best.stats["shield"]:
                        best = p
            h = t.health
            if best is None:
                t.shield_max = 0.0
                h.shield = 0.0
                continue
            st = best.stats
            t.shield_max = float(st["shield"])
            if h.since_hit >= st.get("delay", 3.0) and h.shield < t.shield_max:
                h.shield = min(t.shield_max, h.shield + st.get("regen", 5) * dt)
            h.shield = min(h.shield, t.shield_max)
            if st.get("heal") and not h.is_dead and h.ratio < 1:   # Rapid Recharge
                h.heal(st["heal"] * dt)

    # ---- Phase 5 batch 2 ----------------------------------------------------------------
    def _behavior_decoy(self, tower, dt):
        """Decoy Beacon: every few seconds lures the nearest ground aliens; they stop and
        attack the hologram (see Enemy.blocking_barricade). Hunters chase it from further
        away (Hunter.decoy). Booby Trap shocks whatever is chewing on it."""
        st = tower.stats
        tower.target = None
        tower.exploded = False
        thorns = st.get("thorns", 0)
        if thorns:
            for e in self.enemies.enemies:
                if getattr(e, "lured_by", None) is tower and e.fsm.name == "chew":
                    self.enemies.damage(e, thorns * dt, ignore_armor=True, quiet=True, source=tower)
        if not tower.cooldown.ready:
            return
        pool = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
                if not e.is_boss and getattr(e, "lured_by", None) is None]
        if not pool:
            return
        tower.cooldown.trigger()
        pool.sort(key=lambda e: dist_sq(tower.x, tower.y, e.pos.x, e.pos.y))
        for e in pool[:int(st.get("targets", 4))]:
            e.lured_by = tower
            e.lure_timer = st["lure"]
            self.effects.lightning([(tower.x, tower.y - 6), (e.pos.x, e.pos.y)], S.CYAN, 0.2)
        self.effects.ring(tower.x, tower.y, tower.range, S.CYAN, 0.5, width=2)
        self.audio.play("shield")

    def update_decoys(self):
        """Booby Trap: a destroyed decoy explodes once (it re-arms when repaired)."""
        for t in self.towers:
            if t.behavior == "decoy" and t.health.is_dead and not getattr(t, "exploded", False):
                t.exploded = True
                blast = t.stats.get("blast")
                if blast:
                    self.enemies.splash(t.x, t.y, t.stats["splash"], blast, include_air=False,
                                        knockback=20, source=t)
                    self.effects.explosion(t.x, t.y, S.CYAN, count=30)
                    self.effects.ring(t.x, t.y, t.stats["splash"], S.CYAN, 0.4, width=4)
                    self.effects.shake(0.2)
                    self.audio.play("explode")

    def update_fences(self, dt):
        """Plasma Fence: each pylon links to its nearest pylon in range (Overload Grid: to
        every pylon in range). Aliens touching a beam take damage every frame."""
        pylons = [t for t in self.towers if t.behavior == "fence" and t.fsm.name == "active"]
        links = {}
        for a in pylons:
            near = sorted((b for b in pylons if b is not a and dist_sq(a.x, a.y, b.x, b.y) <= a.range ** 2),
                          key=lambda b: dist_sq(a.x, a.y, b.x, b.y))
            for b in (near if a.stats.get("link_all") else near[:1]):
                links[frozenset((id(a), id(b)))] = (a, b)
        self.fence_links = list(links.values())
        for a, b in self.fence_links:
            sa, sb = a.stats, b.stats
            dps = (sa["dps"] + sb["dps"]) / 2
            slow = max(sa.get("slow", 0), sb.get("slow", 0))
            air = sa.get("hits_air") or sb.get("hits_air")
            length = math.hypot(b.x - a.x, b.y - a.y)
            for e in self.collision.enemies_in_range((a.x + b.x) / 2, (a.y + b.y) / 2, length / 2 + 24, air):
                if e.hit_test_segment(a.x, a.y, b.x, b.y, pad=2):
                    owner = a if sa["dps"] >= sb["dps"] else b
                    self.enemies.damage(e, dps * dt, ignore_armor=True, quiet=True, source=owner)
                    if slow:
                        e.apply_slow(slow, 0.3)
                    if random.random() < dt * 8:
                        self.effects.sparks(e.pos.x, e.pos.y, (255, 120, 230))

    def fence_partner(self, x, y, rng):
        """Nearest active pylon within rng of (x, y): the build preview shows the link."""
        best, best_d = None, rng * rng
        for t in self.towers:
            if t.behavior == "fence" and t.fsm.name == "active":
                d = dist_sq(x, y, t.x, t.y)
                if d <= best_d:
                    best, best_d = t, d
        return best

    def _behavior_hacker(self, tower, dt):
        """Hacker Spire: takes over the lead ground alien(s) for a few seconds. A hacked
        alien walks back along the path and hurts every alien it touches; towers and
        Vance ignore it. Bosses, Juggernauts and flyers can't be hacked."""
        st = tower.stats
        pool = [e for e in self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
                if not e.is_boss and e.kind != "juggernaut" and not e.flying]
        target = pick_target(tower, pool)
        tower.target = target
        if target is None or not tower.cooldown.ready:
            return
        tower.aim_at(target.pos.x, target.pos.y)
        tower.cooldown.trigger()
        pool.sort(key=lambda e: -e.progress)
        picked = [target] + [e for e in pool if e is not target][:int(st.get("targets", 1)) - 1]
        for e in picked:
            e.hacked = st["hack_time"]
            e.hacker = tower
            e.lured_by = None
            if e not in self.hacked:
                self.hacked.append(e)
            self.effects.lightning([(tower.x, tower.y - 8), (e.pos.x, e.pos.y)], HACK, 0.25)
            self.effects.floating_text(e.pos.x, e.pos.y - 22, "HACKED", HACK, 18)
        self.audio.play("zap")

    def _behavior_brood(self, tower, dt):
        """Brood Turret: hatches tame aliens on the path; they walk back toward the spawn biting
        every alien they touch (the Hacker Spire's code), then wither away."""
        st = tower.stats
        tower.target = None
        if not tower.cooldown.ready or not self.collision.enemies_in_range(tower.x, tower.y, tower.range, False):
            return
        tower.cooldown.trigger()
        from ..entities.enemy_p5 import route_distance
        route = min(self.level.routes, key=lambda r: min((x - tower.x) ** 2 + (y - tower.y) ** 2 for x, y in r))
        d = route_distance(route, tower.x, tower.y)
        for i in range(int(st.get("hatch", 2))):
            e = self.enemies.spawn(st.get("spawn", "skitter"), 1, start_distance=max(0.0, d - i * 10), route=route)
            e.hacked = st.get("life", 8.0)
            e.hacker = tower
            e.tame = True
            e.reward = e.score = 0
            self.hacked.append(e)
        self.effects.burst(tower.x, tower.y, S.ALIEN_GREEN, 12, 100, 0.4, 3)

    def update_hacked(self, dt):
        live = []
        for e in self.hacked:
            if not e.targetable:
                continue
            e.hacked -= dt
            owner = e.hacker
            st = owner.stats
            if e.hacked <= 0 and getattr(e, "tame", False):   # brood hatchlings wither away
                e.remove = True
                self.effects.burst(e.pos.x, e.pos.y, S.ALIEN_GREEN, 6, 60, 0.3, 2)
                continue
            if e.hacked <= 0:
                blast = st.get("blast")
                if blast and owner in self.towers:   # Virus
                    self.enemies.splash(e.pos.x, e.pos.y, st["splash"], blast, include_air=False,
                                        knockback=10, source=owner)
                    self.enemies.damage(e, blast, ignore_armor=True, source=owner)
                    self.effects.explosion(e.pos.x, e.pos.y, HACK, count=20)
                    self.audio.play("explode")
                continue
            e.stun_timer = max(e.stun_timer, 0.05)          # its own brain is offline...
            e.knockback(e.base_speed * dt)                 # ...and it marches back toward spawn
            reach = e.radius + 12
            for o in self.enemies.enemies:
                if o is e or not o.targetable or o.hidden or o.flying or getattr(o, "hacked", 0) > 0:
                    continue
                if dist_sq(e.pos.x, e.pos.y, o.pos.x, o.pos.y) <= (reach + o.radius) ** 2:
                    self.enemies.damage(o, st["contact_dps"] * dt, ignore_armor=True, quiet=True,
                                        source=owner)
            live.append(e)
        self.hacked = live

    def _behavior_magnet(self, tower, dt):
        """Magnet Coil: strips armor from everything in range and chips it. Juggernauts are
        immune to slows, but the coil drags on their plating anyway."""
        st = tower.stats
        inside = self.collision.enemies_in_range(tower.x, tower.y, tower.range, False)
        tower.target = inside[0] if inside else None
        for e in inside:
            e.corrode(st["shred"], 0.3)
            if st.get("dps"):
                self.enemies.damage(e, st["dps"] * dt * tower.fire_rate_mult, ignore_armor=True,
                                    quiet=True, source=tower)
            if e.kind == "juggernaut" or e.is_boss:
                amount = st["jugg_slow"] * (0.5 if e.is_boss else 1.0)
                e.slow = max(e.slow, amount)            # bypasses Juggernaut slow immunity
                e.slow_timer = max(e.slow_timer, 0.3)
            elif st.get("slow"):
                e.apply_slow(st["slow"], 0.3)
            drain = st.get("shield_drain", 0)
            if drain:
                e.aura_shield = 0.0
                if e.shield > 0:
                    e.shield = max(0.0, e.shield - drain * dt)
        if inside and int(tower.pulse_t * 2) != int((tower.pulse_t - dt) * 2):
            self.effects.ring(tower.x, tower.y, tower.range, (200, 80, 80), 0.4, width=2)

    def render_overlays(self, screen, offset):
        """Drawn over the aliens: hacked markers."""
        for e in self.enemies.enemies:   # lured aliens attacking a Decoy Beacon
            d = getattr(e, "lured_by", None)
            if d is not None and e.fsm.name == "chew" and e.targetable:
                pygame.draw.line(screen, (120, 230, 255), (e.pos.x + offset[0], e.pos.y + offset[1]),
                                 (d.x + offset[0], d.y + offset[1]), 1)
        for e in self.hacked:
            draw_hack(screen, (e.pos.x + offset[0], e.pos.y + offset[1]), e.radius,
                      e.hacked / max(0.1, e.hacker.stats["hack_time"]))

    # ---- Phase 5 batch 3 ----------------------------------------------------------------
    def _behavior_lightning(self, tower, dt):
        """Lightning Rod: builds charge (much faster while weather is on the map), then calls
        down a bolt that chains through nearby aliens for the stored charge."""
        st = tower.stats
        rate = st["charge_rate"] * (st.get("weather_mult", 4) if self.weather_kind else 1.0)
        tower.charge = min(st["max_charge"], getattr(tower, "charge", 0.0) + rate * dt * tower.fire_rate_mult)
        if self.weather_kind and random.random() < dt * 2:
            self.effects.lightning([(tower.x, tower.y - 40), (tower.x, tower.y - 8)], S.ENERGY, 0.08)
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        target = pick_target(tower, candidates)
        tower.target = target
        if target is None or tower.charge < st["max_charge"]:
            return
        hit = [target]
        while len(hit) < int(st.get("chain", 3)):
            last = hit[-1]
            near = [e for e in self.collision.enemies_in_range(last.pos.x, last.pos.y, 90, True)
                    if e not in hit]
            if not near:
                break
            hit.append(min(near, key=lambda e: dist_sq(last.pos.x, last.pos.y, e.pos.x, e.pos.y)))
        damage = tower.charge
        for e in hit:
            self.enemies.damage(e, damage, ignore_armor=True, source=tower)
            if st.get("stun"):
                e.apply_stun(st["stun"])
            damage *= 0.8
        tower.charge = 0.0
        sky = (target.pos.x + random.uniform(-30, 30), -10)
        self.effects.lightning([sky, (target.pos.x, target.pos.y)], S.WHITE, 0.25)
        self.effects.lightning([(e.pos.x, e.pos.y) for e in hit], S.ENERGY, 0.25)
        self.effects.lightning([(tower.x, tower.y - 10), sky], S.ENERGY, 0.15)
        self.effects.flash((255, 250, 210), 0.08)
        self.effects.shake(0.15)
        self.audio.play("zap")

    def on_enemy_killed(self, enemy, **_):
        """Bio-Labs pay Energy (the best lab in range pays once); Uplink Dishes cut the
        Orbital Strike cooldown."""
        x, y = enemy.pos.x, enemy.pos.y
        pay, cut = 0, 0.0
        for t in self.towers:
            if t.fsm.name != "active" or dist_sq(x, y, t.x, t.y) > t.range * t.range:
                continue
            if "per_kill" in t.stats:   # Bio-Lab, Bio-Refinery
                pay = max(pay, int(t.stats["per_kill"]))
            elif t.behavior == "uplink":
                cut = max(cut, t.stats["cut"])
        if pay:   # Bio-Labs harvest Biomass
            if self.economy is not None:
                self.economy.add_biomass(pay, x, y)
            else:
                self.session.energy += pay
        if cut and self.player is not None and not self.player.orbital.ready:
            self.player.orbital.remaining = max(0.0, self.player.orbital.remaining - cut)

    def update_support(self, dt):
        """Bio-Lab vulnerability, Overclocker burn, Uplink orbital bonuses and Bait Pod regen."""
        for e in self.enemies.enemies:
            e.vuln = 0.0
        twin, dmg_mult, rad_mult = False, 1.0, 1.0
        for t in self.towers:
            if t.fsm.name != "active":
                continue
            st = t.stats
            b = t.behavior
            if b == "biolab" and st.get("vuln"):
                for e in self.collision.enemies_in_range(t.x, t.y, t.range, True):
                    e.vuln = max(e.vuln, st["vuln"])
            elif b == "overclock" and st.get("burn"):
                for o in self.towers:   # only towers that are actually working get hot
                    if (o is not t and o.target is not None and o.fsm.name == "active"
                            and dist_sq(o.x, o.y, t.x, t.y) <= t.range * t.range):
                        o.health.damage(st["burn"] * dt, ignore_armor=True)
            elif b == "uplink":
                twin = twin or bool(st.get("extra_charge"))
                dmg_mult = max(dmg_mult, st.get("orbital_mult", 1.0))
                rad_mult = max(rad_mult, st.get("radius_mult", 1.0))
            elif b == "bait":
                if t.health.since_hit > 1.0:
                    t.health.heal(st.get("regen", 0) * dt)
                spores = st.get("spores")
                if spores and t.health.since_hit < 0.05 and t.cooldown.ready:
                    t.cooldown.trigger()
                    for e in self.collision.enemies_in_range(t.x, t.y, t.range, False):
                        self.enemies.damage(e, spores, ignore_armor=True, quiet=True, source=t)
                    self.effects.burst(t.x, t.y, (170, 220, 90), 16, 120, 0.5, 3)
                    self.effects.ring(t.x, t.y, t.range, (170, 220, 90), 0.35, width=2)
        p = self.player
        if p is not None:
            p.uplink_damage_mult, p.uplink_radius_mult = dmg_mult, rad_mult
            if not twin:
                p.spare_charges, p.spare_progress = 0, 0.0
            elif p.orbital.ready and p.spare_charges < 1:   # the second charge fills after the first
                p.spare_progress += dt / max(1.0, p.orbital.duration)
                if p.spare_progress >= 1.0:
                    p.spare_charges, p.spare_progress = 1, 0.0

    # ---- Phase 5 tower systems ----------------------------------------------------------------
    ATTACK_STATS = ("damage", "dps")

    def neighbors(self, t):
        """Towers on the 8 tiles around t."""
        return [o for o in self.towers if o is not t and abs(o.tx - t.tx) <= 1 and abs(o.ty - t.ty) <= 1]

    def refresh_topology(self):
        """Recompute adjacency synergies for every tower (after anything is built, sold,
        moved, upgraded or fused) and rebuild each tower's stat mods."""
        rules = self.systems.get("synergies", [])
        for t in self.towers:
            kinds = {o.kind for o in self.neighbors(t)} | {p for o in self.neighbors(t)
                                                           for p in getattr(o, "fusion_parts", ())}
            own = {t.kind} | set(getattr(t, "fusion_parts", ()))
            mods, texts = {}, []
            for r in rules:
                if r["tower"] in own and r["partner"] in kinds:
                    for k, (mult, add) in r["mods"].items():
                        m = mods.setdefault(k, [1.0, 0.0])
                        m[0] *= mult
                        m[1] += add
                    texts.append(r["text"])
            t.mod_sources["adj"] = {"mods": mods}
            if self.features is not None:
                src, more = self.features.terrain_mods(t)
                t.mod_sources["terrain"] = src
                texts += more
            if self.research_source:
                t.mod_sources["research"] = self.research_source
            lvl = self.mastery.get(t.kind if not t.fusion else t.fusion_parts[0], 0)
            if lvl:
                from .meta import MASTERY_BONUS
                t.mod_sources["mastery"] = {"mods": {"damage": [1.0 + MASTERY_BONUS[lvl], 0.0]}}
            t.synergies = texts
            t.refresh_mods()

    def synergy_partners(self, kind):
        """[(partner kind, text)] for tooltips."""
        return [(r["partner"], r["text"]) for r in self.systems.get("synergies", []) if r["tower"] == kind]

    def update_power(self):
        """Generators give every tower in range (not other generators) a fire-rate bonus;
        Grid Hub also extends range. An EMP'd or broken generator powers nothing."""
        gens = [g for g in self.towers if g.behavior == "generator" and g.fsm.name == "active"]
        for t in self.towers:
            power, boost, src = 0.0, 0.0, None
            if t.behavior != "generator":
                for g in gens:
                    if dist_sq(t.x, t.y, g.x, g.y) <= g.range * g.range and g.stats["power"] > power:
                        power, src = g.stats["power"], g
                        boost = max(boost, g.stats.get("range_boost", 0.0))
            t.power = power
            t.power_source = src
            if boost:
                t.range_buff = max(t.range_buff, boost)

    def promote_veteran(self, t):
        """Rank 3: the tower earns a name and a random trait."""
        sysd = self.systems
        if t.vet_name or not sysd.get("veteran_names"):
            return
        used = {o.vet_name for o in self.towers}
        names = [n for n in sysd["veteran_names"] if n not in used] or sysd["veteran_names"]
        t.vet_name = random.choice(names)
        t.vet_trait = random.choice(list(sysd["veteran_traits"]))
        trait = sysd["veteran_traits"][t.vet_trait]
        t.mod_sources["trait"] = trait
        if trait.get("hp_mult"):
            t.health.max_hp *= trait["hp_mult"]
            t.health.hp = t.health.max_hp
        t.refresh_mods()
        self.events.publish("meta_count", stat="veterans")
        self.events.publish("toast", text=f'{t.name} is now "{t.vet_name}" ({trait["name"]}: {trait["desc"]})',
                            color=S.ENERGY)

    def socket_chip(self, t, chip):
        inv = self.session.chips
        if t is None or inv.get(chip, 0) <= 0 or len(t.chips) >= t.chip_slots:
            self.audio.play("error")
            return False
        inv[chip] -= 1
        info = self.systems["chips"][chip]
        t.chips.append(chip)
        t.mod_sources[f"chip{len(t.chips) - 1}"] = info
        if info.get("hp_mult"):
            t.health.max_hp *= info["hp_mult"]
            t.health.hp *= info["hp_mult"]
        t.refresh_mods()
        self.effects.ring(t.x, t.y, 26, tuple(info["color"]), 0.4, width=3)
        self.audio.play("upgrade")
        self.events.publish("toast", text=f"{info['name']} socketed into {t.name}", color=tuple(info["color"]))
        return True

    def can_stance(self, t):
        return t is not None and any(k in t.base_stats for k in self.ATTACK_STATS) and not t.walkable

    def toggle_stance(self, t):
        if not self.can_stance(t):
            self.events.publish("toast", text="This tower has no stance", color=S.TEXT_DIM)
            return
        order = [None, "focus", "suppress"]
        t.stance = order[(order.index(t.stance) + 1) % 3]
        if t.stance:
            info = self.systems["stances"][t.stance]
            t.mod_sources["stance"] = {"mods": info["mods"]}
            self.events.publish("toast", text=f"Stance: {info['name']} ({info['desc']})", color=S.CYAN)
        else:
            t.mod_sources.pop("stance", None)
            self.events.publish("toast", text="Stance: Normal", color=S.CYAN)
        t.refresh_mods()

    # relocation (build phase only; PlayScene checks the phase)
    def relocate_fee(self, t):
        return max(10, int(t.spent * self.systems.get("relocate_fee", 0.15)))

    def start_relocate(self, t):
        if t is None:
            return False
        self.relocating = t
        self.build_kind = None
        self.events.publish("toast", text=f"Move {t.name}: click a tile ({self.relocate_fee(t)} E). R-click cancels",
                            color=S.CYAN)
        return True

    def try_relocate(self, tx, ty):
        t = self.relocating
        if t is None:
            return False
        fee = self.relocate_fee(t)
        self.level.vacate(t.tx, t.ty)          # check the new tile as if t weren't there
        self.build_kind = t.kind if t.kind in self.data else None
        problem = self.placement_problem(tx, ty) if self.build_kind else (
            None if self.level.is_buildable(tx, ty) and not self.level.placement_blocks_route(tx, ty)
            else "Can't build there")
        self.build_kind = None
        if problem is None and self.session.energy < fee:
            problem = "Not enough Energy"
        if problem:
            self.level.occupy(t.tx, t.ty, t)
            self.events.publish("toast", text=problem, color=S.RED)
            self.audio.play("error")
            return False
        self.session.energy -= fee
        self.effects.ring(t.x, t.y, 20, S.STEEL_LIGHT, 0.3)
        t.tx, t.ty = tx, ty
        t.x, t.y = tx * S.TILE + S.TILE / 2, ty * S.TILE + S.TILE / 2
        self.level.occupy(tx, ty, t)
        t.__dict__.pop("drones", None)
        self.relocating = None
        self.effects.ring(t.x, t.y, 24, S.CYAN, 0.3)
        self.audio.play("build")
        self.refresh_topology()
        return True

    # fusion (Endless and Siege Run)
    def fusion_options(self, t):
        """[(fusion id, partner tower)] for a maxed, unbranched tower next to its partner."""
        if t is None or not self.allow_fusion or t.fusion or t.branch is not None or t.can_upgrade:
            return []
        out = []
        for fid, f in self.systems.get("fusions", {}).items():
            if t.kind not in f["parts"]:
                continue
            other = [p for p in f["parts"] if p != t.kind][0]
            for o in self.neighbors(t):
                if o.kind == other and not o.fusion and o.branch is None and not o.can_upgrade:
                    out.append((fid, o))
                    break
        return out

    def fuse(self, t, fid, partner):
        cost = self.systems.get("fusion_cost", 150)
        if self.session.energy < cost:
            self.events.publish("toast", text="Not enough Energy", color=S.RED)
            self.audio.play("error")
            return False
        f = self.systems["fusions"][fid]
        self.session.energy -= cost
        stats = dict(f["stats"], upgrade_cost=0)
        data = {"name": f["name"], "behavior": f["behavior"], "cost": t.spent + partner.spent + cost,
                "hp": max(t.data.get("hp", 100), partner.data.get("hp", 100)) * 1.5,
                "can_target_air": f.get("can_target_air", t.can_target_air or partner.can_target_air),
                "description": f["desc"], "tiers": [stats], "category": t.data.get("category")}
        for c in partner.chips:   # the partner's chips come back to the inventory
            self.session.chips[c] = self.session.chips.get(c, 0) + 1
        self.towers.remove(partner)
        self.level.vacate(partner.tx, partner.ty)
        t.kind = f"fusion_{fid}"
        t.fusion = fid
        t.fusion_parts = tuple(f["parts"])
        t.data, t.name, t.behavior = data, f["name"], f["behavior"]
        t.tier, t.branch = 0, None
        t.can_target_air = data["can_target_air"]
        t.spent = data["cost"]
        t.health.reset(data["hp"])
        t.cooldown.duration = t._interval()
        t.__dict__.pop("drones", None)
        t.__dict__.pop("locks", None)
        if self.selected is partner:
            self.selected = t
        self.effects.ring(t.x, t.y, 40, S.MAGENTA, 0.6, width=5)
        self.effects.burst(t.x, t.y, S.ENERGY, 30, 200, 0.6, 4)
        self.audio.play("upgrade")
        self.events.publish("toast", text=f"Fusion: {f['name']}!", color=S.MAGENTA)
        self.events.publish("meta_count", stat="fusions")
        self.refresh_topology()
        return True

    def render_power(self, screen, offset):
        """Cables from each Generator to the towers it powers, with a pulse running along."""
        t_now = pygame.time.get_ticks() / 1000
        for t in self.towers:
            g = getattr(t, "power_source", None)
            if g is None or t.power <= 0:
                continue
            a = (g.x + offset[0], g.y + offset[1])
            b = (t.x + offset[0], t.y + offset[1])
            pygame.draw.line(screen, (120, 100, 30), a, b, 1)
            k = (t_now * 1.5 + (t.tx * 7 + t.ty) * 0.13) % 1.0
            pygame.draw.circle(screen, S.ENERGY, (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k)), 2)

    def update_puddles(self, dt):
        for p in self.puddles:
            p[4] -= dt
            x, y, radius, dps, _left, _total, shred, owner = p
            for e in self.collision.enemies_in_range(x, y, radius, False):
                self.enemies.damage(e, dps * dt, ignore_armor=True, quiet=True, source=owner)
                if shred:
                    e.corrode(shred, 1.0)
        self.puddles = [p for p in self.puddles if p[4] > 0 and p[7] in self.towers]

    def _behavior_repair(self, tower, dt):
        """Repair Bay: heals every tower in range, including broken ones."""
        tower.target = None
        heal = tower.stats.get("heal", 0) * dt
        r2 = tower.range ** 2
        healing = False
        for t in self.towers:
            if t is not tower and t.health.ratio < 1 and dist_sq(t.x, t.y, tower.x, tower.y) <= r2:
                t.health.heal(heal)
                healing = True
        if healing and int(tower.pulse_t * 2) != int((tower.pulse_t - dt) * 2):
            self.effects.ring(tower.x, tower.y, tower.range, S.GREEN, 0.5, width=2)

    def _behavior_shockwave(self, tower, dt):
        """Sonic Disruptor: a shockwave hits every ground alien in range and stuns it."""
        st = tower.stats
        candidates = self.collision.enemies_in_range(tower.x, tower.y, tower.range, tower.can_target_air)
        tower.target = candidates[0] if candidates else None
        if not candidates or not tower.cooldown.ready:
            return
        tower.cooldown.trigger()
        for e in candidates:
            self.enemies.damage(e, st["damage"], ignore_armor=bool(st.get("pierce_armor")), source=tower)
            e.apply_stun(st.get("stun", 0))
            if st.get("pull"):   # Quake Engine
                e.knockback(st["pull"])
        self.effects.ring(tower.x, tower.y, tower.range, S.STEEL_LIGHT, 0.35, width=3)
        self.effects.ring(tower.x, tower.y, tower.range * 0.6, S.WHITE, 0.25, width=2)
        self.effects.shake(0.04)
        self.audio.play("explode")

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
        hasters = [t for t in self.towers if t.stats.get("haste") and t.fsm.name == "active"]
        for t in self.towers:
            best, dmg, haste = 0.0, 0.0, 0.0
            if t.behavior != "support":
                for r in relays:
                    if dist_sq(t.x, t.y, r.x, r.y) <= r.stats["range"] ** 2:
                        best = max(best, r.stats.get("buff", 0.0))
                        dmg = max(dmg, r.stats.get("damage_buff", 0.0))
            for h in hasters:   # Overclock Station
                if h is not t and dist_sq(t.x, t.y, h.x, h.y) <= h.range ** 2:
                    haste = max(haste, h.stats["haste"])
            t.range_buff = best
            t.damage_buff = dmg
            t.haste = haste

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
                self.effects.explosion(x, y, S.ORANGE, count=26)   # (splash also chips rocks, see MapFeatures)
                self.effects.ring(x, y, splash, S.ORANGE, 0.35, width=3)
                self.effects.shake(0.12)
                self.audio.play("explode")
        self.shells = [s for s in self.shells if s[2] > 0]

    # ---- loop ----------------------------------------------------------------------
    def on_update(self, dt):
        self.update_buffs()
        self.update_power()
        self.update_barricades()
        for t in self.towers:
            t.update(dt)
        self.update_shells(dt)
        self.update_mines()
        self.update_puddles(dt)
        self.update_flak(dt)
        self.update_shields(dt)
        self.update_rewound(dt)
        self.update_decoys()
        self.update_fences(dt)
        self.update_hacked(dt)
        self.update_support(dt)
        for b in self.ion_blasts:
            b[1] -= dt
        self.ion_blasts = [b for b in self.ion_blasts if b[1] > 0]

    def on_render(self, screen, assets, offset):
        blink = (pygame.time.get_ticks() // 300) % 2
        for x, y, radius, _dps, left, total, _sh, owner in self.puddles:
            draw_puddle(screen, (x + offset[0], y + offset[1]), radius, min(1.0, left / 0.6),
                        min(owner.tier, 2) if owner.branch is None else 2)
        self.render_power(screen, offset)
        for a, b in self.fence_links:
            draw_fence(screen, (a.x + offset[0], a.y + offset[1]), (b.x + offset[0], b.y + offset[1]),
                       max(a.tier, b.tier) if a.branch is None and b.branch is None else 3)
        for x, y, _d, _s, owner in self.mines:   # mines/drones/shells match their tower's tier
            draw_mine(screen, (x + offset[0], y + offset[1]), min(owner.tier, 2), blink)
        for t in self.towers:
            t.render(screen, assets, offset)
            drones = t.__dict__.get("drones", [])
            if drones:
                name = f"drone_t{min(t.tier, 2)}"
                for d in drones:
                    assets.blit_centered(screen, name, (d["x"] + offset[0], d["y"] + offset[1]),
                                         angle=-math.degrees(d["a"]))
        for t in self.towers:
            if t.behavior == "beam" and t.fsm.name == "active":
                for e in getattr(t, "beam_targets", []):
                    draw_beam(screen, (t.x + offset[0], t.y + offset[1]), (e.pos.x + offset[0], e.pos.y + offset[1]),
                              t.locks.get(e, 0.0) / max(0.1, t.stats.get("ramp_time", 3.0)), t.branch)
                for m, e in getattr(t, "mirror_beams", []):
                    draw_beam(screen, (t.x + offset[0], t.y + offset[1]), (m.x + offset[0], m.y + offset[1]),
                              0.3, t.branch)
                    draw_beam(screen, (m.x + offset[0], m.y + offset[1]), (e.pos.x + offset[0], e.pos.y + offset[1]),
                              0.3, t.branch)
        for routes, left, total, branch, origin in self.ion_blasts:
            draw_ion(screen, routes, origin, left / total, branch, offset)
        for x, y, left, total, sx, sy, _d, splash, owner in self.shells:
            k = 1 - left / total
            px = sx + (x - sx) * k + offset[0]
            py = sy + (y - sy) * k - math.sin(k * math.pi) * 90 + offset[1]
            tier = min(owner.tier, 2)
            pygame.draw.circle(screen, (40, 30, 30), (int(x + offset[0]), int(y + offset[1])),
                               int(4 + 8 * k), 1)
            pygame.draw.circle(screen, (22, 22, 34), (int(px), int(py)), 6 + tier)
            pygame.draw.circle(screen, (S.ORANGE, S.RED, S.ENERGY)[tier], (int(px), int(py)), 4 + tier)
            if tier:
                pygame.draw.circle(screen, S.WHITE, (int(px) - 1, int(py) - 1), tier)
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
        """Green/red tile preview plus range circle while in build mode (or moving a tower)."""
        if self.relocating is not None and mouse[1] < S.MAP_H:
            t = self.relocating
            tx, ty = self.level.world_to_tile(*mouse)
            ok = (self.level.is_buildable(tx, ty) or (t.walkable and self.level.tile_at(tx, ty) == S.T_PATH
                                                      and (tx, ty) not in self.level.occupied))
            color = S.GREEN if ok else S.RED
            rect = pygame.Rect(tx * S.TILE, ty * S.TILE, S.TILE, S.TILE)
            pygame.draw.rect(screen, color, rect, 2)
            pygame.draw.line(screen, S.CYAN, (t.x, t.y), rect.center, 1)
            self.draw_range(screen, rect.centerx, rect.centery, t.range, color)
            ghost = assets.get(f"turret_{t.kind}{t.look}").copy()
            ghost.set_alpha(150)
            screen.blit(ghost, ghost.get_rect(center=rect.center))
            return
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
        if self.data[self.build_kind]["behavior"] == "fence":
            partner = self.fence_partner(rect.centerx, rect.centery, rng)
            if partner is not None:
                draw_fence(screen, rect.center, (partner.x, partner.y), 0)
        ghost = assets.get(f"turret_{self.build_kind}")
        ghost = ghost.copy()
        ghost.set_alpha(150)
        screen.blit(ghost, ghost.get_rect(center=rect.center))

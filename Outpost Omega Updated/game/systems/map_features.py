"""Phase 5 map mechanics.

Always on (driven by the level file):
    high ground (H), resource nodes (R), crystals (K)   tower terrain bonuses (TowerSystem.terrain_mods)
    gates + switches                                     Vance walks onto a switch to open/close its gate
    teleporters                                          pads that jump aliens ahead along the path, and
                                                         carry Vance between the two ends
    vines (Jungle)                                       overgrow a tower (half fire rate) until Vance
                                                         walks up to it
    low gravity (Gas Giant)                              see terrain_mods; Vance slides everywhere

Endless / Siege Run only (the campaign plays as it always has):
    overheat           hot sectors (Magma Forge, Desert Outpost) and Heatwave weather: towers heat up
                       while firing and shut down for a few seconds at max heat; Cryo towers, ice,
                       and rocks/crystals next to them cool them down
    destructible rocks splash damage (mortar shells, missiles, grenades) breaks rocks into build space
    day / night        a 2-minute cycle; at night the map darkens around towers, Vance and the Core,
                       and Cloakers are faster and harder to spot
    map events         rolled at the start of some waves: supply drop, meteor shower, earthquake,
                       wildlife, rising tide
"""
import math
import random

import pygame

from .. import settings as S
from .level_system import BUILDABLE_TILES

HOT_SECTORS = {"sector4", "sector1"}
EVENTS = {"supply_drop": 30, "meteor_shower": 20, "earthquake": 15, "wildlife": 20, "rising_tide": 15}
EVENT_TEXT = {"supply_drop": "Supply drop incoming! Grab the crate.",
              "meteor_shower": "Meteor shower! Watch the red circles.",
              "earthquake": "Earthquake! The ground is shifting.",
              "wildlife": "Wildlife on the field. They bite anyone who gets close.",
              "rising_tide": "The tide is rising! Low ground near the path will flood."}


class MapFeatures:
    DAY, NIGHT = 80.0, 40.0

    def __init__(self, play):
        self.play = play
        lvl = play.level
        self.level = lvl
        self.dynamic = play.endless or play.run is not None   # extra hazards outside the campaign
        data = lvl.data
        weather = play.weather.kind if play.weather else None
        self.overheat = self.dynamic and (lvl.id in HOT_SECTORS or data.get("hot") or weather == "heatwave")
        self.vines = data.get("vines", False)
        self.low_gravity = data.get("low_gravity", False)
        if self.low_gravity:
            lvl.weather_ice = True   # Vance slides around in low gravity
        self.cycle = self.dynamic and not lvl.dark
        self.t = random.uniform(0, self.DAY)
        self.rock_hp = {}
        self.switch_cd = 0.0
        self.tele_cd = 0.0
        self.vine_t = 12.0
        self.meteors = []         # [x, y, t_left]
        self.drops = []           # [x, y, t_left] falling supply crates
        self.critters = []        # dicts
        self.flooded = set()
        self.quake = 0.0
        self.event = None
        play.events.subscribe("wave_started", self.on_wave_started)
        play.events.subscribe("wave_cleared", self.on_wave_cleared)

    # ---- tower terrain bonuses (TowerSystem asks) ----------------------------------
    def terrain_mods(self, t):
        lvl = self.level
        tile = lvl.tile_at(t.tx, t.ty)
        mods, texts = {}, []

        def add(k, mult):
            m = mods.setdefault(k, [1.0, 0.0])
            m[0] *= mult
        if tile == S.T_HIGH:
            add("range", 1.2)
            texts.append("High ground: +20% range")
        if tile == S.T_RESOURCE and t.behavior == "income":
            add("income", 2.0)
            texts.append("Resource node: double income")
        if t.behavior in ("pierce", "beam", "chain", "lightning", "fence", "ion") and any(
                lvl.in_bounds(t.tx + dx, t.ty + dy) and lvl.tile_at(t.tx + dx, t.ty + dy) == S.T_CRYSTAL
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            for k in ("damage", "dps", "max_charge"):
                add(k, 1.25)
            texts.append("Crystal refraction: +25% damage")
        if self.low_gravity and t.behavior in ("mortar", "missile", "flak", "acid"):
            add("range", 1.25)
            add("splash", 1.25)
            texts.append("Low gravity: +25% range and splash")
        if self.night and t.behavior not in ("support",):
            add("range", 0.9)
        return {"mods": mods}, texts

    @property
    def night(self):
        return self.cycle and (self.t % (self.DAY + self.NIGHT)) >= self.DAY

    # ---- waves ---------------------------------------------------------------------
    def on_wave_started(self, number=1, **_):
        if not self.dynamic or number < 4:
            return
        rng = random.Random(hash((self.level.id, number, self.play.seed or 0)))
        if rng.random() > 0.45:
            return
        kinds = list(EVENTS)
        self.event = rng.choices(kinds, [EVENTS[k] for k in kinds])[0]
        self.play.juice.say(EVENT_TEXT[self.event])
        getattr(self, "start_" + self.event)(rng)

    def on_wave_cleared(self, **_):
        if self.flooded:
            self.flooded.clear()
            self.play.ui.toast("The tide recedes", S.CYAN)
        self.critters = []
        self.event = None

    def start_supply_drop(self, rng):
        for _ in range(2):
            tx, ty = self._random_open_tile(rng)
            x, y = self.level.tile_center(tx, ty)
            self.drops.append([x, y, 2.0])

    def start_meteor_shower(self, rng):
        for i in range(10):
            tx, ty = rng.randrange(2, 38), rng.randrange(2, 18)
            x, y = self.level.tile_center(tx, ty)
            self.meteors.append([x, y, 1.5 + i * 0.9])

    def start_earthquake(self, rng):
        lvl = self.level
        cx, cy = rng.randrange(6, 34), rng.randrange(4, 16)
        area = [(x, y) for x in range(cx - 5, cx + 6) for y in range(cy - 3, cy + 4) if lvl.in_bounds(x, y)]
        rocks = [t for t in area if lvl.tile_at(*t) == S.T_BLOCK]
        free = [t for t in area if lvl.tile_at(*t) == S.T_BUILD and t not in lvl.occupied]
        rng.shuffle(free)
        moved = 0
        for (rx, ry), (fx, fy) in zip(rocks, free):
            lvl.tiles[ry][rx] = S.T_BUILD
            lvl.tiles[fy][fx] = S.T_BLOCK
            if not lvl.all_lanes_connected():
                lvl.tiles[ry][rx], lvl.tiles[fy][fx] = S.T_BLOCK, S.T_BUILD
            else:
                moved += 1
        lvl.rebuild_surface()
        if lvl.free_path:
            lvl.recompute_path()
        px, py = lvl.tile_center(cx, cy)
        for t in self.play.towers.towers:
            if abs(t.tx - cx) <= 5 and abs(t.ty - cy) <= 3:
                t.health.damage(20, ignore_armor=True)
        for e in self.play.enemies.enemies:
            if abs(e.pos.x - px) < 180 and abs(e.pos.y - py) < 110:
                e.apply_stun(1.5)
        self.quake = 1.2
        self.play.effects.shake(0.9)
        self.play.audio.play("explode")

    def start_wildlife(self, rng):
        for _ in range(rng.randint(3, 5)):
            tx, ty = self._random_open_tile(rng)
            x, y = self.level.tile_center(tx, ty)
            self.critters.append({"x": x, "y": y, "a": rng.random() * math.tau, "hp": 60, "cd": 0.0,
                                  "life": 45.0})

    def start_rising_tide(self, rng):
        lvl = self.level
        near = set()
        for tiles in lvl.route_tiles:
            for x, y in tiles[2:-2]:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    t = (x + dx, y + dy)
                    if lvl.in_bounds(*t) and lvl.tile_at(*t) in (S.T_BUILD, S.T_RESOURCE):
                        near.add(t)
        self.tide_queue = rng.sample(sorted(near), min(len(near), 40))
        self.tide_t = 0.0

    def _random_open_tile(self, rng):
        lvl = self.level
        for _ in range(200):
            t = (rng.randrange(1, 39), rng.randrange(1, 19))
            if lvl.tile_at(*t) in BUILDABLE_TILES and t not in lvl.occupied:
                return t
        return (20, 10)

    # ---- destructible rocks ------------------------------------------------------------
    def blast(self, x, y, radius, damage):
        """Splash damage from shells, missiles and grenades chips at rocks (Endless / Siege Run)."""
        if not self.dynamic:
            return
        lvl = self.level
        tx0, ty0 = lvl.world_to_tile(x, y)
        r = int(radius // S.TILE) + 1
        broke = False
        for tx in range(tx0 - r, tx0 + r + 1):
            for ty in range(ty0 - r, ty0 + r + 1):
                if not lvl.in_bounds(tx, ty) or lvl.tile_at(tx, ty) != S.T_BLOCK:
                    continue
                cx, cy = lvl.tile_center(tx, ty)
                if (cx - x) ** 2 + (cy - y) ** 2 > (radius + 16) ** 2:
                    continue
                hp = self.rock_hp.get((tx, ty), 160) - damage
                self.rock_hp[(tx, ty)] = hp
                if hp <= 0:
                    lvl.tiles[ty][tx] = S.T_BUILD
                    broke = True
                    self.play.effects.burst(cx, cy, lvl.theme["rock"], 16, 150, 0.6, 4)
        if broke:
            lvl.rebuild_surface()
            if lvl.free_path:
                lvl.recompute_path()
            self.play.juice.say("Rock blasted open: new build space!", "rock", 20)

    # ---- per frame -----------------------------------------------------------------------
    def update(self, dt):
        play = self.play
        self.t += dt
        night = self.night
        if night != getattr(self, "_was_night", False):
            self._was_night = night
            play.towers.refresh_topology()
            play.juice.say("Night is falling. Range is down, watch for Cloakers." if night
                           else "Sun's up.", "night", 30)
        self.switch_cd = max(0.0, self.switch_cd - dt)
        self.tele_cd = max(0.0, self.tele_cd - dt)
        self.quake = max(0.0, self.quake - dt)
        c = play.player.commander
        wave = play.waves.phase == "wave"
        # gates
        if c.alive and self.switch_cd <= 0:
            ctile = self.level.world_to_tile(c.pos.x, c.pos.y)
            for g in self.level.gates:
                if ctile == g["switch"]:
                    self.toggle_gate(g)
                    self.switch_cd = 2.0
        # teleporters
        for a, b in self.level.teleporters:
            pa, pb = self.level.tile_center(*a), self.level.tile_center(*b)
            for e in play.enemies.enemies:
                if (e.targetable and not e.flying and getattr(e, "tele_cd", 0) <= 0
                        and (e.pos.x - pa[0]) ** 2 + (e.pos.y - pa[1]) ** 2 < 14 * 14):
                    from ..entities.enemy_p5 import route_distance
                    d = route_distance(e.follower.waypoints, *pb)
                    if d > e.follower.distance:
                        e.follower.advance(d - e.follower.distance)
                        e.pos.update(e.follower.pos)
                        e.tele_cd = 3.0
                        play.effects.ring(pb[0], pb[1], 18, (200, 110, 240), 0.3)
                if getattr(e, "tele_cd", 0) > 0:
                    e.tele_cd -= dt / max(1, len(self.level.teleporters))
            if c.alive and self.tele_cd <= 0:
                for p, q in ((pa, pb), (pb, pa)):
                    if c.pos.distance_squared_to(p) < 12 * 12:
                        c.pos.update(q[0], q[1] - 20)
                        self.tele_cd = 2.0
                        play.effects.ring(q[0], q[1], 22, S.CYAN, 0.4)
                        break
        # vines (Jungle)
        if self.vines and wave:
            self.vine_t -= dt
            if self.vine_t <= 0 and play.towers.towers:
                self.vine_t = 14.0
                t = random.choice(play.towers.towers)
                t.vined = True
                play.effects.burst(t.x, t.y, (60, 160, 60), 12, 80, 0.4, 3)
                play.juice.say(f"Vines are choking the {t.name}! Walk over to cut them.", "vines", 12)
        for t in play.towers.towers:
            if getattr(t, "vined", False) and c.alive and c.pos.distance_squared_to((t.x, t.y)) < 44 * 44:
                t.vined = False
                play.effects.floating_text(t.x, t.y - 22, "CUT", S.GREEN, 16)
        # overheat
        if self.overheat:
            self.update_heat(dt, wave)
        # events
        for m in self.meteors:
            m[2] -= dt
            if m[2] <= 0:
                self.meteor_hit(m[0], m[1])
        self.meteors = [m for m in self.meteors if m[2] > 0]
        for d in self.drops:
            d[2] -= dt
            if d[2] <= 0:
                for i, kind in enumerate(random.sample(["energy_crystal", "energy_crystal", "weapon", "grenade",
                                                        "repair_kit", "chip"], 3)):
                    play.items.drop(kind, d[0] + (i - 1) * 16, d[1])
                play.effects.ring(d[0], d[1], 24, S.ENERGY, 0.4)
        self.drops = [d for d in self.drops if d[2] > 0]
        self.update_critters(dt)
        if getattr(self, "tide_queue", None) and wave:
            self.tide_t += dt
            while self.tide_queue and self.tide_t > 0.6:
                self.tide_t -= 0.6
                t = self.tide_queue.pop()
                self.flooded.add(t)
                tw = self.level.occupied.get(t)
                if tw is not None:
                    tw.disable(3.0)
        for t in self.flooded:
            tw = self.level.occupied.get(t)
            if tw is not None and tw.disabled_timer < 0.5:
                tw.disable(0.6)
        # night: cloakers are faster
        if self.night:
            for e in play.enemies.enemies:
                if e.kind == "cloaker":
                    e.aura_speed = max(e.aura_speed, 0.3)

    def toggle_gate(self, g):
        lvl = self.level
        new = not g["open"]
        ch = S.T_PATH if new else S.T_WALL
        old = {t: lvl.tile_at(*t) for t in g["tiles"]}
        for tx, ty in g["tiles"]:
            lvl.tiles[ty][tx] = ch
        if not new and not lvl.all_lanes_connected():
            for (tx, ty), c in old.items():
                lvl.tiles[ty][tx] = c
            self.play.ui.toast("That gate is the only way through: it won't close", S.TEXT_DIM)
            return
        g["open"] = new
        lvl.rebuild_surface()
        lvl.recompute_path(announce=True)
        self.play.ui.toast("Gate opened" if new else "Gate closed: aliens rerouted", S.CYAN)
        self.play.audio.play("shield")

    def update_heat(self, dt, wave):
        play = self.play
        vents = getattr(play.vents, "vents", [])
        cryos = [t for t in play.towers.towers if t.behavior == "aura" and t.fsm.name == "active"]
        lvl = self.level
        for t in play.towers.towers:
            heat = getattr(t, "heat", 0.0)
            cool = 0.2
            if any((t.x - c.x) ** 2 + (t.y - c.y) ** 2 <= c.range ** 2 for c in cryos) or lvl.is_ice(t.tx, t.ty):
                cool = 0.6
            shade = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                        if lvl.in_bounds(t.tx + dx, t.ty + dy) and lvl.tile_at(t.tx + dx, t.ty + dy)
                        in (S.T_BLOCK, S.T_CRYSTAL))
            rate = 1 / 14.0
            if any((t.x - v["x"]) ** 2 + (t.y - v["y"]) ** 2 < 130 ** 2 for v in vents):
                rate *= 1.5
            rate *= max(0.4, 1 - 0.15 * shade)
            if wave and t.target is not None and t.fsm.name == "active" and t.behavior != "aura":
                heat += rate * dt * (0.3 if cool > 0.2 else 1.0)
            else:
                heat -= cool * dt
            heat = max(0.0, heat)
            if heat >= 1.0:
                heat = 0.35
                t.disable(3.0)
                play.effects.burst(t.x, t.y, S.ORANGE, 12, 100, 0.5, 3)
                play.effects.floating_text(t.x, t.y - 22, "OVERHEATED", S.ORANGE, 16)
            t.heat = heat

    def meteor_hit(self, x, y):
        play = self.play
        r = 52
        play.enemies.splash(x, y, r, 45, include_air=True, knockback=20)
        for t in play.towers.towers:
            if (t.x - x) ** 2 + (t.y - y) ** 2 <= r * r:
                t.health.damage(30, ignore_armor=True)
        c = play.player.commander
        if c.alive and c.pos.distance_squared_to((x, y)) <= r * r:
            c.take_damage(20)
        play.effects.explosion(x, y, S.ORANGE, count=26)
        play.effects.shake(0.25)
        play.audio.play("explode")
        if random.random() < 0.5:
            play.items.drop("energy_crystal", x, y)   # crystal deposit

    def update_critters(self, dt):
        play = self.play
        c = play.player.commander
        for cr in self.critters:
            cr["life"] -= dt
            cr["cd"] -= dt
            cr["a"] += random.uniform(-2, 2) * dt
            nx = cr["x"] + math.cos(cr["a"]) * 30 * dt
            ny = cr["y"] + math.sin(cr["a"]) * 30 * dt
            if 10 < nx < S.MAP_W - 10 and 10 < ny < S.MAP_H - 10:
                cr["x"], cr["y"] = nx, ny
            else:
                cr["a"] += math.pi
            if cr["cd"] > 0:
                continue
            for e in play.enemies.enemies:   # they bite aliens...
                if e.targetable and not e.flying and (e.pos.x - cr["x"]) ** 2 + (e.pos.y - cr["y"]) ** 2 < 30 ** 2:
                    play.enemies.damage(e, 15, quiet=True)
                    cr["cd"] = 1.0
                    break
            if cr["cd"] <= 0 and c.alive and c.pos.distance_squared_to((cr["x"], cr["y"])) < 26 ** 2:
                c.take_damage(6)   # ...and Vance
                cr["hp"] -= 30     # she swats back
                cr["cd"] = 1.0
            for t in play.towers.towers:   # ...and towers
                if cr["cd"] <= 0 and (t.x - cr["x"]) ** 2 + (t.y - cr["y"]) ** 2 < 24 ** 2:
                    t.health.damage(8, ignore_armor=True)
                    cr["cd"] = 1.0
        self.critters = [cr for cr in self.critters if cr["life"] > 0 and cr["hp"] > 0]

    # ---- drawing --------------------------------------------------------------------------
    def render_ground(self, screen, offset):
        lvl = self.level
        t_now = self.t
        if self.flooded:
            surf = pygame.Surface((S.TILE, S.TILE), pygame.SRCALPHA)
            surf.fill((40, 110, 200, 150))
            for tx, ty in self.flooded:
                screen.blit(surf, (tx * S.TILE + offset[0], ty * S.TILE + offset[1]))
        for g in lvl.gates:
            sx, sy = lvl.tile_center(*g["switch"])
            col = S.GREEN if g["open"] else S.RED
            pygame.draw.rect(screen, (22, 22, 34), (sx - 10 + offset[0], sy - 10 + offset[1], 20, 20), border_radius=4)
            pygame.draw.rect(screen, col, (sx - 7 + offset[0], sy - 7 + offset[1], 14, 14), border_radius=3)
            for tx, ty in g["tiles"]:
                gx, gy = lvl.tile_center(tx, ty)
                pygame.draw.line(screen, col, (sx + offset[0], sy + offset[1]), (gx + offset[0], gy + offset[1]), 1)
        for a, b in lvl.teleporters:
            for p in (a, b):
                x, y = lvl.tile_center(*p)
                r = 12 + 2 * math.sin(t_now * 4)
                pygame.draw.circle(screen, (60, 30, 90), (int(x + offset[0]), int(y + offset[1])), 14)
                pygame.draw.circle(screen, (200, 110, 240), (int(x + offset[0]), int(y + offset[1])), int(r), 2)
        for m in self.meteors:
            if m[2] < 2.0:
                x, y = int(m[0] + offset[0]), int(m[1] + offset[1])
                pygame.draw.circle(screen, S.RED, (x, y), 52, 2)
                k = m[2] / 2.0   # falling rock
                pygame.draw.circle(screen, S.ORANGE, (int(x + 120 * k), int(y - 260 * k)), 7)
        for d in self.drops:
            x, y = int(d[0] + offset[0]), int(d[1] + offset[1])
            pygame.draw.ellipse(screen, (40, 40, 40), (x - 10, y - 4, 20, 8))
            k = d[2] / 2.0
            pygame.draw.rect(screen, (150, 104, 64), (x - 8, y - 8 - int(240 * k), 16, 16))
        for cr in self.critters:
            x, y = int(cr["x"] + offset[0]), int(cr["y"] + offset[1])
            pygame.draw.ellipse(screen, (22, 22, 34), (x - 9, y - 6, 18, 12))
            pygame.draw.ellipse(screen, (170, 130, 80), (x - 8, y - 5, 16, 10))
            pygame.draw.circle(screen, S.RED, (int(x + 6 * math.cos(cr["a"])), int(y + 4 * math.sin(cr["a"]))), 2)
        towers = self.play.towers.towers
        for t in towers:
            x, y = t.x + offset[0], t.y + offset[1]
            if getattr(t, "vined", False):
                for k in range(4):
                    a = k * 1.6 + 0.3
                    pygame.draw.arc(screen, (60, 160, 60), (x - 15, y - 15, 30, 30), a, a + 1.0, 3)
            heat = getattr(t, "heat", 0.0)
            if heat > 0.05:
                pygame.draw.rect(screen, (40, 10, 0), (x - 14, y + 16, 28, 3))
                pygame.draw.rect(screen, S.ORANGE if heat < 0.8 else S.RED, (x - 14, y + 16, int(28 * heat), 3))

    def render_night(self, screen, offset):
        if not self.cycle:
            return
        phase = self.t % (self.DAY + self.NIGHT)
        if phase < self.DAY - 5:
            return
        # fade in over the last 5 s of day, out over the first 5 s of the next
        if phase < self.DAY:
            k = (phase - (self.DAY - 5)) / 5
        elif phase > self.DAY + self.NIGHT - 5:
            k = (self.DAY + self.NIGHT - phase) / 5
        else:
            k = 1.0
        shade = pygame.Surface((S.MAP_W, S.MAP_H), pygame.SRCALPHA)
        shade.fill((6, 8, 30, int(150 * k)))
        lights = self.play.enemies.light_sources()
        for x, y, r in lights:
            pygame.draw.circle(shade, (6, 8, 30, int(60 * k)), (int(x), int(y)), int(r * 0.8 + 16))
        for x, y, r in lights:
            pygame.draw.circle(shade, (0, 0, 0, 0), (int(x), int(y)), int(r * 0.8))
        screen.blit(shade, offset)
        if self.quake > 0:
            pass

    def status(self):
        bits = []
        if self.cycle:
            bits.append("NIGHT" if self.night else "DAY")
        if self.overheat:
            bits.append("OVERHEAT")
        if self.low_gravity:
            bits.append("LOW GRAVITY")
        return "  ".join(bits)

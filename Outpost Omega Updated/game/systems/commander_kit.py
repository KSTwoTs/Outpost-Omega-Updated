"""CommanderKit: Vance's Phase 5 toolkit.

    R  dash (short burst with a moment of invulnerability)
    V  throw the selected grenade at the mouse; B cycles grenade type
    Z  mech suit ultimate (charges from kills, 15 s as a tank)
    Weapon pickups (shotgun, sniper, flamethrower, rocket launcher) replace her blaster for a while.
    Ammo crates land near the Core each wave: walk over one, carry it to a tower for a boost.
    A drone buddy orbits her and levels up with her.
    Gear (helmet / armor / boots) drops from elites and bosses and auto-equips if it's better.

Numbers live in data/commander_kit.json. The Commander asks the kit for multipliers
(speed, damage taken, blaster range/damage) instead of the kit overwriting her stats, so
perks and hero bonuses still stack normally.
"""
import math
import random

import pygame

from .. import settings as S

Vec = pygame.math.Vector2
GREN_COLORS = {"frag": S.ORANGE, "cryo": S.CRYO, "emp": (200, 110, 240)}


class CommanderKit:
    def __init__(self, player, data, session, events):
        self.player = player
        self.data = data
        self.session = session
        self.events = events
        self.dash_cd = 0.0
        self.weapon = None            # weapon id or None (blaster)
        self.weapon_time = 0.0
        self.grenades = dict(data.get("start_grenades", {"frag": 2}))
        self.grenade_type = "frag"
        self.flying = []              # [x, y, tx, ty, t_left, t_total, type]
        self.mech_charge = 0.0
        self.mech_time = 0.0
        self.stomp_t = 0.0
        self.crates = []              # [x, y] crates on the ground
        self.carrying = False
        self.drone = {"a": 0.0, "cd": 0.0, "x": 0.0, "y": 0.0}
        self.level = 1                # mirrors the Commander's level (PlayScene sets it)
        if getattr(session, "gear", None) is None:
            session.gear = {}
        events.subscribe("enemy_killed", self.on_enemy_killed)
        events.subscribe("wave_started", self.on_wave_started)

    # ---- multipliers the Commander reads --------------------------------------
    def gear_bonus(self, slot):
        tier = self.session.gear.get(slot, 0)
        return self.data["gear"][slot]["per_tier"] * tier

    @property
    def speed_mult(self):
        m = 1.0 + self.gear_bonus("boots")
        if self.mech_time > 0:
            m *= self.data["mech"]["speed_mult"]
        if self.carrying:
            m *= self.data["crate"]["carry_speed"]
        return m

    @property
    def damage_taken_mult(self):
        m = 1.0 - self.gear_bonus("armor")
        if self.mech_time > 0:
            m *= self.data["mech"]["damage_taken"]
        return max(0.05, m)

    @property
    def range_mult(self):
        return 1.0 + self.gear_bonus("helmet")

    @property
    def blaster_mult(self):
        return self.data["mech"]["blaster_mult"] if self.mech_time > 0 else 1.0

    # ---- actions ---------------------------------------------------------------
    def dash(self, c=None):
        """c: which Commander (co-op Player 2 dashes with her own cooldown)."""
        c = c or self.player.commander
        p2 = c is not self.player.commander
        if not c.alive or (c.dash_cd if p2 else self.dash_cd) > 0:
            return False
        d = Vec(c.move_input)
        if d.length_squared() < 0.01:
            d = Vec(math.cos(c.aim_angle), math.sin(c.aim_angle))
        d = d.normalize()
        cfg = self.data["dash"]
        c.vel = d * cfg["speed"]
        c.dash_time = cfg["time"]
        c.invuln = cfg["invuln"]
        cd = max(0.5, cfg["cooldown"] - self.data["gear"]["boots"].get("dash_cut", 0)
                 * self.session.gear.get("boots", 0))
        if p2:
            c.dash_cd = cd
        else:
            self.dash_cd = cd
        self.player.effects.burst(c.pos.x, c.pos.y, S.CYAN, 10, 120, 0.25, 3)
        self.player.audio.play("blaster")
        return True

    def cycle_grenade(self):
        kinds = [k for k in self.data["grenades"] if self.grenades.get(k, 0) > 0] or list(self.data["grenades"])
        i = kinds.index(self.grenade_type) if self.grenade_type in kinds else -1
        self.grenade_type = kinds[(i + 1) % len(kinds)]
        g = self.data["grenades"][self.grenade_type]
        self.events.publish("toast", text=f"Grenade: {g['name']} x{self.grenades.get(self.grenade_type, 0)}",
                            color=GREN_COLORS[self.grenade_type])

    def throw(self, target):
        c = self.player.commander
        if not c.alive or c.jammed > 0:
            return False
        if self.grenades.get(self.grenade_type, 0) <= 0:
            self.cycle_grenade()
            if self.grenades.get(self.grenade_type, 0) <= 0:
                self.events.publish("toast", text="No grenades", color=S.TEXT_DIM)
                return False
        self.grenades[self.grenade_type] -= 1
        tx, ty = target
        dist = math.hypot(tx - c.pos.x, ty - c.pos.y)
        rng = self.data["grenade_range"]
        if dist > rng:   # clamp to throwing range
            tx = c.pos.x + (tx - c.pos.x) / dist * rng
            ty = c.pos.y + (ty - c.pos.y) / dist * rng
        t = 0.3 + 0.3 * min(1.0, dist / rng)
        self.flying.append([c.pos.x, c.pos.y, tx, ty, t, t, self.grenade_type])
        self.player.audio.play("missile")
        return True

    def explode(self, x, y, kind):
        g = self.data["grenades"][kind]
        r = g["radius"]
        p = self.player
        fx = p.effects
        if kind == "frag":
            p.enemies.splash(x, y, r, g["damage"], include_air=True, knockback=20)
            fx.explosion(x, y, S.ORANGE, count=24)
            fx.shake(0.25)
        elif kind == "cryo":
            for e in p.collision.enemies_in_range(x, y, r, True):
                p.enemies.damage(e, g["damage"], quiet=True)
                e.apply_slow(g["slow"], g["slow_time"])
            fx.burst(x, y, S.CRYO, 30, 160, 0.6, 4)
        else:   # EMP cleanse: stun aliens, strip shields, fix corrupted towers, knock off Leeches
            for e in p.enemies.enemies:
                if e.targetable and (e.pos.x - x) ** 2 + (e.pos.y - y) ** 2 <= r * r:
                    e.apply_stun(g["stun"])
                    e.shield = 0.0
                    e.aura_shield = 0.0
                    if getattr(e, "latched", None) is not None:
                        e.unlatch()
            for t in p.towers.towers:
                if (t.x - x) ** 2 + (t.y - y) ** 2 <= r * r:
                    if t.corrupted:
                        t.corrupted = False
                        fx.floating_text(t.x, t.y - 22, "CLEANSED", S.GREEN, 18)
                    t.disabled_timer = 0.0
            fx.burst(x, y, (200, 110, 240), 30, 180, 0.5, 3)
        fx.ring(x, y, r, GREN_COLORS[kind], 0.4, width=3)
        p.audio.play("explode")

    def activate_mech(self):
        c = self.player.commander
        need = self.data["mech"]["charge"]
        if not c.alive:
            return False
        if self.mech_charge < need:
            self.events.publish("toast", text=f"Mech suit {int(100 * self.mech_charge / need)}% charged",
                                color=S.TEXT_DIM)
            return False
        self.mech_charge = 0.0
        self.mech_time = self.data["mech"]["duration"]
        c.health.heal(c.health.max_hp)
        self.player.effects.ring(c.pos.x, c.pos.y, 60, S.ENERGY, 0.6, width=5)
        self.player.effects.shake(0.3)
        self.player.audio.play("upgrade")
        self.events.publish("toast", text="MECH SUIT ONLINE", color=S.ENERGY)
        return True

    def equip_weapon(self, wid):
        self.weapon = wid
        self.weapon_time = self.data["weapons"][wid]["duration"]
        self.events.publish("toast", text=f"Picked up: {self.data['weapons'][wid]['name']}", color=S.ORANGE)

    def give_grenade(self, kind, n=1):
        self.grenades[kind] = self.grenades.get(kind, 0) + n

    def give_gear(self, slot, tier):
        cur = self.session.gear.get(slot, 0)
        g = self.data["gear"][slot]
        name = f"{g['names'][tier - 1]} ({g['desc'].format(int(g['per_tier'] * tier * 100))})"
        if tier > cur:
            self.session.gear[slot] = tier
            self.events.publish("toast", text=f"Equipped {name}", color=S.ENERGY)
        else:
            self.events.publish("toast", text=f"{name}: not better than yours", color=S.TEXT_DIM)

    # ---- weapon fire (replaces the blaster while a pickup is active) ----------------
    def fire_weapon(self, c):
        w = self.data["weapons"][self.weapon]
        if not c.weapon_cd_ready():
            return False
        p = self.player
        rng = w["range"] * self.range_mult
        target = p.collision.nearest_enemy(c.pos.x, c.pos.y, rng)
        if target is None:
            return False
        c.weapon_cd = 1.0 / w["rate"]
        mult = self.blaster_mult
        c.aim_angle = math.atan2(target.pos.y - c.pos.y, target.pos.x - c.pos.x)
        c.facing_left = math.cos(c.aim_angle) < 0
        kind = self.weapon
        if kind == "shotgun":
            for i in range(w["pellets"]):
                a = c.aim_angle + (i - (w["pellets"] - 1) / 2) * w["spread"]
                tx, ty = c.pos.x + math.cos(a) * rng, c.pos.y + math.sin(a) * rng
                for e in p.collision.enemies_in_range(c.pos.x, c.pos.y, rng, True):
                    if e.hit_test_segment(c.pos.x, c.pos.y, tx, ty, pad=2):
                        p.enemies.damage(e, w["damage"] * mult, quiet=True)
                        break
                p.effects.beam(c.pos.x, c.pos.y, tx, ty, S.ENERGY, 0.05)
        elif kind == "sniper":
            p.enemies.damage(target, w["damage"] * mult, ignore_armor=True)
            p.effects.beam(c.pos.x, c.pos.y, target.pos.x, target.pos.y, S.WHITE, 0.12)
        elif kind == "flamethrower":
            for e in p.collision.enemies_in_range(c.pos.x, c.pos.y, rng, False):
                a = math.atan2(e.pos.y - c.pos.y, e.pos.x - c.pos.x)
                if abs((a - c.aim_angle + math.pi) % math.tau - math.pi) <= 0.45:
                    p.enemies.damage(e, w["damage"] * mult, quiet=True)
                    e.apply_burn(w["burn_dps"], 2.0)
            for _ in range(3):
                a = c.aim_angle + random.uniform(-0.4, 0.4)
                pt = p.effects.particles.acquire()
                pt.spawn(c.pos.x, c.pos.y, math.cos(a) * rng * 2, math.sin(a) * rng * 2, 0.35,
                         random.choice((S.ORANGE, S.ENERGY)), 4, drag=2.0)
        else:   # rocket
            p.projectiles.fire_at(c.pos.x, c.pos.y, target, 380, w["damage"] * mult, color=S.RED,
                                  hits_air=True, radius=4, splash=w["splash"])
        p.audio.play("shoot" if kind != "rocket" else "missile")
        return True

    # ---- events -----------------------------------------------------------------
    def on_enemy_killed(self, enemy, **_):
        c = self.player.commander
        if c.alive and self.mech_time <= 0:
            self.mech_charge = min(self.data["mech"]["charge"],
                                   self.mech_charge + (3 if enemy.is_boss else 1))
        if enemy.affix or enemy.is_boss:   # gear drop
            chance = 1.0 if enemy.is_boss else self.data["gear_drop_elite"]
            if random.random() < chance:
                self.player.drop_item("gear", enemy.pos.x - 14, enemy.pos.y)

    def on_wave_started(self, **_):
        lvl = self.player.level
        cx, cy = lvl.core_positions[0]
        spots = []
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                tx, ty = lvl.world_to_tile(cx, cy)
                tx, ty = tx + dx, ty + dy
                if lvl.in_bounds(tx, ty) and not lvl.is_solid(tx, ty) and 2 <= abs(dx) + abs(dy) <= 6:
                    spots.append(lvl.tile_center(tx, ty))
        if spots and len(self.crates) < 2:
            self.crates.append(list(random.choice(spots)))

    # ---- loop --------------------------------------------------------------------------
    def update(self, dt):
        p = self.player
        c = p.commander
        self.dash_cd = max(0.0, self.dash_cd - dt)
        if self.weapon:
            self.weapon_time -= dt
            if self.weapon_time <= 0:
                self.events.publish("toast", text=f"{self.data['weapons'][self.weapon]['name']} ran dry",
                                    color=S.TEXT_DIM)
                self.weapon = None
        # grenades in flight
        for g in self.flying:
            g[4] -= dt
            if g[4] <= 0:
                self.explode(g[2], g[3], g[6])
        self.flying = [g for g in self.flying if g[4] > 0]
        # mech suit
        if self.mech_time > 0:
            self.mech_time -= dt
            self.stomp_t += dt
            if self.stomp_t >= 2.0 and c.alive:
                self.stomp_t = 0.0
                m = self.data["mech"]
                p.enemies.splash(c.pos.x, c.pos.y, m["stomp_radius"], m["stomp_damage"], include_air=False,
                                 knockback=16)
                p.effects.ring(c.pos.x, c.pos.y, m["stomp_radius"], S.ENERGY, 0.35, width=3)
            if self.mech_time <= 0:
                self.events.publish("toast", text="Mech suit offline", color=S.TEXT_DIM)
        # crates
        if c.alive:
            if not self.carrying:
                for cr in self.crates:
                    if (cr[0] - c.pos.x) ** 2 + (cr[1] - c.pos.y) ** 2 <= 22 * 22:
                        self.crates.remove(cr)
                        self.carrying = True
                        self.events.publish("toast", text="Ammo crate! Carry it to a tower", color=S.ENERGY)
                        break
            else:
                r = self.data["crate"]["deliver_range"]
                near = [t for t in p.towers.towers if (t.x - c.pos.x) ** 2 + (t.y - c.pos.y) ** 2 <= r * r
                        and not t.walkable]
                if near:
                    t = min(near, key=lambda t: (t.x - c.pos.x) ** 2 + (t.y - c.pos.y) ** 2)
                    t.overcharge(self.data["crate"]["boost_time"])
                    t.health.heal(t.health.max_hp * 0.3)
                    self.carrying = False
                    p.effects.ring(t.x, t.y, 30, S.ENERGY, 0.5, width=4)
                    p.effects.floating_text(t.x, t.y - 22, "AMMO UP!", S.ENERGY, 20)
                    p.audio.play("upgrade")
        else:
            if self.carrying:   # dropped where she fell
                self.crates.append([c.pos.x, c.pos.y])
                self.carrying = False
            self.mech_time = 0.0
        # drone buddy
        d = self.drone
        d["a"] += dt * 2.0
        d["x"] = c.pos.x + math.cos(d["a"]) * 22
        d["y"] = c.pos.y + math.sin(d["a"]) * 16 - 8
        d["cd"] -= dt
        cfg = self.data["drone"]
        if c.alive and d["cd"] <= 0:
            e = p.collision.nearest_enemy(d["x"], d["y"], cfg["range"])
            if e is not None:
                d["cd"] = 1.0 / (cfg["rate"] + cfg["rate_per_level"] * (self.level - 1))
                p.enemies.damage(e, cfg["damage"] + cfg["damage_per_level"] * (self.level - 1), quiet=True)
                p.effects.beam(d["x"], d["y"], e.pos.x, e.pos.y, S.GREEN, 0.05)

    def render(self, screen, assets, offset):
        p = self.player
        c = p.commander
        for x, y in self.crates:
            _crate(screen, (x + offset[0], y + offset[1]))
        for sx, sy, tx, ty, t, total, kind in self.flying:
            k = 1 - t / total
            x = sx + (tx - sx) * k + offset[0]
            y = sy + (ty - sy) * k - math.sin(k * math.pi) * 40 + offset[1]
            pygame.draw.circle(screen, (22, 22, 34), (int(x), int(y)), 5)
            pygame.draw.circle(screen, GREN_COLORS[kind], (int(x), int(y)), 4)
        if not c.alive:
            return
        cx, cy = c.pos.x + offset[0], c.pos.y + offset[1]
        if self.carrying:
            _crate(screen, (cx, cy - 24), small=True)
        if self.mech_time > 0:   # mech frame around her
            pygame.draw.rect(screen, (22, 22, 34), (cx - 15, cy - 15, 30, 30), border_radius=6)
            pygame.draw.rect(screen, S.ENERGY, (cx - 15, cy - 15, 30, 30), 2, border_radius=6)
            for sx in (-1, 1):
                pygame.draw.rect(screen, S.STEEL, (cx + sx * 15 - 4, cy - 6, 8, 14))
        d = self.drone
        x, y = d["x"] + offset[0], d["y"] + offset[1]
        pygame.draw.circle(screen, (22, 22, 34), (int(x), int(y)), 5)
        pygame.draw.circle(screen, S.GREEN if self.level < 5 else S.ENERGY, (int(x), int(y)), 4)
        pygame.draw.line(screen, S.STEEL_LIGHT, (x - 6, y - 5), (x + 6, y - 5), 1)

    def render_status(self, screen, assets, extra=""):
        """A strip just above the HUD on the left: weapon, grenades, mech, dash, gear."""
        parts = [(extra, S.CYAN)] if extra else []
        if self.weapon:
            parts.append((f"{self.data['weapons'][self.weapon]['name']} {int(self.weapon_time)}s", S.ORANGE))
        g = self.data["grenades"][self.grenade_type]
        parts.append((f"V {g['name']} x{self.grenades.get(self.grenade_type, 0)}", GREN_COLORS[self.grenade_type]))
        need = self.data["mech"]["charge"]
        if self.mech_time > 0:
            parts.append((f"MECH {int(self.mech_time)}s", S.ENERGY))
        else:
            parts.append((f"Z Mech {int(100 * self.mech_charge / need)}%",
                          S.ENERGY if self.mech_charge >= need else S.TEXT_DIM))
        parts.append(("R Dash" if self.dash_cd <= 0 else f"Dash {self.dash_cd:.1f}", S.CYAN if self.dash_cd <= 0
                      else S.TEXT_DIM))
        gear = self.session.gear
        if gear:
            parts.append(("Gear " + " ".join(f"{k[0].upper()}{v}" for k, v in sorted(gear.items())), S.ENERGY))
        if self.carrying:
            parts.append(("Carrying ammo", S.ENERGY))
        x, y = 10, S.HUD_Y - 24
        surfs = [assets.text(t, 15, col, True) for t, col in parts]
        w = sum(s.get_width() for s in surfs) + 14 * len(surfs) + 6
        bg = pygame.Surface((w, 20), pygame.SRCALPHA)
        bg.fill((*S.HUD_BG, 200))
        screen.blit(bg, (x - 4, y - 2))
        for s in surfs:
            screen.blit(s, (x, y))
            x += s.get_width() + 14


def _crate(screen, pos, small=False):
    s = 7 if small else 9
    x, y = int(pos[0]), int(pos[1])
    pygame.draw.rect(screen, (22, 22, 34), (x - s - 1, y - s - 1, 2 * s + 2, 2 * s + 2))
    pygame.draw.rect(screen, (150, 104, 64), (x - s, y - s, 2 * s, 2 * s))
    pygame.draw.line(screen, (96, 64, 40), (x - s, y - s), (x + s, y + s), 2)
    pygame.draw.line(screen, (96, 64, 40), (x + s, y - s), (x - s, y + s), 2)
    pygame.draw.rect(screen, S.ENERGY, (x - 3, y - 3, 6, 6))

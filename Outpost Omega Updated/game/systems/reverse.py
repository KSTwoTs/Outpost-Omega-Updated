"""Reverse mode: you are the hive (data/reverse.json).

You earn Biomass every second (and more for every point of Core damage) and spend it to
send packs of aliens down the path. An AI commander builds and upgrades towers with the
Energy it earns from a steady income plus kill rewards. Break the Core before the clock
runs out to win.

    1-0, -, =     send the first 12 alien cards (or click any card in the bottom panel)
    G             Hive Growth: more Biomass per second
    V             Evolve: every alien you send gets more HP
"""
import math
import random

import pygame

from .. import settings as S

CARD_W, CARD_GAP = 66, 2


class Reverse:
    def __init__(self, play, data):
        self.play = play
        self.data = data
        self.bio = float(data["start_biomass"])
        self.income = float(data["income"])
        self.time_left = float(data["time_limit"])
        self.growth_level = 0
        self.evolve_level = 0
        self.roster = [r for r in data["roster"] if r["kind"] in play.game.data["enemies"]]
        self.cooldowns = [0.0] * len(self.roster)
        self.sent = 0
        self.queue = []         # [delay, kind, lane] aliens waiting to walk on
        self.wave = 1           # alien strength grows with time like Endless waves
        ai = data["ai"]
        self.ai_income = ai["income"].get(play.difficulty, ai["income"]["Normal"])
        self.ai_think = 1.0
        self.air_seen = False
        self.air_sent = 0       # flyers sent so far: the AI answers with anti-air
        self.ai_log = []
        play.kill_mult *= ai.get("kill_reward", 1.0)   # the AI earns part of each kill
        s = play.session
        s.energy = ai["start_energy"]
        s.core_hp = s.core_max = data["core_hp"]
        play.enemies.diff = dict(S.DIFFICULTIES["Normal"])   # difficulty only changes the AI
        play.waves.build_time = 1e9
        play.waves.countdown = 1e9
        for t in play.towers.data.values():   # the player never builds
            t["enabled"] = False
        play.player.commander.disabled = True
        play.wild.living = False            # the Living Core would be on the outpost's side
        play.towers.on_tower_kill = None    # the AI's kills don't count toward your mastery
        play.progress.add_xp = lambda *_a, **_k: False   # no Vance, no level-ups
        play.items.drop = lambda *_a, **_k: None         # nobody to pick drops up
        play.events.subscribe("enemy_reached_core", self.on_core_hit)
        self.path_tiles = {t for tiles in play.level.route_tiles for t in tiles}
        for i in range(ai.get("opening_builds", 3)):   # the outpost starts with a few towers up
            pool = ai["air"][:1] if i == 0 else ai["ground"]   # one Flak Cannon, just in case
            self.ai_build(random.choice([k for k in pool if k in play.towers.data]))

    # ---- the hive (player) --------------------------------------------------------------
    @property
    def growth_cost(self):
        g = self.data["growth"]
        return int(g["cost"] * g["cost_mult"] ** self.growth_level)

    @property
    def evolve_cost(self):
        e = self.data["evolve"]
        return int(e["cost"] * e["cost_mult"] ** self.evolve_level)

    def send(self, i):
        play = self.play
        if not (0 <= i < len(self.roster)) or play.result:
            return False
        card = self.roster[i]
        if self.cooldowns[i] > 0:
            play.ui.toast(f"{self.name(card)} ready in {self.cooldowns[i]:.0f}s", S.TEXT_DIM)
            play.audio.play("error")
            return False
        if self.bio < card["cost"]:
            play.ui.toast("Not enough Biomass", S.RED)
            play.audio.play("error")
            return False
        self.bio -= card["cost"]
        self.cooldowns[i] = card["cooldown"]
        lanes = max(1, play.level.lane_count)
        for k in range(card["count"]):   # a pack walks in single file, 0.35 s apart
            self.queue.append([k * 0.35, card["kind"], (self.sent + k) % lanes])
        self.sent += 1
        play.audio.play("click")
        return True

    def grow(self):
        if self.bio < self.growth_cost:
            self.play.audio.play("error")
            return
        self.bio -= self.growth_cost
        self.growth_level += 1
        self.income += self.data["growth"]["income"]
        self.play.ui.toast(f"Hive Growth {self.growth_level}: {self.income:.0f} Biomass/s", S.ALIEN_GREEN)
        self.play.audio.play("upgrade")

    def evolve(self):
        if self.bio < self.evolve_cost:
            self.play.audio.play("error")
            return
        self.bio -= self.evolve_cost
        self.evolve_level += 1
        pct = int(self.data["evolve"]["hp"] * self.evolve_level * 100)
        self.play.ui.toast(f"Evolution {self.evolve_level}: your aliens have +{pct}% HP", S.ALIEN_GREEN)
        self.play.audio.play("upgrade")

    def on_core_hit(self, enemy, **_):
        self.bio += enemy.core_damage * self.data["core_bonus"]

    # ---- the outpost (AI) ---------------------------------------------------------------
    def tile_score(self, tx, ty, rng_tiles):
        r2 = rng_tiles * rng_tiles
        return sum(1 for px, py in self.path_tiles if (px - tx) ** 2 + (py - ty) ** 2 <= r2)

    def ai_build(self, kind):
        play = self.play
        towers = play.towers
        d = towers.data[kind]
        if play.session.energy < d["cost"]:
            return False
        rng_tiles = d["tiers"][0].get("range", 120) / S.TILE
        towers.build_kind = kind
        best, best_score = None, 0
        cands = set()
        for px, py in self.path_tiles:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    cands.add((px + dx, py + dy))
        for tx, ty in random.sample(sorted(cands), min(len(cands), 160)):
            if not play.level.is_buildable(tx, ty):
                continue
            score = self.tile_score(tx, ty, rng_tiles) + random.random()
            if score > best_score and towers.placement_problem(tx, ty) is None:
                best, best_score = (tx, ty), score
        ok = False
        if best is not None:
            d["enabled"] = True
            ok = towers.try_place(*best)
            d["enabled"] = False
        towers.build_kind = None
        towers.placed_this_build.clear()
        return ok

    def ai_step(self):
        play = self.play
        towers = play.towers
        ai = self.data["ai"]
        energy = play.session.energy
        anti_air = sum(1 + t.tier for t in towers.towers if t.kind in ai["air"])
        if self.air_seen and anti_air < 2 + self.air_sent // 5:
            pool = ai["air"][:2]          # dedicated anti-air (Flak, Missile)
            short = [t for t in towers.towers if t.kind in pool and t.can_upgrade and t.upgrade_cost <= energy]
            if short and random.random() < 0.4:
                towers.upgrade(min(short, key=lambda t: t.tier))
                return
        else:
            pool = ai["ground"] + (ai["air"] if self.air_seen else [])
        pool = [k for k in pool if k in towers.data]
        upgradable = [t for t in towers.towers if t.can_upgrade and t.upgrade_cost <= energy]
        build_first = len(towers.towers) < 4 or (len(towers.towers) < ai["max_towers"] and random.random() < 0.6)
        if build_first and pool:
            kind = random.choice(pool)
            if self.ai_build(kind):
                return
        if upgradable:
            t = min(upgradable, key=lambda t: (t.tier, -t.kills))
            towers.upgrade(t)

    # ---- loop ---------------------------------------------------------------------------
    def update(self, dt):
        play = self.play
        if play.result:
            return
        self.bio += self.income * dt
        play.session.energy += self.ai_income * dt
        self.cooldowns = [max(0.0, c - dt) for c in self.cooldowns]
        hp = 1.0 + self.data["evolve"]["hp"] * self.evolve_level
        for q in self.queue:
            q[0] -= dt
            if q[0] <= 0:
                e = play.enemies.spawn(q[1], self.wave, lane=q[2], announce=True)
                if hp != 1.0:
                    e.health.max_hp *= hp
                    e.health.hp = e.health.max_hp
                if e.flying:
                    self.air_seen = True
                    self.air_sent += 3 if q[1] == "carrier" else 1
        self.queue = [q for q in self.queue if q[0] > 0]
        self.time_left -= dt
        elapsed = self.data["time_limit"] - self.time_left
        self.wave = 1 + int(elapsed // 30)
        play.waves.wave_number = self.wave
        self.ai_think -= dt
        if self.ai_think <= 0:
            self.ai_think = self.data["ai"]["think"]
            self.ai_step()
        if self.time_left <= 0:
            play.finish("win")   # the outpost held: Reverse flips this into a loss for the hive

    def handle_command(self, cmd):
        """True if Reverse used the command."""
        n = cmd.name
        if n == "select_slot":
            self.send(cmd.value)
            return True
        if n == "stance":
            self.grow()
            return True
        if n == "grenade":
            self.evolve()
            return True
        if n == "click" and cmd.pos[1] >= S.HUD_Y:
            for i, r in self.card_rects():
                if r.collidepoint(cmd.pos):
                    self.send(i)
                    return True
            g, e = self.upgrade_rects()
            if g.collidepoint(cmd.pos):
                self.grow()
            elif e.collidepoint(cmd.pos):
                self.evolve()
            return True
        if n in ("start_wave", "upgrade", "sell", "move_tower", "socket", "fuse", "undo", "sacrifice", "tame",
                 "dash", "dash2", "mech", "orbital_strike", "orbital_auto", "cycle_grenade", "next_tab", "click",
                 "right_click"):
            return True    # nothing to do with towers or Vance in Reverse
        return False

    # ---- HUD ----------------------------------------------------------------------------
    def card_rects(self):
        return [(i, pygame.Rect(6 + i * (CARD_W + CARD_GAP), S.HUD_Y + 6, CARD_W, S.HUD_H - 12))
                for i in range(len(self.roster))]

    def upgrade_rects(self):
        x = 6 + len(self.roster) * (CARD_W + CARD_GAP) + 6
        w = S.SCREEN_W - x - 6
        return (pygame.Rect(x, S.HUD_Y + 6, w, 32), pygame.Rect(x, S.HUD_Y + 42, w, 32))

    def name(self, card):
        return self.play.game.data["enemies"][card["kind"]].get("name", card["kind"])

    def render(self, screen, assets, mouse):
        play = self.play
        pygame.draw.rect(screen, S.HUD_BG, (0, S.HUD_Y, S.SCREEN_W, S.HUD_H))
        pygame.draw.line(screen, S.ALIEN_GREEN, (0, S.HUD_Y), (S.SCREEN_W, S.HUD_Y), 2)
        hover_card = None
        for i, r in self.card_rects():
            card = self.roster[i]
            ok = self.bio >= card["cost"] and self.cooldowns[i] <= 0
            hover = r.collidepoint(mouse)
            if hover:
                hover_card = card
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, r, border_radius=6)
            pygame.draw.rect(screen, S.ALIEN_GREEN if ok else S.HUD_EDGE, r, 2, border_radius=6)
            img = assets.get(f"{card['kind']}_0")
            if img.get_width() > 44:
                img = pygame.transform.smoothscale(img, (44, int(44 * img.get_height() / img.get_width())))
            if not ok:
                img = img.copy()
                img.set_alpha(90)
            screen.blit(img, img.get_rect(center=(r.centerx, r.y + 26)))
            if card["count"] > 1:
                c = assets.text(f"x{card['count']}", 14, S.WHITE, True)
                screen.blit(c, (r.right - c.get_width() - 4, r.y + 3))
            if i < 12:
                k = assets.text("1234567890-="[i], 14, S.TEXT_DIM, True)
                screen.blit(k, (r.x + 4, r.y + 3))
            cost = assets.text(str(card["cost"]), 16, S.ALIEN_GREEN if ok else S.TEXT_DIM, True)
            screen.blit(cost, cost.get_rect(center=(r.centerx, r.bottom - 10)))
            if self.cooldowns[i] > 0:
                frac = self.cooldowns[i] / card["cooldown"]
                shade = pygame.Surface((r.w, int(r.h * frac)), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 140))
                screen.blit(shade, (r.x, r.bottom - shade.get_height()))
        g, e = self.upgrade_rects()
        for rect, label, cost in ((g, f"G  Growth +{self.data['growth']['income']}/s", self.growth_cost),
                                  (e, f"V  Evolve +{int(self.data['evolve']['hp'] * 100)}% HP", self.evolve_cost)):
            ok = self.bio >= cost
            pygame.draw.rect(screen, S.PANEL_HI if rect.collidepoint(mouse) else S.PANEL, rect, border_radius=6)
            pygame.draw.rect(screen, S.ALIEN_GREEN if ok else S.HUD_EDGE, rect, 2, border_radius=6)
            t = assets.text(f"{label}  ({cost})", 14, S.WHITE if ok else S.TEXT_DIM, True)
            screen.blit(t, t.get_rect(center=rect.center))
        # top banner: Biomass, income, clock, Core, the AI's Energy
        m, s = divmod(max(0, int(self.time_left)), 60)
        bar = pygame.Rect(S.SCREEN_W // 2 - 330, 8, 660, 34)
        panel = pygame.Surface(bar.size, pygame.SRCALPHA)
        panel.fill((10, 12, 24, 210))
        screen.blit(panel, bar)
        pygame.draw.rect(screen, S.ALIEN_GREEN, bar, 2, border_radius=6)
        txt = (f"BIOMASS {int(self.bio)}  (+{self.income:.0f}/s)     {m}:{s:02d}     "
               f"CORE {int(max(0, play.session.core_hp))}/{int(play.session.core_max)}     "
               f"OUTPOST {len(play.towers.towers)} towers, {int(play.session.energy)} E")
        t = assets.text(txt, 18, S.WHITE, True)
        screen.blit(t, t.get_rect(center=bar.center))
        if hover_card is not None:
            st = play.game.data["enemies"][hover_card["kind"]]
            tip = (f"{self.name(hover_card)} x{hover_card['count']}: {int(st.get('hp', 0))} HP, "
                   f"speed {st.get('speed', 0)}{', flies' if st.get('flying') else ''}. "
                   f"Cooldown {hover_card['cooldown']:.0f}s")
            t = assets.text(tip, 16, S.WHITE, True)
            box = t.get_rect(midbottom=(min(max(mouse[0], t.get_width() // 2 + 8), S.SCREEN_W - t.get_width() // 2 - 8),
                                        S.HUD_Y - 8)).inflate(14, 8)
            pygame.draw.rect(screen, S.HUD_BG, box, border_radius=6)
            pygame.draw.rect(screen, S.ALIEN_GREEN, box, 1, border_radius=6)
            screen.blit(t, t.get_rect(center=box.center))

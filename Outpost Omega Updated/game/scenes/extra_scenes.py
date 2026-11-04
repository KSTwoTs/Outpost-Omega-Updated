"""Phase 5 menu screens: Modes, Codex (aliens, towers, profile, leaderboards, achievements)
and the Map Editor."""
import json
import os

import pygame

from .. import settings as S
from ..systems import meta as meta_sys
from ..systems import modes as modes_sys
from ..systems.ui_system import Button
from .menu import Starfield
from .scene_manager import Scene

MODS_DIR = os.path.join(S.ROOT_DIR, "mods")
CUSTOM_DIR = os.path.join(MODS_DIR, "levels")


# ---- Modes ------------------------------------------------------------------------------
class ModesScene(Scene):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.stars = Starfield()
        cx = S.SCREEN_W // 2
        self.items = [
            ("boss_rush", "BOSS RUSH", "Every boss, back to back. 800 Energy to start."),
            ("last_stand", "LAST STAND", "No towers at all: just Vance, her kit and Core upgrades."),
            ("weekly", "WEEKLY CHALLENGE", ""),
            ("sandbox", "SANDBOX", "Unlimited Energy. Spawn any alien with Y; Space starts a wave."),
            ("reverse", "REVERSE", "You are the hive: send aliens, break the AI's Core in 6 minutes."),
        ]
        self.buttons = [Button((cx - 470, 150 + i * 78, 420, 64), label, "mode", key)
                        for i, (key, label, _d) in enumerate(self.items)]
        self.puzzles = list(game.data["puzzles"])
        self.puzzle_buttons = [Button((cx + 60, 150 + i * 78, 410, 64), game.data["puzzles"][p]["name"].upper(),
                                      "puzzle", p) for i, p in enumerate(self.puzzles)]
        self.hard = Button((cx + 60, 400, 410, 50), "", "hardcore")
        self.asc = Button((cx + 60, 458, 410, 50), "", "ascension")
        self.coop = Button((cx + 60, 516, 410, 50), "", "coop")
        self.story = Button((cx + 60, 574, 410, 50), "", "story")
        self.back = Button((40, S.SCREEN_H - 80, 140, 46), "BACK", "back")
        self.t = 0.0

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        if cmd.name != "click":
            return
        g = self.game
        for b in self.buttons + self.puzzle_buttons + [self.hard, self.asc, self.coop, self.story, self.back]:
            if not b.hit(cmd.pos):
                continue
            self.audio.play("click")
            if b.command == "back":
                g.scenes.change("menu")
            elif b.command == "hardcore":
                g.hardcore = not g.hardcore
            elif b.command == "coop":
                g.coop = not g.coop
            elif b.command == "story":
                g.settings["story"] = not g.settings.get("story", True)
                g.write_save()
            elif b.command == "ascension":
                top = g.save.get("ascension_unlocked", 0)
                g.ascension = (g.ascension + 1) % (min(top, len(modes_sys.ASCENSION)) + 1)
            elif b.command == "puzzle":
                pz = g.data["puzzles"][b.value]
                g.scenes.change("play", level_id=pz["level"], difficulty="Normal", mode="campaign",
                                variant=f"puzzle:{b.value}")
            elif b.value == "weekly":
                sector, _rules, seed = modes_sys.weekly_setup()
                g.scenes.change("play", level_id=sector, difficulty="Normal", mode="endless", seed=seed,
                                variant="weekly")
            elif b.value == "boss_rush":
                g.scenes.change("play", level_id="sector1", difficulty=g.difficulty, mode="campaign",
                                variant="boss_rush")
            elif b.value == "reverse":
                import random as _r
                g.scenes.change("play", level_id=_r.choice(["sector1", "sector3", "sector5", "sector9"]),
                                difficulty=g.difficulty, mode="endless", variant="reverse")
            else:
                g.scenes.change("play", level_id="sector1" if b.value == "last_stand" else "sector5",
                                difficulty=g.difficulty, mode="endless", variant=b.value)
            return

    def on_update(self, dt):
        self.t += dt
        self.stars.update(dt)

    def on_render(self, screen):
        a, g = self.assets, self.game
        self.stars.draw(screen)
        t = a.text("GAME MODES", 56, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, 80)))
        mouse = self.input.mouse_pos()
        _sector, rules, _seed = modes_sys.weekly_setup()
        for b, (key, _label, desc) in zip(self.buttons, self.items):
            if key == "weekly":
                desc = f"{modes_sys.week_key()}: " + " + ".join(modes_sys.WEEKLY_RULES[r]["name"] for r in rules)
            b.draw(screen, a, mouse, size=26, sub=desc)
        head = a.text("PUZZLES  (no Energy from kills, 1 HP Core)", 20, S.ENERGY, True)
        screen.blit(head, (self.puzzle_buttons[0].rect.x, 120))
        solved = meta_sys.profile(g.save)["puzzles"]
        for b, pid in zip(self.puzzle_buttons, self.puzzles):
            pz = g.data["puzzles"][pid]
            b.draw(screen, a, mouse, size=24, sub=pz["desc"] + ("  [SOLVED]" if pid in solved else ""))
        self.hard.label = f"HARDCORE: {'ON' if g.hardcore else 'OFF'}"
        self.hard.draw(screen, a, mouse, size=22, sub="Vance's death ends Endless / Siege Run games")
        top = g.save.get("ascension_unlocked", 0)
        self.asc.label = f"SIEGE RUN ASCENSION: {g.ascension}"
        sub = ("Win a Siege Run to unlock" if top == 0 else
               "; ".join(modes_sys.ASCENSION[:g.ascension]) or f"Up to {min(top, len(modes_sys.ASCENSION))} unlocked")
        self.asc.draw(screen, a, mouse, size=22, sub=sub[:70])
        self.coop.label = f"LOCAL CO-OP: {'ON' if g.coop else 'OFF'}"
        self.coop.draw(screen, a, mouse, size=22, sub="P2: arrows + R.Ctrl repair + R.Shift dash (or a controller)")
        self.story.label = f"STORY CAMPAIGN: {'ON' if g.settings.get('story', True) else 'OFF'}"
        self.story.draw(screen, a, mouse, size=22, sub="Briefings, radio chatter and a 13th sector in the campaign")
        self.back.draw(screen, a, mouse, size=24)


# ---- Codex -------------------------------------------------------------------------------
class CodexScene(Scene):
    TABS = ("ALIENS", "TOWERS", "PROFILE", "SCORES", "ACHIEVEMENTS")

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.stars = Starfield()
        self.tab = 0
        self.tab_buttons = [Button((60 + i * 236, 70, 226, 40), name, "tab", i) for i, name in enumerate(self.TABS)]
        self.back = Button((40, S.SCREEN_H - 70, 140, 46), "BACK", "back")
        self.page = 0
        self.next = Button((S.SCREEN_W - 180, S.SCREEN_H - 70, 140, 46), "MORE", "more")

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        if cmd.name != "click":
            return
        for b in self.tab_buttons:
            if b.hit(cmd.pos):
                self.tab, self.page = b.value, 0
                self.audio.play("click")
        if self.back.hit(cmd.pos):
            self.game.scenes.change("menu")
        if self.next.hit(cmd.pos):
            self.page += 1
            self.audio.play("click")

    def on_update(self, dt):
        self.stars.update(dt)

    def on_render(self, screen):
        a, g = self.assets, self.game
        self.stars.draw(screen)
        mouse = self.input.mouse_pos()
        t = a.text("CODEX", 44, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, 34)))
        for b in self.tab_buttons:
            b.draw(screen, a, mouse, selected=b.value == self.tab, size=22)
        p = meta_sys.profile(g.save)
        getattr(self, "render_" + self.TABS[self.tab].lower())(screen, a, p)
        self.back.draw(screen, a, mouse, size=24)
        if self.TABS[self.tab] in ("ALIENS", "TOWERS"):
            self.next.draw(screen, a, mouse, size=24)

    def grid(self, items):
        per = 15
        n = max(1, -(-len(items) // per))
        page = self.page % n
        return items[page * per:(page + 1) * per]

    def render_aliens(self, screen, a, p):
        enemies = self.game.data["enemies"]
        kinds = sorted(enemies, key=lambda k: (enemies[k].get("unlock_wave", 99), k))
        for i, k in enumerate(self.grid(kinds)):
            d = enemies[k]
            col, row = i % 3, i // 3
            r = pygame.Rect(60 + col * 396, 130 + row * 100, 384, 92)
            seen = p["codex"].get(k, 0)
            pygame.draw.rect(screen, S.HUD_BG, r, border_radius=8)
            pygame.draw.rect(screen, S.MAGENTA if "Boss" in d.get("description", "") else S.HUD_EDGE, r, 2,
                             border_radius=8)
            img = a.get(f"{k}_0")
            if img.get_height() > 70:
                img = pygame.transform.smoothscale(img, (int(img.get_width() * 70 / img.get_height()), 70))
            if not seen:
                img = img.copy()
                img.fill((20, 20, 30, 255), special_flags=pygame.BLEND_RGBA_MIN)
            screen.blit(img, img.get_rect(center=(r.x + 48, r.centery)))
            name = d.get("name", k) if seen else "???"
            screen.blit(a.text(name, 22, S.WHITE, True), (r.x + 96, r.y + 8))
            if seen:
                stats = f"HP {d['hp']}  Speed {d['speed']}  Armor {d.get('armor', 0)}  Kills {seen}"
                screen.blit(a.text(stats, 15, S.CYAN), (r.x + 96, r.y + 34))
                desc = d.get("description", "")
                screen.blit(a.text(desc[:52], 15, S.TEXT_DIM), (r.x + 96, r.y + 54))
                if len(desc) > 52:
                    screen.blit(a.text(desc[52:104], 15, S.TEXT_DIM), (r.x + 96, r.y + 70))
            else:
                screen.blit(a.text("Kill one to unlock its entry", 15, S.TEXT_DIM), (r.x + 96, r.y + 40))

    def render_towers(self, screen, a, p):
        g = self.game
        towers = g.data["towers"]
        meta = g.data["meta"]
        kinds = sorted(towers, key=lambda k: towers[k]["key"])
        for i, k in enumerate(self.grid(kinds)):
            d = towers[k]
            col, row = i % 3, i // 3
            r = pygame.Rect(60 + col * 396, 130 + row * 100, 384, 92)
            pygame.draw.rect(screen, S.HUD_BG, r, border_radius=8)
            pygame.draw.rect(screen, S.HUD_EDGE, r, 2, border_radius=8)
            img = pygame.transform.scale(a.get(f"turret_{k}"), (60, 60))
            screen.blit(img, img.get_rect(center=(r.x + 44, r.centery)))
            lvl = meta_sys.mastery_level(g.save, meta, k)
            kills = p["mastery"].get(k, 0)
            screen.blit(a.text(d["name"], 22, S.WHITE, True), (r.x + 90, r.y + 8))
            nxt = next((m for m in meta["mastery_levels"] if kills < m), None)
            line = f"Mastery {lvl}/3  ({kills} kills" + (f", next at {nxt})" if nxt else ", maxed)")
            screen.blit(a.text(line, 15, S.ENERGY if lvl else S.TEXT_DIM), (r.x + 90, r.y + 36))
            bonus = int(meta_sys.MASTERY_BONUS[lvl] * 100)
            extra = f"+{bonus}% damage" + ("; tier-4 branches in Endless" if lvl >= 3 else "") if lvl else \
                f"Built {p['built'].get(k, 0)} times"
            screen.blit(a.text(extra, 15, S.CYAN), (r.x + 90, r.y + 56))
            for s in range(3):
                pygame.draw.polygon(screen, S.ENERGY if s < lvl else S.HUD_EDGE,
                                    [(r.right - 70 + s * 20, r.y + 12), (r.right - 64 + s * 20, r.y + 22),
                                     (r.right - 76 + s * 20, r.y + 22)])

    def render_profile(self, screen, a, p):
        g = self.game
        fav = max(p["built"], key=p["built"].get) if p["built"] else None
        nemesis = max(p["killed_by"], key=p["killed_by"].get) if p["killed_by"] else None
        hours = p["play_time"] / 3600
        lines = [("Aliens killed", f"{p['kills']:,}"), ("Bosses killed", f"{p['bosses']} ({len(p['boss_kinds'])}/10 kinds)"),
                 ("Towers built", f"{p['towers_built']:,}"),
                 ("Favorite tower", g.data["towers"][fav]["name"] if fav else "-"),
                 ("Alien that ended the most games",
                  f"{g.data['enemies'][nemesis]['name']} ({p['killed_by'][nemesis]})" if nemesis else "-"),
                 ("Best Endless wave", str(p["best_wave"])), ("Siege Runs won", str(p["runs_won"])),
                 ("Sectors won", f"{len(p['sectors_won'])}/12"), ("Fusions", str(p["fusions"])),
                 ("Named veterans", str(p["veterans"])), ("Aliens tamed", str(p["tamed"])),
                 ("Time played", f"{hours:.1f} h"),
                 ("Achievements", f"{len(g.save.get('achievements', []))}/{len(g.data['meta']['achievements'])}")]
        for i, (k, v) in enumerate(lines):
            y = 140 + i * 36
            screen.blit(a.text(k, 24, S.TEXT_DIM, True), (200, y))
            screen.blit(a.text(v, 24, S.WHITE, True), (700, y))

    def render_scores(self, screen, a, p):
        boards = self.game.save.get("leaderboard", {})
        if not boards:
            screen.blit(a.text("Play some games to fill the local leaderboards.", 24, S.TEXT_DIM), (200, 160))
            return
        keys = sorted(boards)[:9]
        for i, key in enumerate(keys):
            col, row = i % 3, i // 3
            x, y = 60 + col * 396, 130 + row * 180
            screen.blit(a.text(key.upper(), 18, S.CYAN, True), (x, y))
            for j, rec in enumerate(boards[key][:5]):
                w = f"  wave {rec['wave']}" if rec.get("wave") else ""
                screen.blit(a.text(f"{j + 1}. {rec['score']:,}{w}   {rec['date']}", 16, S.WHITE if j == 0 else S.TEXT_DIM),
                            (x, y + 26 + j * 22))

    def render_achievements(self, screen, a, p):
        g = self.game
        got = set(g.save.get("achievements", []))
        for i, (aid, ach) in enumerate(g.data["meta"]["achievements"].items()):
            col, row = i % 2, i // 2
            x, y = 80 + col * 580, 130 + row * 50
            done = aid in got
            cur = meta_sys.stat_value(p, ach["stat"])
            color = S.ENERGY if done else S.TEXT_DIM
            screen.blit(a.text(("[x] " if done else "[ ] ") + ach["name"], 20, color, True), (x, y))
            sub = ach["desc"] + ("" if done else f"  ({min(cur, ach['goal'])}/{ach['goal']})")
            if ach.get("skin"):
                sub += f"  - skin: {g.data['meta']['skins'][ach['skin']]['name']}"
            screen.blit(a.text(sub, 15, S.WHITE if done else S.TEXT_DIM), (x + 30, y + 22))


# ---- Map editor --------------------------------------------------------------------------
PALETTE = [(".", "Ground"), ("#", "Path"), ("S", "Spawn"), ("C", "Core"), ("X", "Rock"), ("H", "High ground"),
           ("R", "Resource"), ("K", "Crystal"), ("I", "Ice"), ("~", "Hazard")]
THEMES = ["desert", "frozen", "hive", "magma", "plains", "jungle", "crystal", "ruins", "gas", "orbital"]


def custom_levels():
    if not os.path.isdir(CUSTOM_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(CUSTOM_DIR) if f.endswith(".json"))


class EditorScene(Scene):
    """Paint a 40x20 sector: pick a tile (keys 1-0 or the palette), left-click paints,
    right-click erases. SAVE writes mods/levels/<name>.json; PLAY tests it in Endless."""
    CELL = 24
    X0, Y0 = 20, 60

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.tiles = [["."] * S.GRID_W for _ in range(S.GRID_H)]
        self.brush = 1
        self.theme = 0
        self.map_name = None
        self.loaded = -1
        self.msg = ("Paint a path from an S to a C, then SAVE or PLAY.", S.TEXT_DIM)
        x = self.X0 + S.GRID_W * self.CELL + 16
        self.palette = [Button((x, 60 + i * 36, 140, 32), label, "brush", i) for i, (_ch, label) in enumerate(PALETTE)]
        bx = x + 150
        self.buttons = [Button((bx, 60, 110, 36), "THEME", "theme"), Button((bx, 102, 110, 36), "CLEAR", "clear"),
                        Button((bx, 144, 110, 36), "LOAD", "load"), Button((bx, 186, 110, 36), "SAVE", "save"),
                        Button((bx, 228, 110, 36), "PLAY", "play"), Button((bx, 270, 110, 36), "BACK", "back")]

    def cell_at(self, pos):
        tx = (pos[0] - self.X0) // self.CELL
        ty = (pos[1] - self.Y0) // self.CELL
        if 0 <= tx < S.GRID_W and 0 <= ty < S.GRID_H:
            return tx, ty
        return None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and pygame.K_0 <= event.key <= pygame.K_9:
            self.brush = (event.key - pygame.K_1) % 10
            return
        if event.type == pygame.MOUSEMOTION and event.buttons[0] or event.type == pygame.MOUSEMOTION and event.buttons[2]:
            c = self.cell_at(self.input.to_canvas(event.pos))
            if c:
                self.paint(c, "." if event.buttons[2] else PALETTE[self.brush][0])
            return
        super().handle_event(event)

    def paint(self, cell, ch):
        tx, ty = cell
        self.tiles[ty][tx] = ch

    def level_data(self):
        return {"name": f"Custom - {self.map_name or 'Untitled'}", "theme": THEMES[self.theme], "core_hp": 100,
                "start_energy": 300, "build_time": 15, "tiles": ["".join(r) for r in self.tiles]}

    def validate(self):
        from ..core import EventBus
        from ..systems.level_system import LevelSystem
        path = os.path.join(CUSTOM_DIR, "_check.json")
        os.makedirs(CUSTOM_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.level_data(), f)
        try:
            LevelSystem(EventBus(), "_check")
            return None
        except (ValueError, KeyError) as err:
            return str(err).replace("_check: ", "")
        finally:
            os.remove(path)

    def save(self):
        problem = self.validate()
        if problem:
            self.msg = (f"Can't save: {problem}", S.RED)
            return None
        if self.map_name is None:
            n = 1
            while f"custom_{n}" in custom_levels():
                n += 1
            self.map_name = f"custom_{n}"
        with open(os.path.join(CUSTOM_DIR, self.map_name + ".json"), "w", encoding="utf-8") as f:
            json.dump(self.level_data(), f, indent=1)
        self.msg = (f"Saved mods/levels/{self.map_name}.json", S.GREEN)
        return self.map_name

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("level_select")
        elif cmd.name == "click":
            c = self.cell_at(cmd.pos)
            if c:
                self.paint(c, PALETTE[self.brush][0])
                return
            for b in self.palette:
                if b.hit(cmd.pos):
                    self.brush = b.value
            for b in self.buttons:
                if not b.hit(cmd.pos):
                    continue
                self.audio.play("click")
                if b.command == "theme":
                    self.theme = (self.theme + 1) % len(THEMES)
                elif b.command == "clear":
                    self.tiles = [["."] * S.GRID_W for _ in range(S.GRID_H)]
                    self.map_name = None
                elif b.command == "load":
                    levels = custom_levels()
                    if levels:
                        self.loaded = (self.loaded + 1) % len(levels)
                        self.map_name = levels[self.loaded]
                        with open(os.path.join(CUSTOM_DIR, self.map_name + ".json"), encoding="utf-8") as f:
                            d = json.load(f)
                        self.tiles = [list(r) for r in d["tiles"]]
                        self.theme = THEMES.index(d.get("theme", "desert")) if d.get("theme") in THEMES else 0
                        self.msg = (f"Loaded {self.map_name}", S.CYAN)
                    else:
                        self.msg = ("No custom maps yet", S.TEXT_DIM)
                elif b.command == "save":
                    self.save()
                elif b.command == "play":
                    name = self.save()
                    if name:
                        self.game.scenes.change("play", level_id=name, difficulty=self.game.difficulty, mode="endless")
                elif b.command == "back":
                    self.game.scenes.change("level_select")
        elif cmd.name == "right_click":
            c = self.cell_at(cmd.pos)
            if c:
                self.paint(c, ".")

    def on_render(self, screen):
        from ..systems.level_system import THEMES as LT
        a = self.assets
        screen.fill(S.SPACE)
        th = LT.get(THEMES[self.theme], LT["desert"])
        colors = {".": th["ground"], "#": th["path"], "S": S.MAGENTA, "C": S.CYAN, "X": th["rock"],
                  "H": th["light"], "R": S.ENERGY, "K": (150, 200, 255), "I": S.ICE, "~": S.ACID}
        for ty, row in enumerate(self.tiles):
            for tx, ch in enumerate(row):
                r = (self.X0 + tx * self.CELL, self.Y0 + ty * self.CELL, self.CELL - 1, self.CELL - 1)
                pygame.draw.rect(screen, colors.get(ch, S.WHITE), r)
                if ch in "SCRK":
                    t = a.text(ch, 16, S.SPACE, True)
                    screen.blit(t, t.get_rect(center=(r[0] + self.CELL // 2, r[1] + self.CELL // 2)))
        t = a.text(f"MAP EDITOR  -  {self.map_name or 'untitled'}  -  theme: {THEMES[self.theme]}", 26, S.CYAN, True)
        screen.blit(t, (self.X0, 18))
        mouse = self.input.mouse_pos()
        for b in self.palette:
            ch = PALETTE[b.value][0]
            b.label = f"{(b.value + 1) % 10}  {PALETTE[b.value][1]}"
            b.draw(screen, a, mouse, selected=b.value == self.brush, size=16)
            pygame.draw.rect(screen, colors.get(ch, S.WHITE), (b.rect.right - 18, b.rect.y + 8, 12, 16))
        for b in self.buttons:
            b.draw(screen, a, mouse, size=20)
        text, col = self.msg
        screen.blit(a.text(text, 18, col, True), (self.X0, self.Y0 + S.GRID_H * self.CELL + 10))
        screen.blit(a.text("Left-click/drag paints, right-click erases. Needs at least one S and one C joined by "
                           "path. Saved maps live in mods/levels/.", 16, S.TEXT_DIM),
                    (self.X0, self.Y0 + S.GRID_H * self.CELL + 34))

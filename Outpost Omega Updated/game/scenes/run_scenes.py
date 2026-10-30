"""Siege Run screens: sector map, reward drafts, Supply Cache, events, run end
and the Command Tech Lab. The run itself lives in game.run (systems/run.py);
these scenes only draw it and pass the player's choices back to it."""
import math

import pygame

from .. import settings as S
from ..systems.ui_system import Button
from .commander_picker import CommanderPicker
from .menu import Starfield
from .scene_manager import Scene

NODE_STYLE = {
    "combat": ("COMBAT", S.ALIEN_GREEN, "C", "3 waves on a random sector"),
    "elite": ("ELITE", S.ORANGE, "E", "3 waves, mostly elites. Drops a relic"),
    "cache": ("SUPPLY CACHE", S.ENERGY, "$", "Spend Scrap on towers, augments, relics, repairs"),
    "event": ("EVENT", S.CYAN, "?", "Something unexpected"),
    "boss": ("BOSS", S.MAGENTA, "B", "The Hive Overseer. Ends the act"),
}
KIND_STYLE = {"augment": ("AUGMENT", S.CYAN), "tower": ("TOWER", S.ALIEN_GREEN),
              "relic": ("RELIC", S.ENERGY), "repair": ("REPAIR", S.GREEN)}


# ---- drawing helpers -------------------------------------------------------------
def wrap(assets, text, size, width, color=S.WHITE, bold=False):
    """Greedy word wrap into a list of rendered lines."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and assets.text(trial, size, color, bold).get_width() > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return [assets.text(l, size, color, bold) for l in lines]


def blit_lines(screen, lines, x, y, gap=2, center=False):
    for surf in lines:
        if center:
            screen.blit(surf, surf.get_rect(midtop=(x, y)))
        else:
            screen.blit(surf, (x, y))
        y += surf.get_height() + gap
    return y


def card_style(run, kind, oid):
    label, color = KIND_STYLE[kind]
    if kind == "repair":
        hp = run.cfg["shop"]["repair_hp"]
        return "Core Repair", f"Heal the Core {hp} HP", label, color
    name, desc, cursed = run.describe(kind, oid)
    if cursed:
        label, color = "CURSED RELIC", S.RED
    return name, desc, label, color


def draw_card(screen, a, rect, run, kind, oid, hover=False, dim=False, footer=None):
    name, desc, label, color = card_style(run, kind, oid)
    pygame.draw.rect(screen, S.PANEL_HI if hover and not dim else S.PANEL, rect, border_radius=10)
    pygame.draw.rect(screen, color if not dim else S.HUD_EDGE, rect, 3 if hover else 2, border_radius=10)
    pygame.draw.rect(screen, color, (rect.x + 3, rect.y + 3, rect.w - 6, 26),
                     border_top_left_radius=8, border_top_right_radius=8)
    tag = a.text(label, 16, S.SPACE, True)
    screen.blit(tag, tag.get_rect(center=(rect.centerx, rect.y + 16)))
    y = rect.y + 40
    if kind == "tower":
        icon = a.get(f"turret_{oid}")
        icon = pygame.transform.scale(icon, (icon.get_width() * 2, icon.get_height() * 2))
        screen.blit(icon, icon.get_rect(midtop=(rect.centerx, y)))
        y += icon.get_height() + 6
    y = blit_lines(screen, wrap(a, name, 24, rect.w - 24, S.WHITE if not dim else S.TEXT_DIM, True),
                   rect.centerx, y, center=True)
    blit_lines(screen, wrap(a, desc, 18, rect.w - 28, S.TEXT_DIM), rect.centerx, y + 10, center=True)
    if footer:
        text, fcolor = footer
        f = a.text(text, 22, fcolor, True)
        screen.blit(f, f.get_rect(center=(rect.centerx, rect.bottom - 22)))


def draw_run_bar(screen, a, run, title=None):
    """Top strip: act, Core HP, Scrap and owned towers."""
    pygame.draw.rect(screen, S.HUD_BG, (0, 0, S.SCREEN_W, 72))
    pygame.draw.line(screen, S.HUD_EDGE, (0, 72), (S.SCREEN_W, 72), 2)
    screen.blit(a.text(title or f"SIEGE RUN  -  ACT {run.act}/{run.cfg['acts']}", 30, S.CYAN, True), (20, 10))
    cls = getattr(run, "commander", None) or "vanguard"
    screen.blit(a.text(f"{cls.title()}   Sectors cleared {run.nodes_cleared}   Kills {run.kills}", 18,
                       S.TEXT_DIM), (20, 44))
    x = 430
    screen.blit(a.text("CORE", 16, S.TEXT_DIM, True), (x, 12))
    frac = run.core_hp / run.core_max
    pygame.draw.rect(screen, (40, 10, 16), (x, 32, 220, 18), border_radius=3)
    pygame.draw.rect(screen, S.CYAN if frac > 0.5 else S.RED, (x, 32, int(220 * frac), 18), border_radius=3)
    hp = a.text(f"{int(run.core_hp)}/{run.core_max}", 18, S.WHITE, True)
    screen.blit(hp, hp.get_rect(center=(x + 110, 41)))
    screen.blit(a.text("SCRAP", 16, S.TEXT_DIM, True), (680, 12))
    screen.blit(a.text(str(run.scrap), 30, S.ENERGY, True), (680, 30))
    screen.blit(a.text("TOWERS", 16, S.TEXT_DIM, True), (790, 12))
    for i, kind in enumerate(run.towers):
        a.blit_centered(screen, f"turret_{kind}", (806 + i * 38, 48))


def tooltip(screen, a, pos, lines, color=S.WHITE):
    surfs = [a.text(l, 18, color if i == 0 else S.TEXT_DIM, i == 0) for i, l in enumerate(lines)]
    w = max(s.get_width() for s in surfs) + 20
    h = sum(s.get_height() + 2 for s in surfs) + 12
    x = min(pos[0] + 16, S.SCREEN_W - w - 6)
    y = min(pos[1] + 16, S.SCREEN_H - h - 6)
    pygame.draw.rect(screen, S.HUD_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, S.HUD_EDGE, (x, y, w, h), 1, border_radius=6)
    blit_lines(screen, surfs, x + 10, y + 6)


class _RunScene(Scene):
    """Shared background, plus a guard for when no run is active."""

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.bg = Starfield()
        self.run = game.run
        self.t = 0.0

    def on_update(self, dt):
        self.t += dt
        self.bg.update(dt)


# ---- sector map -----------------------------------------------------------------------
class RunMapScene(_RunScene):
    MAP_X0, MAP_X1, MAP_Y0, MAP_Y1 = 110, 1170, 110, 520

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.btn_menu = Button((S.SCREEN_W - 260, 16, 110, 40), "MENU", "menu")
        self.btn_abandon = Button((S.SCREEN_W - 140, 16, 124, 40), "ABANDON", "abandon")
        self.tips = []

    def on_start(self):
        self.game.save_run()   # resume from here if the game is closed

    def on_update(self, dt):
        super().on_update(dt)
        if self.run is None or self.run.over:
            self.game.scenes.change("run_end" if self.run else "menu")

    def node_pos(self, node):
        floors = len(self.run.map)
        x = self.MAP_X0 + node["floor"] * (self.MAP_X1 - self.MAP_X0) / max(1, floors - 1)
        y = self.MAP_Y0 + node["x"] * (self.MAP_Y1 - self.MAP_Y0)
        return int(x), int(y)

    def node_at(self, pos):
        for layer in self.run.map:
            for n in layer:
                x, y = self.node_pos(n)
                r = 34 if n["type"] == "boss" else 26
                if (pos[0] - x) ** 2 + (pos[1] - y) ** 2 <= r * r:
                    return n
        return None

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        elif cmd.name == "click":
            if self.btn_menu.hit(cmd.pos):
                self.game.scenes.change("menu")
                return
            if self.btn_abandon.hit(cmd.pos):
                self.run.fail()
                self.game.scenes.change("run_end")
                return
            node = self.node_at(cmd.pos)
            if node and node in self.run.available_nodes():
                self.audio.play("click")
                kind = self.run.enter(node)
                if kind in ("combat", "elite", "boss"):
                    self.game.scenes.change("play", level_id=node["sector"],
                                            difficulty=self.game.difficulty, mode="run")
                elif kind == "cache":
                    self.game.scenes.change("run_shop")
                else:
                    self.game.scenes.change("run_event")
            elif node:
                self.audio.play("error")

    def on_render(self, screen):
        if self.run is None:
            return
        a, run = self.assets, self.run
        self.bg.draw(screen)
        draw_run_bar(screen, a, run)
        mouse = self.input.mouse_pos()
        self.btn_menu.draw(screen, a, mouse, size=22)
        self.btn_abandon.draw(screen, a, mouse, size=22)
        avail = run.available_nodes()
        avail_ids = {n["id"] for n in avail}
        # edges
        for layer in run.map:
            for n in layer:
                p = self.node_pos(n)
                for nid in n["next"]:
                    m = run.node_by_id(nid)
                    taken = n["id"] in run.visited and nid in run.visited
                    reachable = run.position is n and nid in avail_ids
                    color = S.CYAN if taken else (S.STEEL if reachable else S.HUD_EDGE)
                    pygame.draw.line(screen, color, p, self.node_pos(m), 3 if (taken or reachable) else 2)
        # nodes
        hovered = self.node_at(mouse)
        for layer in run.map:
            for n in layer:
                x, y = self.node_pos(n)
                label, color, letter, _desc = NODE_STYLE[n["type"]]
                r = 34 if n["type"] == "boss" else 26
                done = n["id"] in run.visited
                open_ = n["id"] in avail_ids
                if open_:
                    pulse = 6 + 3 * math.sin(self.t * 4)
                    pygame.draw.circle(screen, color, (x, y), int(r + pulse), 2)
                fill = color if done else (S.PANEL_HI if n is hovered and open_ else S.PANEL)
                pygame.draw.circle(screen, fill, (x, y), r)
                pygame.draw.circle(screen, color if (open_ or done) else S.HUD_EDGE, (x, y), r, 3)
                t = a.text(letter, 30 if n["type"] == "boss" else 26,
                           S.SPACE if done else (color if open_ else S.TEXT_DIM), True)
                screen.blit(t, t.get_rect(center=(x, y + 1)))
        # floor labels
        for f in range(len(run.map)):
            x = self.MAP_X0 + f * (self.MAP_X1 - self.MAP_X0) / max(1, len(run.map) - 1)
            t = a.text(f"FLOOR {f + 1}" if f < len(run.map) - 1 else "BOSS", 16, S.TEXT_DIM, True)
            screen.blit(t, t.get_rect(center=(int(x), 92)))
        hint = "Pick a glowing node to continue" if avail else ""
        h = a.text(hint, 20, S.TEXT_DIM)
        screen.blit(h, h.get_rect(center=(S.SCREEN_W // 2, 540)))
        self.render_loadout(screen, mouse)
        if hovered:
            label, color, _l, desc = NODE_STYLE[hovered["type"]]
            lines = [label, desc]
            if hovered["type"] in ("combat", "elite", "boss"):
                names = {"sector1": "Desert Outpost", "sector2": "Frozen Relay Station",
                         "sector3": "Hive Crash Site", "sector4": "Magma Forge", "sector5": "Open Plains",
                         "sector6": "Orbital Platform", "sector7": "Derelict Ship", "sector8": "Twin Cores"}
                sid = hovered["sector"]
                lines.append("Map: " + ("Uncharted (generated)" if sid.startswith("proc_") else names.get(sid, sid)))
                lines.append(f"Starts at threat level {run.wave_start(hovered)}")
            tooltip(screen, a, mouse, lines, color)
        for rect, lines, color in self.tips:
            if rect.collidepoint(mouse):
                tooltip(screen, a, mouse, lines, color)

    def render_loadout(self, screen, mouse):
        a, run = self.assets, self.run
        panel = pygame.Rect(20, 560, S.SCREEN_W - 40, 148)
        pygame.draw.rect(screen, S.HUD_BG, panel, border_radius=10)
        pygame.draw.rect(screen, S.HUD_EDGE, panel, 2, border_radius=10)
        self.tips = []
        screen.blit(a.text(f"AUGMENTS ({len(run.augments)})", 18, S.CYAN, True), (40, 572))
        for i, aid in enumerate(run.augments[:18]):
            aug = run.cfg["augments"][aid]
            col, row = divmod(i, 5)
            pos = (40 + col * 200, 598 + row * 21)
            surf = a.text(aug["name"], 18, S.WHITE)
            screen.blit(surf, pos)
            self.tips.append((surf.get_rect(topleft=pos), [aug["name"], aug["desc"]], S.CYAN))
        if not run.augments:
            screen.blit(a.text("None yet. Win sectors to draft them.", 18, S.TEXT_DIM), (40, 598))
        rx = 880
        screen.blit(a.text(f"RELICS ({len(run.relics)})", 18, S.ENERGY, True), (rx, 572))
        for i, rid in enumerate(run.relics[:10]):
            rel = run.cfg["relics"][rid]
            col, row = divmod(i, 5)
            pos = (rx + col * 180, 598 + row * 21)
            color = S.RED if rel.get("cursed") else S.WHITE
            surf = a.text(rel["name"], 18, color)
            screen.blit(surf, pos)
            self.tips.append((surf.get_rect(topleft=pos), [rel["name"], rel["desc"]],
                              S.RED if rel.get("cursed") else S.ENERGY))
        if not run.relics:
            screen.blit(a.text("Beat elites and bosses for relics.", 18, S.TEXT_DIM), (rx, 598))


# ---- rewards ---------------------------------------------------------------------------
class RunRewardScene(_RunScene):
    CARD_W, CARD_H, CARD_Y = 250, 300, 220

    def __init__(self, game, reward=None, **kwargs):
        super().__init__(game, **kwargs)
        self.reward = reward or {"steps": [], "scrap": 0}
        self.steps = list(self.reward.get("steps", []))
        self.options = []
        self.btn_skip = Button((S.SCREEN_W // 2 - 120, 560, 240, 50), "SKIP", "skip")
        self.next_step()

    def next_step(self):
        self.options = []
        while self.steps and not self.options:
            step = self.steps.pop(0)
            if step == "draft":
                self.options = self.run.draft_options()
                self.title = "CHOOSE AN UPGRADE"
                self.btn_skip.label = f"SKIP (+{self.run.cfg.get('skip_scrap', 10)} Scrap)"
                self.skip_scrap = self.run.cfg.get("skip_scrap", 10)
            else:
                boss = self.reward.get("node") == "boss"
                n = self.run.cfg["boss_relic_choices" if boss else "relic_choices"]
                self.options = self.run.relic_options(n)
                self.title = "CHOOSE A RELIC"
                self.btn_skip.label = "SKIP"
                self.skip_scrap = 0

    def done(self):
        if self.run.over:
            self.game.scenes.change("run_end")
        else:
            self.game.scenes.change("run_map")

    def card_rects(self):
        n = len(self.options)
        total = n * self.CARD_W + (n - 1) * 30
        x0 = S.SCREEN_W // 2 - total // 2
        return [pygame.Rect(x0 + i * (self.CARD_W + 30), self.CARD_Y, self.CARD_W, self.CARD_H)
                for i in range(n)]

    def on_update(self, dt):
        super().on_update(dt)
        if not self.options:
            self.done()

    def handle_command(self, cmd):
        if cmd.name != "click" or not self.options:
            return
        for rect, (kind, oid) in zip(self.card_rects(), self.options):
            if rect.collidepoint(cmd.pos):
                self.audio.play("upgrade")
                self.run.take(kind, oid)
                self.next_step()
                return
        if self.btn_skip.hit(cmd.pos):
            self.audio.play("click")
            if self.skip_scrap:
                self.run.gain_scrap(self.skip_scrap)
            self.next_step()

    def on_render(self, screen):
        if not self.options:
            return
        a = self.assets
        self.bg.draw(screen)
        draw_run_bar(screen, a, self.run)
        head = "ACT COMPLETE" if self.reward.get("next_act") else "SECTOR CLEARED"
        t = a.text(head, 48, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, 116)))
        bits = []
        if self.reward.get("scrap"):
            bits.append(f"+{self.reward['scrap']} Scrap")
        if self.reward.get("healed"):
            bits.append(f"Core healed {self.reward['healed']} HP")
        if bits:
            sub = a.text("   ".join(bits), 24, S.ENERGY, True)
            screen.blit(sub, sub.get_rect(center=(S.SCREEN_W // 2, 156)))
        title = a.text(self.title, 28, S.WHITE, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 194)))
        mouse = self.input.mouse_pos()
        for rect, (kind, oid) in zip(self.card_rects(), self.options):
            draw_card(screen, a, rect, self.run, kind, oid, hover=rect.collidepoint(mouse))
        self.btn_skip.draw(screen, a, mouse, size=24)


# ---- supply cache -------------------------------------------------------------------------
class ShopScene(_RunScene):
    CARD_W, CARD_H, GAP = 160, 270, 14

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        if self.run is not None and self.run.shop is None:
            self.run.shop = self.run.make_shop()
        self.btn_leave = Button((S.SCREEN_W // 2 - 120, 600, 240, 52), "LEAVE", "leave")

    def card_rects(self):
        n = len(self.run.shop)
        total = n * self.CARD_W + (n - 1) * self.GAP
        x0 = S.SCREEN_W // 2 - total // 2
        return [pygame.Rect(x0 + i * (self.CARD_W + self.GAP), 210, self.CARD_W, self.CARD_H)
                for i in range(n)]

    def handle_command(self, cmd):
        if cmd.name != "click" or self.run is None:
            return
        for rect, offer in zip(self.card_rects(), self.run.shop):
            if rect.collidepoint(cmd.pos):
                self.audio.play("build" if self.run.buy(offer) else "error")
                return
        if self.btn_leave.hit(cmd.pos):
            self.audio.play("click")
            self.run.complete_node()
            self.game.scenes.change("run_map")

    def on_render(self, screen):
        if self.run is None or self.run.shop is None:
            return
        a, run = self.assets, self.run
        self.bg.draw(screen)
        draw_run_bar(screen, a, run)
        t = a.text("SUPPLY CACHE", 48, S.ENERGY, True)
        screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, 120)))
        sub = a.text("Spend Scrap. Repairs can be bought more than once.", 22, S.TEXT_DIM)
        screen.blit(sub, sub.get_rect(center=(S.SCREEN_W // 2, 165)))
        mouse = self.input.mouse_pos()
        for rect, offer in zip(self.card_rects(), run.shop):
            afford = run.scrap >= offer["price"]
            if offer["sold"]:
                footer = ("SOLD", S.TEXT_DIM)
            else:
                footer = (f"{offer['price']} Scrap", S.ENERGY if afford else S.RED)
            draw_card(screen, a, rect, run, offer["kind"], offer["id"],
                      hover=rect.collidepoint(mouse) and afford and not offer["sold"],
                      dim=offer["sold"], footer=footer)
        self.btn_leave.draw(screen, a, mouse, size=28)


# ---- events ---------------------------------------------------------------------------------
class EventScene(_RunScene):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.event_id = self.run.pick_event() if self.run else None
        self.event = self.run.cfg["events"][self.event_id] if self.run else None
        self.result = None
        cx = S.SCREEN_W // 2
        self.buttons = []
        if self.event:
            for i, choice in enumerate(self.event["choices"]):
                self.buttons.append(Button((cx - 330, 400 + i * 76, 660, 64), choice["label"], "choice", i))
        self.btn_continue = Button((cx - 120, 560, 240, 52), "CONTINUE", "continue")

    def handle_command(self, cmd):
        if cmd.name != "click" or self.event is None:
            return
        if self.result is not None:
            if self.btn_continue.hit(cmd.pos):
                self.audio.play("click")
                self.run.complete_node()
                self.game.scenes.change("run_map")
            return
        for b in self.buttons:
            choice = self.event["choices"][b.value]
            if b.rect.collidepoint(cmd.pos):
                if self.run.can_afford(choice):
                    self.audio.play("upgrade")
                    self.result = self.run.resolve_choice(choice)
                else:
                    self.audio.play("error")
                return

    def on_render(self, screen):
        if self.event is None:
            return
        a, run = self.assets, self.run
        self.bg.draw(screen)
        draw_run_bar(screen, a, run)
        cx = S.SCREEN_W // 2
        panel = pygame.Rect(cx - 380, 100, 760, 580)
        pygame.draw.rect(screen, S.HUD_BG, panel, border_radius=12)
        pygame.draw.rect(screen, S.CYAN, panel, 2, border_radius=12)
        t = a.text(self.event["title"].upper(), 42, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(cx, 150)))
        blit_lines(screen, wrap(a, self.event["text"], 24, 660, S.WHITE), cx, 200, gap=4, center=True)
        mouse = self.input.mouse_pos()
        if self.result is None:
            for b in self.buttons:
                choice = self.event["choices"][b.value]
                b.enabled = run.can_afford(choice)
                b.draw(screen, a, mouse, size=26, sub=choice.get("sub"))
        else:
            y = 400
            for line in self.result:
                s = a.text(line, 28, S.ENERGY, True)
                screen.blit(s, s.get_rect(center=(cx, y)))
                y += 38
            self.btn_continue.draw(screen, a, mouse, size=28)


# ---- run end -------------------------------------------------------------------------------
class RunEndScene(_RunScene):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.ended = self.run
        if self.ended is not None:
            self.ended.finish(self.ended.victory)
            game.bank_run(self.ended)
        cx = S.SCREEN_W // 2
        self.buttons = [Button((cx - 150, 470, 300, 52), "NEW RUN", "new"),
                        Button((cx - 150, 536, 300, 52), "TECH LAB", "tech"),
                        Button((cx - 150, 602, 300, 52), "MAIN MENU", "menu")]

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        if cmd.name != "click":
            return
        for b in self.buttons:
            if b.hit(cmd.pos):
                self.audio.play("click")
                if b.command == "new":
                    self.game.start_run()
                    self.game.scenes.change("run_map")
                elif b.command == "tech":
                    self.game.scenes.change("tech_lab")
                else:
                    self.audio.stop_music()
                    self.game.scenes.change("menu")

    def on_render(self, screen):
        a = self.assets
        self.bg.draw(screen)
        run = self.ended
        cx = S.SCREEN_W // 2
        if run is None:
            return
        title, color = ("VICTORY", S.CYAN) if run.victory else ("RUN OVER", S.RED)
        t = a.text(title, 90, color, True)
        screen.blit(t, t.get_rect(center=(cx, 120)))
        lines = [f"Reached act {run.act} of {run.cfg['acts']}",
                 f"Sectors cleared {run.nodes_cleared}   Elites {run.elites}   Bosses {run.bosses}",
                 f"Aliens destroyed {run.kills}   Score {run.score}",
                 f"{len(run.augments)} augments   {len(run.relics)} relics   {len(run.towers)} towers"]
        for i, line in enumerate(lines):
            s = a.text(line, 28, S.WHITE)
            screen.blit(s, s.get_rect(center=(cx, 220 + i * 38)))
        s = a.text(f"+{run.salvage_earned} Salvage   (total {self.game.salvage})", 32, S.ENERGY, True)
        screen.blit(s, s.get_rect(center=(cx, 400)))
        mouse = self.input.mouse_pos()
        for b in self.buttons:
            b.draw(screen, a, mouse, size=28)


# ---- tech lab ---------------------------------------------------------------------------------
class TechLabScene(Scene):
    CARD_W, CARD_H, GAP = 280, 190, 20

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.bg = Starfield()
        self.ids = list(game.data["tech"])
        self.btn_back = Button((40, S.SCREEN_H - 80, 140, 46), "BACK", "back")
        self.picker = CommanderPicker(game, 590)

    def card_rects(self):
        cols = 4
        x0 = S.SCREEN_W // 2 - (cols * self.CARD_W + (cols - 1) * self.GAP) // 2
        return [pygame.Rect(x0 + (i % cols) * (self.CARD_W + self.GAP),
                            170 + (i // cols) * (self.CARD_H + self.GAP), self.CARD_W, self.CARD_H)
                for i in range(len(self.ids))]

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        elif cmd.name == "click":
            if self.btn_back.hit(cmd.pos):
                self.game.scenes.change("menu")
                return
            if self.picker.handle_click(cmd.pos):
                self.audio.play("click")
                return
            for rect, tid in zip(self.card_rects(), self.ids):
                if rect.collidepoint(cmd.pos):
                    self.audio.play("upgrade" if self.game.buy_tech(tid) else "error")

    def on_update(self, dt):
        self.bg.update(dt)

    def on_render(self, screen):
        a = self.assets
        self.bg.draw(screen)
        t = a.text("COMMAND TECH LAB", 60, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, 70)))
        s = a.text(f"Salvage: {self.game.salvage}", 30, S.ENERGY, True)
        screen.blit(s, s.get_rect(center=(S.SCREEN_W // 2, 122)))
        mouse = self.input.mouse_pos()
        ranks = self.game.tech_ranks
        for rect, tid in zip(self.card_rects(), self.ids):
            node = self.game.data["tech"][tid]
            rank, maxr = ranks.get(tid, 0), len(node["costs"])
            maxed = rank >= maxr
            cost = None if maxed else node["costs"][rank]
            afford = cost is not None and self.game.salvage >= cost
            hover = rect.collidepoint(mouse) and afford
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, rect, border_radius=10)
            edge = S.GREEN if maxed else (S.CYAN if afford else S.HUD_EDGE)
            pygame.draw.rect(screen, edge, rect, 3 if hover else 2, border_radius=10)
            screen.blit(a.text(node["name"], 24, S.WHITE, True), (rect.x + 14, rect.y + 12))
            blit_lines(screen, wrap(a, node["desc"], 18, rect.w - 28, S.TEXT_DIM), rect.x + 14, rect.y + 44)
            for i in range(maxr):
                pip = pygame.Rect(rect.x + 14 + i * 26, rect.bottom - 64, 20, 12)
                pygame.draw.rect(screen, S.CYAN if i < rank else S.STEEL_DARK, pip, border_radius=3)
            label, color = ("MAXED", S.GREEN) if maxed else (f"{cost} Salvage", S.ENERGY if afford else S.RED)
            screen.blit(a.text(label, 22, color, True), (rect.x + 14, rect.bottom - 40))
        self.picker.draw(screen, a, mouse)
        hint = a.text("Upgrades and the Commander apply when a new Siege Run starts.", 20, S.TEXT_DIM)
        screen.blit(hint, hint.get_rect(center=(S.SCREEN_W // 2, S.SCREEN_H - 40)))
        self.btn_back.draw(screen, a, mouse, size=28)

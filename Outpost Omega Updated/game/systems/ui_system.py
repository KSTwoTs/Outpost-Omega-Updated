"""UISystem: buttons, the 80 px HUD bar, toasts, wave banners and the F1
debug overlay. Clicking the HUD returns the same Command objects the
keyboard produces, so the HUD and hotkeys share one code path."""
import pygame

from .. import settings as S
from .endless import summarize
from .input_system import Command


class Button:
    def __init__(self, rect, label, command, value=None, enabled=True, hotkey=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.command = command
        self.value = value
        self.enabled = enabled
        self.hotkey = hotkey

    def hit(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, screen, assets, mouse, selected=False, size=24, sub=None):
        hover = self.enabled and self.rect.collidepoint(mouse)
        bg = S.PANEL_HI if (hover or selected) else S.PANEL
        pygame.draw.rect(screen, bg, self.rect, border_radius=6)
        edge = S.CYAN if selected else (S.STEEL if hover else S.HUD_EDGE)
        pygame.draw.rect(screen, edge, self.rect, 2, border_radius=6)
        color = S.WHITE if self.enabled else S.TEXT_DIM
        label = assets.text(self.label, size, color, bold=True)
        cy = self.rect.centery - (7 if sub else 0)
        screen.blit(label, label.get_rect(center=(self.rect.centerx, cy)))
        if sub:
            s = assets.text(sub, 18, S.TEXT_DIM if self.enabled else (90, 96, 120))
            screen.blit(s, s.get_rect(center=(self.rect.centerx, cy + 17)))
        if self.hotkey:
            hk = assets.text(self.hotkey, 16, S.TEXT_DIM)
            screen.blit(hk, (self.rect.x + 5, self.rect.y + 4))


class UISystem:
    TOWER_BTN_X = 236
    TOWER_BTN_W = 30
    TOWER_BTN_PITCH = 32
    HOTKEYS = {11: "-", 12: "=", 13: "\\"}

    def __init__(self, assets, tower_data):
        self.assets = assets
        self.tower_data = tower_data
        self.toasts = []         # [text_surface, life]
        self.banner = None       # [title, subtitle, life]
        self.tower_buttons = []
        order = sorted(tower_data.items(), key=lambda kv: kv[1]["key"])
        for i, (kind, d) in enumerate(order):
            rect = (self.TOWER_BTN_X + i * self.TOWER_BTN_PITCH, S.HUD_Y + 8, self.TOWER_BTN_W, 64)
            hotkey = self.HOTKEYS.get(d["key"], str(d["key"] % 10))
            b = Button(rect, "", "select_tower", d["key"], d.get("enabled", True), hotkey)
            b.kind = kind
            self.tower_buttons.append(b)
        y = S.HUD_Y + 44
        self.btn_upgrade = Button((652, y, 92, 28), "Upgrade", "upgrade", hotkey="U")
        self.btn_sell = Button((750, y, 84, 28), "Sell", "sell", hotkey="X")
        self.btn_target = Button((840, y, 96, 28), "Target", "cycle_targeting", hotkey="T")
        self.btn_wave = Button((1110, S.HUD_Y + 8, 162, 30), "Start Wave", "start_wave", hotkey="Spc")
        self.btn_pause = Button((1236, 8, 36, 28), "II", "pause")
        self.branch_tower = None   # tower whose tier-4 choice panel is open
        self.core_selected = False # Omega Core upgrade panel
        self.core_buttons = [Button((652, y, 92, 28), "", "core_upgrade", "turret"),
                             Button((750, y, 84, 28), "", "core_upgrade", "shield"),
                             Button((840, y, 96, 28), "", "core_upgrade", "regen")]
        self.perk_visible = False

    # ---- messages ---------------------------------------------------------------
    def toast(self, text, color=S.WHITE):
        # Same message already showing? Just restart its timer instead of stacking.
        for t in self.toasts:
            if t[2] == text:
                t[1] = 1.8
                return
        self.toasts.append([self.assets.text(text, 26, color, bold=True), 1.8, text])
        self.toasts = self.toasts[-4:]

    def show_banner(self, title, subtitle="", duration=2.0):
        self.banner = [title, subtitle, duration, duration]

    def on_update(self, dt):
        for t in self.toasts:
            t[1] -= dt
        self.toasts = [t for t in self.toasts if t[1] > 0]
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None

    # ---- input ----------------------------------------------------------------------
    def handle_click(self, pos, play):
        """Return a Command if a HUD element was clicked, else None."""
        if self.btn_pause.hit(pos):
            return Command("pause")
        if self.branch_tower is not None:
            for i, rect in enumerate(self.branch_rects()):
                if rect.collidepoint(pos):
                    return Command("choose_branch", value=i)
            self.branch_tower = None
            return Command("hud_click")
        if self.perk_visible:
            for i, rect in enumerate(self.perk_rects()):
                if rect.collidepoint(pos):
                    return Command("choose_perk", value=i)
        if pos[1] < S.HUD_Y:
            return None
        for b in self.tower_buttons:
            if b.rect.collidepoint(pos):
                return Command("select_tower", value=b.value)
        if self.core_selected and not play.towers.selected:
            for b in self.core_buttons:
                if b.hit(pos):
                    return Command("core_upgrade", value=b.value)
        if play.towers.selected:
            for b in (self.btn_upgrade, self.btn_sell, self.btn_target):
                if b.hit(pos):
                    return Command(b.command)
        if play.waves.phase == "build" and self.btn_wave.hit(pos):
            return Command("start_wave")
        return Command("hud_click")   # swallow clicks on empty HUD space

    # ---- drawing --------------------------------------------------------------------
    def bar(self, screen, x, y, w, h, frac, color, back=(40, 10, 16)):
        pygame.draw.rect(screen, back, (x, y, w, h), border_radius=3)
        pygame.draw.rect(screen, color, (x, y, int(w * max(0.0, min(1.0, frac))), h), border_radius=3)
        pygame.draw.rect(screen, S.HUD_EDGE, (x, y, w, h), 1, border_radius=3)

    def render_hud(self, screen, play, mouse):
        a = self.assets
        session, towers, waves, player = play.session, play.towers, play.waves, play.player
        pygame.draw.rect(screen, S.HUD_BG, (0, S.HUD_Y, S.SCREEN_W, S.HUD_H))
        pygame.draw.line(screen, S.HUD_EDGE, (0, S.HUD_Y), (S.SCREEN_W, S.HUD_Y), 2)

        # Core + Energy
        screen.blit(a.text("OMEGA CORE", 18, S.TEXT_DIM, True), (12, S.HUD_Y + 8))
        frac = session.core_hp / session.core_max
        self.bar(screen, 12, S.HUD_Y + 24, 214, 16, frac, S.CYAN if frac > 0.5 else S.RED)
        hp = a.text(f"{int(session.core_hp)}/{session.core_max}", 18, S.WHITE)
        screen.blit(hp, hp.get_rect(center=(119, S.HUD_Y + 32)))
        a.blit_centered(screen, "energy_crystal", (22, S.HUD_Y + 60))
        screen.blit(a.text(f"{session.energy} E", 30, S.ENERGY, True), (38, S.HUD_Y + 49))
        screen.blit(a.text(f"Score {session.score}", 20, S.TEXT_DIM), (140, S.HUD_Y + 54))

        # Tower build buttons
        for b in self.tower_buttons:
            d = self.tower_data[b.kind]
            sel = towers.build_kind == b.kind
            b.draw(screen, a, mouse, selected=sel)
            icon = pygame.transform.smoothscale(a.get(f"turret_{b.kind}"), (24, 24))
            if not b.enabled:
                icon.set_alpha(70)
            screen.blit(icon, icon.get_rect(center=(b.rect.centerx, b.rect.y + 28)))
            if b.enabled:
                color = S.ENERGY if session.energy >= d["cost"] else S.RED
                cost = a.text(str(d["cost"]), 15, color, True)
            else:
                cost = a.text("--", 16, S.TEXT_DIM, True)
            screen.blit(cost, cost.get_rect(center=(b.rect.centerx, b.rect.bottom - 10)))

        # Info panel
        px = 652
        t = towers.selected
        if t:
            title = f"{t.name}  T{t.tier + 1}" if t.branch is None else f"{t.branch_name}  T4"
            screen.blit(a.text(title, 24, S.WHITE if t.branch is None else S.MAGENTA, True), (px, S.HUD_Y + 8))
            extra = f"+{t.stats['income']}E/wave" if t.behavior == "income" else f"Target: {t.targeting}"
            if t.kills:
                extra += f"   Kills {t.kills}" + (f" (Vet {t.vet_rank})" if t.vet_rank else "")
            info = f"HP {int(t.health.hp)}/{int(t.health.max_hp)}   {extra}"
            screen.blit(a.text(info, 18, S.TEXT_DIM), (px, S.HUD_Y + 27))
            self.btn_upgrade.enabled = t.can_upgrade or bool(t.branch_available)
            if t.can_upgrade:
                self.btn_upgrade.label = f"Up {t.upgrade_cost}E"
            elif t.branch_available:
                self.btn_upgrade.label = "Tier 4"
            else:
                self.btn_upgrade.label = "Up MAX"
            self.btn_sell.label = f"+{t.sell_value}E"
            for b in (self.btn_upgrade, self.btn_sell, self.btn_target):
                b.draw(screen, a, mouse, size=20)
        elif self.core_selected and not towers.build_kind:
            core = play.core
            screen.blit(a.text("OMEGA CORE upgrades", 24, S.CYAN, True), (px, S.HUD_Y + 8))
            lv = core.levels
            info = (f"Gun L{lv['turret']}   Shield {core.SHIELD[lv['shield']]}/wave   "
                    f"Regen +{core.REGEN[lv['regen']]}")
            screen.blit(a.text(info, 18, S.TEXT_DIM), (px, S.HUD_Y + 27))
            for b in self.core_buttons:
                cost = core.cost(b.value)
                b.enabled = cost is not None
                b.label = f"{core.NAMES[b.value]} {cost}" if cost is not None else f"{core.NAMES[b.value]} MAX"
                b.draw(screen, a, mouse, size=18)
        elif towers.build_kind:
            d = self.tower_data[towers.build_kind]
            screen.blit(a.text(f"{d['name']}  ({d['cost']} E)", 24, S.WHITE, True), (px, S.HUD_Y + 8))
            screen.blit(a.text(d["description"], 18, S.TEXT_DIM), (px, S.HUD_Y + 30))
            screen.blit(a.text("Shift+click: build more   R-click: cancel", 18, S.TEXT_DIM),
                        (px, S.HUD_Y + 50))
        else:
            lines = ["WASD move   E repair   Q orbital strike",
                     "1-0 - = \\ build   click tower: select   F speed",
                     "R-click tower: upgrade   Esc: pause   F1 debug"]
            for i, line in enumerate(lines):
                screen.blit(a.text(line, 18, S.TEXT_DIM), (px, S.HUD_Y + 10 + i * 20))

        # Wave / Commander panel
        rx = 950
        if waves.endless:
            wave_txt = f"WAVE {waves.wave_number}"
        else:
            wave_txt = f"WAVE {waves.wave_number}/{waves.total_waves}"
        label = a.text(wave_txt, 26, S.WHITE, True)
        screen.blit(label, (rx, S.HUD_Y + 8))
        if play.speed > 1:
            screen.blit(a.text(f"{play.speed}x", 20, S.CYAN, True),
                        (rx + label.get_width() + 8, S.HUD_Y + 11))
        if waves.phase == "build":
            secs = max(0, int(waves.countdown + 0.99))
            screen.blit(a.text(f"Next in {secs}s", 18, S.ENERGY), (rx, S.HUD_Y + 30))
            self.btn_wave.draw(screen, a, mouse, size=22)
        elif waves.phase == "wave":
            left = waves.remaining_in_queue + play.enemies.alive_count
            screen.blit(a.text(f"Aliens left: {left}", 18, S.ALIEN_GREEN), (rx, S.HUD_Y + 30))
        cmd = player.commander
        prog = play.progress
        screen.blit(a.text(f"VANCE {prog.level}", 16, S.TEXT_DIM, True), (rx, S.HUD_Y + 50))
        pygame.draw.rect(screen, S.ENERGY, (rx + 66, S.HUD_Y + 61, int(110 * prog.xp / prog.xp_needed()), 2))
        if cmd.alive:
            self.bar(screen, rx + 66, S.HUD_Y + 50, 110, 10, cmd.health.ratio, S.CYAN)
        else:
            screen.blit(a.text(f"DOWNED {cmd.respawn_timer:.1f}s", 16, S.RED, True), (rx + 66, S.HUD_Y + 50))
        screen.blit(a.text("ORBITAL", 16, S.TEXT_DIM, True), (rx, S.HUD_Y + 64))
        orb = player.orbital
        self.bar(screen, rx + 66, S.HUD_Y + 64, 110, 10, orb.fraction,
                 S.ORANGE if orb.ready else S.STEEL_DARK)
        if orb.ready:
            screen.blit(a.text("Q READY", 16, S.ORANGE, True), (rx + 184, S.HUD_Y + 62))

    def perk_rects(self):
        w, h, gap = 250, 96, 16
        x0 = S.MAP_W // 2 - (3 * w + 2 * gap) // 2
        y = S.MAP_H - h - 14
        return [pygame.Rect(x0 + i * (w + gap), y, w, h) for i in range(3)]

    def render_perk_menu(self, screen, play, mouse):
        choice = play.progress.current_choice
        self.perk_visible = choice is not None and self.branch_tower is None
        if not self.perk_visible:
            return
        a = self.assets
        rects = self.perk_rects()
        bg = rects[0].union(rects[-1]).inflate(20, 50).move(0, -14)
        shade = pygame.Surface(bg.size, pygame.SRCALPHA)
        shade.fill((*S.HUD_BG, 225))
        screen.blit(shade, bg)
        pending = len(play.progress.choices)
        head = f"LEVEL UP! Vance is level {play.progress.level - pending + 1}: pick a perk"
        if pending > 1:
            head += f"  ({pending} waiting)"
        t = a.text(head, 22, S.CYAN, True)
        screen.blit(t, t.get_rect(midtop=(S.MAP_W // 2, bg.y + 6)))
        perks = play.game.data["perks"]
        for rect, pid in zip(rects, choice):
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, rect, border_radius=8)
            pygame.draw.rect(screen, S.CYAN, rect, 3 if hover else 2, border_radius=8)
            screen.blit(a.text(perks[pid]["name"], 26, S.WHITE, True), (rect.x + 12, rect.y + 14))
            screen.blit(a.text(perks[pid]["desc"], 18, S.TEXT_DIM), (rect.x + 12, rect.y + 48))

    def branch_rects(self):
        w, h, gap = 300, 130, 20
        x0 = S.MAP_W // 2 - w - gap // 2
        y = S.MAP_H - h - 16
        return [pygame.Rect(x0, y, w, h), pygame.Rect(x0 + w + gap, y, w, h)]

    def render_branch_menu(self, screen, play, mouse):
        t = self.branch_tower
        if t is None:
            return
        if t not in play.towers.towers or not t.branch_available:
            self.branch_tower = None
            return
        a = self.assets
        head = a.text(f"{t.name}: choose a tier-4 branch (click outside to cancel)", 22, S.WHITE, True)
        r0 = self.branch_rects()[0]
        bg = pygame.Rect(r0.x - 10, r0.y - 34, 640, r0.h + 44)
        shade = pygame.Surface(bg.size, pygame.SRCALPHA)
        shade.fill((*S.HUD_BG, 230))
        screen.blit(shade, bg)
        screen.blit(head, head.get_rect(midtop=(S.MAP_W // 2, r0.y - 28)))
        for rect, br in zip(self.branch_rects(), t.data["branches"]):
            afford = play.session.energy >= br["cost"]
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, rect, border_radius=8)
            pygame.draw.rect(screen, S.MAGENTA if afford else S.HUD_EDGE, rect, 3 if hover else 2,
                             border_radius=8)
            screen.blit(a.text(br["name"], 28, S.WHITE, True), (rect.x + 14, rect.y + 12))
            screen.blit(a.text(br["desc"], 18, S.TEXT_DIM), (rect.x + 14, rect.y + 46))
            stats = "  ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in br["stats"].items()
                              if k in ("damage", "range", "fire_rate", "chain", "slow", "splash", "dps"))
            screen.blit(a.text(stats, 16, S.CYAN), (rect.x + 14, rect.y + 70))
            screen.blit(a.text(f"{br['cost']} E", 24, S.ENERGY if afford else S.RED, True),
                        (rect.x + 14, rect.bottom - 32))

    def render_wave_preview(self, screen, play):
        """Small panel in the top-right corner during the build phase."""
        waves = play.waves
        nxt = waves.next_wave
        if waves.phase != "build" or not nxt:
            return
        a = self.assets
        enemy_data = play.game.data["enemies"]
        rows = summarize(nxt, enemy_data)
        lines = [(f"NEXT: WAVE {waves.wave_number + 1}", S.WHITE, True)]
        for name, count in rows:
            boss = nxt.get("boss") and name == enemy_data.get(nxt["boss"], {}).get("name")
            lines.append((f"BOSS  {name}" if boss else f"{count}x {name}",
                          S.MAGENTA if boss else S.TEXT_DIM, bool(boss)))
        mutator = nxt.get("mutator")
        if mutator:
            m = play.game.data["endless"]["mutators"][mutator]
            lines.append((m["name"], S.ORANGE, True))
            lines.append((m["desc"], S.ORANGE, False))
        mods = nxt.get("mods") or {}
        if mods.get("elite_chance", 0) > 0:
            lines.append((f"Elite chance {int(mods['elite_chance'] * 100)}%", S.ENERGY, False))
        surfs = [a.text(text, 18, color, bold) for text, color, bold in lines]
        w = max(s.get_width() for s in surfs) + 20
        h = 20 * len(surfs) + 12
        x, y = S.MAP_W - w - 10, 46
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((*S.HUD_BG, 210))
        screen.blit(panel, (x, y))
        pygame.draw.rect(screen, S.HUD_EDGE, (x, y, w, h), 1, border_radius=4)
        for i, s in enumerate(surfs):
            screen.blit(s, (x + 10, y + 6 + i * 20))

    def render_overlays(self, screen, mouse, boss=None):
        a = self.assets
        self.btn_pause.draw(screen, a, mouse, size=22)
        if boss is not None:
            w = 500
            x = S.MAP_W // 2 - w // 2
            color = S.MAGENTA if boss.invulnerable else S.RED
            self.bar(screen, x, 12, w, 14, boss.health.ratio, color)
            label = boss.stats.get("name", "BOSS").upper() + ("  [SHIELDED]" if boss.invulnerable else "")
            t = a.text(label, 20, S.WHITE, True)
            screen.blit(t, t.get_rect(center=(S.MAP_W // 2, 36)))
        for i, (surf, life, _text) in enumerate(reversed(self.toasts)):
            surf.set_alpha(int(255 * min(1.0, life * 2)))
            screen.blit(surf, surf.get_rect(center=(S.MAP_W // 2, (64 if boss else 40) + i * 28)))
        if self.banner:
            title, sub, life, max_life = self.banner
            alpha = int(255 * min(1.0, life / 0.4, (max_life - life) / 0.2 + 0.01))
            big = a.text(title, 72, S.WHITE, True)
            big.set_alpha(alpha)
            screen.blit(big, big.get_rect(center=(S.MAP_W // 2, S.MAP_H // 2 - 30)))
            if sub:
                small = a.text(sub, 30, S.CYAN, True)
                small.set_alpha(alpha)
                screen.blit(small, small.get_rect(center=(S.MAP_W // 2, S.MAP_H // 2 + 20)))

    # ---- F1 debug overlay -------------------------------------------------------------
    def render_debug(self, screen, play, fps):
        a = self.assets
        lvl = play.level
        # Spatial hash cells that contain something
        for cx, cy in play.collision.hash.occupied_cells():
            c = S.HASH_CELL
            pygame.draw.rect(screen, (255, 255, 0), (cx * c, cy * c, c, c), 1)
        # Enemy route
        for route in lvl.routes:
            if len(route) > 1:
                pygame.draw.lines(screen, S.MAGENTA, False, [(int(x), int(y)) for x, y in route], 2)
            for x, y in route:
                pygame.draw.circle(screen, S.MAGENTA, (int(x), int(y)), 4)
        # Tower ranges
        for t in play.towers.towers:
            pygame.draw.circle(screen, S.CYAN, (int(t.x), int(t.y)), int(t.range), 1)
            if t.target is not None and t.target.targetable:
                pygame.draw.line(screen, S.RED, (t.x, t.y), t.target.pos, 1)
        # Enemy hit circles + state
        for e in play.enemies.enemies:
            if hasattr(e, "mask_outline") and e.targetable:
                if e.invulnerable:   # shield bubble is the hitbox while shielded
                    pygame.draw.circle(screen, S.MAGENTA, (int(e.pos.x), int(e.pos.y)), e.SHIELD_RADIUS, 1)
                else:                # pixel-perfect pygame.mask outline
                    outline = e.mask_outline()
                    if len(outline) > 2:
                        pygame.draw.lines(screen, S.RED, True, outline, 1)
            else:
                pygame.draw.circle(screen, S.RED, (int(e.pos.x), int(e.pos.y)), int(e.radius), 1)
            lab = a.text(e.fsm.name, 14, S.WHITE)
            screen.blit(lab, (e.pos.x + e.radius, e.pos.y - 6))
        # Commander collision box
        c = play.player.commander
        pygame.draw.rect(screen, S.GREEN, (c.pos.x - c.half, c.pos.y - c.half, c.half * 2, c.half * 2), 1)
        pygame.draw.circle(screen, S.GREEN, (int(c.pos.x), int(c.pos.y)), int(c.blaster_range), 1)
        lines = [
            f"FPS {fps:.0f}",
            f"enemies {len(play.enemies.enemies)}  projectiles {len(play.projectiles.pool)}",
            f"particles {len(play.effects.particles)}  hash cells {len(play.collision.hash.occupied_cells())}",
            f"commander {c.state}  pos ({c.pos.x:.0f},{c.pos.y:.0f})",
            f"wave phase {play.waves.phase}  queue {play.waves.remaining_in_queue}",
        ]
        pygame.draw.rect(screen, (0, 0, 0), (6, 6, 330, 18 * len(lines) + 8))
        for i, line in enumerate(lines):
            screen.blit(a.text(line, 18, S.ENERGY), (12, 10 + i * 18))

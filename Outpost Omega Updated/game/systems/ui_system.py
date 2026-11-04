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
        self.hotkey_size = 16

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
            hk = assets.text(self.hotkey, self.hotkey_size, S.TEXT_DIM)
            pad = 5 if self.hotkey_size >= 16 else 3
            screen.blit(hk, (self.rect.x + pad, self.rect.y + pad - 1))


TABS = (("assault", "ASSAULT"), ("control", "CONTROL"), ("support", "SUPPORT"))
SLOT_KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=")

# Tower pairs that react with each other (hover tooltips explain them)
COMBOS = {
    "cryo": ["Shatter: Railguns deal 2x to slowed aliens", "Conduct: Tesla chains +2 through slowed aliens"],
    "railgun": ["Shatter: 2x damage to slowed aliens", "Mirror Arrays bounce its shot around corners"],
    "tesla": ["Conduct: +2 chain jumps through slowed aliens"],
    "flamer": ["Detonate: Mortar shells hit burning aliens 1.5x harder", "Sets Tar Pits ablaze"],
    "mortar": ["Detonate: 1.5x damage and splash on burning aliens"],
    "laser": ["Mirror Arrays bend its beam at extra targets"],
    "mirror": ["Bends Railgun and Laser Lance beams in its range"],
    "tar": ["Ignites when a Flamer hits it or a burning alien walks in"],
    "lightning": ["Charges 4x faster while weather is on the map"],
    "fence": ["Needs a second pylon in range to make a beam"],
    "radar": ["Reveals Cloakers and Burrowers"],
    "shield": ["Soaks Spitter acid, Volatile blasts and Titan stomps"],
    "bait": ["Spitters target it before other towers"],
    "decoy": ["Hunters chase it instead of Vance"],
}

# Stats worth showing in a tooltip, in display order: key -> (label, format)
TIP_STATS = (("damage", "DMG", "{:g}"), ("dps", "DPS", "{:g}"), ("range", "RNG", "{:g}"),
             ("fire_rate", "RATE", "{:g}/s"), ("splash", "SPLASH", "{:g}"), ("slow", "SLOW", "{:.0%}"),
             ("chain", "CHAIN", "{:g}"), ("burst", "BURST", "{:g}"), ("shield", "SHIELD", "{:g}"),
             ("max_hp", "HP", "{:g}"), ("income", "INCOME", "{:g}E"), ("per_kill", "PER KILL", "{:g}E"),
             ("haste", "HASTE", "+{:.0%}"), ("shred", "SHRED", "{:g}"), ("heal", "HEAL", "{:g}/s"),
             ("rewind", "REWIND", "{:g}s"), ("hack_time", "HACK", "{:g}s"), ("lure", "LURE", "{:g}s"),
             ("max_charge", "CHARGE", "{:g}"), ("cut", "CUT", "{:g}s/kill"), ("reflect", "REFLECT", "{:.0%}"))


class UISystem:
    TOWER_BTN_X = 236
    TOWER_BAR_W = 412
    TAB_H = 17
    SLOT_PITCH = 37

    def __init__(self, assets, tower_data):
        self.assets = assets
        self.tower_data = tower_data
        self.toasts = []         # [text_surface, life]
        self.banner = None       # [title, subtitle, life]
        self.tab = 0
        self.tabs = []           # [(category, label, [kinds by key])]
        for cat, label in TABS:
            kinds = sorted((k for k, d in tower_data.items() if d.get("category", "assault") == cat),
                           key=lambda k: tower_data[k]["key"])
            if kinds:
                self.tabs.append((cat, label, kinds))
        w = self.TOWER_BAR_W // max(1, len(self.tabs))
        self.tab_rects = [pygame.Rect(self.TOWER_BTN_X + i * w, S.HUD_Y + 4, w - 2, self.TAB_H)
                          for i in range(len(self.tabs))]
        self.tower_buttons = []
        self.build_tab_buttons()
        self.stats_report = None    # post-wave stats panel (dict), shown in the build phase
        self.report_visible = False
        self.report_close = pygame.Rect(0, 0, 0, 0)
        self.picker = None          # chip / fusion chooser: {"kind", "title", "cards", "values", "tower"}
        ab = S.HUD_Y - 32
        self.action_buttons = [Button((652, ab, 76, 26), "Move", "move_tower", hotkey="M"),
                               Button((732, ab, 118, 26), "Stance", "stance", hotkey="G"),
                               Button((854, ab, 92, 26), "Chips", "socket", hotkey="K"),
                               Button((950, ab, 70, 26), "Fuse", "fuse", hotkey="J")]
        for b in self.action_buttons:
            b.hotkey_size = 13
        y = S.HUD_Y + 44
        self.btn_upgrade = Button((652, y, 92, 28), "Upgrade", "upgrade", hotkey="U")
        self.btn_sell = Button((750, y, 84, 28), "Sell", "sell", hotkey="X")
        self.btn_target = Button((840, y, 96, 28), "Target", "cycle_targeting", hotkey="T")
        self.btn_wave = Button((1110, S.HUD_Y + 8, 162, 30), "Start Wave", "start_wave", hotkey="Spc")
        self.btn_pause = Button((1236, 8, 36, 28), "II", "pause")
        self.btn_insure = Button((1110, S.HUD_Y + 44, 78, 28), "Insure", "insure")
        self.btn_research = Button((1192, S.HUD_Y + 44, 80, 28), "Research", "research")
        self.branch_tower = None   # tower whose tier-4 choice panel is open
        self.core_selected = False # Omega Core upgrade panel
        cols = ((652, 92), (750, 84), (840, 96))
        kinds = ("turret", "shield", "regen", "reactor", "nova", "plating")
        self.core_buttons = [Button((cols[i % 3][0], S.HUD_Y + 30 + (i // 3) * 25, cols[i % 3][1], 22),
                                    "", "core_upgrade", k) for i, k in enumerate(kinds)]
        self.perk_visible = False

    # ---- tower tabs --------------------------------------------------------------
    def build_tab_buttons(self):
        _cat, _label, kinds = self.tabs[self.tab]
        self.tower_buttons = []
        pitch = min(self.SLOT_PITCH, self.TOWER_BAR_W // max(1, len(kinds)))
        for i, kind in enumerate(kinds):
            d = self.tower_data[kind]
            rect = (self.TOWER_BTN_X + i * pitch, S.HUD_Y + 8 + self.TAB_H,
                    pitch - 2, S.HUD_H - 12 - self.TAB_H)
            b = Button(rect, "", "select_tower", d["key"], d.get("enabled", True),
                       SLOT_KEYS[i] if i < len(SLOT_KEYS) else None)
            b.hotkey_size = 14
            b.kind = kind
            self.tower_buttons.append(b)

    def set_tab(self, index):
        self.tab = index % len(self.tabs)
        self.build_tab_buttons()

    def show_tab_of(self, kind):
        for i, (_c, _l, kinds) in enumerate(self.tabs):
            if kind in kinds and i != self.tab:
                self.set_tab(i)

    def slot_kind(self, slot):
        kinds = self.tabs[self.tab][2]
        return kinds[slot] if 0 <= slot < len(kinds) else None

    def hovered_tower_button(self, mouse):
        for b in self.tower_buttons:
            if b.rect.collidepoint(mouse):
                return b
        return None

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
        if self.picker is not None:
            for i, rect in enumerate(self.picker_rects()):
                if rect.collidepoint(pos) and self.picker["cards"][i][3]:
                    return Command("pick", value=i)
            return Command("pick", value=None)
        if play.towers.selected and play.towers.relocating is None:
            for b in self.action_buttons:
                if b.hit(pos):
                    return Command(b.command)
        if self.perk_visible:
            for i, rect in enumerate(self.perk_rects()):
                if rect.collidepoint(pos):
                    return Command("choose_perk", value=i)
        if self.report_visible and self.report_close.collidepoint(pos):
            return Command("toggle_report")
        if pos[1] < S.HUD_Y:
            return None
        for i, rect in enumerate(self.tab_rects):
            if rect.collidepoint(pos):
                return Command("set_tab", value=i)
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
        if play.waves.phase == "build" and self.btn_insure.hit(pos):
            return Command("insure")
        if self.btn_research.hit(pos):
            return Command("research")
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
        screen.blit(a.text(f"Bio {getattr(session, 'biomass', 0)}", 16, (150, 230, 120), True), (140, S.HUD_Y + 46))
        screen.blit(a.text(f"Score {session.score}", 16, S.TEXT_DIM), (140, S.HUD_Y + 62))

        # Tower category tabs + build buttons
        for i, ((cat, label, kinds), rect) in enumerate(zip(self.tabs, self.tab_rects)):
            active = i == self.tab
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if active or hover else S.HUD_BG, rect, border_radius=4)
            pygame.draw.rect(screen, S.CYAN if active else S.HUD_EDGE, rect, 1, border_radius=4)
            building = towers.build_kind in kinds
            t = a.text(label, 14, S.WHITE if active else (S.CYAN if building else S.TEXT_DIM), True)
            screen.blit(t, t.get_rect(center=rect.center))
            if active:
                hk = a.text("Tab", 12, S.TEXT_DIM)
                screen.blit(hk, hk.get_rect(midright=(rect.right - 4, rect.centery)))
        for b in self.tower_buttons:
            d = self.tower_data[b.kind]
            sel = towers.build_kind == b.kind
            b.draw(screen, a, mouse, selected=sel)
            icon = pygame.transform.smoothscale(a.get(f"turret_{b.kind}"), (24, 24))
            if not b.enabled:
                icon.set_alpha(70)
            screen.blit(icon, icon.get_rect(center=(b.rect.centerx + 2, b.rect.y + 20)))
            if b.enabled:
                color = S.ENERGY if session.energy >= d["cost"] else S.RED
                cost = a.text(str(d["cost"]), 14, color, True)
            else:
                cost = a.text("--", 14, S.TEXT_DIM, True)
            screen.blit(cost, cost.get_rect(midbottom=(b.rect.centerx, b.rect.bottom - 1)))

        # Info panel
        px = 652
        t = towers.selected
        if t:
            if t.fusion:
                title, col = f"{t.display_name}  FUSED", S.MAGENTA
            elif t.branch is None:
                title, col = f"{t.display_name}  T{t.tier + 1}", S.WHITE
            else:
                title, col = f"{t.display_name}  T4", S.MAGENTA
            surf = a.text(title, 24, S.ENERGY if t.vet_name else col, True)
            if surf.get_width() > 292:
                surf = a.text(title, 18, S.ENERGY if t.vet_name else col, True)
            screen.blit(surf, (px, S.HUD_Y + 8))
            if t.behavior == "income":
                extra = f"+{t.stats['income']}E/wave"
            elif t.behavior == "ion":
                extra = f"Charge {int(t.cooldown.fraction * 100)}%"
            elif t.behavior in ("shield", "tar", "decoy", "fence", "mirror", "magnet"):
                extra = t.data["description"].split(".")[0]
            else:
                extra = f"Target: {t.targeting}"
            if t.shield_max:
                extra += f"   Shield {int(t.health.shield)}"
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
            screen.blit(a.text("OMEGA CORE upgrades", 22, S.CYAN, True), (px, S.HUD_Y + 7))
            for b in self.core_buttons:
                cost = core.cost(b.value)
                b.enabled = cost is not None
                b.label = f"{core.NAMES[b.value]} {cost}" if cost is not None else f"{core.NAMES[b.value]} MAX"
                b.draw(screen, a, mouse, size=16)
                for i in range(core.levels[b.value]):   # level pips
                    pygame.draw.rect(screen, S.CYAN, (b.rect.right - 6, b.rect.y + 3 + i * 6, 3, 4))
        elif towers.build_kind:
            d = self.tower_data[towers.build_kind]
            screen.blit(a.text(f"{d['name']}  ({d['cost']} E)", 24, S.WHITE, True), (px, S.HUD_Y + 8))
            screen.blit(a.text(d["description"], 18, S.TEXT_DIM), (px, S.HUD_Y + 30))
            screen.blit(a.text("Shift+click: build more   R-click: cancel", 18, S.TEXT_DIM),
                        (px, S.HUD_Y + 50))
        else:
            lines = ["WASD move  E repair  Q orbital  R dash",
                     "1-0 - build  Tab tabs  V grenade  Z mech",
                     "R-click: upgrade  I report  F speed  Esc"]
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
            if secs < 100000:   # sandbox waits forever
                screen.blit(a.text(f"Next in {secs}s", 18, S.ENERGY), (rx, S.HUD_Y + 30))
            self.btn_wave.draw(screen, a, mouse, size=22)
            eco = play.economy
            self.btn_insure.label = "Insured" if eco.insured else f"Insure {eco.data['insurance_cost']}"
            self.btn_insure.draw(screen, a, mouse, selected=eco.insured, size=15)
        eco = play.economy
        self.btn_research.label = "Research" if eco.current is None else "Busy"
        self.btn_research.draw(screen, a, mouse, selected=eco.current is not None, size=15)
        if eco.status:
            st = a.text(eco.status, 13, (150, 230, 120))
            screen.blit(st, st.get_rect(topright=(1272, S.HUD_Y + 30 if play.waves.phase != "build" else S.HUD_Y + 74)))
        elif waves.phase == "wave":
            left = waves.remaining_in_queue + play.enemies.alive_count
            screen.blit(a.text(f"Aliens left: {left}", 18, S.ALIEN_GREEN), (rx, S.HUD_Y + 30))
        cmd = player.commander
        prog = play.progress
        screen.blit(a.text(f"{getattr(play, 'hero_name', 'VANCE')[:7]} {prog.level}", 14, S.TEXT_DIM, True),
                    (rx, S.HUD_Y + 51))
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
            spare = getattr(player, "spare_charges", 0)
            screen.blit(a.text("Q READY" + (" x2" if spare else ""), 16, S.ORANGE, True), (rx + 184, S.HUD_Y + 62))

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
        name = getattr(play, "hero_name", "VANCE").title()
        head = f"LEVEL UP! {name} is level {play.progress.level - pending + 1}: pick a perk"
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

    # ---- wave timeline ----------------------------------------------------------------
    @staticmethod
    def wave_brief(wave, enemy_data):
        """(text, color) one-liner for an upcoming wave."""
        rows = summarize(wave, enemy_data)
        boss = wave.get("boss")
        if boss:
            return f"BOSS {enemy_data.get(boss, {}).get('name', boss)}", S.MAGENTA
        total = sum(c for _n, c in rows)
        text = f"{total} aliens" + (f": {rows[0][0]}" if rows else "")
        if len(rows) > 1:
            text += f" +{len(rows) - 1}"
        return text, S.TEXT_DIM

    def upcoming(self, play, count=5):
        """[(wave number, wave dict)] for the next `count` waves (fewer near the end of a sector)."""
        out = []
        waves = play.waves
        for n in range(waves.wave_number + 1, waves.wave_number + 1 + count):
            w = waves.wave_data(n)
            if w is None:
                break
            out.append((n, w))
        return out

    def render_wave_preview(self, screen, play, timeline=True):
        """Top-right: the next wave in detail plus the four after it (build phase), or a
        strip of five chips while a wave is running."""
        waves = play.waves
        a = self.assets
        enemy_data = play.game.data["enemies"]
        mutators = play.game.data["endless"]["mutators"]
        coming = self.upcoming(play, 5 if timeline else 1)
        if not coming:
            return
        if waves.phase != "build":
            if not timeline:
                return
            x = S.MAP_W - 10
            for n, w in reversed(coming):   # chips, right to left
                boss, mut = w.get("boss"), w.get("mutator")
                col = S.MAGENTA if boss else (S.ORANGE if mut else S.STEEL_DARK)
                label = a.text(("B" if boss else "") + str(n), 14, S.WHITE, True)
                r = pygame.Rect(0, 46, max(28, label.get_width() + 10), 18)
                r.right = x
                pygame.draw.rect(screen, (*S.HUD_BG,), r, border_radius=4)
                pygame.draw.rect(screen, col, r, 2, border_radius=4)
                screen.blit(label, label.get_rect(center=r.center))
                x = r.left - 4
            nxt = a.text("NEXT", 12, S.TEXT_DIM, True)
            screen.blit(nxt, nxt.get_rect(midright=(x - 2, 55)))
            return
        n0, nxt = coming[0]
        rows = summarize(nxt, enemy_data)
        lines = [(f"NEXT: WAVE {n0}", S.WHITE, True)]
        for name, count in rows:
            boss = nxt.get("boss") and name == enemy_data.get(nxt["boss"], {}).get("name")
            lines.append((f"BOSS  {name}" if boss else f"{count}x {name}",
                          S.MAGENTA if boss else S.TEXT_DIM, bool(boss)))
        mutator = nxt.get("mutator")
        if mutator:
            m = mutators[mutator]
            lines.append((m["name"], S.ORANGE, True))
            lines.append((m["desc"], S.ORANGE, False))
        mods = nxt.get("mods") or {}
        if mods.get("elite_chance", 0) > 0:
            lines.append((f"Elite chance {int(mods['elite_chance'] * 100)}%", S.ENERGY, False))
        if len(coming) > 1:
            lines.append(("COMING UP", S.CYAN, True))
            for n, w in coming[1:]:
                text, col = self.wave_brief(w, enemy_data)
                if w.get("mutator") and not w.get("boss"):
                    text += f"  [{mutators[w['mutator']]['name']}]"
                    col = S.ORANGE
                lines.append((f"W{n}  {text}", col, bool(w.get("boss"))))
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

    # ---- selected-tower action bar, info box and pickers ---------------------------------
    def render_tower_actions(self, screen, play, mouse):
        towers = play.towers
        t = towers.selected
        if t is None or t not in towers.towers or self.picker is not None or self.branch_tower is not None:
            return
        a = self.assets
        sysd = towers.systems
        lines = []
        for text in t.synergies:
            lines.append(("+ " + text, S.GREEN))
        if t.power > 0:
            lines.append((f"Powered: +{int(t.power * 100)}% fire rate", S.ENERGY))
        if t.vet_trait:
            tr = sysd["veteran_traits"][t.vet_trait]
            lines.append((f"Veteran trait: {tr['name']} ({tr['desc']})", S.ENERGY))
        for c in t.chips:
            info = sysd["chips"][c]
            lines.append((f"{info['name']}: {info['desc']}", tuple(info["color"])))
        if t.stance:
            st = sysd["stances"][t.stance]
            lines.append((f"Stance: {st['name']} ({st['desc']})", S.CYAN))
        if getattr(t, "corrupted", False):
            lines.append(("CORRUPTED: repair it to full (E)", (200, 110, 240)))
        if lines:
            surfs = [a.text(text, 15, col) for text, col in lines]
            w = max(s.get_width() for s in surfs) + 16
            h = 18 * len(surfs) + 8
            x, y = 652, S.HUD_Y - 36 - h
            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            panel.fill((*S.HUD_BG, 225))
            screen.blit(panel, (x, y))
            for i, surf in enumerate(surfs):
                screen.blit(surf, (x + 8, y + 4 + i * 18))
        move, stance, chips, fuse = self.action_buttons
        move.enabled = play.waves.phase == "build"
        move.label = f"Move {towers.relocate_fee(t)}"
        stance.enabled = towers.can_stance(t)
        stance.label = "Stance: " + {None: "Normal", "focus": "Focus", "suppress": "Suppr."}[t.stance]
        have = sum(play.session.chips.values())
        chips.enabled = have > 0 and len(t.chips) < t.chip_slots
        chips.label = f"Chips {len(t.chips)}/{t.chip_slots}"
        fuse.enabled = bool(towers.fusion_options(t))
        buttons = self.action_buttons if towers.allow_fusion else self.action_buttons[:3]
        for b in buttons:
            b.draw(screen, a, mouse, size=15)
        if have:
            inv = a.text(f"{have} chip{'s' if have != 1 else ''} in stock", 14, S.TEXT_DIM)
            screen.blit(inv, (buttons[-1].rect.right + 8, buttons[-1].rect.y + 6))

    def open_chip_picker(self, tower, inventory, chips):
        if len(tower.chips) >= tower.chip_slots:
            self.toast(f"No free socket ({tower.chip_slots} max at this tier)", S.TEXT_DIM)
            return
        values = [c for c in chips if inventory.get(c, 0) > 0]
        if not values:
            self.toast("No chips yet: elites and bosses drop them", S.TEXT_DIM)
            return
        cards = [(chips[c]["name"], chips[c]["desc"], f"x{inventory[c]}", True, tuple(chips[c]["color"]))
                 for c in values]
        self.picker = {"kind": "chip", "title": f"Socket a chip into {tower.name}", "cards": cards,
                       "values": values, "tower": tower}

    def open_research_picker(self, eco, biomass):
        opts = eco.options()
        if not opts:
            self.toast("All research done", S.TEXT_DIM)
            return
        cards = []
        for rid in opts:
            r = eco.data["research"][rid]
            ok = biomass >= r["cost"]
            cards.append((r["name"], f"{r['desc']}. Takes {r['waves']} waves.", f"{r['cost']} Biomass", ok,
                          (150, 230, 120) if ok else S.HUD_EDGE))
        self.picker = {"kind": "research", "title": f"Research ({biomass} Biomass)", "cards": cards,
                       "values": opts, "tower": None}

    def open_fusion_picker(self, tower, options, sysd):
        cost = sysd.get("fusion_cost", 150)
        cards = []
        for fid, partner in options:
            f = sysd["fusions"][fid]
            cards.append((f["name"], f["desc"], f"{cost} E  (uses {partner.name})", True, S.MAGENTA))
        self.picker = {"kind": "fusion", "title": f"Fuse {tower.name} with a neighbor", "cards": cards,
                       "values": options, "tower": tower}

    def picker_rects(self):
        n = len(self.picker["cards"]) if self.picker else 0
        w, h, gap = 210, 104, 12
        per_row = 5
        rows = -(-n // per_row) if n else 1
        out = []
        for i in range(n):
            r, c = divmod(i, per_row)
            in_row = min(per_row, n - r * per_row)
            x0 = S.MAP_W // 2 - (in_row * w + (in_row - 1) * gap) // 2
            y = S.MAP_H - 16 - (rows - r) * (h + gap) + gap
            out.append(pygame.Rect(x0 + c * (w + gap), y, w, h))
        return out

    def render_picker(self, screen, play, mouse):
        p = self.picker
        if p is None:
            return
        a = self.assets
        rects = self.picker_rects()
        bg = rects[0].union(rects[-1]).inflate(20, 44).move(0, -12)
        shade = pygame.Surface(bg.size, pygame.SRCALPHA)
        shade.fill((*S.HUD_BG, 232))
        screen.blit(shade, bg)
        head = a.text(p["title"] + "  (R-click to cancel)", 20, S.WHITE, True)
        screen.blit(head, head.get_rect(midtop=(S.MAP_W // 2, bg.y + 6)))
        for rect, (title, desc, foot, enabled, col) in zip(rects, p["cards"]):
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, rect, border_radius=8)
            pygame.draw.rect(screen, col, rect, 3 if hover else 2, border_radius=8)
            screen.blit(a.text(title, 22, S.WHITE, True), (rect.x + 10, rect.y + 8))
            for i, line in enumerate(self.wrap(desc, 15, rect.w - 20)[:3]):
                screen.blit(a.text(line, 15, S.TEXT_DIM), (rect.x + 10, rect.y + 36 + i * 17))
            screen.blit(a.text(foot, 15, col, True), (rect.x + 10, rect.bottom - 22))

    # ---- post-wave report ------------------------------------------------------------
    IDLE_EXEMPT = {"income", "support", "barricade", "repair", "shield", "decoy", "mirror", "biolab",
                   "overclock", "uplink", "bait", "aura", "gravity", "chrono"}

    def build_report(self, number, towers):
        rows = [t for t in towers if t.wave_damage > 0 or t.wave_kills > 0]
        rows.sort(key=lambda t: -t.wave_damage)
        idle = {}
        for t in towers:
            if t.wave_damage <= 0 and t.behavior not in self.IDLE_EXEMPT:
                idle[t.name] = idle.get(t.name, 0) + 1
        return {"wave": number,
                "rows": [(t.kind, t.name if t.branch is None else t.branch_name, t.tier, t.branch,
                          t.wave_damage, t.wave_kills) for t in rows],
                "idle": idle,
                "total": sum(t.wave_damage for t in rows),
                "kills": sum(t.wave_kills for t in rows)}

    def render_report(self, screen, play, mouse):
        rep = self.stats_report
        if not self.report_visible or rep is None or play.waves.phase != "build":
            self.report_close = pygame.Rect(0, 0, 0, 0)
            return
        a = self.assets
        rows = rep["rows"][:8]
        w = 340
        h = 62 + 24 * max(1, len(rows)) + (22 if rep["idle"] else 0)
        x, y = 10, 46
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((*S.HUD_BG, 225))
        screen.blit(panel, (x, y))
        pygame.draw.rect(screen, S.HUD_EDGE, (x, y, w, h), 1, border_radius=4)
        screen.blit(a.text(f"WAVE {rep['wave']} REPORT", 20, S.WHITE, True), (x + 10, y + 6))
        sub = f"{int(rep['total'])} damage   {rep['kills']} kills"
        screen.blit(a.text(sub, 16, S.TEXT_DIM), (x + 10, y + 28))
        self.report_close = pygame.Rect(x + w - 26, y + 6, 18, 18)
        hover = self.report_close.collidepoint(mouse)
        pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, self.report_close, border_radius=3)
        xx = a.text("x", 16, S.WHITE, True)
        screen.blit(xx, xx.get_rect(center=self.report_close.center))
        top = max((r[4] for r in rows), default=1) or 1
        yy = y + 50
        if not rows:
            screen.blit(a.text("No tower dealt damage this wave", 16, S.TEXT_DIM), (x + 10, yy))
        for kind, name, tier, branch, dmg, kills in rows:
            icon = pygame.transform.smoothscale(a.get(f"turret_{kind}"), (20, 20))
            screen.blit(icon, (x + 8, yy))
            label = f"{name} T{tier + 1}" if branch is None else name
            screen.blit(a.text(label, 15, S.WHITE if branch is None else S.MAGENTA), (x + 32, yy + 2))
            self.bar(screen, x + 168, yy + 6, 64, 8, dmg / top, S.CYAN)
            screen.blit(a.text(f"{int(dmg)}", 14, S.TEXT_DIM), (x + 238, yy + 2))
            if kills:
                screen.blit(a.text(f"{kills} kill{'s' if kills != 1 else ''}", 14, S.ENERGY), (x + 280, yy + 2))
            yy += 24
        if rep["idle"]:
            names = ", ".join(f"{c}x {n}" if c > 1 else n for n, c in rep["idle"].items())
            surf = a.text(f"Idle: {names}", 15, S.ORANGE)
            if surf.get_width() > w - 20:
                surf = a.text(f"Idle: {sum(rep['idle'].values())} towers did no damage", 15, S.ORANGE)
            screen.blit(surf, (x + 10, yy + 2))

    # ---- tooltips ----------------------------------------------------------------------
    def wrap(self, text, size, width):
        words, lines, line = text.split(), [], ""
        for w in words:
            test = (line + " " + w).strip()
            if self.assets.text(test, size, S.WHITE).get_width() > width and line:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        return lines

    def render_tooltip(self, screen, play, mouse):
        """Hovering a build button: stats, upgrade costs, branches and combos."""
        if mouse[1] < S.HUD_Y or self.branch_tower is not None:
            return
        b = self.hovered_tower_button(mouse)
        if b is None:
            return
        a = self.assets
        d = self.tower_data[b.kind]
        w = 320
        body = []   # (text, size, color, bold)
        for line in self.wrap(d["description"], 16, w - 20):
            body.append((line, 16, S.TEXT_DIM, False))
        t0 = d["tiers"][0]
        stats = [f"{label} {fmt.format(t0[k])}" for k, label, fmt in TIP_STATS
                 if k in t0 and t0[k] not in (0, None) and not isinstance(t0[k], bool)]
        if stats:
            for line in self.wrap("   ".join(stats[:6]), 15, w - 20):
                body.append((line, 15, S.CYAN, True))
        ups = [t["upgrade_cost"] for t in d["tiers"][1:]]
        if ups:
            body.append((f"Upgrades: {' / '.join(f'{u}E' for u in ups)}", 15, S.ENERGY, False))
        if d.get("branches"):
            names = " or ".join(br["name"] for br in d["branches"])
            for line in self.wrap(f"Tier 4 (Siege Run): {names}", 15, w - 20):
                body.append((line, 15, S.MAGENTA, False))
        for partner, text in play.towers.synergy_partners(b.kind):
            pname = self.tower_data.get(partner, {}).get("name", partner)
            for line in self.wrap(f"Next to a {pname}: {text.split(': ', 1)[-1]}", 15, w - 20):
                body.append((line, 15, S.ENERGY, False))
        for combo in COMBOS.get(b.kind, []):
            for line in self.wrap("+ " + combo, 15, w - 20):
                body.append((line, 15, S.GREEN, False))
        if not b.enabled:
            body.append(("LOCKED: pick up its tower card first", 15, S.RED, True))
        title = a.text(d["name"], 22, S.WHITE, True)
        cost = a.text(f"{d['cost']} E", 20, S.ENERGY, True)
        h = 36 + sum(18 for _ in body) + 8
        x = max(4, min(S.SCREEN_W - w - 4, b.rect.centerx - w // 2))
        y = S.HUD_Y - h - 6
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((*S.HUD_BG, 240))
        screen.blit(panel, (x, y))
        pygame.draw.rect(screen, S.CYAN, (x, y, w, h), 1, border_radius=5)
        screen.blit(title, (x + 10, y + 6))
        screen.blit(cost, cost.get_rect(topright=(x + w - 10, y + 8)))
        yy = y + 34
        for text, size, color, bold in body:
            screen.blit(a.text(text, size, color, bold), (x + 10, yy))
            yy += 18

    def render_overlays(self, screen, mouse, boss=None):
        a = self.assets
        self.btn_pause.draw(screen, a, mouse, size=22)
        if boss is not None:
            w = 500
            x = S.MAP_W // 2 - w // 2
            color = S.MAGENTA if boss.invulnerable else S.RED
            self.bar(screen, x, 12, w, 14, getattr(boss, "bar_ratio", boss.health.ratio), color)
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

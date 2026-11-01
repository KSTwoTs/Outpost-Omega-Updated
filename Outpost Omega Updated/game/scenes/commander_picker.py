"""A row of Commander class buttons, shared by Level Select and the Tech Lab.

Heroes with a "modes" list in commanders.json only appear in those modes; the
Level Select passes the current mode so campaign hides Endless/Siege-only heroes."""
from .. import settings as S
from ..systems.run import hero_allowed
from ..systems.ui_system import Button


class CommanderPicker:
    def __init__(self, game, y, mode=None):
        self.game = game
        self.y = y
        self.mode = mode          # callable returning "campaign" / "endless" / "run"
        self.ids = []
        self.buttons = []
        self.refresh()

    def allowed(self):
        mode = self.mode() if self.mode else "run"
        return [cid for cid, h in self.game.data["commanders"].items() if hero_allowed(h, mode)]

    def refresh(self):
        ids = self.allowed()
        if self.game.commander_class not in ids:
            self.game.commander_class = ids[0]
        if ids == self.ids:
            return
        self.ids = ids
        n = len(ids)
        if n <= 4:   # roomy: centered, with a "Commander" label on the left
            w = 150
            x0 = S.SCREEN_W // 2 - (n * w + 8 * (n - 1)) // 2
        else:        # crowded: fit between the BACK button and the right edge
            left, right = 196, S.SCREEN_W - 20
            w = min(150, (right - left - 8 * (n - 1)) // n)
            x0 = (left + right) // 2 - (n * w + 8 * (n - 1)) // 2
        cmds = self.game.data["commanders"]
        self.buttons = [Button((x0 + i * (w + 8), self.y, w, 44), cmds[cid]["name"].upper(), "commander", cid)
                        for i, cid in enumerate(ids)]

    def handle_click(self, pos):
        self.refresh()
        for b in self.buttons:
            if b.hit(pos):
                self.game.commander_class = b.value
                return True
        return False

    def draw(self, screen, assets, mouse):
        self.refresh()
        if self.buttons[0].rect.x > 140:
            label = assets.text("Commander", 20, S.TEXT_DIM)
            screen.blit(label, label.get_rect(midright=(self.buttons[0].rect.x - 12, self.y + 22)))
        cmds = self.game.data["commanders"]
        for b in self.buttons:
            hero = cmds[b.value].get("palette")
            label, b.label = b.label, ""
            b.draw(screen, assets, mouse, selected=(b.value == self.game.commander_class))
            b.label = label
            text = assets.text(label, 22 if b.rect.w >= 140 else 18, S.WHITE, True)
            cx = b.rect.centerx + (12 if hero else 0)
            screen.blit(text, text.get_rect(center=(cx, b.rect.centery)))
            if hero:   # tiny portrait in the hero's colors
                assets.blit_centered(screen, f"commander_0~{b.value}",
                                     (cx - text.get_width() // 2 - 15, b.rect.centery))
        hero = self.game.data["commanders"][self.game.commander_class]
        info = hero["desc"]
        if hero.get("modes"):
            info += "   (Endless & Siege Run only)"
        t = assets.text(info, 18, S.CYAN)
        screen.blit(t, t.get_rect(midtop=(S.SCREEN_W // 2, self.y + 50)))

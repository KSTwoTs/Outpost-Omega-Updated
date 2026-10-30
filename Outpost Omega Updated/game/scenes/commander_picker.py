"""A row of Commander class buttons, shared by Level Select and the Tech Lab."""
from .. import settings as S
from ..systems.ui_system import Button


class CommanderPicker:
    def __init__(self, game, y):
        self.game = game
        self.y = y
        ids = list(game.data["commanders"])
        cx = S.SCREEN_W // 2
        self.buttons = [Button((cx - 235 + i * 160, y, 150, 44), game.data["commanders"][cid]["name"].upper(),
                               "commander", cid) for i, cid in enumerate(ids)]

    def handle_click(self, pos):
        for b in self.buttons:
            if b.hit(pos):
                self.game.commander_class = b.value
                return True
        return False

    def draw(self, screen, assets, mouse):
        label = assets.text("Commander", 20, S.TEXT_DIM)
        screen.blit(label, label.get_rect(midright=(self.buttons[0].rect.x - 14, self.y + 22)))
        for b in self.buttons:
            b.draw(screen, assets, mouse, selected=(b.value == self.game.commander_class), size=22)
        info = self.game.data["commanders"][self.game.commander_class]["desc"]
        t = assets.text(info, 18, S.CYAN)
        screen.blit(t, t.get_rect(midtop=(S.SCREEN_W // 2, self.y + 50)))

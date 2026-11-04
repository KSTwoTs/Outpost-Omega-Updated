"""Controls overlay (Settings > Controls): click an action, then press its new key.

Bindings are saved in settings["keys"] as {action: pygame key code}; InputSystem.apply_bindings
rebuilds the key map. A controller works out of the box (see input_system.PAD_BUTTONS).
"""
import pygame

from .. import settings as S
from ..systems import input_system as inp
from ..systems.ui_system import Button
from .scene_manager import Scene

ROWS = [("walk_up", "Move up"), ("walk_down", "Move down"), ("walk_left", "Move left"),
        ("walk_right", "Move right"), ("repair", "Repair (hold)")] + inp.REBINDABLE


class ControlsScene(Scene):
    is_overlay = True
    COLS = 2
    ROW_H = 34

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.waiting = None
        cx = S.SCREEN_W // 2
        self.rows = []
        per_col = (len(ROWS) + 1) // 2
        for i, (action, label) in enumerate(ROWS):
            col, row = divmod(i, per_col)
            x = cx - 520 + col * 540
            y = 130 + row * self.ROW_H
            self.rows.append((action, label, pygame.Rect(x + 300, y, 160, 28), (x, y)))
        self.back = Button((cx - 290, 630, 280, 48), "BACK", "back", hotkey="Esc")
        self.reset = Button((cx + 10, 630, 280, 48), "RESET DEFAULTS", "reset")

    def handle_event(self, event):
        if self.waiting is not None and event.type == pygame.KEYDOWN:
            if event.key != pygame.K_ESCAPE:
                keys = self.game.settings.setdefault("keys", {})
                keys[self.waiting] = event.key
                inp.apply_bindings(keys)
                self.game.write_save()
                self.audio.play("click")
            self.waiting = None
            return
        super().handle_event(event)

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.pop()
        elif cmd.name == "click":
            if self.back.hit(cmd.pos):
                self.game.scenes.pop()
            elif self.reset.hit(cmd.pos):
                self.game.settings["keys"] = {}
                inp.apply_bindings({})
                self.game.write_save()
            for action, _label, rect, _pos in self.rows:
                if rect.collidepoint(cmd.pos):
                    self.waiting = action
                    self.audio.play("click")

    def on_render(self, screen):
        shade = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        shade.fill((5, 6, 16, 245))
        screen.blit(shade, (0, 0))
        a = self.assets
        title = a.text("CONTROLS", 56, S.CYAN, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 70)))
        hint = a.text("Click an action, then press a key. Controller: A wave, B grenade, X repair, "
                      "Y mech, RB dash, LB tab, RT orbital", 16, S.TEXT_DIM)
        screen.blit(hint, hint.get_rect(center=(S.SCREEN_W // 2, 108)))
        mouse = self.input.mouse_pos()
        for action, label, rect, (x, y) in self.rows:
            screen.blit(a.text(label, 20, S.WHITE, True), (x, y + 4))
            waiting = self.waiting == action
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if hover or waiting else S.PANEL, rect, border_radius=5)
            pygame.draw.rect(screen, S.ENERGY if waiting else S.HUD_EDGE, rect, 2, border_radius=5)
            key = inp.key_for(action)
            text = "press a key..." if waiting else (pygame.key.name(key).upper() if key else "-")
            t = a.text(text, 18, S.ENERGY if waiting else S.CYAN, True)
            screen.blit(t, t.get_rect(center=rect.center))
        self.back.draw(screen, a, mouse, size=24)
        self.reset.draw(screen, a, mouse, size=22)

"""Seeded Siege Run: type a run seed (shown on the run map) to replay or share a run."""
import pygame

from .. import settings as S
from ..systems.ui_system import Button
from .scene_manager import Scene


class SeedScene(Scene):
    is_overlay = True

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.text = ""
        cx = S.SCREEN_W // 2
        self.start = Button((cx - 290, 430, 280, 52), "START RUN", "start", hotkey="Enter")
        self.back = Button((cx + 10, 430, 280, 52), "BACK", "back", hotkey="Esc")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.unicode and event.unicode.isdigit() and len(self.text) < 10:
                self.text += event.unicode
                return
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.go()
                return
        super().handle_event(event)

    def go(self):
        if not self.text:
            self.audio.play("error")
            return
        self.game.start_run(seed=int(self.text))
        self.game.scenes.change("run_map")

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.pop()
        elif cmd.name == "click":
            if self.start.hit(cmd.pos):
                self.go()
            elif self.back.hit(cmd.pos):
                self.game.scenes.pop()

    def on_render(self, screen):
        shade = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        shade.fill((5, 6, 16, 248))
        screen.blit(shade, (0, 0))
        a = self.assets
        cx = S.SCREEN_W // 2
        t = a.text("SEEDED SIEGE RUN", 52, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(cx, 200)))
        sub = a.text("Type a run seed (from a friend, or from the run map). Same seed = same maps, "
                     "faction and events.", 20, S.TEXT_DIM)
        screen.blit(sub, sub.get_rect(center=(cx, 250)))
        box = pygame.Rect(cx - 200, 300, 400, 64)
        pygame.draw.rect(screen, S.PANEL, box, border_radius=8)
        pygame.draw.rect(screen, S.CYAN, box, 2, border_radius=8)
        caret = "_" if (pygame.time.get_ticks() // 400) % 2 else " "
        v = a.text(self.text + caret, 40, S.ENERGY, True)
        screen.blit(v, v.get_rect(center=box.center))
        if self.game.run is not None and not self.game.run.over:
            w = a.text("This replaces your current run.", 18, S.RED)
            screen.blit(w, w.get_rect(center=(cx, 390)))
        mouse = self.input.mouse_pos()
        self.start.draw(screen, a, mouse, size=26)
        self.back.draw(screen, a, mouse, size=26)

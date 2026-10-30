"""Pause overlay: pushed on top of PlayScene, which stays frozen underneath."""
import pygame

from .. import settings as S
from ..systems.ui_system import Button
from .scene_manager import Scene


class PauseScene(Scene):
    is_overlay = True

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        cx = S.SCREEN_W // 2
        self.buttons = [
            Button((cx - 140, 300, 280, 52), "RESUME", "resume", hotkey="Esc"),
            Button((cx - 140, 366, 280, 52), "RESTART SECTOR", "restart"),
            Button((cx - 140, 432, 280, 52), "QUIT TO MENU", "menu"),
        ]

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.activate("resume")
        elif cmd.name == "click":
            for b in self.buttons:
                if b.hit(cmd.pos):
                    self.audio.play("click")
                    self.activate(b.command)
                    return

    def activate(self, command):
        scenes = self.game.scenes
        play = scenes.stack[-2] if len(scenes.stack) > 1 else None
        if command == "resume":
            scenes.pop()
        elif command == "restart" and play is not None:
            scenes.change("play", level_id=play.level_id, difficulty=play.difficulty)
        elif command == "menu":
            self.audio.stop_music()
            scenes.change("menu")

    def on_render(self, screen):
        shade = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        shade.fill((5, 6, 16, 170))
        screen.blit(shade, (0, 0))
        title = self.assets.text("PAUSED", 80, S.CYAN, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 220)))
        mouse = self.input.mouse_pos()
        for b in self.buttons:
            b.draw(screen, self.assets, mouse, size=30)

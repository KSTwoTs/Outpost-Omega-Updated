"""Main menu, plus the Starfield background shared by the menu screens."""
import math
import random

import pygame

from .. import settings as S
from ..systems.ui_system import Button
from .scene_manager import Scene


class Starfield:
    def __init__(self, count=140, seed=2189):
        rng = random.Random(seed)
        self.stars = [(rng.uniform(0, S.SCREEN_W), rng.uniform(0, S.SCREEN_H),
                       rng.uniform(8, 40), rng.choice((1, 1, 2))) for _ in range(count)]
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        screen.fill(S.SPACE)
        for x, y, speed, size in self.stars:
            sx = (x - self.t * speed) % S.SCREEN_W
            b = 150 + int(80 * math.sin(self.t * 2 + x))
            screen.fill((b, b, min(255, b + 30)), (int(sx), int(y), size, size))
        # Earth's shield glow at the bottom
        glow = pygame.Surface((S.SCREEN_W, 200), pygame.SRCALPHA)
        for i in range(10):
            pygame.draw.ellipse(glow, (0, 229, 255, 6 + i * 2),
                                (-200 + i * 20, 120 - i * 6, S.SCREEN_W + 400 - i * 40, 300))
        screen.blit(glow, (0, S.SCREEN_H - 200))


class MenuScene(Scene):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.stars = Starfield()
        cx = S.SCREEN_W // 2
        self.buttons = [
            Button((cx - 130, 380, 260, 54), "PLAY", "play"),
            Button((cx - 130, 450, 260, 54), "QUIT", "quit"),
        ]
        self.t = 0.0

    def handle_command(self, cmd):
        if cmd.name == "click":
            for b in self.buttons:
                if b.hit(cmd.pos):
                    self.audio.play("click")
                    self.activate(b.command)
        elif cmd.name in ("confirm", "start_wave"):
            self.activate("play")
        elif cmd.name == "pause":
            self.activate("quit")

    def activate(self, command):
        if command == "play":
            self.game.scenes.change("level_select")
        elif command == "quit":
            self.game.running = False

    def on_update(self, dt):
        self.t += dt
        self.stars.update(dt)

    def on_render(self, screen):
        a = self.assets
        self.stars.draw(screen)
        bob = math.sin(self.t * 1.5) * 4
        title = a.text("OUTPOST OMEGA", 110, S.CYAN, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 170 + bob)))
        sub = a.text("ALIEN SIEGE", 54, S.ORANGE, True)
        screen.blit(sub, sub.get_rect(center=(S.SCREEN_W // 2, 245 + bob)))
        tag = a.text("Year 2189. Hold the Omega Core until Earth's shield is charged.", 26, S.TEXT_DIM)
        screen.blit(tag, tag.get_rect(center=(S.SCREEN_W // 2, 305)))
        # A row of the cast along the bottom
        names = ("commander_0", "skitter_0", "brute_0", "glider_0")
        for i, name in enumerate(names):
            img = a.image(name)
            img = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
            x = S.SCREEN_W // 2 - 300 + i * 200
            y = 610 + math.sin(self.t * 3 + i) * 5
            screen.blit(img, img.get_rect(center=(x, int(y))))
        mouse = self.input.mouse_pos()
        for b in self.buttons:
            b.draw(screen, a, mouse, size=34)
        hint = a.text("CPSC 4160  -  Trenton McDonald", 20, S.TEXT_DIM)
        screen.blit(hint, (12, S.SCREEN_H - 26))

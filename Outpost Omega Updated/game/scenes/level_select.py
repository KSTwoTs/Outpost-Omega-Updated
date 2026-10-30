"""Level Select: pick a sector and a difficulty. Shows best stars from save.json."""
import math

import pygame

from .. import settings as S
from ..core import EventBus
from ..systems.level_system import LevelSystem, level_exists
from ..systems.ui_system import Button
from .menu import Starfield
from .scene_manager import Scene

SECTORS = [
    ("sector1", "Sector 1", "Desert Outpost", S.SAND),
    ("sector2", "Sector 2", "Frozen Relay Station", S.ICE),
    ("sector3", "Sector 3", "Hive Crash Site", S.MAGENTA),
]


def draw_star(screen, center, r, filled):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((center[0] + math.cos(ang) * rad, center[1] + math.sin(ang) * rad))
    if filled:
        pygame.draw.polygon(screen, S.ENERGY, pts)
    pygame.draw.polygon(screen, S.ENERGY if filled else S.TEXT_DIM, pts, 2)


class LevelSelectScene(Scene):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.stars = Starfield()
        self.cards = []
        save = game.save
        for i, (sid, title, sub, color) in enumerate(SECTORS):
            rect = pygame.Rect(130 + i * 360, 170, 300, 300)
            # All sectors unlocked for the Milestone 2 demo. To restore
            # progression: unlocked = level_exists(sid) and i < save.get("unlocked", 1)
            unlocked = level_exists(sid)
            self.cards.append((rect, sid, title, sub, color, unlocked))
        self.thumbs = {sid: self.make_thumbnail(sid) for _, sid, *_ in self.cards if level_exists(sid)}
        self.diff_buttons = [
            Button((S.SCREEN_W // 2 - 240 + i * 165, 520, 150, 46), name, "difficulty", name)
            for i, name in enumerate(S.DIFFICULTIES)
        ]
        self.back = Button((40, S.SCREEN_H - 80, 140, 46), "BACK", "back")

    @staticmethod
    def make_thumbnail(level_id, size=(260, 130)):
        """Shrink the level's real tile map down to a mini-map for the card."""
        try:
            level = LevelSystem(EventBus(), level_id)
        except (OSError, ValueError, KeyError):
            return None
        thumb = pygame.transform.smoothscale(level.surface, size)
        sx, sy = size[0] / S.MAP_W, size[1] / S.MAP_H
        cx, cy = level.core_pos
        pygame.draw.circle(thumb, S.CYAN, (int(cx * sx), int(cy * sy)), 5)
        for route in level.routes:
            x, y = route[0]
            px = min(size[0] - 4, max(4, int(x * sx)))
            py = min(size[1] - 4, max(4, int(y * sy)))
            pygame.draw.circle(thumb, S.MAGENTA, (px, py), 4)
        return thumb

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        elif cmd.name == "click":
            for rect, sid, *_rest, unlocked in self.cards:
                if rect.collidepoint(cmd.pos):
                    if unlocked:
                        self.audio.play("click")
                        self.game.scenes.change("play", level_id=sid, difficulty=self.game.difficulty)
                    else:
                        self.audio.play("error")
            for b in self.diff_buttons:
                if b.hit(cmd.pos):
                    self.game.difficulty = b.value
                    self.audio.play("click")
            if self.back.hit(cmd.pos):
                self.game.scenes.change("menu")

    def on_update(self, dt):
        self.stars.update(dt)

    def on_render(self, screen):
        a = self.assets
        self.stars.draw(screen)
        title = a.text("SELECT SECTOR", 64, S.CYAN, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 95)))
        mouse = self.input.mouse_pos()
        for rect, sid, name, sub, color, unlocked in self.cards:
            hover = unlocked and rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, rect, border_radius=12)
            pygame.draw.rect(screen, color if unlocked else S.HUD_EDGE, rect, 3, border_radius=12)
            preview = pygame.Rect(rect.x + 20, rect.y + 20, rect.w - 40, 140)
            thumb = self.thumbs.get(sid)
            if thumb is not None:
                if not unlocked:
                    thumb = thumb.copy()
                    thumb.set_alpha(80)
                pygame.draw.rect(screen, S.SPACE, preview, border_radius=8)
                screen.blit(thumb, thumb.get_rect(center=preview.center))
                pygame.draw.rect(screen, color if unlocked else S.HUD_EDGE, preview, 2, border_radius=8)
            else:
                pygame.draw.rect(screen, S.STEEL_DARK, preview, border_radius=8)
            screen.blit(a.text(name, 40, S.WHITE, True), (rect.x + 20, rect.y + 175))
            screen.blit(a.text(sub, 26, S.TEXT_DIM), (rect.x + 20, rect.y + 210))
            if unlocked:
                best = self.game.save.get("sectors", {}).get(sid, {})
                for s in range(3):
                    draw_star(screen, (rect.x + 40 + s * 40, rect.y + 260), 15, s < best.get("stars", 0))
                if best.get("score"):
                    screen.blit(a.text(f"Best {best['score']}", 22, S.TEXT_DIM), (rect.x + 170, rect.y + 252))
            else:
                msg = "LOCKED" if level_exists(sid) else "COMING SOON"
                lock = a.text(msg, 34, S.TEXT_DIM, True)
                screen.blit(lock, lock.get_rect(center=preview.center))
        label = a.text("Difficulty", 26, S.TEXT_DIM)
        screen.blit(label, label.get_rect(center=(S.SCREEN_W // 2, 500)))
        for b in self.diff_buttons:
            b.draw(screen, a, mouse, selected=(b.value == self.game.difficulty), size=28)
        self.back.draw(screen, a, mouse, size=28)

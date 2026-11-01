"""Level Select: pick a sector and a difficulty. Shows best stars from save.json."""
import math
import random

import pygame

from .. import settings as S
from ..core import EventBus
from ..systems.level_system import LevelSystem, level_exists
from ..systems.ui_system import Button
from .commander_picker import CommanderPicker
from .menu import Starfield
from .scene_manager import Scene

SECTORS = [
    ("sector1", "Sector 1", "Desert Outpost", S.SAND),
    ("sector2", "Sector 2", "Frozen Relay Station", S.ICE),
    ("sector3", "Sector 3", "Hive Crash Site", S.MAGENTA),
    ("sector4", "Sector 4", "Magma Forge", S.ORANGE),
    ("sector5", "Sector 5", "Open Plains", S.GREEN),
    ("sector6", "Sector 6", "Orbital Platform", S.STEEL_LIGHT),
    ("sector7", "Sector 7", "Derelict Ship", S.TEXT_DIM),
    ("sector8", "Sector 8", "Twin Cores", S.CRYO),
    ("procedural", "Uncharted", "New map every time", S.ENERGY),
]
PROCEDURAL = "procedural"     # Endless only: a freshly generated map each play
CARD_W, CARD_H, CARD_PITCH_X, CARD_PITCH_Y = 224, 150, 240, 164


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
        per_row = 5
        for i, (sid, title, sub, color) in enumerate(SECTORS):
            row, col = divmod(i, per_row)
            in_row = min(per_row, len(SECTORS) - row * per_row)
            x0 = S.SCREEN_W // 2 - (in_row * CARD_PITCH_X - (CARD_PITCH_X - CARD_W)) // 2
            rect = pygame.Rect(x0 + col * CARD_PITCH_X, 128 + row * CARD_PITCH_Y, CARD_W, CARD_H)
            # All sectors unlocked for the demo. To restore progression:
            # unlocked = level_exists(sid) and i < game.save.get("unlocked", 1)
            unlocked = sid == PROCEDURAL or level_exists(sid)
            self.cards.append((rect, sid, title, sub, color, unlocked))
        self.thumbs = {sid: self.make_thumbnail(sid) for _, sid, *_ in self.cards
                       if sid != PROCEDURAL and level_exists(sid)}
        self.diff_buttons = [
            Button((S.SCREEN_W // 2 - 240 + i * 165, 504, 150, 42), name, "difficulty", name)
            for i, name in enumerate(S.DIFFICULTIES)
        ]
        self.back = Button((40, S.SCREEN_H - 80, 140, 46), "BACK", "back")
        cx = S.SCREEN_W // 2
        self.mode_buttons = [
            Button((cx - 165, 556, 160, 42), "CAMPAIGN", "mode", "campaign"),
            Button((cx + 5, 556, 160, 42), "ENDLESS", "mode", "endless"),
        ]
        self.picker = CommanderPicker(game, 608, mode=lambda: game.mode)

    @staticmethod
    def make_thumbnail(level_id, size=(150, 75)):
        """Shrink the level's real tile map down to a mini-map for the card."""
        try:
            level = LevelSystem(EventBus(), level_id)
        except (OSError, ValueError, KeyError):
            return None
        thumb = pygame.transform.smoothscale(level.surface, size)
        sx, sy = size[0] / S.MAP_W, size[1] / S.MAP_H
        for cx, cy in level.core_positions:
            pygame.draw.circle(thumb, S.CYAN, (int(cx * sx), int(cy * sy)), 4)
        for route in level.routes:
            x, y = route[0]
            px = min(size[0] - 3, max(3, int(x * sx)))
            py = min(size[1] - 3, max(3, int(y * sy)))
            pygame.draw.circle(thumb, S.MAGENTA, (px, py), 3)
        return thumb

    def playable(self, sid, unlocked):
        return unlocked and (sid != PROCEDURAL or self.game.mode == "endless")

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.change("menu")
        elif cmd.name == "click":
            for rect, sid, *_rest, unlocked in self.cards:
                if rect.collidepoint(cmd.pos):
                    if self.playable(sid, unlocked):
                        self.audio.play("click")
                        level_id = f"proc_{random.randrange(1, 10 ** 6)}" if sid == PROCEDURAL else sid
                        self.game.scenes.change("play", level_id=level_id, difficulty=self.game.difficulty,
                                                mode=self.game.mode)
                    else:
                        self.audio.play("error")
            for b in self.diff_buttons:
                if b.hit(cmd.pos):
                    self.game.difficulty = b.value
                    self.audio.play("click")
            if self.picker.handle_click(cmd.pos):
                self.audio.play("click")
            for b in self.mode_buttons:
                if b.hit(cmd.pos):
                    self.game.mode = b.value
                    self.audio.play("click")
            if self.back.hit(cmd.pos):
                self.game.scenes.change("menu")

    def on_update(self, dt):
        self.stars.update(dt)

    def on_render(self, screen):
        a = self.assets
        self.stars.draw(screen)
        title = a.text("SELECT SECTOR", 56, S.CYAN, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 70)))
        mouse = self.input.mouse_pos()
        endless = self.game.mode == "endless"
        for rect, sid, name, sub, color, unlocked in self.cards:
            ok = self.playable(sid, unlocked)
            hover = ok and rect.collidepoint(mouse)
            pygame.draw.rect(screen, S.PANEL_HI if hover else S.PANEL, rect, border_radius=10)
            pygame.draw.rect(screen, color if ok else S.HUD_EDGE, rect, 3, border_radius=10)
            preview = pygame.Rect(rect.x + 10, rect.y + 8, 154, 79)
            pygame.draw.rect(screen, S.SPACE, preview, border_radius=6)
            thumb = self.thumbs.get(sid)
            if thumb is not None:
                if not ok:
                    thumb = thumb.copy()
                    thumb.set_alpha(80)
                screen.blit(thumb, thumb.get_rect(center=preview.center))
            else:
                q = a.text("?", 56, color if ok else S.TEXT_DIM, True)
                screen.blit(q, q.get_rect(center=preview.center))
            pygame.draw.rect(screen, color if ok else S.HUD_EDGE, preview, 2, border_radius=6)
            screen.blit(a.text(name, 26, S.WHITE if ok else S.TEXT_DIM, True), (rect.x + 12, rect.y + 94))
            screen.blit(a.text(sub, 18, S.TEXT_DIM), (rect.x + 12, rect.y + 122))
            side_x = rect.right - 50
            if sid == PROCEDURAL and not endless:
                t = a.text("ENDLESS", 15, S.TEXT_DIM, True)
                screen.blit(t, t.get_rect(center=(side_x + 18, rect.y + 32)))
                t = a.text("ONLY", 15, S.TEXT_DIM, True)
                screen.blit(t, t.get_rect(center=(side_x + 18, rect.y + 50)))
            elif ok and endless:
                best = self.game.save.get("endless", {}).get(sid, {})
                t = a.text("BEST", 15, S.TEXT_DIM, True)
                screen.blit(t, t.get_rect(center=(side_x + 18, rect.y + 28)))
                t = a.text(str(best.get("wave", "-")), 30, S.ENERGY if best.get("wave") else S.TEXT_DIM, True)
                screen.blit(t, t.get_rect(center=(side_x + 18, rect.y + 54)))
            elif ok:
                best = self.game.save.get("sectors", {}).get(sid, {})
                for st in range(3):
                    draw_star(screen, (side_x + 18, rect.y + 22 + st * 24), 10, st < best.get("stars", 0))
            if not unlocked:
                msg = "LOCKED" if level_exists(sid) else "COMING SOON"
                lock = a.text(msg, 26, S.TEXT_DIM, True)
                screen.blit(lock, lock.get_rect(center=preview.center))
        label = a.text("Difficulty", 22, S.TEXT_DIM)
        screen.blit(label, label.get_rect(center=(S.SCREEN_W // 2, 488)))
        for b in self.diff_buttons:
            b.draw(screen, a, mouse, selected=(b.value == self.game.difficulty), size=28)
        for b in self.mode_buttons:
            b.draw(screen, a, mouse, selected=(b.value == self.game.mode), size=26)
        self.picker.draw(screen, a, mouse)
        self.back.draw(screen, a, mouse, size=28)

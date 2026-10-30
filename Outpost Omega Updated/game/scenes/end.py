"""Win and Lose screens shown after a sector ends."""
from .. import settings as S
from ..systems.level_system import level_exists
from ..systems.ui_system import Button
from .level_select import SECTORS, draw_star
from .menu import Starfield
from .scene_manager import Scene


class _EndScene(Scene):
    title = ""
    color = S.WHITE

    def __init__(self, game, level_id="sector1", difficulty=S.DEFAULT_DIFFICULTY,
                 stars=0, score=0, kills=0, core=0.0, waves=0, **kwargs):
        super().__init__(game, **kwargs)
        self.level_id = level_id
        self.difficulty = difficulty
        self.stars_earned = stars
        self.score = score
        self.kills = kills
        self.core = core
        self.waves = waves
        self.bg = Starfield()
        cx = S.SCREEN_W // 2
        self.buttons = [Button((cx - 150, 470, 300, 52), "RETRY", "retry"),
                        Button((cx - 150, 536, 300, 52), "LEVEL SELECT", "select")]
        nxt = self.next_level()
        if nxt:
            self.buttons.insert(0, Button((cx - 150, 404, 300, 52), "NEXT SECTOR", "next"))

    def next_level(self):
        return None

    def handle_command(self, cmd):
        if cmd.name == "click":
            for b in self.buttons:
                if b.hit(cmd.pos):
                    self.audio.play("click")
                    self.activate(b.command)
                    return
        elif cmd.name in ("confirm", "start_wave"):
            self.activate("retry")
        elif cmd.name == "pause":
            self.activate("select")

    def activate(self, command):
        scenes = self.game.scenes
        if command == "retry":
            scenes.change("play", level_id=self.level_id, difficulty=self.difficulty)
        elif command == "next":
            scenes.change("play", level_id=self.next_level(), difficulty=self.difficulty)
        elif command == "select":
            self.audio.stop_music()
            scenes.change("level_select")

    def on_update(self, dt):
        self.bg.update(dt)

    def stats_lines(self):
        return [f"Score {self.score}", f"Aliens destroyed {self.kills}",
                f"Core integrity {int(self.core * 100)}%"]

    def on_render(self, screen):
        a = self.assets
        self.bg.draw(screen)
        title = a.text(self.title, 90, self.color, True)
        screen.blit(title, title.get_rect(center=(S.SCREEN_W // 2, 130)))
        for i, line in enumerate(self.stats_lines()):
            t = a.text(line, 32, S.WHITE)
            screen.blit(t, t.get_rect(center=(S.SCREEN_W // 2, 280 + i * 36)))
        self.render_extra(screen)
        mouse = self.input.mouse_pos()
        for b in self.buttons:
            b.draw(screen, a, mouse, size=30)

    def render_extra(self, screen):
        pass


class WinScene(_EndScene):
    title = "SECTOR SECURED"
    color = S.CYAN

    def next_level(self):
        ids = [s[0] for s in SECTORS]
        i = ids.index(self.level_id) if self.level_id in ids else -1
        if 0 <= i < len(ids) - 1 and level_exists(ids[i + 1]):
            return ids[i + 1]
        return None

    def render_extra(self, screen):
        for s in range(3):
            draw_star(screen, (S.SCREEN_W // 2 - 60 + s * 60, 215), 24, s < self.stars_earned)


class LoseScene(_EndScene):
    title = "CORE DESTROYED"
    color = S.RED

    def stats_lines(self):
        return [f"You held out until wave {self.waves}", f"Score {self.score}",
                f"Aliens destroyed {self.kills}"]

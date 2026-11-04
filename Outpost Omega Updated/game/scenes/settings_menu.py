"""Settings overlay: volume, screen shake, particles and HUD panels.

Opened from the main menu or the pause menu. Values live in GameManager.settings
and are saved to save.json as soon as they change.
"""
import pygame

from .. import settings as S
from ..systems.ui_system import Button
from .scene_manager import Scene

LEVELS3 = ("Off", "Low", "Full")
PARTICLES = ("Low", "Medium", "High")

# key, label, kind, extra
ROWS = (
    ("sfx", "Sound effects", "percent", None),
    ("music", "Music", "percent", None),
    ("shake", "Screen shake", "choice", LEVELS3),
    ("particles", "Particles", "choice", PARTICLES),
    ("numbers", "Damage numbers", "toggle", None),
    ("wave_report", "Post-wave report", "toggle", None),
    ("timeline", "Wave timeline", "toggle", None),
    ("colorblind", "Colorblind mode", "toggle", None),
    ("skin", "Commander skin", "skin", None),
    ("unlock_all", "Unlock all sectors", "toggle", None),
)


class SettingsScene(Scene):
    is_overlay = True
    ROW_H = 46

    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        cx = S.SCREEN_W // 2
        self.top = 150
        self.buttons = []
        for i, (key, _label, _kind, _extra) in enumerate(ROWS):
            y = self.top + i * self.ROW_H
            self.buttons.append(Button((cx + 60, y, 44, 38), "<", "dec", key))
            self.buttons.append(Button((cx + 236, y, 44, 38), ">", "inc", key))
        y = self.top + len(ROWS) * self.ROW_H + 14
        self.controls = Button((cx - 290, y, 280, 50), "CONTROLS", "controls")
        self.back = Button((cx + 10, y, 280, 50), "BACK", "back", hotkey="Esc")
        self.buttons += [self.controls, self.back]

    @staticmethod
    def value_text(key, kind, extra, value):
        if kind == "percent":
            return f"{value}%"
        if kind == "choice":
            return extra[value]
        if kind == "skin":
            return value.capitalize()
        return "On" if value else "Off"

    def change(self, key, step):
        settings = self.game.settings
        _k, _label, kind, extra = next(r for r in ROWS if r[0] == key)
        if kind == "percent":
            settings[key] = max(0, min(100, settings[key] + 10 * step))
        elif kind == "choice":
            settings[key] = max(0, min(len(extra) - 1, settings[key] + step))
        elif kind == "skin":   # skins unlock through achievements (data/meta.json)
            from ..systems.meta import unlocked_skins
            skins = unlocked_skins(self.game.save, self.game.data["meta"])
            cur = settings.get(key, "classic")
            i = skins.index(cur) if cur in skins else 0
            settings[key] = skins[(i + step) % len(skins)]
        else:
            settings[key] = not settings[key]
        self.game.apply_settings()
        self.game.write_save()
        self.audio.play("click")

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.game.scenes.pop()
        elif cmd.name == "click":
            for b in self.buttons:
                if b.hit(cmd.pos):
                    if b.command == "back":
                        self.audio.play("click")
                        self.game.scenes.pop()
                    elif b.command == "controls":
                        self.audio.play("click")
                        self.game.scenes.push("controls")
                    else:
                        self.change(b.value, -1 if b.command == "dec" else 1)
                    return

    def on_render(self, screen):
        shade = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        shade.fill((5, 6, 16, 245))
        screen.blit(shade, (0, 0))
        a = self.assets
        cx = S.SCREEN_W // 2
        title = a.text("SETTINGS", 64, S.CYAN, True)
        screen.blit(title, title.get_rect(center=(cx, 110)))
        mouse = self.input.mouse_pos()
        for i, (key, label, kind, extra) in enumerate(ROWS):
            y = self.top + i * self.ROW_H
            screen.blit(a.text(label, 28, S.WHITE, True), (cx - 280, y + 6))
            value = self.game.settings.get(key, False)
            v = a.text(self.value_text(key, kind, extra, value), 26, S.ENERGY, True)
            screen.blit(v, v.get_rect(center=(cx + 170, y + 19)))
            if kind == "percent":   # little volume bar under the number
                pygame.draw.rect(screen, S.HUD_EDGE, (cx + 116, y + 34, 108, 4))
                pygame.draw.rect(screen, S.CYAN, (cx + 116, y + 34, int(108 * value / 100), 4))
        for b in self.buttons:
            b.draw(screen, a, mouse, size=26 if b in (self.back, self.controls) else 28)
        from ..systems.meta import unlocked_skins
        n = len(unlocked_skins(self.game.save, self.game.data["meta"]))
        tip = a.text(f"{n}/{len(self.game.data['meta']['skins'])} skins unlocked (earn more from achievements in the Codex)",
                     18, S.TEXT_DIM)
        screen.blit(tip, tip.get_rect(center=(cx, S.SCREEN_H - 14)))

"""Story campaign (data/story.json).

StoryScene shows a sector's briefing before it starts, its debrief after a win, and the
ending after Sector 13. Click / Space / Enter: next line (or finish the one being typed).
Esc: skip the rest. StoryRadio plays the in-mission radio lines as waves start.
"""
import pygame

from .. import settings as S
from ..systems.ui_system import Button
from .menu import Starfield
from .scene_manager import Scene

FINAL = "sector13"


def story_on(game, level_id, mode="campaign"):
    return (mode == "campaign" and game.settings.get("story", True)
            and level_id in game.data["story"]["sectors"])


class StoryRadio:
    """Lives in a PlayScene: says the sector's radio lines when their wave starts."""

    def __init__(self, play, sector):
        self.play = play
        self.lines = {int(k): v for k, v in sector.get("radio", {}).items()}
        self.speakers = play.game.data["story"]["speakers"]
        play.events.subscribe("wave_started", self.on_wave)

    def on_wave(self, **_):
        line = self.lines.get(self.play.waves.wave_number)
        if line:
            who, text = line
            sp = self.speakers.get(who, {})
            self.play.juice.say(text, speaker=sp.get("name", who).upper() or None,
                                color=tuple(sp.get("color", S.CYAN)), life=7.0)


class StoryScene(Scene):
    """phase: "briefing" (then plays the sector), "debrief" (then `then`), "ending" (then menu)."""
    TYPE_SPEED = 70   # characters per second

    def __init__(self, game, level_id="sector1", phase="briefing", launch=None, then=None, **kwargs):
        super().__init__(game, **kwargs)
        story = game.data["story"]
        self.speakers = story["speakers"]
        self.level_id = level_id
        self.phase = phase
        self.launch = launch or {}
        self.then = then
        sector = story["sectors"].get(level_id, {})
        self.chapter = sector.get("chapter", "")
        if phase == "ending":
            self.lines = story["ending"]
            self.chapter = "Epilogue"
        else:
            self.lines = sector.get(phase, [])
        self.i = 0
        self.shown = 0.0
        self.stars = Starfield()
        self.thumb = None
        if phase != "ending":
            from .level_select import LevelSelectScene
            self.thumb = LevelSelectScene.make_thumbnail(level_id, (480, 240))
        self.skip = Button((S.SCREEN_W - 170, 16, 154, 40), "SKIP", "skip", hotkey="Esc")
        if phase == "briefing":
            sectors = game.save.setdefault("story", [])
            if level_id not in sectors:
                sectors.append(level_id)

    @property
    def line(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def advance(self):
        line = self.line
        if line is None:
            return self.done()
        if self.shown < len(line[1]):
            self.shown = len(line[1])
            return
        self.i += 1
        self.shown = 0.0
        if self.i >= len(self.lines):
            self.done()

    def done(self):
        g = self.game
        if self.phase == "briefing":
            g.scenes.change("play", **self.launch)
        elif self.phase == "debrief" and self.level_id == FINAL:
            g.scenes.change("story", level_id=FINAL, phase="ending", then=self.then)
        elif self.phase == "ending":
            g.save["story_complete"] = True
            g.write_save()
            if self.then:
                name, kwargs = self.then
                g.scenes.change(name, **kwargs)
            else:
                g.scenes.change("menu")
        elif self.then:
            name, kwargs = self.then
            g.scenes.change(name, **kwargs)
        else:
            g.scenes.change("menu")

    def handle_command(self, cmd):
        if cmd.name == "pause":
            self.audio.play("click")
            self.done()
        elif cmd.name == "click":
            if self.skip.hit(cmd.pos):
                self.audio.play("click")
                self.done()
            else:
                self.advance()
        elif cmd.name in ("confirm", "start_wave"):
            self.advance()

    def on_update(self, dt):
        self.stars.update(dt)
        if self.line is not None:
            self.shown = min(len(self.line[1]), self.shown + self.TYPE_SPEED * dt)
        elif not self.lines:
            self.done()

    @staticmethod
    def wrap(assets, text, size, width):
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if assets.text(test, size).get_width() > width and cur:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines

    def on_render(self, screen):
        a = self.assets
        self.stars.draw(screen)
        cx = S.SCREEN_W // 2
        num = self.level_id.replace("sector", "")
        head = {"briefing": f"SECTOR {num} BRIEFING", "debrief": f"SECTOR {num} DEBRIEF",
                "ending": "MISSION COMPLETE"}[self.phase]
        t = a.text(head, 22, S.TEXT_DIM, True)
        screen.blit(t, t.get_rect(center=(cx, 70)))
        t = a.text(self.chapter.upper(), 46, S.CYAN, True)
        screen.blit(t, t.get_rect(center=(cx, 116)))
        # earlier lines, faded, as a transcript
        y = 180
        width = 480 if self.thumb is not None else 900
        x0 = cx - 520 if self.thumb is not None else cx - 450
        for who, text in self.lines[max(0, self.i - 4):self.i]:
            sp = self.speakers.get(who, {})
            name = sp.get("name", who)
            line = f"{name}: {text}" if name else text
            for row in self.wrap(a, line, 18, width)[:3]:
                surf = a.text(row, 18, S.TEXT_DIM)
                screen.blit(surf, (x0, y))
                y += 22
            y += 8
        if self.thumb is not None:   # tactical map of the sector
            r = self.thumb.get_rect(topleft=(cx + 40, 172))
            screen.blit(self.thumb, r)
            pygame.draw.rect(screen, S.CYAN, r.inflate(4, 4), 2, border_radius=4)
            cap = a.text("TACTICAL MAP", 14, S.TEXT_DIM, True)
            screen.blit(cap, (r.x, r.bottom + 8))
        # current line in the dialog box
        box = pygame.Rect(cx - 520, 470, 1040, 180)
        pygame.draw.rect(screen, S.HUD_BG, box, border_radius=12)
        line = self.line
        if line is not None:
            who, text = line
            sp = self.speakers.get(who, {})
            col = tuple(sp.get("color", S.WHITE))
            pygame.draw.rect(screen, col, box, 2, border_radius=12)
            tx = box.x + 24
            if sp.get("tag"):
                por = pygame.Rect(box.x + 20, box.y + 24, 120, 132)
                pygame.draw.rect(screen, S.PANEL, por, border_radius=10)
                pygame.draw.rect(screen, col, por, 3, border_radius=10)
                # a simple helmet silhouette with the speaker's initials
                pygame.draw.circle(screen, col, (por.centerx, por.y + 52), 30)
                pygame.draw.rect(screen, S.PANEL, (por.centerx - 20, por.y + 44, 40, 12), border_radius=4)
                pygame.draw.rect(screen, col, (por.centerx - 34, por.y + 86, 68, 34), border_radius=10)
                tag = a.text(sp["tag"], 20, S.SPACE, True)
                screen.blit(tag, tag.get_rect(center=(por.centerx, por.y + 103)))
                tx = por.right + 24
                name = a.text(sp.get("name", who), 24, col, True)
                screen.blit(name, (tx, box.y + 22))
            shown = text[:int(self.shown)]
            yy = box.y + (60 if sp.get("tag") else 40)
            for row in self.wrap(a, shown, 24, box.right - tx - 24):
                screen.blit(a.text(row, 24, S.WHITE), (tx, yy))
                yy += 30
        hint = a.text(f"Click / Space: next  ({min(self.i + 1, len(self.lines))}/{len(self.lines)})", 16, S.TEXT_DIM)
        screen.blit(hint, hint.get_rect(bottomright=(box.right - 12, box.bottom - 8)))
        self.skip.draw(screen, a, self.input.mouse_pos(), size=22)

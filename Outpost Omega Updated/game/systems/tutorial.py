"""Interactive tutorial: a checklist that walks a new player through Sector 1.

Each step has a check(play) that turns True when the player has done it; the panel at
the top of the map shows the current step and ticks it off. Started from the main menu's
TUTORIAL button (PlayScene(..., tutorial=True)).
"""
import pygame

from .. import settings as S


def _moved(play):
    c = play.player.commander
    return c.pos.distance_to(c.spawn) > 64


STEPS = [
    ("Move Commander Vance with WASD or the arrow keys.", _moved),
    ("Pick the Pulse Turret: press 1 (Assault tab) or click its button.",
     lambda p: p.towers.build_kind == "pulse" or any(t.kind == "pulse" for t in p.towers.towers)),
    ("Click a green tile next to the path to build it.", lambda p: len(p.towers.towers) >= 1),
    ("Hover the build buttons to see stats and combos. Press Tab to see the other tabs.",
     lambda p: p.ui.tab != 0),
    ("Press Space to start the first wave early.", lambda p: p.waves.wave_number >= 1),
    ("Vance shoots aliens near her automatically. Walk close to help.",
     lambda p: p.session.kills >= 3),
    ("Select a tower (click it) and press U to upgrade it.",
     lambda p: any(t.tier > 0 for t in p.towers.towers)),
    ("Press Q, then click the map, to call an Orbital Strike.",
     lambda p: not p.player.orbital.ready or p.player.strikes),
    ("Press R to dash and V to throw a grenade at the mouse.",
     lambda p: p.player.kit.dash_cd > 0 or p.player.kit.flying or
     p.player.kit.grenades.get("frag", 0) < 2),
    ("Walk over drops to collect them. Hold E near a damaged tower to repair it.",
     lambda p: p.waves.wave_number >= 2),
    ("That's the basics! Survive all 10 waves. (Esc for Settings)", lambda p: False),
]


class Tutorial:
    def __init__(self):
        self.step = 0
        self.flash = 0.0

    def update(self, play, dt):
        self.flash = max(0.0, self.flash - dt)
        if self.step < len(STEPS) - 1 and STEPS[self.step][1](play):
            self.step += 1
            self.flash = 0.6
            play.audio.play("pickup")

    def render(self, screen, assets):
        text = STEPS[self.step][0]
        surf = assets.text(text, 22, S.WHITE, True)
        w = surf.get_width() + 40
        x, y = S.MAP_W // 2 - w // 2, 64
        bg = pygame.Surface((w, 52), pygame.SRCALPHA)
        bg.fill((*S.HUD_BG, 230))
        screen.blit(bg, (x, y))
        col = S.ENERGY if self.flash > 0 else S.CYAN
        pygame.draw.rect(screen, col, (x, y, w, 52), 2, border_radius=6)
        head = assets.text(f"TUTORIAL  {self.step + 1}/{len(STEPS)}", 14, col, True)
        screen.blit(head, (x + 20, y + 5))
        screen.blit(surf, (x + 20, y + 22))

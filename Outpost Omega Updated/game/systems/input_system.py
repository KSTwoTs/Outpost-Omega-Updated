"""InputSystem: turns raw pygame events into named Commands.

Scenes never check key codes directly. They ask for commands
("start_wave", "select_tower", ...) so rebinding keys only means
editing KEY_BINDINGS.
"""
import math
from dataclasses import dataclass

import pygame


@dataclass
class Command:
    name: str
    pos: tuple = None
    value: object = None


KEY_BINDINGS = {
    pygame.K_SPACE: ("start_wave", None),
    pygame.K_q: ("orbital_strike", None),
    pygame.K_ESCAPE: ("pause", None),
    pygame.K_p: ("pause", None),
    pygame.K_F1: ("toggle_debug", None),
    pygame.K_u: ("upgrade", None),
    pygame.K_x: ("sell", None),
    pygame.K_t: ("cycle_targeting", None),
    pygame.K_1: ("select_tower", 1),
    pygame.K_2: ("select_tower", 2),
    pygame.K_3: ("select_tower", 3),
    pygame.K_4: ("select_tower", 4),
    pygame.K_5: ("select_tower", 5),
    pygame.K_RETURN: ("confirm", None),
}

MOVE_KEYS = {
    "up": (pygame.K_w, pygame.K_UP),
    "down": (pygame.K_s, pygame.K_DOWN),
    "left": (pygame.K_a, pygame.K_LEFT),
    "right": (pygame.K_d, pygame.K_RIGHT),
}
REPAIR_KEYS = (pygame.K_e,)


class InputSystem:
    def __init__(self):
        self.quit_requested = False

    def process(self, event):
        """Return a list of Commands for one pygame event."""
        cmds = []
        if event.type == pygame.QUIT:
            self.quit_requested = True
        elif event.type == pygame.KEYDOWN:
            bound = KEY_BINDINGS.get(event.key)
            if bound:
                cmds.append(Command(bound[0], value=bound[1]))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                cmds.append(Command("click", pos=event.pos))
            elif event.button == 3:
                cmds.append(Command("right_click", pos=event.pos))
        return cmds

    @staticmethod
    def move_vector():
        """Normalized (x, y) from WASD / arrow keys, so diagonals aren't faster."""
        keys = pygame.key.get_pressed()
        held = lambda name: any(keys[k] for k in MOVE_KEYS[name])
        x = held("right") - held("left")
        y = held("down") - held("up")
        if x and y:
            inv = 1 / math.sqrt(2)
            return (x * inv, y * inv)
        return (float(x), float(y))

    @staticmethod
    def repair_held():
        keys = pygame.key.get_pressed()
        return any(keys[k] for k in REPAIR_KEYS)

    @staticmethod
    def shift_held():
        return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

    @staticmethod
    def mouse_pos():
        return pygame.mouse.get_pos()

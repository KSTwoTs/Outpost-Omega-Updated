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
    # Number row picks a slot in the HUD's current tower tab; Tab switches tabs.
    pygame.K_1: ("select_slot", 0),
    pygame.K_2: ("select_slot", 1),
    pygame.K_3: ("select_slot", 2),
    pygame.K_4: ("select_slot", 3),
    pygame.K_5: ("select_slot", 4),
    pygame.K_6: ("select_slot", 5),
    pygame.K_7: ("select_slot", 6),
    pygame.K_8: ("select_slot", 7),
    pygame.K_9: ("select_slot", 8),
    pygame.K_0: ("select_slot", 9),
    pygame.K_MINUS: ("select_slot", 10),
    pygame.K_EQUALS: ("select_slot", 11),
    pygame.K_TAB: ("next_tab", None),
    pygame.K_i: ("toggle_report", None),
    pygame.K_m: ("move_tower", None),
    pygame.K_g: ("stance", None),
    pygame.K_k: ("socket", None),
    pygame.K_j: ("fuse", None),
    pygame.K_r: ("dash", None),
    pygame.K_v: ("grenade", None),
    pygame.K_b: ("cycle_grenade", None),
    pygame.K_z: ("mech", None),
    pygame.K_BACKSPACE: ("undo", None),
    pygame.K_h: ("tame", None),
    pygame.K_DELETE: ("sacrifice", None),
    pygame.K_y: ("sandbox_menu", None),
    pygame.K_RETURN: ("confirm", None),
    pygame.K_f: ("cycle_speed", None),
}

# Rebindable single-key actions (Settings > Controls). action -> label
REBINDABLE = [("start_wave", "Start wave"), ("orbital_strike", "Orbital Strike"), ("dash", "Dash"),
              ("grenade", "Throw grenade"), ("cycle_grenade", "Next grenade"), ("mech", "Mech suit"),
              ("upgrade", "Upgrade tower"), ("sell", "Sell tower"), ("cycle_targeting", "Targeting"),
              ("move_tower", "Move tower"), ("stance", "Stance"), ("socket", "Socket chip"),
              ("fuse", "Fuse towers"), ("next_tab", "Next tower tab"), ("toggle_report", "Wave report"),
              ("cycle_speed", "Game speed"), ("undo", "Undo placement"), ("tame", "Tame alien"),
              ("sacrifice", "Sacrifice tower")]
DEFAULT_BINDINGS = None   # filled below

MOVE_KEYS = {
    "up": (pygame.K_w, pygame.K_UP),
    "down": (pygame.K_s, pygame.K_DOWN),
    "left": (pygame.K_a, pygame.K_LEFT),
    "right": (pygame.K_d, pygame.K_RIGHT),
}
REPAIR_KEYS = [pygame.K_e]
# Local co-op Player 2: arrow keys move, Right Ctrl / Numpad 0 repairs, Right Shift / Numpad Enter
# dashes. A controller, if plugged in, drives Player 2 instead of Player 1.
P2_REPAIR_KEYS = (pygame.K_RCTRL, pygame.K_KP0)
P2_DASH_KEYS = (pygame.K_RSHIFT, pygame.K_KP_ENTER)
DEFAULT_BINDINGS = dict(KEY_BINDINGS)
DEFAULT_MOVE = {k: tuple(v) for k, v in MOVE_KEYS.items()}


def apply_bindings(custom):
    """custom: {action: pygame key code} from settings["keys"] (also "walk_up" etc. and "repair")."""
    KEY_BINDINGS.clear()
    KEY_BINDINGS.update(DEFAULT_BINDINGS)
    for action, key in (custom or {}).items():
        if action.startswith("walk_"):
            d = action[5:]
            MOVE_KEYS[d] = (key, DEFAULT_MOVE[d][1])
            continue
        if action == "repair":
            REPAIR_KEYS[:] = [key]
            continue
        for k, (cmd, _v) in list(KEY_BINDINGS.items()):
            if cmd == action:
                del KEY_BINDINGS[k]
        KEY_BINDINGS[key] = (action, None)


def key_for(action):
    if action.startswith("walk_"):
        return MOVE_KEYS[action[5:]][0]
    if action == "repair":
        return REPAIR_KEYS[0]
    for k, (cmd, _v) in KEY_BINDINGS.items():
        if cmd == action:
            return k
    return None


# Controller (Xbox layout): A start wave, B grenade, X hold to repair, Y mech, LB next tab,
# RB dash, View report, Menu pause, RT Orbital Strike on the biggest group, D-pad up: upgrade.
PAD_BUTTONS = {0: "start_wave", 1: "grenade_auto", 3: "mech", 4: "next_tab", 5: "dash",
               6: "toggle_report", 7: "pause"}
PAD_REPAIR = 2
DEADZONE = 0.25


class InputSystem:
    # (x offset, y offset, scale) of the game canvas inside the window; GameManager.present
    # updates it every frame so clicks land in the right place when the window is resized.
    viewport = (0, 0, 1.0)

    joysticks = []
    coop = False     # PlayScene sets this while a co-op game is running

    def __init__(self):
        self.quit_requested = False
        self.trigger_down = False
        try:
            pygame.joystick.init()
            InputSystem.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        except pygame.error:
            InputSystem.joysticks = []

    @classmethod
    def to_canvas(cls, pos):
        x0, y0, scale = cls.viewport
        return (int((pos[0] - x0) / scale), int((pos[1] - y0) / scale))

    def process(self, event):
        """Return a list of Commands for one pygame event."""
        cmds = []
        if event.type == pygame.QUIT:
            self.quit_requested = True
        elif event.type == pygame.KEYDOWN and InputSystem.coop and event.key in P2_DASH_KEYS:
            cmds.append(Command("dash2"))
        elif event.type == pygame.KEYDOWN:
            bound = KEY_BINDINGS.get(event.key)
            if bound:
                cmds.append(Command(bound[0], value=bound[1]))
        elif event.type == pygame.JOYDEVICEADDED:
            try:
                InputSystem.joysticks.append(pygame.joystick.Joystick(event.device_index))
            except pygame.error:
                pass
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button in PAD_BUTTONS:
                name = PAD_BUTTONS[event.button]
                if InputSystem.coop and name == "dash":
                    name = "dash2"
                cmds.append(Command(name))
        elif event.type == pygame.JOYHATMOTION:
            if event.value[1] == 1:
                cmds.append(Command("upgrade"))
            elif event.value[0] != 0:
                cmds.append(Command("next_tab"))
        elif event.type == pygame.JOYAXISMOTION and event.axis == 5:
            down = event.value > 0.5
            if down and not self.trigger_down:
                cmds.append(Command("orbital_auto"))
            self.trigger_down = down
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                cmds.append(Command("click", pos=self.to_canvas(event.pos)))
            elif event.button == 3:
                cmds.append(Command("right_click", pos=self.to_canvas(event.pos)))
        return cmds

    @staticmethod
    def move_vector(player=1):
        """Normalized (x, y) from WASD / arrow keys, so diagonals aren't faster.
        In co-op, Player 1 has WASD only and Player 2 the arrows plus any controller."""
        keys = pygame.key.get_pressed()
        if InputSystem.coop:
            idx = 0 if player == 1 else 1
            held = lambda name: keys[MOVE_KEYS[name][idx]]
        else:
            held = lambda name: any(keys[k] for k in MOVE_KEYS[name])
        x = held("right") - held("left")
        y = held("down") - held("up")
        pads = InputSystem.joysticks if (not InputSystem.coop or player == 2) else []
        for js in pads:   # left stick
            try:
                ax, ay = js.get_axis(0), js.get_axis(1)
            except pygame.error:
                continue
            if abs(ax) > DEADZONE or abs(ay) > DEADZONE:
                length = math.hypot(ax, ay)
                return (ax / max(1.0, length), ay / max(1.0, length))
        if x and y:
            inv = 1 / math.sqrt(2)
            return (x * inv, y * inv)
        return (float(x), float(y))

    @staticmethod
    def repair_held(player=1):
        keys = pygame.key.get_pressed()
        pad = False
        if InputSystem.coop:
            if player == 1:
                return any(keys[k] for k in REPAIR_KEYS)
            if any(keys[k] for k in P2_REPAIR_KEYS):
                return True
        for js in InputSystem.joysticks:
            try:
                pad = pad or js.get_button(PAD_REPAIR)
            except pygame.error:
                pass
        return any(keys[k] for k in REPAIR_KEYS) or bool(pad)

    @staticmethod
    def shift_held():
        return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

    @classmethod
    def mouse_pos(cls):
        return cls.to_canvas(pygame.mouse.get_pos())

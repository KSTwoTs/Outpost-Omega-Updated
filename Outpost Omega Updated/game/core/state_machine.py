"""A small finite state machine shared by the Commander, enemies and towers.

Subclass State and override the hooks you need:

    class Walk(State):
        def update(self, owner, dt):
            owner.follow_path(dt)
            if owner.health.is_dead:
                return "dying"          # returning a name switches state

    fsm = StateMachine(owner, {"walk": Walk(), "dying": Dying()}, "walk")
    fsm.update(dt)
"""


class State:
    name = "state"

    def enter(self, owner):
        pass

    def exit(self, owner):
        pass

    def update(self, owner, dt):
        """Return the name of the next state to switch, or None to stay."""
        return None


class StateMachine:
    def __init__(self, owner, states, initial):
        self.owner = owner
        self.states = states
        for key, state in states.items():
            state.name = key
        self.current = None
        self.time_in_state = 0.0
        self.change(initial)

    @property
    def name(self):
        return self.current.name if self.current else None

    def change(self, name):
        if name not in self.states:
            raise KeyError(f"Unknown state '{name}'")
        if self.current is not None:
            if self.current.name == name:
                return
            self.current.exit(self.owner)
        self.current = self.states[name]
        self.time_in_state = 0.0
        self.current.enter(self.owner)

    def update(self, dt):
        self.time_in_state += dt
        nxt = self.current.update(self.owner, dt)
        if nxt:
            self.change(nxt)

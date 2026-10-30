"""Timer / Cooldown helpers driven by dt (no wall-clock time)."""


class Timer:
    """Counts down `duration` seconds. update() returns True on the frame it fires.

    repeat=True restarts automatically (good for fire-rate cooldowns).
    """

    def __init__(self, duration, repeat=False, start_done=False):
        self.duration = float(duration)
        self.repeat = repeat
        self.remaining = 0.0 if start_done else self.duration
        self.active = not start_done

    def reset(self, duration=None):
        if duration is not None:
            self.duration = float(duration)
        self.remaining = self.duration
        self.active = True

    def stop(self):
        self.active = False
        self.remaining = 0.0

    @property
    def done(self):
        return not self.active

    @property
    def progress(self):
        """0.0 when just started, 1.0 when finished."""
        if self.duration <= 0:
            return 1.0
        return 1.0 - max(0.0, self.remaining) / self.duration

    def update(self, dt):
        if not self.active:
            return False
        self.remaining -= dt
        if self.remaining <= 0:
            if self.repeat:
                self.remaining += self.duration
            else:
                self.active = False
                self.remaining = 0.0
            return True
        return False


class Cooldown:
    """Ready/not-ready gate, e.g. a tower's fire rate or the Orbital Strike."""

    def __init__(self, duration, ready=True):
        self.duration = float(duration)
        self.remaining = 0.0 if ready else self.duration

    @property
    def ready(self):
        return self.remaining <= 0

    @property
    def fraction(self):
        """1.0 = fully charged."""
        if self.duration <= 0:
            return 1.0
        return 1.0 - max(0.0, self.remaining) / self.duration

    def trigger(self, duration=None):
        if duration is not None:
            self.duration = float(duration)
        self.remaining = self.duration

    def update(self, dt, rate=1.0):
        if self.remaining > 0:
            self.remaining -= dt * rate

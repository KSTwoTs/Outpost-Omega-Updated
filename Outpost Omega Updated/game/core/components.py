"""Reusable components: Health and PathFollower.

Kept free of pygame so they can be unit-tested on their own.
"""
import math


class Health:
    def __init__(self, max_hp, armor=0):
        self.max_hp = float(max_hp)
        self.hp = float(max_hp)
        self.armor = armor

    @property
    def is_dead(self):
        return self.hp <= 0

    @property
    def ratio(self):
        return max(0.0, self.hp / self.max_hp) if self.max_hp else 0.0

    def damage(self, amount, ignore_armor=False):
        """Apply damage and return what was actually dealt.

        Armor rule from the pitch: damage = max(1, dmg - armor).
        """
        if self.is_dead or amount <= 0:
            return 0
        dealt = amount if ignore_armor else max(1, amount - self.armor)
        dealt = min(dealt, self.hp)
        self.hp -= dealt
        return dealt

    def heal(self, amount):
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def reset(self, max_hp=None):
        if max_hp is not None:
            self.max_hp = float(max_hp)
        self.hp = self.max_hp


class PathFollower:
    """Moves a point along a list of (x, y) waypoints at a given speed.

    `distance` is how far along the path we are, used by towers for
    "first"/"last" targeting. `progress` is that distance as 0..1.
    """

    def __init__(self, waypoints, start_distance=0.0):
        self.waypoints = [tuple(map(float, p)) for p in waypoints]
        self.segment_lengths = []
        for a, b in zip(self.waypoints, self.waypoints[1:]):
            self.segment_lengths.append(math.dist(a, b))
        self.total_length = sum(self.segment_lengths) or 1.0
        self.index = 0             # current segment
        self.seg_pos = 0.0         # distance into current segment
        self.distance = 0.0
        self.finished = False
        self.x, self.y = self.waypoints[0]
        self.direction = (1.0, 0.0)
        if start_distance > 0:
            self.advance(start_distance)

    @property
    def progress(self):
        return self.distance / self.total_length

    @property
    def pos(self):
        return (self.x, self.y)

    def advance(self, amount):
        """Move `amount` pixels forward. Returns True if the end is reached."""
        while amount > 0 and not self.finished:
            seg_len = self.segment_lengths[self.index]
            left = seg_len - self.seg_pos
            step = min(left, amount)
            self.seg_pos += step
            self.distance += step
            amount -= step
            if self.seg_pos >= seg_len - 1e-6:
                if self.index + 1 >= len(self.segment_lengths):
                    self.finished = True
                else:
                    self.index += 1
                    self.seg_pos = 0.0
        self._update_position()
        return self.finished

    def _update_position(self):
        if not self.segment_lengths:
            return
        a = self.waypoints[self.index]
        b = self.waypoints[self.index + 1]
        seg_len = self.segment_lengths[self.index] or 1.0
        t = min(1.0, self.seg_pos / seg_len)
        self.x = a[0] + (b[0] - a[0]) * t
        self.y = a[1] + (b[1] - a[1]) * t
        self.direction = ((b[0] - a[0]) / seg_len, (b[1] - a[1]) / seg_len)

    def position_ahead(self, extra):
        """Where we will be after moving `extra` more pixels (for lead aim)."""
        clone = PathFollower(self.waypoints, self.distance + extra)
        return clone.pos

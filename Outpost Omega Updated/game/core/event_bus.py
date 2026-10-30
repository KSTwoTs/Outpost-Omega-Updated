"""EventBus: lets systems talk without holding references to each other.

    bus.subscribe("enemy_killed", on_enemy_killed)
    bus.publish("enemy_killed", enemy=e)        # calls every listener now

Each PlayScene creates its own bus, so restarting a level throws away all
listeners at once and nothing leaks between runs.
"""
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)

    def subscribe(self, event, callback):
        if callback not in self._listeners[event]:
            self._listeners[event].append(callback)

    def unsubscribe(self, event, callback):
        if callback in self._listeners[event]:
            self._listeners[event].remove(callback)

    def publish(self, event, **data):
        # Copy so a listener may unsubscribe while we iterate.
        for callback in list(self._listeners[event]):
            callback(**data)

    def clear(self):
        self._listeners.clear()

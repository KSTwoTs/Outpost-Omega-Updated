"""Shared, engine-agnostic building blocks (no pygame imports here)."""
from .event_bus import EventBus
from .state_machine import State, StateMachine
from .timer import Timer, Cooldown
from .components import Health, PathFollower
from .pathfinding import astar, compress_path
from .spatial_hash import SpatialHash, circles_overlap, dist_sq
from .pool import ObjectPool

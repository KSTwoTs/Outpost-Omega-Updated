"""ObjectPool: reuse projectiles and particles instead of allocating new ones.

    pool = ObjectPool(Particle, prealloc=500)
    p = pool.acquire()        # an inactive object, or a new one
    p.spawn(...)
    ...
    pool.release(p)           # back on the free list

Objects must have an `active` attribute. `pool.active` is the live list.
"""


class ObjectPool:
    def __init__(self, factory, prealloc=0, max_size=None):
        self.factory = factory
        self.max_size = max_size
        self.free = [factory() for _ in range(prealloc)]
        self.active = []

    def acquire(self):
        if self.free:
            obj = self.free.pop()
        elif self.max_size is not None and len(self.active) >= self.max_size:
            # Pool is full: recycle the oldest live object.
            obj = self.active.pop(0)
        else:
            obj = self.factory()
        obj.active = True
        self.active.append(obj)
        return obj

    def release(self, obj):
        obj.active = False
        self.free.append(obj)

    def sweep(self):
        """Move every object whose `active` became False back to the free list."""
        still = []
        for obj in self.active:
            if obj.active:
                still.append(obj)
            else:
                self.free.append(obj)
        self.active = still

    def clear(self):
        for obj in self.active:
            obj.active = False
            self.free.append(obj)
        self.active = []

    def __len__(self):
        return len(self.active)

    def __iter__(self):
        return iter(self.active)

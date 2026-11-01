"""WaveSystem: the build phase -> wave phase loop and the spawn queue.

Waves come from the level JSON:
    {"groups": [{"enemy": "skitter", "count": 8, "interval": 1.0, "delay": 0}],
     "boss": null}
Every enemy of the wave gets a spawn time; they go into a heap (heapq) ordered
by that time, and each update pops whatever is due.

Endless mode passes a generator instead of a fixed list: waves are made on
demand, total_waves is None and the run only ends when the Core falls.
"""
import heapq

BUILD, WAVE, DONE = "build", "wave", "done"


class WaveSystem:
    def __init__(self, events, waves, build_time, generator=None):
        self.events = events
        self.waves = waves
        self.generator = generator     # EndlessWaveGenerator, or None for a campaign level
        self.build_time = build_time
        self.phase = BUILD
        self.countdown = build_time
        self.wave_number = 0       # 1-based number of the current/last wave
        self.wave_time = 0.0
        self.queue = []
        self.spawned_this_wave = 0
        self.total_this_wave = 0

    @property
    def endless(self):
        return self.generator is not None

    @property
    def total_waves(self):
        return None if self.endless else len(self.waves)

    def wave_data(self, number):
        """The wave dict for a 1-based wave number, or None past the last wave."""
        if self.endless:
            return self.generator.wave(number)
        if 1 <= number <= len(self.waves):
            return self.waves[number - 1]
        return None

    @property
    def next_wave(self):
        """What the next wave will send (for the HUD preview)."""
        return self.wave_data(self.wave_number + 1)

    @property
    def current_wave(self):
        return self.wave_data(self.wave_number) if self.wave_number else None

    @property
    def remaining_in_queue(self):
        return len(self.queue)

    def build_queue(self, wave):
        heap = []
        seq = 0
        last = 0.0
        for group in wave.get("groups", []):
            t = float(group.get("delay", 0.0))
            for _ in range(int(group["count"])):
                heapq.heappush(heap, (t, seq, group["enemy"], group.get("lane", 0)))
                seq += 1
                last = max(last, t)
                t += float(group.get("interval", 1.0))
        if wave.get("boss"):
            heapq.heappush(heap, (last + 3.0, seq, wave["boss"], 0))
        return heap

    def start_next_wave(self):
        """Space bar or the build countdown reaching 0."""
        if self.phase != BUILD or self.next_wave is None:
            return False
        self.wave_number += 1
        wave = self.wave_data(self.wave_number)
        self.queue = self.build_queue(wave)
        self.total_this_wave = len(self.queue)
        self.spawned_this_wave = 0
        self.wave_time = 0.0
        self.phase = WAVE
        self.events.publish("wave_started", number=self.wave_number, total=self.total_waves,
                            mods=wave.get("mods"), mutator=wave.get("mutator"))
        return True

    def on_update(self, dt, enemies_alive):
        if self.phase == BUILD:
            self.countdown -= dt
            if self.countdown <= 0:
                self.start_next_wave()
        elif self.phase == WAVE:
            self.wave_time += dt
            spawned = False
            while self.queue and self.queue[0][0] <= self.wave_time:
                _, _, enemy_type, lane = heapq.heappop(self.queue)
                self.spawned_this_wave += 1
                spawned = True
                self.events.publish("spawn_enemy", enemy_type=enemy_type,
                                    wave=self.wave_number, lane=lane)
            # enemies_alive was counted before this frame's spawns, so if anything just
            # spawned (e.g. the boss, after the rest of the wave is dead) wait a frame.
            if not spawned and not self.queue and enemies_alive == 0:
                self.events.publish("wave_cleared", number=self.wave_number)
                if not self.endless and self.wave_number >= self.total_waves:
                    self.phase = DONE
                    self.events.publish("all_waves_cleared")
                else:
                    self.phase = BUILD
                    self.countdown = self.build_time

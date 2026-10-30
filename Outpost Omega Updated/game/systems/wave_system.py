"""WaveSystem: the build phase -> wave phase loop and the spawn queue.

Waves come from the level JSON:
    {"groups": [{"enemy": "skitter", "count": 8, "interval": 1.0, "delay": 0}],
     "boss": null}
Every enemy of the wave gets a spawn time; they go into a heap (heapq) ordered
by that time, and each update pops whatever is due.
"""
import heapq

BUILD, WAVE, DONE = "build", "wave", "done"


class WaveSystem:
    def __init__(self, events, waves, build_time):
        self.events = events
        self.waves = waves
        self.build_time = build_time
        self.phase = BUILD
        self.countdown = build_time
        self.wave_number = 0       # 1-based number of the current/last wave
        self.wave_time = 0.0
        self.queue = []
        self.spawned_this_wave = 0
        self.total_this_wave = 0

    @property
    def total_waves(self):
        return len(self.waves)

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
        if self.phase != BUILD or self.wave_number >= self.total_waves:
            return False
        self.wave_number += 1
        self.queue = self.build_queue(self.waves[self.wave_number - 1])
        self.total_this_wave = len(self.queue)
        self.spawned_this_wave = 0
        self.wave_time = 0.0
        self.phase = WAVE
        self.events.publish("wave_started", number=self.wave_number, total=self.total_waves)
        return True

    def on_update(self, dt, enemies_alive):
        if self.phase == BUILD:
            self.countdown -= dt
            if self.countdown <= 0:
                self.start_next_wave()
        elif self.phase == WAVE:
            self.wave_time += dt
            while self.queue and self.queue[0][0] <= self.wave_time:
                _, _, enemy_type, lane = heapq.heappop(self.queue)
                self.spawned_this_wave += 1
                self.events.publish("spawn_enemy", enemy_type=enemy_type,
                                    wave=self.wave_number, lane=lane)
            if not self.queue and enemies_alive == 0:
                self.events.publish("wave_cleared", number=self.wave_number)
                if self.wave_number >= self.total_waves:
                    self.phase = DONE
                    self.events.publish("all_waves_cleared")
                else:
                    self.phase = BUILD
                    self.countdown = self.build_time

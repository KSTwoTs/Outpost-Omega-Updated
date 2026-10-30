"""EndlessWaveGenerator: builds waves forever from a growing threat budget.

Every enemy in enemies.json has a "threat" cost and an "unlock_wave". Wave n
gets a budget of budget_base * budget_growth^(n-1) and spends it on 1-3 groups
of unlocked enemies. Every Nth wave rolls a mutator, every 10th adds a boss.

The output has the same shape as a level file's wave, so WaveSystem.build_queue
works unchanged:
    {"groups": [{"enemy", "count", "interval", "delay", "lane"}], "boss": ...,
     "mods": {...}, "mutator": "swarm" | None}

Waves are generated once and cached, so the HUD preview always matches what
actually spawns. Kept free of pygame so it can be unit-tested.
"""
import random


class EndlessWaveGenerator:
    def __init__(self, config, enemy_data, lanes=1, seed=None):
        self.cfg = config
        self.enemies = enemy_data
        self.lanes = max(1, lanes)
        self.rng = random.Random(seed)
        self.cache = {}
        self.boss_count = 0

    # ---- public ------------------------------------------------------------
    def wave(self, n):
        """Wave n (1-based). Generated in order so the RNG stays reproducible."""
        for i in range(len(self.cache) + 1, n + 1):
            self.cache[i] = self._generate(i)
        return self.cache[n]

    def budget(self, n):
        return self.cfg["budget_base"] * self.cfg["budget_growth"] ** (n - 1)

    def hp_scale(self, n):
        """Extra compounding HP on top of the base game's linear wave scaling."""
        start = self.cfg.get("hp_scale_after_wave", 10)
        return (1 + self.cfg.get("hp_growth", 0.05)) ** max(0, n - start)

    def elite_chance(self, n):
        el = self.cfg.get("elites", {})
        if n < el.get("start_wave", 12):
            return 0.0
        return min(el.get("max_chance", 0.35),
                   el.get("chance_per_wave", 0.015) * (n - el["start_wave"] + 1))

    # ---- generation ----------------------------------------------------------
    def unlocked(self, n):
        return {k: d for k, d in self.enemies.items()
                if d.get("enabled", True) and d.get("threat", 0) > 0
                and d.get("unlock_wave", 1) <= n}

    def _pick_mutator(self, n):
        every = self.cfg.get("mutator_every", 5)
        if not every or n % every:
            return None
        options = list(self.cfg.get("mutators", {}))
        if "glider" not in self.unlocked(n) and "air_raid" in options:
            options.remove("air_raid")
        return self.rng.choice(options) if options else None

    def _pick_enemy(self, pool, n):
        # Early waves favor cheap enemies, later waves favor expensive ones.
        bias = n / 15.0 - 0.5
        kinds = list(pool)
        base = self.cfg.get("enemy_weights", {})
        weights = [base.get(k, 1.0) * pool[k]["threat"] ** bias for k in kinds]
        return self.rng.choices(kinds, weights)[0]

    def _generate(self, n):
        mutator = self._pick_mutator(n)
        mut = self.cfg.get("mutators", {}).get(mutator, {})
        budget = self.budget(n) * mut.get("budget_mult", 1.0)
        pool = self.unlocked(n)

        max_groups = min(self.cfg.get("max_groups", 3), 1 + n // 4)
        group_count = self.rng.randint(1, max_groups)
        shares = [self.rng.uniform(0.7, 1.3) for _ in range(group_count)]
        total = sum(shares)

        counts = {}   # (enemy, lane) -> count, so duplicate picks merge
        order = []
        for share in shares:
            kind = self._pick_enemy(pool, n)
            count = max(1, round(budget * share / total / pool[kind]["threat"]))
            key = (kind, self.rng.randrange(self.lanes))
            if key not in counts:
                order.append(key)
                counts[key] = 0
            counts[key] += count

        share = mut.get("air_share", 0.0)
        if share and "glider" in self.enemies:
            for key in list(order):
                kind, lane = key
                if self.enemies[kind].get("flying"):
                    continue
                moved = int(counts[key] * share)
                if moved <= 0:
                    continue
                counts[key] -= moved
                threat = moved * self.enemies[kind]["threat"]
                gkey = ("glider", lane)
                if gkey not in counts:
                    order.append(gkey)
                    counts[gkey] = 0
                counts[gkey] += max(1, round(threat / self.enemies["glider"]["threat"]))

        groups, delay = [], 0.0
        length = self.cfg.get("wave_length", 20.0)
        lo, hi = self.cfg.get("min_interval", 0.25), self.cfg.get("max_interval", 1.2)
        for kind, lane in order:
            count = counts[(kind, lane)]
            if count <= 0:
                continue
            interval = round(max(lo, min(hi, length / count)), 2)
            groups.append({"enemy": kind, "count": count, "interval": interval,
                           "delay": round(delay, 1), "lane": lane})
            delay += self.rng.uniform(3.0, 6.0)

        boss = None
        mods = {
            "hp_mult": self.hp_scale(n) * mut.get("hp_mult", 1.0),
            "speed_mult": mut.get("speed_mult", 1.0),
            "armor_add": mut.get("armor_add", 0),
            "tower_range_mult": mut.get("tower_range_mult", 1.0),
            "elite_chance": self.elite_chance(n),
            "boss_hp_mult": 1.0,
        }
        every = self.cfg.get("boss_every", 10)
        if every and n % every == 0 and self.cfg.get("boss") in self.enemies:
            self.boss_count += 1
            rotation = [b for b in self.cfg.get("bosses", [self.cfg["boss"]]) if b in self.enemies]
            boss = rotation[(self.boss_count - 1) % len(rotation)] if rotation else self.cfg["boss"]
            mods["boss_hp_mult"] = 1 + self.cfg.get("boss_hp_step", 0.5) * (self.boss_count - 1)

        return {"groups": groups, "boss": boss, "mods": mods, "mutator": mutator}


def summarize(wave, enemy_data):
    """[(name, count)] for the HUD preview, biggest groups first."""
    totals = {}
    for g in wave.get("groups", []):
        totals[g["enemy"]] = totals.get(g["enemy"], 0) + g["count"]
    rows = sorted(totals.items(), key=lambda kv: -kv[1])
    out = [(enemy_data.get(k, {}).get("name", k), c) for k, c in rows]
    if wave.get("boss"):
        out.append((enemy_data.get(wave["boss"], {}).get("name", wave["boss"]), 1))
    return out

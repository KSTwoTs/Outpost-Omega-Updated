"""Siege Run: the roguelike layer. Kept free of pygame so it can be unit-tested.

A run is 3 acts. Each act is a branching map of floors (like Slay the Spire):
Combat, Elite, Supply Cache, Event, and a Boss at the end. Combat nodes reuse
the endless wave generator at a depth set by act and floor, so later floors
are harder.

Augments, relics, events and the Command Tech tree all share one effect
format, e.g. {"type": "tower_stat", "tower": "pulse", "stat": "damage", "mult": 1.3}.
Modifiers folds a list of effects into the numbers PlayScene needs.

Effect types:
    tower_stat       tower ("*" or kind), stat, mult and/or add   (patches towers.json tiers)
    tower_cost       tower, mult                                  (build + upgrade cost)
    core_max         add and/or mult
    start_energy     add
    start_scrap      add (tech only, applied when the run starts)
    kill_reward      mult on Energy per kill
    orbital_cooldown mult        orbital_damage  mult        blaster_damage  mult
    drop_chance      add, or set
    sell_refund      set
    interest         rate, cap   (after each wave: +rate x unspent Energy, at most cap)
    crystal_every    kills       (every Nth kill drops an Energy Crystal)
    node_heal        add         (Core HP healed after each sector)
    scrap            mult        draft_choices   add        extra_tower_card  add
    slowed_damage    mult        (damage taken by slowed enemies)
"""
import copy
import random

from .endless import EndlessWaveGenerator


# ---- effects --------------------------------------------------------------------
class Modifiers:
    def __init__(self, effects):
        self.effects = list(effects)

    def of(self, kind):
        return [e for e in self.effects if e.get("type") == kind]

    def mult(self, kind):
        out = 1.0
        for e in self.of(kind):
            out *= e.get("mult", 1.0)
        return out

    def add(self, kind):
        return sum(e.get("add", 0) for e in self.of(kind))

    def set(self, kind, default):
        found = [e["set"] for e in self.of(kind) if "set" in e]
        return found[-1] if found else default

    # ---- derived numbers ----------------------------------------------------
    def interest(self):
        effects = self.of("interest")
        return (sum(e.get("rate", 0) for e in effects), sum(e.get("cap", 0) for e in effects))

    def crystal_every(self):
        kills = [e["kills"] for e in self.of("crystal_every") if e.get("kills")]
        return min(kills) if kills else 0

    def drop_chance(self, base):
        return max(0.0, min(0.9, self.set("drop_chance", base + self.add("drop_chance"))))

    # ---- data patching ------------------------------------------------------
    def tower_data(self, base, owned):
        """A copy of towers.json with run upgrades baked in. Towers not owned are disabled
        (the HUD already shows those as LOCKED)."""
        data = copy.deepcopy(base)
        for kind, d in data.items():
            d["enabled"] = d.get("enabled", True) and kind in owned
            cost_mult = 1.0
            for e in self.of("tower_cost"):
                if e.get("tower", "*") in ("*", kind):
                    cost_mult *= e.get("mult", 1.0)
            d["cost"] = max(1, round(d["cost"] * cost_mult))
            stat_effects = [e for e in self.of("tower_stat") if e.get("tower", "*") in ("*", kind)]
            for br in d.get("branches", []):
                br["cost"] = max(1, round(br["cost"] * cost_mult))
            for tier in d["tiers"] + [br["stats"] for br in d.get("branches", [])]:
                if tier.get("upgrade_cost"):
                    tier["upgrade_cost"] = max(1, round(tier["upgrade_cost"] * cost_mult))
                for e in stat_effects:
                    stat = e["stat"]
                    if stat not in tier:
                        continue
                    tier[stat] = tier[stat] * e.get("mult", 1.0) + e.get("add", 0)
                if "damage" in tier:
                    tier["damage"] = round(tier["damage"])
                if "chain" in tier:
                    tier["chain"] = int(round(tier["chain"]))
                if "slow" in tier:
                    tier["slow"] = min(0.8, tier["slow"])
        return data

    def items_data(self, base):
        data = copy.deepcopy(base)
        data["drop_chance"] = self.drop_chance(base.get("drop_chance", 0.15))
        return data


def expand_tech(tech_data, ranks):
    """Tech ranks -> a flat effect list (each rank applies the effects once more)."""
    effects = []
    for tid, rank in ranks.items():
        node = tech_data.get(tid)
        if node:
            for _ in range(min(rank, len(node["costs"]))):
                effects.extend(node["effects"])
    return effects


# ---- the run -------------------------------------------------------------------
class RunState:
    BASE_CORE = 100

    def __init__(self, cfg, tower_data, tech_effects=(), seed=None):
        self.cfg = cfg
        self.tower_data = tower_data
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.tech_effects = list(tech_effects)
        self.augments = []
        self.relics = []
        self.event_effects = []         # permanent bonuses from events (e.g. Core max HP)
        self.seen_events = set()

        tech = Modifiers(self.tech_effects)
        self.towers = list(cfg.get("start_towers", ["pulse"]))
        extra = cfg.get("random_start_towers", 1) + int(tech.add("extra_tower_card"))
        for _ in range(extra):   # starting picks only come from towers that attack
            self.unlock_random_tower(cfg.get("start_pool"))
        self.scrap = cfg.get("start_scrap", 0) + int(tech.add("start_scrap"))

        self.act = 1
        self.floor = -1                 # last floor cleared this act
        self.node = None                # node being played / visited
        self.position = None            # last node completed (the map path continues from here)
        self.visited = set()            # ids of completed nodes (drawn as the path taken)
        self.map = self.generate_map()
        self.core_hp = self.core_max

        self.nodes_cleared = 0
        self.elites = 0
        self.bosses = 0
        self.kills = 0
        self.score = 0
        self.over = False
        self.victory = False
        self.salvage_earned = 0
        self.shop = None
        self.commander = None           # Commander class id, set by GameManager.start_run
        self.cmd_level, self.cmd_xp, self.cmd_perks = 1, 0, []   # Vance's level carries over

    # ---- saving -----------------------------------------------------------------
    SAVED = ("seed", "tech_effects", "augments", "relics", "event_effects", "towers", "scrap",
             "act", "floor", "map", "core_hp", "nodes_cleared", "elites", "bosses", "kills",
             "score", "shop", "commander", "cmd_level", "cmd_xp", "cmd_perks")

    def to_dict(self):
        """Everything needed to resume the run (JSON-safe), kept in save.json."""
        data = {k: getattr(self, k, None) for k in self.SAVED}
        version, state, gauss = self.rng.getstate()
        data["rng"] = [version, list(state), gauss]
        data["seen_events"] = sorted(self.seen_events)
        data["visited"] = sorted(self.visited)
        data["node_id"] = self.node["id"] if self.node else None
        data["position_id"] = self.position["id"] if self.position else None
        return data

    @classmethod
    def from_dict(cls, data, cfg, tower_data):
        run = cls.__new__(cls)
        run.cfg = cfg
        run.tower_data = tower_data
        for k in cls.SAVED:
            setattr(run, k, data.get(k))
        run.rng = random.Random()
        version, state, gauss = data["rng"]
        run.rng.setstate((version, tuple(state), gauss))
        run.seen_events = set(data.get("seen_events", []))
        run.visited = set(data.get("visited", []))
        run.node = run.node_by_id(data["node_id"]) if data.get("node_id") else None
        run.position = run.node_by_id(data["position_id"]) if data.get("position_id") else None
        run.over = False
        run.victory = False
        run.salvage_earned = 0
        return run

    # ---- effects ------------------------------------------------------------
    @property
    def effects(self):
        out = list(self.tech_effects) + list(self.event_effects)
        for a in self.augments:
            out += self.cfg["augments"][a]["effects"]
        for r in self.relics:
            out += self.cfg["relics"][r]["effects"]
        return out

    @property
    def mods(self):
        return Modifiers(self.effects)

    @property
    def core_max(self):
        m = self.mods
        return max(10, int((self.BASE_CORE + m.add("core_max")) * m.mult("core_max")))

    def _with_core_change(self, change):
        """Apply a change, then heal by any max-HP gained and clamp to the new max."""
        before = self.core_max
        change()
        after = self.core_max
        if after > before:
            self.core_hp += after - before
        self.core_hp = min(self.core_hp, after)

    def add_augment(self, aid):
        self._with_core_change(lambda: self.augments.append(aid))

    def add_relic(self, rid):
        self._with_core_change(lambda: self.relics.append(rid))

    def add_event_effect(self, effect):
        self._with_core_change(lambda: self.event_effects.append(effect))

    def heal(self, amount):
        self.core_hp = min(self.core_max, self.core_hp + amount)

    def unowned_towers(self):
        return [k for k, d in self.tower_data.items() if d.get("enabled", True) and k not in self.towers]

    def unlock_random_tower(self, pool=None):
        options = [k for k in self.unowned_towers() if pool is None or k in pool]
        if not options:
            return None
        kind = self.rng.choice(options)
        self.towers.append(kind)
        return kind

    def gain_scrap(self, amount):
        amount = round(amount * self.mods.mult("scrap"))
        self.scrap += amount
        return amount

    # ---- map ----------------------------------------------------------------
    def _pick_type(self, floor, floors):
        if floor == 0:
            return "combat"
        if floor == floors - 1:
            return "boss"
        if floor == floors - 2:
            return self.rng.choice(["cache", "event"])
        weights = dict(self.cfg["node_weights"])
        if floor < self.cfg.get("elite_min_floor", 2):
            weights.pop("elite", None)
        kinds = list(weights)
        return self.rng.choices(kinds, [weights[k] for k in kinds])[0]

    def _pick_sector(self):
        sector = self.rng.choice(self.cfg["sectors"])
        if sector == "procedural":   # a brand-new map, fixed by the run's seed
            sector = f"proc_{self.rng.randrange(1, 10 ** 6)}"
        return sector

    def generate_map(self):
        floors = self.cfg["floors_per_act"]
        lo, hi = self.cfg["floor_width"]
        layers = []
        for f in range(floors):
            width = 1 if f == floors - 1 else (3 if f == 0 else self.rng.randint(lo, hi))
            layers.append([{"id": f"{self.act}-{f}-{i}", "floor": f, "index": i,
                            "x": (i + 0.5) / width, "type": self._pick_type(f, floors),
                            "sector": self._pick_sector(), "next": []}
                           for i in range(width)])
        for f in range(floors - 1):
            here, nxt = layers[f], layers[f + 1]
            for a in here:
                order = sorted(nxt, key=lambda b: abs(b["x"] - a["x"]))
                a["next"].append(order[0]["id"])
                if len(order) > 1 and self.rng.random() < 0.45:
                    a["next"].append(order[1]["id"])
            for b in nxt:   # every node must be reachable
                if not any(b["id"] in a["next"] for a in here):
                    closest = min(here, key=lambda a: abs(b["x"] - a["x"]))
                    closest["next"].append(b["id"])
        return layers

    def node_by_id(self, nid):
        for layer in self.map:
            for n in layer:
                if n["id"] == nid:
                    return n
        return None

    def available_nodes(self):
        if self.floor < 0:
            return list(self.map[0])
        if self.position is None:
            return []
        return [self.node_by_id(nid) for nid in self.position["next"]]

    def enter(self, node):
        self.node = node
        if node["type"] == "cache":
            self.shop = self.make_shop()
        return node["type"]

    # ---- combat nodes ---------------------------------------------------------
    def wave_start(self, node):
        depth = self.cfg["wave_depth"]
        return 1 + (self.act - 1) * depth["per_act"] + node["floor"] * depth["per_floor"]

    def node_waves(self, node, endless_cfg, enemy_data, lanes=1):
        kind = node["type"]
        count = self.cfg["waves_per_node"].get(kind, 3)
        start = self.wave_start(node)
        gen = EndlessWaveGenerator(endless_cfg, enemy_data, lanes=lanes,
                                   seed=self.seed * 31 + self.act * 101 + node["floor"] * 7 + node["index"])
        waves = []
        for i in range(count):
            w = copy.deepcopy(gen.wave(start + i))
            w["boss"] = None
            w["mods"]["boss_hp_mult"] = 1.0
            if kind == "elite":
                w["mods"]["elite_chance"] = max(w["mods"]["elite_chance"], self.cfg.get("elite_node_chance", 0.6))
            waves.append(w)
        if kind == "boss" and waves:
            bosses = self.cfg.get("bosses_by_act") or [self.cfg.get("boss", "hive_overseer")]
            waves[-1]["boss"] = bosses[min(self.act, len(bosses)) - 1]
            waves[-1]["mods"]["boss_hp_mult"] = 1 + self.cfg.get("boss_hp_per_act", 0.5) * (self.act - 1)
        return waves

    def complete_node(self, core_hp=None, kills=0, score=0):
        """A node is done (combat won, shop left, event resolved). Returns the reward summary."""
        node = self.node
        if core_hp is not None:
            self.core_hp = min(self.core_max, core_hp)
        self.kills += kills
        self.score += score
        self.nodes_cleared += 1
        self.floor = node["floor"]
        self.position = node
        self.visited.add(node["id"])
        reward = {"scrap": 0, "steps": [], "healed": 0, "node": node["type"]}
        spec = self.cfg["rewards"].get(node["type"])
        if spec:
            before = self.core_hp
            self.heal(self.mods.add("node_heal"))
            reward["scrap"] = self.gain_scrap(self.rng.randint(*spec["scrap"]))
            reward["steps"] = list(spec["steps"])
            if spec.get("heal"):
                self.heal(self.core_max * spec["heal"])
            reward["healed"] = round(self.core_hp - before)
        if node["type"] == "elite":
            self.elites += 1
        if node["type"] == "boss":
            self.bosses += 1
            if self.act >= self.cfg["acts"]:
                reward["steps"] = []
                self.finish(victory=True)
            else:
                self.act += 1
                self.floor = -1
                self.position = None
                self.node = None
                self.map = self.generate_map()
                reward["next_act"] = self.act
        self.shop = None
        return reward

    def fail(self, kills=0, score=0):
        self.kills += kills
        self.score += score
        self.core_hp = 0
        self.finish(victory=False)

    def finish(self, victory):
        if self.over:
            return
        self.over = True
        self.victory = victory
        s = self.cfg["salvage"]
        self.salvage_earned = (self.nodes_cleared * s["node"] + self.elites * s["elite"]
                               + self.bosses * s["boss"] + (s["victory"] if victory else 0))

    # ---- rewards --------------------------------------------------------------
    def augment_pool(self):
        return [aid for aid, a in self.cfg["augments"].items()
                if aid not in self.augments and (not a.get("requires") or a["requires"] in self.towers)]

    def relic_pool(self, cursed=None):
        return [rid for rid, r in self.cfg["relics"].items()
                if rid not in self.relics and (cursed is None or bool(r.get("cursed")) == cursed)]

    def draft_options(self):
        n = self.cfg.get("draft_choices", 3) + int(self.mods.add("draft_choices"))
        options = []
        if self.unowned_towers() and self.rng.random() < self.cfg.get("tower_card_chance", 0.4):
            options.append(("tower", self.rng.choice(self.unowned_towers())))
        pool = self.augment_pool()
        options += [("augment", a) for a in self.rng.sample(pool, min(n - len(options), len(pool)))]
        return options

    def relic_options(self, n):
        pool = self.relic_pool()
        return [("relic", r) for r in self.rng.sample(pool, min(n, len(pool)))]

    def take(self, kind, oid):
        if kind == "tower":
            if oid not in self.towers:
                self.towers.append(oid)
        elif kind == "augment":
            self.add_augment(oid)
        elif kind == "relic":
            self.add_relic(oid)

    def describe(self, kind, oid):
        """(name, description, cursed) for a card."""
        if kind == "tower":
            d = self.tower_data[oid]
            return d["name"], f"Unlock this tower. {d['description']}", False
        src = self.cfg["augments" if kind == "augment" else "relics"][oid]
        return src["name"], src["desc"], bool(src.get("cursed"))

    # ---- supply cache ------------------------------------------------------------
    def make_shop(self):
        s = self.cfg["shop"]
        offers = []
        towers = self.unowned_towers()
        for t in self.rng.sample(towers, min(s["towers"], len(towers))):
            offers.append({"kind": "tower", "id": t, "price": s["tower"], "sold": False})
        pool = self.augment_pool()
        for a in self.rng.sample(pool, min(s["augments"], len(pool))):
            offers.append({"kind": "augment", "id": a, "price": s["augment"], "sold": False})
        relics = self.relic_pool(cursed=False)
        for r in self.rng.sample(relics, min(s["relics"], len(relics))):
            offers.append({"kind": "relic", "id": r, "price": s["relic"], "sold": False})
        offers.append({"kind": "repair", "id": "repair", "price": s["repair"], "sold": False})
        return offers

    def buy(self, offer):
        if offer["sold"] or self.scrap < offer["price"]:
            return False
        if offer["kind"] == "repair":
            if self.core_hp >= self.core_max:
                return False
            self.heal(self.cfg["shop"]["repair_hp"])
        else:
            self.take(offer["kind"], offer["id"])
        self.scrap -= offer["price"]
        offer["sold"] = offer["kind"] != "repair"   # repairs can be bought again
        return True

    # ---- events --------------------------------------------------------------------
    def pick_event(self):
        events = self.cfg["events"]
        fresh = [e for e in events if e not in self.seen_events] or list(events)
        eid = self.rng.choice(fresh)
        self.seen_events.add(eid)
        return eid

    def can_afford(self, choice):
        cost = choice.get("cost", {})
        return self.scrap >= cost.get("scrap", 0) and self.core_hp > cost.get("core_hp", 0)

    def resolve_choice(self, choice):
        """Pay the cost, apply the gains, return a list of result lines."""
        cost, gain, lines = choice.get("cost", {}), choice.get("gain", {}), []
        self.scrap -= cost.get("scrap", 0)
        self.core_hp -= cost.get("core_hp", 0)
        if gain.get("scrap"):
            lines.append(f"+{self.gain_scrap(gain['scrap'])} Scrap")
        if gain.get("core_hp"):
            before = self.core_hp
            self.heal(gain["core_hp"])
            lines.append(f"Core healed {round(self.core_hp - before)} HP")
        if gain.get("core_max"):
            self.add_event_effect({"type": "core_max", "add": gain["core_max"]})
            lines.append(f"Core max HP +{gain['core_max']}")
        for _ in range(gain.get("augment", 0)):
            pool = self.augment_pool()
            if pool:
                a = self.rng.choice(pool)
                self.add_augment(a)
                lines.append(f"Augment: {self.cfg['augments'][a]['name']}")
        for key, cursed in (("relic", False), ("curse", True)):
            for _ in range(gain.get(key, 0)):
                pool = self.relic_pool(cursed=cursed)
                if pool:
                    r = self.rng.choice(pool)
                    self.add_relic(r)
                    lines.append(f"Relic: {self.cfg['relics'][r]['name']}")
        for _ in range(gain.get("tower_card", 0)):
            t = self.unlock_random_tower()
            if t:
                lines.append(f"Tower unlocked: {self.tower_data[t]['name']}")
            else:
                lines.append(f"+{self.gain_scrap(40)} Scrap (every tower already unlocked)")
        return lines or ["Nothing happens."]

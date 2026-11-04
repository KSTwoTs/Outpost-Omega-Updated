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
    cmd_hp, cmd_speed, repair_speed   mult (Commander)
    build_time       add         (seconds of build phase between waves, min 3)
    wave_energy      add         (Energy after every wave)
    wave_heal        add         (Core HP after every wave)
    salvage          mult        (Salvage when the run ends)
    shop_discount    mult        (Supply Cache prices)
    relic_choices    add         (extra relic cards to choose from)
    rarity_luck      add         (boosts the odds of Rare / Epic / Legendary rolls)
    tower_hp         mult        (tower HP, Barricade HP included)
    upgrade_discount mult        (tier 2/3 upgrade costs)
    branch_discount  mult        (tier-4 branch costs)
    boss_damage      mult        elite_damage  mult       (damage dealt to bosses / elites)
    crit_chance      add         crit_damage   add        (tower crits; base crit is x2)
    execute          set         (tower hits kill non-boss aliens below this HP fraction)
    core_shield      add         (free Core shield every wave)
    vet_bonus        mult        (veterancy damage per rank)
    orbital_radius   mult        blaster_range mult       respawn_time mult
    cmd_armor        mult        (damage the Commander takes)

Endless acts: after the final act's boss the player picks CLAIM VICTORY (run ends
as a win) or PUSH ON. Pushing on banks the win and keeps generating acts until the
Core falls.

Rarity: every augment and relic has a "rarity" (common / rare / epic / legendary;
cursed relics are their own pool). Drafts, relic picks, the shop and events roll a
tier from cfg["rarity"]["odds"][source], shifted toward rarer tiers each act and by
rarity_luck, then pick a card of that tier (falling back to the nearest tier).
"""
import copy
import random

from .endless import EndlessWaveGenerator


# ---- effects --------------------------------------------------------------------
def hero_allowed(hero, mode):
    """Commanders with a "modes" list (the newer heroes) only appear in those modes:
    "campaign", "endless" or "run"."""
    modes = hero.get("modes")
    return not modes or mode in modes


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
        hp_mult = self.mult("tower_hp")
        up_mult = self.mult("upgrade_discount")
        branch_mult = self.mult("branch_discount")
        for kind, d in data.items():
            d["enabled"] = d.get("enabled", True) and kind in owned
            cost_mult = 1.0
            for e in self.of("tower_cost"):
                if e.get("tower", "*") in ("*", kind):
                    cost_mult *= e.get("mult", 1.0)
            d["cost"] = max(1, round(d["cost"] * cost_mult))
            d["hp"] = round(d.get("hp", 100) * hp_mult)
            stat_effects = [e for e in self.of("tower_stat") if e.get("tower", "*") in ("*", kind)]
            for br in d.get("branches", []):
                br["cost"] = max(1, round(br["cost"] * cost_mult * branch_mult))
            for tier in d["tiers"] + [br["stats"] for br in d.get("branches", [])]:
                if tier.get("upgrade_cost"):
                    tier["upgrade_cost"] = max(1, round(tier["upgrade_cost"] * cost_mult * up_mult))
                if "max_hp" in tier:
                    tier["max_hp"] = round(tier["max_hp"] * hp_mult)
                for e in stat_effects:
                    stat = e["stat"]
                    if stat not in tier:
                        continue
                    tier[stat] = tier[stat] * e.get("mult", 1.0) + e.get("add", 0)
                if "damage" in tier:
                    tier["damage"] = round(tier["damage"])
                for int_stat in ("chain", "drones", "max_mines", "beams", "income", "burst", "targets", "splits"):
                    if int_stat in tier:
                        tier[int_stat] = int(round(tier[int_stat]))
                if "slow" in tier:
                    tier["slow"] = min(0.8, tier["slow"])
            if "max_hp" in d["tiers"][0]:   # Barricades start at their tier-1 HP
                d["hp"] = round(d["tiers"][0]["max_hp"])
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
        # Phase 5: an alien faction for the whole run, an act-wide event, the debt merchant
        factions = list(cfg.get("factions", {}))
        self.faction = self.rng.choice(factions) if factions else None
        self.act_event = None
        self.debt = None                # [repay, nodes_left]
        self.messages = []              # one-shot lines for the run map (debt collected, etc.)
        self.roll_act_event()

        self.nodes_cleared = 0
        self.elites = 0
        self.bosses = 0
        self.kills = 0
        self.score = 0
        self.over = False
        self.victory = False
        self.endless = False            # True once the player pushes on past the final act
        self.salvage_earned = 0
        self.shop = None
        self.commander = None           # Commander class id, set by GameManager.start_run
        self.cmd_level, self.cmd_xp, self.cmd_perks = 1, 0, []   # Vance's level carries over

    # ---- saving -----------------------------------------------------------------
    SAVED = ("seed", "tech_effects", "augments", "relics", "event_effects", "towers", "scrap",
             "act", "floor", "map", "core_hp", "nodes_cleared", "elites", "bosses", "kills",
             "score", "shop", "commander", "cmd_level", "cmd_xp", "cmd_perks", "endless", "chips", "gear",
             "faction", "act_event", "debt", "messages", "research", "ascension", "pet")

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
        run.endless = bool(run.endless)
        run.messages = run.messages or []
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
        for sid in self.complete_sets():
            out += self.cfg["relic_sets"][sid]["effects"]
        ev = getattr(self, "act_event", None)
        if ev:
            out += self.cfg["act_events"][ev]["effects"]
        return out

    # ---- Phase 5 ------------------------------------------------------------------
    def set_counts(self):
        counts = {}
        for r in self.relics:
            sid = self.cfg["relics"][r].get("set")
            if sid:
                counts[sid] = counts.get(sid, 0) + 1
        return counts

    def complete_sets(self):
        sets = self.cfg.get("relic_sets", {})
        return [sid for sid, n in self.set_counts().items() if sid in sets and n >= sets[sid]["pieces"]]

    def roll_act_event(self):
        """Act 1 has a 50% chance of a run-wide event; every later act gets one."""
        events = list(self.cfg.get("act_events", {}))
        if not events:
            self.act_event = None
            return
        self.act_event = self.rng.choice(events) if (self.act > 1 or self.rng.random() < 0.5) else None

    def apply_hero_deck(self, hero):
        for kind in self.cfg.get("hero_decks", {}).get(hero, []):
            if kind in self.tower_data and kind not in self.towers:
                self.towers.append(kind)

    def faction_cfg(self, endless_cfg):
        """endless.json with this run's faction weights folded in."""
        f = self.cfg.get("factions", {}).get(getattr(self, "faction", None))
        if not f:
            return endless_cfg
        cfg = copy.deepcopy(endless_cfg)
        w = cfg["enemy_weights"]
        for kind, mult in f["weights"].items():
            w[kind] = w.get(kind, 0.5) * mult
        return cfg

    def special_event(self, kind):
        """Rest / Forge / Gamble nodes reuse EventScene with generated choices."""
        cfg = self.cfg
        if kind == "rest":
            pct = int(cfg.get("rest_heal", 0.4) * 100)
            choices = [{"label": "Repair the Core", "gain": {"heal_pct": cfg.get("rest_heal", 0.4)},
                        "sub": f"Heal {pct}% of the Core's max HP"}]
            if self.augments:
                aid = self.rng.choice(self.augments)
                name = cfg["augments"][aid]["name"]
                choices.append({"label": f"Train: {name}", "gain": {"empower": aid},
                                "sub": "Its effect stacks a second time"})
            return {"title": "Rest Stop", "text": "A quiet ridge with a working med-bay and a training rig. "
                    "There's time for one thing before the next push.", "choices": choices}
        if kind == "forge":
            choices = []
            if len(self.augments) >= 2:
                a, b = self.rng.sample(self.augments, 2)
                na, nb = cfg["augments"][a]["name"], cfg["augments"][b]["name"]
                choices.append({"label": f"Forge {na} + {nb}", "gain": {"forge": [a, b]},
                                "sub": "Lose both, gain one Epic or Legendary augment"})
            choices.append({"label": "Salvage the forge", "gain": {"scrap": 30}, "sub": "+30 Scrap"})
            return {"title": "Forge", "text": "An abandoned fabricator still hums. It could fuse two of your "
                    "augments into something stronger, if you can spare them.", "choices": choices}
        if kind == "gamble":
            g = cfg.get("gamble", {"cheap": 40, "rich": 80, "curse_chance": 0.25})
            return {"title": "Gambler's Den", "text": "A scavenger with a crate of sealed relics. "
                    "No refunds, no peeking.",
                    "choices": [{"label": f"Blind relic ({g['cheap']} Scrap)", "cost": {"scrap": g["cheap"]},
                                 "gain": {"gamble": "cheap"},
                                 "sub": f"Any relic. {int(g['curse_chance'] * 100)}% chance it's cursed"},
                                {"label": f"Sealed vault ({g['rich']} Scrap)", "cost": {"scrap": g["rich"]},
                                 "gain": {"gamble": "rich"}, "sub": "A Rare or better relic, never cursed"},
                                {"label": "Walk away", "sub": "Keep your Scrap"}]}
        return None

    def take_loan(self):
        d = self.cfg.get("debt", {})
        if self.debt:
            return False
        self.scrap += d.get("loan", 100)
        self.debt = [d.get("repay", 150), d.get("nodes", 2)]
        return True

    def tick_debt(self):
        if not self.debt:
            return
        self.debt[1] -= 1
        if self.debt[1] > 0:
            return
        owed = self.debt[0]
        self.debt = None
        if self.scrap >= owed:
            self.scrap -= owed
            self.messages.append(f"The debt merchant collected {owed} Scrap.")
        else:
            pen = self.cfg.get("debt", {}).get("penalty_hp", 25)
            paid = self.scrap
            self.scrap = 0
            self.core_hp = max(1, self.core_hp - pen)
            self.messages.append(f"Couldn't pay the debt merchant: took {paid} Scrap and {pen} Core HP.")

    def boss_relic_options(self):
        pool = [rid for rid, r in self.cfg["relics"].items()
                if r.get("rarity") == "boss" and rid not in self.relics]
        n = min(len(pool), self.cfg.get("boss_relic_choices", 3))
        return [("relic", r) for r in self.rng.sample(pool, n)]

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
            return self.rng.choice(["cache", "event", "rest"])
        weights = dict(self.cfg["node_weights"])
        if floor < self.cfg.get("elite_min_floor", 2):
            weights.pop("elite", None)
            weights.pop("forge", None)
        if floor < floors - 3:   # mini-bosses sit between the elites and the boss
            weights.pop("miniboss", None)
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

    def waves_for(self, kind):
        """How many waves a combat/elite/boss fight has in the current act."""
        cfg = self.cfg["waves_per_node"]
        if kind == "miniboss":
            kind = "elite"
        if "base" in cfg:
            return min(cfg.get("max", 999), cfg["base"] + cfg.get("per_act", 0) * (self.act - 1))
        return cfg.get(kind, 3)

    def node_waves(self, node, endless_cfg, enemy_data, lanes=1):
        kind = node["type"]
        count = self.waves_for(kind)
        start = self.wave_start(node)
        step = self.cfg["wave_depth"].get("per_wave", 1.0)
        gen = EndlessWaveGenerator(self.faction_cfg(endless_cfg), enemy_data, lanes=lanes,
                                   seed=self.seed * 31 + self.act * 101 + node["floor"] * 7 + node["index"])
        mult = self.cfg.get("enemy_count_mult", 1.0)
        min_interval = endless_cfg.get("min_interval", 0.25)
        waves = []
        prev_depth = None
        for i in range(count):
            depth = start + int(i * step)
            w = copy.deepcopy(gen.wave_at(depth, allow_mutator=depth != prev_depth))
            prev_depth = depth
            if mult != 1.0:
                for g in w["groups"]:
                    g["count"] = max(1, round(g["count"] * mult))
                    g["interval"] = round(max(min_interval, g["interval"] / mult ** 0.5), 2)
            w["boss"] = None
            w["mods"]["boss_hp_mult"] = 1.0
            if kind in ("elite", "miniboss"):
                w["mods"]["elite_chance"] = max(w["mods"]["elite_chance"], self.cfg.get("elite_node_chance", 0.6))
            waves.append(w)
        if kind == "miniboss" and waves:   # a Swarm Queenlet caps the fight
            waves[-1]["boss"] = "swarm_queenlet"
        if kind == "boss" and waves:
            waves[-1]["boss"] = self.boss_for_act()
            waves[-1]["mods"]["boss_hp_mult"] = 1 + self.cfg.get("boss_hp_per_act", 0.5) * (self.act - 1)
        return waves

    def boss_for_act(self):
        bosses = self.cfg.get("bosses_by_act") or [self.cfg.get("boss", "hive_overseer")]
        if self.act <= len(bosses):
            return bosses[self.act - 1]
        cycle = self.cfg.get("endless_bosses") or bosses   # endless acts rotate every boss
        return cycle[(self.act - 1) % len(cycle)]

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
        if node["type"] in ("elite", "miniboss"):
            self.elites += 1
        self.tick_debt()
        if node["type"] == "boss":
            self.bosses += 1
            if self.act == self.cfg["acts"] and not self.endless:
                reward["milestone"] = True   # RunRewardScene asks: claim victory or push on
            else:
                self.next_act()
                reward["next_act"] = self.act
        self.shop = None
        return reward

    def next_act(self):
        self.act += 1
        self.floor = -1
        self.position = None
        self.node = None
        self.map = self.generate_map()
        self.roll_act_event()

    def claim_victory(self):
        self.finish(victory=True)

    def push_on(self):
        """Keep going after the final boss. The win is banked (counted when the run ends)."""
        self.endless = True
        self.next_act()
        return self.act

    def fail(self, kills=0, score=0):
        self.kills += kills
        self.score += score
        self.core_hp = 0
        self.finish(victory=False)

    def finish(self, victory):
        if self.over:
            return
        self.over = True
        self.victory = victory or self.endless   # pushing on already beat the final boss
        s = self.cfg["salvage"]
        earned = (self.nodes_cleared * s["node"] + self.elites * s["elite"]
                  + self.bosses * s["boss"] + (s["victory"] if self.victory else 0))
        self.salvage_earned = round(earned * self.mods.mult("salvage"))

    # ---- rewards --------------------------------------------------------------
    def augment_pool(self):
        return [aid for aid, a in self.cfg["augments"].items()
                if aid not in self.augments and (not a.get("requires") or a["requires"] in self.towers)]

    def relic_pool(self, cursed=None):
        return [rid for rid, r in self.cfg["relics"].items()
                if rid not in self.relics and r.get("rarity") != "boss"
                and (cursed is None or bool(r.get("cursed")) == cursed)]

    # ---- rarity ---------------------------------------------------------------
    def rarity_of(self, kind, oid):
        """'common' / 'rare' / 'epic' / 'legendary' / 'cursed', or None for towers and repairs."""
        if kind not in ("augment", "relic"):
            return None
        src = self.cfg["augments" if kind == "augment" else "relics"][oid]
        return "cursed" if src.get("cursed") else src.get("rarity", "common")

    def rarity_weights(self, source):
        r = self.cfg.get("rarity", {})
        odds = r.get("odds", {})
        weights = dict(odds.get(source) or odds.get("combat") or {"common": 1})
        luck = self.mods.add("rarity_luck")
        bonus = r.get("act_bonus", {})
        for tier in weights:
            if tier != "common":
                weights[tier] *= (1 + bonus.get(tier, 0) * (self.act - 1)) * (1 + luck)
        return weights

    def roll_rarity(self, source):
        weights = self.rarity_weights(source)
        tiers = [t for t, w in weights.items() if w > 0]
        return self.rng.choices(tiers, [weights[t] for t in tiers])[0] if tiers else "common"

    def pick_by_rarity(self, pool, table, n, source):
        """Up to n distinct ids from pool, each rolled at a rarity tier for this source."""
        order = self.cfg.get("rarity", {}).get("order", ["common", "rare", "epic", "legendary"])
        left, out = list(pool), []
        while left and len(out) < n:
            tier = self.roll_rarity(source)
            i = order.index(tier) if tier in order else 0
            pick = None
            for t in [order[i]] + order[:i][::-1] + order[i + 1:]:   # rolled tier, then lower, then higher
                matches = [x for x in left if table[x].get("rarity", "common") == t]
                if matches:
                    pick = self.rng.choice(matches)
                    break
            if pick is None:
                pick = self.rng.choice(left)
            left.remove(pick)
            out.append(pick)
        return out

    def draft_options(self, source="combat"):
        n = self.cfg.get("draft_choices", 3) + int(self.mods.add("draft_choices"))
        options = []
        if self.unowned_towers() and self.rng.random() < self.cfg.get("tower_card_chance", 0.4):
            options.append(("tower", self.rng.choice(self.unowned_towers())))
        picks = self.pick_by_rarity(self.augment_pool(), self.cfg["augments"], n - len(options), source)
        return options + [("augment", a) for a in picks]

    def relic_options(self, n, source="elite"):
        n += int(self.mods.add("relic_choices"))
        picks = self.pick_by_rarity(self.relic_pool(cursed=False), self.cfg["relics"], n, source)
        return [("relic", r) for r in picks]

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
        tiers = self.cfg.get("rarity", {}).get("tiers", {})
        discount = self.mods.mult("shop_discount")

        def price(base, rarity=None):
            mult = tiers.get(rarity, {}).get("price", 1.0) if rarity else 1.0
            return max(5, int(5 * round(base * mult * discount / 5)))

        offers = []
        towers = self.unowned_towers()
        for t in self.rng.sample(towers, min(s["towers"], len(towers))):
            offers.append({"kind": "tower", "id": t, "price": price(s["tower"]), "sold": False})
        for a in self.pick_by_rarity(self.augment_pool(), self.cfg["augments"], s["augments"], "shop"):
            offers.append({"kind": "augment", "id": a, "sold": False,
                           "price": price(s["augment"], self.rarity_of("augment", a))})
        for r in self.pick_by_rarity(self.relic_pool(cursed=False), self.cfg["relics"], s["relics"], "shop"):
            offers.append({"kind": "relic", "id": r, "sold": False,
                           "price": price(s["relic"], self.rarity_of("relic", r))})
        offers.append({"kind": "repair", "id": "repair", "price": price(s["repair"]), "sold": False})
        if not self.debt and self.cfg.get("debt"):   # the debt merchant
            offers.append({"kind": "loan", "id": "loan", "price": 0, "sold": False})
        sellable = [r for r in self.relics if self.cfg["relics"][r].get("rarity") != "boss"]
        bm = self.cfg.get("black_market", {"common": 25, "rare": 45, "epic": 70, "legendary": 100, "cursed": 40})
        for r in self.rng.sample(sellable, min(1, len(sellable))):   # the black market buys a relic
            offers.append({"kind": "sell_relic", "id": r, "price": 0, "sold": False,
                           "value": bm.get(self.rarity_of("relic", r), 30)})
        return offers

    def buy(self, offer):
        if offer["sold"] or self.scrap < offer["price"]:
            return False
        if offer["kind"] == "loan":
            offer["sold"] = self.take_loan()
            return offer["sold"]
        if offer["kind"] == "sell_relic":
            if offer["id"] in self.relics:
                self.relics.remove(offer["id"])
                self.scrap += offer["value"]
            offer["sold"] = True
            return True
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
            for a in self.pick_by_rarity(self.augment_pool(), self.cfg["augments"], 1, "event"):
                self.add_augment(a)
                lines.append(f"{self.rarity_of('augment', a).title()} augment: {self.cfg['augments'][a]['name']}")
        for _ in range(gain.get("relic", 0)):
            for r in self.pick_by_rarity(self.relic_pool(cursed=False), self.cfg["relics"], 1, "event"):
                self.add_relic(r)
                lines.append(f"{self.rarity_of('relic', r).title()} relic: {self.cfg['relics'][r]['name']}")
        for _ in range(gain.get("curse", 0)):
            pool = self.relic_pool(cursed=True)
            if pool:
                r = self.rng.choice(pool)
                self.add_relic(r)
                lines.append(f"Cursed relic: {self.cfg['relics'][r]['name']}")
        if gain.get("heal_pct"):
            before = self.core_hp
            self.heal(self.core_max * gain["heal_pct"])
            lines.append(f"Core repaired {round(self.core_hp - before)} HP")
        if gain.get("empower"):
            self.add_augment(gain["empower"])
            lines.append(f"{self.cfg['augments'][gain['empower']]['name']} now stacks twice")
        if gain.get("forge"):
            for aid in gain["forge"]:
                if aid in self.augments:
                    self.augments.remove(aid)
            pool = [a for a in self.augment_pool() if self.cfg["augments"][a].get("rarity") in ("epic", "legendary")]
            if pool:
                aid = self.rng.choice(pool)
                self.add_augment(aid)
                lines.append(f"Forged: {self.rarity_of('augment', aid).title()} augment {self.cfg['augments'][aid]['name']}")
        if gain.get("gamble"):
            g = self.cfg.get("gamble", {})
            if gain["gamble"] == "cheap" and self.rng.random() < g.get("curse_chance", 0.25) and self.relic_pool(True):
                r = self.rng.choice(self.relic_pool(cursed=True))
                lines.append(f"Cursed! {self.cfg['relics'][r]['name']}")
            else:
                pool = self.relic_pool(cursed=False)
                if gain["gamble"] == "rich":
                    pool = [r for r in pool if self.cfg["relics"][r].get("rarity") in ("rare", "epic", "legendary")] or pool
                r = self.rng.choice(pool)
                lines.append(f"{self.rarity_of('relic', r).title()} relic: {self.cfg['relics'][r]['name']}")
            self.add_relic(r)
            for sid in self.complete_sets():
                lines.append(f"Set complete: {self.cfg['relic_sets'][sid]['name']}!")
        for _ in range(gain.get("tower_card", 0)):
            t = self.unlock_random_tower()
            if t:
                lines.append(f"Tower unlocked: {self.tower_data[t]['name']}")
            else:
                lines.append(f"+{self.gain_scrap(40)} Scrap (every tower already unlocked)")
        return lines or ["Nothing happens."]

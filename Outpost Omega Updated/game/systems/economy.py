"""Economy: Biomass, interest, insurance and the research queue (data/economy.json).

    Biomass   every kill drops some (Bio-Labs in range add their per_kill on top);
              it pays for research.
    Interest  Endless / Siege Run: +5% of unspent Energy after each wave (capped).
    Insurance pay before a wave; towers broken during it are rebuilt for free at the end
              and refund part of their value.
    Research  one project at a time, paid in Biomass, finishes after N cleared waves and
              then applies for the rest of the sector (the whole run in a Siege Run).
"""
from .. import settings as S


class Economy:
    def __init__(self, play, data):
        self.play = play
        self.data = data
        s = play.session
        if getattr(s, "biomass", None) is None:
            s.biomass = 0
        run = play.run
        self.done = list(getattr(run, "research", None) or []) if run else []
        if run is not None:
            run.research = self.done
        self.current = None          # [id, waves_left]
        self.insured = False
        self.broken_during_wave = set()
        ev = play.events
        ev.subscribe("enemy_killed", self.on_enemy_killed)
        ev.subscribe("wave_started", self.on_wave_started)
        ev.subscribe("wave_cleared", self.on_wave_cleared)
        for rid in self.done:
            self.apply(rid, announce=False)

    # ---- Biomass ---------------------------------------------------------------
    def on_enemy_killed(self, enemy, **_):
        if getattr(enemy, "zombie", False):
            return
        gain = self.data["biomass_boss"] if enemy.is_boss else self.data["biomass_per_kill"]
        self.play.session.biomass += gain

    def add_biomass(self, n, x=None, y=None):
        self.play.session.biomass += n
        if x is not None:
            self.play.effects.floating_text(x, y - 14, f"+{n} bio", (150, 230, 120), 16)

    # ---- insurance -----------------------------------------------------------------
    def toggle_insurance(self):
        play = self.play
        if play.waves.phase != "build":
            play.ui.toast("Insurance can only be bought between waves", S.TEXT_DIM)
            return
        cost = self.data["insurance_cost"]
        if self.insured:
            self.insured = False
            play.session.energy += cost
            play.ui.toast("Insurance cancelled (refunded)", S.TEXT_DIM)
        elif play.session.energy >= cost:
            self.insured = True
            play.session.energy -= cost
            play.ui.toast(f"Towers insured for the next wave ({cost} E)", S.CYAN)
        else:
            play.ui.toast("Not enough Energy", S.RED)

    def on_wave_started(self, **_):
        self.broken_during_wave = set()

    def note_broken(self, tower):
        self.broken_during_wave.add(tower)

    # ---- research ------------------------------------------------------------------
    def options(self):
        return [rid for rid in self.data["research"] if rid not in self.done
                and (self.current is None or self.current[0] != rid)]

    def start(self, rid):
        r = self.data["research"][rid]
        play = self.play
        if self.current is not None:
            play.ui.toast("Already researching something", S.TEXT_DIM)
            return False
        if play.session.biomass < r["cost"]:
            play.ui.toast(f"Needs {r['cost']} Biomass", S.RED)
            play.audio.play("error")
            return False
        play.session.biomass -= r["cost"]
        self.current = [rid, r["waves"]]
        play.ui.toast(f"Researching {r['name']} ({r['waves']} waves)", (150, 230, 120))
        return True

    def apply(self, rid, announce=True):
        r = self.data["research"][rid]
        play = self.play
        towers = play.towers
        src = towers.research_source
        mods = src.setdefault("mods", {})
        if r.get("range"):
            m = mods.setdefault("range", [1.0, 0.0])
            m[0] *= 1 + r["range"]
        if r.get("damage"):
            for k in ("damage", "dps"):
                m = mods.setdefault(k, [1.0, 0.0])
                m[0] *= 1 + r["damage"]
        if r.get("rate"):
            src["rate"] = src.get("rate", 0.0) + r["rate"]
        if r.get("tower_hp"):
            towers.research_hp *= r["tower_hp"]
            for t in towers.towers:
                t.health.max_hp *= r["tower_hp"]
                t.health.hp *= r["tower_hp"]
        if r.get("wave_energy"):
            play.wave_energy += r["wave_energy"]
        if r.get("orbital_cd"):
            play.player.orbital.duration *= r["orbital_cd"]
        if r.get("sell"):
            towers.sell_refund += r["sell"]
        towers.refresh_topology()
        if announce:
            play.ui.toast(f"Research complete: {r['name']} ({r['desc']})", (150, 230, 120))
            play.audio.play("upgrade")

    def on_wave_cleared(self, **_):
        play = self.play
        if play.endless or play.run is not None:   # interest
            gain = min(self.data["interest_cap"], int(play.session.energy * self.data["interest_rate"]))
            if gain > 0:
                play.session.energy += gain
                play.ui.toast(f"Interest: +{gain} Energy", S.ENERGY)
        if self.insured:
            refund = 0
            for t in self.broken_during_wave:
                if t in play.towers.towers:
                    t.health.hp = t.health.max_hp
                    t.corrupted = False
                    refund += int(t.spent * self.data["insurance_refund"])
            if refund or self.broken_during_wave:
                play.session.energy += refund
                play.ui.toast(f"Insurance paid out: {len(self.broken_during_wave)} towers rebuilt, +{refund} E",
                              S.CYAN)
            self.insured = False
        if self.current is not None:
            self.current[1] -= 1
            if self.current[1] <= 0:
                rid = self.current[0]
                self.current = None
                self.done.append(rid)
                self.apply(rid)

    @property
    def status(self):
        if self.current is None:
            return None
        r = self.data["research"][self.current[0]]
        return f"{r['name']}: {r['waves'] - self.current[1]}/{r['waves']}"

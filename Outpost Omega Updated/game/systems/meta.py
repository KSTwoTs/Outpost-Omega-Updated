"""Meta progression kept in save.json: profile stats, achievements, Commander skins,
tower mastery, the alien Codex and local leaderboards (data/meta.json).

Profile (save["profile"]):
    kills, towers_built, bosses, boss_kinds (list), best_wave, runs_won, fusions, veterans,
    perfect_wins, tamed, max_energy, sectors_won (list), killed_by {alien: n}, built {tower: n},
    codex {alien: kills}, mastery {tower: kills}, play_time
Achievements unlock automatically (MetaTracker.check) and some unlock a skin.
"""
import datetime

from .. import settings as S


def profile(save):
    p = save.setdefault("profile", {})
    for k, v in (("kills", 0), ("towers_built", 0), ("bosses", 0), ("boss_kinds", []), ("best_wave", 0),
                 ("runs_won", 0), ("ascension_won", 0), ("fusions", 0), ("veterans", 0), ("perfect_wins", 0),
                 ("tamed", 0), ("max_energy", 0), ("sectors_won", []), ("killed_by", {}), ("built", {}),
                 ("codex", {}), ("mastery", {}), ("play_time", 0.0), ("lights_out", 0), ("boss_rush", 0),
                 ("puzzles", []), ("hardcore_wave", 0)):
        p.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
    return p


def stat_value(p, stat):
    v = p.get(stat, 0)
    return len(v) if isinstance(v, (list, dict)) else v


def mastery_level(save, meta, kind):
    kills = profile(save)["mastery"].get(kind, 0)
    return sum(kills >= k for k in meta["mastery_levels"])


MASTERY_BONUS = (0.0, 0.03, 0.06, 0.10)


def unlocked_skins(save, meta):
    got = set(save.get("achievements", []))
    return ["classic"] + [a["skin"] for aid, a in meta["achievements"].items() if a.get("skin") and aid in got]


def record_score(save, key, score, wave=None):
    """Local leaderboard: top 10 scores per mode key."""
    board = save.setdefault("leaderboard", {}).setdefault(key, [])
    board.append({"score": int(score), "wave": wave, "date": datetime.date.today().isoformat()})
    board.sort(key=lambda r: -r["score"])
    del board[10:]


class MetaTracker:
    """Lives in a PlayScene; listens to its events and updates the profile."""

    def __init__(self, play):
        self.play = play
        game = play.game
        self.save = game.save
        self.meta = game.data["meta"]
        self.p = profile(self.save)
        self.core_damaged = False
        self.built_radar = False
        ev = play.events
        ev.subscribe("enemy_killed", self.on_kill)
        ev.subscribe("tower_built", self.on_built)
        ev.subscribe("enemy_reached_core", self.on_core_hit)
        ev.subscribe("meta_count", lambda stat, **_: self.count(stat))
        play.towers.on_tower_kill = self.on_tower_kill
        play.towers.mastery = {k: mastery_level(self.save, self.meta, k) for k in game.data["towers"]}
        play.towers.mastery_branches = bool(play.endless)
        self.dirty = 0.0

    def on_kill(self, enemy, **_):
        p = self.p
        if getattr(self.play, "reverse", None) is not None:
            return
        if getattr(enemy, "zombie", False) or getattr(enemy, "tame", False):
            return
        p["kills"] += 1
        p["codex"][enemy.kind] = p["codex"].get(enemy.kind, 0) + 1
        if enemy.is_boss:
            p["bosses"] += 1
            if enemy.kind not in p["boss_kinds"]:
                p["boss_kinds"].append(enemy.kind)

    def on_tower_kill(self, tower):
        kind = tower.kind if not tower.fusion else tower.fusion_parts[0]
        m = self.p["mastery"]
        before = mastery_level(self.save, self.meta, kind)
        m[kind] = m.get(kind, 0) + 1
        after = mastery_level(self.save, self.meta, kind)
        if after > before:
            self.play.towers.mastery[kind] = after
            self.play.ui.toast(f"{tower.name} mastery level {after}! (+{int(MASTERY_BONUS[after] * 100)}% damage)",
                               S.ENERGY)

    def on_built(self, tower, **_):
        self.p["towers_built"] += 1
        self.p["built"][tower.kind] = self.p["built"].get(tower.kind, 0) + 1
        if tower.kind == "radar":
            self.built_radar = True

    def on_core_hit(self, enemy, **_):
        self.core_damaged = True
        self.last_hitter = enemy.kind

    def count(self, stat, n=1):
        self.p[stat] = self.p.get(stat, 0) + n

    def raise_to(self, stat, value):
        self.p[stat] = max(self.p.get(stat, 0), value)

    def update(self, dt):
        self.p["play_time"] += dt
        self.raise_to("max_energy", self.play.session.energy)
        self.dirty += dt
        if self.dirty > 2.0:
            self.dirty = 0.0
            self.check()

    def finish(self, result):
        play = self.play
        p = self.p
        if result == "win":
            if not self.core_damaged:
                self.count("perfect_wins")
            if not play.endless and not play.run and play.level_id.startswith("sector") and \
                    play.level_id not in p["sectors_won"] and not getattr(play, "variant", None):
                p["sectors_won"].append(play.level_id)
            if play.level_id == "sector7" and not self.built_radar:
                self.count("lights_out")
            if getattr(play, "variant", None) == "boss_rush":
                self.count("boss_rush")
            pz = getattr(play, "puzzle_id", None)
            if pz and pz not in p["puzzles"]:
                p["puzzles"].append(pz)
        else:
            hitter = getattr(self, "last_hitter", None)
            if hitter:
                p["killed_by"][hitter] = p["killed_by"].get(hitter, 0) + 1
        if play.endless:
            self.raise_to("best_wave", play.waves.wave_number)
            if getattr(play.game, "hardcore", False):
                self.raise_to("hardcore_wave", play.waves.wave_number)
        key = self.board_key()
        if key:
            record_score(self.save, key, play.session.final_score(), play.waves.wave_number)
        self.check()

    def board_key(self):
        play = self.play
        if play.run:
            return None
        variant = getattr(play, "variant", None)
        if variant:
            return variant.split(":")[0]
        if play.daily:
            return f"daily {play.daily}"
        return ("endless " if play.endless else "campaign ") + play.level_id

    def check(self):
        got = self.save.setdefault("achievements", [])
        for aid, a in self.meta["achievements"].items():
            if aid in got:
                continue
            if stat_value(self.p, a["stat"]) >= a["goal"]:
                got.append(aid)
                msg = f"ACHIEVEMENT: {a['name']}"
                if a.get("skin"):
                    msg += f"  (skin unlocked: {self.meta['skins'][a['skin']]['name']})"
                self.play.ui.toast(msg, S.ENERGY)
                self.play.audio.play("upgrade")

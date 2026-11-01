"""GameManager: owns the window, the global systems and the main loop.

Global (live for the whole program): AssetManager, AudioSystem,
InputSystem, SceneManager, loaded JSON data and save data.
Per-level systems (towers, enemies, waves...) are created by PlayScene so a
restart always starts clean.

The loop uses a FIXED timestep: logic always advances in 1/60 s steps,
no matter how fast frames are drawn, so a lag spike can't let a bullet
tunnel through an enemy.
"""
import datetime
import json
import os

import pygame

from . import settings as S
from .scenes import (EventScene, LevelSelectScene, LoseScene, MenuScene, PauseScene, PlayScene,
                     RunEndScene, RunMapScene, RunRewardScene, SceneManager, ShopScene,
                     TechLabScene, WinScene)
from .systems import asset_manager
from .systems.asset_manager import AssetManager
from .systems.audio_system import AudioSystem
from .systems.input_system import InputSystem
from .systems.run import RunState, expand_tech


def load_json(name):
    with open(os.path.join(S.DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


class GameManager:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(S.TITLE)
        # The game always draws onto a fixed 1280x720 canvas (self.screen). The real
        # window can be any size: present() scales the canvas to fit it (letterboxed),
        # and InputSystem maps mouse positions back onto the canvas.
        self.fullscreen = False
        self.window = pygame.display.set_mode((S.SCREEN_W, S.SCREEN_H), pygame.RESIZABLE)
        self.screen = pygame.Surface((S.SCREEN_W, S.SCREEN_H)).convert()
        self.clock = pygame.time.Clock()
        self.running = True

        self.assets = AssetManager()
        self.audio = AudioSystem()
        self.input = InputSystem()
        self.data = {
            "towers": load_json("towers.json"),
            "enemies": load_json("enemies.json"),
            "items": load_json("items.json"),
            "endless": load_json("endless.json"),
            "run": load_json("run.json"),
            "tech": load_json("tech.json"),
            "commanders": load_json("commanders.json"),
            "perks": load_json("perks.json"),
        }
        self.data["tech"].pop("_comment", None)
        self.save = self.load_save()
        self.difficulty = self.save.get("difficulty", S.DEFAULT_DIFFICULTY)
        self.run = None    # the active Siege Run (also kept in save.json so it survives a restart)
        if self.save.get("run"):
            try:
                self.run = RunState.from_dict(self.save["run"], self.data["run"], self.data["towers"])
            except (KeyError, TypeError, ValueError) as err:
                print("Could not restore the saved Siege Run:", err)
                self.save.pop("run", None)
        self.mode = self.save.get("mode", "campaign")     # "campaign" or "endless"
        self.commander_class = self.save.get("commander", "vanguard")
        if self.commander_class not in self.data["commanders"]:
            self.commander_class = next(iter(self.data["commanders"]))
        for cid, hero in self.data["commanders"].items():   # hero sprite recolors
            if hero.get("palette"):
                asset_manager.HERO_PALETTES[cid] = hero["palette"]

        self.scenes = SceneManager(self)
        self.scenes.register("menu", MenuScene)
        self.scenes.register("level_select", LevelSelectScene)
        self.scenes.register("play", PlayScene)
        self.scenes.register("pause", PauseScene)
        self.scenes.register("win", WinScene)
        self.scenes.register("lose", LoseScene)
        self.scenes.register("run_map", RunMapScene)
        self.scenes.register("run_reward", RunRewardScene)
        self.scenes.register("run_shop", ShopScene)
        self.scenes.register("run_event", EventScene)
        self.scenes.register("run_end", RunEndScene)
        self.scenes.register("tech_lab", TechLabScene)

    # ---- save data -----------------------------------------------------------
    @staticmethod
    def load_save():
        try:
            with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"unlocked": 1, "sectors": {}}

    def write_save(self):
        self.save["difficulty"] = self.difficulty
        self.save["mode"] = self.mode
        self.save["commander"] = self.commander_class
        try:
            with open(S.SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.save, f, indent=2)
        except OSError as err:
            print("Could not write save file:", err)

    def record_result(self, level_id, stars, score):
        """Keep the best stars/score per sector and unlock the next sector."""
        sectors = self.save.setdefault("sectors", {})
        best = sectors.setdefault(level_id, {"stars": 0, "score": 0})
        best["stars"] = max(best["stars"], stars)
        best["score"] = max(best["score"], score)
        try:
            index = int(level_id.replace("sector", ""))
            self.save["unlocked"] = max(self.save.get("unlocked", 1), index + 1)
        except ValueError:
            pass
        self.write_save()

    def record_endless(self, level_id, wave, score):
        """Endless runs keep the best wave reached and best score per sector."""
        runs = self.save.setdefault("endless", {})
        best = runs.setdefault(level_id, {"wave": 0, "score": 0})
        new_best = wave > best["wave"]
        best["wave"] = max(best["wave"], wave)
        best["score"] = max(best["score"], score)
        self.write_save()
        return new_best

    # ---- Daily Challenge ------------------------------------------------------------------
    @staticmethod
    def daily_info():
        """Today's challenge: a generated map, waves and weather all fixed by the date."""
        today = datetime.date.today()
        seed = int(today.strftime("%Y%m%d"))
        return {"daily": today.isoformat(), "seed": seed, "level_id": f"proc_{seed}"}

    def start_daily(self):
        info = self.daily_info()
        self.scenes.change("play", level_id=info["level_id"], difficulty="Normal", mode="endless",
                           daily=info["daily"], seed=info["seed"])

    def record_daily(self, day, wave, score):
        log = self.save.setdefault("daily", {})
        best = log.setdefault(day, {"wave": 0, "score": 0})
        new_best = wave > best["wave"]
        best["wave"] = max(best["wave"], wave)
        best["score"] = max(best["score"], score)
        self.write_save()
        return new_best

    # ---- Siege Run meta progression ---------------------------------------------------
    @property
    def tech_ranks(self):
        return self.save.setdefault("tech", {})

    @property
    def salvage(self):
        return self.save.get("salvage", 0)

    def start_run(self, seed=None):
        effects = expand_tech(self.data["tech"], self.tech_ranks)
        self.run = RunState(self.data["run"], self.data["towers"], effects, seed=seed)
        self.run.commander = self.commander_class
        self.save_run()
        return self.run

    def save_run(self):
        """Store the active run between sectors (called from the run map)."""
        if self.run is not None and not self.run.over:
            self.save["run"] = self.run.to_dict()
        else:
            self.save.pop("run", None)
        self.write_save()

    def bank_run(self, run):
        """Add a finished run's Salvage to the save (once) and record stats."""
        if getattr(run, "banked", False):
            return
        run.banked = True
        self.save["salvage"] = self.salvage + run.salvage_earned
        stats = self.save.setdefault("runs", {"played": 0, "wins": 0, "best_act": 0})
        stats["played"] += 1
        stats["wins"] += 1 if run.victory else 0
        stats["best_act"] = max(stats["best_act"], run.act)
        if self.run is run:
            self.run = None
        self.save.pop("run", None)
        self.write_save()

    def buy_tech(self, tid):
        node = self.data["tech"][tid]
        rank = self.tech_ranks.get(tid, 0)
        if rank >= len(node["costs"]) or self.salvage < node["costs"][rank]:
            return False
        self.save["salvage"] = self.salvage - node["costs"][rank]
        self.tech_ranks[tid] = rank + 1
        self.write_save()
        return True

    # ---- main loop --------------------------------------------------------------
    def on_start(self):
        self.assets.preload()
        self.scenes.change("menu")

    def on_update(self, dt):
        self.scenes.on_update(dt)

    def on_render(self):
        self.scenes.on_render(self.screen)
        self.present()

    def present(self):
        """Scale the canvas into the window, keeping the 16:9 shape (black bars fill the rest)."""
        window = pygame.display.get_surface()
        ww, wh = window.get_size()
        if (ww, wh) == (S.SCREEN_W, S.SCREEN_H):
            window.blit(self.screen, (0, 0))
            InputSystem.viewport = (0, 0, 1.0)
        else:
            scale = min(ww / S.SCREEN_W, wh / S.SCREEN_H)
            w, h = max(1, int(S.SCREEN_W * scale)), max(1, int(S.SCREEN_H * scale))
            x, y = (ww - w) // 2, (wh - h) // 2
            window.fill((0, 0, 0))
            window.blit(pygame.transform.smoothscale(self.screen, (w, h)), (x, y))
            InputSystem.viewport = (x, y, scale)
        pygame.display.flip()

    def toggle_fullscreen(self):
        """F11: borderless fullscreen at the desktop resolution, or back to a window."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((S.SCREEN_W, S.SCREEN_H), pygame.RESIZABLE)

    def main_loop(self):
        self.on_start()
        accumulator = 0.0
        while self.running:
            frame = min(self.clock.tick(S.FPS) / 1000.0, S.MAX_FRAME_TIME)
            accumulator += frame
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                    continue
                self.scenes.handle_event(event)
                if self.input.quit_requested:
                    self.running = False
            while accumulator >= S.FIXED_DT:
                self.on_update(S.FIXED_DT)
                accumulator -= S.FIXED_DT
            self.on_render()
        self.write_save()
        pygame.quit()

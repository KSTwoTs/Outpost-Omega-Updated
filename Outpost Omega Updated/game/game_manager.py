"""GameManager: owns the window, the global systems and the main loop.

Global (live for the whole program): AssetManager, AudioSystem,
InputSystem, SceneManager, loaded JSON data and save data.
Per-level systems (towers, enemies, waves...) are created by PlayScene so a
restart always starts clean.

The loop uses a FIXED timestep: logic always advances in 1/60 s steps,
no matter how fast frames are drawn, so a lag spike can't let a bullet
tunnel through an enemy.
"""
import json
import os

import pygame

from . import settings as S
from .scenes import (LevelSelectScene, LoseScene, MenuScene, PauseScene, PlayScene,
                     SceneManager, WinScene)
from .systems.asset_manager import AssetManager
from .systems.audio_system import AudioSystem
from .systems.input_system import InputSystem


def load_json(name):
    with open(os.path.join(S.DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


class GameManager:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(S.TITLE)
        self.screen = pygame.display.set_mode((S.SCREEN_W, S.SCREEN_H))
        self.clock = pygame.time.Clock()
        self.running = True

        self.assets = AssetManager()
        self.audio = AudioSystem()
        self.input = InputSystem()
        self.data = {
            "towers": load_json("towers.json"),
            "enemies": load_json("enemies.json"),
            "items": load_json("items.json"),
        }
        self.save = self.load_save()
        self.difficulty = self.save.get("difficulty", S.DEFAULT_DIFFICULTY)

        self.scenes = SceneManager(self)
        self.scenes.register("menu", MenuScene)
        self.scenes.register("level_select", LevelSelectScene)
        self.scenes.register("play", PlayScene)
        self.scenes.register("pause", PauseScene)
        self.scenes.register("win", WinScene)
        self.scenes.register("lose", LoseScene)

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

    # ---- main loop --------------------------------------------------------------
    def on_start(self):
        self.assets.preload()
        self.scenes.change("menu")

    def on_update(self, dt):
        self.scenes.on_update(dt)

    def on_render(self):
        self.scenes.on_render(self.screen)
        pygame.display.flip()

    def run(self):
        self.on_start()
        accumulator = 0.0
        while self.running:
            frame = min(self.clock.tick(S.FPS) / 1000.0, S.MAX_FRAME_TIME)
            accumulator += frame
            for event in pygame.event.get():
                self.scenes.handle_event(event)
                if self.input.quit_requested:
                    self.running = False
            while accumulator >= S.FIXED_DT:
                self.on_update(S.FIXED_DT)
                accumulator -= S.FIXED_DT
            self.on_render()
        self.write_save()
        pygame.quit()

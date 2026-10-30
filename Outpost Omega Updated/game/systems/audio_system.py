"""AudioSystem: sound effects and looping music through pygame.mixer.

If assets/sounds/<name>.wav (or .ogg) exists it is used. Otherwise a short
synthesized placeholder beep is generated. If the computer has no audio
device, every call quietly does nothing.

Music: put assets/sounds/music.ogg in place and call play_music().
"""
import array
import math
import os
import random

import pygame

from .. import settings as S

# name: (start_freq, end_freq, seconds, volume, waveform)
SYNTH = {
    "shoot":     (880, 660, 0.05, 0.18, "square"),
    "blaster":   (1200, 900, 0.04, 0.12, "square"),
    "hit":       (300, 200, 0.05, 0.15, "noise"),
    "explode":   (180, 40, 0.35, 0.35, "noise"),
    "build":     (440, 880, 0.12, 0.25, "square"),
    "sell":      (660, 330, 0.12, 0.22, "square"),
    "upgrade":   (523, 1046, 0.18, 0.25, "square"),
    "core_hit":  (120, 60, 0.25, 0.40, "square"),
    "pickup":    (990, 1480, 0.10, 0.22, "sine"),
    "wave":      (330, 660, 0.40, 0.30, "sine"),
    "error":     (160, 140, 0.15, 0.25, "square"),
    "cryo":      (1400, 1200, 0.20, 0.06, "sine"),
    "downed":    (400, 100, 0.50, 0.30, "square"),
    "click":     (700, 700, 0.03, 0.15, "square"),
    "zap":       (2000, 400, 0.12, 0.15, "noise"),
    "rail":      (1800, 200, 0.25, 0.25, "square"),
    "missile":   (300, 500, 0.15, 0.15, "noise"),
    "emp":       (200, 1200, 0.9, 0.18, "sine"),
    "shield":    (250, 500, 0.5, 0.25, "sine"),
    "boss":      (90, 60, 1.2, 0.40, "square"),
}


class AudioSystem:
    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.enabled = True
            self.rate, _, self.channels = pygame.mixer.get_init()
        except pygame.error:
            self.enabled = False

    def _load(self, name):
        for ext in (".wav", ".ogg"):
            path = os.path.join(S.SOUND_DIR, name + ext)
            if os.path.exists(path):
                return pygame.mixer.Sound(path)
        if name in SYNTH:
            return self._synth(*SYNTH[name])
        return None

    def _synth(self, f0, f1, seconds, volume, wave):
        n = int(self.rate * seconds)
        buf = array.array("h")
        phase = 0.0
        for i in range(n):
            t = i / max(1, n - 1)
            freq = f0 + (f1 - f0) * t
            phase += 2 * math.pi * freq / self.rate
            if wave == "square":
                v = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "noise":
                v = random.uniform(-1, 1)
            else:
                v = math.sin(phase)
            env = (1 - t) ** 2  # quick decay
            sample = int(v * env * volume * 32767)
            for _ in range(self.channels):
                buf.append(sample)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is None and name not in self.sounds:
            snd = self._load(name)
            self.sounds[name] = snd
        if snd:
            snd.set_volume(self.sfx_volume)
            snd.play()

    def play_music(self, name="music", loops=-1):
        if not self.enabled:
            return
        for ext in (".ogg", ".mp3", ".wav"):
            path = os.path.join(S.SOUND_DIR, name + ext)
            if os.path.exists(path):
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(loops)
                return

    def stop_music(self):
        if self.enabled:
            pygame.mixer.music.stop()

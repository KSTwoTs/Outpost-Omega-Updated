"""Juice and feel: goo splats that fade, tower destruction debris, boss-kill slow motion,
a red low-Core tint, radio chatter from Vance, and adaptive music.

Music: if assets/sounds/music.ogg exists the AudioSystem plays it as before. Otherwise a
small synthesized track is built at startup in three layers (pad, bass, drums) that fade
in and out with the threat on the map.
"""
import array
import math
import random

import pygame

from .. import settings as S

SPLAT_COLORS = [(110, 230, 60), (90, 200, 50), (170, 90, 220), (120, 220, 60)]


class Juice:
    SPLAT_LIFE = 20.0

    def __init__(self, play):
        self.play = play
        self.splats = []          # [x, y, r, color, life, seed]
        self.smoke = []           # broken towers emitting smoke
        self.slowmo = 0.0
        self.radio = []           # [text, life]
        self.seen = set()         # alien kinds already called out this sector
        self.cooldowns = {}
        ev = play.events
        ev.subscribe("enemy_killed", self.on_enemy_killed)
        ev.subscribe("boss_spawned", self.on_boss)
        ev.subscribe("spawn_enemy", self.on_spawn)
        ev.subscribe("commander_downed", lambda commander=None, **_: self.say(
            "I'm down! Hold the line!" if getattr(commander, "player_no", 1) == 1 else "Partner down! Covering you!",
            "downed"))
        self.low_core_warned = False

    # ---- radio chatter -------------------------------------------------------------
    CALLOUTS = {
        "brute": "Brute incoming! Bring the heavy guns.", "glider": "Flyers! Get anti-air up.",
        "saboteur": "Saboteur! It'll EMP our towers.", "cloaker": "Cloakers, I can't see them without Radar.",
        "burrower": "Burrowers going underground!", "juggernaut": "Juggernaut! Cryo won't slow it.",
        "spitter": "Spitters, they're shooting our towers!", "hunter": "Hunter... it's coming for me.",
        "carrier": "Carrier inbound, it's dropping Gliders!", "mimic": "Careful, some loot bites.",
        "thief": "Thief! It's after our Energy.", "leech": "Leech on the field, I'll have to knock it off.",
        "jammer": "Jammer! My gear goes dark near it.", "reflector": "Reflector, bullets bounce off it. Use beams.",
        "infector": "Infector! Keep it away from the towers.", "blob": "Blob, it's eating the others!",
        "necro_spore": "Necro-Spore, it raises the dead.", "phaser": "Phasers, they skip ahead!",
        "swarm_mind": "Swarm Mind, break up the pack.", "bomber": "Bombers, they're going for our towers!",
        "pathcutter": "Pathcutter, it's digging a shortcut!", "artillery_grub": "Artillery Grub, outranging us!",
        "adaptive": "Adaptive, mix up the damage.", "swarm_queenlet": "Swarm Queenlet with an escort!",
    }

    def say(self, text, key=None, cooldown=8.0, speaker="VANCE", color=None, life=3.5):
        if key is not None:
            if self.cooldowns.get(key, 0) > 0:
                return
            self.cooldowns[key] = cooldown
        self.radio.append([text, life, speaker, color or S.CYAN])
        self.radio = self.radio[-2:]

    def on_spawn(self, enemy_type, **_):
        if enemy_type not in self.seen:
            self.seen.add(enemy_type)
            line = self.CALLOUTS.get(enemy_type)
            if line:
                self.say(line)

    def on_boss(self, enemy, **_):
        self.say(f"{enemy.stats.get('name', 'Boss')} sighted. Everything we've got!")

    def tower_broken(self, tower):
        fx = self.play.effects
        fx.explosion(tower.x, tower.y, S.STEEL_LIGHT, count=18)
        fx.burst(tower.x, tower.y, (70, 70, 80), 12, 140, 0.8, 4, gravity=200)
        fx.shake(0.15)
        self.smoke.append(tower)
        self.say(f"We lost the {tower.name}! Repair it with E.", "broken", 6.0)

    # ---- kills ---------------------------------------------------------------------
    def on_enemy_killed(self, enemy, **_):
        r = max(6, enemy.radius) * random.uniform(0.9, 1.4)
        col = (170, 90, 220) if enemy.zombie else random.choice(SPLAT_COLORS[:2])
        if not enemy.flying:
            self.splats.append([enemy.pos.x, enemy.pos.y, r, col, self.SPLAT_LIFE, random.random() * 1000])
            self.splats = self.splats[-180:]
        if enemy.is_boss and not getattr(enemy, "dormant", 0):
            self.slowmo = 1.4
            self.play.effects.flash(S.WHITE, 0.35)
            self.play.effects.shake(0.8)
            self.say("Boss down! Great work.")

    @property
    def time_scale(self):
        return 0.3 if self.slowmo > 0 else 1.0

    def update(self, dt):
        self.slowmo = max(0.0, self.slowmo - dt)
        for s in self.splats:
            s[4] -= dt
        self.splats = [s for s in self.splats if s[4] > 0]
        for k in list(self.cooldowns):
            self.cooldowns[k] -= dt
        for r in self.radio:
            r[1] -= dt
        self.radio = [r for r in self.radio if r[1] > 0]
        towers = self.play.towers.towers
        self.smoke = [t for t in self.smoke if t in towers and t.health.is_dead]
        for t in self.smoke:
            if random.random() < dt * 8:
                p = self.play.effects.particles.acquire()
                p.spawn(t.x + random.uniform(-6, 6), t.y, random.uniform(-8, 8), random.uniform(-40, -20),
                        1.0, random.choice(((60, 60, 70), (90, 90, 100))), 4, drag=0.5)
        s = self.play.session
        if s.core_hp / s.core_max < 0.2 and not self.low_core_warned:
            self.low_core_warned = True
            self.say("The Core is critical! Fall back and defend it!")

    # ---- drawing -------------------------------------------------------------------
    def render_splats(self, screen, offset):
        for x, y, r, col, life, seed in self.splats:
            a = int(160 * min(1.0, life / 6.0))
            size = int(r * 2 + 8)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            rng = random.Random(seed)
            c = size // 2
            pygame.draw.circle(surf, (*col, a), (c, c), int(r * 0.7))
            for _ in range(5):
                ang = rng.random() * math.tau
                d = rng.uniform(0.5, 1.0) * r
                pygame.draw.circle(surf, (*col, a), (int(c + math.cos(ang) * d), int(c + math.sin(ang) * d)),
                                   rng.randint(2, 4))
            screen.blit(surf, (x - c + offset[0], y - c + offset[1]))

    def render_overlay(self, screen, assets):
        s = self.play.session
        frac = s.core_hp / s.core_max
        if 0 < frac < 0.2:   # pulsing red vignette
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 250)
            a = int(40 + 50 * pulse * (1 - frac / 0.2))
            surf = pygame.Surface((S.MAP_W, S.MAP_H), pygame.SRCALPHA)
            for i in range(6):
                w = 18 + i * 10
                pygame.draw.rect(surf, (200, 20, 20, max(0, a - i * 8)), (0, 0, S.MAP_W, S.MAP_H), w)
            screen.blit(surf, (0, 0))
        y = S.HUD_Y - 54
        for text, life, speaker, color in self.radio:
            surf = assets.text(f"{speaker}: {text}" if speaker else text, 17, color, True)
            surf.set_alpha(int(255 * min(1.0, life / 0.5)))
            bg = pygame.Surface((surf.get_width() + 16, 22), pygame.SRCALPHA)
            bg.fill((*S.HUD_BG, int(200 * min(1.0, life / 0.5))))
            screen.blit(bg, (6, y - 2))
            pygame.draw.rect(screen, color, (6, y - 2, 3, 22))
            screen.blit(surf, (14, y))
            y -= 26


# ---- adaptive music -----------------------------------------------------------------
NOTES = {"A2": 110.0, "C3": 130.8, "D3": 146.8, "E3": 164.8, "G3": 196.0, "A3": 220.0, "C4": 261.6,
         "E4": 329.6, "G4": 392.0, "A4": 440.0}


def _render_layer(rate, seconds, fn):
    n = int(rate * seconds)
    buf = array.array("h", [0]) * n
    for i in range(n):
        buf[i] = int(max(-1.0, min(1.0, fn(i / rate))) * 9000)
    return pygame.mixer.Sound(buffer=buf.tobytes())


class AdaptiveMusic:
    """Three looping layers on their own mixer channels; set_threat(0..1) fades them."""
    BAR = 4.0

    def __init__(self, audio):
        self.ok = False
        self.layers = []
        if not audio.enabled:
            return
        try:
            rate = audio.rate
            prog = ["A2", "A2", "C3", "G3"]   # one chord root per beat-bar
            beat = self.BAR / 8

            def pad(t):
                root = NOTES[prog[int(t / self.BAR) % 4]] * 2
                return 0.25 * (math.sin(math.tau * root * t) + 0.5 * math.sin(math.tau * root * 1.5 * t))

            def bass(t):
                root = NOTES[prog[int(t / self.BAR) % 4]]
                k = (t % beat) / beat
                return 0.6 * math.copysign(1, math.sin(math.tau * root * t)) * (1 - k) ** 2

            def drums(t):
                k = (t % beat) / beat
                kick = math.sin(math.tau * 60 * (1 - k) * t) * (1 - k) ** 6 if int(t / beat) % 2 == 0 else 0
                hat = random.uniform(-1, 1) * (1 - (t % (beat / 2)) / (beat / 2)) ** 12 * 0.4
                return kick + hat

            length = self.BAR * 4
            self.layers = [_render_layer(rate, length, f) for f in (pad, bass, drums)]
            self.channels = [pygame.mixer.Channel(5 + i) for i in range(3)]
            self.volume = audio.music_volume
            self.levels = [0.0, 0.0, 0.0]
            self.ok = True
        except (pygame.error, ValueError):
            self.ok = False

    def start(self, volume):
        if not self.ok:
            return
        self.volume = volume
        for ch, snd in zip(self.channels, self.layers):
            ch.play(snd, loops=-1)
            ch.set_volume(0.0)

    def stop(self):
        if self.ok:
            for ch in self.channels:
                ch.stop()

    def set_threat(self, threat, dt, volume):
        """threat 0..1: pad always, bass from 0.25, drums from 0.6."""
        if not self.ok:
            return
        self.volume = volume
        targets = [0.6, min(1.0, max(0.0, (threat - 0.15) * 3)), min(1.0, max(0.0, (threat - 0.5) * 3))]
        for i, (ch, tgt) in enumerate(zip(self.channels, targets)):
            self.levels[i] += (tgt - self.levels[i]) * min(1.0, dt * 1.5)
            ch.set_volume(self.levels[i] * self.volume * 0.6)

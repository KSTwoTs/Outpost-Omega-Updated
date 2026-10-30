# Outpost Omega: Alien Siege

CPSC 4160 · 2D top-down tower defense with a playable hero · Python 3 + pygame-ce

## Run it

```
pip install -r requirements.txt
python main.py
```

If you already have classic `pygame` installed, it works too. Don't install both.

## Controls

| Input | Action |
|---|---|
| WASD / arrows | Move Commander Vance (she auto-fires at the closest alien within 160 px) |
| E (hold) | Repair a nearby damaged or EMP'd tower |
| Click a drop | Collect it (or walk over it) |
| Q, then click | Orbital Strike (1 s delay, 45 s cooldown). Right-click cancels |
| 1–5 or HUD buttons | Pick a tower to build. Click a green tile to place it. Shift+click places several |
| Click a tower | Select it (HUD shows Upgrade / Sell / Targeting) |
| Right-click a tower | Upgrade it |
| U / X / T | Upgrade / Sell (70% refund) / cycle targeting (first, last, strongest, closest) |
| Space | Start the next wave early |
| Esc / P | Pause |
| F1 | Debug overlay: waypoints, ranges, spatial-hash cells, hitboxes (boss shows its pixel-mask outline), FPS |

## What works now (Milestone 2)

- Menu → Level Select (difficulty Easy/Normal/Hard, best stars, mini-map) → Play → Pause → Win/Lose
- Three sectors, 10 waves each, boss on wave 10 (all unlocked for the demo):
  - Sector 1 Desert Outpost: one winding path
  - Sector 2 Frozen Relay Station: two lanes merging before the Core, ice patches (Vance slides)
  - Sector 3 Hive Crash Site: acid pools, hive walls that grow mid-wave and reroute aliens (A*)
- All 5 towers: Pulse (lead-aimed shots), Tesla (chain lightning), Cryo (slow aura),
  Railgun (piercing beam, ignores armor), Missile Battery (homing + splash), 3 tiers each
- All 6 enemies: Skitter, Brute, Glider (seek steering), Brood Sac (splits into Skitters),
  Saboteur (EMPs towers), Hive Overseer boss (shield phases, summons Skitters,
  pixel-perfect `pygame.mask` hit detection)
- Commander: acceleration/friction movement, tile collision, auto-blaster, repair,
  Orbital Strike, downed → respawn at the Core after 5 s
- Items from a weighted loot table: Energy Crystal, Repair Kit, Overcharge Cell, Shield Battery.
  Drops stay on the map until the next wave starts (they blink for the last 3 s of the
  build countdown); walk over them or click them (generous click area)
- Energy economy, scoring, 3-star rating, save.json (best stars/score, unlocks)
- Effects: pooled particles, screen shake, hit flash, damage numbers, lightning, beams
- Placeholder pixel-art sprites and synthesized sound effects (see "Art & sound")

## Still to build

| Feature | Where |
|---|---|
| Unlock progression | Turned off for the demo; one line in `scenes/level_select.py` restores it |
| Music | Drop `assets/sounds/music.ogg` in |

The grading write-up (items developed) is in `readme.txt`.

## Project layout

```
main.py                     entry point
data/towers.json            tower stats per tier
data/enemies.json           enemy stats
data/items.json             loot table
data/levels/sector1-3.json  tile maps (40x20), waves, lanes, hive-wall events
assets/sprites, assets/sounds   optional real art/sound (overrides placeholders)
game/
  settings.py               constants, palette, difficulty multipliers
  game_manager.py           window, fixed-timestep loop, save data
  core/                     EventBus, StateMachine, Timer, Health, PathFollower,
                            A*, SpatialHash, ObjectPool (no pygame, unit-testable)
  scenes/                   SceneManager + Menu, LevelSelect, Play, Pause, Win/Lose
  systems/                  Input, Level, Wave, Asset, Player, Tower, Enemy,
                            Projectile, Collision, Effects, UI, Audio
  entities/                 Commander, Tower, Enemy (+ subclasses), Projectile, Item
```

## Architecture notes

- **Fixed timestep.** Logic runs in 1/60 s steps no matter the frame rate, so
  lag spikes can't make fast projectiles skip through enemies.
- **EventBus.** Systems publish events (`enemy_killed`, `enemy_reached_core`,
  `item_collected`, `wave_started`…) instead of calling each other. Each PlayScene
  has its own bus, so restarting a level drops every listener.
- **Global vs. per-level systems.** GameManager owns assets, audio, input and save
  data. PlayScene creates the gameplay systems, so a restart is always clean.
- **Data-driven.** Tuning lives in the JSON files. Enemy waypoints come from A*
  over the painted path tiles, so editing the map changes the route.
- **Collision.** A spatial hash (64 px cells) is rebuilt every frame. Hit tests
  use circle-vs-circle with squared distances, and the Commander uses
  axis-separated AABB checks against tiles. The Hive Overseer uses
  `pygame.mask` instead: bullets and splash test a circle mask against the
  boss's sprite mask with `mask.overlap`, and railgun beams are sampled along
  the line. Each enemy owns its narrow-phase test (`hit_test_circle` /
  `hit_test_segment`), so the boss just overrides them.

## Art & sound

Every sprite is drawn in code (`systems/asset_manager.py`) with the game palette.
To use real art, save a PNG under `assets/sprites/` using the sprite's name, for
example `skitter_0.png`, `turret_pulse.png` or `core.png`. The full list is
`SPRITE_NAMES` in `asset_manager.py`. Sounds work the same way: put
`assets/sounds/shoot.wav` (or `.ogg`) in place to replace that placeholder beep.

## Balancing

These numbers are a first pass, tested with a scripted bot player. They are all
in the JSON files plus `DIFFICULTIES` in `settings.py`.

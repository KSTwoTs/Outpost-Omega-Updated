# Outpost Omega: Alien Siege

CPSC 4160 · 2D top-down tower defense with a playable hero · Python 3 + pygame-ce

## Run it

### Windows (one click)

Double-click **`Play Outpost Omega.bat`** in the repo root.

- **First run:** it finds Python 3.10+ (or installs Python 3.12 for your user
  account with `winget` if none is found), creates a private `.venv` inside
  `Outpost Omega Updated/`, and installs `pygame-ce` into it. Needs internet.
- **After that:** it just launches the game.
- If the game crashes, the window stays open so you can read the error.
- Something broken? Delete `Outpost Omega Updated/.venv` and run it again to
  rebuild the environment from scratch.

Because the game uses its own `.venv`, it never conflicts with a `pygame` or
`pygame-ce` install elsewhere on your PC.

### Standalone build (no Python needed to play)

After running `Play Outpost Omega.bat` once, double-click
**`Build Standalone EXE.bat`**. It uses PyInstaller to produce:

- `dist/Outpost Omega/Outpost Omega.exe`: the playable game
- `dist/Outpost Omega.zip`: the same folder zipped for sharing (unzip, then run the `.exe`)

Notes:
- The packaged game keeps its own `save.json` (inside `_internal/`), separate
  from your development copy.
- The `.exe` is unsigned, so Windows SmartScreen may warn on first launch;
  click **More info > Run anyway**.
- If the zip step reports a file in use, close the game (or wait for antivirus
  to finish scanning) and run the build again, or right-click the folder in
  `dist/` and choose **Compress to ZIP file**.

### Manual (any OS)

```
cd 'Outpost Omega Updated'
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
| 1–9, 0, -, =, \\, Z, C, V, B or HUD buttons | Pick a tower to build. Click a green tile to place it. Shift+click places several |
| Click a tower | Select it (HUD shows Upgrade / Sell / Targeting) |
| Click the Core | Core upgrades: Gun, Shield, Regen, Reactor, Nova, Plating |
| Level-up panel | Click one of 3 perks when your Commander levels up (the game keeps running) |
| Right-click a tower | Upgrade it (in a Siege Run, a maxed tower opens the tier-4 branch choice) |
| U / X / T | Upgrade / Sell (70% refund) / cycle targeting (first, last, strongest, closest) |
| Space | Start the next wave early |
| F | Game speed 1x / 2x / 3x |
| Esc / P | Pause |
| F11 | Toggle fullscreen. The window can also be resized or maximized; the game scales to fit |
| F1 | Debug overlay: waypoints, ranges, spatial-hash cells, hitboxes (boss shows its pixel-mask outline), FPS |

## What works now 

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

## Endless mode (Phase 1)

Pick **ENDLESS** under the difficulty buttons in Level Select, then any sector.

- Waves are generated forever from a threat budget that grows 12% per wave.
  Each enemy has a `threat` cost and `unlock_wave` in `enemies.json`.
- Past wave 10, enemy HP also grows 5% per wave (compounding).
- Every 5th wave rolls a mutator: Swarm, Armored Tide, Blitz, Air Raid or Blackout.
- Every 10th wave adds the Hive Overseer, +50% HP each time.
- From wave 12, aliens can spawn as elites (2x HP and reward) with one affix:
  Hasted, Armored, Regenerating, Shielded, Volatile or Vampiric.
- During the build phase a panel in the top-right previews the next wave
  (campaign levels show it too).
- Best wave and score per sector are saved in `save.json` and shown on the
  Level Select cards.
- All tuning lives in `data/endless.json`; the generator is
  `game/systems/endless.py` (no pygame, unit-testable).

## Siege Run (Phase 2)

Pick **SIEGE RUN** on the main menu. A run is 3 acts; each act is a branching
map of 7 floors ending in a boss.

- **Nodes:** Combat (3 generated waves on a random sector), Elite (3 waves,
  60%+ elites, drops a relic), Supply Cache (shop), Event (a choice with a
  cost), Boss (Hive Overseer, tougher each act).
- **Core HP carries over** between sectors. Energy resets each sector.
- **Tower cards:** you start with the Pulse Turret plus one random tower.
  Other towers are unlocked through drafts, the shop and events.
- **Augments:** after each win, draft 1 of 3 upgrades (24 in the pool,
  tower-specific ones only show up for towers you own).
- **Relics:** from elites, bosses, the shop and events. Cursed relics (red)
  have a big upside and a real drawback.
- **Scrap** is the in-run currency; **Salvage** is earned when a run ends and
  spent in the **TECH LAB** on permanent upgrades for future runs.
- **Tier-4 branches:** in a run, a tier-3 tower can take one of two branches
  (e.g. Railgun becomes Overpenetrator or Executioner).
- The run is saved to `save.json` every time you're on the map, so CONTINUE
  RUN works after closing the game. Pausing in a sector offers ABANDON RUN.
- Content lives in `data/run.json` (augments, relics, events, shop, rewards)
  and `data/tech.json`. Logic is in `game/systems/run.py` (no pygame); screens
  are in `game/scenes/run_scenes.py`.

### Long fights, endless acts and rarity

- **Waves per fight:** 10 in Act 1, +5 per act (15, 20, ...), capped at 30.
  Each wave has 1.6x the enemies of an Endless wave at the same threat level.
  Threat climbs about once every 3 waves inside a fight. Tune `waves_per_node`,
  `enemy_count_mult` and `wave_depth.per_wave` in `data/run.json`.
- **Endless acts:** after the Act 3 boss you choose **CLAIM VICTORY** (run ends
  as a win) or **PUSH ON**. Pushing on banks the win and keeps generating acts
  until the Core falls, rotating through every boss (`endless_bosses`).
- **Rarity:** every augment and relic is Common, Rare, Epic or Legendary (cursed
  relics are their own pool). Cards are colored by tier. Each draft, relic pick,
  shop slot and event rolls a tier from `rarity.odds` for that source (bosses
  never roll Common), shifted toward rarer tiers every act (`act_bonus`) and by
  luck effects. Rarer cards cost more in the Supply Cache.
- **Pool:** 93 augments and 40 relics (11 cursed). Effect types added along the way:
  `build_time`, `wave_energy`, `wave_heal`, `salvage`, `shop_discount`,
  `relic_choices`, `rarity_luck` (see the top of `game/systems/run.py`).

## Phase 3 content

Pick **DAILY CHALLENGE** on the main menu for today's generated map (same for everyone,
best wave saved per day). All modes are reachable from the main menu and Level Select.

**New towers** (available in every mode; unlocked as tower cards in a Siege Run)

| Key | Tower | What it does |
|---|---|---|
| 6 | Flamer | Short cone; damages and burns ground aliens |
| 7 | Mortar | Lobbed shells with big splash; can't hit close or flying targets |
| 8 | Gravity Well | Every few seconds pulls ground aliens back along the path |
| 9 | Harvester | No attack; pays Energy after every wave |
| 0 | Radar Relay | +15–25% range to nearby towers; reveals Cloakers and Burrowers |
| - | Drone Bay | Drones hunt aliens anywhere in range, flyers included |
| = | Barricade | Goes ON the path; aliens stop to chew through it; repair it with E |
| \\ | Mine Layer | Scatters proximity mines on path tiles in range |

**Combos:** Railgun hits on slowed aliens *Shatter* (2x damage); Missiles and Mortar
shells *Detonate* (1.5x splash) on burning aliens; Tesla *Conducts* 2 extra jumps
when its first target is slowed.

**Veterancy:** towers rank up at 10 / 30 / 75 kills (+6% damage per rank, yellow chevrons).

**New enemies:** Mender (heals nearby aliens), Juggernaut (can't be slowed, stunned or
pushed), Cloaker (invisible unless Vance or a Radar Relay is close), Burrower
(untargetable while tunnelling), Spitter (spits acid at towers), Shield Drone (flying;
aliens under its bubble take half damage), Hunter (ignores the path and chases Vance),
Mimic (disguised as an Energy Crystal; bites when Vance comes to collect it), Carrier
(big flyer that keeps dropping Gliders). **New bosses:** Siege Titan (crushes and stomps
towers), Hive Queen (lays eggs that hatch into Skitters), Burrow Wyrm (tunnels ahead and
erupts under towers). Endless rotates all four bosses; a Siege Run has one per act.

**New sectors**

| Sector | Mechanic |
|---|---|
| 4 Magma Forge | Volcanic vents erupt during waves and knock nearby towers offline |
| 5 Open Plains | No path: aliens walk around your towers, so you build the maze |
| 6 Orbital Platform | Conveyor belts speed up or slow down aliens (and push Vance); airlocks swap the route every two waves |
| 7 Derelict Ship | Pitch dark: only aliens near a tower, Vance or the Core can be seen or hit |
| 8 Twin Cores | Two Cores share one HP pool, one lane each; Vance is the swing defender |
| Uncharted | Endless only: a procedurally generated map every time (also appears in Siege Runs) |

**Weather** (35% chance per sector in Endless and Siege Run): Sandstorm (-20% tower
range), Blizzard (aliens 15% slower, Vance slides), Acid Rain (towers slowly corrode
during waves, so keep repairing with E).

**Commander:** pick a class in Level Select or the Tech Lab: Vanguard (+40% HP,
faster, +60% blaster), Engineer (towers 10% cheaper, 2x repair speed), Tactician
(Orbital Strike cooldown -35%, +25% damage). Vance also earns XP from every kill and
picks a perk at each level (`data/perks.json`); in a Siege Run his level carries over.

**Core upgrades:** click the Core: Gun (a turret on every Core), Shield (soaks
10/20/35 Core damage each wave), Regen (+3/6/10 Core HP after each wave). 120/200/300 Energy.

## Phase 4 content

**More towers** (every mode; tower cards in a Siege Run)

| Key | Tower | What it does |
|---|---|---|
| Z | Laser Lance | Continuous beam whose damage ramps up the longer it holds one alien |
| C | Acid Spitter | Lobs acid that pools on the path, melting aliens and stripping their armor |
| V | Repair Bay | No attack; repairs towers in range, broken ones included |
| B | Sonic Disruptor | Shockwaves hit every ground alien in range and stun them |

**Tier-4 branches for every tower** (Siege Run): Flamer (Dragon's Breath / Napalm
Sprayer), Mortar (Siege Cannon / Rapid Battery), Gravity Well (Singularity / Stasis
Field), Harvester (Energy Refinery / Overflow Core), Radar Relay (Targeting Uplink /
Overwatch Array), Drone Bay (Drone Swarm / Gunship Wing), Barricade (Bulwark Wall /
Shock Barricade), Mine Layer (Minefield / Cluster Charges), Laser Lance (Prism Lance /
Annihilator), Acid Spitter (Corrosive Bath / Toxic Flood), Repair Bay (Nanite Forge /
Overclock Station), Sonic Disruptor (Earthshaker / Resonance Cannon). Every tier and
branch has its own look (`systems/tower_art.py`).

**Heroes** (Endless and Siege Run only; hidden in the campaign): Ignis (fire), Rime
(frost), Bastion (defense), Kestrel (drones and mines), Ledger (economy) and Hawk
(sniper), each with their own colors. They're the entries in `data/commanders.json`
with a `modes` list; `palette` recolors the Commander sprite.

**Perks:** 18 Commander perks (10 new, e.g. Second Wind, Wide Strike, Tower Tuning).
**Core upgrades:** Reactor (+15/30/50 Energy a wave), Nova (shockwave around the Core
every 10 s), Plating (+20/40/70 Core max HP). **Tech Lab:** 20 upgrades, most with
more ranks.

## Phase 5 (in progress)

Nothing below is built yet. Full details and the task checklist are in `DESIGN.md`.

| Area | Planned |
|---|---|
| Towers | Shield Projector, Decoy Beacon, Plasma Fence, Chrono Spire, Mirror Array, Flak Cannon, Ion Cannon, Hacker Spire, Magnet Coil, Tar Pit, Lightning Rod, Bio-Lab, Overclocker, Uplink Dish, Bait Pod |
| Tower systems | Adjacency bonuses, power grid, sockets, relocate, named veterans, tower fusion, Focus/Suppress stance |
| Enemies | Adaptive, Thief, Leech, Phaser, Reflector, Swarm Mind, Necro-Spore, Infector, Blob, Bomber, Jammer, Artillery Grub, Pathcutter, Swarm Queenlet |
| Bosses | Mothership, Hive Mind, Fallen Commander, Acid Leviathan, Nest Heart, Architect |
| Commander | Dash, weapon pickups, grenades, mech suit ultimate, carry system, drone buddy, gear loadout, skins |
| Modes | Local co-op, Boss Rush, Puzzle, Last Stand, Reverse, Ascension, Weekly Challenge, Hardcore, Sandbox, Story campaign |
| Siege Run | Rest, Forge, Gamble and Mini-boss nodes; relic sets; boss relics; alien factions; shareable seeds; hero starting decks; run-wide events; debt merchant |
| Maps | High ground, overheat on hot maps (Magma Forge, Desert Outpost, new Heatwave weather), destructible terrain, day/night, rising tide, switches and gates, teleporters, supply drops, meteor showers, wildlife, resource nodes, earthquakes |
| New sectors | Jungle, Crystal Caves, Ruined City, Gas Giant Station |
| Economy | Biomass, interest, black market, insurance, research queue |
| Meta | Achievements, Codex, tower mastery, profile stats, local leaderboards, unlock progression |
| QoL | Undo placement, post-wave stats, key rebinding and controller, colorblind mode, settings menu, tutorial, wave timeline, combo tooltips |
| Juice | Adaptive music, boss-kill slow-mo, goo splats, tower destruction, radio chatter, low-Core tint |
| Wild ideas | Tameable alien pet, alien towers, Living Core, tower sacrifice, map editor and mod folder, itch.io release |

## Still to build

| Feature | Where |
|---|---|
| Playtesting and balance for all new content | Numbers live in `data/*.json` |
| Unlock progression | Turned off for the demo; one line in `scenes/level_select.py` restores it |
| Music | Drop `assets/sounds/music.ogg` in |

The grading write-up (items developed) is in `readme.txt`.

## Project layout

```
Play Outpost Omega.bat      one-click launcher (repo root; sets up .venv on first run)
Build Standalone EXE.bat    packages the game into dist/ with PyInstaller (repo root)
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

**Upgrade looks** (`systems/tower_art.py`): every tower changes appearance as
it's upgraded. Tier 2 adds cyan trim and extra hardware, tier 3 goes gold and
heavier, and tier-4 branches are magenta with their own silhouette (e.g.
Minigun vs Marksman). Sprite names: `turret_<kind>_t1`, `turret_<kind>_t2`,
`turret_<kind>_b0` / `_b1`, and base plates `tower_base_t1`, `_t2`, `_b`.
Things towers spawn follow their tower's tier too: drones (`drone_t0`-`drone_t2`),
mines and mortar shells. All of these can be replaced with PNGs the same way.

## Balancing

These numbers are a first pass, tested with a scripted bot player. They are all
in the JSON files plus `DIFFICULTIES` in `settings.py`.

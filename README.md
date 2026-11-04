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
| R / V / B / Z | Dash / throw grenade / next grenade / mech suit |
| Backspace | Undo the last tower placed (build phase) |
| H / Delete | Tame a weakened alien next to Vance / sacrifice the selected tower |
| Y | Sandbox mode: show / hide the alien spawn menu |
| Arrows, Right Ctrl, Right Shift | Local co-op Player 2: move, repair, dash (a controller also works) |
| WASD / arrows | Move Commander Vance (she auto-fires at the closest alien within 160 px) |
| E (hold) | Repair a nearby damaged or EMP'd tower |
| Click a drop | Collect it (or walk over it) |
| Q, then click | Orbital Strike (1 s delay, 45 s cooldown). Right-click cancels |
| 1–9, 0, - or HUD buttons | Pick a tower from the current HUD tab (Assault, Control, Support). Click a green tile to place it. Shift+click places several. Hover a button for stats and combos |
| Tab | Next tower tab (or click a tab) |
| I | Show / hide the post-wave report |
| M / G / K / J | Move / stance / socket a chip / fuse the selected tower |
| Click a tower | Select it (HUD shows Upgrade / Sell / Targeting) |
| Click the Core | Core upgrades: Gun, Shield, Regen, Reactor, Nova, Plating |
| Level-up panel | Click one of 3 perks when your Commander levels up (the game keeps running) |
| Right-click a tower | Upgrade it (in a Siege Run, a maxed tower opens the tier-4 branch choice) |
| U / X / T | Upgrade / Sell (70% refund) / cycle targeting (first, last, strongest, closest) |
| Space | Start the next wave early |
| F | Game speed 1x / 2x / 3x |
| Esc / P | Pause (Settings is in the pause menu and on the main menu) |
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

| Tab | Tower | What it does |
|---|---|---|
| Assault | Flamer | Short cone; damages and burns ground aliens |
| Assault | Mortar | Lobbed shells with big splash; can't hit close or flying targets |
| Control | Gravity Well | Every few seconds pulls ground aliens back along the path |
| Support | Harvester | No attack; pays Energy after every wave |
| Support | Radar Relay | +15–25% range to nearby towers; reveals Cloakers and Burrowers |
| Assault | Drone Bay | Drones hunt aliens anywhere in range, flyers included |
| Support | Barricade | Goes ON the path; aliens stop to chew through it; repair it with E |
| Control | Mine Layer | Scatters proximity mines on path tiles in range |

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

| Tab | Tower | What it does |
|---|---|---|
| Assault | Laser Lance | Continuous beam whose damage ramps up the longer it holds one alien |
| Control | Acid Spitter | Lobs acid that pools on the path, melting aliens and stripping their armor |
| Support | Repair Bay | No attack; repairs towers in range, broken ones included |
| Control | Sonic Disruptor | Shockwaves hit every ground alien in range and stun them |

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

## Phase 5

Full details and the task checklist are in `DESIGN.md`.

**Batch 1: five new towers** (every mode; tower cards in a Siege Run).

| Tab | Tower | What it does |
|---|---|---|
| Assault | Flak Cannon | Anti-air only. Fires bursts of shells that splash every flyer around the target |
| Assault | Ion Cannon | Charges for about 20 s (ring around it), then one armor-piercing blast down every lane |
| Support | Shield Projector | Gives towers in range (itself included) a shield that soaks damage from Spitter acid, Volatile blasts, Titan stomps, Saboteur EMPs and acid rain. Recharges after a few seconds without a hit |
| Control | Tar Pit | Goes ON the path like a Barricade, but aliens and Vance walk through it. Slows ground aliens; a Flamer hit or a burning alien sets it ablaze |
| Control | Chrono Spire | Every few seconds rewinds the lead alien back along the path (2–3 s of walking). Bosses and Juggernauts can't be moved |

Tier-4 branches: Flak Cannon (Skyburst / Hailstorm, which also hits ground), Ion Cannon
(Orbital Lance / Planet Cracker), Shield Projector (Aegis Dome / Rapid Recharge), Tar Pit
(Napalm Bog / Deep Tar), Chrono Spire (Time Loop / Stasis Lock). Every tier and branch
has its own look.

**Batch 2: five more towers.**

| Tab | Tower | What it does |
|---|---|---|
| Support | Decoy Beacon | A hologram of Vance. Every few seconds it lures the nearest ground aliens, which stop and attack it instead of walking on. Hunters within range chase it instead of Vance. Repair it with E |
| Control | Plasma Fence | A pylon. Build two within range of each other and a plasma beam links them; aliens crossing it take damage. Build a row of pylons to chain fences |
| Support | Mirror Array | No attack of its own. Railguns and Laser Lances within its range also bounce their beams off it at aliens near the mirror, so they can shoot around corners |
| Control | Hacker Spire | Hacks the lead ground alien for a few seconds: it walks back toward spawn and damages every alien it touches. Towers ignore it while hacked. Bosses, Juggernauts and flyers can't be hacked |
| Control | Magnet Coil | Strips armor from everything in range and chips it. Slows Juggernauts a little despite their slow immunity |

Tier-4 branches: Decoy Beacon (Mirage Field / Booby Trap, which shocks attackers and
explodes when destroyed), Plasma Fence (Arc Wall / Overload Grid, which links to every
pylon in range and hits flyers), Mirror Array (Prism Splitter / Focusing Lens), Hacker
Spire (Virus, whose hacked aliens explode / Botnet, 3 at once), Magnet Coil
(Demagnetizer, which also drains shields / Maglock).

**Batch 3: the last five towers.**

| Tab | Tower | What it does |
|---|---|---|
| Assault | Lightning Rod | Builds charge (4x faster while weather is on the map), then calls down a bolt that chains through nearby aliens. The yellow ring shows the charge |
| Support | Bio-Lab | No attack. Every alien that dies in its range pays 2–4 Energy |
| Support | Overclocker | Towers next to it (8 surrounding tiles) fire 60–100% faster, but lose HP while they're shooting |
| Support | Uplink Dish | Each kill in range takes 0.4–0.8 s off the Orbital Strike cooldown |
| Support | Bait Pod | Cheap, 400+ HP and regenerates. Spitters shoot it before any other tower |

Tier-4 branches: Lightning Rod (Storm Caller / Capacitor Bank), Bio-Lab (Rendering Plant /
Mutagen Lab, aliens in range take +20% damage), Overclocker (Turbo Core / Cryo-Cooled, no
burn), Uplink Dish (Twin Strike, a second stored Orbital Strike / Targeting Array, +50%
damage and +30% radius), Bait Pod (Spore Pod / Regenerator).

**Phase 5 UI**

- **Tower tabs:** the 32 towers are split into Assault (11), Control (10) and Support (11).
  The number row (1–9, 0, -) builds from the open tab; Tab or a click switches tabs.
  Each tower's tab is the `category` field in `data/towers.json`.
- **Tooltips:** hover a build button for its stats, upgrade costs, tier-4 branches and
  combos (Shatter, Conduct, Detonate, Tar ignition, Mirror bounces...).
- **Wave timeline:** in the build phase the top-right panel shows the next wave in detail
  plus the four after it (bosses in magenta, mutators in orange). During a wave it shrinks
  to five chips.
- **Post-wave report:** after each wave a panel lists damage and kills per tower and calls
  out attacking towers that did nothing. I or the x button hides it.
- **Settings** (main menu and pause menu): sound and music volume, screen shake, particle
  amount, damage numbers, post-wave report and wave timeline. Saved in `save.json`.

**New aliens** (Endless and Siege Run; the campaign sectors keep their original waves).
Each one counters a strategy:

| Alien | From wave | What it does |
|---|---|---|
| Thief | 8 | Steals Energy at the Core and runs back to spawn. Kill it to get the Energy back (+25%) |
| Phaser | 9 | Blinks a few tiles ahead along the path every few seconds |
| Leech | 10 | Latches onto a tower and drains it. Walk Vance up to it to knock it off |
| Jammer | 11 | Vance can't shoot, repair or call an Orbital Strike near it |
| Reflector | 12 | Bullets and missiles bounce back and hurt the tower that fired. Beams, fire and splash work |
| Bomber | 12 | Flyer that bombs towers instead of heading for the Core |
| Adaptive | 13 | Builds up to 60% resistance to the damage type (kinetic, energy, fire, chemical) that hits it most |
| Infector | 14 | Corrupts a tower so it zaps your other towers until you repair it to full |
| Swarm Mind | 15 | Takes less damage for every alien near it and speeds them up |
| Blob | 15 | Absorbs aliens it touches and grows |
| Necro-Spore | 16 | Raises aliens that just died nearby as weaker zombies (purple ring, no reward) |
| Artillery Grub | 17 | Shells towers from 240 px away |
| Pathcutter | 18 | Digs a permanent shortcut through open ground between two parts of the path |
| Swarm Queenlet | 20 | Mini-boss with an escort; aliens near her are faster and take 25% less damage |

**New bosses** (Endless rotates all ten bosses every 10th wave; they're also in the Siege Run
endless acts):

| Boss | What it does |
|---|---|
| Mothership | Flies slowly toward the Core and drops a wave of aliens at 75%, 50% and 25% HP |
| Hive Mind | Three bodies share one bar. A body killed while another stands goes dormant and revives at half HP after 6 s |
| Fallen Commander | An infected Vance: shoots towers, dodge-rolls ahead when hurt, and calls Orbital Strikes on tower clusters |
| Acid Leviathan | Swims under the path; when it surfaces it drags the nearest tower under (disabled 6 s, half its HP) |
| Nest Heart | Doesn't move. Sits 30% of the way down the path spawning aliens until you destroy it |
| Architect | At 66% and 33% HP it digs a new route and fills in the old one (on Open Plains it drops rock walls on the aliens' route) |

**Tower systems.** Select a tower and an action bar appears above the HUD:

| Key | System | How it works |
|---|---|---|
| (build) | Adjacency synergies | 16 pairs buff each other when on neighboring tiles, e.g. Railgun next to Cryo +15% damage, Tesla next to Cryo +1 chain. Build tooltips list them; the selected tower shows which are active |
| (build) | Generator (Support tab) | Powers towers in range: +20–30% fire rate, shown as cables. EMPs, vents and damage can knock it offline. Towers still work unpowered |
| K | Augment chips | Elites sometimes drop a chip and bosses drop two. Socket them into a tower: Damage, Range, Rapid, Plating or Salvage. 1 socket, 2 at tier 3 / tier 4. Selling returns the chips. Chips carry over between Siege Run fights |
| M | Move | Between waves, move a tower for 15% of what you've spent on it, without selling it |
| G | Stance | Normal / Focus (+20% damage) / Suppress (-20% damage, every hit slows 25%) |
| (75 kills) | Named veterans | At veteran rank 3 a tower gets a name and a random trait (Sharpshooter, Relentless, Heavy Hitter, Ironclad, Lucky) |
| J | Fusion (Endless and Siege Run) | Two maxed towers from a recipe on neighboring tiles fuse into a hybrid for 150 Energy: Frost Arc (Tesla + Cryo), Photon Lance (Railgun + Laser), Napalm Spitter (Flamer + Acid), Siege Battery (Missile + Mortar), Gunship Hangar (Pulse + Drone), Quake Engine (Sonic + Gravity), Storm Coil (Lightning + Tesla), Bio-Refinery (Harvester + Bio-Lab) |

All the numbers live in `data/tower_systems.json`.

**Commander kit** (all numbers in `data/commander_kit.json`):

| Key | Feature | How it works |
|---|---|---|
| R | Dash | A quick burst in the direction you're moving, with a moment of invulnerability (3 s cooldown) |
| V / B | Grenades | Throw the selected grenade at the mouse; B cycles type. Frag (damage), Cryo (60% slow) and EMP Cleanse (stuns aliens, strips shields, un-corrupts towers, knocks off Leeches). You start each sector with 2 Frags; more drop from aliens |
| Z | Mech suit | Charges from kills (60). For 15 s Vance takes 80% less damage, her blaster hits 4x harder and faster, and she stomps nearby aliens |
| (pickup) | Weapons | Shotgun, Sniper Rifle, Flamethrower and Rocket Launcher drop from aliens and replace the blaster for 30–40 s |
| (walk) | Ammo crates | A crate lands near the Core every wave. Walk over it, then walk up to a tower: it fires twice as fast for 15 s and repairs 30% |
| — | Drone buddy | Orbits Vance and shoots nearby aliens; it gets stronger as she levels up |
| (pickup) | Gear | Helmets (+range), armor (-damage taken) and boots (+speed, shorter dash cooldown) drop from elites and bosses in tiers 1–3 and equip automatically if better. Gear carries over between Siege Run fights |

A status strip above the HUD shows the weapon, grenade, mech charge, dash and gear.

**Economy** (`data/economy.json`):

- **Biomass** (green, under your Energy): every kill drops 1 (bosses 25) and Bio-Labs add more in their range. It pays for research.
- **Research:** the Research button by Start Wave. One project at a time (towers +HP, fire rate, range or damage, +Energy per wave, faster Orbital Strike, better sell refunds). It finishes after a few cleared waves and lasts the rest of the sector (the whole run in a Siege Run).
- **Interest** (Endless and Siege Run): +5% of unspent Energy after each wave, up to 50.
- **Insurance:** the Insure button (60 E, before a wave). Towers broken during the wave are rebuilt for free at the end and refund 25% of their value.
- **Black market:** see the Siege Run additions.

**Quality of life:** Backspace undoes the last tower placed this build phase (full refund);
Settings > Controls rebinds every key; a controller works (left stick moves, A wave, B
grenade, X repair, Y mech, RB dash, LB tab, RT Orbital Strike); Settings > Colorblind mode
swaps the good/bad and elite colors for a colorblind-safe palette; the main menu's TUTORIAL
button starts a guided Sector 1.

**Juice:** alien splats that fade over 20 s, debris and smoke from broken towers, slow
motion and a white flash when a boss dies, a pulsing red edge when the Core is under 20%,
radio callouts from Vance (new alien types, bosses, lost towers, low Core), and adaptive
music: without a `music.ogg`, a synthesized track plays whose bass and drums come in as
the threat rises.

**Siege Run additions** (`data/run.json`):

- **New nodes:** Rest (repair 40% of the Core, or train an augment so it stacks twice), Forge (merge two augments into an Epic/Legendary one), Gamble (blind relic for 40 Scrap with a 25% curse chance, or a Rare+ relic for 80), and Mini-boss (an elite fight capped by a Swarm Queenlet; relic + draft).
- **Relic sets:** Cryo Doctrine, Siege Protocol and Storm Network. Own all 3 pieces of a set for a bonus. Progress shows on the run map.
- **Boss relics:** after each boss, choose one of 3 powerful relics with a catch (e.g. Shattered Crown: +30% fire rate, Core max HP -30%).
- **Alien factions:** each run rolls Hive, Machine or Void, which shifts the alien mix of every fight.
- **Run-wide events:** each act can roll an event like Solar Flare (towers +20% damage, Vance takes double damage).
- **Hero decks:** every Commander and hero starts with their own tower cards (Ignis: Flamer + Tar Pit, Rime: Cryo + Chrono Spire...).
- **Supply Cache:** the debt merchant (+100 Scrap now, repay 150 after 2 nodes or lose 25 Core HP) and the black market (sells one of your relics for Scrap).
- **Seeds:** the run seed is shown on the map; SEED RUN on the main menu starts a run from a typed seed.

**Map mechanics** (`systems/map_features.py`):

- **Terrain:** high ground / rooftops (H tiles: +20% tower range), resource nodes (R: Harvesters there earn double), crystals (K: beam towers next to one hit 25% harder).
- **Gates and switches:** walk Vance onto a switch to close (or open) its gate and reroute the aliens. A gate that is the only way through won't close.
- **Teleporters:** pads that jump aliens ahead along the path; Vance can use them too.
- **Endless and Siege Run only** (the campaign plays as before):
  - **Overheat** on hot sectors (Magma Forge, Desert Outpost) and in the new **Heatwave** weather: towers heat up while firing (faster near vents) and shut down for 3 s at max heat. Cryo coverage, ice and neighboring rocks cool them. A heat bar shows under each tower.
  - **Destructible rocks:** splash damage (mortar shells, missiles, grenades, meteors) breaks rocks into new build space.
  - **Day/night:** an 80 s day and 40 s night. At night the map darkens except around towers, Vance and the Core, tower range drops 10%, and Cloakers move faster.
  - **Map events** (some waves from wave 4): supply drop, meteor shower (damages everything, leaves crystals), earthquake (moves rocks, stuns aliens, shakes towers), wildlife (critters that bite anyone nearby) and rising tide (tiles beside the path flood and shut down towers on them until the wave ends).

**New sectors** (campaign, Endless and Siege Run):

| Sector | Mechanic | Boss |
|---|---|---|
| 9 · Jungle | Vines overgrow a tower every 14 s (half fire rate) until Vance walks up to it; resource nodes | Hive Mind |
| 10 · Crystal Caves | Crystals boost beam towers; two teleporter pairs | Acid Leviathan |
| 11 · Ruined City | Rooftops (high ground) and a gate on the shortcut through the city | Fallen Commander |
| 12 · Gas Giant Station | Low gravity: mortar, missile, flak and acid get +25% range and splash; Vance slides; two lanes | Mothership |

**Game modes** (main menu > MODES, `systems/modes.py`):

| Mode | Rules |
|---|---|
| Boss Rush | All 10 bosses back to back with escorts, 800 Energy to start |
| Last Stand | Endless with no towers: just Vance, her grenades, the mech suit and Core upgrades |
| Weekly Challenge | Endless on the week's map with two odd rules (Tesla Only, Double Time, No Repairs, Inflation, Glass Core, Elite Storm, Trust Fund). Same for everyone that week |
| Sandbox | Unlimited Energy, waves only start when you press Space, Y opens a menu to spawn any alien |
| Puzzles | Choke Point, Air Defense, Armored Column: a fixed tower set, fixed Energy, a 1 HP Core, no Energy from kills |
| Hardcore (toggle) | Vance going down ends the game |
| Ascension (toggle) | Siege Run difficulty levels 1-6 (alien HP, Core HP, prices, elites, speed, fewer draft choices). Each win unlocks the next |
| Reverse | You are the hive (`systems/reverse.py`, `data/reverse.json`). Earn Biomass every second (and more for Core damage), send packs of aliens from the card bar (1-0, -, = or click), buy Growth (G, more income) and Evolve (V, more alien HP). An AI builds and upgrades towers, and answers flyers with anti-air. Break its Core within 6 minutes. Difficulty sets the AI's income |
| Local co-op (toggle) | A second Commander joins on the same screen with shared Energy and towers. Player 1: WASD + E. Player 2: arrow keys, Right Ctrl / Numpad 0 to repair, Right Shift / Numpad Enter to dash, or a controller. Player 2 has no grenades, mech or weapon pickups. In Hardcore the game ends when both are down |
| Story campaign (toggle, on by default) | Briefings before every campaign sector, radio chatter during it, a debrief after a win, a new final **Sector 13: The Hive Heart** (12 waves, Hive Queen at wave 6, the Architect at wave 12) and an ending. Esc skips a scene; Retry skips the briefing |

**Meta progression** (`systems/meta.py`, `data/meta.json`, saved in `save.json`):

- **Codex** (main menu > CODEX): Aliens (each entry unlocks on your first kill), Towers (with mastery), Profile stats, local Scores (top 10 per mode) and Achievements.
- **19 achievements**; five of them unlock Commander skins (Crimson, Gold, Shadow, Arctic, Royal), picked in Settings.
- **Tower mastery:** tower kills across every game. 100 / 500 / 2,000 kills give +3% / +6% / +10% damage, and level 3 unlocks that tower's tier-4 branches in Endless too.
- **Unlock progression:** Settings > "Unlock all sectors" (on by default). Turn it off to open sectors one by one by beating them.

**Wild ideas** (`systems/wild.py`):

- **Tame a pet (H):** walk Vance up to a non-boss ground alien under 35% HP and press H. It follows her and bites nearby aliens for the rest of the sector (the whole run in a Siege Run).
- **Brood Turret** (Control tab, alien tower): hatches tame Skitters that run back down the path biting aliens. Branches: Brute Hatchery, Swarm Nest.
- **Living Core** (Endless and Siege Run): aliens killed near the Core feed it. At 40 and 120 it evolves down the path of what it ate most: Carapace (less Core damage), Spore Launcher (shoots flyers) or Regrowth (heals after each wave).
- **Tower sacrifice (Delete):** destroys the selected tower for an Orbital Strike on its spot, stronger the more you'd spent on it. Its chips come back.
- **Map editor** (Play > Map Editor card): paint a 40x20 sector with 10 tile types and 10 themes, SAVE it to `mods/levels/`, PLAY it in Endless.
- **Mods folder:** a `mods/<name>.json` file is merged over `data/<name>.json` at startup, so a mod only lists what it changes (see `mods/README.txt`).

## Still to build

| Feature | Where |
|---|---|
| Playtesting and balance for all new content | Numbers live in `data/*.json` |
| Standalone EXE | Run `Build Standalone EXE.bat` again to include Phase 5 |
| Deferred ideas | itch.io release |
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
data/levels/sector1-13.json tile maps (40x20), waves, lanes, hive-wall events
data/story.json             Story campaign script (briefings, radio, debriefs, ending)
data/reverse.json           Reverse mode alien cards and AI settings
data/meta.json, puzzles.json  achievements, skins, mastery / puzzle setups
mods/                       JSON overrides merged over data/ and Map Editor levels
assets/sprites, assets/sounds   optional real art/sound (overrides placeholders)
game/
  settings.py               constants, palette, difficulty multipliers
  game_manager.py           window, fixed-timestep loop, save data
  core/                     EventBus, StateMachine, Timer, Health, PathFollower,
                            A*, SpatialHash, ObjectPool (no pygame, unit-testable)
  scenes/                   SceneManager + Menu, LevelSelect, Play, Pause, Win/Lose,
                            Story, Modes / Codex / Map Editor (extra_scenes.py), Siege Run screens
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

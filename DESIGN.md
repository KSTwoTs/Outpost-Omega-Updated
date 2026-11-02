# Outpost Omega: Endless & Roguelike Design

Oct 30, 2026 · Trenton McDonald · Updated Nov 1, 2026

Living version: https://claude.ai/artifact/RuWnHzqEDZ2rVH8YT4z4m7 (this file is a snapshot of it).

## Overview

Outpost Omega grows from a 3-sector campaign into a replayable game: an Endless mode first, then a roguelike Siege Run built on top of it, then batches of new towers, enemies and maps. Phases 1–4 are done; Phase 5 (a large expansion) is in progress.

The base game already has 3 sectors of 10 waves, 5 towers with 3 tiers, 6 enemies including the Hive Overseer boss, Commander Vance, a loot table and a 3-star rating. Stats live in JSON, systems talk over the EventBus, and enemies route with A*. Most additions are new JSON entries plus one new system each.

**Goals**

- Runs that play differently every time
- A reason to come back: high scores, unlocks, meta progression
- Keep the campaign working exactly as it does today

## Endless mode

Endless mode generates waves forever from a growing threat budget, and the score is the wave you reach.

**Wave generator.** Each enemy gets a `threat` cost in `enemies.json`. Wave *n* gets a budget of roughly 12 × 1.12^(n−1). The generator spends it on enemies the wave has unlocked, in 1–3 groups, with per-enemy weights so Saboteurs stay rare, and feeds the result to the existing `WaveSystem` queue.

| Enemy | Threat | Unlocks at wave |
| --- | --- | --- |
| Skitter | 1 | 1 |
| Glider | 3 | 3 |
| Saboteur | 4 | 5 |
| Brood Sac | 4 | 6 |
| Brute | 6 | 4 |
| Hive Overseer (boss) | n/a | every 10th wave |

**HP scaling.** Past wave 10, enemy HP grows 5% per wave (compounding), on top of the difficulty multiplier. Rewards grow more slowly, so the economy stays tight.

**Mutators.** Every 5th wave rolls one modifier, shown in the HUD before the wave starts:

- *Swarm*: twice as many enemies, each with 60% HP
- *Armored Tide*: +3 armor on everything
- *Blitz*: +30% speed
- *Air Raid*: Gliders replace 40% of the ground units
- *Blackout*: towers lose 20% range

**Bosses.** Every 10th wave adds a boss on top of its budget. For now that is the Overseer with +50% HP each time; new bosses join the rotation later.

**Elite affixes.** From wave 12, each enemy has a chance (growing per wave, capped at 35%) to spawn as an elite with one affix, drawn with a colored ring and a name tag:

| Affix | Effect |
| --- | --- |
| Hasted | +40% speed |
| Armored | +4 armor |
| Regenerating | Heals 3% max HP per second |
| Shielded | Absorbs the first 30% of max HP as shield |
| Volatile | Explodes on death, damaging nearby towers |
| Vampiric | Heals when it damages towers or the Commander |

Elites have 2× HP and give 2× reward and score.

**Quality of life.** 1× / 2× / 3× game speed (F key), a next-wave preview in the HUD, and the best wave per sector saved in `save.json`.

## Roguelike layer: Siege Run

A Siege Run is a sequence of endless-style encounters where you draft your loadout as you go, and every run earns Salvage for permanent unlocks.

**Run structure.** A branching sector map in the style of Slay the Spire, 7 floors per act and 3 acts. Core HP carries over between sectors; Energy resets:

- *Combat*: 3 generated waves on a random sector
- *Elite*: 3 waves where 60%+ of aliens are elites; drops a relic
- *Supply Cache*: shop for towers, relics and Core repairs
- *Event*: a short choice ("A crashed drone: repair it for 100 energy?")
- *Boss*: ends the act

**Augment draft.** After each combat node, pick 1 of 3 augments. Examples: Tesla chains +2; Cryo-slowed enemies take +25% damage; Orbital Strike cooldown −40%; every 10th kill drops an Energy Crystal.

**Tower cards.** A run starts with Pulse plus one random tower. Other towers enter through drafts and shops, so no two runs build the same way.

**Tier-4 branches (run only).** Each tower gets two tier-4 options. Railgun becomes *Overpenetrator* (unlimited pierce) or *Executioner* (kills enemies below 15% HP). Tesla becomes *Storm Spire* (hits every enemy in range) or *Arc Battery* (stores charge, releases one huge chain).

**Cursed relics.** Big upside with a catch: "+50% tower damage, Core max HP halved"; "Towers cost 30% less, selling refunds nothing".

**Meta progression.** Runs pay out *Salvage* based on nodes cleared. Salvage buys permanent nodes on a Command Tech tree: starting energy, Commander perks, and new towers and relics added to the draft pool.

## New towers and elemental combos

Eight new towers fill roles the current five leave open: damage over time, economy, path blocking and support.

| Tower | Behavior | Role |
| --- | --- | --- |
| Flamer | Short cone that applies Burn | Strong against swarms, weak against armor |
| Mortar | Large splash, minimum range, ground only | Placement puzzle |
| Drone Bay | Launches 2–3 drones that chase enemies | Anti-air |
| Gravity Well | Pulls enemies back along the path every few seconds | Combos with splash |
| Barricade | Placed on the path; aliens stop and chew through it, Vance can repair it | Buys time |
| Harvester | Produces energy each wave, no attack | Economy vs. defense |
| Radar Relay | +15% range to nearby towers, reveals cloaked enemies | Support |
| Mine Layer | Drops proximity mines on nearby path tiles | Burst damage |

**Elemental combos.** Status effects stack into reactions, which rewards mixing towers:

- Frozen + Railgun = *Shatter*, a guaranteed critical hit
- Burning + Missile = *Detonate*, extra splash
- Slowed + Tesla = *Conduct*, +2 chain jumps

## New enemies and bosses

Each new enemy counters a specific strategy, so no single build wins every run.

| Enemy | Behavior | Counters |
| --- | --- | --- |
| Burrower | Dives underground for part of the path, untargetable there | Towers stacked on one stretch |
| Cloaker | Invisible unless a Radar Relay or Vance is nearby | Ignoring the Commander |
| Mender | Heals nearby aliens | Slow, low-DPS builds |
| Shield Drone | Flies and projects a bubble over ground units | Ground-only towers |
| Spitter | Stops at range and shoots towers | Skipping repairs |
| Juggernaut | Immune to slow | Cryo-heavy builds |
| Hunter | Targets Vance instead of the Core | Careless Commander play |
| Mimic | Looks like an item drop, bites when collected | Greedy looting |
| Carrier | Large flyer that drops Gliders mid-air | Thin anti-air |

**Bosses**

- *Burrow Wyrm*: tunnels and surfaces at random path points
- *Siege Titan*: crushes any tower next to the path as it walks
- *Hive Queen*: lays egg sacs that hatch unless you destroy them

## New maps and weather

Five new sectors each add one mechanic the current three don't have.

| Sector | Mechanic |
| --- | --- |
| 4 · Orbital Platform | Conveyor tiles push Vance and enemies; airlocks open and close to switch lanes |
| 5 · Magma Forge | Lava vents erupt on a timer and disable nearby towers |
| 6 · Derelict Ship | Fog of war; towers emit light, enemies outside it can't be targeted |
| 7 · Open Plains | No path; enemies A* around your towers, so you build the maze |
| 8 · Twin Cores | Two Cores to defend; Vance is the swing defender |

**Weather** can sit on top of any map: sandstorm (−20% range), blizzard (extra ice tiles), acid rain (towers slowly lose HP).

**Procedural maps** for Endless and Siege Run: random-walk a path from S to C on the 40×20 grid, then scatter blocked and hazard tiles, rejecting layouts with a path that is too short.

## Other mechanics

- **Commander classes:** Engineer (faster repair, can place a mini-turret), Vanguard (shotgun and dash), Tactician (a second ability such as Supply Drop or Cryo Grenade)
- **Commander leveling:** Vance earns XP from kills during a run and picks a perk at each level
- **Tower veterancy:** towers gain small bonuses from kills, which rewards keeping them alive
- **Interest:** +5% of unspent energy after each wave, capped, as a risk/reward choice
- **Core upgrades:** spend energy on Core turrets, a shield, or HP regeneration
- **Daily seed:** the same endless run for everyone that day, with a local score log

## Phase 4: More towers, branches and heroes (done)

Four towers that fill the remaining gaps (ramping damage, armor stripping, repair and crowd control), a tier-4 branch for every tower, and heroes for Endless and Siege Run.

| Tower | Behavior | Role |
| --- | --- | --- |
| Laser Lance | Continuous beam whose damage ramps the longer it holds one alien | Boss and tank killer |
| Acid Spitter | Lobs acid that pools on the path, melting aliens and stripping armor | Anti-armor |
| Repair Bay | No attack; repairs towers in range, broken ones included | Support |
| Sonic Disruptor | Shockwaves hit every ground alien in range and stun them | Crowd control |

**Tier-4 branches for every tower** (Siege Run): Flamer (Dragon's Breath / Napalm Sprayer), Mortar (Siege Cannon / Rapid Battery), Gravity Well (Singularity / Stasis Field), Harvester (Energy Refinery / Overflow Core), Radar Relay (Targeting Uplink / Overwatch Array), Drone Bay (Drone Swarm / Gunship Wing), Barricade (Bulwark Wall / Shock Barricade), Mine Layer (Minefield / Cluster Charges), Laser Lance (Prism Lance / Annihilator), Acid Spitter (Corrosive Bath / Toxic Flood), Repair Bay (Nanite Forge / Overclock Station), Sonic Disruptor (Earthshaker / Resonance Cannon). Every tier and branch has its own look.

**Heroes** (Endless and Siege Run): Ignis (fire), Rime (frost), Bastion (defense), Kestrel (drones and mines), Ledger (economy) and Hawk (sniper), each with their own palette.

**More depth:** 18 Commander perks (10 new, e.g. Second Wind, Wide Strike, Tower Tuning); three more Core upgrades, Reactor (+15/30/50 Energy a wave), Nova (shockwave every 10 s) and Plating (+20/40/70 Core max HP); and a Tech Lab of 20 upgrades, most with several ranks.

## Phase 5: Expansion (in progress)

Added Nov 1, 2026. The next batch of content and systems, picked from a brainstorm. Nothing here is built yet; numbers are starting points for tuning.

### New towers

| Tower | Behavior | Role |
| --- | --- | --- |
| Shield Projector | Bubble over nearby towers that soaks Spitter acid, Volatile blasts and Titan stomps | Protection |
| Decoy Beacon | Hologram of Vance or the Core that draws Hunters and pathing aliens | Misdirection |
| Plasma Fence | Two pylons with a damaging beam between them, aimed across the path | Placement puzzle |
| Chrono Spire | Every few seconds rewinds one alien a few seconds back along the path | Stalling |
| Mirror Array | Bends Railgun and Laser Lance beams around corners | Beam support |
| Flak Cannon | Anti-air only, strong burst | Anti-air |
| Ion Cannon | Charges about 20 s, then one huge shot down the whole path | Burst |
| Hacker Spire | Turns one alien to your side for a few seconds | Control |
| Magnet Coil | Strips armor; slightly slows Juggernauts (soft counter to their immunity) | Anti-armor |
| Tar Pit | Placed on the path; slows ground aliens; Flamer hits ignite it | Combo |
| Lightning Rod | Stores charge during weather and releases it as damage | Weather payoff |
| Bio-Lab | Harvests alien corpses for Biomass | Economy |
| Overclocker | Doubles adjacent towers' fire rate, but they slowly take damage | Risky support |
| Uplink Dish | Second Orbital Strike charge, or cooldown cut per kill in range | Commander support |
| Bait Pod | Cheap tower aliens prefer to attack | Tank |

### Tower systems

- **Adjacency bonuses:** specific pairs buff each other (e.g. Cryo next to Railgun), so clusters are planned
- **Power grid:** towers draw power from generators; Saboteurs and vents can hit the grid itself
- **Tower sockets:** augment chips placed into individual towers instead of global upgrades
- **Relocate:** move a tower during the build phase for a fee, without selling it
- **Named veterans:** max-rank towers get a random name and a special trait
- **Tower fusion:** combine two max-tier towers into a hybrid (e.g. Tesla + Cryo = Frost Arc)
- **Stance toggle:** each tower switches between Focus (single target) and Suppress (spread or slow)

### New enemies

| Enemy | Behavior | Counters |
| --- | --- | --- |
| Adaptive | Gains resistance to whichever damage type hits it most | One-damage-type builds |
| Thief | Grabs Energy and runs back to spawn; killing it returns the Energy | Leaky defenses |
| Leech | Latches onto a tower and drains it until Vance knocks it off | Ignoring the Commander |
| Phaser | Teleports a few tiles ahead along the path | Towers stacked at one choke |
| Reflector | Bounces projectiles back; beams get through | Projectile-only builds |
| Swarm Mind | Stronger for every alien near it | Weak splash |
| Necro-Spore | Raises recently dead aliens as weaker zombies | Slow cleanup |
| Infector | Corrupts a tower so it shoots your towers until repaired | Skipping repairs |
| Blob | Absorbs aliens it touches and grows | Letting groups bunch up |
| Bomber | Flyer that bombs towers instead of heading for the Core | Thin anti-air |
| Jammer | Disables Vance's abilities nearby | Ability-reliant play |
| Artillery Grub | Shells towers from outside their range | Short-range builds |
| Pathcutter | Digs a new shortcut through terrain mid-wave | Building for one route |
| Swarm Queenlet | Mini-boss whose escort buffs the whole group | Single-target builds |

### New bosses

- **Mothership:** floats across the map over several phases, dropping waves
- **Hive Mind:** three bodies share one HP bar; ones not killed close together revive
- **Fallen Commander:** an infected copy of Vance with his abilities and a dodge roll
- **Acid Leviathan:** surfaces from acid pools and drags towers under
- **Nest Heart:** stationary; you push out and destroy it while waves keep coming
- **Architect:** rebuilds the path every phase

### Commander

- Dodge roll / dash
- Weapon pickups: shotgun, sniper rifle, flamethrower, rocket launcher
- Grenade slot: frag, cryo, EMP-cleanse
- **Mech suit ultimate:** charges from kills, 15 s as a tank
- **Carry system:** haul an ammo crate to a tower for a temporary boost
- **Drone buddy:** levels up alongside Vance
- **Gear loadout:** helmet, armor and boots slots, with drops from elites
- Unlockable Commander skins and palettes

### Game modes

- **Local co-op:** a second Commander on a controller or arrow keys
- **Boss Rush:** every boss back to back
- **Puzzle mode:** fixed Energy, fixed waves, one correct solution
- **Last Stand:** no towers; only Vance and Core upgrades
- **Reverse mode:** play as the aliens, spending a threat budget against an AI defense (reuses the wave generator)
- **Ascension levels:** stacking difficulty modifiers after beating a Siege Run
- **Weekly Challenge:** fixed odd rules ("Tesla only, double speed, no repairs")
- **Hardcore:** Vance's death ends the run
- **Sandbox:** unlimited Energy and an alien spawn menu
- **Story campaign:** radio chatter, short cutscenes and a reason for every sector

### Siege Run additions

- **Rest node:** repair the Core or upgrade one augment
- **Forge node:** merge two augments into a stronger one
- **Gamble node:** spend Scrap on a blind relic
- **Mini-boss node:** between Elite and Boss, with a choice of rewards
- **Relic sets:** 3 relics of a set (e.g. Cryo Doctrine) grant a set bonus
- **Boss relics:** swap a starting perk for a powerful, risky one
- **Alien faction per run:** Hive, Machine or Void, each with its own enemy mix
- **Shareable run seeds**
- **Hero starting decks:** each hero begins with their own tower cards
- **Run-wide events:** e.g. "Solar flare: towers +20% damage, Vance takes double damage this act"
- **Debt merchant:** take a loan now, repay with interest later

### Maps and environment

- **High ground:** raised tiles give towers extra range
- **Overheat (hot maps only):** on hot sectors and in heat weather, towers build heat while firing and shut down for a few seconds at max heat. Cryo towers, ice tiles and shade cool them. Applies to Magma Forge (strongest near the vents), Desert Outpost in Endless and Siege Run, and a new **Heatwave** weather that can roll on any map. Off everywhere else, so cool maps stay as they are
- **Destructible terrain:** Missiles can open new build space
- **Day/night cycle:** Cloakers stronger at night; towers get spotlights
- **Rising tide:** water or lava climbs during a wave and floods low tiles
- **Switches and gates:** Vance flips them mid-wave to reroute aliens
- **Teleporter pads:** usable by aliens and Vance
- **Supply drops:** crates land mid-wave for Vance to grab
- **Meteor showers:** damage everything and leave crystal deposits
- **Neutral wildlife:** attacks whoever gets close
- **Resource nodes:** Harvesters only work on these tiles
- **Earthquake event:** rearranges part of the map
- **New sectors:** Jungle (vines overgrow towers), Crystal Caves (beams refract), Ruined City (build on rooftops), Gas Giant Station (low gravity, arcing projectiles)

### Economy

- **Biomass:** a second resource from kills, spent on special upgrades
- **Interest:** +5% of unspent Energy after each wave, capped
- **Black market:** sell relics or towers for big Scrap
- **Insurance:** pay up front for refunds on destroyed towers
- **Research queue:** unlocks that complete over several waves

### Progression and meta

- **Achievements** (e.g. "Beat Sector 7 without a light tower")
- **Codex / Bestiary:** alien lore and stats unlocked by kills
- **Tower mastery:** towers level across runs, unlocking skins and branch options
- **Profile stats:** total kills, favorite tower, the alien that ended the most runs
- **Local leaderboards** per mode and per daily seed
- **Unlock progression** turned back on, with goals worth chasing

### Quality of life

- **Undo** the last placement during the build phase
- **Post-wave stats:** damage and kills per tower, and towers that did nothing
- **Key rebinding and controller support**
- **Colorblind mode** for elite rings and rarity colors
- **Settings menu:** volume, screen shake, particle intensity
- **Interactive tutorial**
- **Wave timeline:** the next 5 waves, mutators and bosses at a glance
- **Hover tooltips** explaining combos (Shatter, Detonate, Conduct)

### Juice and feel

- **Adaptive music** that intensifies with threat (needs the base track first)
- **Boss kills:** slow motion and a big flash
- **Persistent goo splats** that fade over time
- **Tower destruction:** debris and smoke
- **Radio chatter:** Vance calls out threats ("Brute incoming!")
- **Close-call effects:** red screen tint below 20% Core HP

### Wild ideas

- **Tame an alien** as a pet that fights for you
- **Alien towers:** captured aliens become towers (e.g. a Brood Sac turret that spits Skitters)
- **Living Core** that evolves based on what you feed it during a run
- **Sacrifice** a tower for an instant Orbital Strike
- **Map editor and mod folder** built on the existing JSON data
- **Release** a free build on itch.io

## Roadmap

Endless mode ships first because the roguelike runs on its wave generator, and new content then drops straight into both modes.

1. **Phase 1 · done — Endless foundation:** wave generator and threat budget, mutators and boss waves, elite affixes, game speed and wave preview
2. **Phase 2 · done — Siege Run:** augment drafts, tower cards and tier-4 branches, relics and sector map, Salvage and tech tree
3. **Phase 3 · done — Content batches:** towers and combos, enemies and bosses, sectors and weather, Commander classes
4. **Phase 4 · done — More towers, branches and heroes:** Laser Lance, Acid Spitter, Repair Bay, Sonic Disruptor, tier-4 branches for every tower, six heroes, more perks, Core upgrades and Tech Lab
5. **Phase 5 · in progress — Expansion:** towers and tower systems, enemies and bosses, Commander kit, new modes, Siege Run nodes, maps, economy, meta progression, QoL and polish (see *Phase 5: Expansion*)

**Phase 1 tasks**

- [x] `threat` and `unlock_wave` on every enemy in `enemies.json`
- [x] `data/endless.json` for the budget curve, mutators and affixes
- [x] Endless wave generator plugged into `WaveSystem` (`game/systems/endless.py`)
- [x] Elite affixes on enemies, drawn with a ring and tag
- [x] Endless button in Level Select, best wave saved per sector
- [x] 1× / 2× / 3× game speed (F key) and a next-wave preview in the HUD
- [ ] Playtest and tune the budget curve and elite chance in `endless.json`

**Phase 2 tasks**

- [x] Siege Run map: 3 acts of 7 floors with Combat, Elite, Supply Cache, Event and Boss nodes
- [x] Augment drafts after every win (24 augments in `data/run.json`)
- [x] Tower cards: start with Pulse plus 1 random attacking tower, unlock the rest during the run
- [x] Relics, including 4 cursed ones
- [x] Supply Cache shop and 6 events
- [x] Salvage and a Command Tech Lab with 8 permanent upgrades (`data/tech.json`)
- [x] Tier-4 tower branches: 2 per original tower, chosen from an in-game panel
- [x] A run in progress is saved to `save.json` and resumes after a restart
- [ ] Playtest and tune rewards, prices and node difficulty

**Phase 3 tasks**

- [x] 8 new towers: Flamer, Mortar, Gravity Well, Harvester, Radar Relay, Drone Bay, Barricade, Mine Layer (HUD holds 13; keys 1–0, -, =, \\)
- [x] Elemental combos: Shatter, Detonate, Conduct
- [x] 9 new enemies: Mender, Juggernaut, Cloaker, Burrower, Spitter, Shield Drone, Hunter, Mimic, Carrier
- [x] 3 new bosses: Siege Titan, Hive Queen, Burrow Wyrm (Endless rotates all four; Siege Run has one per act)
- [x] 5 new sectors: Magma Forge, Open Plains, Orbital Platform, Derelict Ship, Twin Cores
- [x] Procedural maps: the Uncharted card in Endless, plus random nodes in Siege Run
- [x] Weather in Endless and Siege Run: sandstorm, blizzard, acid rain
- [x] Commander classes: Vanguard, Engineer, Tactician
- [x] Commander leveling: XP from kills, pick 1 of 3 perks per level (carries over in a Siege Run)
- [x] Tower veterancy: +6% damage per rank at 10 / 30 / 75 kills
- [x] Core upgrades: click the Core to buy a turret, a shield or regeneration
- [x] Daily Challenge: one generated map per day, same waves and weather for everyone, best wave saved
- [ ] Playtest and balance everything

**Phase 4 tasks**

- [x] 4 new towers: Laser Lance, Acid Spitter, Repair Bay, Sonic Disruptor (keys Z, C, V, B)
- [x] Tier-4 branches for all 12 remaining towers, each with its own art
- [x] 6 heroes for Endless and Siege Run: Ignis, Rime, Bastion, Kestrel, Ledger, Hawk
- [x] 10 new Commander perks (18 total)
- [x] Core upgrades: Reactor, Nova, Plating
- [x] Tech Lab expanded to 20 upgrades with ranks
- [ ] Playtest and balance

**Phase 5 tasks** (in progress)

- [ ] 15 new towers: Shield Projector, Decoy Beacon, Plasma Fence, Chrono Spire, Mirror Array, Flak Cannon, Ion Cannon, Hacker Spire, Magnet Coil, Tar Pit, Lightning Rod, Bio-Lab, Overclocker, Uplink Dish, Bait Pod
- [ ] Tower systems: adjacency bonuses, power grid, sockets, relocate, named veterans, fusion, stance toggle
- [ ] 14 new enemies: Adaptive, Thief, Leech, Phaser, Reflector, Swarm Mind, Necro-Spore, Infector, Blob, Bomber, Jammer, Artillery Grub, Pathcutter, Swarm Queenlet
- [ ] 6 new bosses: Mothership, Hive Mind, Fallen Commander, Acid Leviathan, Nest Heart, Architect
- [ ] Commander: dash, weapon pickups, grenades, mech suit, carry system, drone buddy, gear loadout, skins
- [ ] Modes: local co-op, Boss Rush, Puzzle, Last Stand, Reverse, Ascension, Weekly Challenge, Hardcore, Sandbox, Story campaign
- [ ] Siege Run: Rest, Forge, Gamble and Mini-boss nodes; relic sets; boss relics; factions; seeds; hero decks; run-wide events; debt merchant
- [ ] Maps: high ground, overheat on hot maps plus Heatwave weather, destructible terrain, day/night, rising tide, switches and gates, teleporters, supply drops, meteors, wildlife, resource nodes, earthquakes
- [ ] 4 new sectors: Jungle, Crystal Caves, Ruined City, Gas Giant Station
- [ ] Economy: Biomass, interest, black market, insurance, research queue
- [ ] Meta: achievements, Codex, tower mastery, profile stats, local leaderboards, unlock progression back on
- [ ] QoL: undo placement, post-wave stats, rebinding and controller, colorblind mode, settings menu, tutorial, wave timeline, combo tooltips
- [ ] Juice: adaptive music, boss-kill slow-mo, goo splats, tower destruction, radio chatter, low-Core tint
- [ ] Wild ideas: tameable alien pet, alien towers, Living Core, tower sacrifice, map editor and mod folder, itch.io release

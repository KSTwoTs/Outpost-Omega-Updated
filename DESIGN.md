# Outpost Omega: Endless & Roguelike Design

Oct 30, 2026 · Trenton McDonald

Living version: https://claude.ai/artifact/RuWnHzqEDZ2rVH8YT4z4m7 (this file is a snapshot of it).

## Overview

Outpost Omega grows from a 3-sector campaign into a replayable game: an Endless mode first, then a roguelike Siege Run built on top of it, then batches of new towers, enemies and maps.

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

## Roadmap

Endless mode ships first because the roguelike runs on its wave generator, and new content then drops straight into both modes.

1. **Phase 1 · done — Endless foundation:** wave generator and threat budget, mutators and boss waves, elite affixes, game speed and wave preview
2. **Phase 2 · done — Siege Run:** augment drafts, tower cards and tier-4 branches, relics and sector map, Salvage and tech tree
3. **Phase 3 · done — Content batches:** towers and combos, enemies and bosses, sectors and weather, Commander classes

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

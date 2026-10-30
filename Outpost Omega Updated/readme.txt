OUTPOST OMEGA: ALIEN SIEGE
CPSC 4160 - Milestone 2 (Working Draft)
Trenton McDonald - Individual Project

==========================================================================
HOW TO RUN
==========================================================================
Requires Python 3.10+ and pygame-ce (or classic pygame 2.x - install only one).

    pip install -r requirements.txt
    python main.py

Run main.py from inside the Outpost Omega folder.

==========================================================================
CONTROLS
==========================================================================
WASD / Arrow keys ... Move Commander Vance (auto-fires at the closest alien)
E (hold) ............ Repair a nearby damaged or EMP'd tower
Q, then click ....... Orbital Strike (1 s delay, 45 s cooldown); right-click cancels
1-5 / HUD buttons ... Choose a tower; click a green tile to build
Shift + click ....... Build several towers of the same type
Click a tower ....... Select it (Upgrade / Sell / Targeting buttons appear)
Right-click tower ... Upgrade it
U / X / T ........... Upgrade / Sell (70% refund) / cycle targeting mode
Space ............... Start the next wave early
Esc or P ............ Pause
F1 .................. Debug overlay (waypoints, ranges, spatial hash, hitboxes,
                      boss pixel-mask outline)

==========================================================================
ITEMS DEVELOPED
==========================================================================

Task 1: Core Engine and Architecture
  - GameManager with a fixed-timestep game loop (60 updates/sec,
    independent of frame rate) and OnStart / OnUpdate / OnRender hooks
  - SceneManager using a scene stack: Menu, Level Select, Play,
    Pause (overlay), Win and Lose screens
  - EventBus so systems communicate through events instead of
    direct calls (enemy_killed, enemy_reached_core, item_collected, ...)
  - Reusable components: Health (with armor), StateMachine, Timer and
    Cooldown, PathFollower
  - Data-driven design: towers.json, enemies.json, items.json and
    levels/sector1.json hold all stats, waves and the map
  - Save system (save.json): best stars and score per sector,
    sector unlocks, last difficulty

Task 2: Player Character - Commander Rhea Vance
  - InputSystem that maps keys and mouse to named Commands
  - 8-direction movement with acceleration, max speed and
    friction (Vector2 velocity, lower friction on ice tiles)
  - Tile collision with axis-separated AABB resolution (slides along
    rocks, towers and the Core)
  - Finite state machine: Idle, Move, Shoot, Repair, Downed
  - Auto-blaster: targets the closest alien within 160 px, 4 shots/sec,
    with lead targeting
  - Repair ability (hold E) restores tower HP over 2 seconds
  - Orbital Strike: aim, 1 s delay, splash damage with falloff,
    knockback, screen shake, 45 s cooldown
  - Downed at 0 HP, respawns at the Core after 5 s

Task 3: Towers (all 5 from Milestone 1)
  - Grid placement with green/red preview, range circle and checks
    (buildable tile, Commander not in the way, path not blocked)
  - Targeting priorities: first, last, strongest, closest
  - 3 upgrade tiers per tower loaded from towers.json; selling refunds 70%
  - Towers have HP; disabled when EMP'd or broken until repaired
  - Pulse Turret: fast single-target shots with lead targeting
  - Tesla Coil: chain lightning jumping between enemies (jittered
    lightning effect, brief stun)
  - Cryo Emitter: slows all enemies in range by 40% (cryo tint)
  - Railgun: piercing beam that hits every ground enemy on the line
    and ignores armor (segment-vs-circle test)
  - Missile Battery: homing missiles with a turn-rate limit and
    splash damage; can hit flyers

Task 4: Enemies (all 6 from Milestone 1)
  - Enemy base class + subclasses, stats from enemies.json
  - Finite state machine: Walk, Attack, Stunned, Dying
    (subclasses add their own states)
  - Armor rule: damage = max(1, damage - armor)
  - Status effects stored as timers: slow, stun, burn
  - Skitter: fast, low HP, comes in swarms
  - Brute: slow, armored, heavy Core damage
  - Glider: flies straight at the Core using seek steering, ignores the path
  - Brood Sac: bursts into 3 Skitters on death
  - Saboteur: stops near towers, charges, then EMPs them
    (disables for 3 s and damages them)
  - Hive Overseer (boss, final wave): summons Skitters every 8 s,
    raises an invulnerable shield at 66% and 33% HP, boss HP bar;
    pixel-perfect hit detection with pygame.mask (shield bubble blocks
    shots while it is up)
  - Ground enemies attack the Commander when she blocks their route

Task 5: Levels and Waves
  - Tile map loader for a 40x20 grid of 32 px tiles (path,
    buildable, blocked, spawn, core; ice/acid/hive-wall tile types
    supported)
  - A* pathfinding (Manhattan heuristic) builds each enemy route from
    the painted path tiles and checks that tower placement never blocks it
  - Multiple spawn lanes: waves choose which lane each group enters from
  - Tile map drawn once to a cached Surface
  - WaveSystem: build phase (15 s countdown or Space) -> wave phase,
    spawn queue ordered by time with heapq
  - Sector 1 - Desert Outpost: tutorial sector, one winding path,
    10 scripted waves with the boss on wave 10
  - Sector 2 - Frozen Relay Station: two lanes (top and left) that merge
    before the Core; ice patches make the Commander slide (low friction)
  - Sector 3 - Hive Crash Site: acid pools damage the Commander; hive
    walls grow and recede during waves (scripted wall events), A*
    recomputes the route and every alien already walking is rerouted
    from where it stands; branching path; boss on wave 10
  - Per-sector visual themes (desert, frozen, hive), starting Energy and
    enemy HP scaling so difficulty ramps by sector
  - All three sectors are unlocked on Level Select for this milestone
  - Difficulty: enemy HP x (1 + 0.15 x wave), plus
    Easy / Normal / Hard multipliers

Task 6: Items and Economy
  - Energy economy: start with 250 E, earn from kills and crystals
  - Weighted loot table drops on enemy death
  - Energy Crystal (+25 E), Repair Kit (heals a tower 40%),
    Overcharge Cell (tower fires 2x faster for 10 s), Shield Battery (+10 Core HP)
  - Items bob and glow and stay on the map until the next wave starts
    (they blink for the last 3 s of the build countdown); collected by
    walking over them or clicking (generous click area)
  - Scoring (kills + leftover Energy) and 1-3 star rating from Core HP

Task 7: Collision and Physics
  - Spatial hash broad phase (64 px cells) rebuilt every frame
  - Circle-vs-circle narrow phase using squared distances (no sqrt)
  - pygame.mask narrow phase for the Hive Overseer's irregular shape:
    bullets and splash use a circle mask vs. the boss sprite mask
    (mask.overlap), railgun beams are sampled along the line; masks are
    built from the current sprite frame (flipped when it faces left) and cached
  - Lead targeting by solving for the projectile intercept point
  - Homing steering with a turn-rate limit; splash falloff and knockback
  - Object pooling for projectiles and particles

Task 8: Graphics, Effects, UI and Audio
  - AssetManager: loads PNGs from assets/sprites if present, otherwise
    generates placeholder pixel-art sprites in code; caches rotated,
    flipped and tinted versions
  - Pooled particle system: explosions, sparks, alien goo, muzzle flashes
  - Screen shake, hit flash, floating damage numbers, red flash on Core
    hits, lightning bolts, railgun beams, EMP and shield rings
  - HUD bar: Core HP, Energy, score, tower build buttons, selected-tower
    panel, wave info, Commander HP and Orbital cooldown, boss HP bar
  - Toast messages and wave banners; menu starfield; level select with
    a mini-map thumbnail; F1 debug overlay
  - AudioSystem: loads sounds from assets/sounds if present, otherwise
    synthesizes placeholder sound effects; music hook

==========================================================================
WORK IN PROGRESS / NEXT STEPS
==========================================================================
  - Restore sector-unlock progression (code is in place, turned off
    for the demo)
  - Final sprite art, music and sound effects (placeholders now)
  - Balancing across all sectors

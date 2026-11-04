Outpost Omega mods folder
=========================

Any file here named like a file in data/ (towers.json, enemies.json, endless.json, run.json,
economy.json, meta.json, ...) is merged over the original when the game starts. A mod only
needs the keys it changes. Example mods/towers.json:

    {"pulse": {"cost": 40}, "tesla": {"description": "Cheap and cheerful"}}

Lists (like a tower's "tiers") are replaced whole, not merged.
Delete or rename a file to turn the mod off. Bad files are skipped (see the console).

mods/levels/ holds maps saved from the Map Editor (Play > Map Editor). They are normal
level files, so you can share them: drop someone's custom_N.json in here and open it with
LOAD in the editor.

# Non-Steam games (branch `non-steam-games`, work in progress)

From GitHub issue: games from GOG, Epic etc. (here via the Unifideck plugin) should show up in the game list.
This file is the handoff between sessions; delete it before merging into main.

## Approach

Read where stores installed their games instead of crawling drives, so the list stays as fast as Steam's (each game
folder costs one shallow `scan_folder`, as a Steam game does).

| Source | Read from | Id in the plugin |
|---|---|---|
| Steam | `appmanifest_*.acf` (unchanged) | Steam app id |
| Unifideck | `~/.local/share/unifideck/games.map`: `store:id=<exe>\t<work dir>\t<signed shortcut appid>` | `unifideck:<store:id>` |
| Steam shortcuts ("Add a non-Steam game") | `~/.local/share/Steam/userdata/*/config/shortcuts.vdf` (binary KeyValues), only shortcuts whose Exe is an existing `.exe` | `shortcut:<unsigned appid>` |
| Added folders | panel button "Add game folder" (Decky's folder picker), stored in settings `custom_games` | `folder:<sha1 of path, 12 chars>` |

A folder listed by several sources keeps the first (Steam, Unifideck, shortcut, added folder).

## Safety boundary

`inside_library()` decides which files the plugin may change. `game_roots()` = Steam libraries' `common` folders plus
each non-Steam game's own folder (never a parent). `safe_game_folder()` refuses `/`, the home folder, a Steam
`common` folder and a whole drive (`/run/media/<user>/<drive>`). Added folders must contain an `.exe` (in the folder
or one level down).

## Done (on the Mac, commit on this branch)

- Backend (`main.py`): `read_binary_vdf`, `steam_shortcuts`, `unifideck_games`, `shortcut_games`, `custom_games`,
  `all_games`, `safe_game_folder`, `game_roots`, `steam_appid` (Steam-only lookups: process env, localconfig,
  downloads), `game_last_played` (shortcut LastPlayTime for non-Steam games). Plugin methods `add_custom_game`,
  `remove_custom_game`, `home_dir`. `list_games`, `_game`, `_guard`, `get_game` use `all_games()`.
- Panel (`src/index.tsx`): source tag in the game list ("· Unifideck", "· non-Steam", "· added folder"), "Add game
  folder" (folder picker) under Rescan, the game's folder and "Remove from the list (files stay)" for added folders,
  launch options use the shortcut's appid for non-Steam games.
- Tested with a stand-in home folder: shortcuts.vdf written in binary KV, a games.map, added folders (home, `/`, no
  exe refused), boundary (listed game folders allowed, others not), removal.

## To do / check on the Deck

1. Real Unifideck: does `games.map` exist at that path, do work dirs point at the game folders, do names come from
   the shortcuts? (Its format was read from Unifideck's source, `py_modules/unifideck/utils/paths.py`,
   `DEFAULT_GAMES_MAP`; a custom `paths.games_map` in its config isn't followed yet.)
2. Real shortcuts.vdf: parsing on the Deck (several users, odd types), and that launcher shortcuts (Heroic, Lutris,
   NonSteamLaunchers) are skipped rather than listed with a wrong folder.
3. Folder picker (`openFilePicker`, FOLDER): works in Game Mode with the controller; SD card paths (`/run/media/...`).
4. Running-game guard for non-Steam games: matched by exe path inside the folder only (Steam's SteamAppId isn't used).
   Check it greys out buttons while a Unifideck game runs.
5. Session check: LastPlayTime from shortcuts.vdf updates when a shortcut is played?
6. Heroic (step 2): GOG `~/.config/heroic/gog_store/installed.json`, Epic
   `~/.config/heroic/legendaryConfig/legendary/installed.json`, Flatpak under
   `~/.var/app/com.heroicgameslauncher.hgl/config/heroic/`; Lutris maybe later (`pga.db`).
7. README (game list, sources, Add game folder), version bump, release notes; delete this file.

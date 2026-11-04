# Unreal II Enhanced - standalone Windows player and screenshot compaction (2026-11-03)

## Result

A double-clickable Windows player, `Unreal II Enhanced.exe`, plays the owner's installed Unreal II without Python, dev.py,
authorization flags, map allow-lists or a hand-made sandbox. It was validated in 10 contained game launches: clean first
start through New Game into TutA gameplay, restart with persisted settings and saves, import of the owner's developer
profile and play from the owner's M08A1 quicksave, full screen, window resize, frame limit, the diagnostics mode,
DirectMusic helper loss and restart, and the game's normal shutdown with no process left behind. A developer-harness
regression launch with the rebuilt developer executable also passed.

- Executable: `out/player/dist/Unreal II Enhanced/Unreal II Enhanced.exe` (sha256 `0e99e21c...`; save point
  `out/dev-init-savepoints/player-20261103`).
- Build: `python -I tools/xrt/dev/dev.py build --lean --order tools/xrt/dev/order-r4-multi.txt`, then
  `python -I tools/xrt/dev/dev.py player-build` (about 15 s; links the developer objects with the current runtime).
- Launch: double-click the exe (Windows 10/11 x64, Vulkan driver). The first time it finds or asks for the installation.

## Design (reuse, no new framework)

| Piece | What it is |
|---|---|
| `tools/xrt/dev/player.c` | Linked only into the player. Launcher half: data folder, installation discovery and checks, data-folder preparation, optional profile import, then the same exe as the game process in a kill-on-close Job; restores StickyKeys/ClipCursor and reports an abnormal end. Game half: sets the content root, hands the runtime its usual command line. |
| Runtime content overlay (`patches/player-runtime.patch`) | `CreateFile` read opens, `fopen`, `FindFirstFile`/`_findfirst` (merged listings) fall back to the installation for files the game root lacks. Never `Save\`; writes keep the existing sandbox guard. Inert in the developer exe (empty content root). |
| DirectMusic helper `--content` (`patches/player-dmusic-helper.patch`) | The installation is the helper's read-only root (its disk guard still refuses writes and links). |
| Focus guard (`hle_gui.c`) | After the player switched to another application, the game's own SetForegroundWindow/SetActiveWindow/SetFocus stay virtual (the background-mode path); clicking or Alt+Tabbing back activates natively. |
| `dev.py player-build` / `run --player` | Build and package; contained tests of the dist exe through the existing contain.exe, input-script and scene-stop machinery. |

The developer executable contains no player code: `xrt_main.c` declares `xrt_player_setup` with an
`/alternatename` default that returns 0.

### Installation and data

- Installation: `--game DIR` > remembered `player.ini` GamePath > beside the exe (up to 3 parents) > GOG registry
  (`GOG.com\Games\1207658677`) > folder dialog. DIR may be the game folder, `singleplayer` or `System`.
- Checks before anything starts: required files and folders; each of the 20 translated modules must match the
  SHA-256 the code was translated from (a readable message names the file); no links in the path; the code page can
  carry the path; data folder and installation separate.
- Data folder `%LOCALAPPDATA%\UnrealIIEnhanced\` (or `--data DIR`): `player.ini`, `System\` (a private copy of the
  installation's System folder, 35 MB, refreshed only for changed files; the player's ini files are never overwritten),
  `UIScripts\U2Menus.ui` + `System\U2Menus.int` (port.py's menu edits, generated into `player_edits.h` and verified
  byte-identical to port.py), `System\U2Port.u`, `Save\`, `Temp\`, the installation's other folders mirrored empty
  (431 folders, no files), `Logs\player.log` and `Logs\<time>\` per session (the newest 8 kept).
- The installation is never written; its `Save` junction is never read or listed.
- Profile import (`--import-profile DIR`): User.ini and the display section are copied after backing up the player's
  own; `Save\*.usa` copied only where no save of that name exists; the source is only read.

### Defaults (the owner's `--play` settings)

No session time limit, no world-frame stop, every map allowed, guard staging, quiet trace, sound on, no frame
captures, `-windowed` unless `StartupFullscreen=True`. `--diagnostics`: development trace and strict staging (the
reference mode). Developer authorization flags are not exposed.

## Validation

Setup without a game process (`tools/xrt/dev/player/setup_tests.py`, under contain.exe): 17/17, three times -
missing installation (exit 3), incomplete installation, wrong module version (Engine.dll, one byte changed), clean
preparation, second preparation (remembered path, User.ini kept, 0 files recopied), profile import (saves
byte-identical), second import (player's own save not overwritten), unknown option (exit 6, no dialog); the
installation (size and time of every file) and the import source were unchanged.

Game launches (journal `out/player/tests/journal.txt`; all contained, background mode, scripted input):

| # | Result |
|---|---|
| 1 | No game process: harness started the build-folder exe (no `port\`); counted anyway. Fixed: tests start the dist exe. |
| 2 | FATAL in CS_Titles: GlmLib `_chdir`s into `Meshes\<sub>\` to find `*.gem`; those folders were only in the installation. Fixed by the folder mirror. |
| 3 | PASS: clean data folder, intro, NEW GAME, NORMAL, CS_Titles, TutA cutscene with subtitles, player control, F5, exit 0. |
| 4 | PASS: restart; Options > Video FOV slider persisted in the data folder's User.ini; F8 loaded launch 3's save; resize to 1600x900 (persisted); 60 FPS limit; exit 0. |
| 5 | PASS: owner profile imported; owner's M08A1 quicksave loaded (HUD, weapon); level music from the installation; walking speed 115 from the profile; F5 rotation; exit 0. |
| 6 | PASS: start in borderless full screen (1280x720 scaled to 2560x1440); exit 0. |
| 7 | PASS: `--diagnostics` (development trace, strict staging); helper killed: music stops, game continues; exit 0. |
| 8 | PASS (developer exe `7f416480`, rebuilt with the shared runtime): established dev path, exit 0, sandbox retired. |
| 9 | PASS: helper killed in M08A1, next load restarted it from the installation (restart 1 of 3); exit 0. |
| 10 | Final exe, remembered installation, persisted FOV: exit 0, but the scripted Ok click missed (the window was 1600x900 since launch 4). |
| 11 | PASS (final exe): quickload, mouse turn, strafe, F5, exit 0, no process left. |

Totals: 11 of 12 launches, 759.7 s of 5,400 s. Every game end left 0 processes in the Job (helper ended).

Not verified by a launch: the folder dialog (needs a person), a real foreground session with Alt+Tab/minimize
(automation runs in background mode; the focus guard is logic-reviewed only), sessions longer than 5 minutes (no
time-based stop exists in the player: no watchdog, no scene stop; bounded logs: xrt.log 50,000 lines, fixed monitor
snapshot), audible output (sound ran muted; mix levels were metered).

## Packaging

`out/player/dist/Unreal II Enhanced/` (82 MB): the exe (76 MB), `dmusic_helper.exe` (x86, built from the developer
helper source), `dxvk\d3d8.dll`/`d3d9.dll` (DXVK 3.1.1 x64, hash-pinned, zlib/libpng license in `dxvk\LICENSE.txt`,
fetched from the v3.1.1 tag), `port\U2Port.u`, `README.txt` (requirements, locations, options, limitations),
`build-info.json` (all hashes, lift options, runtime source hashes). Static CRT; imports only Windows DLLs (incl.
XAudio2_9, DirectMusic through the helper). PDB in `out/player/symbols`. No game assets, saves, screenshots, test
harness or manifests. **Not reviewed for redistribution**: the exe contains machine-translated code derived from the
game's binaries (personal use only; the README says so).

## Storage compaction

See the section appended below by the compaction run (frames_cleanup_20261103.py).

## Known limitations

Subtitle size not adjustable; Mouse Smoothing over-turns above ~120 FPS (original script); DPI-unaware window;
single instance; xrt.log caps at 50,000 lines (late events of long sessions are not logged); `--import-profile`
replaces the display section with the profile's (a 2560x1369 window brings the Auto 125% UI).

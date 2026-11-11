Unreal II Enhanced - experimental native player for Unreal II: The Awakening
=============================================================================

Plays YOUR installed copy of Unreal II: The Awakening (single player) as a native 64-bit Windows program. This download
contains no game files and no game program code: on the first start the player makes the game-specific part from your
own installation, on your computer, and keeps it for later starts.

Status: EXPERIMENTAL. The campaign has been played through its first missions in testing (training, Atlantis,
Sanctuary, M08A1-M08A2); a complete playthrough has not been tested. Expect bugs.

What you need
  - Windows 10 or 11, 64-bit.
  - Unreal II: The Awakening Special Edition, installed (the GOG release). The player checks every program file it
    uses and refuses other versions with a message naming the file.
  - A graphics card and driver with Vulkan 1.3.
  - About 1 GB of free disk space during the first start (about 120 MB afterwards), plus your saved games.
  Nothing else: no Visual Studio, Python or other tools to install.

Start
  1. Unpack the whole folder anywhere (not inside the game's folder).
  2. Double-click "Unreal II Enhanced.exe".
  3. The first time it looks for the game (GOG's registry entry, or beside this folder) and otherwise asks you for the
     game's installation folder. Then it prepares the game for this computer: a window shows the progress. This
     takes a few minutes once (about 3 minutes on a 16-core PC; longer on slower ones). The installation is only read.
  4. The game starts with its intro: press Escape for the main menu.
  Later starts skip step 3. After an update of the player, the preparation runs once more.

Where things are
  %LOCALAPPDATA%\UnrealIIEnhanced\
    GameCode\<id>\           the game-specific part prepared from your installation (delete it to prepare again,
                             or start with --rebuild-game-code)
    System\                  settings (Unreal2.ini, User.ini) and a private copy of the game's System folder
    Save\                    your saved games (F5 quicksave, F8 quickload)
    Logs\player.log          start-up messages; Logs\gamecode.log the last preparation; Logs\<date-time>\ sessions

Options (none are needed normally): --game DIR, --select-game, --data DIR, --rebuild-game-code, --nosound,
  --diagnostics, --prepare-only (check the installation and prepare, then stop without starting the game).

Enhanced settings (Options menus): resolution, borderless full screen (Alt+Enter), frame rate limit, field of view
  (Hor+ widescreen), VSync, UI scale, walking speed.

Known limitations: experimental; subtitle size cannot be changed; Mouse Smoothing over-turns above about 120 FPS (turn
  it off or limit the frame rate); not DPI-aware; one instance at a time; music needs Windows' DirectMusic.

What is in this folder
  Unreal II Enhanced.exe   the player: launcher and the runtime that runs the game's translated code
  dmusic_helper.exe        32-bit helper that plays the game's DirectMusic music through Windows
  dxvk\                    DXVK 3.1.1 (Direct3D 8/9 on Vulkan), zlib/libpng license
  setup\                   the preparation tool (u2gen.exe): the project's translator and build steps
  toolchain\               LLVM 23.1.4 clang-cl and lld-link, used only to compile the prepared game code
  THIRD-PARTY-NOTICES.txt  licenses of the bundled components

Unreal II: The Awakening is a trademark of its owners; this project is not affiliated with Epic Games or Legend
Entertainment. Source code: https://github.com/thekojac304/unreal2-recompiled

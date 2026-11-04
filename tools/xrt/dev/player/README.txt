Unreal II Enhanced - standalone Windows player
==============================================

A native Windows x64 build of Unreal II: The Awakening (single player), made by static recompilation of the game's
own program code. It plays YOUR installed copy of the game: no game files are included here.

Requirements
  - Windows 10 or 11, 64-bit (x64). Not for ARM64 Windows or 32-bit Windows.
  - Unreal II: The Awakening Special Edition installed (the GOG release; the player checks every program file it
    needs and refuses other versions with a message naming the file).
  - A graphics card and driver with Vulkan 1.3 (graphics go through DXVK, included).
  - Windows' own DirectMusic and XAudio2 (part of Windows; nothing to install).
  - About 50 MB in your local application data folder, plus your saved games (about 7 MB each).

Start
  Double-click "Unreal II Enhanced.exe". The first time, it looks for the game (beside this folder, or through GOG's
  registry entry) and otherwise asks you to choose the game's installation folder (the folder that contains
  "singleplayer", or "singleplayer" itself). The choice is remembered.
  The game starts with its intro: press Escape for the main menu.

Where things are
  %LOCALAPPDATA%\UnrealIIEnhanced\              (type it into Explorer's address bar)
    player.ini                the installation folder (GamePath); delete it to choose again
    System\Unreal2.ini        display settings (resolution, full screen), as in the original game
    System\User.ini           controls, game options and the Enhanced settings ([U2Port.PortSettings])
    Save\                     your saved games (F5 quicksave, F8 quickload, Save/Load menus)
    Logs\player.log           start-up messages; Logs\<date-time>\ one folder per session (the last 8 are kept)
  The installation is only read. Its own Save folder is never used, so saves of the original game stay untouched.
  System\ also holds a private copy of the installation's System folder (35 MB, refreshed when the installation
  changes): the game writes its settings and logs there.

Enhanced settings (Options menus)
  Video: Resolution, Full Screen (borderless; Alt+Enter), Frame Rate Limit, Field of View (Hor+ widescreen), VSync,
  UI Scale. Game: Walking Speed. Input: Mouse Smoothing (turn it off above about 120 FPS: it over-turns there).
  Windows can be resized and maximized.

Options (shortcut or command line; none are needed normally)
  --game DIR             use this installation (and remember it)
  --select-game          choose the installation again
  --data DIR             keep settings and saves in DIR instead of %LOCALAPPDATA%\UnrealIIEnhanced
  --import-profile DIR   copy settings and saves from a developer play profile folder (User.ini, WindowsClient.ini,
                         Save\*.usa); saves of the same name are not overwritten; DIR is only read
  --diagnostics          detailed diagnostic logs and the strict (slower) graphics buffer checks, for bug reports
  --nosound              start without sound
  --prepare-only         check the installation and prepare the data folder, then stop without starting the game

If the game stops unexpectedly a message names the session's log folder; your saves are kept.

Known limitations
  - Subtitle size cannot be changed (the attempted setting made subtitles disappear and was removed).
  - Mouse Smoothing (the original game's option, on by default) over-turns above about 120 FPS: turn it off or set a
    Frame Rate Limit of 120 or less.
  - The program is not DPI-aware: on a scaled (high-DPI) display Windows enlarges the window and its contents.
  - Only one copy can run at a time. Music depends on Windows' DirectMusic; if the music helper fails the game
    continues without music and restarts it at the next level load (at most 3 times per session).

Contents
  Unreal II Enhanced.exe   the player (start-up, the recompiled game code and its runtime)
  dmusic_helper.exe        32-bit helper that plays the game's DirectMusic music through Windows' DirectMusic; it is
                           started and ended by the game
  dxvk\d3d8.dll, d3d9.dll  DXVK 3.1.1 (zlib/libpng license, dxvk\LICENSE.txt), Direct3D 8/9 on Vulkan
  port\U2Port.u            the Enhanced settings package (compiled UnrealScript of this project)
  build-info.json          exact build identity and file hashes

Legal status
  This folder contains machine-translated program code derived from Unreal II's own binaries. It is intended for the
  owner's personal use with a legally obtained copy of the game. Its redistribution has NOT been reviewed: do not
  publish or pass it on. Unreal II: The Awakening is a trademark of its owners; this project is not affiliated with them.

# Downloadable player: game code prepared on the player's machine

The downloadable release contains no translated game code and no game files. It contains our runtime and launcher
(prebuilt), the translator (frozen into `setup\u2gen.exe`), and a pinned LLVM toolchain. On first start the player
prepares the game-specific part from the user's own installation and caches it.

```
release zip (ours + redistributable)            prepared on the player's machine (from their own installation)
-------------------------------------           ------------------------------------------------------------------
Unreal II Enhanced.exe   runtime + launcher  <-- %LOCALAPPDATA%\UnrealIIEnhanced\GameCode\<build id>\
  exports 32 runtime functions + 4 variables       UnrealII-game.dll  translated modules, compiled by clang-cl
  delay-loads UnrealII-game.dll                    U2Port.u           Enhanced settings, compiled by the game's UCC
setup\u2gen.exe          translator + build steps  gamecode.json      identity and the reference-source check
toolchain\               clang-cl, lld-link 23.1.4
dmusic_helper.exe, dxvk\
```

## The boundary

The translated code needs 32 runtime functions and 4 variables (`xrt_g`, `xrt_preempt_req`, `xrt_call_cache`,
`xrt_call_cache_gen`) from the runtime. This was measured with `lld-link` on all 276 compiled units
(`player_exports.def`).

- **`xrt.h` under `XRT_GAME_DLL`:** declares the 4 variables `dllimport` and reads the monitor depth through
  `xm_depth()`, because a thread-local variable can't be imported. Without the define, every existing build compiles
  exactly as before.
- **Calls in the other direction:** the runtime's Enhanced hooks and the `msvcr70` pow core call into the DLL. These go
  through a delay-loaded import library (`game.def`), because the player starts before the DLL exists.
- **Module list:** `xrt_main.c` under `XRT_SPLIT` takes it from the DLL's `xrt_game_modules` (`glue.c`), after
  checking the interface version.
- **Structure layouts:** `layout_probe.c` records how the runtime's compiler (MSVC) lays out the shared structures.
  The generator then compiles those facts as C11 assertions with clang-cl and the minimal headers in `include/`, so a
  mismatch stops the build.

## Building the release (maintainer)

```bat
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-release.txt
.venv\Scripts\python -I tools\xrt\setup\build_release.py --version 0.1.0-alpha.1
```

Requirements: Visual Studio 2026 C++ tools, and LLVM 23.1.4 installed at `C:\Program Files\LLVM` or given with
`--llvm`. The game is not needed. Output: `out\release\UnrealII-Enhanced-<version>-win-x64.zip` and `SHA256SUMS.txt`.

`u2gen.py` also runs from source: `python tools\xrt\setup\u2gen.py --game ... --out ... --toolchain ... --player-lib ...`.
For a source run, `runtime-include/` and `layout_asserts.c` must be generated first (`build_release.py` does this).

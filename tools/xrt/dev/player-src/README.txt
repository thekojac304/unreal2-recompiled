Player source snapshot (2026-11-10)
===================================

runtime/        the 64 runtime source files the standalone player "Unreal II Enhanced.exe" (2026-11-03, exe sha256
                0e99e21c...) was built from. Each file's SHA-256 equals the "runtime_sources_sha256" entry of that build's
                out/player/dist/Unreal II Enhanced/build-info.json (verified 64 of 64 on 2026-11-10).
dmusic_helper/  the source of the 32-bit DirectMusic helper process (dmusic_helper.exe) that dev.py player-build compiles.

Why this exists: dev.py builds from out/dev-init/runtime and out/dev-init/dmusic_helper, which are git-ignored
(out/). The patches in tools/xrt/dev/patches/ are diffs against those working copies, and dev.py setup seeds them from
out/recovery/practical-init-20261031-01/runtime, which is also local only. Without this snapshot a clone of the
repository could not rebuild the player.

Contents: independently written runtime code only (CPU model, guest memory and loader, high-level emulation of
kernel32/user32/msvcr70/COM/Direct3D 8/DirectInput/DirectMusic/OpenAL, GUI, monitoring). It contains no machine-translated
game code and no game data. The translated modules (generated C) stay local: they are produced from your own
installation by tools/xrt/xlift.py and are never committed.

To rebuild the player in a fresh clone (not yet exercised end to end on a second machine):
  1. copy runtime/ to out/dev-init/runtime and dmusic_helper/ to out/dev-init/dmusic_helper;
  2. lift your installation's modules (tools/xrt/xlift.py; experiments/xrt/README.md lists the invocations, and
     dev.py lift / lift-audio produce the developer copies with the --opt list in the player's build-info.json);
  3. set U2_GAME_INSTALL (the installation's singleplayer folder) and, if Visual Studio is elsewhere, U2_VCVARSALL;
  4. python -I tools/xrt/dev/dev.py build --lean --order tools/xrt/dev/order-r4-multi.txt
     python -I tools/xrt/dev/dev.py port-build
     python -I tools/xrt/dev/dev.py player-build

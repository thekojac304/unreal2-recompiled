# Unreal II Windows port — Enhanced Edition batch, 2026-11-02 (night)

**Summary.** The port now has Hor+ widescreen with a field-of-view setting. Frame rate limit and a working VSync are
settings in the game's own Options menus, persisted in the player's `User.ini`. **Subtitle Size was not delivered**
(section 3). Long personal play
sessions are allowed. Music failures no longer end the game.

High-frame-rate behaviour was measured from 30 to ~340 FPS. The engine's simulation is time-based and matched at every
frame rate. The script-level frame-rate bugs found are fixed or documented:

- A 60 Hz script-Tick ceiling covers six actor classes (Drakk limb damage, black-hole damage and others).
- The game's own **Mouse Smoothing** over-turns at high FPS (+33% measured). It can't be fixed natively without
  patching game bytecode, so it is documented and the Input tooltip now says to turn it off above ~120 FPS.

Budget used: **24 of 28 launches, 5,003 s of 14,000 s** (journal: `out/dev-init/enhanced/journal.txt`), no fatal.
Recommended build: save point **`out/dev-init-savepoints/enhanced-final-20261102`** (exe `87a51212…`, U2Port.u
`f8b94b10…`, DirectMusic helper `b47d41ee…`). `enhanced-rc1-20261102` (exe `1342d5c6…`) is the benchmarked build;
the final build differs only by the removed subtitle mechanism. The pre-batch build is kept as `enhanced-start-20261102`
(= beta-campaign, exe `e57b006e…`).

## 1. Gameplay timing at high frame rates

**Where time comes from.** The main loop measures each frame on the wall clock. `ULevel::Tick` (`native/level_tick.c`
documents the disassembly) multiplies that by TimeDilation and advances the level's time. It then clamps every actor's
DeltaTime to **[1 ms, 0.4 s]**. Physics, animation, timers and movers all use that DeltaTime. Game time therefore
follows the wall clock between 2.5 and 1000 FPS; above 1000 FPS the simulation would run fast. The frame limiter now
keeps a **1 ms floor even when "Unlimited"**, which no game scene in this port reaches (its maximum is ~510 FPS).

**Measured** (identical quickload per limit, the same scripted inputs, per-frame camera + game time in frames.csv;
launches 1, 4, 5, 6):

| limit | achieved | game/wall | walk into wall (2 s) | open-floor walk (2 s) | jump height / air time | AR rounds per 1.5 s |
|---|---|---|---|---|---|---|
| 30 | 30.0 | 0.997 | 157.1 uu | 801.8 uu, 392.5 uu/s | 88.30 uu / 0.73 s | 15 |
| 60 | 59.8 | 0.997 | 157.3 | – | 88.33 / 0.75 | 15 |
| 90 | 89.7 | 0.997 | 157.4 | – | 88.35 / 0.74 | 15 |
| 120 | 119.5 | 0.997 | 157.4 | – | 88.27 / 0.75 | 15 |
| 144 | 143.4 | 0.997 | 157.4 | 806.8, 395.1 | 88.24 / 0.74 | 16 (hold quantization) |
| unlimited | 281–340 | 0.997 | 157.5 | 813.0, 399.5 | 88.34 / 0.75 | 15 |

Cinematics and scripted timing:

- The CS_Titles cinematic lasts 73.13 s at 30 FPS and 73.09 s uncapped. The reference uncapped 4K run gave 73.55 s
  measured between level opens; my two runs measured the same span the same way.
- The **TutA cutscene camera path at equal time** after the level start is identical: median 0.0 uu, and 98% of 0.1 s
  samples are within 20 uu (the rest are interpolation at camera cuts).
- Level transitions TutB → PD_Avalon → Atlantis came at +24.98/+71.08 s and +24.92/+70.94 s, against 24.9/70.9 before
  the batch.
- Collision, stairs/ledge contact, weapon fire rate and the dialogue/subtitle schedule all matched across frame rates.

**Script audit.** Every UnrealScript function containing `Tick(float` in 13 packages was audited
(`out/dev-init/enhanced/grep/tick`). Defects found and what was done about each:

| defect | effect at high FPS | action |
|---|---|---|
| U2DrakkMedium limb attacks `Max(int(R*dt),1)` per tick | damage ∝ FPS above ~100 FPS (500 dps at 500 FPS) | **fixed**: 60 Hz script-Tick ceiling |
| projectileBlackHole `int(300*dt)` | pain ring 0 damage above 300 FPS | **fixed** (ceiling) |
| U2DrakkLight `GroundSpeed = Lerp(Charge, GroundSpeed, 0)` per tick | drone freezes when charging | **fixed** (ceiling) |
| U2KillerSproutController damage only if `R*dt >= 1` in one tick | no grab damage at ≥31 FPS (original at 60 FPS too) | ceiling = 60 FPS behaviour |
| RubbleChunk `FRand()<0.1` per tick (bubble spawns) | spawn rate ∝ FPS | **fixed** (ceiling) |
| Legend.Fader flicker per tick | invisible at high FPS | **fixed** (ceiling) |
| **PlayerInput.SmoothMouse** (Mouse Smoothing, on by default) | every input frame without mouse counts within 70 ms is extrapolated: **+33% turn** at ~300 FPS (launch 2a), 0 at 90 FPS; off: 55.4° vs 54.2° for the same input at 60/330 FPS | script-to-script call, no native hook without patching bytecode: **documented**, Input tooltip says to turn it off above ~120 FPS |
| PlayerController.UpdateRotation `int(32*dt*aTurn)` | ≤1 rotator unit lost per tick (−2% at 330 FPS, measured) | documented (negligible) |
| AdjustView zoom `Max(7°, …)` per tick | zoom-in transition faster (0.27 s at 30, 0.06 s at 144 FPS) | documented (cosmetic) |
| ViewFlash instant flash × 10·dt | damage flashes weaker at high FPS | documented (cosmetic) |

The ceiling (`native/script_tick.c`, wraps `UObject::ProcessEvent`) delivers the Tick event of these classes at most
60 times per second of game time, with the accumulated DeltaTime. At or below 60 FPS nothing changes. Above it these
actors behave as at 60 FPS. Native physics and all other events still run every frame.

In game the mechanism was exercised with a developer test class (`--tick-extra U2Pawn`, launch 4): 9,373 events
delivered and 45,093 deferred at ~330 FPS, which is 60 Hz. None of the six target classes appears in the test
checkpoints (TutA/TutB/Atlantis/M08A1), so their own behaviour change is verified by code and audit, not in play.

## 2. Hor+ widescreen and field of view

The engine's projection takes the FOV as the **horizontal** angle at any aspect ratio, so widescreen was Vert-: at
16:9 the top and bottom of the 4:3 view were cut. `native/view_fov.c` wraps `FCameraSceneNode::UpdateMatrices`.

- For the player view and Canvas.DrawActor (the first-person weapon), the angle is widened to
  `2·atan(tan(F/2)·A·3/4)` for aspect A > 4:3. The vertical angle stays the 4:3 one, and the frustum culling built in
  the same call uses the wider angle. The game's own FovAngle (zoom, scripted/cinematic FOV, mouse scaling) keeps its
  meaning.
- Orthographic views, shadow projectors, light maps and every other node are untouched.
- Two defects were found and fixed during the batch:
  - **Doubled angle** (launch 1, the broken weapon the owner saw): the view hit the 170° clamp.
  - **Constructor path** (launch 3): FCameraSceneNode's constructor builds the matrices before the derived vtable is
    set. The derived constructor is now found on the guest stack.
- Verified on rendered frames (launches 2a, 3, 4, 7) at 4:3 (960×720), 16:10, 16:9 (1280×720 to 3840×2160), 21:9
  (1260×540, 3440×1440) and 32:9 (1600×450). With FOV 100 the view is 110.1° / 115.6° / 128.8° / 145.1° horizontal,
  always 83.6° vertical. At equal height a 21:9 frame has the same vertical framing as 16:9 plus width at both sides,
  and the weapon has the same size and position relative to the screen height. Cinematics (PD_Avalon, TutA) keep
  their vertical framing and letterbox.
- **Field of View setting** (Options > Video, 75–120, horizontal degrees at 4:3):
  - It keeps the player's DefaultFOV/DesiredFOV every frame, so loads and level changes can't reset it. Zoom works and
    scripted FOV is untouched.
  - Live and persistent: 110 → 100 via the slider, restored at the next start (launches 10a/10b). The 110/75/90 views
    are compared in `l04-fov.png`.
  - **Default 85**, the game's class default. The shipped and owner `User.ini` set DefaultFOV=100. That value
    compensated the old Vert- view (100° across 16:9 = 67.7° vertical, about the original 85 at 4:3); kept under Hor+
    it would show 83.6° vertically. 85 under Hor+ gives 101.4° × 69.0° at 16:9, the original framing.
  - Note: the game scales mouse turning with the FOV, so turning at 85 is ~15% slower per count than at 100.
- Weapon: no separate viewmodel FOV slider. The weapon uses the game's own FOV-dependent offset and gets Hor+, so it
  looks as at 4:3. A separate value would need repositioning the weapon actor and was not needed.
- Remaining: the sniper-scope overlay and the menu background are ScaleContainers stretched non-uniformly (1024×768
  scaled to the screen), as in the original at widescreen. Not changed.

## 3. Subtitles — not delivered

An independent Subtitle Size setting was implemented twice, and both versions failed in game. The final build has no
Subtitle Size row, so subtitles stay exactly the original (verified, launch 14).

1. **Draw scale.** The subtitle container was wrapped in the game's own ScaleContainer and its scale was set from the
   setting (first plainly, then with a virtual frame W/S × H/S as the global UI scale uses). The scaler ran (logged
   ×1.25 to ×2.0), but no subtitle was drawn at any size above 100% (launches 11b and 11c, 3440×1440).
   - Launches 11a and 12 photographed the wrong time window.
   - On re-checking, every subtitle earlier read as "scaled" (launches 5 and 7) was actually drawn at 100%: the
     setting times were matched against the wrong line times.
2. **Larger game font.** The game ships its subtitle font as SubTFonts EE16 (default), EE18 and EE20.
   - The menu change to 125% applied and persisted, but did not reach the TutA level's DialogEngine (launch 13).
   - A session started with EE20 drew no subtitles at all (launch 13b).

Next steps for a follow-up: trace how `UIConsole.BroadcastStatusMessage` places and clips the subtitle labels, and how
`UDialogEngine::execLoadSubtitleFont` resolves `SubTFonts.EE20`. The game's 8 KB Unreal2.log may hold the load error
if it is flushed. The runtime keeps the `SubtitleSize` key and the UnrealScript helpers for that work, but they are not
used.

## 4. Frame rate limit, VSync, presentation

- **Frame Rate Limit** (Options > Video row 2, replacing Bit-depth, which has no effect in the port's windowed
  presentation):
  - Choices 30/60/90/120/144/165/240/Unlimited, plus "Custom N" for any User.ini value from 20 to 1000.
  - It is the existing waitable-timer limiter (no busy wait, the baton is released while waiting), now runtime-settable.
  - Achieved rates: 30.0 / 59.8 / 89.7 / 119.5 / 143.4.
  - Set from the menu to 144, live and persisted (launch 10c). `dev.py --fps-cap` still pins benchmarks.
- **VSync** (row 11):
  - D3DDrv sets a presentation interval only for exclusive full screen, which the port never uses, so the game's
    checkbox did nothing before.
  - The runtime now gives windowed and borderless devices `D3DSWAPEFFECT_COPY_VSYNC`, which DXVK turns into a FIFO swap
    chain.
  - A menu change triggers a device re-creation through the game's own resize path.
  - Measured on a 240 Hz monitor: 236 FPS with VSync on vs 345 off. The DXVK log shows FIFO.
  - Live and persisted from the menu (launches 10b/10c); restored at start.
- **Field of View** replaces Refresh Rate (row 3), which has no effect in windowed/borderless presentation.
- Windowed, maximized and borderless modes, resolution selection and resizing are unchanged from the beta. The size
  sweeps ran through the device-re-creation path many times without a fault.

## 5. DirectMusic

Evidence:

- The beta's three failures all followed `dmFadeout` during the music re-initialization of a quickload. One was a
  crash in `dmusic.dll`+0x18a38 (null read); two were request-side failures after the new performance was created.
- **Found and fixed:** both the guest proxy table and the helper's object table never reused released slots
  (128 each). Every load re-creates ~10 objects, so a long session would die after about a dozen loads (the helper
  with `die("object limit")`). Both tables now reuse released slots, with new guest proxy addresses so stale pointers
  are still caught.
- **Recovery policy:** a helper failure (crash, pipe failure, deadline, rejected request) no longer ends the game.
  - The cause is logged once ("DirectMusic: music stopped - …") and the helper's Job is closed.
  - Objects of the failed helper become stale (generations). Calls on them are answered locally: S_OK, or inert
    proxies for interfaces they return. Sound effects and speech (OpenAL/XAudio2) are unaffected.
  - At the game's next music initialization (level load or quickload) a new helper starts, at most 3 times per
    session.
- Verified (launch 3):
  - The helper was terminated twice with the `dmkill` developer step. The game went on each time.
  - The next quickloads started new helpers, which then served 126 and 107 real requests.
  - 14 M08A1 loads ran in one session.
- The natural `dmusic.dll` crash did not recur in this batch (about 20 M08A1 loads in all). Its root cause inside
  Windows' DLL is unconfirmed; the policy above contains it.

## 6. Personal play

`dev.py run --play` sessions now last up to **12 h by default** (`--session-minutes 10..1440`), with no world-frame
stop. The old 100,000-frame stop would also have ended a session after ~11 minutes at 144 FPS.

- `contain.c` accepts more than 600 s only with `XRT_DEV_PLAY=1` and real input. Scripted, background and developer
  launches keep the 600 s cap; an owned test covers all six cases.
- The Job, kill-on-close, the deadline, Ctrl+C, the sandbox, save isolation and the profile carry-over are unchanged.
- Run output is bounded: ~44 MB per session plus the 2.1 GB sandbox. The xrt.log 50,000-line cap and the frame table
  cap are both safe.
- **Owner session 20261103-000530 (after the batch):** every level change ended a `--play` session. The 47-map allow-list
  (570 characters) exceeded the runtime's 512-byte copy, so `map_allowed` refused all maps; the message box then
  reported the clean stop as the time limit. Present since the beta added `--play`; earlier owner sessions never
  changed level. Fixed: `map_allowed` scans any length and `--play` passes `*`; the notice names the actual stop
  reason. Owned test of the extracted function with the real list: pass.

## 7. Windows polish, regressions, performance

- Clean shutdown via the console: EXIT → ExitProcess(0) (launch 7).
- M08A1 combat at unlimited FPS: route, Puppeteer and pack, death → GAME OVER screen (launch 8).
- TutA new game, cinematics and movement (launches 5/6); TutB → PD_Avalon → Atlantis (7/7b); save/load (14 quickloads
  in launch 3, plus every run). Settings persistence was checked across sessions.
- Test-harness limit, not a game defect: scripted mouse input reaches the attract-mode menu but not the in-game pause
  menu; owner sessions use the menus normally. Alt-Tab, focus and minimize were not exercised; they need an
  interactive owner session.
- Workflow: routine runs at 1280×720 in the background, UI checks at 1920×1080, 4K/ultrawide only for the
  subtitle/aspect tests. The benchmark keeps the fixed 4K configuration.
- **Performance** (fixed 4K benchmark configuration: bench_tuta.ps1 via ab_run.ps1, uncapped 3840×2160, strict
  staging, quiet trace, background, CPU mask 0xFFFF; single runs; A = pre-batch build e57b006e):

| TutA window | A FPS | new build, same view (Hor+ off, game FOV 100) | new build, defaults (Hor+, FOV 85) |
|---|---|---|---|
| CS_Intro 30–60 s | 301.5 | 297.6 (x0.987) | 294.7 (x0.978) |
| cutscene 96–210 s | 206.4 | 205.6 (x0.996) | 195.0 (x0.945; +10.7% draw calls) |
| slow 158–177 s | 135.1 | 132.8 (x0.983) | 128.6 (x0.952; +13.1% draw calls) |
| spawn 220–230 s | 224.0 | 217.7 (x0.972) | 219.7 (x0.981) |
| movement 230–245.5 s | 291.8 | 288.9 (x0.990) | 272.8 (view differs: FOV 85 changes the bench's mouse turns) |
| pause menu | 518.3 | 520.7 (x1.005) | 520.3 (x1.004) |

  The overhead of the new wrappers (ProcessEvent tick ceiling, view/level/UI hooks, limiter floor) is 0–3% in single
  runs, inside the 4–10% run-to-run spread of earlier batches. Hor+ costs what it shows: the wider view draws 11–13%
  more in the cutscene and the CPU-bound frame follows. No broad optimization was started.

## 8. Commits, files, save points

- Runtime: `patches/enhanced-runtime.patch` (port_settings.c, hle_d3d8_device.inc VSync, DirectMusic recovery,
  xrt_internal.h) against `beta-campaign-20261102/runtime`. Helper: `patches/enhanced-dmusic-helper.patch`.
- Natives (`tools/xrt/dev/native`): view_fov.c, level_tick.c, script_tick.c (ui_scale_container.c was removed with the
  draw-scale subtitles). Other changes:
  dev.py (PORT table, `--play` policy, `--tick-extra`), dev_support.c (limiter, probe columns, `fps`/`pset`/`dmkill`
  steps), contain.c, port.py and PortSettings.uc (menus).
- Evidence and launch scripts: `out/dev-init/enhanced/` (journal, helpers, contact sheets, crops).
- Save points: `enhanced-start-20261102` (before), `enhanced-rc1-20261102` (benchmarked) and `enhanced-final-20261102`
  (recommended). Test profiles `enhanced-menu`, `enhanced-smoothoff` and `enhanced-subs`. The owner profile was not modified.

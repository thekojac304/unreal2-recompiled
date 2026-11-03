# Unreal II Windows beta batch, 2026-11-02 night: campaign compatibility, stability, polish

**Summary.** The guest memory pool no longer fragments: free blocks are split and merged, and the client gets a second
pool segment, so the original non-large-address-aware process's address space is available again. Round 4 had found
this as the main stability risk for long sessions. An owned test reproduces the old failure: the old allocator died with
8.7 MiB live. A 516 s three-level soak with three in-map reloads, and a final regression ending in the game's own
shutdown, ran without a fatal. Guard staging stays the play default. Inlining the C++ EH landing-pad link/unlink gives
+2.8 to +7.5% FPS in every TutA benchmark window (2+2 interleaved runs). Campaign: the transitions Atlantis →
PA_Sanctuary → M08A1 and TutB → PD_Avalon → Atlantis work. Progress in M08A1 stops at the first-room Izarian pack. Its
death opens the only way on (the runoff-basin hatches, from Danny Miller's camera broadcast), and it could not be cleared
by scripted open-loop fire, even with the owner-approved console `god`. That is a gameplay-scripting limit; no
translation fault was observed. Budget: **20 of 36 launches, 5,075 s of 18,000 s**, no fatal, no watchdog kill. Commits
`e9f7ffb`, `467b7dd` and the report commit, on `codex/level-initialization`, not pushed.

Recommended build: **save point `out/dev-init-savepoints/beta-final-20261102`** (exe `A0E80527…`).
Journal with every launch: `out/dev-init/beta-evidence-20261102/journal.txt`.

## 1. Allocator fragmentation (first priority), fixed

Round-4 finding G: once the 224 MB bump region was used up, a reclaimed free block was reused *whole*.

| change (`xrt_mem.c`, patch `tools/xrt/dev/patches/beta-batch-runtime.patch` vs perf-r4d) | effect |
|---|---|
| best fit **splits** the block; the remainder stays a free block, inserted after it (table keeps address order) | a 24 MiB free run serves 20 new sizes instead of one |
| reclaim (release warm/guarded staging blocks, merge adjacent free blocks, return a free tail to the bump region) **only when no free block fits** | guard blocks keep their pages until real pressure |
| **second pool segment 0x60000000–0x7FEFFFFF** (guest heap now 0x20000000–0x5FFFFFFF; it peaks at 53 MB); the first segment's unused tail becomes a free block | the owned test showed the 224 MB segment fragmenting at 61–72% occupancy even with splitting; the original process had its whole 2 GB |
| guest heap: coalesce/split large free blocks **only** when its bump region is exhausted | normal heap addresses unchanged |
| `runtime-report.json` → `guest_virtual_pool` | live/free/staging bytes, largest free, bump, reclaims, splits |

Unchanged: exact-size reuse and bump-first order before pressure, 64 KiB alignment, zero-on-recommit, stale pointers
fault (freed = decommitted; guard = PAGE_NOACCESS), interior/double/unknown frees refused, lifted images skipped.

Tests: `experiments/xrt/tests/pool_fragmentation` (new, 8 phases, one fresh process each: split, churn 150/400 MiB,
40 simulated level loads with guard+reuse staging, invalid frees, staging across splits/reclaims, segments, heap): PASS.
`run.cmd reference` builds the same test against the round-4 allocator, which fails split, churn (exhausted with 8.7 MiB
live), levels, staging and heap. `staging_reuse` and `staging_guard` (test + strict/guard differential, post-pressure
tail lengthened 400 → 4000 operations including new sizes; traces identical) updated for reclaim-on-demand and PASS.
Game: pool stats in every run, e.g. the soak ended with 984 live blocks / 86.9 MB, bump at 0x1A120000 (stepped over two
lifted images), 0 reclaims. A level load uses ~93 MB of address space, so long sessions now have ~7x headroom before the
first reclaim, and reclaims split instead of wasting space.

## 2. Guard staging: final status

**Guard stays the default** of `dev.py run` (owner decision `2501a91`); strict is unchanged and is the benchmark
default (`bench_tuta.ps1`); reuse stays a diagnostic. After the allocator change: the differential test passes (2
seeds, identical traces), and 16 game runs used guard (Lock/Unlock thousands of times per second, three level loads,
three reloads, resizing not exercised) without a fatal. Nothing challenged guard's correctness.

## 3. Campaign compatibility

| state | result |
|---|---|
| Atlantis post-briefing → dropship Use → PA_Sanctuary cinematic → M08A1 | natural transitions (+34.5 s, +88.7 s), launch 7 |
| TutB farewell → PD_Avalon cinematic → Atlantis | natural transitions (+24.9 s, +70.9 s), launch 20 |
| M08A1 start → use-door m08adoor1 → seal door (Use panel) → Puppeteer room | route reliable with the new `sync` step |
| Puppeteer Izarian | killed in launches 2, 6, 11, 14, 15 (hits, gore, death) |
| first-room pack (PawnFactory1/2 + alarm-called Izarians) | **blocker**: open-loop fire kills some; with `god` (owner instruction) the player survives indefinitely, but the AR runs dry and moving targets/ledges are not reliably hit |
| way on (from `Scripts/M08A/M08APollock1.u2s`, `Dialog/M08A/Sanctuary_15G.dlg`) | dead pack → `meetPollock1` → Danny Miller's camera broadcast ("I'll open the hatches to the runoff basin") → `runoffbasinHs` opens floor hatches Mover1/3 → flooded basin → ladder AutoLadder6/7 (-1204,1136) → glass-door level |

Furthest natural state: **M08A1, Puppeteer dead, first-room pack fight in progress**. M08A1 objective 1 (reach the
survivor) is not complete, and no mission was completed in this batch. Map analysis showed two dead ends that cost
launches: Mover15 `lilhuey` closes onto the scripted scientist, and the x=-1840 walkway is a one-way 70 uu drop. Mover5
and Mover19 are wall switches, not doors. The scripts and dialogs are the reliable source for such questions.

Verified in game: movement (walk, collision, ledges, a timed door closing), Use panels, save/load (quicksaves in 10 runs,
four in-map F8 reloads plus a quickload from the menu at the start of every run, exact pose restore, a timed door
keeps running after a load), level transitions (4), enemy detection, pursuit,
ranged and melee attacks, player hits and enemy deaths, knock-back, god mode, weapon auto-switch when out of ammo,
cinematics, HUD, console, pause menu, walking speed through the console (1.50x measured), normal shutdown
(`exit` → ExitProcess(0)).
Audio: muted mode throughout (full ALAudio → XAudio2 path), so audibility was not judged. Not exercised: swimming,
ladders, mantling, crouch through a gap, companion AI, grenades, death/respawn by checkpoint (god mode).

## 4. Windows usability

- **`dev.py run --play`**: the owner's interactive settings as one switch (real input, profile `owner`, sound on, the
  longest contained run, all 47 retail maps allowed, no periodic 4K captures, quiet trace). The authorization flags
  stay explicit.
- **Saves persist between sessions**: `--profile` now carries the game's own `Save/*.usa` to the next session (the
  previous set is kept in `Save.prev`; never the install's Save junction). Before, every session started without the
  player's quicksaves.
- **End-of-session notice** (`--play`): a message box when the contained session limit or a runtime stop ends the
  game, with the cause and the log folder. Before, the window simply vanished.
- Console findings: the UI console stays open after Enter and **Escape closes it**, so a second console key types "`".
  The first console use works ≥ 15 s after a load. This explains the round-4 "second console use fails".

**Biggest remaining usability limit:** a contained session ends after 600 s (`dev.py` first-scene policy), so a play
session is 10 minutes (quicksave before it ends; the profile keeps the save). Lifting it is a policy decision for the
owner, not changed here.

## 5. Performance (reported separately)

The only change taken from the profile evidence was **inline ehframe pad link/unlink**
(`patches/beta-eh-inline-runtime.patch`): `XRT_EH_REGISTER/POP` push/pop in generated code; the `XrtThread` prefix is
mirrored in `xrt.h` with static asserts, and the monitor depth is an exported TLS variable. ehprobe dev frames: PASS.

| TutA window (uncapped 3840x2160, strict, CCD0, 2+2 interleaved A B B A) | A FPS | B FPS | B/A |
|---|---|---|---|
| CS_Intro 30–60 s | 279.1 | 300.0 | **x1.075** |
| pause menu | 481.9 | 510.9 | x1.060 |
| cutscene 96–210 s | 198.8 | 207.7 | x1.045 |
| slow subsection 158–177 s (p95 9.06 → 8.53 ms) | 129.9 | 135.9 | x1.046 |
| spawn 220–230 s | 214.2 | 220.2 | x1.028 |
| movement 230–245.5 s | 280.5 | 289.4 | x1.032 |

Every B run beats every A run in every window; host load is equal. These absolute FPS are not comparable with round 4's
tables (different host load). At the 90 FPS cap, M08A1 gameplay holds 87–88 FPS (p95 12.2–12.6 ms, p99 ≤ 13.6 ms)
with ~46% of one core, so nothing triggered further optimization. The remaining D3D8 staging cost is two protection
changes per Lock/Unlock in guard mode; lowering it would shorten the stale-pointer window and is rejected (as in R4).
Small-cache CCD1 was not measured in this batch; the change removes code and calls, so no CCD1 regression is expected,
but that is unverified.

## 6. Portability notes (Linux x86-64 / ARM64 / Android)

- The allocator change is portable logic on top of `VirtualAlloc`/`VirtualProtect`/decommit. The POSIX equivalents
  are `mmap`/`mprotect`/`madvise(MADV_DONTNEED)` (zero-fill on reuse holds); the 6 GB guest reservation needs
  overcommit-friendly `PROT_NONE` reservations, which Android allows.
- The inline EH change only touches `xrt.h` macros and a TLS variable (`__declspec(thread)` → `_Thread_local`). The
  Windows x64 `RtlUnwindEx` landing stays Windows-only; the portable setjmp landing (`XRT_EH_FRAMES` off) is unchanged.
- Windows-specific additions this batch: dev.py's message box (ctypes `user32`, launcher-only) and the profile save
  carry-over (plain file copies, portable).
- Known barriers unchanged: D3D8 → DXVK/Vulkan host path, XAudio2 OpenAL adapter, x86 DirectMusic helper process,
  Win32 GUI HLE, x87 80-bit semantics on ARM64 (doubles as on x64).

## 7. Recommended next steps

1. Owner plays the M08A1 first-room fight once with `--play` (from `saves/20261102-1907-checkpoint-m08a1-postpack-god`
   or `-prelos`) and quicksaves after the hatches open. Alternatively, approve another console aid (e.g. `loaded`) for
   scripted runs. Then continue: basin swim → ladder → glass-door level → M08A2.
2. Decide the session-length policy for personal play (600 s today).
3. Measure the inline-EH build on CCD1 (small cache), and listen to sound once with `--sound on`.
4. Next performance lever if wanted: GLM animation (2.2 ms of the slow subsection in R4).

## 8. Commits and save points

- `e9f7ffb` pool split/coalesce/second segment, tests, `sync` input step, `--play`
- `467b7dd` inline ehframe pad link/unlink, profile save carry-over, `--play` end notice
- report commit: `face:X:Y[:Z]` pitch steering, input-log cap, README, this report
- Save points: `beta-start-20261102` (= perf-r4d + profiles), `beta-alloc-20261102`, `beta-ehinline-20261102`,
  **`beta-final-20261102`**. New checkpoints in `out/dev-init/saves/`: `20261102-1816-…-puppeteer-prelos`,
  `…-postkill`, `20261102-1907-…-postpack-god`.
- Not touched: the install, personal saves (Proton Drive junction), production policy, authorization evidence, and the
  unrelated uncommitted work of earlier sessions.

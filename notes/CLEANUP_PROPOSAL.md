# Storage cleanup proposal (2026-11-01) — NOTHING HAS BEEN DELETED

Sizes in GiB, measured without following junctions (Save junction excluded).
Method: every file in each candidate tree was compared (size + blake2b) against the 4757 files of the original install
(2.55 GiB). "Identical" below means a full-content hash match, not name/size/mtime.

## Totals
| Location | Size | Files |
|---|---|---|
| E:\Unreal2-Port-Investigation | 376.9 | 1,367,011 |
| C:\Users\lawma\Unreal2-dev-sandbox-overflow | 184.9 | 417,746 |
| Combined | 561.8 | |

## Top consumers
| Group | GiB | Class |
|---|---|---|
| C: dev-init-* sandboxes (98) | 165.9 | DUPLICATE (100% identical to install) |
| E: sandbox_cmp | 116.9 | DUPLICATE 116.7 (0.2 unique: d3d9/d3d8 wrapper DLLs, logs, ini) |
| E: out/dev-init/runs (145 runs) | 58.8 | REVIEW (50.1 is BMP frames) |
| E: experiments/xrt/build (214 dirs) | 44.1 | exe 16.3 KEEP; obj 13.7 REVIEW; ilk 6.5 REBUILDABLE; bin 4.1; pdb 3.2 KEEP |
| E: sandbox_archive (first-world-* x32) | 42.0 | DUPLICATE (identical except ~1.4 MB logs/ini/.u) |
| E: 55 dated sandbox_* dirs | 81.4 | 65.3 DUPLICATE (nested game copy), 16.1 REVIEW (workspace snapshots, exes, ppm) |
| E: out/recovery | 22.8 | REVIEW (zips 3.6, bin 5.0, pdb 3.9, ilk 1.8) |
| C: selftest-* + selftest-runs | 8.8 | REVIEW (transient self-test output) |
| C: runs-archive | 5.8 | KEEP/REVIEW (binary traces from early init runs) |
| C: run-* (7) | 2.9 | REVIEW (BMP frames) |
| E: out/dev-init-savepoints | 3.5 | KEEP |

Likely cause: every `dev.py run` / test case did `copytree` of the 1.3-2.0 GiB asset snapshot into a fresh sandbox
(assets untouched by the game), plus per-run BMP captures (4K runs: 4-6 GiB each).

## Proposed deletion (A): verified-identical game assets only  ≈ 387 GiB
Delete only files whose hash matches an install file; leave every non-identical file (logs, ini, traces, DLL wrappers) in place.
1. C:\...\Unreal2-dev-sandbox-overflow\dev-init-*  — 165.9 GiB (surviving copy: original install + sandbox_inputs/first-world; run records live in out/dev-init/runs and runs-archive).
2. E:\...\sandbox_archive\first-world-*  — 42.0 GiB (surviving copy: install). Hash-named; ledgers/records are not touched.
3. E:\...\sandbox_cmp\* EXCEPT first-world and level — ≈114.2 GiB identical files. Kept: first-world, level (tools/tests read them: asset_boundary, level_probe, dev.py LIFT_SYSTEM), and the 0.2 GiB unique files.
4. E:\...\sandbox_<case>_2026102*\ (55 dirs): identical files only — 65.3 GiB. The 16.1 GiB non-identical remainder stays.
Effect on builds/debugging: none for builds. Old sandboxes would no longer be re-runnable as-is (assets re-copy from install via dev.py/asset_boundary); their logs/evidence remain.

## Proposed deletion (B): rebuildable intermediates  ≈ 8 GiB
- *.ilk (incremental-link state) in experiments/xrt/build (6.5) and out/ (2.0), except out/dev-init/build and out/recovery/practical-init-20261031-01 (dev.py BASE). Effect: next link of that dir is a full link.

Expected recovery A+B ≈ 395 GiB: E: 377 -> ~147, C: 185 -> ~19, combined 562 -> ~167 GiB. Nothing moves between drives.

## Needs your decision (unique data, not rebuildable)
1. out/dev-init/runs BMPs: 50.1 GiB. Keeping only runs 20261031-192710 (final 4K, 5.75) and 20261101-005436 (88a05f9 final, 0.30) frees ≈ 44 GiB; JSON/logs/CSV/.bin stay. Frames are not byte-reproducible (game time follows wall clock). 3.6 GiB of frames across runs are hash-identical duplicates (102 groups).
2. C: run-* BMPs (2.9) and selftest outputs (8.8): transient, regenerable by rerunning, but not by me now.
3. experiments/xrt/build *.obj 13.7 GiB: reproducible from sources only if the gen/ sources of that moment exist; some build dirs are linked-against bases (client_identity --base). I recommend keeping objs of anything named final/checkpoint/handoff and deleting the rest only after you pick.
4. out/recovery 22.8 GiB (incl. 16 complete-sandbox zips 3.6): consumed-candidate/qualification evidence — untouched.
5. The 16.1 GiB non-identical remainder of dated sandbox_* dirs (copies of gen/*.c, exes, pdb, ppm): probably superseded, unproven.

## Protected (not touched by any proposal)
.git, working tree incl. uncommitted changes (branch codex/level-initialization, main, HEAD 88a05f9), .venv, tools/, third_party/, notes/, *.md, debug-symbols.json, vc140.pdb;
out/dev-init (build with unreal2-dev.exe + PDB, runtime, generated, dmusic_helper, setup.json), out/dev-init-savepoints (17, incl. x87w-20261031 = 88a05f9),
out/recovery/practical-init-20261031-01 (dev.py BASE), out/desktop-supervisor, fixture-*, supervisor/one-shot ledgers, lq-*, fc-*, natives_sp;
experiments/xrt (sources, gen/, results, build *.exe/*.pdb); sandbox, sandbox_inputs, sandbox_ref, sandbox_xrt, sandbox_cmp/first-world, sandbox_cmp/level;
C: *-generated (floor-cap, iflags, sse, x87v, x87w), iflags-20261031-obj, runs-archive; original install and the Save junction (never touched).

## Retention convention (proposal)
- Keep: latest successful build (out/dev-init/build) + one savepoint per milestone commit; per-milestone run dir without BMPs; best/last run's frames.
- Keep unique failure evidence only while the bug is open; note the run id in the README journal, then drop its frames.
- After each session: delete run sandboxes (they equal the install), *.ilk, and BMPs of non-milestone runs. Never copy the asset snapshot twice; check free space >= 4 GiB before launching.

# GetFocus boundary — validated; stopped at AdjustWindowRect

2026-10-24, US Eastern. The measured GetFocus adapter returned in the genuine
translated client. Highest verified world milestone remains **T2**: selected
CS_Intro actor lifecycle complete. Init and both kinds of tick have not returned.
The one authorized continuation stopped at **USER32!AdjustWindowRect**, without
implementing it. No device creation or rendering occurred.

Starting HEAD: `673a4d3e502549a2b49f9051b6099c41c9a73c38`. All 451 prior working files and the complete
unstaged/staged patches were preserved before editing. Existing pending changes
remain unstaged. The scoped local commit records GetFocus, its fixture and this
checkpoint; the earlier pending keyboard adapter retains its type-correct
SetKeyboardState cast in the working tree.

## Exact binaries and sources

Accepted input: `experiments/xrt/build/postram-20261024-174304-d3a9040d-serial01/xrt_ucc.exe`

SHA-256 `b0f5985c9ac49b82a9d29e7ef915df898955777fd672085656789deb4c5356dc`

New tested executable: `experiments/xrt/build/getfocus-20261024-01/xrt_ucc.exe`

SHA-256 `3f2a284a8197970fac19a38b41dda4323debfa699080f220d766457cd4b405b1`

Runtime aggregate: `3d370307ad606655f0ecb7af0b89c7fabbc8eb5d28acb68a2ec4ba560af14f4a`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

Exact source hashes, commands, object/PDB/executable hashes and copied originals
are retained under `out/recovery/getfocus-20261024-01/`. The executable corresponds
to that pinned working source, including the preserved pre-existing pending work.
All 265 generated and 14 runtime objects were freshly compiled serially. No
historical objects or PDBs were reused. Compiler/linker identities match the
post-RAM qualification. Zero main-build warnings or compiler/linker failures.
278 objects retain identical code and named relocation targets; only hle_gui
changes as expected. Linked comparison covers 79,226,692
non-relocation bytes with zero differences. Unmapped local helper bytes have the
same object-level coverage and limitation as the post-RAM qualification.

## Measured focus and keyboard boundary

The same project-owned x86 DLL runs natively and through the real lifter/runtime.
48 focus reads on two OS/guest threads pass exact native-HWND identity checks via
the typed host table, stable guest tokens, last-error sentinels 0/0x5555/0xdeadbeef,
and paired stdcall return/stack checks. All 98 fixture events survive, zero dropped
or truncated. Cases cover no focus, owned A/B/A focus transitions, destroyed
focused windows, invalid/destroyed SetFocus targets, initially unrepresented
native stock windows, and independent thread queues. GetFocus has no HWND argument:
invalid target attempts are made by native fixture orchestration, then queried.
Native invalid/destroyed attempts report error 1400; cross-thread SetFocus reports
error 5, and leaves the other thread's focus intact. No input injection or
AttachThreadInput is used; these additional behaviors are not claimed measured.

The adapter queries actual USER32 on the calling thread and maps only its returned
HWND through the existing typed GUI table. NULL stays NULL; a live previously
unrepresented window gets a normal guest token. No native HWND bits enter guest
memory, and no focus is cached or fabricated. SetFocus remains unbound in production.

The old C4090 record remains in the untouched qualification build.json. Correcting
SetKeyboardState's cast from const BYTE* to BYTE* matches the SDK's LPBYTE parameter;
its function machine code and named relocations remain identical. Its buffer
preservation and keyboard regressions pass. The older text summary's zero-warning
claim is not retroactively adopted. The pre-existing classprobe C4133 warning is
retained in this phase's class regression log; it is outside the requested correction.

## One bounded client continuation

Run: `experiments/xrt/results/raw/level/20261024-225210-f9cde2a9-candidate`.
One translated graphical session, zero native graphical sessions; established
DXVK/DirectMusic IPC configuration and 60000-ms runtime watchdog. Controlled exit 75.
All **74,363 events**, contiguous and untruncated, retained; **zero dropped**.

| Observation | Verified result |
|---|---|
| Selected CS_Intro LoadMap | world 0x12f52800; paired call 23484 / return 25850 |
| Initial selected-world lifecycle | 268 paired calls/returns per stage, 267 distinct actors |
| All observed selected-world lifecycle | 279 paired calls/returns per stage, 278 distinct actors, zero unpaired |
| GetFocus | call 74348 / return 74349; guest token 0x1020; last-error 0 |
| GetFocus caller/stack | return 0x111048ca; ESP 0x0120d1f8 -> 0x0120d1fc |
| UGameEngine::Init | one entry, zero paired returns |
| UGameEngine::Tick | zero entries, zero paired returns |
| Selected-world ULevel::Tick | zero entries, zero paired returns |
| D3D CreateDevice / Clear / Present | zero / zero / zero |

Selected-world identity is derived from the paired CS_Intro LoadMap return, and
actor identity comes from each actor's own world pointer. Entry-world activity is
not combined with the selected world. No entry alone establishes completion.
After GetFocus's return, the guest executes GetDC and GetDeviceCaps before stopping.
DXVK factory and adapter/capability/format queries are not device creation.

First remaining blocker: **USER32!AdjustWindowRect**, event 74352, instruction
`0x11103550` (`WinDrv.dll+0x3550`) in `UWindowsViewport::OpenWindow`, IAT
`0x1110b378`, expected return `0x11103556`. Snapshot disassembly, CPU/FPU/stack
diagnostics and complete trace remain local in the raw evidence. This API was
not implemented. No D3D unsupported-method or CreateDevice arguments arose.

Cleanup released DirectMusic's five tracked references, balanced one COM apartment,
and released the D3D/DirectInput references. StickyKeys restored to flags 510,
matching the independent before/after query. No orphan client/helper or unexpected
process crash was observed. The prior writable world sandbox was archived intact.

## Acceptance and integrity

Focus native/translated differential: PASS. GUI/keyboard, class/callback and module
regressions: PASS. Compact commandlet/VM: all nine cases PASS against fresh snapshot
native references. UnrealScript compiler: 16 compiles, 12 executions and four
expected invalid-source failures PASS. Traced HelloWorld: PASS. Full Python suite:
158 discovered, 141 passed, 17 documented opt-in E2E skips, with XRT_FULL=1; includes
the five observer tests. No compiler failure, C1001, D8040 or unexpected crash.

Two orchestration setup stops remain preserved: Python -I needed an explicit
sibling-module search path before verification; later, six commandlet cases passed
before a missing isolated tracer stopped the harness. The unchanged tracer was
built and only the three unrun cases continued. No production source changed, no
compiler was retried, and no additional graphical session was started.

Protected manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`:
all 4,122 files, three protected trees and nine protected files match before/after.
Accepted and new executable/object hashes and pinned source identities match after
execution. Original installation and saves were not accessed. Historical evidence
was not overwritten. Existing expanded CRT (110 mismatches / 1,796 pending), six
ACP932 differences and x87 limitations remain open; this phase does not requalify
those unaffected suites or infer hardware stability.

Smallest next experiment: separately authorize a native/translated AdjustWindowRect
fixture for the OpenWindow style/menu combinations, RECT input/output, last-error
and safe guest memory validation. Stop here; no further API implementation, client
continuation, renderer expansion, Android work, push or release.

[Structured checkpoint](results/compare/getfocus_world_resume.json).
Full local evidence: `out/recovery/getfocus-20261024-01/`.

# CRT tolower and first-world-tick phase — integrity stop

2026-10-23, US Eastern. **No first world tick completed.** Execution advanced
through the previously blocked later actor, then stopped at keyboard-state
initialization. A subsequent unexpected change in a pinned experimental executable
triggered the required integrity stop before the next client build and full regressions.

## Exact identities

HEAD remains `673a4d3e502549a2b49f9051b6099c41c9a73c38`. All original pending
changes were copied and hashed before editing. No commit, push or release was made.

The last valid, completely retained experimental run used:

```
experiments/xrt/build/tolower-world-client-02/xrt_ucc.exe
SHA-256 696d5734773612cb1620f81c9985b752265affedabdee870fd11c383c311e6fa
```

Its exact 27-file runtime source aggregate is:

```
0f910161f4928c561e753651d96889c9cb670a41ae33ef8132efe7cdba28efec
```

`client-identity.json` records generated inputs, every compiled object, baseline
identity, source state and binary. The unchanged client/observed Engine objects
were copied only after checking their recorded hashes and all compilation headers;
the runtime was rebuilt serially in a fresh directory. `reuse.json` records that
provenance. The exact runtime source has also been preserved and its aggregate
verified in `results/raw/tolower-world-20261023/build02-runtime-source/`.

The current **uncommitted** runtime source includes the subsequent SetKeyboardState
adapter, which passed the native/lifted fixture but has **not** run in a client:

```
930233a0dd0ca0e2853fa1a6ab6ab7f52c4bb5616d77a82fb3f9dc4048831202
```

## Native/translated CRT comparison

The native x86 fixture calls the actual isolated msvcr70 export; the x64 fixture
calls the actual runtime import table. Both full **2^32-input return sweeps** pass,
with zero differences against the full-width C-locale mapping: only integer
65 through 90 change, by adding 32. Every other signed-int bit pattern, including
EOF, is retained. There is no unsigned-byte truncation or host CRT delegation.

The separate 397,314-case corpus checks all bytes/EOF, dense signed boundaries,
all high words and seeded random bits, with errno, last-error, cdecl stack cleanup
and callee-saved registers. C, C+MBCP932 and C+MBCP1254 outputs are byte-identical
to the candidate. New native CRT threads preserve last-error and have independent
errno addresses; guest-thread errno storage is also checked.

English/1252, Turkish/1254 and Japanese/932 were measured separately and differ
from C, including non-ASCII, EOF and some out-of-domain last-error effects. They
are not implemented. `setlocale` and `_setmbcp` remain explicitly unbound.
See [fixture scope](tests/tolower_boundary/README.md) and
`results/raw/tolower-world-20261023/oracle-final/result.json` for exact identities,
all results and the distinction between exhaustive return and sampled state checks.
An additional guest-TEB fixture was written but **not run** after the integrity stop.

## Genuine execution evidence

Run: `results/raw/level/20261023-213843-9b35dfe9-candidate/`.
Selected CS_Intro world: **0x12f52800**. All **74,358 events** are retained, zero dropped.

| Milestone | Verified result |
|---|---|
| CS_Intro LoadMap returns | Yes, selected world identified from paired caller return |
| Initial map lifecycle | 268 calls and 268 paired returns per stage, 267 distinct actors |
| All observed selected-world lifecycle | 279 calls and 279 paired returns per stage, 278 distinct actors; none unpaired |
| Previously pending actor `0x1474ee00` | All three stages returned; PostBeginPlay call 26237, return 26259 |
| UGameEngine::Init | One entry, zero returns |
| UGameEngine::Tick | Zero entries, zero returns |
| Selected-world ULevel::Tick | Zero entries, zero returns |
| D3D CreateDevice / Present | Zero / zero; existing adapter query calls only |

The next reproducible execution fatal is **USER32!SetKeyboardState**, from
**WinDrv.dll+0x44bd**, in UWindowsViewport::UpdateInput. The client explicitly exits
**75**. GetKeyState was bridged only after a native/lifted fixture passed.
The later SetKeyboardState fixture passes 1,024 key queries across four thread-local
state patterns, input-buffer preservation, signed SHORT results, last-error, a NULL
buffer failure (0 / error 998), and explicit rejection of virtual key 256.

The first new run exceeded the old 32,768-event capacity: 74,358 events, 41,590
dropped. Its milestone verdict is rejected and preserved. The observer capacity
was increased to 262,144 before the valid second run. Engine tick now has dedicated
paired observations with its measured RET-4 cleanup. Pairing also prevents one return
from satisfying multiple calls; entries alone never establish completion.

## Integrity finding and held gates

The next relink stopped **before compilation** because client 01 no longer matches
its recorded executable hash. Three repeated reads, repeated again in the final
audit, consistently produce:

```
Recorded d17d8f639f671d1f382dcb9e0da4a4d7b7d9f9a39b7c96ff99ce9228e54a0c11
Observed 6f2d48ad78aa77c28e827e89ad77ede3a5d41d52bdf18e33b9dc99a137e6b9fe
```

The observed executable is copied to `results/raw/tolower-world-20261023/binary01-at-stop.exe`.
No repair or overwrite was attempted. Cause, timing and physical-write attribution
are unestablished; no hardware-health conclusion is drawn.

The original validated `72080d0b…` binary and client 02 still match. All recorded
objects in the three checked client directories, baseline generated objects,
generated source and helper identity match. Prior controlled-validation evidence
has **zero differences**. The 4,122-file manifest, three protected trees and nine
protected files match before/after execution and in the final audit:
`3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`.
Neither the original installation nor original saves was read or modified.

The tolower oracle, five focused observer tests and GUI/keyboard differential pass.
The full serial client build, serial runtime relink and fixture compilations pass;
no C1001 or D8040 was observed in these compilations. Historical compiler instability
remains unresolved. **Commandlet/VM, compiler acceptance, full Python, Gate-F CRT,
floor/ceil and remaining integration suites were not rerun**: the integrity stop
took precedence. Their previous results remain preserved, not claimed as fresh passes.

Known findings remain open: expanded CRT **110 mismatches / 1,796 pending**,
**six ACP 932 differences**, and x87 sticky-status, tag/large-input and
double-rounding limitations.

The smallest next experiment is an owner-reviewed integrity investigation of the
preserved client-01 discrepancy, starting with repeated read-only binary/object/source
comparisons and explicit provenance. Hold game execution until that gate is resolved.
Then use a fresh serial runtime relink to test the already fixture-tested
SetKeyboardState adapter and resume the paired Init/tick observations.

[Structured report](results/compare/tolower_world_resume.json).
Full raw phase record: `results/raw/tolower-world-20261023/FINAL_REPORT.json`.

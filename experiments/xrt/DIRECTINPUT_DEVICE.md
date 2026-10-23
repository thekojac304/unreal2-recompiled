# Measured DirectInput device checkpoint — 2026-10-23

The translated game passes the previously fatal mouse creation boundary through real x64 Windows
DirectInput. Its genuine next fatal is **U2AI.dll not linked into that executable**. Compiler/game
execution is now held because repeated unexplained MSVC failures appeared in different units.
No new protected asset/source-byte discrepancy was found, and no hardware-health claim is made.

## Asset isolation and source identity

All **4,120** files in `sandbox_cmp/level` matched the last DirectMusic run's recorded final state
(`before` plus `written`, less `deleted`). No hardlinks or reparse components were present. Preserved
configuration/Golem inputs matched the historical staging or pre-run manifest. The VMProbe package
and ini matched the preserved successful original run. DirectMusic helper/oracle/client identities
and original runtime/generated digests were checked before new game/compiler execution.

Independent `copy2`/`copytree` inputs now live under `sandbox_inputs/first-world/content`. Pristine
configuration replaces the old run's mutable configuration there; diagnostic logs are omitted.
Three later-required packages were already in preserved reference `dc9cc5ddd1c5-dxvk` and matched its
recorded hashes: U2Player_A.uax, HUD_Fonts.utx and UI_Fonts.utx. Nothing was sourced from the installation.
The resulting **4,122-file** manifest has SHA-256
`3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`.

`tools/xrt/asset_boundary.py` verifies the source, three protected trees and nine protected files.
It rejects hardlinks/reparse components, missing/changed files, and run destinations overlapping
protected inputs. Experiment wrappers retain before/after checks. Commandlet staging checks relevant
System/probe inputs before and after every copy; outer suites check the complete protected trees.
Client runs also hash their working copies before/after and reject changes to protected run inputs.
Only isolated Save/Cache, configuration/log files and the known generated Golem.u are mutable.
Old disposable commandlet/compiler trees are archived under `sandbox_archive`, not deleted.

The active installation-read paths were removed:

- `make_sandbox.py`, and consequently commandlet/compiler acceptance, use only the configured manifest.
- `level_probe.py` preparation/package staging and `graphics_reference.py` use that snapshot source.
- The compiler unit test reads snapshot Unreal2.ini instead of installed Unreal2.ini.
- The DirectMusic negative guard test still attempts its explicit forbidden source path; the helper denies it.

There is no installation fallback when a manifest/package is absent. Argument-driven installation
audit utilities were not run. Legacy `trace_original.py` targets sandbox_ref and is now refused by the
destination restriction; adapt it deliberately before future use. Original installation/saves, registry,
drivers and global settings were not modified. The prior Ogg/storage/bugcheck history remains unresolved;
same-drive hash agreement does **not** prove RAM/storage health. The installation was not recensused here.

Identity evidence: `results/raw/resume-source-checkpoint.json`,
`results/raw/resume-assets-initial-manifest.json`, `results/raw/resume-final-integrity.json` and the
manifest at `sandbox_inputs/first-world/manifest.json` (workspace relative).

## Interrupted regressions closed before input development

`results/raw/directmusic/regressions-d38bb485195a/result.json` is complete and passing against the preserved
DirectMusic client SHA-256 `414bdec39c84023eb018348b6ec1e59c42304df680bc6c28fe164dff5f45016b`.
Fresh passes cover IPC/native comparison (normal plus 17 IPC cases), DirectInput/D3D8 COM, GUI, class,
module, file, startup/memory, COM, exceptions, CRT Gate-F, nine commandlet/VM cases, compiler acceptance,
traced VMProbe and Python. CRT Gate-F has **51,536 cases, zero mismatches**. Compiler acceptance passed
16 compiles (four expected invalid-source failures) and 12 execution comparisons. Python passed
**153 tests, 17 expected skips**. Native/original and translated runs were serialized.

These are fresh passes for the preserved implementation, **not** full acceptance for the later input/world
changes. Existing expanded CRT **110 mismatches / 1,796 pending**, six ACP 932 differences, x87 status,
large-input/tag and double-rounding limitations remain visible. Unrelated large corpora were not rerun.

## Actual device path and differential

Fresh original input traces are `results/raw/graphics-startup/b7dcd6a6fc3a-dxvk` and final
`0781777c3ebf-dxvk`. They run isolated content and pinned DXVK, close normally after three Presents,
and complete without observer drops. The observer tracks returned COM objects and actual caller returns;
it reads arguments/output memory without injecting input or replacing API results.

WinDrv requests `GUID_SysMouse` (`6f1d2b60-d5a0-11cf-bfc7-444553540000`) through IDirectInput8W.
CreateDevice implicitly supplies IDirectInputDevice8W; there is no requested-IID argument to that method.
CreateDevice returns S_OK/non-null. The game supplies 24-byte DIDATAFORMAT, 16-byte object records,
relative flags 2, 16 state bytes and seven objects; x64 uses explicit 32/24-byte host structures.
It sets device buffer size 1024 and relative-axis mode, then encounters buffered reads and acquisition
before D3D CreateDevice. No controller enumeration, device capability query or Poll occurred.
Later native cooperative-level/Unacquire calls occur beyond the translated run's current stop.

Implemented typed device operations: CreateDevice, QI/AddRef/Release, SetDataFormat, the two observed
SetProperty types, Acquire and GetDeviceData. Guest interfaces/vtables remain 32-bit allocations;
native COM pointers stay in private typed host tables. Data-format GUID/object pointers are marshalled
explicitly. Buffered records convert guest 20-byte records to native 24-byte records; unmapped high
application data is rejected, with the native all-ones sentinel converted explicitly. Device lifetimes
are independent of the factory. Tombstones are not reused; cleanup releases owned device references
before parent references. No success/status/input data is fabricated.

`results/raw/input-device-oracle-final.txt` passes **seven positive and six explicit negative probes**.
Native x86 and translated logs match exactly. Coverage includes the 8W and IUnknown identities,
missing-IID failure, AddRef/Release counts, two independent devices, parent release before device release,
unknown GUID `80040154` with NULL output/canaries, actual setup HRESULTs, unacquired buffered-read error
`8007000c` with unchanged count/buffer, acquisition S_OK then S_FALSE, zero-capacity acquired reads,
stale/unmeasured rejection and cleanup of two outstanding device references.

Acquired **nonempty** data was not differentially tested. Other layouts, properties, aggregation,
interfaces and methods remain unsupported. Native capabilities/enumeration/callback structures were
not encountered, so no speculative implementation was added. Immutable fixture binaries, results,
runtime-source hashes and reports are under `results/raw/input-device-checkpoint-20261023/`.
The post-stop metadata additions to compare.py were syntax-reviewed, not executed.

## Genuine game progress and separate world milestones

Executed client: `build/input-device-client-01/xrt_ucc.exe`, SHA-256
`be14698cec8b62d6e12ed5203ad3de5871f37e944432566be026a758740f862d`.
Run: `results/raw/level/20261023-194110-8023b9db-candidate`, **24,208 events, zero drops**.
CS_Intro LoadMap returns world `0x12f52800` at 24158. Actual mouse CreateDevice, SetDataFormat and both
SetProperty calls return S_OK at 24175–24178. The first fatal (24197) is loading U2AI.dll, present in the
verified tree but absent from this linked client. Real device/parent references are released at teardown.

T1 is verified. T2 remains **unverified**: the initial loader observer misses direct Engine calls.
T3–T6 are unreached; **zero selected-world ticks completed**. There is **no translated D3D device or Present**.

The final original reference independently pairs all **268 calls and returns per lifecycle stage** to
its selected world through actor GetLevel (native accessor offset d4), covering **267 distinct actor
addresses**, not 268 distinct actors. It completes four selected-world ticks, one D3D CreateDevice and
three normal Presents. These original results do not establish translated ticks, pixels or interactive play.

## Preserved unaccepted work and stop

Pending source changes add U2AI linkage at `1c6d0000`, an Engine observer for direct as well as indirect
calls, build/identity selection, and conservative milestone logic/tests. U2AI was lifted only from the
verified snapshot; generated code is ignored. The observer keeps the original checked return/preemption
behavior and matches actor world, thread, object, stack and return target. Its three Python logic tests
passed, but it has **no genuine translated-game acceptance**. These experimental changes remain uncommitted.

`build/input-world-client-04` compiled and all recorded source/object/binary hashes were verified;
its binary is `72080d0b1972a635ee9b788b6b19e4b2093365c217c1b7ef79a725a8f26b06bb`.
It was **never executed**. It is not an accepted replacement for the executed client above.

Preserved compiler evidence:

- `input-world-client-build-02.txt`: forced-include path error, corrected in later attempts.
- `input-world-client-build-03.txt`: MSVC C1001, Engine_032.
- `input-world-client-build-04.txt`: completed broader observed build, Engine_032 at /Od; unexecuted.
- `input-world-client-build-05.txt`: C1001 in unchanged ParticleSystems_001.
- `compiler-particle-isolated.txt`: same unit passes isolated /O1; protected inputs unchanged.
- `input-world-client-build-06.txt`: C1001 in unchanged Unreal2_000, then D8040.

Logs are in `results/raw/`; each has a companion integrity record. Superseded failed compiler processes
were ended; their files were preserved. No build error is counted as a compatibility pass. No further
compiler/game run was made after the final instability stop. The full post-input regression sweep remains
incomplete, and source/hash agreement does not explain or dismiss the compiler failures.

The smallest next experiment is an owner-reviewed, bounded **compiler stability check**, using one unchanged,
hash-pinned unit, serial compilation into separate fresh directories, bounded process lifetime and before/after
source/input hashes. Keep game execution held. After that gate, validate the pending U2AI/world-observer client
and run affected integration/commandlet/VM/compiler/Python checks before accepting it. If D3D CreateDevice is
then encountered, preserve that boundary and propose its focused native/translated oracle; do not begin a
renderer expansion. No Android, editor, portable DirectMusic, supervisor, push or release work was done.

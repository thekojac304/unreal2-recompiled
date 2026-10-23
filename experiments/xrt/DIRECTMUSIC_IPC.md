# Bounded DirectMusic helper — integrity stop, 2026-10-23

The approved x86 helper faithfully executes the measured native DirectMusic session. The focused x64
IPC driver and existing x86 oracle have **identical stdout**, including all HRESULTs, 14 routine names,
logged reference counts and normal shutdown counts. A separate lifetime case checks IUnknown identity.
The real translated game uses the same preserved
helper executable, completes Script.Init, receives the real native empty-routine error **8878121b**, and
returns from **CS_Intro LoadMap with world 0x12f52800**. No script result is synthesized or replayed.

**Work stopped because another unexplained source Ogg byte difference appeared.** The final regression
sweep was interrupted, so this is an identified checkpoint, not full regression acceptance. No input or
renderer expansion was undertaken. [Structured evidence](results/compare/directmusic_ipc.json) binds the
tested executables, protocol, native reference, candidate reports and installation observations.

## Milestones and first remaining dependency

Two candidate runs reproduce the same boundary, each with 24,186 events and zero drops:

- `results/raw/level/20261023-134136-ee6b8487-candidate` (initial client).
- `results/raw/level/20261023-134708-45cf0e57-candidate` (final bounded-write transport).

In the final report, Entry LoadMap returns at event 23395. The second LoadMap begins at 23400; its
CS_Intro package PostLoad returns at 23933. Script.Init succeeds at 24153, volume setup at 24156,
and the real empty CallRoutine returns 8878121b at 24157. **LoadMap then returns to its recorded caller
at 24158 with non-null world 0x12f52800**, paired by thread, stack and actual return address.

The first remaining fatal is `IDirectInput8W::CreateDevice`, at WinDrv.dll+3153, caller +3156, during
UWindowsViewport construction. UGameEngine::Init has not returned. Neither ULevel::Tick nor
UGameEngine::Tick is in Engine's executed-function set. **Zero selected-world ticks completed.**
PreBeginPlay/BeginPlay/PostBeginPlay functions are in that set, but this observer does not pair their
per-actor returns or bind every actor to the selected world. Consequently milestone 3 is **not separately
verified**. The highest independently verified requested milestone is **2**, not a claim of completed
selected-world actor lifecycle or a tick. No translated device/frame is established.

A fresh serialized original reference, `results/raw/graphics-startup/dc9cc5ddd1c5-dxvk`, exits naturally
with code 0. Its complete observer has no drops: CS_Intro has 268 of each actor lifecycle entry, four
selected-world ticks paired through their caller returns, one successful device creation and three
successful Presents. This agrees with the existing original reference. Pixels and interactive play remain
unverified. The original and translated clients were executed sequentially.

## Implemented COM/backend boundary

`runtime/hle_dmusic_guest.inc` owns 32-bit guest interfaces/vtables and guest-local tool callbacks.
It consumes backend-neutral messages and opaque IDs. `dmusic_backend_pipe.inc` selects the Windows
transport; `dmusic_pipe.h` owns pipes, processes, deadlines and Jobs. A replacement backend can implement
the same measured operations without changing translated COM marshalling. No portable backend was begun.
The previous native x64 Loader8 fixture/capability gate remains available when IPC is not selected.

The helper owns every selected-backend DirectMusic COM pointer on its main STA. Implemented operations:

- Loader8 and Performance8 creation using the measured CLSID/IID, NULL outer, context 3.
- Actual QI/AddRef/Release; canonical IUnknown identity; bridge-owned counts distinct from native counts;
  monotonic opaque IDs, stale handles rejected, unexpected successful interface aliases rejected.
- InitAudio with measured NULL pointers, type 8, 128 PChannels and flags 0x3f; actual DirectSound output;
  GetDefaultAudioPath and the measured AudioPath graph query.
- Native graph insertion of a proxy for the actual translated game tool. AddRef/Release, Init, QI,
  delivery, media count and media types execute the actual guest methods on the owning host thread.
  QI permits only measured IUnknown/Tool/Tool8/IPersistStream requests. The game supplies E_NOTIMPL for
  Init, E_NOINTERFACE for the two unsupported measured IIDs, delivery 0x10 and types 13/14.
- Isolated Music search directory; Intro.con container load; pointer-free 848-byte Script1 descriptor
  with flags 0x206, validated before transmission; actual Script.Init(performance,NULL).
- Container/script ReleaseObjectByUnknown, signed 32-bit master volume, native CallRoutine(empty,NULL),
  Stop(NULL,NULL,0,0), CloseDown and apartment cleanup.

Native HRESULTs and native AddRef/Release return values cross unchanged. The oracle includes Script
Release 15, Performance Release 18 before loader teardown and Loader Release 0. These nonzero intermediate
counts remain visible. The game's observed unbalanced AudioPath/apartment references are owned and
reclaimed by runtime teardown. Fatal cleanup releases the five remaining bridge-owned references; it
does not pretend the game executed normal Stop/CloseDown. Native residual lifetimes end with the child.

Every unmeasured guest method, descriptor, named routine, tool callback, ProcessPMsg and Flush fails
explicitly. Production permits only the measured empty routine and Script1/Intro.con path. Enumeration,
the missing test identifier and deliberate fault operations require the helper's explicit test mode;
the game starts it without that flag. Present routines are never executed by these probes.

## IPC, containment and tests

Protocol v1: magic `31424d44`, fixed **2000-byte** little-endian frames, UTF-16LE strings, sequence/type/
size/version validation, 128 object slots and eight tool proxies. No native/guest pointer is sent.
One request is outstanding per owning thread, with at most 128 synchronous callback replies and an
absolute **10-second** deadline including callbacks. Pipe writes use a cancellable worker that touches
no guest/COM state; read and write failures kill/disconnect the child. Cleanup waits are separately
bounded. The existing runtime watchdog also bounds a stalled translated callback.

Only private pipe ends and a diagnostic handle are inherited through an explicit handle list. The child
starts suspended, is placed in a noninherited kill-on-close Job with a one-process limit, then resumes.
Host process exit closes the Job. Pipe EOF exits the idle helper; a stuck native call is killed by the
host deadline/Job. STA ownership/reentrancy violations fail explicitly.

The helper has a process-local NtCreateFile/NtOpenFile guard, installed before COM initialization.
It verifies the installed WoW64 five-byte MOV EAX prologues rather than guessing instruction lengths.
Game disk opens are read-only under the isolated sandbox; traversal, other disk locations, writes and
reparse components are rejected. Necessary Windows component reads, this exact helper executable,
Defender's MpOav.dll and measured audio/COM device endpoints remain accessible. This is a bounded guard
for trusted installed components on this host, not a general hostile-code security sandbox. Its patches
are private to the helper process; no disk DLL, registration, system setting or Microsoft binary is changed
or redistributed. Accepted game asset opens are logged and confined to sandbox Music/Intro.con.

Final independent acceptance is `results/raw/directmusic/ipc-3fb42bf9e393/result.json`: native session
plus 17 IPC cases pass. It covers exact normal-session equality; QI identity and reference lifetime;
stale/invalid handles; version, size, kind and sequence rejection; truncated frames; unsupported opcodes;
child crash and stall deadline; host disconnect; host exit/Job termination; source/traversal/write denial
and sandbox read acceptance; unexpected named routine, ProcessPMsg and callback rejection. Fault diagnostic
contents are checked. The 150-ms stall test returns in approximately 207 ms, including launch.

Exact preserved identities used by the final game run:

| Artifact | SHA-256 |
|---|---|
| `ipc-3fb42bf9e393/dmusic_helper.exe` | `a141ffe197f3eb14ed5908c946bd3cb541fdf456175b5a602b52df1b64484d22` |
| `ipc-3fb42bf9e393/ipc_session.exe` | `6534dd309abbc58711fa2edb44385a182949639595ff56221a611e144acbd1f7` |
| Preserved native oracle executable | `a1e062eb4828654068b04fc1318710fd528e3aca16b32acf257101e977c87c54` |
| `runtime/dmusic_backend.h` | `a9538e02b6e2c74b3883d513f6e71ee85a99747ed7d4e33b35ad50274d22331d` |
| `build/dmusic-client-final/xrt_ucc.exe` | `414bdec39c84023eb018348b6ec1e59c42304df680bc6c28fe164dff5f45016b` |

The preserved binaries are under `results/raw/directmusic/`; generated game code and binaries remain
git-ignored. The final client identity binds runtime sources, reused verified baseline objects and lifts.

## Regression coverage and required integrity stop

Before interruption, final-source DirectInput, DXVK D3D8, GUI, class and module suites passed in
`results/raw/directmusic/regressions-a47140efbc8b`. Its `complete:false` is essential; `STOP.json` explains
the integrity cancellation. The file suite had started but did not complete. Earlier in this phase, COM
six positives/four negatives and Python 149 tests (17 expected skips) passed. The startup fixture initially
needed a new explicit-fatal unused callback stub; that correction has **not been retested**.

Final commandlet/VM, compiler, exceptions, CRT, startup, file and COM/Python reruns were **not completed**.
Their existing coverage and earlier passing artifacts are preserved; they are not promoted to fresh
acceptance for this binary. Existing expanded CRT, ACP 932 and FPU-status findings remain open.

The pre-development 4,757-file census exactly matches `directmusic-install-final.json`, including Save
metadata and the known two-byte Ogg difference. After the bounded game runs, a read-only census observes
one changed hash: installed M03_fite_loop2.ogg now reads as
`7ab03f8502a91390cb54c94ed345b16ce21eae484e0b082394e9b3f6f81cff8d`, previously
`413bccc0468b2fa9716e927037646e4c7fc29c699395495d95780a0d3bfce2b4`.

The new difference is offset **487591**, preserved snapshot **96**, installed **d6**. Together with the
prior offsets 489527 and 489791 there are now three differing bytes. Three repeat reads agree. Size
3,677,906 and recorded mtime 1511068956 are unchanged. Page 115 now fails CRC (`9c2729c1` stored versus
`0eca77c8` computed); page 116 retains its prior CRC failure. The other **4,756 files and Save metadata
match**. No claim is made about physical-disk writes, timing or cause from cached reads alone.

Current bytes are preserved at `results/raw/dmusic-ipc-ogg-at-stop.ogg`, alongside both full censuses and
`dmusic-ipc-ogg-escalation.json`. The preserved sandbox copy still hashes to
`b6261e7e09ca82b48361702d09ea6d24c7d24a85b4073dd1ff1920f1317318bb`. Neither copy was repaired.
The helper's guard test explicitly rejected opening the source installation. That observation does not
establish the cause of the independent source read discrepancy.

All experiment execution was stopped on detecting this additional change, as instructed. Further
execution requires an owner decision on the integrity escalation. Extending DirectInput/viewport or
graphics support is also outside this bounded helper checkpoint and needs further approval.

## Commands retained for later owner-authorized resumption

Do not resume these while the integrity stop remains unresolved.

```powershell
cmd /d /c experiments\xrt\dmusic_helper\build.cmd
.venv/Scripts/python -I experiments/xrt/tests/directmusic_boundary/compare_ipc.py
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\dmusic-client-final\xrt_ucc.exe'
$env:XRT_DMUSIC_BACKEND = 'ipc'
$env:XRT_DMUSIC_HELPER = 'E:\Unreal2-Port-Investigation\experiments\xrt\results\raw\directmusic\ipc-3fb42bf9e393\dmusic_helper.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --d3d8-backend dxvk --package Textures/SubTFonts.utx --timeout-ms 45000
.venv/Scripts/python -I tools/xrt/dmusic_regressions.py --binary experiments/xrt/build/dmusic-client-final/xrt_ucc.exe
```

Windows/x86 Microsoft COM, VBScript, DirectSound/audio, STA, pipe and Job dependencies remain. The existing
Win32 GUI/DirectInput and DXVK D3D8/D3D9/Vulkan dependencies are unchanged. The backend separation allows
future replacement but does not itself make music portable to Linux/Android. No portable implementation,
general multimedia rewrite, source repair, push or release was performed.

# DirectMusic characterization and owned COM boundary — 2026-10-23

The translated client now executes real `CoInitialize(NULL)` and creates a native x64 Loader8 through
the typed guest COM boundary. It stops explicitly at native x64 Performance8 `80040154`, NULL output.
**CS_Intro LoadMap has not returned, its selected world is not established, and no translated world tick
has completed.** Entry LoadMap and CS_Intro package PostLoad still complete. No game logic is bypassed.

Starting Git state was clean at `936dcb7b61825c5a1cb422c786ec3b77f53dbaa9`, a later documentation
checkpoint descending from the requested `0fcd8b0`. Both are preserved. No remote push or installed
component registration was performed. This phase stops for the owner's architecture decision below.

The reproducible [comparison](results/compare/directmusic_initialization.json) binds the original traces,
observer, identical restored input manifests, translated binary and COM results. Full operand snapshots,
private implementation calls, HRESULT/refcount histograms and script evidence remain in ignored raw results.

## Original execution, including normal cleanup

Final original references use the existing pinned DXVK 3.1.1 x86 pair and four genuine dynamic packages.
`4906743bd050-dxvk` uses `-nosound`; `7a8c2b9db8e8-dxvk` omits only that flag. Both receive WM_CLOSE
after the third normal game Present and **exit naturally with code 0**, without observer drops. Each
completes CS_Intro LoadMap, 268 of each observed actor lifecycle call, four paired selected-world ticks
and three successful Presents. ASLR pointers, elapsed time, stream polling and internal method counts vary;
these are not deterministic whole-world comparisons or pixel/input verification.

The actual game-side initialization sequence and HRESULTs are identical in both runs:

1. `AMusicScriptEvent::execCallRoutine` → `DMCallRoutine(actor, empty routine, "Intro.Script1")`.
   It enters the music manager and calls `CoInitialize(NULL)` at Engine `18177f`, returning S_OK.
   The underlying request is STA (`COINIT_APARTMENTTHREADED=2`).
2. `CoCreateInstance` with NULL outer and class context **3** creates Loader8 and Performance8, both S_OK.
3. `Performance8::InitAudio(NULL, &sound, NULL, 8, 128, 0x3f, NULL)` succeeds. The default path is
   dynamic stereo, with 128 PChannels. A real DirectSound object and default AudioPath are created.
4. Loader `SetSearchDirectory(GUID_DirectMusicAllTypes, "..\\music\\", FALSE)` succeeds.
   `GetDefaultAudioPath` and AudioPath `GetObjectInPath(0, 0x3200, 0, GUID_NULL, 0, IID_IDirectMusicGraph, out)`
   succeed. The game inserts its real tool into the graph and releases its local tool/graph references.
5. Tool `AddRef` occurs. Its `Init` returns **E_NOTIMPL**, which the native graph tolerates. Native queries
   for Tool8 (`0e674303-3b05-11d3-9bd1-f9e7f0a01536`) and IPersistStream return E_NOINTERFACE and NULL.
   Delivery is `0x10`; media-type count is 2 and types are 13/14. The game supports IUnknown/IDirectMusicTool.
6. Loader `LoadObjectFromFile(CLSID_DirectMusicContainer, IID_IDirectMusicContainer, "Intro.con", out)`
   succeeds. Loader `GetObject` receives an actual x86 848-byte DMUS_OBJECTDESC: valid flags `0x206`,
   class DirectMusicScript, name `Script1`. It returns the real script interface.
7. `Script::Init(performance, NULL)` succeeds. Container removal from the loader and local Release both
   return S_OK/zero. `SetGlobalParam(GUID_PerfMasterVolume, &minus706, 4)` succeeds.
8. `Script::CallRoutine(L"", NULL)` returns **8878121b, DMUS_E_SCRIPT_ROUTINE_NOT_FOUND**. The engine
   returns from DMCallRoutine and continues genuine level initialization. It never receives fabricated success.

Public interface identities extracted from the actual game factory operands:

| Object | CLSID | Requested IID |
|---|---|---|
| Loader8 | `d2ac2892-b39b-11d1-8704-00600893b1bd` | `19e7c08c-0a44-4e6a-a116-595a7cd5de8c` |
| Performance8 | `d2ac2881-b39b-11d1-8704-00600893b1bd` | `679c4137-c62e-4147-b2b4-9d569acb254c` |
| Container | `9301e380-1f22-11d3-8226-d2fa76255d47` | `9301e386-1f22-11d3-8226-d2fa76255d47` |
| Script | `810b5013-e88d-11d2-8bc1-00600893b1b6` | `2252373a-5814-489b-8209-31fedebaf137` |
| Graph | queried through AudioPath | `2befc277-5497-11d2-bccb-00a0c922e6eb` |

The observer also records actual internal COM creation and QI, rather than assuming only these five
interfaces exist. Native loading instantiates containers, 32 segments and numerous tracks, wave/synth and
VBScript objects. Performance QI includes IDispatch, an older Performance IID and private interfaces.
These transitive native calls are evidence, not additional implemented guest methods.

During normal close, the game releases the script from the loader (S_FALSE), then its script reference
(15 references remain). It calls Performance Stop(NULL,NULL,0,0), then CloseDown, both S_OK. The local
Performance Release returns **18**, not zero: script/container internals still own it. DirectSound's local
Release returns zero. Final Loader Release returns zero; observed downstream Script and Performance
Release sequences also reach zero. The tool's graph-owned reference is released. Intermediate nonzero
Release counts are retained rather than treated as leaks by themselves.
The returned default AudioPath has one observed Release returning **1**; no balancing game-side Release
of the GetDefaultAudioPath reference is observed. That remaining path lifetime ends with the process.

The game makes one measured STA CoInitialize call and **does not call CoUninitialize from Engine's music
destructor**. Full traces retain Windows/library initialization and cleanup separately: DirectSound's attempt
to initialize MTA on the STA thread fails with RPC_E_CHANGED_MODE; dedicated native audio/script threads
initialize and uninitialize on their own threads. An API hook does not intercept every private internal COM
entry; aggregate process-wide balance must not be inferred by summing nested CoInitialize/CoInitializeEx.
The translated boundary balances the references it owns at orderly/handled-fatal cleanup, rather than
reproducing the game's unbalanced music initialization until process teardown.

## What -nosound changes

It suppresses the separate ALAudio path in this bounded comparison: ALAudio is loaded only in the sound
run. It **suppresses neither DirectMusic device creation nor starting its real output stream**. Both runs
execute native DirectSoundCreate8, cooperative-level setup, primary-buffer setup, and successful WASAPI
IAudioClient Initialize and Start. Render-client GetBuffer/ReleaseBuffer traffic follows even with -nosound.
The sound run additionally starts the separate engine audio stream. Initialization parameters and all
paired game-side DirectMusic results match between the two runs; their full staged input hashes match.

No named music routine, Performance PlaySegment/PlaySegmentEx/SendPMsg, or game Tool.ProcessPMsg was
observed before the three-Present stop. Native timing/queue queries, PChannel mapping, message allocation
and the audio worker still execute internally. Stream activity does not establish audible music, PCM
equivalence or later cutscene behavior. In particular, the empty routine failure does not justify omitting
successful script initialization, transitive object loading, the graph or the real output path.

## Compatible implementation evaluation

| Candidate | Verified scope and license | Consequence for this game |
|---|---|---|
| Installed Windows x64 COM | Native probe and actual translated calls: Loader8 succeeds; Performance8 class is unregistered. System32 has dmloader/dmusic/dmsynth, but no dmime/dmscript. Windows system components; no redistribution is proposed. | Cannot supply the measured Performance8/container/script path. No success substitution. |
| Installed Windows x86 COM | Actual original game and independently built native session execute the measured methods and cleanup, using installed Microsoft components. | Authentic current oracle and practical child-process candidate; Windows/x86 dependency remains. |
| Wine, pinned `840a939ee526137639665ff5f587224d6a36403f` | LGPL-2.1-or-later dmime/dmscript sources inspected. Performance has a substantial implementation; **Script Init and CallRoutine are explicitly success-returning stubs**. Wine runtime dependencies also require integration. | Not an authentic drop-in solution for the required script path. No Wine binary was represented as tested here, and no LGPL source was linked into this runtime. |
| GothicKit/dmusic, pinned `b73b270b94714b8ec8d9d0b2a9f3a5c445da52d1` | MIT Modern Variant; C11 source and Windows/Linux/macOS build support. Loader/Performance/render API supports segments/styles/DLS. Inspected API/source has no required COM Loader8/Performance8 interface or VBScript/container execution layer. | Potential future portable segment/audio component, not this phase's compatible backend. No game compatibility or tested binary architecture is claimed. |
| libdmusic, pinned `790662e71120ff70359033083eb5a8a5751d5300` | MIT; C++ source and documented 32/64-bit Windows builds. Segment rendering/playback utilities; ScriptTrack constructor is empty and container/toolgraph parsing remains TODO. | Cannot implement the observed script initialization/routine semantics as supplied. No game binary was validated. |

Primary sources: [Wine script](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/dmscript/script.c),
[Wine Performance](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/dmime/performance.c),
[GothicKit API](https://github.com/GothicKit/dmusic/blob/b73b270b94714b8ec8d9d0b2a9f3a5c445da52d1/include/dmusic.h),
[GothicKit license](https://github.com/GothicKit/dmusic/blob/b73b270b94714b8ec8d9d0b2a9f3a5c445da52d1/LICENSE.md),
[libdmusic](https://github.com/libdmusic/libdmusic/tree/790662e71120ff70359033083eb5a8a5751d5300).
Exact downloaded pins/sources remain under ignored `third_party/directmusic-research/`. This is a bounded
candidate survey, not proof that no other implementation exists.

## Implemented and independently compared behavior

`hle_dmusic.inc` calls real host CoInitialize/CoInitializeEx, records every HRESULT and counts S_OK and
S_FALSE as owned references. RPC_E_CHANGED_MODE acquires no reference. Each guest thread runs on its
own host thread; object calls check that owner. Normal worker exit releases that thread's Loader8
references before balancing its apartment. Main-thread handled-fatal cleanup does the same. Cross-thread
fatal stops and watchdog termination rely on process teardown for other live threads; cleanup never
calls another apartment's interfaces from the wrong thread.

The native Loader8 wrapper has 32-bit guest pointers/vtables and a separate typed native ownership table.
QI preserves IUnknown/Loader8 identity, failures return the real HRESULT/NULL, references reach the host,
and stale guest objects remain tombstones. Twelve other Loader8 slots are named unsupported traps.
Unexpected successful QI interfaces, aggregation, unmeasured classes/contexts and unavailable Performance8
remain explicit diagnostics. No script/audio success adapter was added.

The identical PE32 COM fixture runs natively and through the real lifter/runtime. Six positive probes
match all logged HRESULTs, identities and reference counts; four explicit negative probes cover stale
objects, unsupported GetObject, unowned CoUninitialize and wrong-thread use. Worker cleanup releases two
object references and balances two initializations; main cleanup releases three and balances two.
Evidence: `results/raw/directmusic/com-c111dd6c3002/` (including owner-thread assertions).

The independently built native x86 session, launched by the x64 Python driver, reproduces real InitAudio,
tool insertion, container/script loading, Script.Init, native routine enumeration, volume setup, missing
routine failure and cleanup. All 14 native routine names equal those discovered by the independent strict
RIFF/source-name parser. Empty and missing-identifier calls both return 8878121b in native and independent
lookup. **Every present routine raises UnsupportedScript in the independent implementation.** It does
not initialize a script or claim to execute VBScript, schedule music or produce audio. Native x64 stops
at the real Performance8 class failure. The standalone oracle deliberately balances its acquired
AudioPath reference and apartment, unlike the game's unbalanced references described above.
Evidence: `results/raw/directmusic/session-3da7d65653a3/`;
PE machine fields and the 64-bit parent pointer size are checked and recorded.

## Translated milestone and regression checkpoint

Binary `build/directmusic-gate-final/xrt_ucc.exe`, SHA-256
`81a50ef6668a2378a24bd8e0d2f12a82eb328b61555a7fa5c9505801de21c0bd`.
Fresh client/runtime compilation has no warnings; reused generated baseline objects are verified against
`fresh-20261023-015722-b7ee8987`. `client-identity.json` binds the unchanged generated inputs and final runtime.

`results/raw/level/20261023-130516-d075f8bc-candidate/` has 24,139 events, zero drops. Entry's non-null
LoadMap return is paired at 23395; CS_Intro's package PostLoad return at 23933. STA initialization succeeds
at 24132, Loader8 at 24133, Performance8 fails at 24134, and the explicit capability fatal is 24135.
Cleanup releases one Loader8 reference and balances one apartment reference, followed by preserved
DXVK/DirectInput cleanup and StickyKeys restoration. CS_Intro LoadMap return and both Tick entries remain
unreached. No selected-world actor initialization or translated graphics device is established.
Repeat `20261023-131646-576d5736-candidate` also has 24,139 events without drops and the same
COM results/cleanup. The comparison records both identified runs.

Final integrated acceptance: nine commandlet/VM cases PASS (`20261023-130527-3fb45205`), compiler PASS
(`20261023-130658-30bdb7ac`, 16 compiles including four expected failures and 12 executions), traced VMProbe
PASS (`20261023-130926-ae01b0e4`). Fresh public results are under
`results/compare/directmusic_regressions/`; prior public comparison files are preserved unchanged.
Python: 149 tests OK, 17 expected skips. DirectInput, DXVK D3D8, GUI, class, module, binary FILE,
startup/memory and EH component checks pass. Gate-F CRT: 51,536 cases, zero mismatches.

The expanded CRT baseline remains **110 mismatches / 1,796 pending**, not exhaustively rerun; fresh
`fopen.0` still differs. Fresh ACP 932 retains six differences. Existing x87 sticky-status/MXCSR and sine
edge differences remain open as described in GRAPHICS_STARTUP.md. No expectations were weakened.

The installation/Save audit is read-only. All other 4,756 installed files and Save metadata match the
previous census. There is a **newly observed second byte difference in the already disputed Ogg**,
with unchanged size/mtime; timing and cause remain unknown. Three reads reproduce it. Both copies remain
unmodified. See [installation findings](INSTALLATION_INTEGRITY.md) for the exact offsets/hashes/CRC/PCM.

Exploratory failures remain raw and excluded: an incompletely staged reference stopped at U2Player_A;
one package-path attempt and two post-link-failure runs never launched a reference; a lock collision never
restored candidate inputs. Early observer prototypes had incorrect interface slot counts and premature
tombstoning and are not final evidence. Final observers use verified public ABI slot counts and preserve
the actual zero-refcount rule. The final original runs repeat the prior world milestones without drops.

## Owner decision: bounded native helper or portable script/audio work

Recommended next experiment, **subject to owner approval**: an opt-in, project-owned x86 child backend
for the measured initialization window. It would own **all** DirectMusic objects, including Loader8, on
one STA thread. The x64 typed guest bridge would send bounded, versioned requests containing GUIDs,
UTF-16 strings, scalar structures and opaque object handles over private inherited pipes. No native COM
pointer, guest address or HWND crosses the process boundary. No system registration or DLL redistribution
is needed. Child lifetime should be bound to the host with a kill-on-close Job; disconnects/timeouts fail
explicitly. Its resource root must remain the isolated sandbox.

The bounded surface is the observed factories/lifetimes, Loader search/load/get/release-by-unknown,
Performance InitAudio/default-path/volume/stop/close, AudioPath graph query, Graph tool insertion, and Script
Init/CallRoutine. A native tool proxy must implement the measured QI/init/media contract. An unexpected
ProcessPMsg or unsupported method/script must halt with evidence; it cannot be discarded or acknowledged
as successfully executed. A full reverse-callback/event scheduler is outside this proposed first experiment.

Acceptance would require the real native script results and cleanup to match, then genuine CS_Intro
LoadMap return, selected-world initialization and a paired world tick. Any next unsupported graphics or
game boundary stops the experiment; this authorizes no renderer expansion. The current native session
proves authentic operation inside an x86 child, **not** a completed IPC COM bridge or callback solution.

This trades a temporary Windows/x86 dependency for a small authentic oracle path. Keeping the typed
guest interfaces and backend transport separate leaves room for a portable native backend later, but
does not itself solve Linux/Android music. The alternative is to approve a separately bounded portable
RIFF/VBScript/performance design; the surveyed libraries do not eliminate that work. Neither alternative
has begun. The first blocker remains the missing compatible x64 Performance8 implementation.

## Reproduce

```powershell
cmd /d /c experiments\xrt\tracer\build.cmd
cmd /d /c experiments\xrt\tests\directmusic_boundary\build.cmd
cmd /d /c experiments\xrt\tests\directmusic_boundary\build_com.cmd
.venv/Scripts/python -I experiments/xrt/tests/directmusic_boundary/session.py
.venv/Scripts/python -I tools/xrt/graphics_reference.py dxvk --package Textures/SubTFonts.utx --package Sounds/U2Player_A.uax --package Textures/HUD_Fonts.utx --package Textures/UI_Fonts.utx --stop-after-present 3 --close-after-present --music-trace --timeout-ms 120000
# Repeat the preceding original command with --sound for the other configuration.
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\directmusic-gate-final\xrt_ucc.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --d3d8-backend dxvk --package Textures/SubTFonts.utx --timeout-ms 45000
```

Candidate exit 76 is the documented explicit capability stop, not a passing level-initialization result.

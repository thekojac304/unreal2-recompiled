# DirectMusic COM/session oracles

The approved bounded IPC implementation and required integrity stop are recorded in
[DIRECTMUSIC_IPC.md](../../DIRECTMUSIC_IPC.md). Native session plus 17 IPC cases pass; the real game
returns a non-null CS_Intro world, then stops at unimplemented DirectInput CreateDevice. No tick is claimed.
Further execution is stopped pending the additional source Ogg integrity escalation. After owner clearance,
the focused IPC reproducer is `dmusic_helper/build.cmd` followed by `compare_ipc.py` in this directory.

The [current report](../../DIRECTMUSIC_INITIALIZATION.md) records full original initialization, normal
cleanup, the sound/no-sound comparison, native x86 child feasibility and the explicit translated x64 gate.

```powershell
cmd /d /c experiments\xrt\tests\directmusic_boundary\build_com.cmd
cmd /d /c experiments\xrt\tests\directmusic_boundary\build.cmd
.venv/Scripts/python -I experiments/xrt/tests/directmusic_boundary/session.py
```

`build_com.cmd` lifts the same PE32 client used by native Windows and checks six positive/four negative
cases against the real runtime. `session.py` runs a real x86 DirectMusic session from the x64 driver,
compares 14 native routine names and two missing-name failures with the independent RIFF/name oracle,
and retains the real x64 factory failure. Present routines are explicitly unsupported by the independent
code. No translated script/performance backend or IPC bridge is claimed.

## Preserved initial dependency probe

```powershell
cmd /d /c experiments\xrt\tests\directmusic_boundary\build.cmd
.venv/Scripts/python -I experiments/xrt/tests/directmusic_boundary/probe.py
```

The driver extracts the two CLSID/IID pairs directly from the sandbox Engine.dll
data referenced by the original instructions at 18182c/181845. Both native
architectures call CoInitialize twice, then CoCreateInstance with the actual
NULL outer and class context 3. Successful interfaces are released; both successful
apartment references are balanced. No InitAudio, audio device, script, playback,
registration or installation change is performed.

On this host, both architectures return S_OK then S_FALSE for CoInitialize.
Loader8 succeeds on both. Performance8 succeeds on x86 but returns
REGDB_E_CLASSNOTREG (80040154) with NULL output on x64. This is an explicit
dependency difference, not a translated COM or audio compatibility pass.
The exact binaries, extracted operands and outputs are identified in each fresh
raw result. The translated client still stops at CoInitialize; no synthetic
interface or HRESULT bypass was added. The original game's calls can be observed
with graphics_reference.py --package Textures/SubTFonts.utx --stop-after-music-factory.

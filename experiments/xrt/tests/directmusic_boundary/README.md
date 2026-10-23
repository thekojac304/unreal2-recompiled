# Initial DirectMusic COM dependency observation

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

# Guarded production CreateDevice validation

The project-owned PE32 fixture invokes the production IDirect3D8 slot, creates
owned hidden windows through the production GUI bridge, and uses only device
QI/AddRef/Release/GetDirect3D/GetCreationParameters. No graphical game client or
device rendering method is invoked. Every process makes at most one real native
creation attempt. Use a new output directory for every build revision.

```powershell
.venv\Scripts\python -B -I experiments/xrt/tests/d3d8_create/run.py build --out <fresh-output>
.venv\Scripts\python -B -I experiments/xrt/tests/d3d8_create/run.py run --out <fresh-output>
.venv\Scripts\python -B -I experiments/xrt/tests/d3d8_create/audit.py --out <fresh-output>
```

`production/translated.exe` compiles the unchanged runtime source. The separate
`injected/translated.exe` compiles a retained, generated copy of the boundary
with test-only hooks. Mode 1 sends four nested WM_GETICON callbacks before and
after the real native creation, before guest publication, while the
creation context is active, verifies the entire suspended CPU and 32-byte call
frame, and checks that no device is published. It also tests parent release
during a callback. Mode 2 changes the backend-side depth format to 71 after the
production tuple guard; actual DXVK then fails exactly once. Mode 3 injects
distinct scalar copyback values after a real successful creation to verify every
presentation output offset. Mode 4 seeds host MXCSR immediately before the real
native method. These hooks are absent from production runtime sources and the
new game executable. Modes 5/6 force rejection after actual QI/GetDirect3D acquire
a native reference, verifying module retention for unexpected COM identities.
Synthetic copyback values are never claimed as DXVK output.

The translated host provides two specifically committed pages for pointer guards;
the last presentation DWORD or last two output bytes straddle a protected page.
The audit requires the boundary's named range rejection and zero backend entries.
An exit code alone is insufficient. Pointer, tuple, wrong-type/stale HWND, stale
device/parent, retry and live-window destruction stops are checked separately.

Native x86 and x64 assembly checks seed all nonvolatile GPRs, x64 XMM6..XMM15,
two live 80-bit x87 values, control word 077f and MXCSR 3f80. Translated PE32
assembly separately checks the guest's supported control word 027f, live exact
1.5/1.0 values, status/TOP, nonvolatile registers and stack balance. SIMD guest
instructions remain outside the runtime CPU policy; host MXCSR and native XMM
preservation are tested without claiming translated SIMD instruction support.

`preserve.py`, `build_client.py`, `prepare_regressions.py` and `regressions.py`
retain the phase's preflight, full serial production build, independent copied
regression harness and final integrity audit. Historical evidence is preserved.
The regression harness adapts only the previous CreateDevice-negative diagnostic
to its new NULL-presentation/output range guard; its source change is identified.

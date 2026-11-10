# Physical renderer evidence extension

`owner_batch.py` extends the frozen `desktop_batch.py` by composition. All original
runner, fixture, assertion, audit and delivery files remain unchanged. The original
physical run remains `HELD_MISSING_REQUIRED_EVIDENCE`. Its numerical agreement is
functional differential success, and is not a strict production acceptance pass.

The additive package is `out/recovery/renderer-evidence-20261029-01`. Its
`evidence-delivery.json` pins the collector, runner, independent parser, generated
instrumented fixture sources, build records, binaries and validation receipts.
`preservation.json` pins the original delivery/run/audit, runtime, generated source,
supervisor and protected installation/save identities. No renderer bridge or
production implementation was changed. Fixture source instrumentation uses exact,
single-occurrence anchors; the original assembly trampolines are reused by hash.

From an owner PowerShell on the physical **Default input desktop**:

```powershell
Set-Location 'E:\Unreal2-Port-Investigation'
& .\.venv\Scripts\python.exe -B experiments/xrt/tests/renderer_batch/owner_batch.py run --out out/recovery/renderer-physical-batch-02
```

The output directory must be new. This runs **23 fixture processes**: two state-148
native preflights and seven groups in native x86, native x64 and translated x64.
There are 23 CreateDevice attempts, 13,392 group calls and 13,392 readbacks, plus
eight preflight calls. Groups are post-material states, initial samplers, cache
states, identity transforms, cache stages, NULL bindings and FVF. Four last-error
seeds and two repeated calls per case remain unchanged. Gamma and real
ResizeViewport are outside this command. The collector is a DLL in the owner
Python process and adds no collector subprocesses. Fixtures use the Windows PE
subsystem with CRT `main` entry and captured stdout handles, avoiding implicit
console-host processes. Their disposable measurement windows are unchanged.

The runner verifies the historical and new deliveries before any fixture starts.
It requires an active physical owner console, matching session and SID, visible
WinSta0, and matching Default current/input desktops. Sandbox desktops and remote,
locked, disconnected or switched sessions fail this gate. Each child starts
suspended and enters a dedicated non-breakaway, kill-on-close Job Object before
its first instruction. Job PID/image membership is recorded while suspended and
at both checkpoints. Unexpected descendants are rejected. On failures the job is
terminated and the failure cleanup receipt is retained; forced cleanup cannot pass.

For every PID the saved evidence contains:

- Exact CreateProcess command line, argv, cwd, PID and creation/exit times; actual
  process image path/hash; source/build record, executable/object hashes, compiler/
  linker identities, strict FP flags and original source snapshot binding.
- Owner and child session/console/desktop observations, active display paths,
  sizes, positions, refresh, rotation, scaling, monitor device paths and PCI IDs.
- DXGI physical adapter LUID/vendor/device/subsystem/revision; a query of adapter
  zero through the same pinned DXVK D3D9 pair; D3D8 adapter identity and caps;
  complete loaded-module paths, PE architectures, SHA-256, file versions and
  companies, including the vendor Vulkan ICD and pinned D3D8/D3D9 modules.
- Actual native nonvolatile GPR outputs, x64 XMM6..15, stack delta and raw 512-byte
  pre/post FXSAVE records for every measured call. x86 has no ABI nonvolatile XMM
  registers; its empty XMM output is explicitly checked, not claimed as a probe.
- Actual COM AddRef/Release/GetDirect3D/creation-window observations and final
  zero device/parent counts; DestroyWindow/UnregisterClass/FreeLibrary results,
  invalid window and absent backend modules, independently cross-checked against
  the live process module lists after cleanup; final process/job exit accounting.

DXVK's D3D adapter subsystem and revision fields are retained as observed values.
They are zero in this backend and are not interpreted as the physical PCI values.
The LUID is the primary join to DXGI; vendor/device and the selected-device log
also must agree. The backend source for these semantics is
[DXVK 3.1.1 D3D9Adapter](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d9/d3d9_adapter.cpp).

`stdout.txt` contains fixture observations. `runtime-events.jsonl` is a distinct
synchronous stream from instrumented fixture services, with actual sequence,
PID/TID and time on each event. The `xrt_event` sink records any runtime event calls;
fixture boundary enter/leave observations are explicitly named. Native variants
have no translated-runtime boundary events. The write receipt contains actual
attempted/written/error counts. `dropped_event_count` is **null**, because there is
no queue-drop counter. No full production-runtime telemetry or ETW stream is
claimed. Truncated, missing, duplicate or out-of-order observations, unknown job
members, missing environment, raw ABI, ownership or cleanup data reject acceptance.

`evidence_check.py` validates all of these independently of the original parser;
the original parser runs as an additional unchanged assertion set. Checks run after
each process and the final batch is audited again from disk. A successful run
writes `assessment.json` and an evidence index. A failure writes `REJECTED.json`
and stops the batch. A read-only re-audit writes exclusively to a fresh directory:

```powershell
& .\.venv\Scripts\python.exe -B experiments/xrt/tests/renderer_batch/owner_batch.py audit --batch out/recovery/renderer-physical-batch-02 --out out/recovery/renderer-physical-audit-02
```

Preparation validation uses 28 non-graphical contract fixtures, disposable
message-only HWND/DLL fixtures, real raw ABI emission for all 21 intended group
variants, and synthetic rejection cases. `validation-results.json` and
`validation-output.txt` contain the final results. Each validation directory retains
its own evidence; development failure receipts remain available. No graphics device,
gamma update, genuine game, supervisor change, installation/save change, remote push
or release is performed by preparation.

After the fresh run, functional differential status, physical evidence completeness
and production assessment are separate fields. Complete physical evidence does not
waive the historical **FAILED x87, complete WNDPROC equality or strict native x86**
results. Actual renderer configuration must still be bound to measured caps and a
production profile. Real ResizeViewport/Win32 effects, genuine material/SetRes/outer
initialization and rendered presentation remain unqualified. The batch creates no
production allowlist or combined game candidate and always reports
`production_accepted: false` while these gates remain.

Reproduction without graphics: `prepare_evidence.py build`,
`validate_evidence.py`, `prepare_evidence.py freeze`, `owner_batch.py verify`.
These development commands are separate from the single prepared owner run.

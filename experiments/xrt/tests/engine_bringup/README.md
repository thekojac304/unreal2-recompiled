# Engine bring-up implementation and non-game qualification

This directory implements DirectInput lifecycle and D3D8 scenes, viewports and
copied UP draws in the isolated runtime at
out/recovery/engine-bringup-20261030-01/runtime. It does not launch a game or
alter production runtime/supervisor policy. The current candidate and exact
hashes are in build.json and milestone.json in that output directory.

Run from the repository root with .venv/Scripts/python.exe -B -I.

| Script | Purpose |
| --- | --- |
| integrate.py | Deterministically apply source templates to the staged prior semantic runtime. |
| contracts.py | Compile/run x86/x64 COM-double contracts and real system DirectInput probes; no graphics. |
| regressions.py | Unchanged supervisor/collector tests and staged registered-GUI regressions. |
| phase.py audit | Independently inspect historical consumed SetRes evidence. |
| static_audit.py | Original PE disassembly and generated-source instruction-marker audit. |
| phase.py build | Fresh candidate: recompile adapter owner and verify/reuse unchanged objects. |
| phase.py verify | Independent source/object/header/PE/PDB identity and nonconsumption. |
| mapping.py | Offline original/generated/linked Init-return endpoint and adapter bindings. |
| qualify.py | Owned non-game hardware-stop fixtures; candidate mapped SEC_IMAGE_NO_EXECUTE only. |
| prepare_gpu.py | Compile three immutable physical fixture candidates; never submit/run. |
| gpu_evidence.py | Compare three saved stdout files; cannot grant physical acceptance. |
| milestones.py | Copy existing evidence before parsing; pair init/ticks and record scene attempts. |
| test_evidence.py -v | Synthetic corruption/rejection tests; no physical acceptance. |
| phase.py preservation | Verify installation and prior evidence/runtime/supervisor preservation. |
| finalize.py | Verify matching receipts and seal the report/milestone. |

phase.py stage is the one-time initial snapshot/copy and refuses an existing
output directory. Do not restage a completed experiment. Rebuilds use new UUID
paths. Any runtime change invalidates the former candidate, GPU package and
qualification receipts. Rebuild/reverify/requalify dependent artifacts before
sealing. Historical build/fixture directories are retained. There is no genuine
launch command in this workflow.

dinput_lifecycle.inc and scene_draw.inc are maintained source templates; the
copied runtime is the exact compiled implementation. integrate.py also updates
typed interfaces, slot bindings and DirectInput ownership/cleanup.
scene_fixture.c incorporates the prior suite against the new runtime.
Its services are declared doubles, not claims of GPU implementation.

Scope limits: UP inputs use private host copies (64 MiB per block). Unknown
resources/programmatic shaders and unsafe pointers still stop. Viewport getter
revalidates output protection after native callbacks. Real DirectInput
inner-native transfer is measured separately from strict comparison of two
independent invocations; the Acquire last-error discrepancy remains visible.

The physical package includes triangle readback and Present. Its ABI records
surround the outer wrapper, not inner-native call registers. Fixture readback
uses host surfaces and does not implement guest surface COM support. Physical
execution still requires the existing owner/service infrastructure and
collector process, desktop, backend/module and Job evidence. Never replace an
existing failed collector verdict with supplementary numerical comparison.

The proposed genuine endpoint is **before guest 0x1090ED5C**, after checked
UGameEngine::Init return. continuation-design.json leaves observer installation,
physical acceptance and owner authorization pending. The offline milestone
parser is evidence analysis, not enforcement. No main-loop tick is admitted.

API references used during implementation:

- [Microsoft SetCooperativeLevel contract](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee417921(v=vs.85)).
- [Pinned DXVK v3.1.1 D3D8 implementation](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_device.cpp), including viewport validation and UP binding resets.

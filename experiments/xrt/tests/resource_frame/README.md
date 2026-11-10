# D3D8 resources and first-frame preparation

This experiment extends the sealed engine-bringup runtime in
`out/recovery/resource-frame-20261030-01/runtime`. Production runtime, historical
candidates, supervisor policy and original installation/saves are preserved.
There is no genuine-launch entry point here.

The integrated runtime supports typed surfaces, textures, buffers, native
reference counts, device-first release, mip/container access, copied locks,
non-NULL bindings, buffer draws, and declaration-only vertex shaders with
multiple streams. Shader programs, Reset, cube/volume textures and resource
private-data interfaces remain guarded. See the experiment's `REPORT.txt` and
`remaining-unsupported.json` for exact scope and final candidate identity.

Run scripts from the repository root with `.venv/Scripts/python.exe -B -I`:

| Script | Purpose |
| --- | --- |
| `phase.py stage` | One-time preservation snapshot; refuses an existing experiment. |
| `integrate.py` | Regenerate this runtime from the sealed prior input and templates. |
| `contracts.py` | Build/run x86/x64 resource, renderer, scene and DirectInput contracts; also real system DirectInput. |
| `phase.py audit` | Independently pair saved genuine SetRes CPUs, native calls, stop and cleanup. |
| `static_audit.py`, `path_audit.py` | Original PE/generated-source inspection, including Lock and declaration-only shader callsites. |
| `regressions.py` | Unchanged supervisor, collector and registered GUI regressions. |
| `phase.py build`, `phase.py verify` | Fresh candidate and independent complete source/object/PE/PDB/nonconsumption audit. |
| `mapping.py` | Resolve the checked Init-return instruction and all linked adapter bindings offline. |
| `qualify.py` | Owned non-game hardware-stop tests; candidate mapped `SEC_IMAGE_NO_EXECUTE`. |
| `prepare_gpu.py` | Compile native x86/native x64/translated x64 resource fixtures through existing fixed recipes; no submission. |
| `resume_audit.py` | Read-only recheck of all three recipes, executable/source/toolchain identities, qualification seal, authorization ledger, pending requests, genuine candidate and preserved inputs; writes a fresh readiness directory. |
| `gpu_evidence.py` | Supplementary comparison of three saved stdout files; never grants physical acceptance. |
| `test_evidence.py`, `test_observer.py` | Synthetic corruption/rejection tests. |
| `phase.py preservation`, `finalize.py` | Verify preserved inputs and seal the final report. |

Every build uses a new UUID directory. Failed/intermediate builds remain intact.
Runtime edits invalidate the previous build, contracts and physical package;
regenerate all dependent receipts before finalization. These fixtures exercise
the actual compiled adapters using declared COM doubles. Doubles are never
reported as native GPU evidence.

The physical package covers four texture mip levels, aliased surface readback,
VB/IB uploads, FVF and declaration-based two-stream geometry, 16/32-bit indices,
render-target/viewport identity, scene boundaries, guest-surface pixel readback,
Present and native cleanup. It uses synthetic geometry, never a game scene.
The existing collector's process/desktop/module/Job checks remain mandatory.
Its old numerical parser may reject the new records; retain that failure and
run the supplementary parser separately. Neither parser can waive strict gates.
The supplementary parser also requires device creation/ownership records and
the exact argument counts of texture versus surface locks. Synthetic corruption
tests cover missing/duplicate setup records and identical corruption across all
three outputs; these tests are not physical GPU evidence.
Saved stdout parsing also rejects duplicate JSON fields, nonfinite numbers,
truncated records, and invalid HRESULT/last-error integer encodings.

The latest owner startup procedure is in
`out/recovery/resource-gpu-readiness-5a910a46-bb71-4068-bf4b-dea0b4aa50e7/OWNER-STARTUP.txt`.
Its read-only checks found the service stopped, authorization expired, no safety
latch or STOP, and no queued/claimed request. Start `serve-fixtures` from the
owner's physical console and enter its local fixture-only authorization phrase.
Do not use the unrelated historical 23-process `submit-acceptance` package for
these three resource fixtures.

A later read-only remote-startup investigation found the physical console active
and desktop access available, but no already-authorized unattended startup and
console-authorization path. See
`out/recovery/remote-fixture-startup-20261030-01/REPORT.txt` for observed tokens,
session topology, unchanged-policy constraints and a conditional launcher design.
No service or launcher was started by that investigation.

The prepared observer captures the full 416-byte CPU before the checked
UGameEngine::Init continuation at guest `0x1090ED5C`, then requests termination
while stopped. It is tested only on owned fixtures and is not installed into
the active supervisor. It cannot launch or authorize execution. The historical
early stop and separate genuine-continuation authorization remain unchanged.

Current explicit capacities: 4096 resource identities, 2048 declaration handles,
256 declaration DWORDs, one outstanding resource map, 64 MiB per map/buffer,
256 MiB aggregate host buffer mirrors, 16 streams and eight texture stages.
All guest ranges are checked across page boundaries. Native mappings are never
exposed to guest code; unlock decommits the guest staging allocation.

Primary implementation references are pinned to DXVK v3.1.1:
[device](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_device.cpp),
[device-child ownership](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_device_child.h),
[subresource ownership](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_subresource.h),
[declaration translation](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_shader.cpp).
Downloaded source hashes are sealed in `native-source-references.json`.

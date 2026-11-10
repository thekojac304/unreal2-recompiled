# Unreal II initialization monitoring milestone — NOT READY

Evidence: `out/recovery/init-runtime-finish-20261030-01`.
This package preserves the baseline candidate
`75530d04d139539a6ae8f51eee49c5b6b7770fad9c99b2536867ccdb0fc2a8cb`
and all prior evidence. It has no genuine launcher, queue submission or policy
activation API. All live execution is project-owned non-game code.

## Changes and qualified scope

- All **145 inventoried host COM call sites** are wrapped. The 126 typed COM
  descriptors include the seven previously missing DirectMusic calls. Interface,
  receiver generation and physical method slot are separate identity fields.
- **95 SDK-checked Windows signatures at 158 sites** record actual native returns
  and compiler-converted arguments. Pointer values remain opaque unless an explicit
  typed span contract exists. Fixed RECT/class/factory spans are recorded.
- Native calls made by GUI diagnostic probes have **support domain 5**. They are
  distinguished from guest-facing native operations. `XmRecord.context` is the
  assembly probe snapshot; it is not claimed to capture exact volatile registers
  at each actual machine API entry/RET.
- DirectInput format object/GUID arrays, property values and device-data arrays
  use the adapter's existing 256-object bound. COM factory/lifecycle returns remain
  real native results. Historical independent Acquire differences remain FAILED.
- DirectMusic host COM and fixed 2,000-byte IPC frames are traced. Live Loader8
  and apartment tests use real native COM; IPC tests use the existing guarded x86
  helper, its unchanged native implementation and child Job containment.
- Resource observations now include binding kind/index, map offsets/format/length,
  release/cleanup state and actual map download/upload bytes up to **16 KiB**.
  Larger payloads stop explicitly; no sampling or digest-only substitution is used.
- Version 2 adds **explicit aborted invocation records** for nonlocal guest EH
  and worker ExitThread. Abort records never masquerade as native returns. The
  monitor keeps checkpoints externally, preserving the generated landing-pad ABI.
  Unqualified exits through nested native callbacks stop safely.
- A table replaces the bitwise IEEE CRC32 implementation. The record schema,
  sequence checks, CRC chain, synchronous writes/flushes, 131,072-record capacity,
  fail-closed sink and independent pending-record collector remain enforced.

## Validation

`qualification.json` identifies all 11 final owned suites. `record-checks.json`
validates 14 completed traces containing 11,138 records, with no outstanding IDs,
plus CRC-valid receiver/interface/generation/slot substitution rejection.

The suites cover native x86/x64/translated GUI comparison and 114 callback scopes;
actual guest EH with six matching native x86 event sequences and 17 abort records;
four guest CPU threads, including explicit ExitThread with two abort records;
real DirectMusic COM and guarded helper IPC; resource/surface/scene operations,
binding/map bytes and native-address reuse; full CPU, last-error and probe FPU state;
write-failure pending capture, malformed streams and production containment.

The broad retained adapter contracts perform 15,331 checks per architecture.
Their deliberately longjmp-reset negative doubles use the sink disabled; these
are separate from live trace-enabled qualification. All 81 supervisor tests pass.

`composition.json` tests the **production debugger factory** with a runtime
collector on owned code. Four permanent critical slots, all-thread DR readbacks,
new threads, fatal capture, monitor failure, environment rejection and
terminate-before-identical-owned-instruction behavior pass. Production policy
and genuine breakpoint activation remain unchanged.

## Performance and readiness

`performance.json` compares the original and final recording implementations.
`performance-stress.json` evaluates larger owned workloads against the unchanged
60-second limit. Every ordinary trace record remains synchronously durable;
no event/check was removed to improve throughput. CRC optimization does not
materially improve end-to-end throughput because file durability dominates.

Read **REPORT.txt** for final measured times, candidate/PDB hashes and exact stop
RVA. The candidate contains 281 verified objects: 265 inherited generated objects,
15 newly compiled runtime objects and one assembly probe. Independent source
regeneration matches every compiled runtime input. PE/PDB identity, all 60 retained
adapter bindings, monitoring symbols and the original/generated stop mapping are
verified independently. Candidate mapping uses SEC_IMAGE_NO_EXECUTE only.

Remaining Init-relevant gates are recorded in `coverage.json` and `readiness.json`:

- Complete variable pointer/message/graphics payload contracts and larger maps.
- Remaining parent/device/window registry transition and native-exception audit.
- The x86 helper's internal native COM calls and InitAudio/tool/script callbacks.
- Real reached guest FPU/error consumers; strict x87/WNDPROC/DirectInput failures.
- Actual-candidate environment/graphics/state checks in the integrated observer.
- A justified genuine event-volume/time budget. Preparation's current sandbox
  desktop also fails the retained environment gate.

Genuine readiness is **NOT_READY**. One launch, 60 seconds, no retry, the verified
Init return stop before guest `0x1090ED5C`, Job/watchdog containment and all prior
safety rules remain unchanged. A bounded 120-second ceiling is a separately
reviewable proposal only. No owner authorization procedure is issued while gates
remain incomplete. No original installation/save, consumed candidate or release
was modified, and no remote push occurred.

## Reproduction — owned preparation only

Use `.venv/Scripts/python.exe -B -I experiments/xrt/tests/init_runtime_finish/…`
from the workspace. Each live suite uses a fresh UUID evidence directory.

1. `integrate.py stage` once; it refuses an existing evidence root.
2. `prepare_sdk.py`; retain the compiler-preprocessed SDK declarations.
3. `finish.py`; regenerate the isolated runtime from immutable prior sources.
4. `build.py`, then `verify.py`; create a fresh unlaunched candidate and verify it.
5. `run_qualification.py`; run all owned monitoring/oracle/containment suites.
6. Run the supervisor unittest discovery suite with output directed into a fresh
   directory under this evidence root; retain its receipt in `supervisor-tests.json`.
7. `record_checks.py`, `performance.py`, `performance.py --stress` and
   `coverage_finish.py`. Performance should run without other trace-writing suites.
8. Run the unchanged `supervisor.environment.Desktop.check` read-only, preserving
   its result in `environment-check.json`; no graphics device or game is created.
9. `reproduce.py`, then `seal.py` (also exposed through `finalize.py`).

Do not mutate the runtime while qualification runs. Command receipts pin runtime
and explicit file inputs; the seal rejects any different qualification runtime.

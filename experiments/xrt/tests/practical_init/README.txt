Practical Unreal II Init tracing -- experimental preparation only

Evidence: out/recovery/practical-init-20261031-01
Final outcome and measured numbers: REPORT.txt, readiness.json, policy-review.json.
There is no genuine candidate launcher or queue submission in this package.

The runtime is an isolated copy of init-runtime-finish-20261030-01. Only monitor.c
and monitor.h change; all memory, filesystem, COM, unsupported-operation, callback
and existing FPU/runtime checks remain byte-identical. Production policy and
supervisor files remain unchanged. common.py installs a reviewed experimental
debugger handle-ownership correction in this interpreter only. Windows owns the
original debug-event process/thread handles; the observer owns duplicates.

Use .venv/Scripts/python.exe -B -I with scripts in this directory:
  setup.py                 stage a NEW evidence root once (refuses existing root)
  transform.py             deterministic recorder generation, before qualification
  build.py; verify.py      build fresh candidate and verify PE/PDB/281 objects/stop
  run_qualification.py     owned suite/oracle/containment checks, fresh UUID outputs
  handle_checks.py         16 independent Jobs / rapid thread exit ownership stress
  performance.py           matched benchmarks; run without other tracing suites
  record_checks.py         independently check final traces and identity mutations
  support_checks.py        81 unchanged supervisor tests, read-only desktop gate,
                           fresh deterministic runtime reproduction
  prepare_candidate.py     construct actual pinned observer for review; run refuses
  final_checks.py          current collector/composition/music/record/support checks
  seal.py                  preservation, separate policy review and NOT_READY report

The semicolons above denote separate ordered commands, not a shell script.
Run each command separately. --resume on run_qualification.py is for an interrupted
owned qualification only; the final seal also checks every consolidated runtime
receipt. Never change runtime sources during qualification. Failed development
attempts remain in their exclusive UUID directories.

Profiles are selected explicitly via XRT_MONITOR_PROFILE. Unset means forensic;
unrecognized values stop. OPEN records identify the profile, buffer capacity,
batch size and omission mask. Version 3 keeps the fixed 1856-byte CRC-chained
record, adding CHECKPOINT=10 and OMITTED=11.

Forensic: all prior captured payload categories and strict evidence requirements,
FILE_FLAG_WRITE_THROUGH plus a successful FlushFileBuffers on every record.
Experimental development: all essential events, CPU/probe FPU/error state,
typed calls/results and reference/binding/map metadata; ordinary records batch
256 at a time. Resource map upload/download bytes are the only new omissions.
An OMITTED record names each omission and its requested byte count. The profile
OPEN mask declares both categories even when no such event is reached.

Accepted records (xm_recorded), completed writes (xm_written) and flush-confirmed
records (xm_committed) are separate. A 4096-record, 7602176-byte tail never wraps
or overwrites. Normal batches hold at most 256 records while draining. If a write
or flush fails, the entire tail and pending attempt stay available for debugger
capture, and the next operation is the fail-closed xm_failure boundary. A total
131072-normal-record ceiling is followed only by a terminal failure sentinel.
All threads serialize sequence/invocation assignment and tail access under the
existing SRW lock. There is no asynchronous writer, drop mode, or backpressure
that permits unobserved native execution.

OPEN, CLOSE, FATAL, GAP, explicit CHECKPOINT, Init-return and every full batch
flush. Init-return therefore flushes its paired return record before reaching
the separately mapped endpoint. Idle unflushed records have no time-based
durability guarantee. Interrupted snapshots are preserved raw and rejected if
their counters, tail, CRC or nesting cannot be reconciled.

Flush success uses the Windows persistence contract. Hardware power-loss and
storage-firmware honesty are untested. File visibility and WriteFile completion
alone are never called durable. At controlled stops the collector separately
copies and fsyncs the disk prefix, memory tail, pending record and counters; that
preserves independent evidence without retroactively making the guest sink's
tail durable. Abrupt kill/power loss without a successful independent capture
can lose the unflushed tail and is incomplete evidence, never an accepted run.

Opaque pointers are identities, never permission to dereference. Missing typed
pointer payloads remain explicit forensic evidence gaps; experimental Init does
not require exhaustive unrelated whole-engine payload capture. Probe snapshots
are not exact volatile registers at every actual native instruction. Existing
strict x87, WNDPROC and independent DirectInput differences remain FAILED.

Current actual candidate endpoint is verified using SEC_IMAGE_NO_EXECUTE. Live
hardware/readback tests use an identical owned instruction; no candidate
instruction or genuine Init has executed. Existing production endpoint/policy,
consumed candidates, original installation and saves remain preserved.

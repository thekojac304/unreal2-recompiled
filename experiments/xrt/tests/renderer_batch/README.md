# Renderer batch preparation

This is an isolated development/fixture package. It never modifies the accepted runtime,
existing candidates, supervisor, original installation or saves. No GPU is needed for
preparation, the CPU gamma byte differential or the contract tests.

The [readiness report](../../../../out/recovery/d3d8-batch-20261029-01/REPORT.md)
contains all nine groups, exact evidence scope, preservation results and the ordered
physical-desktop batch command. Each group has an independent runtime snapshot and
reviewable patch under that report's `snapshots/` directory.

`prepare.py` stages and incrementally builds native/translated boundary fixtures;
`gamma_input.py` compares original x86 gamma arithmetic with generated x64 input bytes;
`test_audit.py` checks evidence rejection; `finalize.py` audits and freezes the bundle.
`desktop_batch.py plan` prints the future native/translated DXVK batch without running it.
`desktop_batch.py verify` verifies frozen delivery and backend hashes without graphics.
Only `desktop_batch.py run --out <fresh directory>` measures GPU behavior; it refuses RDP.

Contract tests use explicitly declared COM/callback doubles and are never graphics
compatibility passes. ResizeViewport's protocol probes do not qualify the actual
WinDrv window/callback body. Native DXVK behavior and that real Windows gate remain
pending; every new source snapshot is provisional. Strict x87 and complete WNDPROC
equality remain separately FAILED.

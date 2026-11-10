# Loaded-module identity repair

Current package: `out/recovery/renderer-evidence-20261029-03`. The original
`renderer-evidence-20261029-01` and failed `renderer-physical-batch-02` remain
unchanged. `EVIDENCE_CAPTURE.md` is retained as frozen historical documentation.

From an owner PowerShell on the physical Default input desktop:

```powershell
& 'E:\Unreal2-Port-Investigation\.venv\Scripts\python.exe' -B 'E:\Unreal2-Port-Investigation\experiments\xrt\tests\renderer_batch\owner_batch.py' run --out 'E:\Unreal2-Port-Investigation\out\recovery\renderer-physical-batch-03'
```

Only that later `run` command creates graphics devices. Preparation and validation
do not run a physical batch or a genuine game. The new output must not exist.

The old x86 child reported `System32/nvspcap.dll`, which is absent in the 64-bit
collector's filesystem view. `SysWOW64/nvspcap.dll` exists as an x86 PE. A real
non-graphical x86 probe reproduces the path mechanism with `version.dll`: the
loader reports System32 while `GetMappedFileNameW` identifies the SysWOW64 image.
The historical child has exited with zero Job members, so its old live mapping
cannot be re-queried and no successful old module hash is invented.

The collector retains each original native snapshot as `*.raw.json`. Enriched
snapshots use the live kernel mapping, a read-only file handle, canonical final
path, file ID, whole-file SHA-256, version information and matching in-memory PE
architecture/timestamp/image size. File sharing denies writes and rename/delete
through hashing and the mapping recheck. No basename search, guessed System32
replacement, cached hash or module skip is used. Canonical paths continue through
the pinned backend, approved project image and actual NVIDIA ICD checks.

Three bounded enumeration attempts retain failures. A disappeared module is
recorded as unloaded only after fresh enumeration excludes it and it is no longer
mapped as an image. An image still mapped off-list remains unresolved across
retries. Missing files, access/sharing denial, PE mismatches and unstable mappings
are recorded explicitly and reject acceptance. The independent saved-evidence
parser rechecks canonical file identities and hashes, including owner snapshots.

A never-resumed child may have an uninitialized loader list. Its explicit
pre-resume receipt is accepted only at the suspended stage and cannot qualify a
loaded/cleaned checkpoint. Those checkpoints require complete identified module
inventories. Unknown or unreadable mapped images cannot pass.

`test_module_identity.py` covers missing/inaccessible images, stale enumeration,
proved unloads, still-mapped departures, PE/mapping changes, protected module names,
file-ID substitution and the stage restriction. Real x86/x64 probes identify
mapped Windows images; a real file-pin test verifies that a write handle is denied.
`validate_evidence.py` additionally retains the original ABI, ownership, runtime
stream, containment and negative parser coverage. No renderer implementation,
filesystem guard or supervisor endpoint is changed.

All collector/fixture timestamps use GetSystemTimePreciseAsFileTime, matching the
kernel process lifetime clock. A fast non-graphical process exposed an earlier
coarse-clock observation preceding its kernel exit time by 0.26 ms. The old
receipt is retained. Exact lifecycle inequalities remain enforced, without a
tolerance or rewritten timestamps. The intermediate package `renderer-evidence-
20261029-02` is retained as development evidence and is not the owner package.

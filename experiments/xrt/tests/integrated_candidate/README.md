# Integrated experimental candidate

This handoff adopts the completed surface-transfer runtime and executable without
changing or relinking them. All resource, surface, DirectInput, GUI and scene
adapters are tested together. No additional D3D8 domain is implemented.

The output is `out/recovery/integrated-candidate-20261030-01`. `REPORT.txt`,
`physical-batch.json` and `continuation-design.json` define the candidate and the
two separate future experiments. Neither experiment has been executed or submitted.

From the repository root, use `.venv/Scripts/python.exe -B -I` with these scripts:

| Script | Scope |
| --- | --- |
| `phase.py verify` | 279-object source/header/toolchain/PE/PDB lineage and nonconsumption |
| `contracts.py`, `gui_contracts.py`, `regressions.py` | Combined COM doubles, actual system DirectInput, real USER32, supervisor and collector regressions |
| `offline_checks.py` | Original-PE audits and isolated evidence/observer unit tests |
| `mapping.py` | Exact linked Init entry/return, PDB device layout and 60 HLE bindings |
| `construction_check.py` | Construct the actual candidate observer without creating a process |
| `qualify.py` | Owned hardware-stop tests; candidate mapped SEC_IMAGE_NO_EXECUTE |
| `qualify_composed.py` | Exact staged handler composition on owned non-game protocol code |
| `prepare_gpu.py` | Compile three immutable GPU fixtures; never execute or submit |
| `package_audit.py` | Verify fixture recipes, expanded adapter sources, objects, backend/toolchain identities and unchanged authorization state |
| `acceptance.py <x86-capture> <x64-capture> <translated-capture>` | Read-only supplemental audit of complete saved physical evidence |
| `phase.py preservation`, `finalize.py` | Preservation and integrated handoff seal |
| `verify_handoff.py` | Read-only verification of the final seal, receipts, source identities and preserved inputs |

`phase.py stage` is one-time and refuses an existing output. Rechecks write fresh
UUID evidence directories and replace only the current consolidation receipts.
Do not run the tests with a single unittest discovery process: retained suites
use the same module names and modify import paths. `offline_checks.py` runs each
suite in an isolated interpreter and preserves every result.

The revised physical fixture uses coordinate-dependent pixels, so ignored or
misplaced rectangle copies fail. Resource output presence and four mip levels
are explicitly validated. Its geometry remains synthetic, its ABI capture is
around the outer wrapper, and GetFrontBuffer is tested only with NULL output.
DirectInput and GUI have separate non-GPU differential coverage.

The current collector's legacy numerical schema does not recognize these records.
Keep that failure. `acceptance.py` reruns the unchanged physical process, desktop,
module, GPU/ICD, Job and cleanup assertions before comparing all three raw outputs;
it never grants formal acceptance or overwrites collector verdicts.

The staged continuation checks the original Init entry and return CPU, caller,
stack, preserved registers, object, host thread, runtime event pair and absence of
ticks. The entry and permanent return stop consume two hardware slots; fatal and
CreateDevice environment checks consume the other two. The old constructor's
40-byte registry assumption is replaced only in the staged instance with the
freshly verified 280-byte PDB layout. Active supervisor code and authorization
remain unchanged. Activation and one bounded genuine execution require separate
owner authorization after physical evidence review.

No game, physical GPU fixture, service startup or remote-console attempt is part
of this workflow. Existing strict x87/WNDPROC failures and independent DirectInput
Acquire last-error differences remain recorded.

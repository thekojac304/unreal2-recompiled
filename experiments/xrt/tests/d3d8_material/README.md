# Bounded SetMaterial development

This phase never launches a genuine client. It preserves and independently
audits the verified eight-state run, characterizes the next operation on pinned
DXVK x86/x64, and stages a bridge plus a separate supervisor preview.

The operation is `IDirect3DDevice8::SetMaterial`, slot 42, at guest
`0x0696f31d`. The proposed endpoint is before guest `0x0696f323`.

The complete [report](../../../../out/recovery/d3d8-material-20261029-01/REPORT.txt)
contains the exact material contract, PE/PDB identity, tests, strict failures and
owner review steps. `runtime.patch` and `enforcement.patch` in that directory
describe the staged changes. Production sources remain untouched.

Development drivers, in order, are `phase.py` (preserve, audit-prior, inspect,
native-build, native-run, native-audit), `translated.py` (stage, build, run,
audit), `candidate.py` (build, mapping), `enforcement.py` (stage, revise,
finalize_stage), `regressions.py`, `live_observer.py`, `verify.py`, and
`finalize.py`. Use new phase/build/output names for any future reproduction;
existing output directories, failed fixture setups, consumed candidates and
qualification attempts must remain intact.

`enforcement/owner_start.py` and `enforcement/command.py` are later owner entry
points only. They were prepared but never executed. The new policy requires a
fresh explicit owner batch; the old three unused slots cannot authorize it.

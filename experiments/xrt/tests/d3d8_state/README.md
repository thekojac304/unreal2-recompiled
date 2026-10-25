# Exact measured SetRenderState fixtures

Production supports `(7,1)`, `(9,2)`, `(29,0)`, `(26,1)`, and `(143,1)`.
`run.py` and `audit.py` take
`--state N --value V`; state/value defaults remain 7/1. Compiler fixture-only
STATE_TARGET/VALUE_TARGET also apply the selected tuple to identity, lifetime
and reentrant negative cases. The corrected saved-slot invalid-this approach
is retained. Production GetRenderState stays guarded.

Use fresh directories and run serially: `run.py native-build`,
`run.py native-run`, `audit.py native`, `run.py build`, `run.py run`, and
`audit.py translated`, each with `--out PATH --state N --value V`.

New evidence: `out/recovery/d3d8-gouraud-20261025-01`.
Every new tuple has independent native and translated validation, fresh prior
tuple regressions, a fresh serial production build and one bounded genuine
continuation. All earlier output and source backups remain intact.

Earlier recovery notes remain preserved in the prior evidence directory and
this phase's source-preservation tree.

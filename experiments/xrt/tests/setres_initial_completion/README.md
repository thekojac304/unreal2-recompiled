# Initial SetRes completion preparation

The isolated package observes the genuine initial WinDrv call at `0x11104BF5`
and stops before its continuation at `0x11104BF8`. Lock recovery is classified
separately and is not admitted as the initial invocation.

Runtime evidence is a genuine source change in an isolated `xrt_loader.c`
and its new `setres_evidence.inc`: complete raw CPU and argument-frame records
are emitted at entry and paired return without changing guest results, CPU,
configuration or renderer methods. The existing 238-call profile is preserved.

Preparation and fixture commands never launch the game. See the output package
`out/recovery/setres-initial-completion-20261029-01/REPORT.txt` and its verified
seal before considering the separate owner action. The owner launcher requires
two new local phrases: explicit stop-scope authorization, then one-shot launch
authorization. It retains the existing consumed markers and diagnostic hold,
and refuses changed identities, evidence, ledger state, STOP files or replay.

Strict x87, WNDPROC and native-x86 compatibility remain failed. Passing owned
ABI/debugger fixtures does not change those broader compatibility results.

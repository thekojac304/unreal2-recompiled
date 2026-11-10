# SetRes completion preparation — October 29, 2026

This directory adds a separate fixed owner launcher. Preparation does not change
the production supervisor, its authorization, its queue, or its permanent stop.
Evidence and the readiness report are in
`out/recovery/setres-completion-20261029-01/`.

The exact integrated candidate is independently checked against its complete
source, transitive object, serial compile/link, PE, PDB and dependency identities.
The original caller's `call [edx+78h]` at guest `0696D2CA` returns to `0696D2CD`.
The prepared permanent hardware stop is candidate RVA `05A7F813`, bytes
`89 7B 44`, before the generated PC assignment for that next guest instruction.
The checked `xrt_icall` return and conditional bad-return trap precede it.

Non-game hardware tests map the exact candidate with `SEC_IMAGE_NO_EXECUTE`;
no candidate entry point or instruction runs. They read back its bytes and live
hardware registers on the initial and newly created thread, use all four slots,
reject slot overflow and wrong bytes, and terminate before a project-owned
identical instruction. An injected observer failure also terminates before
continuation. This verifies inert candidate mapping and debugger enforcement;
the genuine candidate endpoint has not been hit.

The copied initial observer/audit retains CreateDevice, Clear, Present, all eight
earlier states, device/COM/window identities, callback guards, CPU/FPU, stack,
arguments, input memory, and fatal evidence. The extension adds SetMaterial,
238 configured calls, ResizeViewport and the checked SetRes EAX/ret20 endpoint.
Its cache ordering is independently checked by executing the unchanged generated
195-call cache body with owned object/method dependencies. The tuple inventory
is an allowlist, not an execution-order oracle.

The launcher binds the exact PE/PDB, guarded runtime, generated source, objects,
dependencies and qualified observer sources with read-only file pins. It uses
the established physical desktop gate, module verification, exclusive locks,
Job, independent watchdog, isolation, input restoration and a retained
parent-owned desktop gamma restoration guard. The whole committed event stream
must equal stopped memory at completion. A failure ends the attempt and leaves
a hold; no automatic retry or authorization reset exists. The global ledger
claims the executable before CreateProcess, across all batches.

Historical strict x87, WNDPROC equality and native-x86 compatibility remain
FAILED. Gamma's measured native MXCSR precision effect is recorded explicitly;
unclassified differences fail closed. No production compatibility or gameplay
acceptance is implied. Genuine device gamma readback is not injected into the
guest sequence; input, VOID/last-error/MXCSR effects and parent desktop effects
are captured, with the earlier physical device readbacks retained separately.

Owner procedure, only after choosing to authorize this exact experimental attempt:

1. Stop any running fixture or genuine supervisor locally with Ctrl+C so the
   existing exclusive locks are released. Existing STOP files and unresolved
   holds remain effective; this launcher never clears them.
2. On the signed-in physical desktop, use ordinary PowerShell:

```powershell
& 'E:\Unreal2-Port-Investigation\.venv\Scripts\python.exe' -B -I 'E:\Unreal2-Port-Investigation\experiments\xrt\tests\setres_completion\owner.py' launch-once
```

3. After both physical checks, type this exact phrase in that local console:

```text
AUTHORIZE ONE SETRES COMPLETION D6071F6563300DC4 BEFORE 0696D2CD FOR 60 SECONDS
```

This authorizes one immediate fixed launch, with a five-minute prelaunch expiry,
60-second wall-clock watchdog, and termination at the endpoint or first failure.
Ctrl+C or `out/recovery/setres-completion-20261029-01/STOP` cancels it. There is no
queue submission step. Preparation must stop before running this owner command.

Non-game validation entry points are `prepare.py`, `qualify.py`, and
`test_observer.py`. Existing evidence is not reset by a rerun: live tests use new
UUID directories and initial preservation refuses an existing evidence root.

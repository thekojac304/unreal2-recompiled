# Post-splash fatal diagnosis, October 28

This phase preserves the consumed `getobject-recovery-20261028-01` owner run,
including its complete sandbox, source state, exact EXE/PDB and debugger data.
It contains no automatic genuine-client execution path.

`diagnose.py` proves the fatal caller and guest API from the retained PE/PDB,
registers and 25,840 raw runtime events. The `%s` argument was the thread-local
DirectMusic transport error buffer. Its pointer was saved but the bytes were not.
The complete historical string, including its Win32 suffix, is irrecoverable from
these retained records. A roughly ten-second interval supports a transport
deadline hypothesis; it does not establish the exact string or native HRESULT.

`observer_evidence.py` adds bounded, raw-byte capture of a `%s` argument while the
fatal debug event is pending. It leaves percent characters inside that string
untouched, records unreadable/unterminated values without inventing a message,
and retains the original callback, stack, output-routing and strict-delegation
checks. Ten unit tests, two live non-game debugger cases and the independent
execute-stop selftest pass.

`native_init.c` and `ipc_init.c` characterize the captured real InitAudio tuple.
Native x86, guarded native x86, and the unchanged production x86 helper through
the real x64 transport all return S_OK and real DirectSound objects locally.
They retain the production 10-second transport deadline. These are native/IPC
probes, not a new translated-guest acceptance claim. The consumed owner failure
was not reproduced; no DirectMusic, GUI, renderer, or x87 runtime behavior was
changed to force success.

`prepare.py` binds a one-shot owner Default-desktop probe and a conditional
genuine diagnostic package. The owner probe is non-game only. It does not launch
the diagnostic continuation afterward. The genuine launcher requires a passing
owner probe, separate owner authorization, a fresh sandbox and one session with
the existing 60-second watchdog and permanent stop before guest `0x0696f292`.
Known strict x87 and complete WNDPROC equality failures remain unwaived.

Run the prepared owner action only from the new phase's output directory, using
the command in its report. All historical output paths and consumed markers are
exclusive and must not be reset or reused.

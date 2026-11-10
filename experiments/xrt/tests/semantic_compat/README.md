# Isolated SetRes semantic compatibility investigation

The comprehensive handoff is in
`E:\Unreal2-Port-Investigation\out\recovery\semantic-compat-20261029-01\REPORT.txt`.
The staged runtime and fresh candidate are experimental. This directory has no
game launcher, queue submission or supervisor policy mutation entry point.

From `E:\Unreal2-Port-Investigation`, use `.venv\Scripts\python.exe -B` with:

| Script | Scope |
| --- | --- |
| `prepare.py refresh` | Regenerate the isolated runtime from the preserved baseline and these templates. |
| `prepare.py build` | Build a fresh UUID candidate, compiling both GUI and D3D-owning misc units. |
| `verify.py` | Independently verify source/object/link/PE/PDB identity, actual HLE bindings and initial SetRes endpoint. Never execute the candidate. |
| `contracts.py` | Compile actual adapters for x86/x64 against declared COM doubles, including the original cache and full CreateDevice adapter. No GPU. |
| `differentials.py boolean` | Execute exact original Boolean-store/sampler fragments in an owned probe versus the lift. |
| `differentials.py gui` | Compare real USER32 MoveWindow/GetIcon calls using disposable windows. |
| `regressions.py attach`, `registered`, `resize` | Run focused original/lifted import, callback and ResizeViewport checks. |
| `live_observer.py` | Run the proposed observer on owned adapter protocol fixtures with Job/watchdog cleanup. |
| `qualify.py` | Inert candidate mapping and owned hardware-breakpoint/failure fixtures. No candidate instructions. |
| `inventory.py`, `imports.py` | Regenerate exact guard and original direct-IAT callsite inventories. |
| `finalize.py tests` | Run observer, unchanged supervisor and renderer collector suites. |
| `finalize.py observer_tests` | Record a final observer-source-bound receipt without repeating unchanged suites. |
| `finalize.py preservation` | Verify preserved trees and record current saved fixture availability. |
| `report.py` | Assemble the report and semantic-change register from final receipts. |
| `finalize.py package` | Seal the prepared handoff; does not authorize or execute a game. |

`prepare.py stage` was the initial one-time preservation/staging operation. Do
not repeat it over an existing package. A refresh/build invalidates downstream
receipts; rerun the relevant checks and reseal. Keep failed development evidence.
No script should be pointed at an original installation or saves.

The scalar adapters forward actual results and keep typed memory, COM ownership,
callback and ABI protections. Strict historical x87/WNDPROC/native-x86 failures
remain separate and unchanged. Passing protocol doubles and inert binary checks
do not qualify new physical GPU domains. Physical fixture reauthorization and
qualification must precede any separately authorized bounded genuine attempt.

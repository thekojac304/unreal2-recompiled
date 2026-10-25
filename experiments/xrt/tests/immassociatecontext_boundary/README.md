# Measured ImmAssociateContext boundary

The identical project-owned x86 DLL calls real Windows IMM32 natively and through
the normal lifter/runtime import table. `build.cmd native` measures the oracle;
`build.cmd translated` builds and compares the runtime. Existing output directories
are refused by the native build. No original game installation is required.

56 calls across two actual OS/guest threads verify existing non-NULL default
contexts, detach, repeated detach, restoration, reassociation with the same context,
shared default-context identity between windows, independently created custom
contexts, and survival of a default context after window destruction. Three
last-error seeds are compared. Each sample restores the native reference's input
state before executing the x86 probe; result identity and actual post-call
association are checked, along with ESP and EBP/EBX/ESI/EDI preservation.

12 more calls compare NULL, arbitrary invalid, invalid -1 and destroyed HWNDs.
On this machine NULL preserves last-error; nonzero invalid/destroyed HWNDs return
NULL and set 1400. Detach/restore clear last-error on association changes, whereas
repeated detach and same-context association preserve the sentinel. Results are
delegated to IMM32 rather than encoded in the adapter.

Six isolated unsupported cases retain native evidence and require an explicit
translated stop: unknown HIMC, wrong-type HIMC, foreign HWND detach, foreign HWND
reassociation, foreign-thread HIMC, and a context whose owning thread exited.
Native foreign-window detach actually changes the association and returns the
previous context; foreign-context reassociation fails without changing it. A
single native call is used here: a foreign thread cannot reliably restore the
reference state for a second call. These cases are deliberately outside this
adapter's supported contract, including the native-successful foreign detach.

The adapter uses typed XH_WINDOW and XH_IMC tokens. It never passes guest handle
bits to IMM32 or exposes native handle bits in guest memory. Borrowed HIMC identity
is scoped to a stable XrtThread record and its OS thread, independent of window
lifetime. The bridge does not destroy borrowed contexts. Only contexts obtained
from this boundary may be reused. Guest context creation/destruction, arbitrary
external host mutation, general IME functionality and cross-thread associations
remain unsupported. Invalid nonzero HWNDs use the measured invalid -1 host
sentinel after checking it is invalid, so actual IMM32 supplies the failure.

API contract: [ImmAssociateContext](https://learn.microsoft.com/en-us/windows/win32/api/imm/nf-imm-immassociatecontext).
Thread default-context ownership: [Input Context](https://learn.microsoft.com/en-us/windows/win32/intl/input-context).

# Measured SetFocus boundary

`build.cmd native` compiles and executes the native x86 oracle. `build.cmd
translated` lifts the same DLL, builds the actual runtime adapter and compares
the results. `build.cmd` does both in an exclusively new output directory.

The positive and borrowed-window cases compare 44 paired SetFocus calls,
including nested calls. They cover sibling A/B/A transitions, previous HWND
identity, same-window focus, NULL, invalid/-1/destroyed HWNDs, three last-error
seeds, reentrant WM_SETFOCUS and WM_KILLFOCUS, and focus during both WM_NCCREATE
and WM_CREATE. The identical x86 probe checks stdcall ESP and EBP/EBX/ESI/EDI.
Callbacks compare message order, window/other-window/focus/return identities and
last-error. A previous native stock HWND first encountered by SetFocus receives
a stable guest token and can be reused. Native handle bits appear only inside
the native driver; translated guest memory contains typed guest tokens.

On this Windows installation sibling A-to-B returns A and B-to-A returns B.
Same-window and empty-NULL calls preserve last-error. Changes involving these
default procedures clear it; invalid and destroyed HWNDs return NULL and 1400.
Hidden popup activation may cause additional reentrant focus messages and alter
the HWND returned by USER32. The initial popup exploration is retained locally;
the adapter always maps the actual returned HWND rather than predicting it.

A second OS/guest thread successfully focuses its own window. Three native
unattached cross-thread attempts return NULL/error 5 without changing the
worker's focus. Translation deliberately stops at that cross-thread boundary;
attached queues and cross-thread callback/baton transfer remain unsupported.
A wrong-type token also stops explicitly, independently of native invalid HWND
behavior. The real USER32 failure is used for NULL and unrecognized/dead HWNDs
(a verified invalid host sentinel represents invalid nonzero guest tokens).

Hidden windows only; no input injection or AttachThreadInput. This is a focus
boundary fixture, not a general input manager.

API contract: [SetFocus](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setfocus).

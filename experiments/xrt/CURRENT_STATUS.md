# SetCapture and viewport CreateWindowEx validated; boundary limit reached

2026-10-24, US Eastern. SetCapture, ClipCursor(NULL), window callback 0xae (8,0)
and GetForegroundWindow pass native x86/translated fixtures and final regressions.
Three genuine continuations now pair SetCapture, SetFocus and viewport CreateWindowExW.
OpenWindow and Init remain incomplete. Highest verified world milestone remains T2:
279 paired lifecycle returns per stage across 278 selected CS_Intro actors.
No D3D CreateDevice, Clear, Present or selected-world tick. Three additional boundaries
are exhausted: the final GetForegroundWindow adapter has not run in a fourth client.
Protected inputs and earlier pending keyboard, observer, CRT and build work are preserved.

[Exact checkpoint, identities, coverage and remaining gate](SETCAPTURE_VIEWPORT.md).

---

# Viewport boundaries validated; three-boundary execution limit reached

2026-10-24, US Eastern. WM_GETICON plus SetCursor, GetWindowThreadProcessId and
MapWindowPoints pass native/translated fixtures and final regressions. Three genuine
client continuations stop successively at the latter three APIs. The final map adapter
has not run in a fourth client: the authorized additional-boundary limit is reached.
SetFocus, viewport CreateWindowEx, OpenWindow and Engine Init have no paired return.
Highest verified world milestone remains T2 (279 paired lifecycle returns/stage, 278 actors).
No selected-world tick or D3D CreateDevice/Clear/Present. Protected inputs and prior work are preserved.

[Exact checkpoint, identities, limits and next experiment](GETICON_VIEWPORT.md).

---

# SetFocus validated; bounded continuation stopped

2026-10-24, US Eastern. Real USER32 SetFocus uses typed guest HWND tokens.
Native/translated fixture, fresh serial build and affected/full acceptance pass.
The single authorized continuation stops at WM_GETICON (0x007f), ICON_SMALL2 (wParam=2), lParam=0.
SetFocus calls/paired returns: 1/0;
viewport CreateWindowEx completed: False; OpenWindow returned: False;
engine Init returns: 0; selected-world tick returns: 0;
D3D CreateDevice/Clear/Present: 0/0/0.

[Exact checkpoint and next experiment](SETFOCUS_BOUNDARY.md).

---

# ImmAssociateContext validated; bounded continuation stopped

2026-10-24, US Eastern. Real host IMM32 returns through typed HWND/HIMC tokens.
Native/translated fixture, fresh serial build and affected/full acceptance pass.
The single authorized continuation stops at user32.dll!SetFocus.
Viewport CreateWindowEx completed: False; OpenWindow returned: False;
engine Init returns: 0; selected-world tick returns: 0;
D3D device/Present: 0/0.

[Exact checkpoint and next experiment](IMMASSOCIATECONTEXT_BOUNDARY.md).

---

# AdjustWindowRect passes; viewport creation stops at ImmAssociateContext

2026-10-24, US Eastern. Native/translated RECT, last-error and ABI comparison passes
3,888 calls plus the exact genuine game RECT. Fresh serial 279-object build and one
bounded client run pass AdjustWindowRect, then stop at IMM32!ImmAssociateContext
during viewport window-creation callbacks. Highest verified world milestone remains
T2: 279 paired lifecycle calls per stage across 278 actors. Init and world ticks
have not returned; no D3D device, Clear or Present occurred.

[Validated boundary, identities, regressions and next experiment](ADJUSTWINDOWRECT_BOUNDARY.md).

---

# GetFocus passes; bounded continuation stops at AdjustWindowRect

2026-10-24, US Eastern. Fresh serial 279-object build and measured focus fixture
pass. The one bounded client run returns GetFocus, completes all 279 observed
selected-world lifecycle calls per stage, then stops at USER32!AdjustWindowRect
in WinDrv.dll+0x3550. Init and world ticks remain incomplete; no D3D device.

[Verified GetFocus checkpoint, identities, regressions and next boundary](GETFOCUS_BOUNDARY.md).

---

# DirectInput mouse creation works; execution held on compiler instability

2026-10-23, US Eastern. Starting HEAD was clean at
`75b215317b55dd463183ad3a8f06872ca74962b1`. No work was reset or discarded.

The genuine translated client now passes `IDirectInput8W::CreateDevice` for `GUID_SysMouse`,
the seven-object mouse data format and both required property calls. The next executed fatal
is loading **U2AI.dll**, which exists in the verified snapshot but was absent from that client.
CS_Intro LoadMap again returns `0x12f52800`. **No selected-world tick completed.**

Further compiler/game execution is held after unexplained MSVC C1001 failures moved between
Engine_032, unchanged ParticleSystems_001 and unchanged Unreal2_000; the last build also reported
D8040 child-process communication failure. An isolated `/O1` ParticleSystems build passed.
No protected-input hash difference was detected. These observations do not establish the cause,
hardware health, or that a compiler flag fixes the instability.

[Detailed checkpoint and continuation boundary](DIRECTINPUT_DEVICE.md).
[Structured evidence](results/compare/input_device_resume.json).

| Requested translated milestone | Verified state |
|---|---|
| T1: selected CS_Intro LoadMap returns non-null | Yes, fresh run, world `0x12f52800` |
| T2: selected-world actor lifecycle completed | Unverified; direct-call observer remains unaccepted |
| T3: UGameEngine::Init returns | No |
| T4: selected ULevel::Tick enters | No |
| T5: selected tick returns to its caller | No |
| T6: bounded selected-world tick sequence | No |
| Translated D3D device / Present | None / none |

The interrupted DirectMusic regression sweep is now freshly complete against its preserved binary.
After the DirectInput change, the focused seven-positive/six-negative differential passes; the complete
post-change integration sweep was **not** run after the compiler stop. Preserve that distinction.

Pending, uncommitted experimental source includes U2AI linkage, Engine direct-call observers,
their build/identity changes and milestone summarization. A compiled/hash-checked world-observer
client exists, but it was **never executed or regression accepted**. Do not promote it to a runnable
accepted checkpoint or infer its world milestones from compilation.

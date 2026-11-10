# Measured target Clear and NULL Present

This project-owned PE fixture uses the production typed device registry. It never
loads or launches the graphical Unreal II client. Every process creates one real
device with the captured 1540 x 945 X8R8G8B8 / D24X8 windowed tuple, using pinned
DXVK 3.1.1. Native x86/x64 assembly checks nonvolatile registers, live x87 values,
control/status, stack balance, MXCSR, and x64 XMM6 through XMM15.

`native.c` independently measures real calls and obtains the lockable implicit
backbuffer through test-only native surface calls. It hashes all RGB bytes and
records descriptors, pixel samples, reference counts and queried device state.
`PrintWindow(PW_RENDERFULLCONTENT)` captures actual fixture window output. The
initial BitBlt capture failed to identify the window frame; those captures are
retained and explicitly excluded as presentation proof.

`translated.py` builds both an unchanged production runtime fixture and a separate
observed executable. Only the latter inserts native readback/window observation
and forced nested WM_GETICON callbacks around the actual Clear/Present calls.
The hooks preserve last-error and host MXCSR across observation. Actual native
call intervals have separate enter/leave records; observation callbacks are not
counted as DXVK callbacks. No hook fabricates an HRESULT or substitutes rendering.

Readback/capture changes Present cadence: in this fixture it preserves the seeded
last-error after the first observed Present, whereas the tight direct native and
production-translated loop sets it to zero each time. Each workload compares to
its matching native oracle. The production bridge always returns actual error.

The native x86 first successful Present sets sticky x87 PE. Live values, CW and
TOP survive. The production bridge models this narrow measured effect because
the native x64 implementation performs its calculation using SSE. The repeated
assembly supplement clears exceptions before every method and compares all
x86 status words exactly. General x87 limitations remain as documented elsewhere.

Supported production surface: Clear flags=TARGET, Z bits=0, stencil=0, count at
most one, copied readable rectangle with bounded nonempty coordinates when
count=1; arbitrary DWORD color. Count=0/non-NULL is forwarded as a non-NULL local
copy and retains DXVK's measured no-op behavior. Present takes four NULLs.
All other 90 device methods remain named traps. Reentrant rendering, release
during an active native render, and destruction of pinned HWNDs stop explicitly.
Rendering additionally requires the captured shared, non-NULL focus/device HWND;
the older CreateDevice-only NULL/separate-window variants stop before rendering.
Fatal callbacks retain backend modules until process teardown.

Use a fresh directory for each build revision; preserve failed compiler logs.
`run.py native-build`, `run.py native-run`, `translated.py build`,
`translated.py run`, and `audit.py` accept `--out` (the audit takes a positional
path). The retained phase has native CW=077f evidence in fixture-02, window
capture correction in fixture-03, native CW=027f plus full differential in
fixture-04, repeated assembly supplement in fixture-05, and the final window-tuple
guard plus repeated full differential in fixture-06. See the phase report
for exact identities and commands. No backend download, game session, or remote
publication is part of these scripts.

/* viewport_maximize - focused test of the developer runtime's windowed maximize (out/dev-init/runtime/viewport_window.inc,
 * called from hle_gui_classes.inc class_dispatch before a message reaches the guest window procedure).
 * Runs 20261101-191847-7aea43cf (Maximize button) and 20261101-191912-be757706 (Alt+Enter) died with fatal 76 because
 * WinDrv's viewport procedure turns both into UWindowsViewport::ToggleFullscreen (exclusive fullscreen CreateDevice).
 *
 * An owned "guest" procedure mimics WinDrv: SC_MAXIMIZE, Alt+Enter and a SIZE_MAXIMIZED WM_SIZE count as ToggleFullscreen /
 * fullscreen requests; other system commands and keys go to DefWindowProc; WM_SIZE records the client size it is given.
 * The window class name ends in ViewportWindow like WinDrv's. The window is placed on the LAST monitor (the secondary one
 * when there are two), so the maximized size is checked against that monitor's own work area. Visible about a second.
 *
 *   maximize   SC_MAXIMIZE never reaches the guest; the window is zoomed; the guest's WM_SIZE says SIZE_RESTORED (WinDrv
 *              turns SIZE_MAXIMIZED into SetRes(Fullscreen=1), run 20261101-205740) with the actual client, within that
 *              monitor's work area; caption double-click code 0xF032 too
 *   restore    SC_RESTORE reaches the guest (DefWindowProc) and returns the exact previous client size
 *   alt        Alt+Enter reaches the game's own ToggleFullscreen (fullscreen is borderless); plain Enter reaches the guest
 *   borderless while the borderless device window is frameless its WM_SIZE is held back; once the frame is back it flows
 *   scope      a child window of the same class and a top-level window of another class are not intercepted
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/viewport_maximize/run.cmd */
#include <windows.h>
#include <imm.h>
#include <stdio.h>
#include <stdlib.h>
#include "xrt_internal.h"
#include "monitor_windows.inc"

uint8_t* xrt_g;
unsigned xm_quiet;
CPU* xm_current_cpu(void) { return NULL; }
#undef xm_probe
void xm_probe(CPU* c, const XmRequest* q) { (void)c; (void)q; }
#define xm_probe xm_probe_gated
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
void xrt_log(const char* fmt, ...) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); }
static HWND borderless;   /* stands in for d3d8_borderless.inc's device window */
int xrt_d3d8_borderless_window(void* h) { return h && h == (void*)borderless; }
#include "viewport_window.inc"

static int failures;
#define CHECK(cond, ...) do { int ok_ = !!(cond); printf(ok_ ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!ok_) failures++; } while (0)

static unsigned toggles, guest_syscommands, guest_enters, sizes;
static int size_type, size_x, size_y;
static LRESULT CALLBACK guest_proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_SYSCOMMAND:
        if ((wp & 0xfff0) == SC_MAXIMIZE) { toggles++; return 0; }
        guest_syscommands++; break;
    case WM_KEYDOWN: case WM_SYSKEYDOWN:
        if (wp == VK_RETURN) { if (GetKeyState(VK_MENU) < 0) { toggles++; return 0; } guest_enters++; return 0; }
        break;
    case WM_SIZE: sizes++; size_type = (int)wp; if (wp == SIZE_MAXIMIZED) toggles++; /* WinDrv: SetRes(Fullscreen=1) */ size_x = LOWORD(lp); size_y = HIWORD(lp); return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}
/* class_dispatch: the intercept first, then the guest procedure */
static LRESULT CALLBACK host_thunk(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    LRESULT r;
    if ((m == WM_SYSCOMMAND || m == WM_KEYDOWN || m == WM_SYSKEYDOWN) && viewport_windowed_maximize(h, m, wp, lp, 1, &r))
        return r;
    if (m == WM_SIZE && viewport_fullscreen_size(h, m)) return 0;
    if (m == WM_SIZE) wp = viewport_size_type(h, m, wp);
    return guest_proc(h, m, wp, lp);
}
static MONITORINFO last_monitor;
static BOOL CALLBACK monitors(HMONITOR m, HDC dc, LPRECT r, LPARAM p) {
    (void)dc; (void)r; (void)p; last_monitor.cbSize = sizeof last_monitor; GetMonitorInfoW(m, &last_monitor); return TRUE;
}
static void pump(void) { MSG m; while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&m); DispatchMessageW(&m); } }
static void alt(int down) {
    BYTE k[256]; GetKeyboardState(k); k[VK_MENU] = down ? 0x80 : 0; SetKeyboardState(k);
}
static RECT client(HWND h) { RECT r; GetClientRect(h, &r); return r; }

int main(void) {
    WNDCLASSW wc = {0}, other = {0}; HWND h, child, plain; RECT before, after, w; LRESULT r; unsigned t0;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_UNAWARE); /* like unreal2-dev.exe (no DPI manifest) */
    EnumDisplayMonitors(NULL, NULL, monitors, 0);
    wc.lpfnWndProc = host_thunk; wc.hInstance = GetModuleHandleW(NULL); wc.lpszClassName = L"Unreal2UnrealWWindowsViewportWindow";
    wc.hCursor = LoadCursorW(NULL, IDC_ARROW); RegisterClassW(&wc);
    other.lpfnWndProc = host_thunk; other.hInstance = wc.hInstance; other.lpszClassName = L"Unreal2WWindowsSplash"; RegisterClassW(&other);
    h = CreateWindowExW(0, wc.lpszClassName, L"viewport_maximize test", WS_OVERLAPPEDWINDOW,
                        last_monitor.rcWork.left + 80, last_monitor.rcWork.top + 80, 800, 600, NULL, NULL, wc.hInstance, NULL);
    ShowWindow(h, SW_SHOWNOACTIVATE); pump();
    before = client(h);
    printf("     monitor work area %ld,%ld-%ld,%ld; window client %ldx%ld\n", last_monitor.rcWork.left, last_monitor.rcWork.top,
           last_monitor.rcWork.right, last_monitor.rcWork.bottom, before.right, before.bottom);

    /* maximize button */
    sizes = 0; SendMessageW(h, WM_SYSCOMMAND, SC_MAXIMIZE, 0); pump();
    after = client(h); GetWindowRect(h, &w);
    CHECK(toggles == 0, "maximize: SC_MAXIMIZE did not reach the guest ToggleFullscreen path (%u)", toggles);
    CHECK(IsZoomed(h), "maximize: window is maximized (windowed)");
    CHECK(sizes > 0 && size_type == SIZE_RESTORED && size_x == after.right && size_y == after.bottom,
          "maximize: guest WM_SIZE is SIZE_RESTORED (windowed SetRes) %dx%d = actual client %ldx%ld", size_x, size_y, after.right, after.bottom);
    {
        POINT tl = {0, 0}, br = {after.right, after.bottom}; ClientToScreen(h, &tl); ClientToScreen(h, &br);
        CHECK(tl.x >= last_monitor.rcWork.left && tl.y >= last_monitor.rcWork.top && br.x <= last_monitor.rcWork.right &&
              br.y <= last_monitor.rcWork.bottom && after.right > before.right && after.bottom > before.bottom,
              "maximize: client %ld,%ld-%ld,%ld inside this monitor's work area and larger than before", tl.x, tl.y, br.x, br.y);
    }
    /* restore button */
    sizes = 0; t0 = guest_syscommands; SendMessageW(h, WM_SYSCOMMAND, SC_RESTORE, 0); pump();
    after = client(h);
    CHECK(guest_syscommands == t0 + 1, "restore: SC_RESTORE reached the guest procedure");
    CHECK(!IsZoomed(h) && after.right == before.right && after.bottom == before.bottom && size_type == SIZE_RESTORED,
          "restore: previous client %ldx%ld back (WM_SIZE type %d %dx%d)", after.right, after.bottom, size_type, size_x, size_y);
    /* caption double-click sends SC_MAXIMIZE | HTCAPTION (0xF032) */
    SendMessageW(h, WM_SYSCOMMAND, SC_MAXIMIZE | 2, 0); pump();
    CHECK(IsZoomed(h) && toggles == 0, "maximize: caption double-click code 0xF032 handled the same way");
    SendMessageW(h, WM_SYSCOMMAND, SC_RESTORE, 0); pump();

    /* Alt+Enter is the game's own fullscreen toggle again (borderless fullscreen) */
    alt(1);
    SendMessageW(h, WM_SYSKEYDOWN, VK_RETURN, 0x201C0001); pump();
    CHECK(!IsZoomed(h) && toggles == 1, "alt: Alt+Enter reaches the game's ToggleFullscreen (%u)", toggles);
    alt(0);
    t0 = guest_enters; r = SendMessageW(h, WM_KEYDOWN, VK_RETURN, 0x001C0001);
    CHECK(guest_enters == t0 + 1 && !IsZoomed(h), "alt: plain Enter reaches the guest (%Id)", r);

    /* borderless fullscreen: WM_SIZE held back while the device window is frameless, passed once the frame is back */
    borderless = h;
    SetWindowLongW(h, GWL_STYLE, GetWindowLongW(h, GWL_STYLE) & ~(WS_CAPTION | WS_THICKFRAME));
    sizes = 0; SetWindowPos(h, NULL, last_monitor.rcMonitor.left, last_monitor.rcMonitor.top, 640, 480, SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE); pump();
    CHECK(sizes == 0, "borderless: WM_SIZE held back while frameless (%u)", sizes);
    SetWindowLongW(h, GWL_STYLE, GetWindowLongW(h, GWL_STYLE) | WS_CAPTION | WS_THICKFRAME);
    SetWindowPos(h, NULL, last_monitor.rcWork.left + 80, last_monitor.rcWork.top + 80, 800, 600, SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE); pump();
    CHECK(sizes > 0, "borderless: WM_SIZE flows again once the frame is restored (%u)", sizes);
    borderless = NULL;

    /* scope */
    child = CreateWindowExW(0, wc.lpszClassName, L"", WS_CHILD | WS_VISIBLE, 0, 0, 50, 50, h, NULL, wc.hInstance, NULL);
    SendMessageW(child, WM_SYSCOMMAND, SC_MAXIMIZE, 0);
    CHECK(toggles == 2, "scope: child viewport window not intercepted (%u)", toggles);
    plain = CreateWindowExW(0, other.lpszClassName, L"", WS_OVERLAPPEDWINDOW, last_monitor.rcWork.left, last_monitor.rcWork.top, 100, 100,
                            NULL, NULL, wc.hInstance, NULL);
    SendMessageW(plain, WM_SYSCOMMAND, SC_MAXIMIZE, 0);
    CHECK(toggles == 3 && !IsZoomed(plain), "scope: other window class not intercepted (%u)", toggles);
    DestroyWindow(plain); DestroyWindow(h); pump();
    printf("%s (%d failure%s)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

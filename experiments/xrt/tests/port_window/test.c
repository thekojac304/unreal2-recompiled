/* port_window - focused test of out/dev-init/runtime/port_settings.c: the Video > Resolution request in a window
 * ("PORTSET WindowSize W H") and the UI scale cap. Includes port_settings.c with owned stubs.
 *
 *   window   a maximized top-level ViewportWindow on the last monitor receives "PORTSET WindowSize 1280 720": it leaves the
 *            maximized state in one step (one WM_SIZE, SIZE_RESTORED) with a 1280x720 client, centred in that monitor's
 *            work area; a size larger than the work area is limited to it
 *   scale    the scaled UI frame never gets smaller than 640x480: 720x480 at 150% -> 1.0, 2560x1440 at 200% -> 2.0,
 *            1280x720 at 200% -> 1.5; Auto keeps its height rule (1080 lines -> 1.0, 2160 -> 2.0)
 * The test window is visible for about a second. Exit 0 when every check passes. Build/run: run.cmd here. */
#include <windows.h>
#include <stdio.h>
#include "xrt_internal.h"

uint8_t* xrt_g;
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
void xrt_log(const char* fmt, ...) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); }
XrtModule* xrt_module_by_name(const char* name) { (void)name; return NULL; }
uint32_t xrt_call_guest(CPU* c, uint32_t va, int n, const uint32_t* a, int s) { (void)c; (void)va; (void)n; (void)a; (void)s; return 0; }
CPU* xrt_gui_callback_enter(CPU* c) { return c; }
void xrt_gui_callback_leave(CPU* p) { (void)p; }
#include "port_settings.c"

static int failures;
#define CHECK(cond, ...) do { int ok_ = !!(cond); printf(ok_ ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!ok_) failures++; } while (0)
static unsigned sizes; static WPARAM last_type;
static LRESULT CALLBACK proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_SIZE) { sizes++; last_type = wp; }
    return DefWindowProcW(h, m, wp, lp);
}
static MONITORINFO last_monitor;
static BOOL CALLBACK monitors(HMONITOR m, HDC dc, LPRECT r, LPARAM p) {
    (void)dc; (void)r; (void)p; last_monitor.cbSize = sizeof last_monitor; GetMonitorInfoW(m, &last_monitor); return TRUE;
}
static void command(const wchar_t* s) {
    uint16_t buf[96]; int i;
    for (i = 0; s[i] && i < 95; i++) buf[i] = (uint16_t)s[i];
    buf[i] = 0;
    port_command(NULL, buf);
}
static void pump(void) { MSG m; while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) DispatchMessageW(&m); }

int main(void) {
    WNDCLASSW wc = {0}; HWND h; RECT r, w; int aw, ah;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_UNAWARE);
    EnumDisplayMonitors(NULL, NULL, monitors, 0);
    aw = last_monitor.rcWork.right - last_monitor.rcWork.left; ah = last_monitor.rcWork.bottom - last_monitor.rcWork.top;
    wc.lpfnWndProc = proc; wc.hInstance = GetModuleHandleW(NULL); wc.lpszClassName = L"Unreal2UnrealWWindowsViewportWindow";
    RegisterClassW(&wc);
    h = CreateWindowExW(0, wc.lpszClassName, L"port_window test", WS_OVERLAPPEDWINDOW, last_monitor.rcWork.left + 50,
                        last_monitor.rcWork.top + 50, 800, 600, NULL, NULL, wc.hInstance, NULL);
    ShowWindow(h, SW_SHOWNOACTIVATE); ShowWindow(h, SW_MAXIMIZE); pump();
    CHECK(IsZoomed(h), "window: test window maximized");
    sizes = 0; command(L"PORTSET WindowSize 1280 720"); pump();
    GetClientRect(h, &r); GetWindowRect(h, &w);
    CHECK(!IsZoomed(h) && r.right == 1280 && r.bottom == 720, "window: no longer maximized, client %ldx%ld", r.right, r.bottom);
    CHECK(sizes == 1 && last_type == SIZE_RESTORED, "window: one WM_SIZE (%u), SIZE_RESTORED", sizes);
    CHECK(abs((w.left + w.right) / 2 - (last_monitor.rcWork.left + last_monitor.rcWork.right) / 2) <= 1 &&
          abs((w.top + w.bottom) / 2 - (last_monitor.rcWork.top + last_monitor.rcWork.bottom) / 2) <= 1,
          "window: centred in the monitor's work area");
    command(L"PORTSET WindowSize 5000 4000"); pump(); GetWindowRect(h, &w);
    CHECK(w.right - w.left <= aw && w.bottom - w.top <= ah, "window: an oversized request is limited to the work area (%ldx%ld)",
          w.right - w.left, w.bottom - w.top);
    DestroyWindow(h); pump();

    loaded = 1; ui_choice = 150;
    CHECK(ui_scale(720, 480) == 1.0f, "scale: 720x480 at 150%% -> %.3g (menus need 640x480)", ui_scale(720, 480));
    ui_choice = 200;
    CHECK(ui_scale(2560, 1440) == 2.0f && ui_scale(1280, 720) == 1.5f, "scale: 200%% -> %.3g at 2560x1440, %.3g at 1280x720",
          ui_scale(2560, 1440), ui_scale(1280, 720));
    ui_choice = 0;
    CHECK(ui_scale(1920, 1080) == 1.0f && ui_scale(3840, 2160) == 2.0f, "scale: Auto %.3g at 1080 lines, %.3g at 2160",
          ui_scale(1920, 1080), ui_scale(3840, 2160));
    printf("%s (%d failure%s)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

/* bg_input - focused test of the developer background mode (tools/xrt/dev/dev_support.c XRT_DEV_BACKGROUND, dev.py
 * --background) and of the host behaviour it relies on. Includes dev_support.c itself with the runtime it calls
 * replaced by owned stubs (as experiments/xrt/tests/fps_cap), drives the input script from a message pump that applies
 * the runtime's isolation filter exactly as message_pump.inc does, and runs while ANOTHER process owns the foreground
 * (the test never takes focus; it refuses to judge if its own process is the foreground).
 *
 *   window    an owned top-level window created hidden, shown SW_SHOWNOACTIVATE at HWND_BOTTOM (as the background mode's
 *             create_window/ShowWindow do): the real foreground window never changes. Probe (opt-in, it TAKES the
 *             focus): BG_PROBE=a / f / ca calls SetActiveWindow / SetFocus [after SetForegroundWindow(current)] on it.
 *             Measured 2026-11-01 with the owner idle in a browser: SetActiveWindow took the foreground even after
 *             SetForegroundWindow(current) succeeded - the reason the runtime keeps activation virtual in this mode
 *   script    background mode: scripted key/move/click steps run on time without the foreground; WM_KEYDOWN/UP,
 *             WM_LBUTTONDOWN/UP and WM_MOUSEMOVE reach the window procedure; GetKeyState's scripted hold is reported;
 *             DirectInput records sum to the scripted motion and carry button 0 down/up
 *   leak      unscripted (physical-like) WM_KEYDOWN/WM_MOUSEMOVE/WM_LBUTTONDOWN posted to the window never pass the filter
 *   control   without XRT_DEV_BACKGROUND (child process) the schedule pauses while not foreground: nothing delivered
 *   refused   XRT_DEV_BACKGROUND without isolation (child process) is refused (mode off)
 *   dinput    host DirectInput mouse on this background window: FOREGROUND|EXCLUSIVE cannot be acquired, the background
 *             mode's NONEXCLUSIVE|BACKGROUND can (the runtime's host cooperative-level mapping)
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/bg_input/run.cmd */
#include "../../../../tools/xrt/dev/dev_support.c"
#define DIRECTINPUT_VERSION 0x0800
#include <dinput.h>

/* ---- owned stubs for the runtime symbols dev_support.c uses */
volatile long xrt_exiting;
__declspec(thread) XrtThread* xrt_cur;
unsigned xrt_scene_level_renders, xrt_scene_camera_renders, xrt_scene_engine_ticks, xrt_scene_level_ticks;
void xrt_baton_release(void) {}
void xrt_baton_acquire(void) {}
void xrt_baton_stats_log(FILE* also) { (void)also; }
int xrt_thread_count(void) { return 0; }
XrtThread* xrt_thread_get(int i) { (void)i; return NULL; }
static int verbose;
void xrt_log(const char* fmt, ...) { if (verbose) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); } }
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
void xm_checkpoint(CPU* c, const char* name) { (void)c; (void)name; }
void xrt_report_write(uint32_t exit_code, const char* outcome) { (void)exit_code; (void)outcome; }

static int failures;
#define CHECK(cond, ...) do { printf((cond) ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!(cond)) failures++; } while (0)

static struct { unsigned keydown[256], keyup[256], lbdown, lbup, moves, chars, other_input; } got;
static LRESULT CALLBACK wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_KEYDOWN: if (wp < 256) got.keydown[wp]++; return 0;
    case WM_KEYUP: if (wp < 256) got.keyup[wp]++; return 0;
    case WM_CHAR: got.chars++; return 0;
    case WM_LBUTTONDOWN: got.lbdown++; return 0;
    case WM_LBUTTONUP: got.lbup++; return 0;
    case WM_MOUSEMOVE: got.moves++; return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}
static int input_message(UINT m) {
    return (m >= WM_KEYFIRST && m <= WM_KEYLAST) || (m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) ||
           (m >= WM_NCMOUSEMOVE && m <= WM_NCXBUTTONDBLCLK) || m == WM_INPUT;
}
static unsigned filtered;
static int di_x, di_y, di_button_down, di_button_up, held_w_seen;
/* The runtime's pump: xrt_dev_input_tick before each peek, then the isolation filter (message_pump.inc). */
static void pump(unsigned ms) {
    ULONGLONG end = GetTickCount64() + ms; MSG m; unsigned ofs, data;
    while (GetTickCount64() < end) {
        xrt_dev_input_tick();
        while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) {
            if (input_message(m.message) && xrt_dev_input_blocked(NULL) &&
                !xrt_dev_input_allowed(m.hwnd, m.message, (unsigned long long)m.wParam, (long long)m.lParam)) { filtered++; continue; }
            TranslateMessage(&m); DispatchMessageW(&m);
        }
        while (xrt_dev_input_mouse(&ofs, &data)) {
            if (ofs == 0) di_x += (int)data; else if (ofs == 4) di_y += (int)data;
            else if (ofs == 12) { if (data & 0x80) di_button_down++; else di_button_up++; }
        }
        if (xrt_dev_key_held('W')) held_w_seen++;
        Sleep(1);
    }
}
static DWORD foreground_pid(HWND* out) {
    DWORD pid = 0; HWND fg = GetForegroundWindow();
    if (fg) GetWindowThreadProcessId(fg, &pid);
    if (out) *out = fg;
    return pid;
}
static HWND make_window(void) {
    WNDCLASSW wc = {0}; HWND h;
    wc.lpfnWndProc = wndproc; wc.hInstance = GetModuleHandleW(NULL); wc.lpszClassName = L"XrtBgInputTest";
    RegisterClassW(&wc);
    /* as hle_gui_classes.inc create_window does for WS_VISIBLE top-level windows in background mode */
    h = CreateWindowExW(0, wc.lpszClassName, L"bg_input test", WS_OVERLAPPEDWINDOW, 40, 40, 320, 200, NULL, NULL, wc.hInstance, NULL);
    ShowWindow(h, SW_SHOWNOACTIVATE);
    SetWindowPos(h, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
    return h;
}
/* WM_INITDIALOG returns FALSE as the runtime's dev_background_dialog_bridge reports it (BG_PROBE=d: TRUE, the guest's
 * own answer - measured 2026-11-01: the default focus assignment then took the foreground from a hidden dialog). */
static INT_PTR CALLBACK dlgproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    (void)h; (void)wp; (void)lp;
    return m == WM_INITDIALOG && getenv("BG_PROBE") && strchr(getenv("BG_PROBE"), 'd');
}
/* As create_dialog does in background mode: the template with WS_VISIBLE cleared (here with a tab-stop button, the
 * case where the dialog manager assigns default focus), then SW_SHOWNOACTIVATE at HWND_BOTTOM. */
static HWND make_dialog(void) {
    static WORD t[64]; WORD *p = t; DLGTEMPLATE *d = (DLGTEMPLATE *)t; DLGITEMTEMPLATE *item; HWND h;
    d->style = (WS_POPUP | WS_CAPTION | DS_SETFONT * 0) & ~WS_VISIBLE; d->cdit = 1; d->x = 10; d->y = 10; d->cx = 120; d->cy = 60;
    p = (WORD *)(d + 1); *p++ = 0; *p++ = 0; *p++ = 0;   /* menu, class, title */
    p = (WORD *)(((ULONG_PTR)p + 3) & ~(ULONG_PTR)3);
    item = (DLGITEMTEMPLATE *)p; item->style = WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON; item->x = 10; item->y = 10; item->cx = 50; item->cy = 14; item->id = 1;
    p = (WORD *)(item + 1); *p++ = 0xffff; *p++ = 0x0080; *p++ = 0; *p++ = 0;   /* button class, no text, no data */
    h = CreateDialogIndirectParamW(GetModuleHandleW(NULL), d, NULL, dlgproc, 0);
    ShowWindow(h, SW_SHOWNOACTIVATE);
    SetWindowPos(h, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
    return h;
}
static void setup_env(const char* dir, int background, int isolation) {
    _putenv_s("XRT_DEV_OUTPUT", dir); _putenv_s("XRT_DEV_SCENE", "100000");
    _putenv_s("XRT_DEV_NO_INPUT", isolation ? "1" : "");
    _putenv_s("XRT_DEV_BACKGROUND", background ? "1" : "");
    _putenv_s("XRT_DEV_INPUT", "100:key:87:300;150:move:40:-30:200;600:click:80;700:key:32:50");
}
static int child(const char* dir, const char* which) {
    HWND h;
    setup_env(dir, strcmp(which, "control") != 0, strcmp(which, "refused") != 0);
    if (!strcmp(which, "refused")) return xrt_dev_background() ? 1 : 0;
    h = make_window();
    xrt_dev_input_window(h);
    post_init = 1; init_ms = GetTickCount64();
    pump(1200);
    printf("     control child: steps run %u, delivered %u, paused %llu ms\n", in_next, in_delivered, in_paused);
    DestroyWindow(h);
    return (in_next == 0 && in_delivered == 0 && got.keydown['W'] == 0 && in_paused >= 1000) ? 0 : 1;
}
static DWORD run_child(const char* which) {
    char cmd[MAX_PATH + 32], self[MAX_PATH]; STARTUPINFOA si = {sizeof si}; PROCESS_INFORMATION pi; DWORD code = 99;
    GetModuleFileNameA(NULL, self, sizeof self);
    snprintf(cmd, sizeof cmd, "\"%s\" %s", self, which);
    if (!CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) return 98;
    WaitForSingleObject(pi.hProcess, 20000); GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
    return code;
}
static void dinput_check(HWND h) {
    IDirectInput8W* di = NULL; IDirectInputDevice8W* mouse = NULL; HRESULT a, b, hr;
    hr = DirectInput8Create(GetModuleHandleW(NULL), DIRECTINPUT_VERSION, &IID_IDirectInput8W, (void**)&di, NULL);
    if (FAILED(hr)) { CHECK(0, "dinput: DirectInput8Create %08lx", (unsigned long)hr); return; }
    hr = IDirectInput8_CreateDevice(di, &GUID_SysMouse, &mouse, NULL);
    if (FAILED(hr)) { CHECK(0, "dinput: CreateDevice(SysMouse) %08lx", (unsigned long)hr); IDirectInput8_Release(di); return; }
    IDirectInputDevice8_SetDataFormat(mouse, &c_dfDIMouse2);
    IDirectInputDevice8_SetCooperativeLevel(mouse, h, DISCL_FOREGROUND | DISCL_EXCLUSIVE);
    a = IDirectInputDevice8_Acquire(mouse);
    IDirectInputDevice8_Unacquire(mouse);
    hr = IDirectInputDevice8_SetCooperativeLevel(mouse, h, DISCL_BACKGROUND | DISCL_NONEXCLUSIVE);
    b = IDirectInputDevice8_Acquire(mouse);
    printf("     dinput: FOREGROUND|EXCLUSIVE Acquire %08lx, NONEXCLUSIVE|BACKGROUND (set %08lx) Acquire %08lx\n",
           (unsigned long)a, (unsigned long)hr, (unsigned long)b);
    CHECK(FAILED(a), "dinput: a FOREGROUND|EXCLUSIVE mouse cannot be acquired by the background window (%08lx)", (unsigned long)a);
    CHECK(SUCCEEDED(hr) && SUCCEEDED(b), "dinput: NONEXCLUSIVE|BACKGROUND (the background mode's host level) acquires (%08lx)", (unsigned long)b);
    IDirectInputDevice8_Unacquire(mouse);
    IDirectInputDevice8_Release(mouse); IDirectInput8_Release(di);
}

int main(int argc, char** argv) {
    char dir[MAX_PATH]; HWND fg0, fg1, h; DWORD pid0;
    GetTempPathA(sizeof dir, dir);
    strcat(dir, "xrt-bg-input-test");
    CreateDirectoryA(dir, NULL);
    if (argc > 1) return child(dir, argv[1]);
    pid0 = foreground_pid(&fg0);
    printf("     foreground before: %p (pid %lu; this test pid %lu)\n", fg0, pid0, GetCurrentProcessId());
    if (!fg0 || pid0 == GetCurrentProcessId()) { printf("SKIP: another application must own the foreground\n"); return 2; }
    setup_env(dir, 1, 1);
    verbose = 1;
    CHECK(xrt_dev_background(), "XRT_DEV_BACKGROUND=1 with isolation: background mode on");
    CHECK(run_child("refused") == 0, "XRT_DEV_BACKGROUND=1 without isolation: refused (mode off)");
    h = make_window();
    pump(50);
    printf("     after create/show/bottom: foreground %p\n", GetForegroundWindow());
    if (getenv("BG_PROBE")) {
        if (strchr(getenv("BG_PROBE"), 'c')) { BOOL ok = SetForegroundWindow(fg0); printf("     SetForegroundWindow(current foreground) %d\n", ok); }
        if (strchr(getenv("BG_PROBE"), 'a')) { SetActiveWindow(h); pump(50); printf("     after SetActiveWindow: foreground %p active %p\n", GetForegroundWindow(), GetActiveWindow()); }
        if (strchr(getenv("BG_PROBE"), 'f')) { SetFocus(h); pump(50); printf("     after SetFocus: foreground %p focus %p\n", GetForegroundWindow(), GetFocus()); }
    }
    CHECK(GetForegroundWindow() == fg0, "window: hidden create + SW_SHOWNOACTIVATE + HWND_BOTTOM leave the foreground %p (now %p)",
          fg0, GetForegroundWindow());
    {
        HWND dlg = make_dialog(); pump(50);
        CHECK(dlg && IsWindowVisible(dlg) && GetForegroundWindow() == fg0,
              "dialog: hidden-template dialog with a tab-stop control, shown SW_SHOWNOACTIVATE, leaves the foreground (now %p)", GetForegroundWindow());
        DestroyWindow(dlg);
    }
    /* The guest sends WM_NCACTIVATE TRUE/FALSE around a map load (launch 20261101-123025: a 1.2 s foreground blip at
     * the same time). Passed through unchanged: does it move the foreground? */
    SendMessageW(h, WM_NCACTIVATE, TRUE, 0); pump(300);
    CHECK(GetForegroundWindow() == fg0, "ncactivate: SendMessage(WM_NCACTIVATE, TRUE) leaves the foreground (now %p)", GetForegroundWindow());
    SendMessageW(h, WM_NCACTIVATE, FALSE, 0); pump(50);
    xrt_dev_input_window(h);
    post_init = 1; init_ms = GetTickCount64();
    PostMessageW(h, WM_KEYDOWN, 'X', 1 | (LPARAM)MapVirtualKeyW('X', MAPVK_VK_TO_VSC) << 16);   /* physical-like, unscripted */
    PostMessageW(h, WM_MOUSEMOVE, 0, MAKELPARAM(10, 10));
    PostMessageW(h, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(10, 10));
    pump(1100);
    verbose = 0;
    printf("     background: steps %u/%u, delivered %u, filtered %u, paused %llu ms; keys W %u/%u space %u/%u X %u; "
           "button %u/%u moves %u chars %u; DirectInput x %d y %d button %d/%d; W held in %d pump passes\n",
           in_next, in_count, in_delivered, filtered, in_paused, got.keydown['W'], got.keyup['W'], got.keydown[' '], got.keyup[' '],
           got.keydown['X'], got.lbdown, got.lbup, got.moves, got.chars, di_x, di_y, di_button_down, di_button_up, held_w_seen);
    CHECK(in_next == in_count && in_count == 4 && in_paused == 0, "script: all 4 steps ran on time without the foreground (paused %llu ms)", in_paused);
    CHECK(got.keydown['W'] == 1 && got.keyup['W'] == 1 && got.keydown[' '] == 1 && got.keyup[' '] == 1,
          "script: scripted WM_KEYDOWN/WM_KEYUP (W, Space) reached the window procedure");
    CHECK(held_w_seen >= 10, "script: GetKeyState hold reported for the scripted W (%d passes)", held_w_seen);
    CHECK(got.lbdown == 1 && got.lbup == 1 && got.moves >= 1, "script: WM_LBUTTONDOWN/UP and WM_MOUSEMOVE delivered (%u moves)", got.moves);
    CHECK(di_x == 40 && di_y == -30 && di_button_down == 1 && di_button_up == 1,
          "script: DirectInput records sum to the scripted motion 40,-30 with button 0 down/up");
    CHECK(got.keydown['X'] == 0 && filtered >= 3, "leak: unscripted WM_KEYDOWN/WM_MOUSEMOVE/WM_LBUTTONDOWN dropped by the filter (%u filtered)", filtered);
    fg1 = GetForegroundWindow();
    CHECK(fg1 == fg0, "focus: the foreground window is unchanged after the scripted input (%p)", fg1);
    CHECK(run_child("control") == 0, "control: without XRT_DEV_BACKGROUND the schedule pauses while not foreground (nothing delivered)");
    dinput_check(h);
    CHECK(GetForegroundWindow() == fg0, "focus: still unchanged at the end");
    DestroyWindow(h);
    printf(failures ? "FAILED %d\n" : "PASS\n", failures);
    return failures != 0;
}

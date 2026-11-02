/* quit_message - focused test of the developer runtime's PostQuitMessage adapter (out/dev-init/runtime/message_pump.inc),
 * the import Core's appRequestExit(0) calls when the player chooses Exit (run 20261101-192029-eed53121, fatal 75).
 * Compiles the actual message_pump.inc (and window_transitions.inc for its guest-range check) against owned stubs and a
 * small committed guest memory block, then drives it the way UnEngineWin's MainLoop does (PeekMessageW(NULL,0,0,
 * PM_REMOVE); WM_QUIT -> GIsRequestingExit; TranslateMessage; DispatchMessageW).
 *
 *   adapter   stdcall: one argument popped, EAX 0, return address taken, guest last error kept
 *   quit      the next guest PeekMessage returns WM_QUIT with hwnd token 0 and wParam = exit code; Translate/Dispatch of
 *             that guest MSG are harmless; WM_QUIT is reported once
 *   order     a message posted to an owned window BEFORE the quit is still dispatched to its window procedure first
 *             (native queue semantics: WM_QUIT only when no posted messages remain) - shutdown ordering is the game's
 *   thread    a second guest thread's PostQuitMessage reaches only that thread's queue, never the main loop's
 *   refused   a guest thread whose host thread differs (child process) is refused with fatal 76, not a fake success
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/quit_message/run.cmd */
#include <windows.h>
#include <imm.h>
#include <stdio.h>
#include <stdlib.h>
#include "xrt_internal.h"
#include "monitor_windows.inc"

/* ---- owned stubs for the runtime symbols the adapter uses */
uint8_t* xrt_g;
unsigned xm_quiet;
static __declspec(thread) CPU* current;
static uint32_t last_error_guest = 0x5555;
CPU* xm_current_cpu(void) { return current; }
#undef xm_probe
void xm_probe(CPU* c, const XmRequest* q) { (void)c; (void)q; }
#define xm_probe xm_probe_gated
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
void xrt_log(const char* fmt, ...) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list a; (void)c; va_start(a, fmt); printf("     fatal %d: ", code); vprintf(fmt, a); printf("\n"); va_end(a);
    fflush(stdout); ExitProcess((UINT)code);
}
void xrt_set_last_error(CPU* c, uint32_t e) { (void)c; last_error_guest = e; }
uint32_t xrt_get_last_error(CPU* c) { (void)c; return last_error_guest; }
CPU* xrt_gui_callback_enter(CPU* c) { CPU* p = current; current = c; return p; }
void xrt_gui_callback_leave(CPU* p) { current = p; }
int xrt_dev_input_blocked(const char* what) { (void)what; return 0; }
void xrt_dev_input_tick(void) {}
void xrt_dev_input_window_actions(void) {}
int xrt_dev_input_allowed(void* hwnd, unsigned msg, unsigned long long wp, long long lp) { (void)hwnd; (void)msg; (void)wp; (void)lp; return 1; }
void xrt_dev_cursor(int op, long* x, long* y, const void* r) { (void)op; (void)x; (void)y; (void)r; }
static void begin(CPU* c) { SetLastError(xrt_get_last_error(c)); }
static void end(CPU* c) { xrt_set_last_error(c, GetLastError()); }
static HWND owned_window; /* the only registered window: token 0x100 */
static uint32_t window_token(HWND h) { return !h ? 0 : h == owned_window ? 0x100 : 0xdead; }
void* xrt_gui_device_window(CPU* c, uint32_t token) {
    if (token != 0x100) xrt_fatal(c, 76, "test: unknown window token %08x", token);
    return owned_window;
}
#include "window_transitions.inc"
#include "message_pump.inc"

static int failures;
#define CHECK(cond, ...) do { int ok_ = !!(cond); printf(ok_ ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!ok_) failures++; } while (0)

/* Guest layout inside the committed block: stack at 0x10000-0x18000, MSG at 0x18000. */
enum { GUEST_BASE = 0x10000, GUEST_SIZE = 0x10000, STACK_TOP = 0x18000, GUEST_MSG = 0x18000, RET_ADDR = 0x13371337 };
static void guest_call(CPU* c, void (*fn)(CPU*), const uint32_t* args, unsigned n) {
    unsigned i;
    c->r[ESP] = STACK_TOP - 4 * (n + 1);
    wr32(c->r[ESP], RET_ADDR);
    for (i = 0; i < n; i++) wr32(c->r[ESP] + 4 + 4 * i, args[i]);
    fn(c);
}
static void init_thread(XrtThread* t, CPU** cpu, int index) {
    memset(t, 0, sizeof *t);
    t->index = index; t->state = 1; t->host_tid = t->guest_tid = GetCurrentThreadId();
    t->cpu.thread = t; *cpu = &t->cpu; current = &t->cpu;
}
static int peek(CPU* c, uint32_t* words) {
    uint32_t args[5] = {GUEST_MSG, 0, 0, 0, PM_REMOVE};
    guest_call(c, hle_PeekMessageW, args, 5);
    memcpy(words, G2H(GUEST_MSG), 28);
    return (int)c->r[EAX];
}
static unsigned dispatched_user;
static LRESULT CALLBACK wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_USER + 7) { dispatched_user++; return 0; }
    return DefWindowProcW(h, m, wp, lp);
}

/* Second guest thread: its quit stays in its own queue. */
static volatile long second_quit_seen, second_done;
static DWORD WINAPI second_thread(void* unused) {
    XrtThread t; CPU* c; uint32_t args[1] = {3}, words[7]; MSG m;
    (void)unused;
    init_thread(&t, &c, 1);
    PeekMessageW(&m, NULL, 0, 0, PM_NOREMOVE); /* create this thread's queue */
    guest_call(c, hle_PostQuitMessage, args, 1);
    while (peek(c, words)) if (words[1] == WM_QUIT && words[2] == 3) second_quit_seen++;
    InterlockedExchange(&second_done, 1);
    return 0;
}

int main(int argc, char** argv) {
    XrtThread main_thread; CPU* c; uint32_t words[7], args[2]; int n, quits; WNDCLASSW wc = {0};
    xrt_g = (uint8_t*)VirtualAlloc(NULL, GUEST_BASE + GUEST_SIZE, MEM_RESERVE, PAGE_NOACCESS);
    if (!xrt_g || !VirtualAlloc(xrt_g + GUEST_BASE, GUEST_SIZE, MEM_COMMIT, PAGE_READWRITE)) { printf("FAIL guest memory\n"); return 1; }
    init_thread(&main_thread, &c, 0);
    if (argc > 1 && !strcmp(argv[1], "cross")) {
        main_thread.host_tid ^= 0x40000; /* the guest thread is not running on this host thread */
        args[0] = 0; guest_call(c, hle_PostQuitMessage, args, 1);
        printf("     cross-thread PostQuitMessage returned\n");
        return 0;
    }
    wc.lpfnWndProc = wndproc; wc.hInstance = GetModuleHandleW(NULL); wc.lpszClassName = L"xrt_quit_message";
    RegisterClassW(&wc);
    owned_window = CreateWindowExW(0, wc.lpszClassName, L"", WS_OVERLAPPED, 0, 0, 10, 10, NULL, NULL, wc.hInstance, NULL);
    CHECK(owned_window != NULL, "owned hidden window created");

    /* adapter shape */
    PostMessageW(owned_window, WM_USER + 7, 0, 0);
    last_error_guest = 0x5555;
    args[0] = 0; guest_call(c, hle_PostQuitMessage, args, 1);
    CHECK(c->r[ESP] == STACK_TOP && c->rv == RET_ADDR && c->r[EAX] == 0, "adapter: stdcall(1), EAX 0, return address %08x", c->rv);
    CHECK(last_error_guest == 0x5555, "adapter: guest last error kept (%x)", last_error_guest);

    /* the main loop */
    quits = 0; n = 0;
    while (peek(c, words)) {
        n++;
        if (words[1] == WM_QUIT) {
            quits++;
            CHECK(dispatched_user == 1, "order: message posted before the quit dispatched first (%u)", dispatched_user);
            CHECK(words[0] == 0 && words[2] == 0, "quit: WM_QUIT hwnd token %u wParam %u", words[0], words[2]);
        }
        args[0] = GUEST_MSG;
        guest_call(c, hle_TranslateMessage, args, 1);
        guest_call(c, hle_DispatchMessageW, args, 1);
        CHECK(c->r[ESP] == STACK_TOP, "pump: Translate/Dispatch of message %#x balanced", words[1]);
    }
    CHECK(quits == 1, "quit: WM_QUIT reported exactly once (%d of %d messages)", quits, n);

    /* exit code passes through */
    args[0] = 42; guest_call(c, hle_PostQuitMessage, args, 1);
    CHECK(peek(c, words) && words[1] == WM_QUIT && words[2] == 42, "quit: exit code 42 carried in wParam (%u)", words[2]);

    /* per-thread queue */
    {
        HANDLE h = CreateThread(NULL, 0, second_thread, NULL, 0, NULL);
        WaitForSingleObject(h, 5000); CloseHandle(h);
        current = c;
        CHECK(second_done && second_quit_seen == 1, "thread: second guest thread received its own WM_QUIT (%ld)", second_quit_seen);
        quits = 0;
        while (peek(c, words)) if (words[1] == WM_QUIT) quits++;
        CHECK(quits == 0, "thread: main loop queue unaffected by the other thread's quit");
    }

    /* refused off-thread use (child process) */
    {
        char self[MAX_PATH], cmd[MAX_PATH + 16]; STARTUPINFOA si = {sizeof si}; PROCESS_INFORMATION pi; DWORD code = 0;
        GetModuleFileNameA(NULL, self, MAX_PATH); snprintf(cmd, sizeof cmd, "\"%s\" cross", self);
        if (CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
            WaitForSingleObject(pi.hProcess, 10000); GetExitCodeProcess(pi.hProcess, &code);
            CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
        }
        CHECK(code == 76, "refused: guest/host thread mismatch is fatal 76 (exit %lu)", code);
    }
    DestroyWindow(owned_window);
    printf("%s (%d failure%s)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

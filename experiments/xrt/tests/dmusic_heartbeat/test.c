/* dmusic_heartbeat - owned reproduction of the intermittent DirectMusic helper exit during level music changes
 * (runs 20261101-180222/-180517/-183415/-183512: "helper ended outside shutdown"; the helper's heartbeat lines turned
 * to GetTime 88781170 / segment state 88781161 first).
 *
 * The developer helper (out/dev-init/dmusic_helper/main.c) starts a diagnostic heartbeat thread at each successful
 * InitAudio; it polls that performance every 2 s. A level change closes down and releases the performance and creates
 * a new one. This test drives the real helper in normal (non --test) mode through the same sequence, four times:
 * create performance, InitAudio, wait for a heartbeat, CloseDown, release the sound and the performance, wait 4.5 s.
 * The helper's stderr is captured.
 *
 *   alive    the helper still answers after every cycle (a new performance can be created)
 *   closed   after CloseDown/release no heartbeat reports a DirectMusic error HRESULT (0x8878xxxx): nothing queries a
 *            closed or released performance any more
 *   running  heartbeats of the current performance still appear (the diagnostic itself is kept)
 * Exit 0 when every check passes. Usage: dmusic_heartbeat <dmusic_helper.exe> <sandbox root with System and Music>
 * Build/run: experiments/xrt/tests/dmusic_heartbeat/run.cmd (about 30 s). */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "dmusic_pipe.h"

static DmbConnection conn;
static HANDLE log_read;
static char log_text[65536];
static volatile LONG log_len;
static int sync_cb(void* ctx, const DmbMessage* q, DmbMessage* r) { (void)ctx; (void)q; memset(r->v, 0, sizeof r->v); return 0; }
static DWORD WINAPI log_reader(void* unused) {
    char b[512]; DWORD n;
    (void)unused;
    while (ReadFile(log_read, b, sizeof b, &n, NULL) && n) {
        LONG at = log_len;
        if (at + (LONG)n < (LONG)sizeof log_text - 1) { memcpy(log_text + at, b, n); InterlockedExchange(&log_len, at + (LONG)n); }
        fwrite(b, 1, n, stdout);
    }
    return 0;
}
static DWORD WINAPI drain(void* unused) {   /* asynchronous channel: nothing is expected here */
    DmbMessage q; DWORD got; (void)unused;
    while (ReadFile(conn.async_input, &q, sizeof q, &got, NULL) && got) {}
    return 0;
}
static int failures;
#define CHECK(cond, ...) do { int ok_ = !!(cond); printf(ok_ ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!ok_) failures++; } while (0)
static int exchange(int op, uint32_t object, uint32_t v0, uint32_t v1, uint32_t v2, DmbMessage* m) {
    dmb_message(m, op, object); m->v[0] = v0; m->v[1] = v1; m->v[2] = v2;
    return dmb_exchange(&conn, m);
}
/* heartbeat lines in log_text[from..]: count those reporting a DirectMusic error and those reporting success */
static void heartbeats(LONG from, int* errors, int* good) {
    char* p = log_text + from;
    *errors = *good = 0;
    while ((p = strstr(p, "helper heartbeat")) != NULL) {
        char* gt = strstr(p, "GetTime ");
        if (gt && !strncmp(gt + 8, "8878", 4)) (*errors)++; else if (gt && !strncmp(gt + 8, "00000000", 8)) (*good)++;
        p += 16;
    }
}
int wmain(int argc, wchar_t** argv) {
    SECURITY_ATTRIBUTES sa = {sizeof sa, NULL, TRUE};
    HANDLE log_write, old_err = GetStdHandle(STD_ERROR_HANDLE);
    DmbMessage m;
    int cycle, errors, good, total_errors = 0, total_good = 0;
    if (argc != 3) return 2;
    CreatePipe(&log_read, &log_write, &sa, 65536);
    SetHandleInformation(log_read, HANDLE_FLAG_INHERIT, 0);
    SetStdHandle(STD_ERROR_HANDLE, log_write);         /* dmb_connect hands the helper a copy of this stderr */
    CreateThread(NULL, 0, log_reader, NULL, 0, NULL);
    if (!dmb_connect(&conn, argv[1], argv[2], 0, sync_cb, NULL)) { SetStdHandle(STD_ERROR_HANDLE, old_err); printf("FAIL connect: %s\n", conn.error); return 1; }
    SetStdHandle(STD_ERROR_HANDLE, old_err); CloseHandle(log_write);
    CreateThread(NULL, 0, drain, NULL, 0, NULL);
    for (cycle = 1; cycle <= 4; cycle++) {
        uint32_t perf, sound; LONG mark;
        if (!exchange(DMB_CREATE, 0, DMB_PERFORMANCE, 0, 0, &m) || m.v[0]) { CHECK(0, "cycle %d: create performance (%s)", cycle, conn.error); break; }
        perf = m.v[1];
        if (!exchange(DMB_INIT_AUDIO, perf, 8, 128, 0x3f, &m) || m.v[0]) { CHECK(0, "cycle %d: InitAudio (%s)", cycle, conn.error); break; }
        sound = m.v[1];
        Sleep(2300);
        CHECK(exchange(DMB_CLOSE, perf, 0, 0, 0, &m) && m.v[0] == 0, "cycle %d: CloseDown", cycle);
        mark = log_len;
        exchange(DMB_RELEASE, sound, 0, 0, 0, &m);
        CHECK(exchange(DMB_RELEASE, perf, 0, 0, 0, &m), "cycle %d: final release of the performance (count %u)", cycle, m.v[0]);
        Sleep(4500);
        heartbeats(mark, &errors, &good);
        total_errors += errors;
        CHECK(errors == 0, "cycle %d: no heartbeat queried the closed/released performance (%d error heartbeats)", cycle, errors);
        CHECK(exchange(DMB_HELLO, 0, 0, 0, 0, &m), "cycle %d: helper alive", cycle);
    }
    heartbeats(0, &errors, &good); total_good = good;
    CHECK(total_good >= 4, "running: heartbeats of live performances still reported (%d)", total_good);
    exchange(DMB_SHUTDOWN, 0, 0, 0, 0, &m);
    printf("%s (%d failure%s; %d error heartbeats after close)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s", total_errors);
    return failures ? 1 : 0;
}

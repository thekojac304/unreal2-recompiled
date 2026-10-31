/* Developer diagnostics only. Never linked into the strict candidate. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <stdio.h>
#include <stdlib.h>
#include "dev_support.h"
static volatile LONG dumped;

void dev_dump(EXCEPTION_POINTERS *exception, const char *reason) {
    char path[1024];
    const char *root = getenv("XRT_DEV_OUTPUT");
    MINIDUMP_EXCEPTION_INFORMATION info;
    HANDLE file;
    BOOL ok;
    if (!root || InterlockedExchange(&dumped, 1)) return;
    snprintf(path, sizeof path, "%s\\crash.dmp", root);
    file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "dev: dump open failed: %lu\n", GetLastError()); return;
    }
    info.ThreadId = GetCurrentThreadId();
    info.ExceptionPointers = exception;
    info.ClientPointers = FALSE;
    ok = MiniDumpWriteDump(GetCurrentProcess(), GetCurrentProcessId(), file,
        MiniDumpWithIndirectlyReferencedMemory | MiniDumpWithThreadInfo,
        exception ? &info : NULL, NULL, NULL);
    fprintf(stderr, "dev: %s dump %s (error %lu)\n", reason, ok ? "saved" : "FAILED", ok ? 0 : GetLastError());
    CloseHandle(file);
    fflush(stderr);
}
static LONG WINAPI unhandled(EXCEPTION_POINTERS *exception) {
    dev_dump(exception, "unhandled exception");
    return EXCEPTION_EXECUTE_HANDLER;
}
void dev_start(void) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    SetUnhandledExceptionFilter(unhandled);
    if (getenv("XRT_DEV_ATTACH")) {
        fprintf(stderr, "dev: attach Visual Studio/WinDbg to PID %lu; timeout is still active\n", GetCurrentProcessId());
        fflush(stderr);
        while (!IsDebuggerPresent()) Sleep(50);
        DebugBreak();
    }
}
__declspec(noreturn) void dev_finish(void) {
    fprintf(stderr, "dev: INIT_RETURN endpoint reached; stopping before guest 0x1090ED5C\n");
    fflush(NULL);
    /* A distinct controlled-stop status, never a claim of normal engine exit. */
    ExitProcess(10);
}

#ifndef XRT_DEV_FIXTURE
#include "xrt_internal.h"
#include "monitor.h"
/* First-scene mode (XRT_DEV_SCENE=<world frames>): Init return is recorded and
 * the normal caller continues. The stop is after the Nth successful Present of
 * a frame whose FLevelSceneNode::Render issued native draws. Init-only otherwise. */
static int scene = -1, post_init;
static unsigned scene_limit, world_frames, post_presents, last_renders, last_engine, last_level;
static ULONGLONG init_ms;
static unsigned nonworld, cue_frames[16], cue_count;
/* World frames scheduled for capture by scene cues (beginscene, FinalEvent). */
static int cue_capture(unsigned frame) {
    unsigned i;
    for (i = 0; i < cue_count; i++) if (cue_frames[i] == frame) return 1;
    return 0;
}
static unsigned scene_ms;
static int scene_mode(void) {
    if (scene < 0) {
        const char *v = getenv("XRT_DEV_SCENE");
        scene = v && *v;
        scene_limit = scene ? (unsigned)strtoul(v, NULL, 10) : 0;
        if (scene && (scene_limit < 1 || scene_limit > 100000)) scene_limit = 60;
        v = getenv("XRT_DEV_SCENE_MS");
        scene_ms = v && *v ? (unsigned)strtoul(v, NULL, 10) : 0;
    }
    return scene;
}
/* Powers of two, then every 256th world frame. XRT_DEV_SCENE_MS adds a clean
 * wall-clock stop so long runs end with a report before the outer deadline. */
static int scene_capture_frame(unsigned n) { return (n & (n - 1)) == 0 || !(n % 256) || n == scene_limit; }
/* Performance evidence (first-scene mode): the QPC time of every post-Init present goes
 * to frames.csv at the stop; thread CPU times are logged at each scripted "shot".
 * XRT_DEV_SAMPLE_HZ=N samples the game thread: suspend, copy the top of its stack and
 * context, resume, then unwind the copy (no lock is taken while it is suspended).
 * Samples (host stack + guest pc) go to samples.bin, loaded modules to modules.txt. */
typedef struct { ULONGLONG qpc; unsigned draws, prims, world; } FrameRow;
#define FRAME_ROWS 131072
#define SAMPLE_DEPTH 24
#define SAMPLE_STACK 65536
typedef struct { ULONGLONG qpc; unsigned guest_pc, depth; ULONGLONG rip[SAMPLE_DEPTH]; } Sample;
static FrameRow *frame_rows; static unsigned frame_count;
static LARGE_INTEGER qpc_freq, qpc_init;
static Sample *samples; static volatile LONG sample_count, sampler_stop; static unsigned sample_max;
static HANDLE sampled, sampler; static CPU *sampled_cpu; static ULONG_PTR stack_lo, stack_hi;
static unsigned char *stack_copy;
/* Sample times are de-aliased from the 1 ms timer tick: Sleep alone wakes on the same ticks as the
 * guest's Sleep(1) poller and the scheduler ticker, and then over-samples baton hand-overs. Each
 * sample is taken at a QPC deadline (period + random 0..1 ms), reached by Sleep then a short spin. */
static DWORD WINAPI sampler_main(void *arg) {
    unsigned ms = (unsigned)(UINT_PTR)arg, rng = 0x9e3779b9u;
    LARGE_INTEGER f, next, now;
    QueryPerformanceFrequency(&f); QueryPerformanceCounter(&next);
    while (!sampler_stop && (unsigned)sample_count < sample_max) {
        CONTEXT ctx; ULONG_PTR rsp, n, copy; Sample *s; unsigned k;
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        next.QuadPart += f.QuadPart * ms / 1000 + (LONGLONG)(rng % 1000) * f.QuadPart / 1000000;
        if (ms > 2) Sleep(ms - 2);
        do { YieldProcessor(); QueryPerformanceCounter(&now); } while (now.QuadPart < next.QuadPart);
        ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
        if (SuspendThread(sampled) == (DWORD)-1) break;
        if (!GetThreadContext(sampled, &ctx) || ctx.Rsp < stack_lo || ctx.Rsp >= stack_hi) { ResumeThread(sampled); continue; }
        rsp = ctx.Rsp; n = stack_hi - rsp; if (n > SAMPLE_STACK) n = SAMPLE_STACK;
        memcpy(stack_copy, (void *)rsp, n);
        s = &samples[sample_count];
        s->guest_pc = sampled_cpu ? sampled_cpu->pc : 0;
        ResumeThread(sampled);
        QueryPerformanceCounter((LARGE_INTEGER *)&s->qpc);
        copy = (ULONG_PTR)stack_copy;
        ctx.Rsp = copy; if (ctx.Rbp >= rsp && ctx.Rbp < rsp + n) ctx.Rbp = copy + (ctx.Rbp - rsp);
        k = 0;
        __try {
            while (k < SAMPLE_DEPTH) {
                DWORD64 base; PRUNTIME_FUNCTION fe; void *hd; DWORD64 ef;
                s->rip[k++] = ctx.Rip;
                fe = RtlLookupFunctionEntry(ctx.Rip, &base, NULL);
                if (!fe) {
                    if (ctx.Rsp < copy || ctx.Rsp + 8 > copy + n) break;
                    ctx.Rip = *(DWORD64 *)ctx.Rsp; ctx.Rsp += 8;
                } else RtlVirtualUnwind(UNW_FLAG_NHANDLER, base, ctx.Rip, fe, &ctx, &hd, &ef, NULL);
                if (!ctx.Rip || ctx.Rsp < copy || ctx.Rsp >= copy + n) break;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
        s->depth = k;
        InterlockedIncrement(&sample_count);
    }
    return 0;
}
static double qpc_ms(ULONGLONG t) { return (double)(LONGLONG)(t - (ULONGLONG)qpc_init.QuadPart) * 1000.0 / (double)qpc_freq.QuadPart; }
static void perf_start(CPU *c) {
    const char *v = getenv("XRT_DEV_SAMPLE_HZ");
    unsigned hz = v && *v ? (unsigned)strtoul(v, NULL, 10) : 0;
    QueryPerformanceFrequency(&qpc_freq); QueryPerformanceCounter(&qpc_init);
    frame_rows = calloc(FRAME_ROWS, sizeof *frame_rows);
    if (!hz || hz > 1000) return;
    sample_max = hz * 400;
    samples = calloc(sample_max, sizeof *samples); stack_copy = malloc(SAMPLE_STACK);
    if (!samples || !stack_copy) { xrt_log("DEV sampler: allocation failed; not sampling"); return; }
    GetCurrentThreadStackLimits(&stack_lo, &stack_hi);
    if (!DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &sampled,
                         THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, 0)) return;
    sampled_cpu = c;
    sampler = CreateThread(NULL, 0, sampler_main, (void *)(UINT_PTR)(1000 / hz ? 1000 / hz : 1), 0, NULL);
    xrt_log("DEV sampler: game thread %lu at %u Hz (stack %p-%p)", GetCurrentThreadId(), hz, (void *)stack_lo, (void *)stack_hi);
}
static void perf_frame(unsigned draws, unsigned prims, int world) {
    if (frame_rows && frame_count < FRAME_ROWS) {
        FrameRow *r = &frame_rows[frame_count++];
        QueryPerformanceCounter((LARGE_INTEGER *)&r->qpc); r->draws = draws; r->prims = prims; r->world = (unsigned)world;
    }
}
/* One line per thread of this process: user/kernel CPU ms since thread creation. */
static void perf_threads(const char *why) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0); THREADENTRY32 te; LARGE_INTEGER now;
    if (snap == INVALID_HANDLE_VALUE) return;
    QueryPerformanceCounter(&now);
    te.dwSize = sizeof te;
    if (Thread32First(snap, &te)) do {
        HANDLE h; FILETIME cr, ex, k, u;
        if (te.th32OwnerProcessID != GetCurrentProcessId()) continue;
        if (!(h = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, te.th32ThreadID))) continue;
        if (GetThreadTimes(h, &cr, &ex, &k, &u))
            xrt_log("DEV threads %s at %.1f ms: tid %lu%s user %.1f kernel %.1f", why, qpc_ms((ULONGLONG)now.QuadPart), te.th32ThreadID,
                    te.th32ThreadID == GetCurrentThreadId() ? " (game)" : "",
                    (double)(((ULONGLONG)u.dwHighDateTime << 32) | u.dwLowDateTime) / 1e4,
                    (double)(((ULONGLONG)k.dwHighDateTime << 32) | k.dwLowDateTime) / 1e4);
        CloseHandle(h);
    } while (Thread32Next(snap, &te));
    CloseHandle(snap);
}
static void perf_write(void) {
    char path[1024]; const char *root = getenv("XRT_DEV_OUTPUT"); FILE *f; unsigned i;
    if (!root || !frame_rows) return;
    if (sampler) { sampler_stop = 1; WaitForSingleObject(sampler, 2000); }
    perf_threads("stop");
    xrt_baton_stats_log();
    snprintf(path, sizeof path, "%s\\frames.csv", root);
    if ((f = fopen(path, "w"))) {
        fprintf(f, "present,ms,world,draws,prims\n");
        for (i = 0; i < frame_count; i++)
            fprintf(f, "%u,%.3f,%u,%u,%u\n", i + 1, qpc_ms(frame_rows[i].qpc), frame_rows[i].world, frame_rows[i].draws, frame_rows[i].prims);
        fclose(f);
    }
    if (!samples) return;
    snprintf(path, sizeof path, "%s\\samples.bin", root);
    if ((f = fopen(path, "wb"))) {
        double ms;
        for (i = 0; i < (unsigned)sample_count; i++) {
            ms = qpc_ms(samples[i].qpc);
            fwrite(&ms, sizeof ms, 1, f); fwrite(&samples[i].guest_pc, 4, 1, f); fwrite(&samples[i].depth, 4, 1, f);
            fwrite(samples[i].rip, 8, samples[i].depth, f);
        }
        fclose(f);
    }
    snprintf(path, sizeof path, "%s\\modules.txt", root);
    if ((f = fopen(path, "w"))) {
        HMODULE mods[512]; DWORD need; MODULEINFO mi; wchar_t name[MAX_PATH];
        if (K32EnumProcessModules(GetCurrentProcess(), mods, sizeof mods, &need))
            for (i = 0; i < need / sizeof mods[0] && i < 512; i++)
                if (K32GetModuleInformation(GetCurrentProcess(), mods[i], &mi, sizeof mi) &&
                    GetModuleFileNameW(mods[i], name, MAX_PATH))
                    fprintf(f, "%p %lu %ls\n", mi.lpBaseOfDll, mi.SizeOfImage, name);
        fclose(f);
    }
    xrt_log("DEV perf: %u presents, %ld samples written", frame_count, sample_count);
}
static __declspec(noreturn) void scene_stop(CPU *c, const char *why) {
    perf_write();
    xrt_event("dev_scene_present", "\"world_frames\":%u,\"presents\":%u,\"elapsed_ms\":%llu,\"reason\":\"%s\"",
              world_frames, post_presents, GetTickCount64() - init_ms, why);
    xm_checkpoint(c, "dev.scene.present");
    xrt_report_write(11, "developer first-scene stop after bounded world frames");
    fprintf(stderr, "dev: FIRST_SCENE endpoint (%s) after %u world frames (%u post-Init presents, %llu ms)\n",
            why, world_frames, post_presents, GetTickCount64() - init_ms);
    fflush(NULL);
    ExitProcess(11);
}
/* XRT_DEV_DRAW_FRAMES=a,b,...: up to four world frames whose draws are logged. */
int xrt_dev_draw_dump(void) {
    static unsigned frames[4], count; static int parsed;
    unsigned i;
    if (!parsed) {
        const char *v = getenv("XRT_DEV_DRAW_FRAMES");
        parsed = 1;
        while (v && *v && count < 4) { frames[count++] = (unsigned)strtoul(v, (char **)&v, 10); if (*v) v++; }
    }
    if (!scene_mode() || !post_init) return 0;
    for (i = 0; i < count; i++) if (frames[i] == world_frames + 1) return 1;
    return 0;
}
/* Scene cues from the music's lyric track: logged with timing, and the next
 * world frame plus one 64 frames later are captured (bounded). */
void xrt_dev_music_cue(const unsigned short *text) {
    static unsigned cues;
    if (!scene_mode() || !post_init) return;
    if (wcscmp((const wchar_t *)text, L"beginscene") && wcscmp((const wchar_t *)text, L"FinalEvent")) return;
    cues++;
    xrt_log("DEV music cue %u '%ls' at world frame %u, present %u, +%llu ms", cues, (const wchar_t *)text,
            world_frames, post_presents, GetTickCount64() - init_ms);
    xrt_event("dev_music_cue", "\"cue\":%u,\"world_frame\":%u,\"presents\":%u", cues, world_frames, post_presents);
    if (cue_count + 2 <= 16) { cue_frames[cue_count++] = world_frames + 1; cue_frames[cue_count++] = world_frames + 64; }
}
/* XRT_DEV_NO_INPUT=1: physical keyboard/mouse never reaches the experiment. */
int xrt_dev_input_blocked(const char *what) {
    static int mode = -1; static unsigned dropped;
    if (mode < 0) { const char *v = getenv("XRT_DEV_NO_INPUT"); mode = v && *v == '1'; }
    if (mode && what && dropped++ < 16) xrt_log("DEV input isolation: dropped %s", what);
    return mode;
}
/* XRT_DEV_INPUT (dev.py --input): a short explicit input script, only with isolation on.
 * Steps "T:verb[:a[:b[:c]]]" separated by ';', T = ms after Init return, ascending:
 *   key:VK[:HOLD]    WM_KEYDOWN, WM_KEYUP after HOLD ms (default 100), posted to the game's
 *                    own D3D focus window; GetKeyState reports the key down meanwhile
 *   move:DX:DY[:MS]  mouse motion spread over MS: DirectInput axis data, the virtual cursor
 *                    and WM_MOUSEMOVE, as one physical mouse produces them together
 *   click[:HOLD]     left button: DirectInput button 0 and WM_LBUTTONDOWN/UP
 *   shot             capture the next present
 * Only the exact scripted messages pass the isolation filter; physical input stays dropped.
 * Under isolation GetCursorPos/SetCursorPos/ClipCursor use a virtual cursor, never the desktop's. */
typedef struct { unsigned t; char verb; int a, b, c; } InputStep;
static InputStep in_steps[256];
static unsigned in_count, in_next, in_delivered;
static int in_parsed;
static HWND in_window;
static struct { unsigned vk; ULONGLONG up; } in_keys[8];
static struct { ULONGLONG start; unsigned ms; int dx, dy, done_x, done_y; } in_moves[4];
static ULONGLONG in_button_up, in_paused;
static int in_button;
static struct { UINT msg; WPARAM wp; LPARAM lp; ULONGLONG expires; int any_wp; } in_allow[32];
static struct { unsigned ofs, data; } in_di[256];
static unsigned in_di_head, in_di_tail, in_shot;
static POINT in_cursor;
static RECT in_clip;
static int in_cursor_valid, in_clipped;
static void input_parse(void) {
    const char *v = getenv("XRT_DEV_INPUT");
    in_parsed = 1;
    while (v && *v && in_count < 256) {
        InputStep s = {0};
        char verb[16] = {0};
        int n = 0;
        s.t = (unsigned)strtoul(v, (char **)&v, 10);
        if (*v++ != ':') break;
        while (*v && *v != ':' && *v != ';' && n < 15) verb[n++] = *v++;
        if (!strcmp(verb, "key")) s.verb = 'k'; else if (!strcmp(verb, "move")) s.verb = 'm';
        else if (!strcmp(verb, "click")) s.verb = 'c'; else if (!strcmp(verb, "shot")) s.verb = 's';
        else { xrt_log("DEV input script: unknown verb '%s'; script ignored from here", verb); break; }
        if (*v == ':') s.a = (int)strtol(v + 1, (char **)&v, 0);
        if (*v == ':') s.b = (int)strtol(v + 1, (char **)&v, 0);
        if (*v == ':') s.c = (int)strtol(v + 1, (char **)&v, 0);
        if (in_count && s.t < in_steps[in_count - 1].t) { xrt_log("DEV input script: times must ascend; ignored from step %u", in_count); break; }
        in_steps[in_count++] = s;
        while (*v && *v != ';') v++;
        if (*v == ';') v++;
    }
    if (in_count) xrt_log("DEV input script: %u steps%s", in_count, v && *v ? " (TRUNCATED: more steps than the 256 supported)" : "");
}
void xrt_dev_input_window(void *hwnd) {
    if (!in_window && hwnd) { in_window = (HWND)hwnd; xrt_log("DEV input: game focus window %p", hwnd); }
}
static void input_allow(UINT msg, WPARAM wp, LPARAM lp, int any_wp) {
    unsigned i;
    for (i = 0; i < 32; i++) if (!in_allow[i].expires) break;
    if (i == 32) { xrt_log("DEV input: allow table full; message not posted"); return; }
    in_allow[i].msg = msg; in_allow[i].wp = wp; in_allow[i].lp = lp; in_allow[i].any_wp = any_wp;
    in_allow[i].expires = GetTickCount64() + 2000;
    if (!any_wp && !PostMessageW(in_window, msg, wp, lp)) { xrt_log("DEV input: PostMessage %x failed %lu", msg, GetLastError()); in_allow[i].expires = 0; }
}
/* 1 when a scripted message was posted for exactly this window/message: consumed once. */
int xrt_dev_input_allowed(void *hwnd, unsigned msg, unsigned long long wp, long long lp) {
    unsigned i; ULONGLONG now = GetTickCount64();
    if (!in_window || (HWND)hwnd != in_window) return 0;
    for (i = 0; i < 32; i++) {
        if (!in_allow[i].expires) continue;
        if (in_allow[i].expires < now) { xrt_log("DEV input: scripted message %x expired undelivered", in_allow[i].msg); in_allow[i].expires = 0; continue; }
        if (in_allow[i].msg == msg && (in_allow[i].any_wp || (in_allow[i].wp == wp && in_allow[i].lp == lp))) {
            in_allow[i].expires = 0;
            if (in_delivered++ < 96) xrt_log("DEV input delivered msg %x wp %llx lp %llx at +%llu ms", msg, wp, lp, now - init_ms);
            if (msg == WM_KEYDOWN) input_allow(WM_CHAR, 0, 0, 1); /* TranslateMessage's own WM_CHAR */
            return 1;
        }
    }
    return 0;
}
static void di_push(unsigned ofs, unsigned data) {
    if (in_di_tail - in_di_head >= 256) { xrt_log("DEV input: DirectInput queue full"); return; }
    in_di[in_di_tail++ & 255].ofs = ofs; in_di[(in_di_tail - 1) & 255].data = data;
}
int xrt_dev_input_mouse(unsigned *ofs, unsigned *data) {
    if (in_di_head == in_di_tail) return 0;
    *ofs = in_di[in_di_head & 255].ofs; *data = in_di[in_di_head & 255].data; in_di_head++;
    return 1;
}
static void cursor_init(void) {
    if (!in_cursor_valid) { GetCursorPos(&in_cursor); in_cursor_valid = 1; }
}
static void cursor_clamp(void) {
    if (in_clipped) {
        if (in_cursor.x < in_clip.left) in_cursor.x = in_clip.left;
        if (in_cursor.x >= in_clip.right) in_cursor.x = in_clip.right - 1;
        if (in_cursor.y < in_clip.top) in_cursor.y = in_clip.top;
        if (in_cursor.y >= in_clip.bottom) in_cursor.y = in_clip.bottom - 1;
    }
}
/* Virtual cursor under isolation: op 0 get, 1 set, 2 clip (r NULL = unclip). */
void xrt_dev_cursor(int op, long *x, long *y, const void *r) {
    cursor_init();
    if (op == 0) { *x = in_cursor.x; *y = in_cursor.y; return; }
    if (op == 1) { in_cursor.x = *x; in_cursor.y = *y; cursor_clamp(); return; }
    in_clipped = r != NULL;
    if (r) { in_clip = *(const RECT *)r; cursor_clamp(); }
}
static LPARAM client_point(void) {
    POINT p = in_cursor;
    ScreenToClient(in_window, &p);
    return MAKELPARAM((short)p.x, (short)p.y);
}
int xrt_dev_key_held(unsigned vk) {
    unsigned i;
    for (i = 0; i < 8; i++) if (in_keys[i].up && in_keys[i].vk == vk) return 1;
    return vk == VK_LBUTTON && in_button;
}
static void key_post(unsigned vk, int down) {
    UINT sc = MapVirtualKeyW(vk, MAPVK_VK_TO_VSC);
    LPARAM lp = 1 | (LPARAM)sc << 16 | (down ? 0 : (LPARAM)0xC0000000u);
    input_allow(down ? WM_KEYDOWN : WM_KEYUP, vk, lp, 0);
}
/* Called from the guest's message pump before each host PeekMessage. */
void xrt_dev_input_tick(void) {
    ULONGLONG now; unsigned i; int ours;
    if (!in_parsed) input_parse();
    if (!in_count || !scene_mode() || !post_init || !xrt_dev_input_blocked(NULL)) return;
    now = GetTickCount64();
    if (!in_window) return;
    {
        /* Focus-dependent input: new steps and motion run only while a window of this process is
         * the foreground window; otherwise the schedule pauses (later steps shift). Releases still
         * go out so nothing stays held. Focus is never taken. */
        static ULONGLONG last; static int foreground = -1;
        DWORD pid = 0; HWND fg = GetForegroundWindow();
        if (fg) GetWindowThreadProcessId(fg, &pid);
        ours = pid == GetCurrentProcessId();
        if (ours != foreground) {
            xrt_log("DEV input: game process %s the foreground at +%llu ms (schedule paused %llu ms so far)",
                    ours ? "has" : "does not have", now - init_ms, in_paused);
            foreground = ours;
        }
        if (!ours && last) in_paused += now - last;
        last = now;
    }
    cursor_init();
    for (i = 0; i < 8; i++) if (in_keys[i].up && now >= in_keys[i].up) { key_post(in_keys[i].vk, 0); in_keys[i].up = 0; }
    if (in_button && now >= in_button_up) {
        in_button = 0; di_push(12, 0); input_allow(WM_LBUTTONUP, 0, client_point(), 0);
    }
    if (!ours) return;
    for (i = 0; i < 4; i++) {
        int wx, wy, ddx, ddy; double f;
        if (!in_moves[i].start) continue;
        f = in_moves[i].ms ? (double)(now - in_moves[i].start) / in_moves[i].ms : 1.0;
        if (f > 1.0) f = 1.0;
        wx = (int)(in_moves[i].dx * f); wy = (int)(in_moves[i].dy * f);
        ddx = wx - in_moves[i].done_x; ddy = wy - in_moves[i].done_y;
        if (ddx || ddy) {
            in_moves[i].done_x = wx; in_moves[i].done_y = wy;
            if (ddx) di_push(0, (unsigned)ddx);
            if (ddy) di_push(4, (unsigned)ddy);
            in_cursor.x += ddx; in_cursor.y += ddy; cursor_clamp();
            input_allow(WM_MOUSEMOVE, in_button ? MK_LBUTTON : 0, client_point(), 0);
        }
        if (f >= 1.0) in_moves[i].start = 0;
    }
    while (in_next < in_count && now - init_ms - in_paused >= in_steps[in_next].t) {
        InputStep *s = &in_steps[in_next++];
        xrt_log("DEV input step %u at +%llu ms: %c %d %d %d", in_next, now - init_ms, s->verb, s->a, s->b, s->c);
        if (s->verb == 'k') {
            for (i = 0; i < 8 && in_keys[i].up; i++) {}
            if (i == 8 || s->a < 1 || s->a > 254) { xrt_log("DEV input: key step refused"); continue; }
            in_keys[i].vk = (unsigned)s->a; in_keys[i].up = now + (s->b > 0 ? (unsigned)s->b : 100);
            key_post((unsigned)s->a, 1);
        } else if (s->verb == 'm') {
            for (i = 0; i < 4 && in_moves[i].start; i++) {}
            if (i == 4) { xrt_log("DEV input: move step refused"); continue; }
            in_moves[i].start = now ? now : 1; in_moves[i].ms = s->c > 0 ? (unsigned)s->c : 0;
            in_moves[i].dx = s->a; in_moves[i].dy = s->b; in_moves[i].done_x = in_moves[i].done_y = 0;
        } else if (s->verb == 'c') {
            if (in_button) continue;
            in_button = 1; in_button_up = now + (s->a > 0 ? (unsigned)s->a : 100);
            di_push(12, 0x80); input_allow(WM_LBUTTONDOWN, MK_LBUTTON, client_point(), 0);
        } else if (s->verb == 's') { in_shot = 1; perf_threads("shot"); }
        {
            POINT p = in_cursor; ScreenToClient(in_window, &p);
            xrt_log("DEV input cursor client %ld,%ld", p.x, p.y);
        }
    }
}
static int map_allowed(const char *path) {
    const char *v = getenv("XRT_DEV_ALLOW_MAPS"), *base = strrchr(path, '\\');
    char list[512], *tok, *ctx = NULL;
    base = base ? base + 1 : path;
    if (!v || !*v || strlen(v) >= sizeof list) return 0;
    strcpy(list, v);
    for (tok = strtok_s(list, ";", &ctx); tok; tok = strtok_s(NULL, ";", &ctx)) if (!_stricmp(tok, base)) return 1;
    return 0;
}
/* A successful post-Init open of a map file is the natural transition out of
 * CS_Intro: record it and stop before the next level loads (no gameplay). */
void xrt_dev_map_open(CPU *c, const char *path) {
    size_t n = strlen(path);
    if (!scene_mode() || !post_init || n < 4 || _stricmp(path + n - 4, ".un2")) return;
    if (map_allowed(path)) {
        xrt_log("DEV map transition (allowed): post-Init open of \"%s\" after %u world frames, +%llu ms", path, world_frames,
                GetTickCount64() - init_ms);
        return;
    }
    xrt_log("DEV map transition: post-Init open of \"%s\" after %u world frames", path, world_frames);
    xrt_event("dev_map_transition", "\"world_frames\":%u", world_frames);
    scene_stop(c, "map transition");
}
/* Returns the world frame to capture, or 0x10000|present for the first two
 * non-world post-Init presents (a readback reference from the same run). */
int xrt_dev_scene_capture(unsigned level_renders, unsigned scene_draws) {
    if (!scene_mode() || !post_init) return 0;
    if (in_shot) {
        in_shot = 0;
        if (level_renders != last_renders && scene_draws) return (int)(world_frames + 1);
        if (post_presents + 1 <= 0xffffu) return (int)(0x20000u | (post_presents + 1));
    }
    if (level_renders == last_renders || !scene_draws) {
        unsigned n = nonworld + 1;
        if (post_presents < 2) return (int)(0x10000u | (post_presents + 1));
        /* After world frames began: non-world presents 1,2,4..64, then every 256th. */
        if (world_frames && ((n <= 64 && !(n & (n - 1))) || !(n % 256)) && post_presents + 1 <= 0xffffu)
            return (int)(0x20000u | (post_presents + 1));
        return 0;
    }
    return scene_capture_frame(world_frames + 1) || cue_capture(world_frames + 1) ? (int)(world_frames + 1) : 0;
}
void xrt_dev_scene_frame(unsigned frame, unsigned width, unsigned height, unsigned format, const void *bits, int pitch) {
    char path[1024];
    const char *root = getenv("XRT_DEV_OUTPUT");
    unsigned x, y, lit = 0, used = 0, row = (width * 3 + 3) & ~3u;
    static unsigned char hist[4096];
    double luma = 0;
    unsigned char *line;
    FILE *f;
    if (!root || !width || !height || width > 16384 || height > 16384 || (format != 21 && format != 22)) {
        xrt_log("DEV scene frame %u: unsupported readback %ux%u format %u", frame, width, height, format);
        return;
    }
    if (frame & 0x20000u) snprintf(path, sizeof path, "%s\\present-%05u.bmp", root, frame & 0xffffu);
    else if (frame & 0x10000u) snprintf(path, sizeof path, "%s\\startup-present-%04u.bmp", root, frame & 0xffffu);
    else snprintf(path, sizeof path, "%s\\scene-frame-%04u.bmp", root, frame);
    if (!(f = fopen(path, "wb")) || !(line = malloc(row))) { if (f) fclose(f); xrt_log("DEV scene frame %u: cannot write", frame); return; }
    {
        BITMAPFILEHEADER fh = {0x4d42, (DWORD)(sizeof fh + sizeof(BITMAPINFOHEADER) + row * height), 0, 0, sizeof fh + sizeof(BITMAPINFOHEADER)};
        BITMAPINFOHEADER ih = {sizeof ih, (LONG)width, (LONG)height, 1, 24, BI_RGB};
        fwrite(&fh, sizeof fh, 1, f); fwrite(&ih, sizeof ih, 1, f);
    }
    memset(hist, 0, sizeof hist);
    for (y = height; y-- > 0;) {
        const unsigned char *src = (const unsigned char *)bits + (size_t)y * pitch;
        memset(line, 0, row);
        for (x = 0; x < width; x++) {
            unsigned b = src[4 * x], g = src[4 * x + 1], r = src[4 * x + 2];
            line[3 * x] = (unsigned char)b; line[3 * x + 1] = (unsigned char)g; line[3 * x + 2] = (unsigned char)r;
            if (r | g | b) lit++;
            luma += 0.299 * r + 0.587 * g + 0.114 * b;
            hist[(r >> 4) << 8 | (g >> 4) << 4 | b >> 4] = 1;
        }
        fwrite(line, row, 1, f);
    }
    free(line); fclose(f);
    for (x = 0; x < 4096; x++) used += hist[x];
    xrt_log("DEV scene frame %u captured %ux%u fmt %u: nonblack=%u/%u mean_luma=%.1f colors4bit=%u -> %s",
            frame, width, height, format, lit, width * height, luma / ((double)width * height), used, path);
    xrt_event("dev_scene_capture", "\"frame\":%u,\"width\":%u,\"height\":%u,\"nonblack\":%u,\"colors4bit\":%u",
              frame, width, height, lit, used);
}
void xrt_dev_scene_present(CPU *c, long hr, unsigned draws, unsigned prims, unsigned scene_draws, unsigned scene_prims,
                           unsigned level_draws) {
    unsigned renders, engine, level, scene_renders = xrt_scene_level_renders + xrt_scene_camera_renders;
    int world;
    if (!scene_mode() || !post_init) return;
    post_presents++;
    renders = scene_renders - last_renders; last_renders = scene_renders;
    engine = xrt_scene_engine_ticks - last_engine; last_engine = xrt_scene_engine_ticks;
    level = xrt_scene_level_ticks - last_level; last_level = xrt_scene_level_ticks;
    world = hr >= 0 && renders && scene_draws;
    perf_frame(draws, prims, world);
    if (world) world_frames++;
    else if (hr >= 0) nonworld++;
    if (post_presents <= 32 || (world && scene_capture_frame(world_frames)) || !(post_presents % 64))
        xrt_log("DEV post-Init present %u at +%llu ms hr=%08lx draws=%u prims=%u level_renders=%u scene_draws=%u "
                "scene_prims=%u level_draws=%u engine_ticks=%u level_ticks=%u world_frame=%u",
                post_presents, GetTickCount64() - init_ms, (unsigned long)hr, draws, prims, renders, scene_draws,
                scene_prims, level_draws, engine, level, world ? world_frames : 0);
    if (world && world_frames == scene_limit) scene_stop(c, "frame limit");
    if (hr >= 0 && scene_ms && GetTickCount64() - init_ms >= scene_ms) scene_stop(c, "time limit");
}
__declspec(noinline) void xrt_dev_init_return(CPU *c) {
    xrt_log("DEV Init returned: caller=1090ed59 return=%08x esp=%08x", c->rv, c->r[ESP]);
    xrt_event("dev_init_return", "\"guest_next\": \"0x1090ed5c\"");
    xm_checkpoint(c, "dev.Init.return");
    if (scene_mode()) {
        /* Continue into the normal post-Init caller; counters start here. */
        post_init = 1; init_ms = GetTickCount64();
        perf_start(c);
        last_renders = xrt_scene_level_renders + xrt_scene_camera_renders; last_engine = xrt_scene_engine_ticks; last_level = xrt_scene_level_ticks;
        xrt_log("DEV first-scene mode: continuing to guest 0x1090ed5c; stop after %u world frames", scene_limit);
        fprintf(stderr, "dev: Init returned; first-scene mode continues (%u world frames)\n", scene_limit);
        return;
    }
    xrt_report_write(10, "developer Init-return stop; main loop not entered");
    /* We are still inside outer guest invocation scopes. CHECKPOINT flushes;
       CLOSE would falsely require an orderly return from the whole process. */
    dev_finish();
}
#endif

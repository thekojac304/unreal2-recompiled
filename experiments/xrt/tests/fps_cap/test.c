/* fps_cap - focused test of the developer frame limiter (tools/xrt/dev/dev_support.c, XRT_DEV_FPS_CAP / dev.py
 * --fps-cap). Includes dev_support.c itself with the runtime it calls replaced by owned stubs, then drives
 * xrt_dev_scene_present as the Present hook does, with a simulated game frame (a QPC spin of WORK ms) before each one.
 *
 *   pacing    with headroom the achieved rate is the cap (within 1%) and the median frame is the period (+-0.3 ms)
 *   no spin   the thread's CPU time is the simulated work only: the wait itself costs < 2% of a core
 *   baton     every wait releases the execution baton first and re-acquires it after (balanced, never nested)
 *   overrun   a frame longer than the period is not waited for (rate = 1/work)
 *   phase     alternating 2/12 ms frames at 120 FPS average 120 FPS (a slightly late frame keeps the phase)
 *   stall     after a 100 ms stall the deadline is re-anchored: only the stalled frame goes unwaited and every later
 *             frame waits again (no catch-up burst). Frame times are taken at Present, before the wait, so the frame
 *             after a stall still shows its own work only (frame starts are paced, as with EnforceTickRate)
 *   loading   presents without a UGameEngine::Tick since the previous one (a map load's loading screen) are not
 *             paced, so the cap does not slow loads; pacing resumes after the load
 *   uncapped  without XRT_DEV_FPS_CAP no frame waits and the baton is never touched
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/fps_cap/run.cmd */
#include "../../../../tools/xrt/dev/dev_support.c"

/* ---- owned stubs for the runtime symbols dev_support.c uses */
volatile long xrt_exiting;
__declspec(thread) XrtThread* xrt_cur;
unsigned xrt_scene_level_renders, xrt_scene_camera_renders, xrt_scene_engine_ticks, xrt_scene_level_ticks;
static int baton_held = 1, baton_releases, baton_acquires, baton_misuse;
void xrt_baton_release(void) { if (!baton_held) baton_misuse++; baton_held = 0; baton_releases++; }
void xrt_baton_acquire(void) { if (baton_held) baton_misuse++; baton_held = 1; baton_acquires++; }
void xrt_baton_stats_log(FILE* also) { if (also) fprintf(also, "# baton test stub\n"); }
int xrt_thread_count(void) { return 0; }
XrtThread* xrt_thread_get(int i) { (void)i; return NULL; }
void xrt_log(const char* fmt, ...) { (void)fmt; }
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
void xm_checkpoint(CPU* c, const char* name) { (void)c; (void)name; }
void xrt_report_write(uint32_t exit_code, const char* outcome) { (void)exit_code; (void)outcome; }

static int failures;
#define CHECK(cond, ...) do { printf((cond) ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!(cond)) failures++; } while (0)

static double now_ms(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return (double)t.QuadPart * 1000.0 / (double)qpc_freq.QuadPart; }
static void work(double ms) { double end = now_ms() + ms; while (now_ms() < end) YieldProcessor(); }
/* Thread CPU time from QueryThreadCycleTime (GetThreadTimes has ~15.6 ms granularity), at a cycles-per-ms rate
 * calibrated by a timed spin. */
static double cycles_per_ms;
static double thread_cpu_ms(void) {
    ULONG64 cycles;
    QueryThreadCycleTime(GetCurrentThread(), &cycles);
    return (double)cycles / cycles_per_ms;
}
static void calibrate(void) {
    ULONG64 a, b; double t0;
    QueryThreadCycleTime(GetCurrentThread(), &a); t0 = now_ms();
    while (now_ms() < t0 + 300) YieldProcessor();
    QueryThreadCycleTime(GetCurrentThread(), &b);
    cycles_per_ms = (double)(b - a) / (now_ms() - t0);
}
static int cmp(const void* a, const void* b) { double x = *(const double*)a, y = *(const double*)b; return (x > y) - (x < y); }

typedef struct { double fps, median, min, cpu_share, work_share; unsigned waits, unwaited_after_stall; } Result;
/* frames: work pattern repeated; stall_at: frame index that works 100 ms instead (0: none). */
static Result run_case(unsigned cap, const double* pattern, unsigned npattern, unsigned frames, unsigned stall_at) {
    static double dt[4096];
    Result r = {0};
    double t0, c0, worked = 0;
    unsigned i, first = frame_count;
    cap_period = cap ? qpc_freq.QuadPart / cap : 0; cap_next = 0; cap_fps = cap;
    baton_releases = baton_acquires = 0;
    t0 = now_ms(); c0 = thread_cpu_ms();
    for (i = 0; i < frames; i++) {
        double w = i == stall_at && stall_at ? 100.0 : pattern[i % npattern];
        work(w); worked += w;
        xrt_scene_engine_ticks++;   /* one UGameEngine::Tick per frame, as in the main loop */
        xrt_dev_scene_present(NULL, 0, 1, 1, 0, 0, 0);
    }
    r.cpu_share = (thread_cpu_ms() - c0) / (now_ms() - t0);
    r.work_share = worked / (now_ms() - t0);
    for (i = first + 1; i < frame_count; i++) {
        dt[i - first - 1] = (double)(LONGLONG)(frame_rows[i].qpc - frame_rows[i - 1].qpc) * 1000.0 / (double)qpc_freq.QuadPart;
        if (frame_rows[i - 1].wait_us) r.waits++;
        else if (stall_at && i - 1 - first >= stall_at) r.unwaited_after_stall++;
    }
    r.fps = (frame_count - first - 1) * 1000.0 /
            ((double)(LONGLONG)(frame_rows[frame_count - 1].qpc - frame_rows[first].qpc) * 1000.0 / (double)qpc_freq.QuadPart);
    qsort(dt, frame_count - first - 1, sizeof dt[0], cmp);
    r.median = dt[(frame_count - first - 1) / 2]; r.min = dt[0];
    return r;
}

int main(void) {
    static const double two[] = {2.0}, six[] = {6.0}, twelve[] = {12.0}, mixed[] = {2.0, 12.0};
    static const unsigned caps[] = {60, 90, 120};
    char dir[MAX_PATH]; Result r; unsigned i;
    GetTempPathA(sizeof dir, dir);
    strcat(dir, "xrt-fps-cap-test");
    CreateDirectoryA(dir, NULL);
    SetEnvironmentVariableA("XRT_DEV_OUTPUT", dir);
    SetEnvironmentVariableA("XRT_DEV_SCENE", "100000");
    SetEnvironmentVariableA("XRT_DEV_FPS_CAP", "120");
    _putenv_s("XRT_DEV_OUTPUT", dir); _putenv_s("XRT_DEV_SCENE", "100000"); _putenv_s("XRT_DEV_FPS_CAP", "120");
    timeBeginPeriod(1);   /* as the runtime's scheduler ticker and the guest's Core do */
    CHECK(scene_mode(), "first-scene mode from XRT_DEV_SCENE");
    post_init = 1;
    perf_start(NULL);
    calibrate();
    CHECK(cap_fps == 120 && cap_period > 0 && cap_timer != NULL, "XRT_DEV_FPS_CAP=120 parsed; high-resolution waitable timer created");
    CHECK(thread_csv != NULL, "threads.csv opened in XRT_DEV_OUTPUT");
    for (i = 0; i < 3; i++) {
        unsigned frames = caps[i] * 3;
        r = run_case(caps[i], two, 1, frames, 0);
        printf("     cap %u, 2 ms frames: %.2f FPS, median %.3f ms, min %.3f, thread CPU %.1f%% of wall (work %.1f%%), waits %u/%u\n",
               caps[i], r.fps, r.median, r.min, 100 * r.cpu_share, 100 * r.work_share, r.waits, frames - 1);
        CHECK(fabs(r.fps - caps[i]) <= 0.01 * caps[i], "cap %u: achieved %.2f FPS within 1%%", caps[i], r.fps);
        CHECK(fabs(r.median - 1000.0 / caps[i]) <= 0.3, "cap %u: median frame %.3f ms = period +-0.3 ms", caps[i], r.median);
        CHECK(r.cpu_share - r.work_share < 0.02, "cap %u: no spin (CPU %.1f%% vs work %.1f%%)", caps[i], 100 * r.cpu_share, 100 * r.work_share);
        CHECK(baton_releases == baton_acquires && baton_releases >= (int)frames - 2 && !baton_misuse && baton_held,
              "cap %u: baton released/re-acquired around every wait (%d/%d, misuse %d)", caps[i], baton_releases, baton_acquires, baton_misuse);
    }
    r = run_case(120, six, 1, 360, 0);
    printf("     cap 120, 6 ms frames: %.2f FPS, median %.3f ms, CPU %.1f%% (work %.1f%%)\n", r.fps, r.median, 100 * r.cpu_share, 100 * r.work_share);
    CHECK(fabs(r.fps - 120) <= 1.2 && r.cpu_share - r.work_share < 0.02, "cap 120 with 6 ms frames: %.2f FPS, no spin", r.fps);
    r = run_case(120, twelve, 1, 200, 0);
    printf("     cap 120, 12 ms frames: %.2f FPS, median %.3f ms, waits %u\n", r.fps, r.median, r.waits);
    CHECK(r.waits == 0 && r.fps > 80 && r.fps < 84, "overrun: 12 ms frames are never waited for (%.2f FPS, %u waits)", r.fps, r.waits);
    r = run_case(120, mixed, 2, 360, 0);
    printf("     cap 120, alternating 2/12 ms: %.2f FPS, median %.3f ms\n", r.fps, r.median);
    CHECK(fabs(r.fps - 120) <= 1.2, "phase: alternating 2/12 ms frames average %.2f FPS (cap 120)", r.fps);
    r = run_case(60, two, 1, 180, 60);
    printf("     cap 60, 2 ms frames with a 100 ms stall: %.2f FPS, unwaited frames from the stall on %u\n", r.fps, r.unwaited_after_stall);
    CHECK(r.unwaited_after_stall == 1, "stall: re-anchored, only the stalled frame is unwaited (%u), no catch-up burst", r.unwaited_after_stall);
    {   /* loading: 500 loading-screen presents inside one engine tick are not paced; pacing resumes afterwards */
        unsigned first = frame_count, waited = 0, unwaited_after = 0; double t0;
        r = run_case(120, two, 1, 30, 0);
        t0 = now_ms();
        xrt_scene_engine_ticks++;
        for (i = 0; i < 500; i++) { work(0.2); xrt_dev_scene_present(NULL, 0, 1, 1, 0, 0, 0); }
        printf("     cap 120, 500 loading presents in one engine tick: %.1f ms\n", now_ms() - t0);
        for (i = first + 30; i < frame_count; i++) if (frame_rows[i].wait_us) waited++;
        CHECK(waited <= 1 && now_ms() - t0 < 500 * 0.2 + 50, "loading: at most the tick's first present waits (%u of 500)", waited);
        first = frame_count;
        r = run_case(120, two, 1, 120, 0);
        for (i = first + 1; i < frame_count - 1; i++) if (!frame_rows[i].wait_us) unwaited_after++;
        CHECK(fabs(r.fps - 120) <= 1.2 && unwaited_after == 0, "after the load pacing resumes at %.2f FPS (%u unwaited)", r.fps, unwaited_after);
    }
    _putenv_s("XRT_DEV_FPS_CAP", "");
    perf_start(NULL);
    CHECK(cap_fps == 0, "XRT_DEV_FPS_CAP unset: limiter off");
    r = run_case(0, two, 1, 300, 0);
    printf("     uncapped, 2 ms frames: %.2f FPS\n", r.fps);
    CHECK(r.waits == 0 && baton_releases == 0 && r.fps > 400, "uncapped: no waits, baton untouched (%.1f FPS)", r.fps);
    printf(failures ? "FAILED %d\n" : "PASS\n", failures);
    return failures != 0;
}

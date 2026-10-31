/* Developer diagnostics only. Never linked into the strict candidate. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
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
static int scene_mode(void) {
    if (scene < 0) {
        const char *v = getenv("XRT_DEV_SCENE");
        scene = v && *v;
        scene_limit = scene ? (unsigned)strtoul(v, NULL, 10) : 0;
        if (scene && (scene_limit < 1 || scene_limit > 100000)) scene_limit = 60;
    }
    return scene;
}
static int scene_capture_frame(unsigned n) { return (n & (n - 1)) == 0 || n == scene_limit; }
int xrt_dev_scene_capture(unsigned level_renders, unsigned scene_draws) {
    if (!scene_mode() || !post_init || level_renders == last_renders || !scene_draws) return 0;
    return scene_capture_frame(world_frames + 1) ? (int)(world_frames + 1) : 0;
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
    snprintf(path, sizeof path, "%s\\scene-frame-%04u.bmp", root, frame);
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
    if (world) world_frames++;
    if (post_presents <= 32 || (world && scene_capture_frame(world_frames)) || !(post_presents % 64))
        xrt_log("DEV post-Init present %u at +%llu ms hr=%08lx draws=%u prims=%u level_renders=%u scene_draws=%u "
                "scene_prims=%u level_draws=%u engine_ticks=%u level_ticks=%u world_frame=%u",
                post_presents, GetTickCount64() - init_ms, (unsigned long)hr, draws, prims, renders, scene_draws,
                scene_prims, level_draws, engine, level, world ? world_frames : 0);
    if (world && world_frames == scene_limit) {
        xrt_event("dev_scene_present", "\"world_frames\":%u,\"presents\":%u,\"scene_draws\":%u,\"scene_prims\":%u",
                  world_frames, post_presents, scene_draws, scene_prims);
        xm_checkpoint(c, "dev.scene.present");
        xrt_report_write(11, "developer first-scene stop after bounded world frames");
        fprintf(stderr, "dev: FIRST_SCENE endpoint reached after %u world frames (%u post-Init presents)\n",
                world_frames, post_presents);
        fflush(NULL);
        ExitProcess(11);
    }
}
__declspec(noinline) void xrt_dev_init_return(CPU *c) {
    xrt_log("DEV Init returned: caller=1090ed59 return=%08x esp=%08x", c->rv, c->r[ESP]);
    xrt_event("dev_init_return", "\"guest_next\": \"0x1090ed5c\"");
    xm_checkpoint(c, "dev.Init.return");
    if (scene_mode()) {
        /* Continue into the normal post-Init caller; counters start here. */
        post_init = 1; init_ms = GetTickCount64();
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

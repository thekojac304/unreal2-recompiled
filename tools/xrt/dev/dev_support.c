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
static __declspec(noreturn) void scene_stop(CPU *c, const char *why) {
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

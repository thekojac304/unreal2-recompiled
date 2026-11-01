/* openal_bridge - focused test of the developer runtime's OpenAL 1.0 adapter (out/dev-init/runtime/hle_openal.c), the
 * host implementation that stands in for the game's DefOpenAL32.dll under the translated ALAudio.dll.
 *
 * Every entry point is called through a guest stack (cdecl, arguments and result pointers in guest memory) exactly as
 * translated code calls an import stub. XAudio2 runs for real with the mastering voice muted (XRT_DEV_SOUND=muted);
 * mixed output is observed through the adapter's openal_mix events (an XAudio2 volume meter on the mastering voice).
 *   errors      invalid names/enums/values/operations set the OpenAL error codes; nothing else changes
 *   lifetime    buffer data is copied at alBufferData; a queued buffer cannot be deleted or refilled
 *   state       INITIAL -> PLAYING -> STOPPED by itself; PAUSED holds; Play resumes; Stop/Rewind
 *   queue       streaming: processed counts advance as XAudio2 finishes buffers; unqueue/refill/queue; starvation
 *   looping     a looping source keeps playing and reports no processed buffers; clearing AL_LOOPING ends it
 *   mix         a playing tone is audible in the mix (peak > 0); full-right pan puts it in the right channel only;
 *               inverse-distance-clamped attenuation at 100 m with rolloff 1 is ~1/100 of the near level
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/openal_bridge/run.cmd (about 25 s). */
#include <windows.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xrt_internal.h"

__declspec(thread) XrtThread* xrt_cur;
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list a; (void)c; va_start(a, fmt); fprintf(stderr, "xrt_fatal %d: ", code); vfprintf(stderr, fmt, a); va_end(a);
    fputc('\n', stderr); exit(2);
}
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) { (void)a; (void)size; (void)end; return 0; }
void xrt_log(const char* fmt, ...) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); }
const char* xrt_jstr(char* out, size_t n, const char* s) { snprintf(out, n, "\"%s\"", s); return out; }
static char last_mix[512], last_close[512];
static int nplay;
void xrt_event(const char* kind, const char* fmt, ...) {
    char body[512] = "";
    va_list a;
    if (fmt) { va_start(a, fmt); vsnprintf(body, sizeof body, fmt, a); va_end(a); }
    if (!strcmp(kind, "openal_mix")) strcpy(last_mix, body);
    else if (!strcmp(kind, "openal_close")) strcpy(last_close, body);
    else if (!strcmp(kind, "openal_play")) nplay++;
    else printf("     event %s {%s}\n", kind, body);
}
uint32_t xrt_hle_proc(const char* dll, const char* name) { (void)dll; (void)name; return 0x00300010u; }
extern const XrtHle xrt_hle_openal[];

static int failures;
#define CHECK(cond, what) do { if (!(cond)) { printf("FAIL %s\n", what); failures++; } else printf("ok   %s\n", what); } while (0)

/* ---- guest-call plumbing: [esp] = return address, arguments above it (cdecl: the caller pops them) */
#define STACK 0x00900000u
#define SCRATCH 0x00a00000u
#define RET_SITE 0x0040abcdu
static CPU cpu;
static XrtFn fn(const char* name) {
    const XrtHle* h;
    for (h = xrt_hle_openal; h->dll; h++) if (!strcmp(h->name, name)) return h->fn;
    fprintf(stderr, "no adapter %s\n", name); exit(2);
}
static uint32_t callv(const char* name, int n, const uint32_t* args) {
    int i;
    uint32_t esp = STACK - 0x100;
    wr32(esp, RET_SITE);
    for (i = 0; i < n; i++) wr32(esp + 4 + 4 * i, args[i]);
    cpu.r[ESP] = esp; cpu.r[EAX] = 0xDEADBEEFu; cpu.rv = 0;
    fn(name)(&cpu);
    if (cpu.rv != RET_SITE || cpu.r[ESP] != esp + 4) { printf("FAIL %s: cdecl return (rv %08x, esp %+d)\n", name, cpu.rv, (int)(cpu.r[ESP] - esp)); failures++; }
    return cpu.r[EAX];
}
#define ACALL(name, ...) callv(name, (int)(sizeof((uint32_t[]){__VA_ARGS__}) / 4), (uint32_t[]){__VA_ARGS__})
#define ACALL0(name) callv(name, 0, NULL)
static uint32_t fbits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static uint32_t err(void) { return ACALL0("alGetError"); }
static uint32_t geti(uint32_t src, uint32_t param) { wr32(SCRATCH, 0xFFFFFFFFu); ACALL("alGetSourcei", src, param, SCRATCH); return rd32(SCRATCH); }
static uint32_t state(uint32_t src) { return geti(src, 0x1010); }
static uint32_t ctx_va;
static void pump(int ms) { DWORD t0 = GetTickCount(); while ((int)(GetTickCount() - t0) < ms) { ACALL("alcProcessContext", ctx_va); Sleep(10); } }
/* One meter window fully inside the current condition: let the running window close, then measure a new one. */
static void mix_window(float* l, float* r) {
    last_mix[0] = 0; pump(2150); last_mix[0] = 0;
    while (!last_mix[0]) pump(50);
    *l = *r = -1.0f;
    sscanf(strstr(last_mix, "\"peak\": [") + 9, "%f, %f", l, r);
    printf("     mix %s\n", last_mix);
}
/* A tone of `seconds` at 22050 Hz, mono 16-bit, written into guest memory at p; returns its byte size. */
static uint32_t tone(uint32_t p, double seconds, double amplitude) {
    uint32_t n = (uint32_t)(seconds * 22050), i;
    for (i = 0; i < n; i++) wr16(p + 2 * i, (uint16_t)(int16_t)lrint(amplitude * 32767.0 * sin(2 * 3.14159265358979 * 440.0 * i / 22050.0)));
    return 2 * n;
}

int main(void) {
    uint32_t dev, ctx, src[4], buf[6], data = 0x00b00000u, size, i, q[4];
    float l, r, l2, r2;
    _putenv("XRT_DEV_SOUND=muted");
    xrt_mem_init();
    xrt_commit(STACK - 0x10000, 0x10000);
    xrt_commit(SCRATCH, 0x1000);
    xrt_commit(data, 0x200000);
    strcpy((char*)G2H(SCRATCH + 0x800), "DirectSound3D");
    strcpy((char*)G2H(SCRATCH + 0x900), "EAX3.0");

    dev = ACALL("alcOpenDevice", SCRATCH + 0x800);
    CHECK(dev != 0, "alcOpenDevice(\"DirectSound3D\") opens the XAudio2 device");
    if (!dev) return 1;
    CHECK(ACALL("alcCreateContext", 0x12345678u, 0) == 0 && ACALL0("alcGetError") == 0xA001, "alcCreateContext on a foreign device: ALC_INVALID_DEVICE");
    ctx = ctx_va = ACALL("alcCreateContext", dev, 0);
    CHECK(ctx != 0 && ACALL("alcMakeContextCurrent", ctx) == 1 && err() == 0, "context created and current, no AL error");
    CHECK((ACALL("alIsExtensionPresent", SCRATCH + 0x900) & 0xFF) == 0, "EAX3.0 is not present (ALAudio then skips EAX)");
    CHECK(rd8(ACALL("alGetString", 0xB004)) == 0 && err() == 0, "AL_EXTENSIONS is an empty guest string");
    ACALL("alDistanceModel", 0xD002);
    ACALL("alGenSources", 4, SCRATCH);
    for (i = 0; i < 4; i++) src[i] = rd32(SCRATCH + 4 * i);
    ACALL("alGenBuffers", 6, SCRATCH);
    for (i = 0; i < 6; i++) buf[i] = rd32(SCRATCH + 4 * i);
    CHECK(err() == 0 && src[0] && src[3] != src[0] && buf[0] && buf[5] != buf[0], "alGenSources(4) / alGenBuffers(6) give distinct names");
    CHECK(ACALL("alIsSource", src[1]) == 1 && ACALL("alIsSource", 77777) == 0 && ACALL("alIsBuffer", buf[2]) == 1, "alIsSource / alIsBuffer");

    /* errors */
    ACALL("alSourcei", 77777, 0x1009, buf[0]); CHECK(err() == 0xA001, "alSourcei on an unknown source: AL_INVALID_NAME");
    ACALL("alSourcef", src[0], 0x1003, fbits(0.0f)); CHECK(err() == 0xA003, "AL_PITCH 0: AL_INVALID_VALUE");
    ACALL("alSourcei", src[0], 0x9999, 1); CHECK(err() == 0xA002, "unknown source parameter: AL_INVALID_ENUM");
    ACALL("alBufferData", buf[0], 0x1234, data, 64, 22050); CHECK(err() == 0xA002, "unknown buffer format: AL_INVALID_ENUM");
    ACALL("alBufferData", buf[0], 0x1101, 0x7ff00000u, 64, 22050); CHECK(err() == 0xA003, "data pointer outside committed guest memory: AL_INVALID_VALUE");
    ACALL("alSourcei", src[0], 0x1009, 4242); CHECK(err() == 0xA003, "AL_BUFFER with an unknown buffer: AL_INVALID_VALUE");
    ACALL("alGetSourcei", src[0], 0x1010, 0x7ff00000u); CHECK(err() == 0xA003, "result pointer outside guest memory: AL_INVALID_VALUE");
    CHECK(err() == 0, "alGetError clears the error");
    CHECK(state(src[0]) == 0x1011, "a new source is AL_INITIAL");

    /* lifetime and state machine */
    size = tone(data, 0.30, 0.5);
    ACALL("alBufferData", buf[0], 0x1101, data, size, 22050);
    memset(G2H(data), 0, size);   /* the adapter copied the samples: the guest may reuse its memory */
    ACALL("alGetBufferi", buf[0], 0x2004, SCRATCH);
    CHECK(err() == 0 && rd32(SCRATCH) == size, "alBufferData copies the PCM (AL_SIZE)");
    ACALL("alBufferData", buf[1], 0x1101, data, 33, 22050);
    ACALL("alGetBufferi", buf[1], 0x2004, SCRATCH);
    CHECK(err() == 0 && rd32(SCRATCH) == 32, "a trailing partial frame is dropped (33 -> 32 bytes)");
    ACALL("alSourcei", src[0], 0x1009, buf[0]);
    ACALL("alSourcePlay", src[0]);
    CHECK(err() == 0 && state(src[0]) == 0x1012, "alSourcePlay: AL_PLAYING");
    ACALL("alDeleteBuffers", 1, (wr32(SCRATCH, buf[0]), SCRATCH)); CHECK(err() == 0xA004, "deleting a buffer attached to a source: AL_INVALID_OPERATION");
    ACALL("alBufferData", buf[0], 0x1101, data, size, 22050); CHECK(err() == 0xA004, "refilling an attached buffer: AL_INVALID_OPERATION");
    ACALL("alSourcei", src[0], 0x1009, 0); CHECK(err() == 0xA004, "AL_BUFFER on a playing source: AL_INVALID_OPERATION");
    Sleep(500);
    CHECK(state(src[0]) == 0x1014 && geti(src[0], 0x1016) == 1, "the 0.3 s sound stops by itself: AL_STOPPED, 1 processed");
    ACALL("alSourceRewind", src[0]); CHECK(state(src[0]) == 0x1011, "alSourceRewind: AL_INITIAL");
    ACALL("alSourcei", src[0], 0x1009, 0);
    wr32(SCRATCH, buf[0]); ACALL("alDeleteBuffers", 1, SCRATCH);
    CHECK(err() == 0 && ACALL("alIsBuffer", buf[0]) == 0, "detached buffer deleted; its name stays invalid");

    size = tone(data, 1.0, 0.5);
    ACALL("alBufferData", buf[2], 0x1101, data, size, 22050);
    ACALL("alSourcei", src[1], 0x1009, buf[2]);
    ACALL("alSourcePlay", src[1]); Sleep(200);
    ACALL("alSourcePause", src[1]); CHECK(state(src[1]) == 0x1013, "alSourcePause: AL_PAUSED");
    Sleep(1200); CHECK(state(src[1]) == 0x1013, "a paused source stays paused (1.2 s > its length)");
    ACALL("alSourcePlay", src[1]); CHECK(state(src[1]) == 0x1012, "alSourcePlay resumes: AL_PLAYING");
    Sleep(450); CHECK(state(src[1]) == 0x1012, "resumed from its position (still playing 0.45 s later)");
    Sleep(700); CHECK(state(src[1]) == 0x1014, "then it finishes: AL_STOPPED");

    /* streaming queue */
    for (i = 3; i < 6; i++) ACALL("alBufferData", buf[i], 0x1101, data, tone(data, 0.10, 0.3), 22050);
    ACALL("alBufferData", buf[1], 0x1103, data, 4096, 22050);   /* stereo: a different format */
    wr32(SCRATCH, buf[3]); wr32(SCRATCH + 4, buf[4]);
    ACALL("alSourceQueueBuffers", src[2], 2, SCRATCH);
    CHECK(err() == 0 && geti(src[2], 0x1015) == 2 && geti(src[2], 0x1016) == 0, "two buffers queued, none processed");
    wr32(SCRATCH, buf[1]); ACALL("alSourceQueueBuffers", src[2], 1, SCRATCH); CHECK(err() == 0xA004, "queueing a different format: AL_INVALID_OPERATION");
    ACALL("alSourcePlay", src[2]);
    Sleep(160);
    CHECK(geti(src[2], 0x1016) == 1 && state(src[2]) == 0x1012, "after 0.16 s: 1 processed, still playing");
    ACALL("alSourceUnqueueBuffers", src[2], 2, SCRATCH); CHECK(err() == 0xA003, "unqueueing more than processed: AL_INVALID_VALUE");
    ACALL("alSourceUnqueueBuffers", src[2], 1, SCRATCH);
    CHECK(err() == 0 && rd32(SCRATCH) == buf[3] && geti(src[2], 0x1015) == 1, "unqueue returns the oldest buffer");
    ACALL("alBufferData", buf[3], 0x1101, data, tone(data, 0.10, 0.3), 22050);
    CHECK(err() == 0, "the unqueued buffer can be refilled");
    wr32(SCRATCH, buf[3]); wr32(SCRATCH + 4, buf[5]);
    ACALL("alSourceQueueBuffers", src[2], 2, SCRATCH);
    CHECK(err() == 0 && geti(src[2], 0x1015) == 3, "queued while playing (3 queued)");
    Sleep(500);
    CHECK(state(src[2]) == 0x1014 && geti(src[2], 0x1016) == 3, "the stream drains: AL_STOPPED, all 3 processed");
    ACALL("alSourceUnqueueBuffers", src[2], 3, SCRATCH);
    CHECK(err() == 0 && geti(src[2], 0x1015) == 0, "all unqueued after the stop");

    /* looping */
    ACALL("alBufferData", buf[4], 0x1101, data, tone(data, 0.10, 0.3), 22050);
    ACALL("alSourcei", src[3], 0x1009, buf[4]);
    ACALL("alSourcei", src[3], 0x1007, 1);
    ACALL("alSourcePlay", src[3]);
    Sleep(600);
    CHECK(state(src[3]) == 0x1012 && geti(src[3], 0x1016) == 0, "a looping 0.1 s sound plays on after 0.6 s, none processed");
    ACALL("alSourcei", src[3], 0x1007, 0);
    Sleep(300);
    CHECK(state(src[3]) == 0x1014, "AL_LOOPING 0: it ends after the current pass");

    /* voice reuse race (launch 5: ALAudio saw just-started ambient sources as AL_STOPPED and replayed them every
     * frame): stop and immediately replay on alternating sources sharing one format; each must stay AL_PLAYING */
    {
        int bad = 0, n;
        ACALL("alSourcei", src[3], 0x1009, 0);
        ACALL("alBufferData", buf[4], 0x1101, data, tone(data, 0.5, 0.2), 22050);
        ACALL("alSourcei", src[0], 0x1009, buf[4]); ACALL("alSourcei", src[3], 0x1009, buf[4]);
        ACALL("alSourcei", src[0], 0x1007, 1); ACALL("alSourcei", src[3], 0x1007, 1);
        for (n = 0; n < 300; n++) {
            uint32_t a = n & 1 ? src[0] : src[3], b = n & 1 ? src[3] : src[0];
            ACALL("alSourceStop", b);
            ACALL("alSourcePlay", a);
            if (state(a) != 0x1012) bad++;
            if (n % 3 == 0) Sleep(1);
            if (state(a) != 0x1012) bad++;
        }
        printf("     reuse churn: %d non-playing reports in 600 queries\n", bad);
        CHECK(bad == 0 && err() == 0, "stop/replay churn on reused voices: a started looping source always reports AL_PLAYING");
        ACALL("alSourceStop", src[0]); ACALL("alSourceStop", src[3]);
        ACALL("alSourcei", src[0], 0x1009, 0); ACALL("alSourcei", src[3], 0x1009, 0);
        ACALL("alSourcei", src[0], 0x1007, 0);
    }

    /* mix: centre, full right, far */
    size = tone(data, 1.0, 0.5);
    ACALL("alSourcei", src[1], 0x1009, 0);   /* detach before refilling */
    ACALL("alBufferData", buf[2], 0x1101, data, size, 22050);
    ACALL("alSourcei", src[1], 0x1009, buf[2]);
    ACALL("alSourcei", src[1], 0x1007, 1);
    CHECK(err() == 0, "refill after detaching, attach, loop");
    ACALL("alSourcei", src[1], 0x202, 1);
    wr32(SCRATCH, fbits(0)); wr32(SCRATCH + 4, fbits(0)); wr32(SCRATCH + 8, fbits(-1.0f));
    ACALL("alSourcefv", src[1], 0x1004, SCRATCH);
    ACALL("alSourcePlay", src[1]);
    ACALL("alcSuspendContext", ctx);
    mix_window(&l, &r);
    CHECK(l > 0.2f && r > 0.2f && fabsf(l - r) < 0.02f, "a centred tone is in both channels of the mix (0.5 * 0.707)");
    wr32(SCRATCH, fbits(10.0f)); wr32(SCRATCH + 4, fbits(0)); wr32(SCRATCH + 8, fbits(0));
    ACALL("alSourcefv", src[1], 0x1004, SCRATCH);   /* suspended: committed at the next alcProcessContext */
    mix_window(&l2, &r2);
    CHECK(fabsf(r2 - 0.05f) < 0.003f && l2 < 0.001f, "10 m to the right: right channel only (pan), 0.5 * 1/10 (inverse distance clamped)");
    wr32(SCRATCH, fbits(0)); wr32(SCRATCH + 4, fbits(0)); wr32(SCRATCH + 8, fbits(-100.0f));
    ACALL("alSourcefv", src[1], 0x1004, SCRATCH);
    mix_window(&l2, &r2);
    CHECK(l2 > 0.0f && fabsf(l2 / l - 0.01f) < 0.003f, "100 m away (ref 1, rolloff 1): about 1/100 of the near level");
    ACALL("alSourceStop", src[1]);
    CHECK(state(src[1]) == 0x1014 && geti(src[1], 0x1016) == 1, "alSourceStop: AL_STOPPED, the queue processed");
    mix_window(&l2, &r2);
    CHECK(l2 == 0.0f && r2 == 0.0f, "nothing playing: the mix is silent");

    /* teardown */
    wr32(SCRATCH, src[0]); wr32(SCRATCH + 4, src[1]); wr32(SCRATCH + 8, src[2]); wr32(SCRATCH + 12, src[3]);
    ACALL("alDeleteSources", 4, SCRATCH);
    CHECK(err() == 0 && ACALL("alIsSource", src[2]) == 0, "sources deleted");
    CHECK(ACALL("alcDestroyContext", ctx) == 0 && ACALL("alcCloseDevice", dev) == 1, "context destroyed, device closed");
    printf("     close {%s}\n", last_close);
    CHECK(nplay == 256 && strstr(last_close, "\"plays\": 305,") && strstr(last_close, "\"refused\": 0"), "305 plays (first 256 as events), no voice refused");
    (void)q;
    printf("%s: %d failure(s)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}

/* openal_churn - measures what the ALAudio ambient churn costs in the developer runtime's OpenAL adapter
 * (out/dev-init/runtime/hle_openal.c on XAudio2, mastering voice muted).
 *
 * The churn (runs 20261101-191912/-192029: ~1160 plays/s, stop of a playing source each time): in UALAudioSubsystem::
 * Update the ambient stop pass compares the listener distance with the radius PlaySound stored in the source - reduced
 * by the occlusion factor when the line of sight is blocked - while the start pass compares it with the actor's full
 * SoundRadius. An occluded ambient sound inside its full radius is therefore stopped and played again every frame
 * (original engine logic; the translation reproduces it).
 *
 * Pattern here: 13 looping sources (2 s mono 22050 Hz buffers, 3D, at 40 m with reference distance 8) are stopped and
 * played again in each of 900 "frames" at about 90 per second (10 s), with alcProcessContext between frames, then the
 * same 10 s with the sources simply left playing. Reports process CPU time (all threads: game thread adapter calls
 * and XAudio2's own threads) per second and per stop/play pair. Also checks the restarted sources keep reporting
 * AL_PLAYING. Informational: exit 0 unless the adapter fails. Build/run: experiments/xrt/tests/openal_churn/run.cmd */
#define main bridge_main
#include "../openal_bridge/test.c"
#undef main

static double cpu_seconds(void) {
    FILETIME c, e, k, u;
    GetProcessTimes(GetCurrentProcess(), &c, &e, &k, &u);
    return ((((ULONGLONG)k.dwHighDateTime << 32) | k.dwLowDateTime) + (((ULONGLONG)u.dwHighDateTime << 32) | u.dwLowDateTime)) / 1e7;
}

int main(void) {
    enum { N = 13, FRAMES = 900 };
    uint32_t dev, ctx, src[N], buf[N], data = 0x00b00000u, size, i, f, playing;
    double t0, w0, churn_cpu, idle_cpu, churn_wall, idle_wall;
    LARGE_INTEGER q, freq;
    _putenv("XRT_DEV_SOUND=muted");
    xrt_mem_init();
    xrt_commit(STACK - 0x10000, 0x10000);
    xrt_commit(SCRATCH, 0x1000);
    xrt_commit(data, 0x200000);
    strcpy((char*)G2H(SCRATCH + 0x800), "DirectSound3D");
    dev = ACALL("alcOpenDevice", SCRATCH + 0x800);
    if (!dev) { printf("FAIL no device\n"); return 1; }
    ctx = ctx_va = ACALL("alcCreateContext", dev, 0);
    ACALL("alcMakeContextCurrent", ctx);
    ACALL("alDistanceModel", 0xD002);
    ACALL("alGenSources", N, SCRATCH);
    for (i = 0; i < N; i++) src[i] = rd32(SCRATCH + 4 * i);
    ACALL("alGenBuffers", N, SCRATCH);
    for (i = 0; i < N; i++) buf[i] = rd32(SCRATCH + 4 * i);
    size = tone(data, 2.0, 0.3);
    for (i = 0; i < N; i++) {
        ACALL("alBufferData", buf[i], 0x1101, data, size, 22050);
        ACALL("alSourcei", src[i], 0x1009, buf[i]);
        ACALL("alSourcei", src[i], 0x1007, 1);                       /* AL_LOOPING */
        wrf32(SCRATCH, 40.0f); wrf32(SCRATCH + 4, 0); wrf32(SCRATCH + 8, 0);
        ACALL("alSourcefv", src[i], 0x1004, SCRATCH);                 /* AL_POSITION */
        ACALL("alSourcef", src[i], 0x1020, fbits(8.0f));              /* AL_REFERENCE_DISTANCE */
        ACALL("alSourcePlay", src[i]);
    }
    CHECK(err() == 0, "13 looping 3D sources playing");
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&q); w0 = (double)q.QuadPart / freq.QuadPart; t0 = cpu_seconds();
    for (f = 0; f < FRAMES; f++) {
        for (i = 0; i < N; i++) { ACALL("alSourceStop", src[i]); ACALL("alSourcePlay", src[i]); }
        ACALL("alcProcessContext", ctx);
        Sleep(11);
    }
    churn_cpu = cpu_seconds() - t0; QueryPerformanceCounter(&q); churn_wall = (double)q.QuadPart / freq.QuadPart - w0;
    for (i = 0, playing = 0; i < N; i++) playing += state(src[i]) == 0x1012;
    CHECK(err() == 0 && playing == N, "after 11700 stop/play pairs every source is AL_PLAYING");
    QueryPerformanceCounter(&q); w0 = (double)q.QuadPart / freq.QuadPart; t0 = cpu_seconds();
    for (f = 0; f < FRAMES; f++) { ACALL("alcProcessContext", ctx); Sleep(11); }
    idle_cpu = cpu_seconds() - t0; QueryPerformanceCounter(&q); idle_wall = (double)q.QuadPart / freq.QuadPart - w0;
    printf("     churn: %u stop/play pairs in %.2f s wall, process CPU %.3f s (%.1f%% of one core)\n",
           N * FRAMES, churn_wall, churn_cpu, 100.0 * churn_cpu / churn_wall);
    printf("     steady: same sources playing, %.2f s wall, process CPU %.3f s (%.1f%% of one core)\n",
           idle_wall, idle_cpu, 100.0 * idle_cpu / idle_wall);
    printf("     extra cost of the churn: %.1f us of CPU per stop/play pair, %.1f%% of one core at %.0f pairs/s\n",
           1e6 * (churn_cpu - idle_cpu * churn_wall / idle_wall) / (N * FRAMES),
           100.0 * (churn_cpu / churn_wall - idle_cpu / idle_wall), N * FRAMES / churn_wall);
    printf("     adapter play events: %d\n", nplay);
    printf("%s (%d failure%s)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

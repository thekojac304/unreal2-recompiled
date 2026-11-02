/* Cache/footprint sweep (round 3 of the performance work, owned code only): how the cost of data accesses and of
 * instruction fetch grows with the working set on one logical CPU. Run it pinned to a core of each CCD of the
 * 9950X3D (96 MB L3 with V-cache vs 32 MB) to see where the two dies diverge, and compare with the game's measured
 * footprints. No game code or data is involved.
 *   cache_sweep.exe LP            (LP = logical processor to pin to)
 *   cache_sweep.exe pollute LP MB SECONDS   (L3 occupancy load beside a pinned program; see pollute())
 * clock:  a chain of dependent 64-bit adds (1 cycle each) -> effective core clock in GHz
 * data:   pointer chase over a random cyclic permutation of 64-byte lines in an N-byte buffer -> ns per load
 * code:   N/256 copies of a 256-byte block of independent adds + ret in executable memory, called in a random order
 *         through a pointer table -> ns per call (each call fetches 4 new cache lines) */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static double now_s(void) {
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f); QueryPerformanceCounter(&t);
    return (double)t.QuadPart / (double)f.QuadPart;
}
static uint64_t rng = 0x9e3779b97f4a7c15ull;
static uint64_t next_rand(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; }

static double clock_ghz(void) {
    volatile uint64_t seed = 1;
    uint64_t x = seed, n = 400000000ull, i;
    double t = now_s();
    for (i = 0; i < n; i++) { x += i; x ^= seed; }   /* two dependent ALU ops per iteration (add, xor) */
    t = now_s() - t;
    if (x == 42) puts("");
    return 2.0 * (double)n / t / 1e9;
}

static double data_ns(size_t bytes) {
    size_t lines = bytes / 64, i, j, steps;
    uint32_t *perm = malloc(lines * sizeof *perm);
    char *buf = VirtualAlloc(NULL, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    void **p; double t;
    for (i = 0; i < lines; i++) perm[i] = (uint32_t)i;
    for (i = lines - 1; i > 0; i--) { j = next_rand() % (i + 1); uint32_t s = perm[i]; perm[i] = perm[j]; perm[j] = s; }
    for (i = 0; i < lines; i++) *(void **)(buf + (size_t)perm[i] * 64) = buf + (size_t)perm[(i + 1) % lines] * 64;
    p = (void **)(buf + (size_t)perm[0] * 64);
    for (i = 0; i < lines; i++) p = *p;                       /* warm: one full lap */
    steps = lines * 4 > 20000000 ? lines * 4 : 20000000;
    t = now_s();
    for (i = 0; i < steps; i++) p = *p;
    t = now_s() - t;
    if (!p) puts("");
    VirtualFree(buf, 0, MEM_RELEASE); free(perm);
    return t * 1e9 / (double)steps;
}

static double code_ns(size_t bytes) {
    static const unsigned char adds[7][4] = {{0x48, 0x83, 0xc0, 1}, {0x48, 0x83, 0xc1, 1}, {0x48, 0x83, 0xc2, 1},
                                             {0x49, 0x83, 0xc0, 1}, {0x49, 0x83, 0xc1, 1}, {0x49, 0x83, 0xc2, 1},
                                             {0x49, 0x83, 0xc3, 1}};
    size_t blocks = bytes / 256, i, j, calls;
    unsigned char *code = VirtualAlloc(NULL, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE), *b;
    void (**table)(void) = malloc(blocks * sizeof *table);
    DWORD old; double t;
    for (i = 0; i < blocks; i++) {
        b = code + i * 256;
        for (j = 0; j < 63; j++) memcpy(b + 4 * j, adds[j % 7], 4);
        b[252] = 0xc3; b[253] = b[254] = b[255] = 0xcc;
    }
    VirtualProtect(code, bytes, PAGE_EXECUTE_READ, &old);
    FlushInstructionCache(GetCurrentProcess(), code, bytes);
    for (i = 0; i < blocks; i++) table[i] = (void (*)(void))(code + i * 256);
    for (i = blocks - 1; i > 0; i--) { j = next_rand() % (i + 1); void (*s)(void) = table[i]; table[i] = table[j]; table[j] = s; }
    for (i = 0; i < blocks; i++) table[i]();                  /* warm */
    calls = blocks * 4 > 4000000 ? blocks * 4 : 4000000;
    t = now_s();
    for (i = 0; i < calls; i++) table[i % blocks]();
    t = now_s() - t;
    VirtualFree(code, 0, MEM_RELEASE); free(table);
    return t * 1e9 / (double)calls;
}

/* "pollute LP MB SECONDS": keep an MB-sized random pointer chase running on LP for SECONDS (or until the file
 * pollute.stop appears beside the exe), so its lines stay recently used in the L3 of LP's die. Run beside a program
 * pinned to other cores of the same die, it lowers that program's effective L3 share at the same clock and die. */
static int pollute(size_t mb, unsigned seconds) {
    size_t lines = mb * 1024 * 1024 / 64, i, j, laps = 0;
    uint32_t *perm = malloc(lines * sizeof *perm);
    char *buf = VirtualAlloc(NULL, mb * 1024 * 1024, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    void **p; double t0 = now_s(), t;
    for (i = 0; i < lines; i++) perm[i] = (uint32_t)i;
    for (i = lines - 1; i > 0; i--) { j = next_rand() % (i + 1); uint32_t s = perm[i]; perm[i] = perm[j]; perm[j] = s; }
    for (i = 0; i < lines; i++) *(void **)(buf + (size_t)perm[i] * 64) = buf + (size_t)perm[(i + 1) % lines] * 64;
    free(perm);
    p = (void **)buf;
    for (;;) {
        for (i = 0; i < lines; i++) p = *p;
        laps++;
        t = now_s() - t0;
        if (t >= seconds || GetFileAttributesA("pollute.stop") != INVALID_FILE_ATTRIBUTES) break;
    }
    printf("polluted %zu MB for %.1f s: %zu laps, %.2f ns per load\n", mb, t, laps, t * 1e9 / ((double)laps * lines));
    return p == NULL;
}

int main(int argc, char **argv) {
    static const size_t kb[] = {16, 64, 256, 1024, 2048, 4096, 8192, 12288, 16384, 24576, 32768, 49152, 65536, 81920,
                                98304, 131072, 196608, 262144};
    int polluting = argc > 1 && !strcmp(argv[1], "pollute");
    unsigned lp = (unsigned)atoi(argv[polluting ? 2 : 1 < argc ? 1 : 0]);
    GROUP_AFFINITY ga = {0};
    size_t i;
    if (argc < 2) lp = 0;
    ga.Mask = (KAFFINITY)1 << (lp % 64); ga.Group = (WORD)(lp / 64);
    if (!SetThreadGroupAffinity(GetCurrentThread(), &ga, NULL)) { printf("affinity failed %lu\n", GetLastError()); return 1; }
    if (polluting) return argc < 5 ? 2 : pollute((size_t)atoi(argv[3]), (unsigned)atoi(argv[4]));
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL);
    Sleep(50);
    printf("lp %u clock %.2f GHz (dependent add/xor chain)\n", lp, clock_ghz());
    printf("%10s %12s %12s\n", "KB", "data ns/ld", "code ns/call");
    for (i = 0; i < sizeof kb / sizeof kb[0]; i++)
        printf("%10zu %12.2f %12.2f\n", kb[i], data_ns(kb[i] * 1024), kb[i] >= 64 ? code_ns(kb[i] * 1024) : 0.0);
    printf("lp %u clock %.2f GHz (again)\n", lp, clock_ghz());
    return 0;
}

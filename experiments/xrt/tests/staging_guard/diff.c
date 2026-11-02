/* staging_guard/diff.c - differential test of the D3D8 buffer staging modes (round 4): the same pseudo-random sequence
 * of buffer Locks and Unlocks is run once with strict staging (a fresh guest block per Lock, decommitted at Unlock) and
 * once with guard staging (the block kept committed PAGE_NOACCESS between uses), each in its own process, and every
 * guest-observable outcome is printed; run.cmd requires the two traces to be identical.
 *   diff.exe strict|guard [ops] [seed]  > trace      (a timing summary goes to stderr, not into the trace)
 * The buffer path mirrors resource_storage.inc d8_resource_Lock / d8_unlock (buffers only): offset/size checks,
 * "already mapped" / "missing map" refusals, the staging block from xrt_virtual_alloc or xrt_staging_guard_take, the
 * d8_device_memory check of the block (xrt_is_committed + read-write protection), the shadow -> staging copy, the
 * undefined-byte evidence (d8_valid_all), DISCARD (0x2000) clearing the whole validity map, NOOVERWRITE (0x1000), the
 * staging -> shadow snapshot at Unlock with d8_valid_set, then xrt_virtual_free or xrt_staging_guard_put. Between them:
 * partial guest writes, stale-pointer reads and writes after Unlock (must fault in both modes), the answer an import
 * adapter gets for a stale pointer (xrt_is_committed), ordinary guest VirtualAlloc/VirtualFree of random sizes (must be
 * zero-filled and read-write), buffer destruction and re-creation with another length, and pool-pressure phases that
 * fill the 224 MB guest pool with ordinary blocks so the allocator must reclaim. Printed outcomes never include guest
 * addresses (the modes may place blocks differently); address agreement is counted separately (stderr). */
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xrt_internal.h"
#include "d8_valid_bits.h"

__declspec(thread) XrtThread* xrt_cur;
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list a; (void)c; va_start(a, fmt); printf("FATAL %d: ", code); vprintf(fmt, a); va_end(a); printf("\n");
    fflush(stdout); exit(3);
}
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) { (void)a; (void)size; (void)end; return 0; }
static unsigned reclaims;
void xrt_log(const char* fmt, ...) { if (!strncmp(fmt, "VirtualAlloc pool reclaim", 25)) reclaims++; }

static uint64_t rng = 0x9E3779B97F4A7C15ull;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (uint32_t)(rng >> 16); }
static uint32_t fnv(const unsigned char* p, size_t n) { uint32_t h = 2166136261u; while (n--) h = (h ^ *p++) * 16777619u; return h; }

static int faults_read(uint32_t a) {
    __try { volatile unsigned char x = *(volatile unsigned char*)G2H(a); (void)x; return 0; }
    __except (GetExceptionCode() == EXCEPTION_ACCESS_VIOLATION ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) { return 1; }
}
static int faults_write(uint32_t a) {
    __try { *(volatile unsigned char*)G2H(a) = 0xEE; return 0; }
    __except (GetExceptionCode() == EXCEPTION_ACCESS_VIOLATION ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) { return 1; }
}
/* d8_device_memory's answer for a writable range: committed (xrt_is_committed) and every page read-write */
static int device_memory_ok(uint32_t p, uint32_t size) {
    uint64_t at = p, end = (uint64_t)p + size;
    if (!p || !xrt_is_committed(p, size)) return 0;
    while (at < end) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(G2H((uint32_t)at), &m, sizeof m) || m.State != MEM_COMMIT || (m.Protect & PAGE_GUARD) ||
            (m.Protect & 255) != PAGE_READWRITE) return 0;
        at = (uint64_t)((BYTE*)m.BaseAddress - xrt_g) + m.RegionSize;
    }
    return 1;
}

#define NBUF 24
#define NORD 48
typedef struct { unsigned char *shadow, *valid; uint32_t length, staging, offset, bytes, flags, last; int locked; } Buf;
static Buf buf[NBUF];
static struct { uint32_t base, size; } ord[NORD];
static int guard;
static LARGE_INTEGER t_lock, t_unlock;
static unsigned n_lock, n_unlock, same_addr, diff_addr;

static void create(int i) {
    Buf* b = &buf[i];
    static const uint32_t lens[] = {512, 4096, 6000, 32768, 65536, 70000, 131072, 262144, 400000, 1048576};
    b->length = lens[rnd() % 10] + (rnd() % 2 ? 0 : rnd() % 4096);
    b->shadow = calloc(b->length, 1); b->valid = calloc(d8_valid_bytes(b->length), 1);
    b->locked = 0; b->staging = 0; b->last = 0;
}
static void destroy(int i) {
    Buf* b = &buf[i];
    if (b->locked) {   /* released while mapped: the HLE frees the staging block with the resource */
        if (!xrt_virtual_free(NULL, b->staging)) { printf("destroy %d: staging free failed\n", i); }
    }
    printf("D %d len %u shadow %08x valid %08x\n", i, b->length, fnv(b->shadow, b->length), fnv(b->valid, d8_valid_bytes(b->length)));
    free(b->shadow); free(b->valid);
}

static int zero_range(uint32_t a, uint32_t n) { const unsigned char* p = G2H(a); while (n--) if (*p++) return 0; return 1; }
static void lock(int i) {
    Buf* b = &buf[i];
    uint32_t offset = rnd() % 4 ? (rnd() % b->length) & ~3u : 0, size = rnd() % 5 ? rnd() % (b->length + 64) : 0;
    uint32_t flags = (rnd() % 4 == 0 ? 0x2000 : 0) | (rnd() % 4 == 0 ? 0x1000 : 0), commit, reserve;
    LARGE_INTEGER t0, t1;
    if (b->locked) { printf("L %d refused: resource already mapped\n", i); return; }
    if (offset > b->length) { printf("L %d refused: unsafe buffer descriptor/range\n", i); return; }
    if (!size) size = b->length - offset;
    if (!size || (uint64_t)offset + size > b->length) { printf("L %d off %u size %u refused: unsafe buffer range\n", i, offset, size); return; }
    QueryPerformanceCounter(&t0);
    b->staging = guard ? xrt_staging_guard_take(NULL, size) : xrt_virtual_alloc(NULL, size);
    {
        int ok = device_memory_ok(b->staging, size), undefined = !d8_valid_all(b->valid, offset, size);
        memcpy(G2H(b->staging), b->shadow + offset, size);
        if (flags & 0x2000) memset(b->valid, 0, d8_valid_bytes(b->length));
        QueryPerformanceCounter(&t1); t_lock.QuadPart += t1.QuadPart - t0.QuadPart; n_lock++;
        commit = (size + 0xFFFu) & ~0xFFFu; reserve = (size + 0xFFFFu) & ~0xFFFFu;
        printf("L %d off %u size %u flags %x ok %d undefined %d bytes %08x tail_zero %d past_commit_faults %d\n", i, offset, size,
               flags, ok, undefined, fnv(G2H(b->staging), size),
               zero_range(b->staging + size, commit - size),
               commit < reserve ? faults_read(b->staging + commit) : -1);
    }
    if (b->last) { if (b->last == b->staging) same_addr++; else diff_addr++; }
    b->locked = 1; b->offset = offset; b->bytes = size; b->flags = flags;
}
static void write_some(int i) {
    Buf* b = &buf[i];
    unsigned n = rnd() % 6, k;
    if (!b->locked) return;
    for (k = 0; k < n; k++) {   /* partial writes: some bytes, a run, or the whole range */
        uint32_t at = rnd() % b->bytes, len = rnd() % 3 == 0 ? b->bytes - at : 1 + rnd() % 64;
        if (at + len > b->bytes) len = b->bytes - at;
        memset(G2H(b->staging + at), (int)(rnd() & 255), len);
    }
    printf("W %d n %u bytes %08x\n", i, n, fnv(G2H(b->staging), b->bytes));
}
static void unlock(int i) {
    Buf* b = &buf[i];
    LARGE_INTEGER t0, t1;
    uint32_t stale;
    if (!b->locked) { printf("U %d refused: missing or mismatched map\n", i); return; }
    QueryPerformanceCounter(&t0);
    if (!device_memory_ok(b->staging, b->bytes)) printf("U %d snapshot range refused\n", i);
    memcpy(b->shadow + b->offset, G2H(b->staging), b->bytes);
    d8_valid_set(b->valid, b->offset, b->bytes);
    if (!(guard ? xrt_staging_guard_put(NULL, b->staging) : xrt_virtual_free(NULL, b->staging))) printf("U %d invalidation failed\n", i);
    QueryPerformanceCounter(&t1); t_unlock.QuadPart += t1.QuadPart - t0.QuadPart; n_unlock++;
    stale = b->staging + rnd() % b->bytes;
    printf("U %d shadow %08x valid %08x stale_read_faults %d stale_write_faults %d adapter_sees_committed %d device_memory_ok %d\n", i,
           fnv(b->shadow, b->length), fnv(b->valid, d8_valid_bytes(b->length)), faults_read(stale), faults_write(stale),
           xrt_is_committed(stale, 4), device_memory_ok(stale, 4));
    b->last = b->staging; b->locked = 0; b->staging = 0;
}
static void ordinary(int k) {
    if (ord[k].base) {
        printf("F %d %d\n", k, xrt_virtual_free(NULL, ord[k].base));
        ord[k].base = 0;
    } else {
        /* the engine allocator's request sizes come from a few classes (FMallocWindows pools, level data); fully random
         * sizes would test the bounded pool's capacity (4096 blocks, exact-size reuse) rather than the staging modes */
        static const uint32_t cls[] = {4096, 65536, 98304, 262144};
        uint32_t size = cls[rnd() % 4] - rnd() % 4000, i, zero = 1;
        ord[k].base = xrt_virtual_alloc(NULL, size); ord[k].size = size;
        for (i = 0; i < size; i += 509) zero &= ((unsigned char*)G2H(ord[k].base))[i] == 0;
        printf("A %d size %u zero %u rw %d\n", k, size, zero, device_memory_ok(ord[k].base, size));
        memset(G2H(ord[k].base), 0x77, size < 4096 ? size : 4096);
    }
}
static void pressure(void) {   /* fill the pool with 2 MiB ordinary blocks until the allocator reclaims, then release them */
    static uint32_t big[512];
    unsigned n = 0, k, before = reclaims;
    while (n < 512 && reclaims == before) { big[n] = xrt_virtual_alloc(NULL, 2u << 20); memset(G2H(big[n]), 1, 4096); n++; }
    for (k = 0; k < n; k++) xrt_virtual_free(NULL, big[k]);
    printf("P ok\n");   /* how many blocks fit before a reclaim depends on the mode's pool layout: not guest-visible */
}

int main(int argc, char** argv) {
    LARGE_INTEGER f;
    unsigned ops = argc > 2 ? (unsigned)atoi(argv[2]) : 60000, op, i;
    if (argc > 3) rng ^= (uint64_t)_strtoui64(argv[3], NULL, 0) * 0x2545F4914F6CDD1Dull;
    if (argc < 2 || (strcmp(argv[1], "strict") && strcmp(argv[1], "guard"))) { fprintf(stderr, "usage: diff strict|guard [ops] [seed]\n"); return 2; }
    guard = !strcmp(argv[1], "guard");
    QueryPerformanceFrequency(&f);
    xrt_mem_init();
    for (i = 0; i < NBUF; i++) create(i);
    for (op = 0; op < ops + 4000; op++) {
        uint32_t r = rnd() % 1000, i = rnd() % NBUF;
        /* the last 4000 operations follow one pool-pressure phase: the allocator has reclaimed (guarded blocks decommitted
         * like strict's), and Locks, ordinary allocations and buffer re-creations must get blocks again (beta batch: free
         * blocks are split, so the tail no longer has to avoid new sizes; it was 400 operations without them before). */
        if (op == ops) pressure();
        if (r < 380) lock(i);
        else if (r < 560) write_some(i);
        else if (r < 940) unlock(i);
        else if (r < 995) ordinary(rnd() % NORD);
        else { destroy(i); create(i); printf("R %d len %u\n", i, buf[i].length); }
    }
    for (i = 0; i < NBUF; i++) { if (buf[i].locked) unlock(i); destroy(i); }
    printf("END\n");
    fprintf(stderr, "%s: %u locks %.2f us/lock, %u unlocks %.2f us/unlock; staging address same as the buffer's previous %u, "
            "different %u; pool reclaims %u\n", argv[1], n_lock, n_lock ? t_lock.QuadPart * 1e6 / (double)n_lock / (double)f.QuadPart : 0,
            n_unlock, n_unlock ? t_unlock.QuadPart * 1e6 / (double)n_unlock / (double)f.QuadPart : 0, same_addr, diff_addr, reclaims);
    return 0;
}

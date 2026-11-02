/* pool_fragmentation - owned test of the guest VirtualAlloc pool and guest heap under fragmentation (beta batch; round-4
 * finding G: reclaimed pool blocks were reused whole, so a tail of new sizes exhausted the pool while most of it was
 * free). Links the developer runtime's xrt_mem.c (out/dev-init/runtime), or with -DREFERENCE an older xrt_mem.c, which
 * is expected to die "bounded client pool exhausted" in the fragmentation phases.
 *
 *   split      one reclaimed 24 MiB run serves many smaller new sizes (old: each took the whole run)
 *   churn N    random alloc/free of 64 KiB..6 MiB blocks with about N MiB live, every block checked: inside a pool
 *              segment, 64 KiB aligned, not over the lifted image or another live block, zero-filled; freed = decommitted
 *   segments   the second pool segment (above the guest heap) continues the bump region; the first one's tail is reused
 *   levels     40 simulated level loads: persistent set + per-level sizes + guard and reuse staging blocks, all freed
 *              at level end; then everything freed and the largest contiguous run must be allocatable again
 *   invalid    interior, unknown, double and split-remainder frees are refused and change nothing
 *   staging    guard blocks stay PAGE_NOACCESS across splits; a reclaim decommits them; guard take still re-opens
 *   heap       guest heap large blocks under bump exhaustion coalesce and split (normal path unchanged)
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/pool_fragmentation/run.cmd */
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xrt_internal.h"

__declspec(thread) XrtThread* xrt_cur;
static uint64_t live_bytes, peak_live;
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list a; (void)c; va_start(a, fmt); printf("xrt_fatal %d: ", code); vprintf(fmt, a); va_end(a);
    printf(" (test live %.1f MiB)\n", live_bytes / 1048576.0); fflush(stdout); exit(2);
}
/* A lifted module image inside the pool range, as UI.dll at 0x19100000 in the game (run 20261101-134219). */
#define FAKE_IMAGE_LO 0x19100000u
#define FAKE_IMAGE_HI 0x19200000u
/* Pool segments: the developer runtime has two (xrt_internal.h); the round-4 reference allocator has the first only. */
#ifdef XRT_POOL2_BASE
static const uint32_t seg_lo[2] = { XRT_POOL_BASE, XRT_POOL2_BASE }, seg_hi[2] = { XRT_POOL_END, XRT_POOL2_END };
#define NSEG 2
#else
static const uint32_t seg_lo[1] = { 0x12000000u }, seg_hi[1] = { 0x20000000u };
#define NSEG 1
#endif
#define POOL_LO 0x12000000u
#define POOL_HI 0x80000000u   /* span of the ownership map */
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) {
    if (a < FAKE_IMAGE_HI && FAKE_IMAGE_LO < (uint64_t)a + size) { *end = FAKE_IMAGE_HI; return 1; }
    return 0;
}
static unsigned reclaims, quiet;
void xrt_log(const char* fmt, ...) {
    va_list a;
    if (!strncmp(fmt, "VirtualAlloc pool reclaim", 25)) reclaims++;
    if (quiet) return;
    va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a);
}

static int failures;
#define CHECK(cond, what) do { if (!(cond)) { printf("FAIL %s\n", what); failures++; } else printf("ok   %s\n", what); } while (0)

static uint32_t rng = 0x2545F491u;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static DWORD protect(uint32_t a) {   /* 0 = not committed */
    MEMORY_BASIC_INFORMATION m;
    return VirtualQuery(xrt_g + a, &m, sizeof m) && m.State == MEM_COMMIT ? m.Protect : 0;
}

/* 64 KiB granule ownership map of the pool: catches overlap of live blocks and of the lifted image. */
static unsigned char owner[(POOL_HI - POOL_LO) >> 16];
static unsigned bad_range, bad_overlap, bad_zero, bad_decommit;
static void mark(uint32_t a, uint32_t size, int on) {
    uint32_t g, lo = (a - POOL_LO) >> 16, hi = (uint32_t)(((uint64_t)a + size - POOL_LO + 0xFFFFu) >> 16);
    for (g = lo; g < hi; g++) {
        if (on && owner[g]) bad_overlap++;
        owner[g] = (unsigned char)on;
    }
}
static uint32_t take(uint32_t size) {      /* ordinary guest VirtualAlloc, fully checked */
    uint32_t a = xrt_virtual_alloc(NULL, size);
    unsigned char* p = (unsigned char*)G2H(a);
    int s, in = 0;
    for (s = 0; s < NSEG; s++) if (a >= seg_lo[s] && (uint64_t)a + size <= seg_hi[s]) in = 1;
    if (!in || (a & 0xFFFFu) || (a < FAKE_IMAGE_HI && FAKE_IMAGE_LO < (uint64_t)a + size)) { bad_range++; return a; }
    if (p[0] || p[size - 1] || p[size / 2]) bad_zero++;
    p[0] = 0xA5; p[size - 1] = 0x5A;
    mark(a, size, 1);
    live_bytes += size; if (live_bytes > peak_live) peak_live = live_bytes;
    return a;
}
static void give(uint32_t a, uint32_t size) {
    mark(a, size, 0);
    live_bytes -= size;
    if (!xrt_virtual_free(NULL, a) || protect(a) || xrt_is_committed(a, 4)) bad_decommit++;
}
static void report_bad(const char* phase) {
    char m[160];
    sprintf(m, "%s: range %u overlap %u zero %u decommit %u", phase, bad_range, bad_overlap, bad_zero, bad_decommit);
    CHECK(!bad_range && !bad_overlap && !bad_zero && !bad_decommit, m);
    bad_range = bad_overlap = bad_zero = bad_decommit = 0;
}

static uint32_t fill[4096], fills[4096];
static unsigned nfill;
/* Use the whole bump region, segment by segment (each phase runs in a fresh process, so the pool starts empty at
 * 0x12000000): blocks of one size, then 64 KiB blocks up to the segment end, so no segment tail is left over. The next
 * allocation of a new size can only come from freed blocks. */
static void fill_pool(uint32_t each, uint32_t start) {
    int s;
    nfill = 0;
    for (s = 0; s < NSEG; s++) {
        uint32_t next = start > seg_lo[s] ? start : seg_lo[s];
        while (nfill < 4096 && next < seg_hi[s]) {
            uint32_t sz = next + (uint64_t)each <= seg_hi[s] ? each : 0x10000u;
            if (next < FAKE_IMAGE_HI && FAKE_IMAGE_LO < (uint64_t)next + sz) { next = FAKE_IMAGE_HI; continue; }
            fill[nfill] = take(sz); fills[nfill] = sz;
            if (fill[nfill] != next) bad_range++;
            next += (sz + 0xFFFFu) & ~0xFFFFu;
            nfill++;
        }
    }
}
static void unfill_except(unsigned lo, unsigned hi) { unsigned i; for (i = 0; i < nfill; i++) if (i < lo || i >= hi) give(fill[i], fills[i]); }

static void phase_split(void) {   /* one free 24 MiB run after the bump region is gone must serve many new sizes */
    uint32_t lo, hi, got[20]; unsigned i, k, inside = 0;
    quiet = 1;
    fill_pool(3u << 20, POOL_LO);
    for (i = 10; i < 18; i++) give(fill[i], fills[i]);              /* contiguous 24 MiB free run */
    lo = fill[10]; hi = fill[17] + (3u << 20);
    quiet = 0;
    for (k = 0; k < 20; k++) {                                       /* 20 new sizes 0.5..1.45 MiB, ~19.5 MiB in all */
        uint32_t sz = (512u << 10) + k * (50u << 10);
        got[k] = take(sz);
        if (got[k] >= lo && got[k] + sz <= hi) inside++;
    }
    CHECK(inside == 20, "split: 20 new sizes (19.5 MiB) all served from the one 24 MiB free run");
    for (k = 0; k < 20; k++) give(got[k], (512u << 10) + k * (50u << 10));
    unfill_except(10, 18);
    report_bad("split");
}

static void phase_churn(unsigned target_mib) {   /* random alloc/free with about target_mib live */
    static uint32_t addr[4096], size[4096]; unsigned n = 0, ops;
    uint64_t target = (uint64_t)target_mib << 20;
    quiet = 1;
    for (ops = 0; ops < 200000; ops++) {
        if (n && (live_bytes > target || (rnd() & 1))) {
            unsigned j = rnd() % n;
            give(addr[j], size[j]);
            addr[j] = addr[n - 1]; size[j] = size[n - 1]; n--;
        } else if (n < 4096) {
            uint32_t r = rnd() % 100, sz;
            sz = r < 60 ? 0x10000u : r < 85 ? 0x10000u + rnd() % (1u << 20) : r < 97 ? (1u << 20) + rnd() % (3u << 20)
               : (4u << 20) + rnd() % (2u << 20);
            if (live_bytes + sz > target + (8u << 20)) continue;
            addr[n] = take(sz); size[n] = sz; n++;
        }
    }
    while (n) { n--; give(addr[n], size[n]); }
    quiet = 0;
    printf("     churn: 200000 operations, target %u MiB, peak live %.1f MiB, %u reclaims\n", target_mib, peak_live / 1048576.0, reclaims);
    report_bad("churn (200000 random alloc/free operations)");
}

static void phase_levels(void) {  /* 40 level loads: persistent set, level-specific sizes, guard and reuse staging */
    static uint32_t persist[64], psize[64], lv[2048], lvs[2048];
    unsigned np = 0, level, nl, i, k, guard_ok = 1, guard_seen = 0;
    uint32_t big;
    quiet = 1;
    for (i = 0; i < 40; i++) { psize[np] = 0x10000u * (1 + rnd() % 16); persist[np] = take(psize[np]); np++; }
    for (level = 0; level < 40; level++) {
        uint32_t st[32]; unsigned ns = 0;
        uint64_t budget = (110ull + rnd() % 30) << 20, used = 0;
        nl = 0;
        while (used < budget && nl < 2048) {                         /* textures/meshes: level-specific sizes */
            uint32_t r = rnd() % 100, sz = r < 50 ? 0x10000u : r < 80 ? 0x8000u + rnd() % (512u << 10)
                                          : r < 96 ? (512u << 10) + rnd() % (2u << 20) : (2u << 20) + rnd() % (6u << 20);
            lv[nl] = take(sz); lvs[nl] = sz; used += sz; nl++;
            if ((rnd() & 15) == 0 && nl > 4) {                       /* some frees during the load */
                unsigned j = rnd() % nl; give(lv[j], lvs[j]); used -= lvs[j]; lv[j] = lv[nl - 1]; lvs[j] = lvs[nl - 1]; nl--;
            }
        }
        for (k = 0; k < 24; k++) {                                   /* D3D8 buffer Locks/Unlocks, guard and reuse staging */
            uint32_t sz = 0x4000u + rnd() % (768u << 10), b;
            if (k & 1) {
                b = xrt_staging_guard_take(NULL, sz);
                ((unsigned char*)G2H(b))[sz - 1] = 1;
                xrt_staging_guard_put(NULL, b);
                if (protect(b) != PAGE_NOACCESS) guard_ok = 0;
                guard_seen++;
            } else {
                b = xrt_staging_take(NULL, sz);
                ((unsigned char*)G2H(b))[0] = 1;
                if (ns < 32 && (rnd() & 1)) st[ns++] = b; else xrt_staging_put(NULL, b);
            }
        }
        for (k = 0; k < ns; k++) xrt_staging_put(NULL, st[k]);
        for (k = 0; k < nl; k++) give(lv[k], lvs[k]);               /* level unload */
        if (np < 64 && (level & 3) == 0) { psize[np] = 0x10000u * (1 + rnd() % 8); persist[np] = take(psize[np]); np++; }
    }
    for (k = 0; k < np; k++) give(persist[k], psize[k]);
    quiet = 0;
    printf("     levels: 40 loads, peak live %.1f MiB, %u reclaims\n", peak_live / 1048576.0, reclaims);
    report_bad("levels (40 simulated level loads with staging)");
    CHECK(guard_ok && guard_seen == 480, "levels: every guard-staging block was PAGE_NOACCESS after its put");
    {   /* all free again: large blocks fit (in the reference pool only after a full coalescing) */
        uint32_t b1 = take(100u << 20), b2 = take(100u << 20), b3 = take(200u << 20);
        CHECK(b1 && b2 && b3, "levels: 100 + 100 + 200 MiB blocks fit once everything is freed");
        give(b1, 100u << 20); give(b2, 100u << 20); give(b3, 200u << 20);
    }
    report_bad("levels: large blocks after the level loads");
}

static void phase_invalid(void) {
    uint32_t a, b;
    quiet = 1;
    fill_pool(2u << 20, POOL_LO);
    { unsigned i; for (i = 20; i < 30; i++) give(fill[i], fills[i]); }
    quiet = 0;
    a = take(3u << 20);                                              /* out of the free 20 MiB run */
    b = a + (3u << 20);                                              /* new allocator: base of the split remainder */
    CHECK(a == fill[20], "invalid: the 3 MiB block comes from the free run");
    CHECK(!xrt_virtual_free(NULL, a + 0x10000u) && protect(a + 0x10000u) == PAGE_READWRITE, "invalid: interior free refused, block intact");
    CHECK(!xrt_virtual_free(NULL, b) && !protect(b), "invalid: free of a split remainder (never allocated) refused");
    CHECK(!xrt_virtual_free(NULL, 0x13371234u), "invalid: unknown unaligned address refused");
    give(a, 3u << 20);
    CHECK(!xrt_virtual_free(NULL, a) && !protect(a), "invalid: double free refused, block stays decommitted");
    CHECK(!xrt_staging_put(NULL, a) && !xrt_staging_guard_put(NULL, a), "invalid: staging put of a freed block refused");
    quiet = 1;
    unfill_except(20, 30);
    quiet = 0;
    report_bad("invalid frees");
}

static void phase_staging(void) { /* guard staging blocks across splits and reclaims */
    uint32_t g, g2, r, f;
    g = xrt_staging_guard_take(NULL, 300000);                        /* reserve 0x50000 at the pool start */
    memset(G2H(g), 0x77, 300000);
    xrt_staging_guard_put(NULL, g);
    CHECK(protect(g) == PAGE_NOACCESS, "staging: guard put closes the block");
    g2 = xrt_staging_guard_take(NULL, 290000);
    CHECK(g2 == g && protect(g) == PAGE_READWRITE && ((unsigned char*)G2H(g))[290500] == 0,
          "staging: guard take of the size class re-opens it, zero past the locked bytes");
    xrt_staging_guard_put(NULL, g2);
    quiet = 1;
    fill_pool(4u << 20, g + 0x50000u);
    quiet = 0;
    f = take(0x10000u);                                              /* pressure: no free block, reclaim the guarded one */
    CHECK(f == g && !protect(g + 0x20000u), "staging: a reclaim decommits the guarded block, a split serves the request");
    give(f, 0x10000u);
    give(fill[3], fills[3]);
    r = xrt_staging_guard_take(NULL, 300000);
    CHECK(r == fill[3] && protect(r) == PAGE_READWRITE && ((unsigned char*)G2H(r))[299999] == 0,
          "staging: guard take after the reclaim gets a fresh zeroed block split from a free one");
    xrt_staging_guard_put(NULL, r);
    CHECK(protect(r) == PAGE_NOACCESS, "staging: the split block closes like any guard block");
    quiet = 1;
    unfill_except(3, 4);
    quiet = 0;
    report_bad("staging");
}

#ifdef XRT_POOL2_BASE
static void phase_segments(void) { /* the first segment's end moves the bump pointer to the second; its tail is reusable */
    XrtPoolStats st;
    uint32_t a, last = 0, gap;
    unsigned i;
    quiet = 1;
    for (i = 0; i < 64; i++) { a = take(6u << 20); if (a >= XRT_POOL2_BASE) break; last = a; }
    quiet = 0;
    CHECK(a == XRT_POOL2_BASE, "segments: the allocation that does not fit the first segment starts the second");
    gap = XRT_POOL_END - (last + (6u << 20));
    xrt_virtual_stats(&st);
    CHECK(gap && st.free_reserved == gap && st.largest_free == gap, "segments: the first segment's unused tail is a free block");
    CHECK(st.bump_next == XRT_POOL2_BASE + (6u << 20) && XRT_POOL2_BASE >= XRT_HEAP_END, "segments: the second segment lies above the guest heap");
    report_bad("segments");
}
#endif

static void phase_heap(void) {    /* guest heap large blocks under bump exhaustion (commits the 1 GB heap region) */
    static uint32_t h[1600]; unsigned n = 0, j; uint32_t big, rest, lo, hi;
    while (n < 1600 && (h[n] = xrt_heap_alloc(1u << 20)) != 0) n++;
    printf("     heap: %u blocks of 1 MiB before the region ended\n", n);
    for (j = 100; j < 104; j++) xrt_heap_free(NULL, h[j]);          /* 4 adjacent free large blocks */
    lo = h[100] - 16; hi = h[103] + (1u << 20);
    big = xrt_heap_alloc((3u << 20) + (512u << 10));                 /* only fits if they coalesce */
    CHECK(big && big >= lo && big + (3u << 20) + (512u << 10) <= hi, "heap: 3.5 MiB served from 4 coalesced 1 MiB blocks");
    rest = xrt_heap_alloc(256u << 10);                              /* the split remainder (~0.5 MiB) */
    CHECK(rest && rest > big && rest < hi, "heap: the split remainder serves the next large request");
    xrt_heap_free(NULL, big); xrt_heap_free(NULL, rest);
    for (j = 0; j < n; j++) if (j < 100 || j >= 104) xrt_heap_free(NULL, h[j]);
    big = xrt_heap_alloc(900u << 20);
    CHECK(big != 0, "heap: after freeing everything a 900 MiB block fits again");
    xrt_heap_free(NULL, big);
}

int main(int argc, char** argv) {
    const char* ph = argc > 1 ? argv[1] : "";
    xrt_mem_init();
    if (!strcmp(ph, "split")) phase_split();
    else if (!strcmp(ph, "churn")) phase_churn(argc > 2 ? (unsigned)atoi(argv[2]) : 150u);
#ifdef XRT_POOL2_BASE
    else if (!strcmp(ph, "segments")) phase_segments();
#endif
    else if (!strcmp(ph, "levels")) phase_levels();
    else if (!strcmp(ph, "invalid")) phase_invalid();
    else if (!strcmp(ph, "staging")) phase_staging();
    else if (!strcmp(ph, "heap")) phase_heap();
    else { printf("usage: pool_fragmentation split|churn|levels|invalid|staging|heap\n"); return 2; }
#ifndef REFERENCE
    {
        XrtPoolStats s;
        xrt_virtual_stats(&s);
        printf("     pool: %u blocks, %u live, free %.1f MiB, largest free %.1f MiB, bump %08x (high %08x), %u reclaims, %u splits\n",
               s.blocks, s.live_blocks, s.free_reserved / 1048576.0, s.largest_free / 1048576.0, s.bump_next, s.bump_high,
               s.reclaims, s.splits);
    }
#endif
    printf(failures ? "FAIL %s (%d)\n" : "PASS %s\n", ph, failures);
    return failures != 0;
}

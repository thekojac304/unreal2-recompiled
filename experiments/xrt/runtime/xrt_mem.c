/* xrt_mem.c - guest address space and guest heap.
 * One 4 GB (+64 KB slack for accesses that straddle 0xFFFFFFFF) host reservation holds guest memory;
 * regions are committed explicitly, so a stray guest access to anything else faults and is diagnosed. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

uint8_t* xrt_g;
static SRWLOCK rt_lock = SRWLOCK_INIT;
static uint32_t rt_next = XRT_RT_BASE;

void xrt_mem_init(void) {
    xrt_g = (uint8_t*)VirtualAlloc(NULL, 0x100000000ull + 0x10000u, MEM_RESERVE, PAGE_NOACCESS);
    if (!xrt_g) {
        fprintf(stderr, "xrt: cannot reserve 4 GB of guest address space (error %lu)\n", GetLastError());
        exit(XRT_EXIT_SETUP);
    }
}

void xrt_commit(uint32_t a, uint32_t size) {
    uint64_t lo = a & ~0xFFFull, hi = ((uint64_t)a + size + 0xFFF) & ~0xFFFull;
    if (!size)
        return;
    if (!VirtualAlloc(xrt_g + lo, (SIZE_T)(hi - lo), MEM_COMMIT, PAGE_READWRITE)) {
        fprintf(stderr, "xrt: commit of guest %08x+%x failed (error %lu)\n", a, size, GetLastError());
        exit(XRT_EXIT_SETUP);
    }
}

int xrt_is_committed(uint32_t a, uint32_t size) {
    uint64_t p = a, end = (uint64_t)a + size;
    while (p < end) {
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(xrt_g + p, &mbi, sizeof mbi) || mbi.State != MEM_COMMIT)
            return 0;
        p = (uint64_t)((uint8_t*)mbi.BaseAddress - xrt_g) + mbi.RegionSize;
    }
    return 1;
}

int xrt_range_is_free(uint32_t a, uint32_t size) {   /* no page of [a, a+size) committed */
    uint64_t p = a, end = (uint64_t)a + size;
    while (p < end) {
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(xrt_g + p, &mbi, sizeof mbi) || mbi.State == MEM_COMMIT)
            return 0;
        p = (uint64_t)((uint8_t*)mbi.BaseAddress - xrt_g) + mbi.RegionSize;
    }
    return 1;
}

uint32_t xrt_h2g(const void* p) {
    const uint8_t* q = (const uint8_t*)p;
    if (q < xrt_g || q >= xrt_g + 0x100000000ull)
        xrt_fatal(xrt_cur ? &xrt_cur->cpu : NULL, XRT_EXIT_UNSUPPORTED, "host pointer %p is not guest memory", p);
    return (uint32_t)(q - xrt_g);
}

uint32_t xrt_rt_alloc(uint32_t size, uint32_t align) {
    uint32_t a;
    AcquireSRWLockExclusive(&rt_lock);
    a = (rt_next + align - 1) & ~(align - 1);
    if ((uint64_t)a + size > XRT_RT_END) {
        ReleaseSRWLockExclusive(&rt_lock);
        xrt_fatal(NULL, XRT_EXIT_SETUP, "runtime data region exhausted");
    }
    rt_next = a + size;
    xrt_commit(a, size);
    ReleaseSRWLockExclusive(&rt_lock);
    return a;
}

uint32_t xrt_guest_strdup_a(const char* s) {
    uint32_t n = (uint32_t)strlen(s) + 1, a = xrt_rt_alloc(n, 4);
    memcpy(G2H(a), s, n);
    return a;
}

uint32_t xrt_guest_strlen16(uint32_t p) {
    uint32_t n = 0;
    while (rd16(p + 2 * n))
        n++;
    return n;
}

/* ---------------------------------------------------------------- guest heap
 * Block = 16-byte header {size, cap, magic, 0} + payload (16-byte aligned).
 * Small payloads (cap <= 4096, multiples of 16) use per-class free lists; larger ones are page-rounded
 * and reused best-fit. Freed memory is not returned to the host (bounded by the commandlet workloads). */
#define HDR 16u
#define MAGIC_USED 0x48545258u   /* "XRTH" */
#define MAGIC_FREE 0x46545258u   /* "XRTF" */
#define NSMALL 256u

static SRWLOCK heap_lock = SRWLOCK_INIT;
static uint32_t heap_top = XRT_HEAP_BASE, heap_committed = XRT_HEAP_BASE;
static uint32_t small_free[NSMALL];
typedef struct { uint32_t blk, cap; } LargeFree;
static LargeFree* large_free;
static uint32_t nlarge, large_cap;
static uint64_t st_allocs, st_frees, st_live;

static uint32_t bump(uint32_t total) {
    uint32_t b = heap_top;
    if ((uint64_t)b + total > XRT_HEAP_END)
        return 0;
    heap_top = b + total;
    if (heap_top > heap_committed) {
        uint32_t want = (heap_top - heap_committed + 0xFFFFFu) & ~0xFFFFFu;
        if ((uint64_t)heap_committed + want > XRT_HEAP_END)
            want = XRT_HEAP_END - heap_committed;
        xrt_commit(heap_committed, want);
        heap_committed += want;
    }
    return b;
}

uint32_t xrt_heap_alloc(uint32_t size) {
    uint32_t cap, blk = 0;
    if (size > 0x7FF00000u)
        return 0;
    cap = size ? (size + 15u) & ~15u : 16u;
    AcquireSRWLockExclusive(&heap_lock);
    if (cap <= 4096u) {
        uint32_t k = cap / 16u - 1u;
        if (small_free[k]) {
            blk = small_free[k];
            small_free[k] = rd32(blk + HDR);
        } else {
            blk = bump(HDR + cap);
        }
    } else {
        uint32_t i, best = UINT32_MAX;
        cap = ((cap + HDR + 0xFFFu) & ~0xFFFu) - HDR;
        for (i = 0; i < nlarge; i++)
            if (large_free[i].cap >= cap && (best == UINT32_MAX || large_free[i].cap < large_free[best].cap))
                best = i;
        if (best != UINT32_MAX) {
            blk = large_free[best].blk;
            cap = large_free[best].cap;
            large_free[best] = large_free[--nlarge];
        } else {
            blk = bump(HDR + cap);
        }
    }
    if (blk) {
        wr32(blk, size);
        wr32(blk + 4, cap);
        wr32(blk + 8, MAGIC_USED);
        wr32(blk + 12, 0);
        st_allocs++;
        st_live += size;
    }
    ReleaseSRWLockExclusive(&heap_lock);
    return blk ? blk + HDR : 0;
}

static uint32_t checked_block(CPU* c, uint32_t p, const char* what) {
    uint32_t blk = p - HDR;
    if (p < XRT_HEAP_BASE + HDR || p >= heap_top || (p & 15u) || rd32(blk + 8) != MAGIC_USED)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "%s of %08x: not a live guest heap block%s", what, p,
                  (p >= XRT_HEAP_BASE && p < heap_top && rd32(blk + 8) == MAGIC_FREE) ? " (already freed)" : "");
    return blk;
}

void xrt_heap_free(CPU* c, uint32_t p) {
    uint32_t blk, cap;
    if (!p)
        return;
    AcquireSRWLockExclusive(&heap_lock);
    blk = checked_block(c, p, "free");
    cap = rd32(blk + 4);
    st_frees++;
    st_live -= rd32(blk);
    wr32(blk + 8, MAGIC_FREE);
    if (cap <= 4096u) {
        uint32_t k = cap / 16u - 1u;
        wr32(blk + HDR, small_free[k]);
        small_free[k] = blk;
    } else {
        if (nlarge == large_cap) {
            large_cap = large_cap ? large_cap * 2 : 64;
            large_free = (LargeFree*)realloc(large_free, large_cap * sizeof *large_free);
            if (!large_free)
                xrt_fatal(c, XRT_EXIT_SETUP, "host out of memory");
        }
        large_free[nlarge].blk = blk;
        large_free[nlarge].cap = cap;
        nlarge++;
    }
    ReleaseSRWLockExclusive(&heap_lock);
}

uint32_t xrt_heap_msize(CPU* c, uint32_t p) {
    uint32_t s;
    AcquireSRWLockShared(&heap_lock);
    s = rd32(checked_block(c, p, "_msize"));
    ReleaseSRWLockShared(&heap_lock);
    return s;
}

uint32_t xrt_heap_realloc(CPU* c, uint32_t p, uint32_t size) {
    uint32_t blk, old, q;
    if (!p)
        return xrt_heap_alloc(size);
    if (!size) {                     /* msvcr70: realloc(p, 0) frees p and returns NULL */
        xrt_heap_free(c, p);
        return 0;
    }
    AcquireSRWLockExclusive(&heap_lock);
    blk = checked_block(c, p, "realloc");
    old = rd32(blk);
    if (size <= rd32(blk + 4)) {
        st_live += (uint64_t)size - old;
        wr32(blk, size);
        ReleaseSRWLockExclusive(&heap_lock);
        return p;
    }
    ReleaseSRWLockExclusive(&heap_lock);
    q = xrt_heap_alloc(size);
    if (!q)
        return 0;                    /* original block is left untouched, as in the CRT */
    memmove(G2H(q), G2H(p), old < size ? old : size);
    xrt_heap_free(c, p);
    return q;
}

void xrt_heap_stats(uint64_t* allocs, uint64_t* frees, uint64_t* bytes_live, uint32_t* high_water) {
    *allocs = st_allocs;
    *frees = st_frees;
    *bytes_live = st_live;
    *high_water = heap_top - XRT_HEAP_BASE;
}

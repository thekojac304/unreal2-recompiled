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
    /* the 4 GB window with a 2 GB guard below it (xrt.h: xlift --opt addr64 may compute a [reg + disp] access as
     * the 64-bit sum; a wrapped guest address then lands in a guard and faults as it would at its wrapped address) */
    uint8_t* r = (uint8_t*)VirtualAlloc(NULL, (SIZE_T)(XRT_GUEST_GUARD_BELOW + XRT_GUEST_WINDOW), MEM_RESERVE, PAGE_NOACCESS);
    if (!r) {
        fprintf(stderr, "xrt: cannot reserve 6 GB of guest address space (error %lu)\n", GetLastError());
        exit(XRT_EXIT_SETUP);
    }
    xrt_g = r + XRT_GUEST_GUARD_BELOW;
}

void xrt_commit(uint32_t a, uint32_t size) {
    uint64_t lo = a & ~0xFFFull, hi = ((uint64_t)a + size + 0xFFF) & ~0xFFFull;
    if (!size)
        return;
    if (hi > 0x80000000ull || lo < 0x10000ull) {   /* the layout above, relied on by xlift --opt addr64 */
        fprintf(stderr, "xrt: commit of guest %08x+%x outside the 32-bit user layout [0x10000, 0x80000000) refused\n", a, size);
        exit(XRT_EXIT_SETUP);
    }
    if (!VirtualAlloc(xrt_g + lo, (SIZE_T)(hi - lo), MEM_COMMIT, PAGE_READWRITE)) {
        fprintf(stderr, "xrt: commit of guest %08x+%x failed (error %lu)\n", a, size, GetLastError());
        exit(XRT_EXIT_SETUP);
    }
}

/* Counts guest decommits. xrt_decommit is the only path that takes guest pages out of MEM_COMMIT (and
 * guest pages are never reprotected), so a range observed committed under generation g is still committed
 * unless a decommit since g overlapped it. The last XRT_DECOMMIT_LOG decommitted ranges are kept for that
 * test (a buffer Unlock decommits its staging block every time; that must not invalidate the guest stack).
 * Decommits run on guest threads holding the execution baton. */
#define XRT_DECOMMIT_LOG 1024
volatile long xrt_mem_generation = 1;
static struct { uint64_t lo, hi; } decommit_log[XRT_DECOMMIT_LOG];

/* [lo, hi) is about to become inaccessible (decommit, or PAGE_NOACCESS in the guard staging mode): log it so range hints
 * that overlap it are dropped (xrt_mem_hint_valid) */
static void range_closing(uint64_t lo, uint64_t hi) {
    long g = xrt_mem_generation;
    decommit_log[g % XRT_DECOMMIT_LOG].lo = lo;
    decommit_log[g % XRT_DECOMMIT_LOG].hi = hi;
    MemoryBarrier();
    InterlockedIncrement(&xrt_mem_generation);
}

void xrt_decommit(uint32_t a, uint32_t size) {   /* an unloaded module's image: later accesses fault */
    uint64_t lo = a & ~0xFFFull, hi = ((uint64_t)a + size + 0xFFF) & ~0xFFFull;
    range_closing(lo, hi);
    if (size && !VirtualFree(xrt_g + lo, (SIZE_T)(hi - lo), MEM_DECOMMIT)) {
        fprintf(stderr, "xrt: decommit of guest %08x+%x failed (error %lu)\n", a, size, GetLastError());
        exit(XRT_EXIT_SETUP);
    }
}

/* 1 if guest range [lo, hi) verified under *gen is unaffected by every decommit since; *gen is advanced. */
int xrt_mem_hint_valid(uint64_t lo, uint64_t hi, long* gen) {
    long now = xrt_mem_generation, g = *gen;
    if (g == now)
        return 1;
    if (!g || now - g > XRT_DECOMMIT_LOG)
        return 0;
    for (; g != now; g++)
        if (decommit_log[g % XRT_DECOMMIT_LOG].lo < hi && lo < decommit_log[g % XRT_DECOMMIT_LOG].hi)
            return 0;
    *gen = now;
    return 1;
}

/* Per-thread hints of the last eight committed regions VirtualQuery reported (the guest stack and the heap
 * blocks holding D3D8 arguments): the D3D8 argument checks call this for every device method. */
static __declspec(thread) struct { uint64_t lo, hi; long gen; } commit_hint[8];
static __declspec(thread) unsigned commit_next;
/* Round 4: staging blocks the D3D8 HLE just committed are hinted in two slots of their own (xrt_hint_committed), so the
 * 100-220 buffer Locks of a frame no longer evict the guest stack and heap hints from commit_hint (each eviction cost
 * a VirtualQuery at the next D3D8 argument check). Same answers: every hint is validated against the decommit log. */
static __declspec(thread) struct { uint64_t lo, hi; long gen; } staging_hint[2];
static __declspec(thread) unsigned staging_next;
int xrt_is_committed(uint32_t a, uint32_t size) {
    uint64_t p = a, end = (uint64_t)a + size;
    long gen = xrt_mem_generation;
    unsigned h;
    for (h = 0; h < 8; h++)
        if (p >= commit_hint[h].lo && end <= commit_hint[h].hi &&
            xrt_mem_hint_valid(commit_hint[h].lo, commit_hint[h].hi, &commit_hint[h].gen))
            return 1;
    for (h = 0; h < 2; h++)
        if (p >= staging_hint[h].lo && end <= staging_hint[h].hi &&
            xrt_mem_hint_valid(staging_hint[h].lo, staging_hint[h].hi, &staging_hint[h].gen))
            return 1;
    while (p < end) {
        MEMORY_BASIC_INFORMATION mbi;
        uint64_t lo;
        /* committed but PAGE_NOACCESS / guard: only a guard-mode staging block between its Unlock and the next Lock of
         * its size class (guest pages are otherwise never reprotected). Answered as strict mode answers for the
         * decommitted block, so every adapter refuses a stale staging pointer exactly as in strict mode. */
        if (!VirtualQuery(xrt_g + p, &mbi, sizeof mbi) || mbi.State != MEM_COMMIT ||
            (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
            return 0;
        lo = (uint64_t)((uint8_t*)mbi.BaseAddress - xrt_g);
        p = lo + mbi.RegionSize;
        commit_hint[commit_next].lo = lo; commit_hint[commit_next].hi = p; commit_hint[commit_next].gen = gen;
        commit_next = (commit_next + 1) & 7;
    }
    return 1;
}

void xrt_hint_committed(uint32_t a, uint32_t size) {   /* [a, a+size) was just committed PAGE_READWRITE (xrt_commit) */
    staging_hint[staging_next].lo = a & ~0xFFFull; staging_hint[staging_next].hi = ((uint64_t)a + size + 0xFFF) & ~0xFFFull;
    staging_hint[staging_next].gen = xrt_mem_generation;
    staging_next = (staging_next + 1) & 1;
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

/* FMallocWindows in the real client owns VirtualAlloc blocks separately from the CRT heap. Keep real
 * reserve/commit/release bookkeeping, 64 KiB allocation alignment, page rounding and zero-on-recommit.
 * This bounded pool sits between the platform DLLs and CRT heap; exhaustion is explicitly unsupported.
 * Only NULL-address, read/write reserve+commit and whole-block release are currently exposed by the HLE. */
typedef struct { uint32_t base, reserved, committed; int live, warm; } VirtualBlock;
static VirtualBlock virtual_blocks[4096];
static uint32_t virtual_next = XRT_POOL_BASE;
static int nvirtual;
static SRWLOCK virtual_lock = SRWLOCK_INIT;
static uint32_t virtual_reclaims, virtual_splits, virtual_high = XRT_POOL_BASE;
/* Pool pressure (the bump region is used up): blocks were only ever re-used at their exact reserve size, so a level
 * transition with many new sizes ran the 224 MB pool out while most of it was free (TutA -> TutB, run
 * 20261101-133834). Reclaim, still under virtual_lock: decommit warm staging blocks, merge address-adjacent free
 * blocks (bump order = address order), then the caller takes the smallest free block that fits. Decommitted pages
 * come back zero-filled when committed again, as before. */
static void virtual_reclaim(void) {
    int i, j, warm = 0, merged = 0;
    for (i = 0; i < nvirtual; i++)
        if (virtual_blocks[i].warm) { xrt_decommit(virtual_blocks[i].base, virtual_blocks[i].committed); virtual_blocks[i].warm = 0; warm++; }
    for (i = 0, j = 0; i < nvirtual; i++) {
        VirtualBlock* b = &virtual_blocks[i];
        if (j && !b->live && !virtual_blocks[j - 1].live && !virtual_blocks[j - 1].warm &&
            virtual_blocks[j - 1].base + virtual_blocks[j - 1].reserved == b->base) {
            virtual_blocks[j - 1].reserved += b->reserved; merged++;
            continue;
        }
        virtual_blocks[j++] = *b;
    }
    nvirtual = j;
    /* A free block that ends the bump region goes back to it (the table stays in address order: every later block is
     * bumped above it). */
    if (nvirtual && !virtual_blocks[nvirtual - 1].live && !virtual_blocks[nvirtual - 1].warm &&
        virtual_blocks[nvirtual - 1].base + virtual_blocks[nvirtual - 1].reserved == virtual_next) {
        virtual_next = virtual_blocks[--nvirtual].base;
        merged++;
    }
    virtual_reclaims++;
    if (warm || merged)
        xrt_log("VirtualAlloc pool reclaim: %d warm staging blocks released, %d free blocks merged, %d blocks", warm, merged, nvirtual);
}
/* Pool pressure, part 2 (round-4 finding G, beta batch): a reused free block used to be taken whole, so after one
 * reclaim a tail of new sizes consumed the large merged runs and exhausted the pool with most of it free. The smallest
 * free block that fits is now split: the caller keeps the low `reserve` bytes and the rest stays a free block of its
 * own, inserted right after it so the table keeps address order (virtual_reclaim merges it back once it and a
 * neighbour are free). Free blocks hold no committed pages, so the remainder needs no memory operation. With a full
 * table the block is taken whole, as before. */
static VirtualBlock* virtual_best_fit(uint64_t reserve) {
    VirtualBlock* b = NULL;
    int i;
    for (i = 0; i < nvirtual; i++)
        if (!virtual_blocks[i].live && !virtual_blocks[i].warm && virtual_blocks[i].reserved >= reserve &&
            (!b || virtual_blocks[i].reserved < b->reserved))
            b = &virtual_blocks[i];
    if (b && b->reserved > reserve && nvirtual < 4096) {
        int k = (int)(b - virtual_blocks);
        memmove(&virtual_blocks[k + 2], &virtual_blocks[k + 1], (size_t)(nvirtual - k - 1) * sizeof *b);
        nvirtual++;
        virtual_blocks[k + 1].base = b->base + (uint32_t)reserve;
        virtual_blocks[k + 1].reserved = b->reserved - (uint32_t)reserve;
        virtual_blocks[k + 1].committed = 0; virtual_blocks[k + 1].live = 0; virtual_blocks[k + 1].warm = 0;
        b->reserved = (uint32_t)reserve;
        virtual_splits++;
    }
    return b;
}
/* Room for `reserve` bytes at the bump pointer. A lifted module image inside the pool range (UI.dll at 0x19100000) is
 * stepped over (TutB load, run 20261101-134219). When the first segment cannot hold the request, the bump pointer moves
 * to the second segment; the unused tail of the first becomes a free block, so it is reused like any other. */
static int virtual_bump_room(uint64_t reserve) {
    for (;;) {
        uint32_t seg_end = virtual_next < XRT_POOL2_BASE ? XRT_POOL_END : XRT_POOL2_END, end;
        if (virtual_next + reserve <= seg_end) {
            if (!xrt_lifted_overlap(virtual_next, (uint32_t)reserve, &end) || end <= virtual_next)
                return 1;
            xrt_log("VirtualAlloc pool: bump region %08x skips the lifted image ending at %08x", virtual_next, end);
            virtual_next = (end + 0xFFFFu) & ~0xFFFFu;
            continue;
        }
        if (seg_end != XRT_POOL_END)
            return 0;
        if (virtual_next < XRT_POOL_END && nvirtual < 4096 && !xrt_lifted_overlap(virtual_next, XRT_POOL_END - virtual_next, &end)) {
            VirtualBlock* g = &virtual_blocks[nvirtual++];
            g->base = virtual_next; g->reserved = XRT_POOL_END - virtual_next; g->committed = 0; g->live = 0; g->warm = 0;
        }
        xrt_log("VirtualAlloc pool: first segment used up at %08x, continuing in the second segment at %08x", virtual_next,
                XRT_POOL2_BASE);
        virtual_next = XRT_POOL2_BASE;
    }
}
uint32_t xrt_virtual_alloc(CPU* c, uint32_t size) {
    uint64_t reserve = ((uint64_t)size + 0xFFFFu) & ~0xFFFFull;
    uint32_t commit = (size + 0xFFFu) & ~0xFFFu;
    int i;
    VirtualBlock* b = NULL;
    AcquireSRWLockExclusive(&virtual_lock);
    for (i = 0; i < nvirtual; i++)
        if (!virtual_blocks[i].live && !virtual_blocks[i].warm && virtual_blocks[i].reserved == reserve) { b = &virtual_blocks[i]; break; }
    /* Exact size first, then the bump region (both segments); only when that is used up (or the table is full), a
     * split best fit, then a reclaim and a second best fit. */
    if (!b && size && reserve <= 0x0E000000u && (nvirtual == 4096 || !virtual_bump_room(reserve))) {
        b = virtual_best_fit(reserve);
        if (!b) {
            virtual_reclaim();
            b = virtual_best_fit(reserve);
        }
    }
    if (!b) {
        if (!size || reserve > 0x0E000000u || nvirtual == 4096 || !virtual_bump_room(reserve)) {
            ReleaseSRWLockExclusive(&virtual_lock);
            xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "VirtualAlloc: bounded client pool exhausted or overlaps a lifted module (size %u)", size);
        }
        b = &virtual_blocks[nvirtual++];
        b->base = virtual_next; b->reserved = (uint32_t)reserve;
        virtual_next += (uint32_t)reserve;
        if (virtual_next > virtual_high)
            virtual_high = virtual_next;
    }
    xrt_commit(b->base, commit);
    b->committed = commit; b->live = 1;
    i = b->base;
    ReleaseSRWLockExclusive(&virtual_lock);
    return (uint32_t)i;
}
/* Pool figures for the runtime report: live/free/staging bytes by block state, table size, bump high water. */
void xrt_virtual_stats(XrtPoolStats* s) {
    int i;
    memset(s, 0, sizeof *s);
    AcquireSRWLockShared(&virtual_lock);
    for (i = 0; i < nvirtual; i++) {
        const VirtualBlock* b = &virtual_blocks[i];
        if (b->live) { s->live_blocks++; s->live_reserved += b->reserved; }
        else if (b->warm) s->staging_reserved += b->reserved;
        else { s->free_reserved += b->reserved; if (b->reserved > s->largest_free) s->largest_free = b->reserved; }
    }
    s->blocks = (uint32_t)nvirtual; s->bump_next = virtual_next; s->bump_high = virtual_high;
    s->reclaims = virtual_reclaims; s->splits = virtual_splits;
    ReleaseSRWLockShared(&virtual_lock);
}
int xrt_virtual_free(CPU* c, uint32_t base) {
    int i;
    (void)c;
    AcquireSRWLockExclusive(&virtual_lock);
    for (i = 0; i < nvirtual; i++) if (virtual_blocks[i].live && virtual_blocks[i].base == base) {
        xrt_decommit(base, virtual_blocks[i].committed);
        virtual_blocks[i].live = 0;
        ReleaseSRWLockExclusive(&virtual_lock);
        return 1;
    }
    ReleaseSRWLockExclusive(&virtual_lock);
    return 0;
}

/* Developer D3D8 buffer staging reuse (resource_storage.inc, XRT_DEV_STAGING=reuse): a released staging block stays
 * committed ("warm") instead of being decommitted, and only the next staging Lock of the same reserve size takes it,
 * committing more pages if it needs them. Ordinary VirtualAlloc never takes a warm block (its callers expect
 * zero-filled memory), so the pool holds the same blocks as with decommit. */
uint32_t xrt_staging_take(CPU* c, uint32_t size) {
    uint64_t reserve = ((uint64_t)size + 0xFFFFu) & ~0xFFFFull;
    uint32_t commit = (size + 0xFFFu) & ~0xFFFu;
    int i;
    AcquireSRWLockExclusive(&virtual_lock);
    for (i = 0; i < nvirtual; i++)
        if (virtual_blocks[i].warm == 1 && virtual_blocks[i].reserved == reserve) {
            VirtualBlock* b = &virtual_blocks[i];
            if (b->committed < commit) { xrt_commit(b->base + b->committed, commit - b->committed); b->committed = commit; }
            b->warm = 0; b->live = 1;
            ReleaseSRWLockExclusive(&virtual_lock);
            return b->base;
        }
    ReleaseSRWLockExclusive(&virtual_lock);
    return size ? xrt_virtual_alloc(c, size) : 0;
}
/* Guard staging (resource_storage.inc, XRT_DEV_STAGING=guard): a released block stays committed but PAGE_NOACCESS
 * ("guarded", warm == 2), so a guest pointer kept past Unlock faults exactly as after a decommit; the next staging Lock of
 * the same reserve size re-opens the pages it needs read-write and zeroes them past the locked bytes, so the guest sees
 * what a fresh block would show (the HLE then copies the shadow bytes in). Reclaim decommits guarded blocks like warm
 * ones; ordinary VirtualAlloc never takes them. */
uint32_t xrt_staging_guard_take(CPU* c, uint32_t size) {
    uint64_t reserve = ((uint64_t)size + 0xFFFFu) & ~0xFFFFull;
    uint32_t commit = (size + 0xFFFu) & ~0xFFFu;
    DWORD old;
    int i;
    AcquireSRWLockExclusive(&virtual_lock);
    for (i = 0; i < nvirtual; i++)
        if (virtual_blocks[i].warm == 2 && virtual_blocks[i].reserved == reserve) {
            VirtualBlock* b = &virtual_blocks[i];
            uint32_t open = commit < b->committed ? commit : b->committed;
            if (open && !VirtualProtect(xrt_g + b->base, open, PAGE_READWRITE, &old)) {
                ReleaseSRWLockExclusive(&virtual_lock);
                xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "staging guard: re-opening block %08x failed (%lu)", b->base, GetLastError());
            }
            if (b->committed < commit) { xrt_commit(b->base + b->committed, commit - b->committed); b->committed = commit; }
            b->warm = 0; b->live = 1;
            memset(xrt_g + b->base + size, 0, commit - size);   /* past the locked bytes: zero, as in a fresh block */
            ReleaseSRWLockExclusive(&virtual_lock);
            return b->base;
        }
    ReleaseSRWLockExclusive(&virtual_lock);
    return size ? xrt_virtual_alloc(c, size) : 0;
}
int xrt_staging_guard_put(CPU* c, uint32_t base) {
    DWORD old;
    int i;
    AcquireSRWLockExclusive(&virtual_lock);
    for (i = 0; i < nvirtual; i++) if (virtual_blocks[i].live && virtual_blocks[i].base == base) {
        VirtualBlock* b = &virtual_blocks[i];
        range_closing(b->base, (uint64_t)b->base + b->committed);
        if (b->committed && !VirtualProtect(xrt_g + b->base, b->committed, PAGE_NOACCESS, &old)) {
            ReleaseSRWLockExclusive(&virtual_lock);
            xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "staging guard: closing block %08x failed (%lu)", base, GetLastError());
        }
        b->live = 0; b->warm = 2;
        ReleaseSRWLockExclusive(&virtual_lock);
        return 1;
    }
    ReleaseSRWLockExclusive(&virtual_lock);
    return 0;
}
int xrt_staging_put(CPU* c, uint32_t base) {
    int i;
    (void)c;
    AcquireSRWLockExclusive(&virtual_lock);
    for (i = 0; i < nvirtual; i++) if (virtual_blocks[i].live && virtual_blocks[i].base == base) {
        virtual_blocks[i].live = 0; virtual_blocks[i].warm = 1;
        ReleaseSRWLockExclusive(&virtual_lock);
        return 1;
    }
    ReleaseSRWLockExclusive(&virtual_lock);
    return 0;
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
static uint32_t heap_pressure_allocs;

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

/* Heap pressure (beta batch, defensive: the game's guest heap peaks near 50 MB of the 1.5 GB region): large free blocks
 * are kept whole, unsorted, so a long session could end the bump region with most of it free. Only when bump fails:
 * sort the large free list by address, merge address-adjacent blocks (header + payload contiguous), and give a free
 * block that ends at heap_top back to the bump region. Small-class blocks stay on their lists. Normal allocation order
 * and addresses are unchanged until the first such failure. */
static int large_by_addr(const void* a, const void* b) {
    uint32_t x = ((const LargeFree*)a)->blk, y = ((const LargeFree*)b)->blk;
    return x < y ? -1 : x > y;
}
static void heap_coalesce(void) {
    uint32_t i, j;
    if (!nlarge)
        return;
    qsort(large_free, nlarge, sizeof *large_free, large_by_addr);
    for (i = 1, j = 0; i < nlarge; i++) {
        if (large_free[j].blk + HDR + large_free[j].cap == large_free[i].blk) {
            large_free[j].cap += HDR + large_free[i].cap;
            wr32(large_free[j].blk + 4, large_free[j].cap);
        } else {
            large_free[++j] = large_free[i];
        }
    }
    nlarge = j + 1;
    if (large_free[nlarge - 1].blk + HDR + large_free[nlarge - 1].cap == heap_top)
        heap_top = large_free[--nlarge].blk;
}
/* Best fit from the large free list; under pressure a block with at least two pages to spare is split and the rest
 * stays free (page-rounded, so it stays a large block). */
static uint32_t large_take(uint32_t* cap, int split) {
    uint32_t i, best = UINT32_MAX, blk;
    for (i = 0; i < nlarge; i++)
        if (large_free[i].cap >= *cap && (best == UINT32_MAX || large_free[i].cap < large_free[best].cap))
            best = i;
    if (best == UINT32_MAX)
        return 0;
    blk = large_free[best].blk;
    if (split && large_free[best].cap - *cap >= 0x2000u) {
        uint32_t rest = blk + HDR + *cap;
        large_free[best].blk = rest;
        large_free[best].cap -= HDR + *cap;
        wr32(rest, 0); wr32(rest + 4, large_free[best].cap); wr32(rest + 8, MAGIC_FREE); wr32(rest + 12, 0);
    } else {
        *cap = large_free[best].cap;
        large_free[best] = large_free[--nlarge];
    }
    return blk;
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
            if (!blk) { heap_coalesce(); blk = bump(HDR + cap); }
        }
    } else {
        cap = ((cap + HDR + 0xFFFu) & ~0xFFFu) - HDR;
        blk = large_take(&cap, 0);
        if (!blk)
            blk = bump(HDR + cap);
        if (!blk) {
            heap_coalesce();
            blk = large_take(&cap, 1);
            if (!blk)
                blk = bump(HDR + cap);
            if (blk && heap_pressure_allocs++ < 8)
                xrt_log("guest heap pressure: coalesced to %u large free blocks, served %u bytes at %08x", nlarge, cap, blk);
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

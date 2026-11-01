/* staging_reuse - focused test of the guest VirtualAlloc pool behaviour that the developer D3D8 staging modes rely
 * on (out/dev-init/runtime/xrt_mem.c; resource_storage.inc). Owned code only; links the developer runtime's xrt_mem.c.
 *
 *   strict  xrt_virtual_free decommits: a stale pointer into the block no longer refers to committed memory.
 *   reuse   xrt_staging_put keeps the block committed; xrt_staging_take of the same size class gets it back (and grows
 *           its commit when needed); a different size class does not; ordinary xrt_virtual_alloc never receives a warm
 *           block (it gets zero-filled memory), so the pool holds the same blocks as in strict mode.
 *   both    every block is inside guest memory and never overlaps another live block.
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/staging_reuse/run.cmd */
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "xrt_internal.h"

__declspec(thread) XrtThread* xrt_cur;
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list a; (void)c; va_start(a, fmt); fprintf(stderr, "xrt_fatal %d: ", code); vfprintf(stderr, fmt, a); va_end(a);
    fputc('\n', stderr); exit(2);
}
/* A lifted module image inside the pool range, as UI.dll at 0x19100000 in the game (run 20261101-134219). */
#define FAKE_IMAGE_LO 0x19100000u
#define FAKE_IMAGE_HI 0x19200000u
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) {
    if (a < FAKE_IMAGE_HI && FAKE_IMAGE_LO < (uint64_t)a + size) { *end = FAKE_IMAGE_HI; return 1; }
    return 0;
}
void xrt_log(const char* fmt, ...) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); }

static int failures;
#define CHECK(cond, what) do { if (!(cond)) { printf("FAIL %s\n", what); failures++; } else printf("ok   %s\n", what); } while (0)

static int committed(uint32_t a) {
    MEMORY_BASIC_INFORMATION m;
    return VirtualQuery(xrt_g + a, &m, sizeof m) && m.State == MEM_COMMIT;
}

int main(void) {
    uint32_t a, b, c, d, e, f;
    xrt_mem_init();
    /* strict: free decommits */
    a = xrt_virtual_alloc(NULL, 51080);
    memset(G2H(a), 0x5a, 51080);
    CHECK(a >= 0x12000000u && a < 0x20000000u && committed(a), "strict alloc is a committed guest pool block");
    CHECK(xrt_virtual_free(NULL, a) && !committed(a) && !xrt_is_committed(a, 4), "strict free decommits (stale pointer faults)");
    /* reuse: put keeps the block committed, take of the same class returns it */
    b = xrt_staging_take(NULL, 51080);
    CHECK(b == a && committed(b), "first take reuses the strict-freed block (fresh commit)");
    CHECK(((unsigned char*)G2H(b))[100] == 0, "a recommitted block is zero-filled");
    memset(G2H(b), 0x77, 51080);
    CHECK(xrt_staging_put(NULL, b) && committed(b), "put keeps the block committed (warm)");
    CHECK(((unsigned char*)G2H(b))[100] == 0x77, "a warm block keeps its contents (stale pointer aliases it)");
    c = xrt_virtual_alloc(NULL, 51080);
    CHECK(c != b && committed(c) && ((unsigned char*)G2H(c))[100] == 0, "ordinary VirtualAlloc of the class gets a different, zeroed block");
    d = xrt_staging_take(NULL, 40000);
    CHECK(d == b, "staging take of the same 64 KiB class gets the warm block");
    CHECK(xrt_staging_put(NULL, d), "put again");
    e = xrt_staging_take(NULL, 60000);
    CHECK(e == b && committed(e + 59999), "take with a larger size in the class commits the extra pages");
    CHECK(xrt_staging_put(NULL, e), "put again");
    f = xrt_staging_take(NULL, 200000);
    CHECK(f != b && committed(f) && (f >= b + 0x10000u || f + 0x40000u <= b), "a different size class gets its own block");
    CHECK(xrt_staging_put(NULL, f), "put of the other class");
    CHECK(!xrt_staging_put(NULL, f), "a second put of the same block is refused");
    CHECK(!xrt_staging_put(NULL, 0x12345000u), "put of an unknown address is refused");
    CHECK(xrt_virtual_free(NULL, c), "ordinary free still works");
    {   /* pressure: the bump region runs out while most of the pool is free (blocks of other sizes) - the level-transition
         * case of run 20261101-133834. Reclaim releases warm staging blocks, merges adjacent free blocks and best-fits. */
        static uint32_t blocks[128]; unsigned n = 0, i, overlap = 0; uint32_t big, warm, lo, hi;
        while (n < 128) { blocks[n] = xrt_virtual_alloc(NULL, 3u << 20); if (blocks[n] + (3u << 20) > 0x1F000000u) { n++; break; } n++; }
        printf("     filled the pool with %u blocks of 3 MiB (last at %08x)\n", n, blocks[n - 1]);
        for (i = 0, overlap = 0; i < n; i++) if (blocks[i] < FAKE_IMAGE_HI && FAKE_IMAGE_LO < blocks[i] + (3u << 20)) overlap++;
        CHECK(!overlap && blocks[n - 1] > FAKE_IMAGE_HI, "lifted image: the bump region steps over a module image inside the pool");
        overlap = 0;
        memset(G2H(blocks[10]), 0x33, 4096);
        for (i = 10; i < 18; i++) xrt_virtual_free(NULL, blocks[i]);     /* a contiguous free run of 24 MiB */
        warm = xrt_staging_take(NULL, 1u << 20); xrt_staging_put(NULL, warm);  /* a warm staging block */
        lo = blocks[10]; hi = blocks[17] + (3u << 20);
        big = xrt_virtual_alloc(NULL, 20u << 20);                        /* no block of this size exists; bump space is gone */
        for (i = 0; i < n; i++) if ((i < 10 || i >= 18) && big < blocks[i] + (3u << 20) && blocks[i] < big + (20u << 20)) overlap++;
        CHECK(big >= lo && big + (20u << 20) <= hi && committed(big + (20u << 20) - 1), "pressure: a new 20 MiB size is served from the merged free run");
        CHECK(((unsigned char*)G2H(big))[0] == 0 && ((unsigned char*)G2H(big))[(20u << 20) - 1] == 0, "pressure: the reused block is zero-filled");
        CHECK(!overlap, "pressure: the block overlaps no live block");
        CHECK(!committed(warm) || warm < lo || warm >= hi, "pressure: the warm staging block was released (decommitted) by the reclaim");
        CHECK(xrt_virtual_free(NULL, big) && !committed(big), "pressure: the merged block frees and decommits as one");
    }
    printf(failures ? "FAIL (%d)\n" : "PASS\n", failures);
    return failures != 0;
}

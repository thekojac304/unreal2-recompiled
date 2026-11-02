/* staging_guard - focused test of the opt-in "guard" D3D8 buffer staging mode's pool functions (round 3;
 * out/dev-init/runtime/xrt_mem.c xrt_staging_guard_take/_put; resource_storage.inc d8_staging_guard). Owned code only;
 * links the developer runtime's xrt_mem.c, like staging_reuse.
 *   guard  put leaves the block committed but PAGE_NOACCESS (a stale pointer faults, as after strict's decommit) and
 *          invalidates overlapping range hints; take of the same size class re-opens exactly the pages it needs
 *          read-write, zero past the requested bytes; pages beyond stay inaccessible; a larger take commits the rest;
 *          ordinary VirtualAlloc and reuse-mode take never receive a guarded block; reclaim decommits guarded blocks.
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/staging_guard/run.cmd */
#include <windows.h>
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

static int failures;
#define CHECK(cond, what) do { if (!(cond)) { printf("FAIL %s\n", what); failures++; } else printf("ok   %s\n", what); } while (0)

static DWORD protect(uint32_t a) {   /* 0 = not committed */
    MEMORY_BASIC_INFORMATION m;
    return VirtualQuery(xrt_g + a, &m, sizeof m) && m.State == MEM_COMMIT ? m.Protect : 0;
}
static int faults(uint32_t a) {      /* a read of guest address a raises an access violation */
    __try { volatile unsigned char x = *(volatile unsigned char*)G2H(a); (void)x; return 0; }
    __except (GetExceptionCode() == EXCEPTION_ACCESS_VIOLATION ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) { return 1; }
}

int main(void) {
    uint32_t a, b, c, d, e;
    long gen;
    unsigned i, zero;
    xrt_mem_init();
    a = xrt_staging_guard_take(NULL, 51080);                       /* no guarded block yet: a fresh strict block */
    CHECK(a >= 0x12000000u && protect(a) == PAGE_READWRITE, "first guard take is a fresh committed block");
    memset(G2H(a), 0x5a, 51080);
    CHECK(xrt_is_committed(a, 51080), "range hint for the open block");
    gen = xrt_mem_generation;
    CHECK(xrt_staging_guard_put(NULL, a), "guard put");
    CHECK(protect(a) == PAGE_NOACCESS && protect(a + 51079) == PAGE_NOACCESS, "the block stays committed but PAGE_NOACCESS");
    CHECK(faults(a) && faults(a + 51079), "a stale pointer into the block faults (as after a decommit)");
    CHECK(!xrt_is_committed(a, 4) && !xrt_is_committed(a + 51076, 4),
          "import adapters see a stale pointer as uncommitted, as after strict's decommit (round 4)");
    CHECK(xrt_mem_generation != gen, "the put is logged for range-hint invalidation");
    CHECK(!xrt_staging_guard_put(NULL, a), "a second put of the same block is refused");
    b = xrt_virtual_alloc(NULL, 51080);
    CHECK(b != a && protect(b) == PAGE_READWRITE && ((unsigned char*)G2H(b))[100] == 0, "ordinary VirtualAlloc gets a different, zeroed block");
    c = xrt_staging_take(NULL, 51080);
    CHECK(c != a, "reuse-mode take does not receive a guarded block");
    xrt_staging_put(NULL, c);
    d = xrt_staging_guard_take(NULL, 30000);                       /* same 64 KiB class, fewer bytes */
    CHECK(d == a, "guard take of the same class re-opens the guarded block");
    CHECK(protect(d) == PAGE_READWRITE && protect(d + 29999) == PAGE_READWRITE, "the pages it needs are read-write again");
    CHECK(faults(d + 0x8000) && protect(d + 0x8000) == PAGE_NOACCESS, "pages past the request stay inaccessible");
    for (i = 30000, zero = 1; i < 0x7530u + (0x1000 - (30000 & 0xFFF)) && i < 0x8000; i++) zero &= ((unsigned char*)G2H(d))[i] == 0;
    CHECK(zero, "bytes past the request up to the page end are zero, as in a fresh block");
    CHECK(((unsigned char*)G2H(d))[100] == 0x5a, "bytes inside the request keep old data until the HLE copies the shadow in");
    CHECK(xrt_staging_guard_put(NULL, d), "put again");
    e = xrt_staging_guard_take(NULL, 60000);                       /* larger than ever committed in the class */
    CHECK(e == a && protect(e + 59999) == PAGE_READWRITE, "a larger take re-opens and commits the rest");
    for (i = 51080, zero = 1; i < 60000; i++) zero &= ((unsigned char*)G2H(e))[i] == 0;
    CHECK(zero, "newly committed bytes are zero");
    CHECK(xrt_staging_guard_put(NULL, e), "put of the larger block");
    {   /* pool pressure: fill the bump region exactly (8 MiB blocks, then the remainder), free one 8 MiB block, then ask
         * for a 6 MiB block, a size class that exists nowhere: the allocator best-fits (splits) it; then a request only a merge
         * can serve makes it reclaim (warm and guarded blocks alike are decommitted) */
        static uint32_t blocks[64]; unsigned n = 0; uint32_t fitted, end;
        do { blocks[n] = xrt_virtual_alloc(NULL, 8u << 20); end = blocks[n] + (8u << 20); n++; } while (n < 64 && end + (8u << 20) <= XRT_HEAP_BASE);
        if (end < XRT_HEAP_BASE) xrt_virtual_alloc(NULL, XRT_HEAP_BASE - end);   /* the bump region is now used up */
#ifdef XRT_POOL2_BASE
        {   /* and the second pool segment (beta batch), the same way */
            uint32_t e2 = XRT_POOL2_BASE, b2;
            while (e2 + (8u << 20) <= XRT_POOL2_END) { b2 = xrt_virtual_alloc(NULL, 8u << 20); e2 = b2 + (8u << 20); }
            if (e2 < XRT_POOL2_END) xrt_virtual_alloc(NULL, XRT_POOL2_END - e2);
        }
#endif
        xrt_virtual_free(NULL, blocks[n / 2]);
        fitted = xrt_virtual_alloc(NULL, 6u << 20);
        CHECK(fitted == blocks[n / 2], "pool pressure: the allocator best-fit (and split) the freed block");
        CHECK(protect(a) == PAGE_NOACCESS, "a free block fitted, so no reclaim: the guarded block is still closed");
        /* beta batch: reclaim only when no free block fits. Free the next 8 MiB block and ask for 9 MiB: only the merge
         * of the 2 MiB split remainder with it fits, so the allocator reclaims (decommitting the guarded block). */
        xrt_virtual_free(NULL, blocks[n / 2 + 1]);
        fitted = xrt_virtual_alloc(NULL, 9u << 20);
        CHECK(fitted == blocks[n / 2] + (6u << 20), "pool pressure: the reclaim merged the remainder with its free neighbour");
        CHECK(!protect(a), "reclaim decommitted the guarded block");
    }
    printf(failures ? "FAIL: %d check(s)\n" : "PASS\n", failures);
    return failures != 0;
}

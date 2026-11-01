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
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) { (void)a; (void)size; (void)end; return 0; }

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
    printf(failures ? "FAIL (%d)\n" : "PASS\n", failures);
    return failures != 0;
}

/* Same client allocation/release/reallocation experiment, native x86 versus real guest memory manager. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#ifndef ORIGINAL
#include "xrt_internal.h"
__declspec(thread) XrtThread* xrt_cur;
int xrt_lifted_overlap(uint32_t a, uint32_t n, uint32_t* end) {
    /* Empty module-registry fixture; this test maps no modules. */
    (void)a; (void)n; (void)end; return 0;
}
void xrt_fatal(CPU* c, int code, const char* fmt, ...) { (void)c; (void)fmt; exit(code); }
#endif
int main(void) {
    unsigned char* p;
    unsigned n;
#ifndef ORIGINAL
    uint32_t a;
    xrt_mem_init();
    a = xrt_virtual_alloc(NULL, 0xfff0u); p = (unsigned char*)G2H(a);
    if (a & 0xffffu || !xrt_is_committed(a, 0x10000u)) return 1;
#else
    p = VirtualAlloc(NULL, 0xfff0u, MEM_COMMIT, PAGE_READWRITE);
    if (!p || (ULONG_PTR)p & 0xffffu) return 1;
#endif
    for (n=0;n<0x10000u;n++) if (p[n]) return 1;
    memset(p,0xa5,0x10000u);
#ifndef ORIGINAL
    if (!xrt_virtual_free(NULL,a) || xrt_is_committed(a,1)) return 1;
    a=xrt_virtual_alloc(NULL,0xfff0u); p=(unsigned char*)G2H(a);
#else
    if (!VirtualFree(p,0,MEM_RELEASE)) return 1;
    p=VirtualAlloc(NULL,0xfff0u,MEM_COMMIT,PAGE_READWRITE);
    if (!p) return 1;
#endif
    for (n=0;n<0x10000u;n++) if (p[n]) return 1;
#ifndef ORIGINAL
    if (!xrt_virtual_free(NULL,a) || xrt_virtual_free(NULL,a)) return 1;
#else
    if (!VirtualFree(p,0,MEM_RELEASE) || VirtualFree(p,0,MEM_RELEASE)) return 1;
#endif
    puts("PASS aligned zeroed allocation, release, zeroed reallocation, invalid second release");
    return 0;
}

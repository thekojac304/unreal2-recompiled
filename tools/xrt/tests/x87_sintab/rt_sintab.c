/* rt_sintab.c (x64) - FGlobalMath's sine table computed through the translated runtime's x87 model
 * (experiments/xrt/runtime/xrt_cpu.c, linked as is): the same operations the lifted code performs for
 *   fild dword i; fadd st, st; fmul qword [pi/16384]; fstp qword x; fld qword x; fsin; fstp dword out
 * Output format as hw_sintab.c. */
#include <stdio.h>
#include <stdlib.h>
#include "xrt_internal.h"

static const uint64_t STEP_BITS = 0x3F2921FB54442D18ull;

void xrt_log(const char* fmt, ...) { (void)fmt; }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    (void)c;
    fprintf(stderr, "xrt_fatal %d: %s\n", code, fmt);
    exit(code);
}

int main(void) {
    CPU c;
    double step;
    int i;
    static const uint64_t edges[] = {
        0x0000000000000000ull, 0x8000000000000000ull, 0x400921FB54442D18ull, 0x3FF921FB54442D18ull,
        0x401921FB54442D18ull, 0x4004000000000000ull, 0x412E848000000000ull, 0x43E0000000000000ull,
        0x43DFFFFFFFFFFFFFull, 0x7FF0000000000000ull, 0xFFF0000000000000ull, 0x7FF8000000000001ull, 0x0000000000000001ull};
    memset(&c, 0, sizeof c);
    memcpy(&step, &STEP_BITS, 8);
    c.fcw = 0x027F;
    printf("# fcw %04x\n", c.fcw);
    for (i = 0; i < 16384; i++) {
        double x;
        float f;
        uint32_t u;
        fpush(&c, (double)(int32_t)i);              /* fild dword */
        *ST(&c, 0) = *ST(&c, 0) + *ST(&c, 0);       /* fadd st, st */
        *ST(&c, 0) = *ST(&c, 0) * step;             /* fmul qword */
        x = *ST(&c, 0);                             /* fstp qword */
        fpop(&c);
        fpush(&c, x);                               /* fld qword */
        xrt_fsin(&c);                               /* fsin */
        f = (float)*ST(&c, 0);                      /* fstp dword */
        fpop(&c);
        memcpy(&u, &f, 4);
        printf("%d %08x\n", i, u);
    }
    for (i = 0; i < (int)(sizeof edges / sizeof edges[0]); i++) {
        double x, r;
        uint64_t rb;
        memcpy(&x, &edges[i], 8);
        fpush(&c, x);
        xrt_fsin(&c);
        r = *ST(&c, 0);
        fpop(&c);
        memcpy(&rb, &r, 8);
        printf("e%d %016llx %016llx %d\n", i, (unsigned long long)edges[i], (unsigned long long)rb, (c.fsw >> 10) & 1);
    }
    return 0;
}

/* hw_sintab.c (x86) - FGlobalMath's sine table computed on the hardware x87 with the engine's own instruction
 * sequence (Core.dll FGlobalMath::FGlobalMath, rva 0x3adb0..0x3adda and appSin, rva 0x16fa0):
 *   fild dword i; fadd st, st; fmul qword [pi/16384]; fstp qword x; fld qword x; fsin; fstp dword out
 * at the control word the engine runs with (0x027F). Output: one "<i> <float bits>" line per entry, plus extra
 * edge arguments as "e<k> <double bits> <float bits> <C2>". */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static const uint64_t STEP_BITS = 0x3F2921FB54442D18ull;   /* Core.dll .rdata 0x1016ddb0: the double nearest pi/16384 */

int main(void) {
    double step;
    unsigned short cw = 0x027F, cw_now;
    int i;
    static const uint64_t edges[] = {
        0x0000000000000000ull, 0x8000000000000000ull, 0x400921FB54442D18ull /* pi */, 0x3FF921FB54442D18ull /* pi/2 */,
        0x401921FB54442D18ull /* 2pi */, 0x4004000000000000ull /* 2.5 */, 0x412E848000000000ull /* 1e6 */,
        0x43E0000000000000ull /* 2^63 */, 0x43DFFFFFFFFFFFFFull /* below 2^63 */, 0x7FF0000000000000ull /* +inf */,
        0xFFF0000000000000ull /* -inf */, 0x7FF8000000000001ull /* qnan */, 0x0000000000000001ull /* denormal */};
    memcpy(&step, &STEP_BITS, 8);
    __asm { fldcw cw }
    __asm { fnstcw cw_now }
    printf("# fcw %04x\n", cw_now);
    for (i = 0; i < 16384; i++) {
        double x;
        float f;
        uint32_t u;
        __asm {
            fild dword ptr [i]
            fadd st(0), st(0)
            fmul qword ptr [step]
            fstp qword ptr [x]
            fld qword ptr [x]
            fsin
            fstp dword ptr [f]
        }
        memcpy(&u, &f, 4);
        printf("%d %08x\n", i, u);
    }
    for (i = 0; i < (int)(sizeof edges / sizeof edges[0]); i++) {
        double x, r;
        unsigned short sw;
        uint64_t rb;
        memcpy(&x, &edges[i], 8);
        __asm {
            fld qword ptr [x]
            fsin
            fnstsw word ptr [sw]
            fstp qword ptr [r]
        }
        memcpy(&rb, &r, 8);
        printf("e%d %016llx %016llx %d\n", i, (unsigned long long)edges[i], (unsigned long long)rb, (sw >> 10) & 1);
    }
    return 0;
}

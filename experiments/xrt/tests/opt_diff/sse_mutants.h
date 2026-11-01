/* sse_mutants.h - deliberately broken variants of the xlift --opt sse forms for run.py --mutations and forms_equiv.py
 * (forced into every lifted build; only a mutated lift refers to them). Never part of the game build. */
#ifndef SSE_MUTANTS_H
#define SSE_MUTANTS_H
#include "xrt.h"
/* float store 8 bytes wide (clobbers the next 4 bytes) / double store only 4 bytes wide */
XRT_INLINE void wrf32s_mut_wide(uint8_t* g, uint32_t a, float f) { wrf32s(g, a, f); wr32b(g, a + 4u, 0); }
XRT_INLINE void wrf64s_mut_narrow(uint8_t* g, uint32_t a, double d) { uint64_t u; memcpy(&u, &d, 8); wr32b(g, a, (uint32_t)u); }
/* compare without the unordered case (a NaN operand reads as "greater") / equal reported as "less" */
#define XFCOMPAREO_mut_nan(a, b) do { double a__ = (a), b__ = (b); fsw_ &= (uint16_t)~0x4500; \
        if (a__ < b__) fsw_ |= 0x0100; else if (a__ == b__) fsw_ |= 0x4000; } while (0)
#define XFCOMPAREO_mut_le(a, b) do { double a__ = (a), b__ = (b); fsw_ &= (uint16_t)~0x4500; \
        if (a__ <= b__) fsw_ |= 0x0100; else if (a__ == b__) fsw_ |= 0x4000; \
        else if (!(a__ > b__)) fsw_ |= 0x4500; } while (0)
XRT_INLINE void fcompareo_mut_nan(CPU* c, double a, double b) {
    c->fsw &= (uint16_t)~0x4500;
    if (a < b) c->fsw |= 0x0100; else if (a == b) c->fsw |= 0x4000;
}
XRT_INLINE void fcompareo_mut_le(CPU* c, double a, double b) {
    c->fsw &= (uint16_t)~0x4500;
    if (a <= b) c->fsw |= 0x0100; else if (a == b) c->fsw |= 0x4000; else if (!(a > b)) c->fsw |= 0x4500;
}
#endif

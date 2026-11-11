/* xrt.h - translated runtime (X1): guest CPU state, guest memory, flags, x87 model and the
 * interface between lifter-generated code (tools/xrt/xlift.py) and the host runtime.
 *
 * Address spaces are kept apart deliberately:
 *   guest address  uint32_t, what translated code computes and stores in guest memory
 *   host pointer   void*, only ever obtained with G2H() and converted back with xrt_h2g()
 *   guest handle   uint32_t values handed to guest code for host objects (see xrt_handle_*)
 * Guest memory is one 4 GB host reservation: guest address a lives at host xrt_g + a, so no host
 * pointer is ever narrowed. The low 64 KB stay unmapped so guest null dereferences fault and are
 * reported (xrt_diag.c), like on Windows. The guest never maps memory at or above 0x80000000 (the
 * 32-bit user-mode layout, asserted by xrt_commit), and a 2 GB guard is reserved below the window:
 * translated code may therefore compute a [reg + disp] access as the 64-bit sum (xlift --opt addr64,
 * the helpers below take a 64-bit address) - a wrapped guest address faults in either form.
 *
 * Portable C99 except where marked; host Win32 services are confined to the xrt_*.c adapters. */
#ifndef XRT_H
#define XRT_H
/* The guest load/store, stack, flag and x87 helpers are forced inline: at /O2 MSVC otherwise leaves
 * thousands of out-of-line calls to them in large translated functions. */
#if defined(XRT_NO_FORCE_INLINE)   /* units whose compile time explodes when forced */
#define XRT_INLINE static inline
#elif defined(_MSC_VER)
#define XRT_INLINE static __forceinline
#else
#define XRT_INLINE static inline __attribute__((always_inline))
#endif
#include <math.h>
#include <stdint.h>
#include <string.h>

/* XRT_GAME_DLL: the translated modules built as a DLL on the player's machine (tools/xrt/setup), loaded by the
 * prebuilt player. The few runtime variables translated code reads are then imported from the player executable;
 * without XRT_GAME_DLL these are the ordinary declarations, so every existing build is unchanged. */
#ifdef XRT_GAME_DLL
#define XRT_SHARED __declspec(dllimport)
#else
#define XRT_SHARED
#endif

enum { EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI };

#define XRT_HIST 64

typedef struct XrtThread XrtThread;

typedef struct CPU {
    uint32_t r[8];
    uint32_t cf, pf, zf, sf, of, df;    /* AF is not modelled: no instruction in the lifted modules reads it */
    uint32_t eflags_rest;               /* other EFLAGS bits as last written (not read by lifted code) */
    uint32_t fs_base;                   /* guest address of this thread's TEB */
    uint32_t rv;                        /* return address popped by the most recent ret (checked by callers) */
    uint32_t pc;                        /* guest address of the instruction being executed (diagnostics) */
    double st[8];                       /* x87 registers as host doubles: exact for PC=53-bit (CW 0x027F) */
    uint32_t top;
    uint16_t fcw, fsw;
    uint32_t hist[XRT_HIST];            /* ring of recent function entries (diagnostics) */
    uint32_t hpos;
    uint32_t world_floor;               /* world observer (xrt_events.c): lowest guest esp at which a pending observed
                                           call returns; 0 unknown, 0xFFFFFFFF none pending. Read inline after indirect
                                           calls (ICALLI). Fills the alignment hole before `thread`: sizeof(CPU) stays
                                           416, the monitor record's CPU image (monitor.h). */
    XrtThread* thread;
} CPU;

typedef void (*XrtFn)(CPU*);          /* host adapters: they set c->rv themselves */
/* Translated functions. xlift --opt rv (the protos header defines XRT_RV_ABI): they return the address they returned to
 * instead of storing c->rv, so a call compares a register; the runtime stores the value into c->rv when it calls one
 * (XRT_CALL_LIFTED), which keeps every reader of c->rv after a dispatched call unchanged. All modules of a build agree. */
#ifdef XRT_RV_ABI
typedef uint32_t XrtLiftedRet;
typedef uint32_t (*XrtLiftedFn)(CPU*);
#define XRT_CALL_LIFTED(fn, c) ((c)->rv = (fn)(c))
#define XRT_LIFTED_RETURN(c) return (c)->rv
#define XRT_TAIL(call) return (call)
#else
typedef void XrtLiftedRet;
typedef void (*XrtLiftedFn)(CPU*);
#define XRT_CALL_LIFTED(fn, c) ((fn)(c))
#define XRT_LIFTED_RETURN(c) return
#define XRT_TAIL(call) do { (call); return; } while (0)
#endif

/* ---------------------------------------------------------------- guest memory */
#define XRT_GUEST_GUARD_BELOW 0x80000000ull   /* reserved, never committed: wrapped addr64 accesses fault here */
#define XRT_GUEST_WINDOW 0x100010000ull        /* 4 GB + 64 KB: the top 64 KB catch [reg + disp] past the end */
extern XRT_SHARED uint8_t* xrt_g;      /* host address of guest address 0 */
#define G2H(a) ((void*)(xrt_g + (uint32_t)(a)))
uint32_t xrt_h2g(const void* p);       /* fatal if p is not inside guest memory */

XRT_INLINE uint8_t rd8(uint64_t a) { return xrt_g[a]; }
XRT_INLINE uint16_t rd16(uint64_t a) { uint16_t v; memcpy(&v, xrt_g + a, 2); return v; }
XRT_INLINE uint32_t rd32(uint64_t a) { uint32_t v; memcpy(&v, xrt_g + a, 4); return v; }
XRT_INLINE uint64_t rd64(uint64_t a) { uint64_t v; memcpy(&v, xrt_g + a, 8); return v; }
XRT_INLINE void wr8(uint64_t a, uint8_t v) { xrt_g[a] = v; }
XRT_INLINE void wr16(uint64_t a, uint16_t v) { memcpy(xrt_g + a, &v, 2); }
XRT_INLINE void wr32(uint64_t a, uint32_t v) { memcpy(xrt_g + a, &v, 4); }
XRT_INLINE void wr64(uint64_t a, uint64_t v) { memcpy(xrt_g + a, &v, 8); }
XRT_INLINE float rdf32(uint64_t a) { float f; memcpy(&f, xrt_g + a, 4); return f; }
XRT_INLINE double rdf64(uint64_t a) { double d; memcpy(&d, xrt_g + a, 8); return d; }
XRT_INLINE void wrf32(uint64_t a, float f) { memcpy(xrt_g + a, &f, 4); }
XRT_INLINE void wrf64(uint64_t a, double d) { memcpy(xrt_g + a, &d, 8); }

XRT_INLINE void push32(CPU* c, uint32_t v) { c->r[ESP] -= 4; wr32(c->r[ESP], v); }
XRT_INLINE uint32_t pop32(CPU* c) { uint32_t v = rd32(c->r[ESP]); c->r[ESP] += 4; return v; }

/* The same accesses through an explicit base (xlift --opt base): a translated function copies xrt_g into a local
 * once, because every guest store goes through uint8_t* and may alias the global, so the compiler reloads xrt_g
 * before each access otherwise. The guest address arithmetic and access widths are identical. */
XRT_INLINE uint8_t rd8b(const uint8_t* g, uint64_t a) { return g[a]; }
XRT_INLINE uint16_t rd16b(const uint8_t* g, uint64_t a) { uint16_t v; memcpy(&v, g + a, 2); return v; }
XRT_INLINE uint32_t rd32b(const uint8_t* g, uint64_t a) { uint32_t v; memcpy(&v, g + a, 4); return v; }
XRT_INLINE uint64_t rd64b(const uint8_t* g, uint64_t a) { uint64_t v; memcpy(&v, g + a, 8); return v; }
XRT_INLINE void wr8b(uint8_t* g, uint64_t a, uint8_t v) { g[a] = v; }
XRT_INLINE void wr16b(uint8_t* g, uint64_t a, uint16_t v) { memcpy(g + a, &v, 2); }
XRT_INLINE void wr32b(uint8_t* g, uint64_t a, uint32_t v) { memcpy(g + a, &v, 4); }
XRT_INLINE void wr64b(uint8_t* g, uint64_t a, uint64_t v) { memcpy(g + a, &v, 8); }
XRT_INLINE float rdf32b(const uint8_t* g, uint64_t a) { float f; memcpy(&f, g + a, 4); return f; }
XRT_INLINE double rdf64b(const uint8_t* g, uint64_t a) { double d; memcpy(&d, g + a, 8); return d; }
XRT_INLINE void wrf32b(uint8_t* g, uint64_t a, float f) { memcpy(g + a, &f, 4); }
XRT_INLINE void wrf64b(uint8_t* g, uint64_t a, double d) { memcpy(g + a, &d, 8); }
/* xlift --opt sse: the same float/double guest stores as single SSE stores. Through memcpy, MSVC stores a float or double
 * via a stack temporary (movss/movsd to the stack, integer reload, integer store), a store-forwarding round trip per
 * fst/fstp that often sits on a dependency chain (fstp to a stack slot, fld of it a few instructions later). The stored
 * bytes are the value's bits either way (no conversion happens in the store). */
#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_AMD64))
#include <emmintrin.h>
XRT_INLINE void wrf32s(uint8_t* g, uint64_t a, float f) { _mm_store_ss((float*)(g + a), _mm_set_ss(f)); }
XRT_INLINE void wrf64s(uint8_t* g, uint64_t a, double d) { _mm_storel_pd((double*)(g + a), _mm_set_sd(d)); }
#else
XRT_INLINE void wrf32s(uint8_t* g, uint64_t a, float f) { wrf32b(g, a, f); }
XRT_INLINE void wrf64s(uint8_t* g, uint64_t a, double d) { wrf64b(g, a, d); }
#endif
XRT_INLINE void push32b(uint8_t* g, CPU* c, uint32_t v) { c->r[ESP] -= 4; wr32b(g, c->r[ESP], v); }
XRT_INLINE uint32_t pop32b(const uint8_t* g, CPU* c) { uint32_t v = rd32b(g, c->r[ESP]); c->r[ESP] += 4; return v; }

/* ---------------------------------------------------------------- flags */
XRT_INLINE uint32_t parity8(uint32_t v) { v &= 0xFF; v ^= v >> 4; v ^= v >> 2; v ^= v >> 1; return (~v) & 1; }
XRT_INLINE uint32_t msb(uint32_t v, int bits) { return (v >> (bits - 1)) & 1; }
XRT_INLINE uint32_t bmask(int bits) { return bits == 32 ? 0xFFFFFFFFu : ((1u << bits) - 1); }
XRT_INLINE void fl_szp(CPU* c, uint32_t res, int bits) {
    res &= bmask(bits);
    c->zf = res == 0; c->sf = msb(res, bits); c->pf = parity8(res);
}
XRT_INLINE void fl_logic(CPU* c, uint32_t res, int bits) { fl_szp(c, res, bits); c->cf = 0; c->of = 0; }
XRT_INLINE void fl_add(CPU* c, uint32_t a, uint32_t b, uint32_t res, int bits) {
    uint32_t m = bmask(bits);
    a &= m; b &= m; res &= m;
    c->cf = res < a; fl_szp(c, res, bits);
    c->of = msb((a ^ res) & (b ^ res), bits);
}
XRT_INLINE void fl_sub(CPU* c, uint32_t a, uint32_t b, uint32_t res, int bits) {
    uint32_t m = bmask(bits);
    a &= m; b &= m; res &= m;
    c->cf = a < b; fl_szp(c, res, bits);
    c->of = msb((a ^ b) & (a ^ res), bits);
}

/* ---------------------------------------------------------------- x87 (host-double model) */
XRT_INLINE double* ST(CPU* c, int i) { return &c->st[(c->top + i) & 7]; }
XRT_INLINE void fpush(CPU* c, double v) { c->top = (c->top - 1) & 7; c->st[c->top] = v; }
XRT_INLINE void fpop(CPU* c) { c->top = (c->top + 1) & 7; }
double xrt_fround(CPU* c, double v);                    /* round to integer per FCW.RC */
int64_t xrt_fist64(CPU* c, double v);                   /* integer indefinite on overflow/NaN */
int32_t xrt_fist32(CPU* c, double v);
int16_t xrt_fist16(CPU* c, double v);
XRT_INLINE void fcompare(CPU* c, double a, double b) { /* C0 (bit 8), C2 (bit 10), C3 (bit 14) */
    c->fsw &= (uint16_t)~0x4500;
    if (isnan(a) || isnan(b)) c->fsw |= 0x4500;
    else if (a < b) c->fsw |= 0x0100;
    else if (a == b) c->fsw |= 0x4000;
}
/* xlift --opt sse: the same result without isnan(), which /fp:strict compiles to an out-of-line _dclass call (two per
 * compare, clobbering xmm0-5 in the middle of x87 code). With a NaN operand none of <, == and > holds, so the third
 * test is exactly the unordered case; otherwise exactly one of the three holds. */
XRT_INLINE void fcompareo(CPU* c, double a, double b) {
    c->fsw &= (uint16_t)~0x4500;
    if (a < b) c->fsw |= 0x0100;
    else if (a == b) c->fsw |= 0x4000;
    else if (!(a > b)) c->fsw |= 0x4500;
}
XRT_INLINE uint16_t fstatus(CPU* c) { return (uint16_t)((c->fsw & ~0x3800) | ((c->top & 7) << 11)); }
/* The same operations with TOP and the status word in the translated function's locals ft_ and fsw_ (xlift --opt x87).
 * Without them every fpush/fpop/ST was a read-modify-write of c->top through memory that guest stores may alias, a
 * serial store-forwarding chain. ST values stay in c->st (written through); the locals are stored to c->top/c->fsw
 * at the register spill points and around the x87 helpers above, which use the CPU form. */
#define XST(i) (&c->st[(ft_ + (uint32_t)(i)) & 7u])
#define XFPUSH(v) do { double v__ = (v); ft_ = (ft_ - 1u) & 7u; c->st[ft_] = v__; } while (0)
#define XFPOP() (ft_ = (ft_ + 1u) & 7u)
#define XFSTATUS() ((uint16_t)((fsw_ & ~0x3800) | ((ft_ & 7u) << 11)))
#define XFCOMPARE(a, b) do { double a__ = (a), b__ = (b); fsw_ &= (uint16_t)~0x4500; \
        if (isnan(a__) || isnan(b__)) fsw_ |= 0x4500; else if (a__ < b__) fsw_ |= 0x0100; \
        else if (a__ == b__) fsw_ |= 0x4000; } while (0)
#define XFCOMPAREO(a, b) do { double a__ = (a), b__ = (b); fsw_ &= (uint16_t)~0x4500; \
        if (a__ < b__) fsw_ |= 0x0100; else if (a__ == b__) fsw_ |= 0x4000; \
        else if (!(a__ > b__)) fsw_ |= 0x4500; } while (0)
void xrt_fsin(CPU* c);
void xrt_fcos(CPU* c);
void xrt_fptan(CPU* c);
void xrt_fpatan(CPU* c);
void xrt_fyl2x(CPU* c);
void xrt_f2xm1(CPU* c);
void xrt_fscale(CPU* c);
void xrt_fsqrt(CPU* c);
void xrt_fldcw(CPU* c, uint16_t cw);              /* only PC=53-bit, RC=nearest is modelled; else fatal */
#define XRT_PI 3.14159265358979323846
#define XRT_L2E 1.44269504088896340736
#define XRT_L2T 3.32192809488736234787
#define XRT_LG2 0.30102999566398119521
#define XRT_LN2 0.69314718055994530942

/* ---------------------------------------------------------------- privileged-ish instructions */
void xrt_cpuid(CPU* c);                                 /* documented guest CPU-feature policy */
void xrt_rdtsc(CPU* c);
/* xlift --opt rdtsc: the counter read inline in translated code. x86 hosts use the instruction; others a runtime
 * counter (xrt_cpu.c xrt_rdtsc64: ARM64 CNTVCT). */
#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
#include <intrin.h>
#define XRT_RDTSC() __rdtsc()
#elif defined(__x86_64__) || defined(__i386__)
#define XRT_RDTSC() __builtin_ia32_rdtsc()
#else
uint64_t xrt_rdtsc64(void);
#define XRT_RDTSC() xrt_rdtsc64()
#endif

/* ---------------------------------------------------------------- control transfer */
#if defined(_MSC_VER)
#define XRT_NORETURN __declspec(noreturn)
#else
#define XRT_NORETURN __attribute__((noreturn))
#endif
XrtLiftedRet xrt_icall(CPU* c, uint32_t target, uint32_t site);   /* indirect call (return addr already pushed) */
XrtLiftedRet xrt_ijmp(CPU* c, uint32_t target, uint32_t site);    /* indirect tail jump */
XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* why);
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected);
XRT_NORETURN void xrt_div0(CPU* c, uint32_t site);

/* Every translated function entry records history and is a preemption point: when another guest thread
 * waits for the execution baton and the time slice has expired, the runtime hands the baton over here. */
extern XRT_SHARED volatile long xrt_preempt_req;
void xrt_preempt(CPU* c);
/* XRT_LEAN_ENTER (dev.py build --lean): no per-entry history ring (fatal dumps keep their guest-stack scan); the
 * preemption check stays, it is what makes function entries the scheduling points. */
#ifdef XRT_LEAN_ENTER
#define XRT_ENTER(va) do { if (xrt_preempt_req) xrt_preempt(c); } while (0)
#else
#define XRT_ENTER(va) do { c->hist[c->hpos++ & (XRT_HIST - 1)] = (va); if (xrt_preempt_req) xrt_preempt(c); } while (0)
#endif
#ifdef XRT_NO_PC
#define P(va) ((void)0)
#else
#define P(va) (c->pc = (va))
#endif
#ifdef XRT_RV_ABI
#define CALL(fn, nxt, site) do { uint32_t rv__; push32(c, (nxt)); rv__ = fn(c); \
                                 if (rv__ != (nxt)) { c->rv = rv__; xrt_badret(c, (site), (nxt)); } } while (0)
#else
#define CALL(fn, nxt, site) do { push32(c, (nxt)); fn(c); if (c->rv != (nxt)) xrt_badret(c, (site), (nxt)); } while (0)
#endif
/* Indirect calls. ICALL goes through xrt_icall/dispatch. ICALLI (xlift --opt icall) expands the hit path of the
 * runtime's call-target cache (xrt_loader.c) at the call site, so each guest call site has its own host indirect call:
 * through the single call in dispatch the branch predictor saw one site for all of them. Any module map/unmap advances
 * xrt_call_cache_gen; misses, imports, observed targets (flags) and stale entries take xrt_icall as before. After a
 * cached call the world-observer return check dispatch makes is made inline (c->world_floor; xrt_icall_after is the
 * same check as a function, kept for older generated code). */
typedef struct { uint32_t va, gen; XrtLiftedFn fn; unsigned flags; } XrtCallCache;
extern XRT_SHARED XrtCallCache xrt_call_cache[65536];
extern XRT_SHARED uint32_t xrt_call_cache_gen;
#define XRT_CALL_CACHE_SLOT(t) ((((t) >> 2) ^ ((t) >> 18)) & 65535)
void xrt_icall_after(CPU* c);
void xrt_world_return(CPU* c);
#ifdef XRT_RV_ABI
#define ICALL(t, nxt, site) do { uint32_t t__ = (t), rv__; push32(c, (nxt)); rv__ = xrt_icall(c, t__, (site)); \
                                 if (rv__ != (nxt)) { c->rv = rv__; xrt_badret(c, (site), (nxt)); } } while (0)
#define ICALLI(t, nxt, site) do { uint32_t t__ = (t), rv__; const XrtCallCache* e__ = &xrt_call_cache[XRT_CALL_CACHE_SLOT(t__)]; \
                                 push32(c, (nxt)); \
                                 if (e__->va == t__ && e__->gen == xrt_call_cache_gen && !e__->flags) { rv__ = e__->fn(c); \
                                     if (c->r[ESP] >= c->world_floor) { c->rv = rv__; xrt_world_return(c); } } \
                                 else rv__ = xrt_icall(c, t__, (site)); \
                                 if (rv__ != (nxt)) { c->rv = rv__; xrt_badret(c, (site), (nxt)); } } while (0)
#define RET(n) do { uint32_t rv__ = pop32(c); c->r[ESP] += (n); return rv__; } while (0)
#else
#define ICALL(t, nxt, site) do { uint32_t t__ = (t); push32(c, (nxt)); xrt_icall(c, t__, (site)); \
                                 if (c->rv != (nxt)) xrt_badret(c, (site), (nxt)); } while (0)
#define ICALLI(t, nxt, site) do { uint32_t t__ = (t); const XrtCallCache* e__ = &xrt_call_cache[XRT_CALL_CACHE_SLOT(t__)]; \
                                 push32(c, (nxt)); \
                                 if (e__->va == t__ && e__->gen == xrt_call_cache_gen && !e__->flags) { e__->fn(c); \
                                     if (c->r[ESP] >= c->world_floor) xrt_world_return(c); } \
                                 else xrt_icall(c, t__, (site)); \
                                 if (c->rv != (nxt)) xrt_badret(c, (site), (nxt)); } while (0)
#define RET(n) do { c->rv = pop32(c); c->r[ESP] += (n); return; } while (0)
#endif

/* ---------------------------------------------------------------- lazy guest pc (xlift --opt lazypc)
 * Translated code then stores c->pc only before calls, traps, marks and the helpers that read it; the instruction of
 * a guest memory fault is recovered from the host pc through the chunk's source line table (xrt_diag.c: PDB line
 * information -> file and line -> guest address). A chunk compiled with XRT_PCLINES registers its table at start-up. */
typedef struct XrtPcLine { uint32_t line, va; } XrtPcLine;
void xrt_pclines_register(const char* file, const XrtPcLine* lines, uint32_t n);
#if defined(XRT_PCLINES) && defined(_MSC_VER)
#define XRT_PCLINES_REGISTER(tab, n, file) \
    static void tab##_reg(void) { xrt_pclines_register(file, tab, n); } \
    __pragma(section(".CRT$XCU", read)) __declspec(allocate(".CRT$XCU")) void (*tab##_regp)(void) = tab##_reg; \
    __pragma(comment(linker, "/include:" #tab "_regp"))
#elif defined(XRT_PCLINES)
#define XRT_PCLINES_REGISTER(tab, n, file) \
    __attribute__((constructor)) static void tab##_reg(void) { xrt_pclines_register(file, tab, n); }
#else
#define XRT_PCLINES_REGISTER(tab, n, file) typedef int tab##_unused_t
#endif

/* ---------------------------------------------------------------- C++ exception landing pads (runtime/xrt_eh.c)
 * A translated function that registers an EH node (`mov fs:[0], esp`) declares a pad. XRT_EH_REGISTER() links it,
 * keyed by the node, into the thread's landing stack and sets the host resume point; when the exception
 * dispatcher completes a catch of this frame it longjmps here and xrt_eh_landed() runs the translated code at the
 * catch's continuation address (the rest of the function). XRT_EH_POP() unlinks the pad on every exit. */
#ifdef XRT_EH_FRAMES
/* xlift --opt ehframe (the protos header defines XRT_EH_FRAMES; dev.py builds the runtime alike): no setjmp. The pad
 * only links the frame; when a catch of this frame completes, the dispatcher unwinds the host stack to the frame that
 * holds the pad (RtlUnwindEx, as longjmp does), runs the continuation there and returns from that frame with its result
 * (runtime xrt_eh.c, xrt_eh_land.asm). XRT_EH_FN (noinline) keeps that frame the translated function's own. Round 4
 * (2026-11-02): setjmp (~25 stores), the 256-byte jmp_buf per frame and the monitor marks cost 4-7% of gameplay frames
 * and 18-24% of UI-heavy ones. */
typedef struct XrtEhPad {
    uint32_t node;                 /* guest address of the registered EH node */
    uint32_t resume;               /* continuation address, set by the dispatcher before landing */
    int active;
    int kind;                      /* 0: function frame, 1: active catch block (dispatcher-internal) */
    int host_calls;                /* thread's host->guest call depth when linked */
    unsigned xm_depth;             /* monitor scope depth when linked (scopes above it are aborted at landing) */
    struct XrtEhPad* prev;
    uint64_t host_ret;             /* landing only: the frame's call-site return address (xrt_eh_land.asm reads it) */
} XrtEhPad;
#define XRT_EH_FN __declspec(noinline)
/* Beta batch: the link/unlink is inline (R4: ~1.7 ns per guarded call in xrt_eh_register/xrt_eh_pop calls, ~9% of
 * UI-heavy frames). The prefix of the runtime's XrtThread (static asserts in xrt_internal.h) and the monitor's scope
 * depth are what pad_push used; an out-of-order unlink still goes to xrt_eh_pop for its fatal diagnostic. */
typedef struct { CPU cpu; int host_calls; XrtEhPad* eh_pads; } XrtThreadEh;
#ifdef XRT_GAME_DLL   /* a thread-local variable cannot be imported: the monitor's accessor (same value) */
unsigned xm_depth(void);
#define XM_TLS_DEPTH xm_depth()
#else
extern __declspec(thread) unsigned xm_tls_depth;
#define XM_TLS_DEPTH xm_tls_depth
#endif
#define XRT_EH_REGISTER() do { XrtThreadEh* t_ = (XrtThreadEh*)c->thread; eh_.node = c->r[ESP]; if (!eh_.active) { \
        eh_.kind = 0; eh_.host_calls = t_->host_calls; eh_.xm_depth = XM_TLS_DEPTH; eh_.prev = t_->eh_pads; \
        eh_.active = 1; t_->eh_pads = &eh_; } } while (0)
#define XRT_EH_POP() do { if (eh_.active) { XrtThreadEh* t_ = (XrtThreadEh*)c->thread; \
        if (t_->eh_pads == &eh_) { t_->eh_pads = eh_.prev; eh_.active = 0; } else xrt_eh_pop(c, &eh_); } } while (0)
#else
#include <setjmp.h>
typedef struct XrtEhPad {
    jmp_buf jb;
    uint32_t node;                 /* guest address of the registered EH node */
    uint32_t resume;               /* continuation address, set by the dispatcher before longjmp */
    int active;
    int kind;                      /* 0: function frame, 1: active catch block (dispatcher-internal) */
    int host_calls;                /* thread's host->guest call depth when linked */
    struct XrtEhPad* prev;
} XrtEhPad;
#define XRT_EH_FN
#define XRT_EH_REGISTER() do { xrt_eh_register(c, &eh_); if (setjmp(eh_.jb)) { XRT_TAIL(xrt_eh_landed(c, &eh_)); } } while (0)
#endif
void xrt_eh_register(CPU* c, XrtEhPad* pad);
XrtLiftedRet xrt_eh_landed(CPU* c, XrtEhPad* pad);
void xrt_eh_pop(CPU* c, XrtEhPad* pad);
#define XRT_EH_DECL XrtEhPad eh_; eh_.active = 0
#ifndef XRT_EH_FRAMES
#define XRT_EH_POP() do { if (eh_.active) xrt_eh_pop(c, &eh_); } while (0)
#endif

/* ---------------------------------------------------------------- evidence instrumentation (tools/xrt/marks.json)
 * Marks and watches only record events (xrt_events.c); they never change guest state. */
#define XRT_MARK_CALLERS 32
typedef struct XrtMark {
    uint32_t va;
    const char* name;
    int capture;                   /* guest register recorded with each event, or -1 */
    volatile long count;           /* executions (runtime) */
    uint32_t callers[XRT_MARK_CALLERS];   /* distinct [esp] values seen (return address at a function entry) */
    int ncallers;
} XrtMark;
typedef struct XrtWatchDef {
    uint32_t addr, size;
    const char* name;
    uint32_t last;                 /* value after the last recorded store or initial value (runtime) */
    int armed;
    uint64_t stores;
} XrtWatchDef;
void xrt_mark(CPU* c, XrtMark* m);
void xrt_watch_store(CPU* c, XrtWatchDef* w, uint32_t site);
#define XRT_MARK(m) xrt_mark(c, (m))

/* ---------------------------------------------------------------- generated module descriptors */
typedef struct XrtFuncEntry { uint32_t va; XrtLiftedFn fn; } XrtFuncEntry;
typedef struct XrtLiftedModule {
    const char* name;              /* file name, e.g. "Core.dll" */
    uint32_t base;                 /* image base the code was lifted for */
    uint32_t size;
    const char* sha256;            /* of the original file the code was lifted from */
    const XrtFuncEntry* funcs;     /* sorted by va */
    uint32_t nfuncs;
    uint32_t ntraps;               /* static traps emitted (unsupported code, reached => fatal) */
    uint8_t* hits;                 /* hits[k] != 0 once funcs[k] has been entered (evidence) */
    XrtMark* marks;                /* evidence marks and watches compiled into this module's code */
    uint32_t nmarks;
    XrtWatchDef* watches;
    uint32_t nwatches;
    const char* marks_sha256;      /* SHA-256 of the marks file the code was lifted with ("" if none) */
} XrtLiftedModule;

#endif

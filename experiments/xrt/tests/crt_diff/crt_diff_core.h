/* crt_diff_core.h - shared driver of the msvcr70 differential test (see README.md).
 *
 * Included by ref.c (x86: calls the real msvcr70.dll) and cand.c (x64: calls the runtime's adapters and
 * xrt_wformat over guest memory). The includer provides:
 *   typedef uint32_t Ptr;                     address as the callee sees it (real x86 / guest)
 *   static void* H(Ptr p);                    host pointer for an address in the test arena
 *   static Ptr arena_lo, arena_hi;            test arena [lo, hi) (set before run_corpus)
 *   static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc);   cdecl call
 *   static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc);      variadic call
 *   static uint32_t call_sprintf(Ptr buf, Ptr fmt, const uint32_t* block, uint32_t* exc);   narrow sprintf
 *   static int probe_too_long(Ptr fmt, Ptr va, uint32_t limit, uint32_t* exc);   narrow output >= limit chars?
 *   static int bounded_available(int bf);     1 if bounded function bf can be called (candidate: adapter exists)
 *   static uint32_t call_bounded(int bf, Ptr buf, uint32_t count, Ptr fmt, Ptr va, const uint32_t* block,
 *                                uint32_t* exc);   _snprintf (varargs from block) / _vsnprintf / _vsnwprintf (va)
 *   static int dep_available(int d);          1 if dependency function d can be called (candidate: adapter exists)
 *   static uint32_t call_dep(int d, const uint32_t* args, int nargs, uint32_t* exc);   cdecl call, at most 4 args;
 *                                             sets the thread's Win32 last error to LE_SENTINEL just before the call
 *                                             and stores its value right after the call in dep_last_error
 *   static Ptr cmp_ptr(int kind);             qsort comparator `kind` as the callee sees it (it runs cmp_eval)
 *   static Ptr iob_base(void);                address of msvcr70's _iob (20 FILEs of 32 bytes) as the callee sees it
 *   static void flush_stdout(void);
 * Both sides read the same corpus and write the same result format; compare.py diffs them. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { F_VSNWPRINTF, F_WCSLEN, F_WCSCPY, F_WCSCAT, F_WCSNCPY, F_WCSCMP, F_WCSNCMP, F_WCSICMP, F_WCSNICMP,
       F_WCSCHR, F_WCSRCHR, F_WCSSTR, F_WCSUPR, F_WTOI, F_RAND, F_SRAND, F_MEMMOVE, F_COUNT };
static const char* const fn_names[F_COUNT] = {
    "_vsnwprintf", "wcslen", "wcscpy", "wcscat", "wcsncpy", "wcscmp", "wcsncmp", "_wcsicmp", "_wcsnicmp",
    "wcschr", "wcsrchr", "wcsstr", "_wcsupr", "_wtoi", "rand", "srand", "memmove"};
/* functions whose return value is a pointer into one of the argument buffers */
static const int fn_returns_ptr[F_COUNT] = {0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1};

#define NSLOT 8          /* %n targets */
#define BLOCKW 96        /* argument block words (unused words are 0) */
#define BIG 8192         /* "unbounded" _vsnwprintf buffer, in wide characters */
#define GUARD 8          /* sentinel characters after every output buffer */

#define ABIG 65536       /* narrow sprintf: outputs of ABIG characters or more are not run (sprintf is unbounded) */

/* bounded printf functions (B, K and E lines) */
enum { BF_SNPRINTF, BF_VSNPRINTF, BF_VSNWPRINTF, BF_COUNT };
static const char* const bf_names[BF_COUNT] = {"_snprintf", "_vsnprintf", "_vsnwprintf"};
static const uint32_t bf_unit[BF_COUNT] = {1, 1, 2};   /* bytes per character */
#define BMEASURE 16384   /* capacity, in characters, of the call that measures the full length L */
#define BPRE 16          /* guard bytes before the destination (0xA5) */
#define BPOST 16         /* guard bytes after the destination (0x5A); the destination itself is filled with 0xCC */

/* msvcr70 functions the original `ucc make` reaches from GlmLib.dll, Editor.dll and Core.dll (V, T, Q, Z, X and F
 * lines). A line that needs a function the candidate has no adapter for is reported PENDING, never compared. */
enum { D_VSPRINTF, D_STRRCHR, D_STRCHR, D_STRNCPY, D_STRICMP, D_ATOI, D_TOUPPER, D_QSORT, D_MALLOC, D_REALLOC,
       D_MSIZE, D_FREE, D_SETSE, D_GETCWD, D_FULLPATH, D_CHDIR, D_FINDFIRST, D_FINDNEXT, D_FINDCLOSE, D_FOPEN,
       D_FCLOSE, D_ERRNO, D_COUNT };
static const char* const d_names[D_COUNT] = {
    "vsprintf", "strrchr", "strchr", "strncpy", "_stricmp", "atoi", "toupper", "qsort", "malloc", "realloc",
    "_msize", "free", "?_set_se_translator@@YAP6AXIPAU_EXCEPTION_POINTERS@@@ZP6AXI0@Z@Z", "_getcwd", "_fullpath",
    "_chdir", "_findfirst", "_findnext", "_findclose", "fopen", "fclose", "_errno"};
/* qsort comparators (cmp_eval) */
enum { CMP_I32, CMP_DIFF, CMP_DESC, CMP_KEY, CMP_ZERO, CMP_COUNT };
static const char* const cmp_names[CMP_COUNT] = {"i32", "diff", "desc", "key", "zero"};

static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc);
static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc);
static uint32_t call_sprintf(Ptr buf, Ptr fmt, const uint32_t* block, uint32_t* exc);
static int probe_too_long(Ptr fmt, Ptr va, uint32_t limit, uint32_t* exc);
static int bounded_available(int bf);
static uint32_t call_bounded(int bf, Ptr buf, uint32_t count, Ptr fmt, Ptr va, const uint32_t* block, uint32_t* exc);
static int dep_available(int d);
static uint32_t call_dep(int d, const uint32_t* args, int nargs, uint32_t* exc);
static Ptr cmp_ptr(int kind);
static Ptr iob_base(void);
static void flush_stdout(void);
#define LE_SENTINEL 0x5555u      /* Win32 last error before every call_dep (non-zero: a call that never sets it shows) */
static uint32_t dep_last_error;  /* the thread's last error right after the latest call_dep */

static Ptr bump;
static Ptr slots;

static Ptr talloc(uint32_t n) {
    Ptr p = (bump + 15u) & ~15u;
    if ((uint64_t)p + n > arena_hi) {
        fprintf(stderr, "test arena exhausted\n");
        exit(3);
    }
    bump = p + n;
    memset(H(p), 0, n);
    return p;
}
static uint16_t r16(Ptr p) { uint16_t v; memcpy(&v, H(p), 2); return v; }
static uint32_t r32(Ptr p) { uint32_t v; memcpy(&v, H(p), 4); return v; }
static void w16(Ptr p, uint16_t v) { memcpy(H(p), &v, 2); }
static void w32(Ptr p, uint32_t v) { memcpy(H(p), &v, 4); }
static void fill16(Ptr p, uint32_t n, uint16_t v) { uint32_t i; for (i = 0; i < n; i++) w16(p + 2 * i, v); }

static int hexv(int ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    fprintf(stderr, "bad hex digit '%c'\n", ch);
    exit(3);
}
static uint64_t hexnum(const char* s, int ndig) {
    uint64_t v = 0;
    int i;
    for (i = 0; i < ndig; i++)
        v = v << 4 | (uint64_t)hexv(s[i]);
    return v;
}
/* "~" or hex of 16-bit units -> count; units written to out (may be NULL) */
static uint32_t hexunits(const char* s, uint16_t* out) {
    uint32_t n = 0;
    if (*s == '~')
        return 0;
    while (s[0] && s[0] != ',' && s[0] != ' ') {
        if (out)
            out[n] = (uint16_t)hexnum(s, 4);
        n++;
        s += 4;
    }
    return n;
}
static uint32_t hexbytes(const char* s, uint8_t* out) {
    uint32_t n = 0;
    if (*s == '~')
        return 0;
    while (s[0] && s[0] != ',' && s[0] != ' ') {
        if (out)
            out[n] = (uint8_t)hexnum(s, 2);
        n++;
        s += 2;
    }
    return n;
}
/* wide string with GUARD sentinel units after the terminator */
static Ptr put_wstr(const char* hex, uint32_t cap) {
    uint32_t n = hexunits(hex, NULL), i;
    uint16_t* tmp = (uint16_t*)malloc((n + 1) * 2);
    Ptr p;
    if (cap < n + 1)
        cap = n + 1;
    p = talloc((cap + GUARD) * 2);
    fill16(p, cap + GUARD, 0xCCCC);
    hexunits(hex, tmp);
    for (i = 0; i < n; i++)
        w16(p + 2 * i, tmp[i]);
    w16(p + 2 * n, 0);
    free(tmp);
    return p;
}
static Ptr put_astr(const char* hex) {
    uint32_t n = hexbytes(hex, NULL);
    Ptr p = talloc(n + 1 + GUARD);
    memset(H(p), 0xCC, n + 1 + GUARD);
    hexbytes(hex, (uint8_t*)H(p));
    ((uint8_t*)H(p))[n] = 0;
    return p;
}

static void put_hex16(FILE* o, Ptr p, uint32_t n) {
    uint32_t i;
    if (!n) {
        fputc('~', o);
        return;
    }
    for (i = 0; i < n; i++)
        fprintf(o, "%04X", r16(p + 2 * i));
}
static void put_slots(FILE* o) {
    int i;
    fputs(" N=", o);
    for (i = 0; i < NSLOT; i++)
        fprintf(o, "%s%08X", i ? "," : "", r32(slots + 4u * (uint32_t)i));
}
static void reset_slots(void) {
    int i;
    for (i = 0; i < NSLOT; i++)
        w32(slots + 4u * (uint32_t)i, 0x5A5A5A5Au);
}

/* tokenizer over a mutable line */
static char* next_tok(char** s) {
    char* t;
    while (**s == ' ')
        (*s)++;
    if (!**s)
        return NULL;
    t = *s;
    while (**s && **s != ' ')
        (*s)++;
    if (**s)
        *(*s)++ = 0;
    return t;
}

/* printf-style argument list -> block words; returns 1 if a %n slot is referenced */
static int build_block(char** s, uint32_t* block) {
    int nw = 0, has_n = 0;
    char* t;
    memset(block, 0, BLOCKW * 4);
    while ((t = next_tok(s)) != NULL) {
        uint64_t q;
        if (nw > BLOCKW - 2) {
            fprintf(stderr, "argument block overflow\n");
            exit(3);
        }
        switch (t[0]) {
        case 'i': block[nw++] = (uint32_t)hexnum(t + 1, 8); break;
        case 'q':
        case 'd':
            q = hexnum(t + 1, 16);
            block[nw++] = (uint32_t)q;
            block[nw++] = (uint32_t)(q >> 32);
            break;
        case 'w': block[nw++] = put_wstr(t + 1, 0); break;
        case 'a': block[nw++] = put_astr(t + 1); break;
        case 'n': block[nw++] = slots + 4u * (uint32_t)atoi(t + 1); has_n = 1; break;
        case '0': block[nw++] = 0; break;
        case 'c': {   /* counted string: c<len>,<max>,<hexbytes|~|!> -> {u16 Length, u16 MaximumLength, char* Buffer} */
            char* p = t + 1;
            uint32_t len = (uint32_t)strtoul(p, &p, 10), mx, buf = 0;
            Ptr cs;
            mx = (uint32_t)strtoul(p + 1, &p, 10);
            p++;
            if (*p != '!') {
                uint32_t nb = hexbytes(p, NULL);
                buf = talloc(nb + GUARD);
                memset(H(buf), 0xCC, nb + GUARD);
                hexbytes(p, (uint8_t*)H(buf));
            }
            cs = talloc(8);
            w16(cs, (uint16_t)len);
            w16(cs + 2, (uint16_t)mx);
            w32(cs + 4, buf);
            block[nw++] = cs;
            break;
        }
        default:
            fprintf(stderr, "bad argument token %s\n", t);
            exit(3);
        }
    }
    return has_n;
}

static void exc_line(FILE* o, const char* kind, const char* id, uint32_t exc) {
    fprintf(o, "%s %s EXC=%08X\n", kind, id, exc);
}

static void run_printf(FILE* o, const char* id, Ptr fmt, Ptr va, int has_n) {
    Ptr big = talloc((BIG + GUARD) * 2);
    uint32_t exc = 0, args[4];
    int32_t L;
    int counts[4], nc = 0, k;
    fill16(big, BIG + GUARD, 0xCCCC);
    reset_slots();
    args[0] = big; args[1] = BIG; args[2] = fmt; args[3] = va;
    L = (int32_t)call_fn(F_VSNWPRINTF, args, 4, &exc);
    if (exc) {
        exc_line(o, "P", id, exc);
        return;
    }
    fprintf(o, "P %s L=%d T=", id, L);
    put_hex16(o, big, L >= 0 ? (uint32_t)L : BIG);
    fprintf(o, " Z=%s", L >= 0 && L < BIG ? (r16(big + 2u * (uint32_t)L) == 0 ? "1" : "0") : "-");
    if (has_n)
        put_slots(o);
    if (L >= 0) {
        int cand[4];
        cand[0] = 0; cand[1] = L - 1; cand[2] = L; cand[3] = L + 1;
        for (k = 0; k < 4; k++) {
            int j, dup = 0;
            if (cand[k] < 0)
                continue;
            for (j = 0; j < nc; j++)
                dup |= counts[j] == cand[k];
            if (!dup)
                counts[nc++] = cand[k];
        }
        for (k = 0; k < nc; k++) {
            uint32_t c = (uint32_t)counts[k], from = c > 3 ? c - 3 : 0, m = c < (uint32_t)L ? c : (uint32_t)L;
            Ptr b = talloc((c + GUARD) * 2);
            int32_t r;
            fill16(b, c + GUARD, 0xCCCC);
            reset_slots();
            args[0] = b; args[1] = c;
            r = (int32_t)call_fn(F_VSNWPRINTF, args, 4, &exc);
            if (exc) {
                fprintf(o, " ; %u:EXC%08X", c, exc);
                continue;
            }
            fprintf(o, " ; %u:%d:%d:", c, r, memcmp(H(b), H(big), m * 2) == 0);
            put_hex16(o, b + 2 * from, c + GUARD - from);
            if (has_n)
                put_slots(o);
        }
    }
    fputc('\n', o);
}

/* explicit counts (possibly far larger than the buffer: the outputs used are short, so the 64-character
 * buffer is never overrun; what is tested is how the count itself is interpreted) */
#define CBUF 64
static void run_counts(FILE* o, const char* id, char* counts, Ptr fmt, Ptr va) {
    uint32_t args[4], exc = 0;
    char* p = counts;
    fprintf(o, "C %s", id);
    while (*p) {
        uint32_t c = (uint32_t)strtoul(p, &p, 10);
        Ptr b = talloc((CBUF + GUARD) * 2);
        int32_t r;
        if (*p == ',')
            p++;
        fill16(b, CBUF + GUARD, 0xCCCC);
        args[0] = b; args[1] = c; args[2] = fmt; args[3] = va;
        r = (int32_t)call_fn(F_VSNWPRINTF, args, 4, &exc);
        if (exc) {
            fprintf(o, " ; %u:EXC%08X", c, exc);
            exc = 0;
            continue;
        }
        fprintf(o, " ; %u:%d:", c, r);
        put_hex16(o, b, CBUF + GUARD);
    }
    fputc('\n', o);
}

static uint64_t stdout_pos(void) {
    LARGE_INTEGER z, pos;
    z.QuadPart = 0;
    if (!SetFilePointerEx(GetStdHandle(STD_OUTPUT_HANDLE), z, &pos, FILE_CURRENT))
        return (uint64_t)-1;
    return (uint64_t)pos.QuadPart;
}

static void run_wprintf(FILE* o, const char* id, Ptr fmt, const uint32_t* block, int has_n) {
    uint64_t p0, p1;
    uint32_t exc = 0;
    int32_t r;
    flush_stdout();
    p0 = stdout_pos();
    reset_slots();
    r = (int32_t)call_wprintf(fmt, block, &exc);
    flush_stdout();
    p1 = stdout_pos();
    if (exc) {
        exc_line(o, "W", id, exc);
        return;
    }
    fprintf(o, "W %s R=%d O=%llu,%llu", id, r, (unsigned long long)p0, (unsigned long long)p1);
    if (has_n)
        put_slots(o);
    fputc('\n', o);
}

/* narrow sprintf. sprintf has no bound, so the output length is measured first (reference: the real
 * _vsnprintf into an ABIG buffer; candidate: the runtime's narrow formatter with a sink that refuses the
 * character after ABIG) and cases of ABIG characters or more are reported as SKIP on both sides. The buffer is
 * pre-filled with 0xCC; the line records the return value, the bytes up to and GUARD past the terminator, and
 * the %n targets. V lines do the same through vsprintf (buffer, format, va_list). */
static void run_sprintf(FILE* o, const char* kind, const char* id, Ptr fmt, Ptr va, const uint32_t* block, int has_n) {
    uint32_t exc = 0, n, i;
    Ptr buf;
    int32_t r;
    if (kind[0] == 'V' && !dep_available(D_VSPRINTF)) {
        fprintf(o, "V %s PENDING\n", id);
        return;
    }
    reset_slots();
    if (probe_too_long(fmt, va, ABIG, &exc)) {
        if (exc)
            exc_line(o, kind, id, exc);
        else
            fprintf(o, "%s %s SKIP\n", kind, id);
        return;
    }
    buf = talloc(ABIG + 1 + GUARD);
    memset(H(buf), 0xCC, ABIG + 1 + GUARD);
    reset_slots();
    if (kind[0] == 'V') {
        uint32_t a[3];
        a[0] = buf;
        a[1] = fmt;
        a[2] = va;
        r = (int32_t)call_dep(D_VSPRINTF, a, 3, &exc);
    } else {
        r = (int32_t)call_sprintf(buf, fmt, block, &exc);
    }
    if (exc) {
        exc_line(o, kind, id, exc);
        return;
    }
    fprintf(o, "%s %s R=%d B=", kind, id, r);
    n = r >= 0 && (uint32_t)r <= ABIG ? (uint32_t)r + 1 + GUARD : 64;
    for (i = 0; i < n; i++)
        fprintf(o, "%02X", ((uint8_t*)H(buf))[i]);
    if (has_n)
        put_slots(o);
    fputc('\n', o);
}

/* ---------------------------------------------------------------- bounded printf (_snprintf, _vsnprintf, _vsnwprintf)
 * A destination region is [BPRE guard bytes 0xA5][count characters 0xCC][BPOST guard bytes 0x5A]; the callee
 * gets the address after the front guard and `count`. Each result records the return value and the whole
 * region (both guards included), then the %n targets. */
static int bf_index(const char* name) {
    int i;
    for (i = 0; i < BF_COUNT; i++)
        if (!strcmp(bf_names[i], name))
            return i;
    fprintf(stderr, "unknown bounded function %s\n", name);
    exit(3);
}

static Ptr bregion(uint32_t bytes) {
    Ptr r = talloc(BPRE + bytes + BPOST);
    memset(H(r), 0xA5, BPRE);
    memset((uint8_t*)H(r) + BPRE, 0xCC, bytes);
    memset((uint8_t*)H(r) + BPRE + bytes, 0x5A, BPOST);
    return r;
}

static void put_region(FILE* o, Ptr r, uint32_t bytes) {
    uint32_t i;
    for (i = 0; i < BPRE + bytes + BPOST; i++)
        fprintf(o, "%02X", ((uint8_t*)H(r))[i]);
}

/* one call into a fresh region of `alloc` characters with capacity `count`; appends " ; count:ret:region" */
static void bounded_call(FILE* o, int bf, uint32_t alloc, uint32_t count, Ptr fmt, Ptr va, const uint32_t* block,
                         int has_n) {
    uint32_t exc = 0, bytes = alloc * bf_unit[bf];
    Ptr r = bregion(bytes);
    int32_t ret;
    reset_slots();
    ret = (int32_t)call_bounded(bf, r + BPRE, count, fmt, va, block, &exc);
    if (exc) {
        fprintf(o, " ; %u:EXC%08X", count, exc);
        return;
    }
    fprintf(o, " ; %u:%d:", count, ret);
    put_region(o, r, bytes);
    if (has_n)
        put_slots(o);
}

/* B <id> <func> <fmt> <arg>*: L is measured by the function itself with BMEASURE characters; then capacities
 * 0, 1, 2, L-1, L, L+1, L+2, L+16, each with an allocation of exactly that capacity */
static void run_bounded(FILE* o, const char* id, int bf, Ptr fmt, Ptr va, const uint32_t* block, int has_n) {
    uint32_t exc = 0, caps[8], ncap = 0, k;
    int32_t L;
    Ptr big;
    if (!bounded_available(bf)) {
        fprintf(o, "B %s PENDING\n", id);
        return;
    }
    big = bregion(BMEASURE * bf_unit[bf]);
    reset_slots();
    L = (int32_t)call_bounded(bf, big + BPRE, BMEASURE, fmt, va, block, &exc);
    if (exc) {
        exc_line(o, "B", id, exc);
        return;
    }
    if (L < 0 || L >= BMEASURE) {
        fprintf(o, "B %s SKIP R=%d\n", id, L);
        return;
    }
    {
        int32_t want[8];
        want[0] = 0; want[1] = 1; want[2] = 2; want[3] = L - 1; want[4] = L; want[5] = L + 1; want[6] = L + 2;
        want[7] = L + 16;
        for (k = 0; k < 8; k++) {
            uint32_t j;
            int dup = want[k] < 0;
            for (j = 0; j < ncap && !dup; j++)
                dup = caps[j] == (uint32_t)want[k];
            if (!dup)
                caps[ncap++] = (uint32_t)want[k];
        }
    }
    fprintf(o, "B %s L=%d", id, L);
    for (k = 0; k < ncap; k++)
        bounded_call(o, bf, caps[k], caps[k], fmt, va, block, has_n);
    fputc('\n', o);
}

/* K <id> <func> <alloc> <counts> <fmt> <arg>*: explicit counts (huge, wrapping) with a fixed allocation; the
 * outputs used are short enough for the allocation whatever the count */
static void run_kcounts(FILE* o, const char* id, int bf, uint32_t alloc, char* counts, Ptr fmt, Ptr va,
                        const uint32_t* block, int has_n) {
    char* p = counts;
    if (!bounded_available(bf)) {
        fprintf(o, "K %s PENDING\n", id);
        return;
    }
    fprintf(o, "K %s", id);
    while (*p) {
        uint32_t c = (uint32_t)strtoul(p, &p, 0);
        if (*p == ',')
            p++;
        bounded_call(o, bf, alloc, c, fmt, va, block, has_n);
    }
    fputc('\n', o);
}

/* E <id> <func> <dest: null|<alloc>> <count> <fmt|null> <arg>*: intentional error behaviour (NULL destination,
 * NULL format). compare.py runs every E line in its own pair of processes: on the candidate side a fault ends
 * the process, which compare.py records as the outcome. */
static void run_error(FILE* o, const char* id, int bf, const char* dest, uint32_t count, Ptr fmt, Ptr va,
                      const uint32_t* block) {
    uint32_t exc = 0, alloc = 0;
    Ptr r = 0;
    int32_t ret;
    if (!bounded_available(bf)) {
        fprintf(o, "E %s PENDING\n", id);
        return;
    }
    if (strcmp(dest, "null")) {
        alloc = (uint32_t)atoi(dest);
        r = bregion(alloc * bf_unit[bf]);
    }
    fflush(o);
    ret = (int32_t)call_bounded(bf, r ? r + BPRE : 0, count, fmt, va, block, &exc);
    if (exc) {
        exc_line(o, "E", id, exc);
        return;
    }
    fprintf(o, "E %s R=%d", id, ret);
    if (r) {
        fputc(' ', o);
        put_region(o, r, alloc * bf_unit[bf]);
    }
    fputc('\n', o);
}

static int fn_index(const char* name) {
    int i;
    for (i = 0; i < F_COUNT; i++)
        if (!strcmp(fn_names[i], name))
            return i;
    fprintf(stderr, "unknown function %s\n", name);
    exit(3);
}

/* S <id> <func> <arg>*: w<hex> string, b<cap>,<hex> buffer, u<hex8> integer, 0 null */
static void run_string(FILE* o, const char* id, char* s) {
    char* t = next_tok(&s);
    int f = fn_index(t), na = 0, nb = 0, k;
    uint32_t args[4], exc = 0, r;
    Ptr bufs[4];
    uint32_t caps[4];
    while ((t = next_tok(&s)) != NULL) {
        if (t[0] == 'w' || t[0] == 'b') {
            uint32_t cap = 0;
            char* h = t + 1;
            if (t[0] == 'b') {
                cap = (uint32_t)strtoul(h, &h, 10);
                h++;
            }
            if (cap < hexunits(h, NULL) + 1)
                cap = hexunits(h, NULL) + 1;
            bufs[nb] = put_wstr(h, cap);
            caps[nb] = cap;
            args[na++] = bufs[nb++];
        } else if (t[0] == 'u') {
            args[na++] = (uint32_t)hexnum(t + 1, 8);
        } else {
            args[na++] = 0;
        }
    }
    r = call_fn(f, args, na, &exc);
    if (exc) {
        exc_line(o, "S", id, exc);
        return;
    }
    fprintf(o, "S %s R=", id);
    if (fn_returns_ptr[f]) {
        int found = 0;
        if (!r)
            fputs("0", o), found = 1;
        for (k = 0; k < nb && !found; k++)
            if (r >= bufs[k] && r < bufs[k] + 2 * (caps[k] + GUARD)) {
                fprintf(o, "a%d+%u", k, (r - bufs[k]) / 2);
                found = 1;
            }
        if (!found)
            fprintf(o, "?%08X", r);
    } else {
        fprintf(o, "%d", (int32_t)r);
    }
    fputs(" B=", o);
    for (k = 0; k < nb; k++) {
        if (k)
            fputc(',', o);
        put_hex16(o, bufs[k], caps[k] + GUARD);
    }
    fputc('\n', o);
}

/* M <id> <size> <dst> <src> <n> */
static void run_memmove(FILE* o, const char* id, char* s) {
    uint32_t size = (uint32_t)atoi(next_tok(&s)), d = (uint32_t)atoi(next_tok(&s)), sr = (uint32_t)atoi(next_tok(&s));
    uint32_t n = (uint32_t)atoi(next_tok(&s)), i, exc = 0, args[3], r;
    Ptr b = talloc(size);
    for (i = 0; i < size; i++)
        ((uint8_t*)H(b))[i] = (uint8_t)(i * 7 + 1);
    args[0] = b + d; args[1] = b + sr; args[2] = n;
    r = call_fn(F_MEMMOVE, args, 3, &exc);
    if (exc) {
        exc_line(o, "M", id, exc);
        return;
    }
    fprintf(o, "M %s R=%d B=", id, (int)(r - b));
    for (i = 0; i < size; i++)
        fprintf(o, "%02X", ((uint8_t*)H(b))[i]);
    fputc('\n', o);
}

/* R <id> <seed hex8|-> <count> */
static void run_rand(FILE* o, const char* id, char* s) {
    char* seed = next_tok(&s);
    int n = atoi(next_tok(&s)), i;
    uint32_t exc = 0, a[1];
    fprintf(o, "R %s V=", id);
    if (seed[0] != '-') {
        a[0] = (uint32_t)hexnum(seed, 8);
        call_fn(F_SRAND, a, 1, &exc);
    }
    for (i = 0; i < n && !exc; i++)
        fprintf(o, "%s%u", i ? "," : "", call_fn(F_RAND, a, 0, &exc) & 0xFFFFu);
    if (exc)
        fprintf(o, " EXC=%08X", exc);
    fputc('\n', o);
}

/* ---------------------------------------------------------------- CRT dependencies of `ucc make`
 * T <id> <func> <arg>*: narrow string / character function. s<off>,<hex|~> a string at byte offset off of its
 * region, b<off>,<cap> a destination of cap bytes (0xCC) at offset off, u<hex8> an integer. Every region is
 * [BPRE guard][off + size bytes][BPOST guard] and is recorded whole after the call; a returned pointer is recorded
 * relative to the argument it points into. */
static const struct { const char* name; int d, ptr; } tfuncs[] = {
    {"strrchr", D_STRRCHR, 1}, {"strchr", D_STRCHR, 1}, {"strncpy", D_STRNCPY, 1},
    {"_stricmp", D_STRICMP, 0}, {"atoi", D_ATOI, 0}, {"toupper", D_TOUPPER, 0}};

static void run_tstr(FILE* o, const char* id, char* s) {
    char* t = next_tok(&s);
    int f = -1, na = 0, nb = 0, k;
    uint32_t args[4], exc = 0, r, rbytes[4];
    Ptr regs[4], at[4];
    for (k = 0; k < (int)(sizeof tfuncs / sizeof tfuncs[0]); k++)
        if (!strcmp(tfuncs[k].name, t))
            f = k;
    if (f < 0) {
        fprintf(stderr, "unknown T function %s\n", t);
        exit(3);
    }
    if (!dep_available(tfuncs[f].d)) {
        fprintf(o, "T %s PENDING\n", id);
        return;
    }
    while ((t = next_tok(&s)) != NULL) {
        if (na == 4) {
            fprintf(stderr, "T %s: too many arguments\n", id);
            exit(3);
        }
        if (t[0] == 's' || t[0] == 'b') {
            char* p = t + 1;
            uint32_t off = (uint32_t)strtoul(p, &p, 10), n;
            p++;
            if (t[0] == 's') {
                n = hexbytes(p, NULL);
                rbytes[nb] = off + n + 1;
                regs[nb] = bregion(rbytes[nb]);
                at[nb] = regs[nb] + BPRE + off;
                hexbytes(p, (uint8_t*)H(at[nb]));
                ((uint8_t*)H(at[nb]))[n] = 0;
            } else {
                rbytes[nb] = off + (uint32_t)strtoul(p, NULL, 10);
                regs[nb] = bregion(rbytes[nb]);
                at[nb] = regs[nb] + BPRE + off;
            }
            args[na++] = at[nb++];
        } else if (t[0] == 'u') {
            args[na++] = (uint32_t)hexnum(t + 1, 8);
        } else {
            fprintf(stderr, "bad T argument %s\n", t);
            exit(3);
        }
    }
    r = call_dep(tfuncs[f].d, args, na, &exc);
    if (exc) {
        exc_line(o, "T", id, exc);
        return;
    }
    fprintf(o, "T %s R=", id);
    if (tfuncs[f].ptr) {
        int found = 0;
        if (!r) {
            fputc('0', o);
            found = 1;
        }
        for (k = 0; k < nb && !found; k++)
            if (r >= regs[k] && r < regs[k] + BPRE + rbytes[k] + BPOST) {
                fprintf(o, "a%d%+d", k, (int)(r - at[k]));
                found = 1;
            }
        if (!found)
            fprintf(o, "?%08X", r);
    } else {
        fprintf(o, "%d", (int32_t)r);
    }
    fputs(" B=", o);
    for (k = 0; k < nb; k++) {
        if (k)
            fputc(',', o);
        put_region(o, regs[k], rbytes[k]);
    }
    fputc('\n', o);
}

/* Q <id> <cmp> <width> <num> <hex|~>: qsort of num elements of width bytes with comparator cmp (cmp_names).
 * Records the array region after the call (guards included), the number of comparator calls, an FNV-1a hash of
 * the sequence of (a - base, b - base) offsets they received, and that sequence for the first QLOG calls. A call
 * with a pointer that is not an element of the array is counted (O=) and answered 0 without reading it. */
#define QLOG 256
static struct { Ptr base; uint32_t bytes, width, n, oob; uint64_t h; uint32_t log[2 * QLOG]; } qs;

static int32_t cmp_eval(int kind, Ptr a, Ptr b) {
    uint32_t v[2], i;
    int32_t x, y;
    v[0] = a - qs.base;
    v[1] = b - qs.base;
    for (i = 0; i < 8; i++) {
        qs.h ^= (uint8_t)(v[i / 4] >> (8 * (i % 4)));
        qs.h *= 0x100000001B3ull;
    }
    if (qs.n < QLOG) {
        qs.log[2 * qs.n] = v[0];
        qs.log[2 * qs.n + 1] = v[1];
    }
    qs.n++;
    if (!qs.width || v[0] >= qs.bytes || v[1] >= qs.bytes || v[0] % qs.width || v[1] % qs.width) {
        qs.oob++;
        return 0;
    }
    switch (kind) {
    case CMP_I32:
        x = (int32_t)r32(a);
        y = (int32_t)r32(b);
        return (x > y) - (x < y);
    case CMP_DIFF:
        return (int32_t)(r32(a) - r32(b));
    case CMP_DESC:
        x = (int32_t)r32(a);
        y = (int32_t)r32(b);
        return (y > x) - (y < x);
    case CMP_KEY:
        return (int32_t)((uint8_t*)H(a))[0] - (int32_t)((uint8_t*)H(b))[0];
    default:
        return 0;
    }
}

static void run_qsort(FILE* o, const char* id, char* s) {
    char *cn = next_tok(&s), *w = next_tok(&s), *nm = next_tok(&s), *hex = next_tok(&s);
    uint32_t args[4], exc = 0, i, width, num;
    int kind = -1;
    Ptr r;
    for (i = 0; cn && i < CMP_COUNT; i++)
        if (!strcmp(cmp_names[i], cn))
            kind = (int)i;
    if (kind < 0 || !hex) {
        fprintf(stderr, "bad Q line %s\n", id);
        exit(3);
    }
    width = (uint32_t)strtoul(w, NULL, 10);
    num = (uint32_t)strtoul(nm, NULL, 10);
    if (hexbytes(hex, NULL) != width * num) {
        fprintf(stderr, "Q %s: data is not %u x %u bytes\n", id, num, width);
        exit(3);
    }
    if (!dep_available(D_QSORT)) {
        fprintf(o, "Q %s PENDING\n", id);
        return;
    }
    r = bregion(width * num);
    hexbytes(hex, (uint8_t*)H(r + BPRE));
    memset(&qs, 0, sizeof qs);
    qs.base = r + BPRE;
    qs.bytes = width * num;
    qs.width = width;
    qs.h = 0xCBF29CE484222325ull;
    args[0] = r + BPRE;
    args[1] = num;
    args[2] = width;
    args[3] = cmp_ptr(kind);
    call_dep(D_QSORT, args, 4, &exc);
    if (exc) {
        exc_line(o, "Q", id, exc);
        return;
    }
    fprintf(o, "Q %s A=", id);
    put_region(o, r, width * num);
    fprintf(o, " C=%u H=%016llX O=%u L=", qs.n, (unsigned long long)qs.h, qs.oob);
    for (i = 0; i < qs.n && i < QLOG; i++)
        fprintf(o, "%s%X,%X", i ? ";" : "", qs.log[2 * i], qs.log[2 * i + 1]);
    if (!qs.n)
        fputc('~', o);
    fputc('\n', o);
}

/* Z <id> <op>*: heap sequence over 8 slots: m<k>,<n> slot k = malloc(n); r<k>,<n> slot k = realloc(slot k, n);
 * s<k> _msize(slot k); f<k> free(slot k). After a successful malloc/realloc all n bytes are written with a pattern,
 * and realloc first checks that every byte the block keeps (min(old, new)) still holds it. Records success / NULL,
 * that check and the _msize values, never addresses; s<k> of an empty slot (a NULL result) records s:null without
 * calling _msize, which would be an invalid input. */
static uint8_t zpat(int k, uint32_t i) { return (uint8_t)(k * 37 + (int)i * 11 + 1); }

static void run_heap(FILE* o, const char* id, char* s) {
    Ptr slot[8];
    uint32_t size[8], exc = 0, a[2], r, i;
    char* t;
    if (!dep_available(D_MALLOC) || !dep_available(D_REALLOC) || !dep_available(D_MSIZE) || !dep_available(D_FREE)) {
        fprintf(o, "Z %s PENDING\n", id);
        return;
    }
    memset(slot, 0, sizeof slot);
    memset(size, 0, sizeof size);
    fprintf(o, "Z %s", id);
    while ((t = next_tok(&s)) != NULL) {
        int k = t[1] - '0';
        uint32_t n = t[0] == 'm' || t[0] == 'r' ? (uint32_t)strtoul(t + 3, NULL, 10) : 0;
        if (k < 0 || k > 7) {
            fprintf(stderr, "bad Z op %s\n", t);
            exit(3);
        }
        switch (t[0]) {
        case 'm':
            a[0] = n;
            r = call_dep(D_MALLOC, a, 1, &exc);
            if (!exc) {
                slot[k] = r;
                size[k] = n;
                for (i = 0; r && i < n; i++)
                    ((uint8_t*)H(r))[i] = zpat(k, i);
                fprintf(o, " m:%d", r != 0);
            }
            break;
        case 'r': {
            int kept = 1;
            a[0] = slot[k];
            a[1] = n;
            r = call_dep(D_REALLOC, a, 2, &exc);
            if (exc)
                break;
            if (r) {
                for (i = 0; slot[k] && i < n && i < size[k]; i++)
                    kept &= ((uint8_t*)H(r))[i] == zpat(k, i);
                slot[k] = r;
                size[k] = n;
                for (i = 0; i < n; i++)
                    ((uint8_t*)H(r))[i] = zpat(k, i);
            } else if (!n) {
                slot[k] = 0;            /* realloc(p, 0) frees p */
            }
            fprintf(o, " r:%d:%d", r != 0, kept);
            break;
        }
        case 's':
            if (!slot[k]) {
                fputs(" s:null", o);
                break;
            }
            a[0] = slot[k];
            r = call_dep(D_MSIZE, a, 1, &exc);
            if (!exc)
                fprintf(o, " s:%u", r);
            break;
        case 'f':
            a[0] = slot[k];
            call_dep(D_FREE, a, 1, &exc);
            slot[k] = 0;
            if (!exc)
                fputs(" f", o);
            break;
        default:
            fprintf(stderr, "bad Z op %s\n", t);
            exit(3);
        }
        if (exc) {
            fprintf(o, " EXC=%08X\n", exc);
            return;
        }
    }
    fputc('\n', o);
}

/* X <id> <hex8>*: _set_se_translator with each value in turn, recording the previous translator each call
 * returns. The translator is per-thread state, so compare.py runs every X line in a fresh process; no structured
 * exception is raised, so no translator is ever invoked. */
static void run_setse(FILE* o, const char* id, char* s) {
    uint32_t a[1], exc = 0, r;
    char* t;
    int first = 1;
    if (!dep_available(D_SETSE)) {
        fprintf(o, "X %s PENDING\n", id);
        return;
    }
    fprintf(o, "X %s R=", id);
    while ((t = next_tok(&s)) != NULL) {
        a[0] = (uint32_t)hexnum(t, 8);
        fflush(o);              /* a process that dies in the call leaves the results so far (compare.py) */
        r = call_dep(D_SETSE, a, 1, &exc);
        if (exc) {
            fprintf(o, " EXC=%08X", exc);
            break;
        }
        fprintf(o, "%s%08X", first ? "" : ",", r);
        first = 0;
    }
    fputc('\n', o);
}

/* F <id> <op>*: a sequence of file-system calls. compare.py runs every F line in a fresh process whose current
 * directory is a scratch tree it rebuilds before each process (fixed names, contents, attributes and times); the
 * harness refuses to run F lines in a directory without the tree's marker file. Strings are hex bytes ('~' empty,
 * '-' NULL). Ops:
 *   cwd:<buf>:<size>          _getcwd(buf, size); buf '=' is a buffer of exactly size bytes, '-' is NULL
 *   full:<buf>:<size>:<path>  _fullpath(buf, path, size)
 *   cd:<path>                 _chdir(path)
 *   ff:<pattern>              _findfirst, then _findclose if it succeeded (GlmLib's existence check)
 *   find:<pattern>            _findfirst, _findnext until it fails (at most 300 calls), _findclose; one guarded
 *                             _finddata_t (pre-filled 0xCC) for all of them, as GlmLib does
 *   open:<path>:<mode>        fopen, then fclose if it succeeded
 * <size> is decimal, L+k / L-k (L: GetCurrentDirectoryA's length) or P+k / P-k (P: GetFullPathNameA's length for
 * the op's path); those host calls only choose sizes. Each op records the return values (buffer addresses as
 * offsets, a malloc'd result as its string and _msize; a find handle as h/-1; a FILE as its _iob index), the whole
 * buffer or structure region, the thread's Win32 last error (le=, LE_SENTINEL before the call) and errno (through
 * _errno) after every call. fopen and fclose also record the FILE records _iob[3..5] (fopen's _getstream takes the
 * first free one from 3), pointer fields as 0 / P. The line is flushed before every call, so a process that dies in
 * a call leaves the ops before it for compare.py. */
#define FS_MARKER "crt_diff_fs.marker"
#define FD_SIZE 280      /* struct _finddata_t: attrib, time_create, time_access, time_write (32-bit time_t), size, name[260] */

/* the last error the latest call_dep left: printed right after each file-system call, before any other call */
static void fs_le(FILE* o) { fprintf(o, " le=%u", dep_last_error); }

static void fs_errno(FILE* o, uint32_t* exc) {
    uint32_t a[1] = {0};
    Ptr p = call_dep(D_ERRNO, a, 0, exc);
    if (!*exc)
        fprintf(o, " e=%u", r32(p));
}

/* _iob[3..5], each _ptr, _cnt, _base, _flag, _file, _charbuf, _bufsiz, _tmpfname (pointers as 0 / P) */
static void fs_iob(FILE* o) {
    uint32_t k, f;
    fputs(" I=", o);
    for (k = 3; k < 6; k++) {
        if (k > 3)
            fputc('|', o);
        for (f = 0; f < 8; f++) {
            uint32_t v = r32(iob_base() + 32 * k + 4 * f);
            if (f)
                fputc(',', o);
            if (f == 0 || f == 2 || f == 7)
                fputc(v ? 'P' : '0', o);
            else
                fprintf(o, "%X", v);
        }
    }
}

static uint32_t fs_size(const char* t, Ptr path) {
    long base;
    if (t[0] == 'L')
        base = (long)GetCurrentDirectoryA(0, NULL) - 1;
    else if (t[0] == 'P')
        base = (long)GetFullPathNameA((const char*)H(path), 0, NULL, NULL) - 1;
    else
        return (uint32_t)strtoul(t, NULL, 10);
    return (uint32_t)(base + strtol(t + 1, NULL, 10));
}

/* _getcwd / _fullpath result: R=0, R=b+<offset> into the buffer, or (NULL buffer) R=m with the string and _msize,
 * after which the block is freed */
static void fs_result(FILE* o, uint32_t r, Ptr reg, uint32_t bytes, int nullbuf, uint32_t* exc) {
    if (!r) {
        fputs(" R=0", o);
    } else if (nullbuf) {
        uint32_t n = 0, a[1];
        fputs(" R=m S=", o);
        while (n < 4096 && ((uint8_t*)H(r))[n])
            fprintf(o, "%02X", ((uint8_t*)H(r))[n++]);
        if (!n)
            fputc('~', o);
        a[0] = r;
        fprintf(o, " M=%u", call_dep(D_MSIZE, a, 1, exc));
        if (!*exc)
            call_dep(D_FREE, a, 1, exc);
    } else if (r >= reg + BPRE && r < reg + BPRE + bytes) {
        fprintf(o, " R=b+%u", r - reg - BPRE);
    } else {
        fprintf(o, " R=?%08X", r);
    }
    if (!nullbuf) {
        fputs(" B=", o);
        put_region(o, reg, bytes);
    }
}

static Ptr fs_str(const char* hex) { return hex[0] == '-' ? 0 : put_astr(hex); }

static void run_fs(FILE* o, const char* id, char* s) {
    char* ops[64];
    int nops = 0, i, d;
    int need[D_COUNT];
    uint32_t exc = 0, a[3], r;
    while (nops < 64 && (ops[nops] = next_tok(&s)) != NULL)
        nops++;
    memset(need, 0, sizeof need);
    need[D_ERRNO] = 1;
    for (i = 0; i < nops; i++) {
        const char* p = ops[i];
        if (!strncmp(p, "cwd:", 4))
            need[D_GETCWD] = 1;
        else if (!strncmp(p, "full:", 5))
            need[D_FULLPATH] = 1;
        else if (!strncmp(p, "cd:", 3))
            need[D_CHDIR] = 1;
        else if (!strncmp(p, "ff:", 3))
            need[D_FINDFIRST] = need[D_FINDCLOSE] = 1;
        else if (!strncmp(p, "find:", 5))
            need[D_FINDFIRST] = need[D_FINDNEXT] = need[D_FINDCLOSE] = 1;
        else if (!strncmp(p, "open:", 5))
            need[D_FOPEN] = need[D_FCLOSE] = 1;
        else {
            fprintf(stderr, "bad F op %s\n", p);
            exit(3);
        }
        if (strstr(p, ":-:"))
            need[D_MSIZE] = need[D_FREE] = 1;
    }
    for (d = 0; d < D_COUNT; d++)
        if (need[d] && !dep_available(d)) {
            fprintf(o, "F %s PENDING\n", id);
            return;
        }
    if (GetFileAttributesA(FS_MARKER) == INVALID_FILE_ATTRIBUTES) {
        fprintf(stderr, "F lines run only in the scratch tree (no %s in the current directory)\n", FS_MARKER);
        exit(3);
    }
    fprintf(o, "F %s", id);
    /* every file-system call: flush first; afterwards " le=<last error> e=<errno>", then the op's own fields */
#define FS_CALL(var, d, n)                                                                                           \
    do {                                                                                                             \
        fflush(o);                                                                                                   \
        var = call_dep(d, a, n, &exc);                                                                               \
        if (!exc) {                                                                                                  \
            fs_le(o);                                                                                                \
            fs_errno(o, &exc);                                                                                       \
        }                                                                                                            \
    } while (0)
    for (i = 0; i < nops && !exc; i++) {
        char* f[4];
        int nf = 1;
        char* p = ops[i];
        f[0] = p;
        for (; *p && nf < 4; p++)
            if (*p == ':') {
                *p = 0;
                f[nf++] = p + 1;
            }
        fprintf(o, " ; %s", f[0]);
        if (!strcmp(f[0], "cwd") || !strcmp(f[0], "full")) {
            int full = f[0][0] == 'f', nullbuf = f[1][0] == '-';
            Ptr path = full ? fs_str(f[3]) : 0, reg;
            uint32_t size = fs_size(f[2], path);
            reg = nullbuf ? 0 : bregion(size);
            a[0] = nullbuf ? 0 : reg + BPRE;
            if (full) {
                a[1] = path;
                a[2] = size;
                FS_CALL(r, D_FULLPATH, 3);
            } else {
                a[1] = size;
                FS_CALL(r, D_GETCWD, 2);
            }
            if (!exc)
                fs_result(o, r, reg, size, nullbuf, &exc);
        } else if (!strcmp(f[0], "cd")) {
            a[0] = fs_str(f[1]);
            FS_CALL(r, D_CHDIR, 1);
            if (!exc)
                fprintf(o, " R=%d", (int32_t)r);
        } else if (!strcmp(f[0], "ff") || !strcmp(f[0], "find")) {
            Ptr fd = bregion(FD_SIZE);
            uint32_t h;
            int k;
            a[0] = fs_str(f[1]);
            a[1] = fd + BPRE;
            FS_CALL(h, D_FINDFIRST, 2);
            if (exc)
                break;
            fprintf(o, " F=%s D=", h == 0xFFFFFFFFu ? "-1" : "h");
            put_region(o, fd, FD_SIZE);
            if (h == 0xFFFFFFFFu)
                continue;
            for (k = 0; f[0][1] == 'i' && k < 300 && !exc; k++) {
                a[0] = h;
                a[1] = fd + BPRE;
                FS_CALL(r, D_FINDNEXT, 2);
                if (exc)
                    break;
                fprintf(o, " N=%d D=", (int32_t)r);
                put_region(o, fd, FD_SIZE);
                if (r)
                    break;
            }
            if (exc)
                break;
            a[0] = h;
            FS_CALL(r, D_FINDCLOSE, 1);
            if (!exc)
                fprintf(o, " C=%d", (int32_t)r);
        } else if (!strcmp(f[0], "open")) {
            uint32_t fp, off;
            a[0] = fs_str(f[1]);
            a[1] = fs_str(f[2]);
            FS_CALL(fp, D_FOPEN, 2);
            if (exc)
                break;
            off = fp - iob_base();
            if (!fp)
                fputs(" R=0", o);
            else if (off < 20 * 32 && !(off % 32))
                fprintf(o, " R=i%u", off / 32);
            else
                fprintf(o, " R=?%08X", fp);
            fs_iob(o);
            if (!fp)
                continue;
            a[0] = fp;
            FS_CALL(r, D_FCLOSE, 1);
            if (!exc) {
                fprintf(o, " C=%d", (int32_t)r);
                fs_iob(o);
            }
        }
    }
#undef FS_CALL
    if (exc)
        fprintf(o, " EXC=%08X", exc);
    fputc('\n', o);
}

static void run_corpus(const char* corpus, const char* results) {
    FILE* in = fopen(corpus, "rb");
    FILE* o = fopen(results, "wb");
    static char line[1 << 20];
    static uint32_t block[BLOCKW];
    unsigned long ncases = 0;
    if (!in || !o) {
        fprintf(stderr, "cannot open %s / %s\n", corpus, results);
        exit(3);
    }
    while (fgets(line, sizeof line, in)) {
        char *s = line, *kind, *id;
        size_t L = strlen(line);
        while (L && (line[L - 1] == '\n' || line[L - 1] == '\r'))
            line[--L] = 0;
        kind = next_tok(&s);
        if (!kind || kind[0] == '#')
            continue;
        id = next_tok(&s);
        bump = arena_lo;
        slots = talloc(4 * NSLOT);
        if (kind[0] == 'P' || kind[0] == 'W' || kind[0] == 'C') {
            char* counts = kind[0] == 'C' ? next_tok(&s) : NULL;
            char* f = next_tok(&s);
            Ptr fmt = put_wstr(f, 0), va;
            int has_n = build_block(&s, block);
            if (kind[0] != 'W') {
                va = talloc(BLOCKW * 4);
                memcpy(H(va), block, BLOCKW * 4);
                if (counts)
                    run_counts(o, id, counts, fmt, va);
                else
                    run_printf(o, id, fmt, va, has_n);
            } else {
                run_wprintf(o, id, fmt, block, has_n);
            }
        } else if (kind[0] == 'A' || kind[0] == 'V') {
            char* f = next_tok(&s);
            Ptr fmt = put_astr(f), va;
            int has_n = build_block(&s, block);
            va = talloc(BLOCKW * 4);
            memcpy(H(va), block, BLOCKW * 4);
            run_sprintf(o, kind, id, fmt, va, block, has_n);
        } else if (kind[0] == 'T') {
            run_tstr(o, id, s);
        } else if (kind[0] == 'Q') {
            run_qsort(o, id, s);
        } else if (kind[0] == 'Z') {
            run_heap(o, id, s);
        } else if (kind[0] == 'X') {
            run_setse(o, id, s);
        } else if (kind[0] == 'F') {
            run_fs(o, id, s);
        } else if (kind[0] == 'B' || kind[0] == 'K' || kind[0] == 'E') {
            int bf = bf_index(next_tok(&s)), has_n;
            char *alloc = NULL, *counts = NULL, *dest = NULL, *cnt = NULL, *f;
            Ptr fmt, va;
            if (kind[0] == 'K') {
                alloc = next_tok(&s);
                counts = next_tok(&s);
            } else if (kind[0] == 'E') {
                dest = next_tok(&s);
                cnt = next_tok(&s);
            }
            f = next_tok(&s);
            if (!strcmp(f, "null"))
                fmt = 0;
            else
                fmt = bf_unit[bf] == 2 ? put_wstr(f, 0) : put_astr(f);
            has_n = build_block(&s, block);
            va = talloc(BLOCKW * 4);
            memcpy(H(va), block, BLOCKW * 4);
            if (kind[0] == 'B')
                run_bounded(o, id, bf, fmt, va, block, has_n);
            else if (kind[0] == 'K')
                run_kcounts(o, id, bf, (uint32_t)atoi(alloc), counts, fmt, va, block, has_n);
            else
                run_error(o, id, bf, dest, (uint32_t)strtoul(cnt, NULL, 0), fmt, va, block);
        } else if (kind[0] == 'S') {
            run_string(o, id, s);
        } else if (kind[0] == 'M') {
            run_memmove(o, id, s);
        } else if (kind[0] == 'R') {
            run_rand(o, id, s);
        } else {
            fprintf(stderr, "bad corpus line kind %s\n", kind);
            exit(3);
        }
        ncases++;
    }
    fclose(in);
    fclose(o);
    fprintf(stderr, "%lu cases\n", ncases);
}

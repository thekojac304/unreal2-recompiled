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

static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc);
static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc);
static uint32_t call_sprintf(Ptr buf, Ptr fmt, const uint32_t* block, uint32_t* exc);
static int probe_too_long(Ptr fmt, Ptr va, uint32_t limit, uint32_t* exc);
static int bounded_available(int bf);
static uint32_t call_bounded(int bf, Ptr buf, uint32_t count, Ptr fmt, Ptr va, const uint32_t* block, uint32_t* exc);
static void flush_stdout(void);

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
 * the %n targets. */
static void run_sprintf(FILE* o, const char* id, Ptr fmt, Ptr va, const uint32_t* block, int has_n) {
    uint32_t exc = 0, n, i;
    Ptr buf;
    int32_t r;
    reset_slots();
    if (probe_too_long(fmt, va, ABIG, &exc)) {
        if (exc)
            exc_line(o, "A", id, exc);
        else
            fprintf(o, "A %s SKIP\n", id);
        return;
    }
    buf = talloc(ABIG + 1 + GUARD);
    memset(H(buf), 0xCC, ABIG + 1 + GUARD);
    reset_slots();
    r = (int32_t)call_sprintf(buf, fmt, block, &exc);
    if (exc) {
        exc_line(o, "A", id, exc);
        return;
    }
    fprintf(o, "A %s R=%d B=", id, r);
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
        } else if (kind[0] == 'A') {
            char* f = next_tok(&s);
            Ptr fmt = put_astr(f), va;
            int has_n = build_block(&s, block);
            va = talloc(BLOCKW * 4);
            memcpy(H(va), block, BLOCKW * 4);
            run_sprintf(o, id, fmt, va, block, has_n);
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

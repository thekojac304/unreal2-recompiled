/* crt_diff_core.h - shared driver of the msvcr70 differential test (see README.md).
 *
 * Included by ref.c (x86: calls the real msvcr70.dll) and cand.c (x64: calls the runtime's adapters and
 * xrt_wformat over guest memory). The includer provides:
 *   typedef uint32_t Ptr;                     address as the callee sees it (real x86 / guest)
 *   static void* H(Ptr p);                    host pointer for an address in the test arena
 *   static Ptr arena_lo, arena_hi;            test arena [lo, hi) (set before run_corpus)
 *   static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc);   cdecl call
 *   static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc);      variadic call
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

static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc);
static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc);
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

/* hle_msvcr70.c - host adapters for the MSVCR70.dll imports of the translated modules (cdecl).
 *
 * Semantics follow msvcr70 in the "C" locale (no translated module calls setlocale: it is unbound), not the
 * host UCRT: string functions fold only A-Z, wcscmp returns -1/0/1, rand() is the msvcr70 per-thread LCG,
 * _vsnwprintf returns -1 on truncation and omits the terminator when the output fills the buffer exactly,
 * wide stdout output skips characters the "C" locale cannot convert (> 0xFF) and wprintf then counts as
 * _woutput does (xrt_fmt.c), and stdout is a text-mode stream ('\n' -> "\r\n"). qsort and atof are ports of
 * the DLL's own code (read from the binary). errno is not modelled (_errno is unbound). C++ exception
 * dispatch (_CxxThrowException) is in xrt_eh.c. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#include <math.h>
#include <stdlib.h>
#include <time.h>
#include "xrt_internal.h"

/* ---------------------------------------------------------------- stdout (text-mode stream) */
static uint8_t outbuf[1 << 16];
static size_t outlen;
static uint64_t out_total_chars;

void xrt_stdout_flush(void) {
    if (outlen) {
        fwrite(outbuf, 1, outlen, stdout);
        outlen = 0;
    }
    fflush(stdout);
}

static void out_byte(uint8_t b) {
    if (outlen == sizeof outbuf)
        xrt_stdout_flush();
    outbuf[outlen++] = b;
}

/* returns the number of characters written, or -1 at the first character that is not representable
 * (the rest is not written) */
static long stdout_write(const uint16_t* s, size_t n) {
    size_t i;
    for (i = 0; i < n; i++) {
        if (s[i] > 0xFF) {
            xrt_log("wide stdout: character U+%04X is not convertible in the C locale; not written (as msvcr70)", s[i]);
            return -1;
        }
        if (s[i] == '\n')
            out_byte('\r');
        out_byte((uint8_t)s[i]);
        out_total_chars++;
    }
    return (long)n;
}
void xrt_stdout_write(const uint16_t* s, size_t n) { stdout_write(s, n); }

/* ---------------------------------------------------------------- data objects */
static uint32_t iob;                 /* guest FILE[20], 32 bytes each (msvcr70 layout) */
static uint32_t fmode_var, commode_var, initenv_var, argc_save, argv_save;
static int app_type = -1;

void hle_msvcr70_init(void) {
    int i;
    iob = xrt_hle_data("msvcr70.dll", "_iob");
    for (i = 0; i < 3; i++) {
        wr32(iob + 32 * i + 12, i == 0 ? 0x0001u : 0x0002u);   /* _flag: _IOREAD / _IOWRT */
        wr32(iob + 32 * i + 16, (uint32_t)i);                   /* _file */
    }
    fmode_var = xrt_rt_alloc(4, 4);
    commode_var = xrt_rt_alloc(4, 4);
    initenv_var = xrt_rt_alloc(4, 4);
    _setmode(_fileno(stdout), _O_BINARY);   /* text-mode translation is done above, exactly once */
}

/* XRT_MATH_LOG=<file>: records the operands and results of _CIpow, _CIfmod, _isnan and atof (one line per call, bit
 * patterns in hex), so the inputs of a real run can be replayed against msvcr70 (tools/xrt/tests/crt_gatef). */
static FILE* math_log;
static int math_log_tried;
static FILE* mlog(void) {
    if (!math_log_tried) {
        const char* p = getenv("XRT_MATH_LOG");
        math_log_tried = 1;
        if (p && *p)
            math_log = fopen(p, "w");
    }
    return math_log;
}
static uint64_t dbits(double x) {
    uint64_t b;
    memcpy(&b, &x, 8);
    return b;
}

/* ---------------------------------------------------------------- heap */
/* msvcr70 on Windows NT 5+ uses the system heap: malloc(0) allocates 1 byte, _msize is HeapSize (the requested size) */
static void hle_malloc(CPU* c) { RET_C(xrt_heap_alloc(ARG(0) ? ARG(0) : 1u)); }
static void hle_msize(CPU* c) { RET_C(xrt_heap_msize(c, ARG(0))); }
static void hle_free(CPU* c) { xrt_heap_free(c, ARG(0)); RET_C_VOID(); }
static void hle_realloc(CPU* c) { RET_C(xrt_heap_realloc(c, ARG(0), ARG(1))); }

/* ---------------------------------------------------------------- startup / termination */
static uint32_t* exe_onexit;
static int n_exe_onexit, cap_exe_onexit;

static void hle_initterm(CPU* c) {
    uint32_t p = ARG(0), end = ARG(1);
    for (; p < end; p += 4) {
        uint32_t f = rd32(p);
        if (f)
            xrt_call_guest(c, f, 0, NULL, 0);
    }
    RET_C_VOID();
}

static void hle_onexit(CPU* c) {
    uint32_t f = ARG(0);
    if (n_exe_onexit == cap_exe_onexit) {
        cap_exe_onexit = cap_exe_onexit ? 2 * cap_exe_onexit : 64;
        exe_onexit = (uint32_t*)realloc(exe_onexit, cap_exe_onexit * sizeof *exe_onexit);
    }
    exe_onexit[n_exe_onexit++] = f;
    RET_C(f);
}

/* __dllonexit(func, &__onexitbegin, &__onexitend): the DLL's own table lives in guest memory */
static void hle_dllonexit(CPU* c) {
    uint32_t f = ARG(0), pbegin = ARG(1), pend = ARG(2);
    uint32_t begin = rd32(pbegin), end = rd32(pend), size;
    if (!begin)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "__dllonexit with an unallocated table");
    size = xrt_heap_msize(c, begin);
    if (size <= end - begin) {
        uint32_t grow = size < 512 * 4 ? size : 512 * 4, nb = xrt_heap_realloc(c, begin, size + grow);
        if (!nb) {
            RET_C(0);
            return;
        }
        end = nb + (end - begin);
        begin = nb;
    }
    wr32(end, f);
    end += 4;
    wr32(pbegin, begin);
    wr32(pend, end);
    RET_C(f);
}

static void run_exe_onexit(CPU* c) {
    while (n_exe_onexit > 0) {
        uint32_t f = exe_onexit[--n_exe_onexit];
        if (f)
            xrt_call_guest(c, f, 0, NULL, 0);
    }
}

static void hle_exit(CPU* c) {
    uint32_t code = ARG(0);
    xrt_log("exit(%u): running %d onexit handlers", code, n_exe_onexit);
    xrt_event("crt_exit", "\"code\": %u, \"onexit_handlers\": %d", code, n_exe_onexit);
    run_exe_onexit(c);
    xrt_stdout_flush();
    xrt_process_exit(c, code);
}

static void hle__exit(CPU* c) {
    xrt_stdout_flush();
    xrt_process_exit(c, ARG(0));
}

static void hle_set_app_type(CPU* c) { app_type = (int)ARG(0); RET_C_VOID(); }
static void hle_p_fmode(CPU* c) { RET_C(fmode_var); }
static void hle_p_commode(CPU* c) { RET_C(commode_var); }
static void hle_p_initenv(CPU* c) { RET_C(initenv_var); }

/* msvcr70 stdargv.c parse_cmdline (no MBCS lead bytes in the "C" locale/ANSI code pages used here) */
static int parse_cmdline(const char* cmd, uint32_t* argv, char* args, int* numchars) {
    const char* p = cmd;
    int numargs = 1, inquote = 0;
    char c;
    *numchars = 0;
    if (argv)
        *argv++ = 0;   /* filled by caller */
    if (*p == '"') {
        while (*(++p) != '"' && *p) {
            ++*numchars;
            if (args)
                *args++ = *p;
        }
        ++*numchars;
        if (args)
            *args++ = 0;
        if (*p == '"')
            p++;
    } else {
        do {
            ++*numchars;
            if (args)
                *args++ = *p;
            c = *p++;
        } while (c != ' ' && c != 0 && c != '\t');
        if (c == 0)
            p--;
        else if (args)
            *(args - 1) = 0;
    }
    for (;;) {
        if (*p)
            while (*p == ' ' || *p == '\t')
                ++p;
        if (*p == 0)
            break;
        ++numargs;
        for (;;) {
            int copychar = 1, numslash = 0;
            while (*p == '\\') {
                ++p;
                ++numslash;
            }
            if (*p == '"') {
                if (numslash % 2 == 0) {
                    if (inquote && p[1] == '"')
                        p++;
                    else
                        copychar = 0;
                    inquote = !inquote;
                }
                numslash /= 2;
            }
            while (numslash--) {
                if (args)
                    *args++ = '\\';
                ++*numchars;
            }
            if (*p == 0 || (!inquote && (*p == ' ' || *p == '\t')))
                break;
            if (copychar) {
                if (args)
                    *args++ = *p;
                ++*numchars;
            }
            ++p;
        }
        if (args)
            *args++ = 0;
        ++*numchars;
    }
    return numargs;
}

/* __getmainargs(int* argc, char*** argv, char*** envp, int dowildcard, _startupinfo*) */
static void hle_getmainargs(CPU* c) {
    const char* cmd = (const char*)G2H(xrt_cmdline_a);
    int nchars, nargs = parse_cmdline(cmd, NULL, NULL, &nchars), i;
    char* tmp = (char*)malloc((size_t)nchars + 1);
    uint32_t argv = xrt_rt_alloc(4u * (uint32_t)(nargs + 1), 4), strs, envp;
    const char* s;
    if (ARG(3))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "__getmainargs with wildcard expansion is not implemented");
    parse_cmdline(cmd, NULL, tmp, &nchars);
    strs = xrt_rt_alloc((uint32_t)nchars + 1, 4);
    memcpy(G2H(strs), tmp, (size_t)nchars);
    for (i = 0, s = tmp; i < nargs; i++) {
        wr32(argv + 4u * (uint32_t)i, strs + (uint32_t)(s - tmp));
        s += strlen(s) + 1;
    }
    wr32(argv + 4u * (uint32_t)nargs, 0);
    free(tmp);
    envp = xrt_rt_alloc(4, 4);           /* deliberate limitation: the guest gets an empty environment */
    wr32(ARG(0), (uint32_t)nargs);
    wr32(ARG(1), argv);
    wr32(ARG(2), envp);
    wr32(initenv_var, envp);
    argc_save = (uint32_t)nargs;
    argv_save = argv;
    xrt_log("__getmainargs: argc=%d from \"%s\"", nargs, cmd);
    RET_C(0);
}

/* _controlfp(new, mask): abstract control word <-> x87 control word; only the modelled state is allowed */
static uint32_t cw_to_abstract(uint16_t cw) {
    uint32_t a = 0;
    if (cw & 0x01) a |= 0x10;       /* _EM_INVALID */
    if (cw & 0x02) a |= 0x80000;    /* _EM_DENORMAL */
    if (cw & 0x04) a |= 0x08;       /* _EM_ZERODIVIDE */
    if (cw & 0x08) a |= 0x04;       /* _EM_OVERFLOW */
    if (cw & 0x10) a |= 0x02;       /* _EM_UNDERFLOW */
    if (cw & 0x20) a |= 0x01;       /* _EM_INEXACT */
    a |= (uint32_t)((cw >> 10) & 3) << 8;            /* RC: 0 near, 0x100 down, 0x200 up, 0x300 chop */
    switch ((cw >> 8) & 3) {
    case 0: a |= 0x20000; break;    /* _PC_24 */
    case 2: a |= 0x10000; break;    /* _PC_53 */
    default: break;                 /* _PC_64 */
    }
    if (cw & 0x1000) a |= 0x40000;  /* _IC_AFFINE */
    return a;
}
static uint16_t abstract_to_cw(uint32_t a, uint16_t old) {
    uint16_t cw = (uint16_t)(old & 0xE0C0);
    if (a & 0x10) cw |= 0x01;
    if (a & 0x80000) cw |= 0x02;
    if (a & 0x08) cw |= 0x04;
    if (a & 0x04) cw |= 0x08;
    if (a & 0x02) cw |= 0x10;
    if (a & 0x01) cw |= 0x20;
    cw |= (uint16_t)(((a >> 8) & 3) << 10);
    cw |= (uint16_t)(((a & 0x30000) == 0x20000 ? 0 : (a & 0x30000) == 0x10000 ? 2 : 3) << 8);
    if (a & 0x40000) cw |= 0x1000;
    return cw;
}
static void hle_controlfp(CPU* c) {
    uint32_t nw = ARG(0), mask = ARG(1) & 0x000F031Fu | (ARG(1) & 0x70000u) | (ARG(1) & 0x80000u);
    uint32_t cur = cw_to_abstract(c->fcw), want = (nw & mask) | (cur & ~mask);
    uint16_t cw = abstract_to_cw(want, c->fcw);
    xrt_log("_controlfp(%08x, %08x): x87 control word %04x -> %04x", ARG(0), ARG(1), c->fcw, cw);
    xrt_fldcw(c, cw);
    RET_C(cw_to_abstract(c->fcw));
}

/* ---------------------------------------------------------------- stdio */

/* stdout is a text-mode FILE: fputwc converts with wctomb, which fails for characters above 0xFF in the
 * "C" locale; the formatter then counts -1 (see xrt_fmt.c for how the count recovers) */
static int stdout_put(void* ctx, uint16_t ch) {
    (void)ctx;
    return stdout_write(&ch, 1) == 1;
}

static void hle_wprintf(CPU* c) { RET_C((uint32_t)xrt_woutput(ARG(0), c->r[ESP] + 8, stdout_put, NULL)); }

static void hle_fflush(CPU* c) {
    uint32_t f = ARG(0);
    if (f && f != iob + 32 && f != iob + 64)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "fflush on a FILE other than stdout/stderr (%08x)", f);
    xrt_stdout_flush();
    RET_C(0);
}

/* _vsnwprintf's string FILE: _cnt = count*2 bytes (32-bit, wraps); each wide character takes 2 bytes and
 * is stored only while the decremented count is still non-negative as a signed value. U+FFFF is stored but
 * reported as a failure: fputwc returns the character, which then equals WEOF. */
typedef struct StrSink { uint32_t ptr, cnt; } StrSink;
static int str_put(void* ctx, uint16_t ch) {
    StrSink* s = (StrSink*)ctx;
    s->cnt -= 2;
    if (s->cnt & 0x80000000u)
        return 0;
    wr16(s->ptr, ch);
    s->ptr += 2;
    return ch != 0xFFFF;
}

/* returns the character count, or -1 when a character did not fit; the terminator is written as two
 * single bytes, each only if it still fits (so none when the output fills the buffer exactly) */
static void hle_vsnwprintf(CPU* c) {
    StrSink s;
    int32_t n;
    int k;
    s.ptr = ARG(0);
    s.cnt = ARG(1) * 2u;
    n = xrt_woutput(ARG(2), ARG(3), str_put, &s);
    for (k = 0; k < 2; k++) {
        s.cnt -= 1;
        if (!(s.cnt & 0x80000000u))
            wr8(s.ptr++, 0);
    }
    RET_C((uint32_t)n);
}

/* ---------------------------------------------------------------- time */
static void hle_time(CPU* c) {
    uint32_t t = (uint32_t)time(NULL);
    if (ARG(0))
        wr32(ARG(0), t);
    RET_C(t);
}
static void put_date_time(uint32_t buf, int wide, int date) {
    SYSTEMTIME st;
    char s[16];
    int i;
    GetLocalTime(&st);
    if (date)
        sprintf(s, "%02d/%02d/%02d", st.wMonth, st.wDay, st.wYear % 100);
    else
        sprintf(s, "%02d:%02d:%02d", st.wHour, st.wMinute, st.wSecond);
    for (i = 0; i < 9; i++) {
        if (wide)
            wr16(buf + 2u * (uint32_t)i, (uint8_t)s[i]);
        else
            wr8(buf + (uint32_t)i, (uint8_t)s[i]);
    }
}
static void hle_wstrdate(CPU* c) { put_date_time(ARG(0), 1, 1); RET_C(ARG(0)); }
static void hle_wstrtime(CPU* c) { put_date_time(ARG(0), 1, 0); RET_C(ARG(0)); }
static void hle_strdate(CPU* c) { put_date_time(ARG(0), 0, 1); RET_C(ARG(0)); }
static void hle_strtime(CPU* c) { put_date_time(ARG(0), 0, 0); RET_C(ARG(0)); }

/* ---------------------------------------------------------------- rand */
static void hle_srand(CPU* c) { c->thread->rand_seed = ARG(0); RET_C_VOID(); }
static void hle_rand(CPU* c) {
    XrtThread* t = c->thread;
    t->rand_seed = t->rand_seed * 214013u + 2531011u;
    RET_C((t->rand_seed >> 16) & 0x7FFFu);
}

/* ---------------------------------------------------------------- memory and wide strings (guest UTF-16) */
static void hle_memmove(CPU* c) { memmove(G2H(ARG(0)), G2H(ARG(1)), ARG(2)); RET_C(ARG(0)); }
static uint16_t fold(uint16_t ch) { return (ch >= 'A' && ch <= 'Z') ? (uint16_t)(ch + 32) : ch; }

static void hle_wcslen(CPU* c) { RET_C(xrt_guest_strlen16(ARG(0))); }
static void hle_wcscpy(CPU* c) {
    uint32_t d = ARG(0), s = ARG(1);
    uint16_t ch;
    do {
        ch = rd16(s);
        wr16(d, ch);
        s += 2;
        d += 2;
    } while (ch);
    RET_C(ARG(0));
}
static void hle_wcscat(CPU* c) {
    uint32_t d = ARG(0) + 2u * xrt_guest_strlen16(ARG(0)), s = ARG(1);
    uint16_t ch;
    do {
        ch = rd16(s);
        wr16(d, ch);
        s += 2;
        d += 2;
    } while (ch);
    RET_C(ARG(0));
}
static void hle_wcsncpy(CPU* c) {
    uint32_t d = ARG(0), s = ARG(1), n = ARG(2);
    while (n && rd16(s)) {
        wr16(d, rd16(s));
        d += 2;
        s += 2;
        n--;
    }
    while (n--) {
        wr16(d, 0);
        d += 2;
    }
    RET_C(ARG(0));
}
static void hle_wcscmp(CPU* c) {
    uint32_t a = ARG(0), b = ARG(1);
    int r;
    while ((r = (int)rd16(a) - (int)rd16(b)) == 0 && rd16(b)) {
        a += 2;
        b += 2;
    }
    RET_C(r < 0 ? -1 : r > 0 ? 1 : 0);
}
static void hle_wcsncmp(CPU* c) {
    uint32_t a = ARG(0), b = ARG(1), n = ARG(2);
    int r = 0;
    if (n) {
        while (--n && rd16(a) && rd16(a) == rd16(b)) {
            a += 2;
            b += 2;
        }
        r = (int)rd16(a) - (int)rd16(b);
    }
    RET_C((uint32_t)r);
}
static void hle_wcsicmp(CPU* c) {
    uint32_t a = ARG(0), b = ARG(1);
    uint16_t f, l;
    do {
        f = fold(rd16(a));
        l = fold(rd16(b));
        a += 2;
        b += 2;
    } while (f && f == l);
    RET_C((uint32_t)((int)f - (int)l));
}
static void hle_wcsnicmp(CPU* c) {
    uint32_t a = ARG(0), b = ARG(1), n = ARG(2);
    uint16_t f = 0, l = 0;
    if (n) {
        do {
            f = fold(rd16(a));
            l = fold(rd16(b));
            a += 2;
            b += 2;
        } while (--n && f && f == l);
    }
    RET_C((uint32_t)((int)f - (int)l));
}
static void hle_wcschr(CPU* c) {
    uint32_t s = ARG(0);
    uint16_t ch = (uint16_t)ARG(1);
    while (rd16(s) && rd16(s) != ch)
        s += 2;
    RET_C(rd16(s) == ch ? s : 0);
}
static void hle_wcsrchr(CPU* c) {
    uint32_t s = ARG(0), last = 0;
    uint16_t ch = (uint16_t)ARG(1);
    for (;; s += 2) {
        if (rd16(s) == ch)
            last = s;
        if (!rd16(s))
            break;
    }
    RET_C(last);
}
static void hle_wcsstr(CPU* c) {
    uint32_t s = ARG(0), w = ARG(1);
    if (!rd16(w)) {
        RET_C(s);
        return;
    }
    for (; rd16(s); s += 2) {
        uint32_t a = s, b = w;
        while (rd16(a) && rd16(b) && rd16(a) == rd16(b)) {
            a += 2;
            b += 2;
        }
        if (!rd16(b)) {
            RET_C(s);
            return;
        }
    }
    RET_C(0);
}
static void hle_wcsupr(CPU* c) {
    uint32_t s = ARG(0);
    for (; rd16(s); s += 2)
        if (rd16(s) >= 'a' && rd16(s) <= 'z')
            wr16(s, (uint16_t)(rd16(s) - 32));
    RET_C(ARG(0));
}
/* iswspace in the "C" locale: msvcr70's table below U+0100, the system's CT_CTYPE1 classification above
 * (U+FFFF is WEOF: not a space) */
static int wc_isspace(uint16_t ch) {
    WORD type;
    if (ch < 0x100)
        return (ch >= 0x09 && ch <= 0x0D) || ch == 0x20 || ch == 0xA0;
    if (ch == 0xFFFF)
        return 0;
    return GetStringTypeW(CT_CTYPE1, (LPCWSTR)&ch, 1, &type) && (type & C1_SPACE);
}
/* _wchartodigit: ASCII and fullwidth digits and the decimal digit blocks msvcr70 knows; -1 otherwise */
static int wc_digit(uint16_t ch) {
    static const uint16_t zeros[] = {0x0660, 0x06F0, 0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0C66, 0x0CE6,
                                     0x0D66, 0x0E50, 0x0ED0, 0x0F20, 0x1040, 0x17E0, 0x1810, 0xFF10};
    size_t i;
    if (ch >= '0' && ch <= '9')
        return ch - '0';
    for (i = 0; i < sizeof zeros / sizeof zeros[0]; i++)
        if (ch >= zeros[i] && ch < zeros[i] + 10)
            return ch - zeros[i];
    return -1;
}
/* msvcr70 _wtol (also _wtoi): skip iswspace, optional sign, accumulate digits (32-bit wrap, no overflow check) */
static void hle_wtoi(CPU* c) {
    uint32_t s = ARG(0), total = 0;
    uint16_t ch, sign;
    int d;
    while (wc_isspace(rd16(s)))
        s += 2;
    ch = sign = rd16(s);
    s += 2;
    if (ch == '-' || ch == '+') {
        ch = rd16(s);
        s += 2;
    }
    while ((d = wc_digit(ch)) != -1) {
        total = total * 10u + (uint32_t)d;
        ch = rd16(s);
        s += 2;
    }
    RET_C(sign == '-' ? 0u - total : total);
}

/* ---------------------------------------------------------------- narrow characters and strings ("C" locale) */
static void hle_toupper(CPU* c) {
    int32_t ch = (int32_t)ARG(0);
    RET_C((uint32_t)(ch >= 'a' && ch <= 'z' ? ch - ('a' - 'A') : ch));
}

static void hle_strchr(CPU* c) {
    uint32_t s = ARG(0);
    uint8_t ch = (uint8_t)ARG(1);
    for (;; s++) {
        uint8_t v = rd8(s);
        if (v == ch) {
            RET_C(s);
            return;
        }
        if (!v) {
            RET_C(0);
            return;
        }
    }
}

static uint8_t afold(uint8_t ch) { return (uint8_t)((uint8_t)(ch - 'A') < 26u ? ch + 0x20 : ch); }
static void hle_stricmp(CPU* c) {          /* __ascii_stricmp: A-Z folded to lower case, unsigned, -1/0/1 */
    uint32_t a = ARG(0), b = ARG(1);
    for (;; a++, b++) {
        uint8_t x = rd8(a), y = rd8(b);
        if (x == y) {
            if (!x) {
                RET_C(0);
                return;
            }
            continue;
        }
        x = afold(x);
        y = afold(y);
        if (x != y) {
            RET_C(x < y ? 0xFFFFFFFFu : 1u);
            return;
        }
    }
}

static void hle_atoi(CPU* c) {             /* atol: isspace, one sign, decimal digits, wrap-around */
    uint32_t s = ARG(0), total = 0;
    uint8_t ch, sign;
    while ((ch = rd8(s)) == ' ' || (ch >= 0x09 && ch <= 0x0D))
        s++;
    ch = sign = rd8(s++);
    if (ch == '-' || ch == '+')
        ch = rd8(s++);
    while (ch >= '0' && ch <= '9') {
        total = total * 10u + (uint32_t)(ch - '0');
        ch = rd8(s++);
    }
    RET_C(sign == '-' ? 0u - total : total);
}

/* sprintf: _output into an unbounded string stream (it never fails), then the terminator */
typedef struct StrOut { uint32_t dst, n; } StrOut;
static int strout_put(void* ctx, uint16_t ch) {
    StrOut* s = (StrOut*)ctx;
    wr8(s->dst + s->n++, (uint8_t)ch);
    return 1;
}
static void hle_sprintf(CPU* c) {
    StrOut s;
    int32_t r;
    s.dst = ARG(0);
    s.n = 0;
    r = xrt_output(ARG(1), c->r[ESP] + 12, strout_put, &s);
    wr8(s.dst + s.n, 0);
    RET_C((uint32_t)r);
}

/* ---------------------------------------------------------------- qsort
 * msvcr70's algorithm as read from the DLL: median of three (lo, mid, hi), a partition that skips elements
 * equal to the pivot and follows the pivot when it is swapped, the smaller part sorted first with the larger
 * one on a 30-entry stack, and a max-selection sort for 8 elements or fewer. The comparator is guest code
 * (cdecl) and sees the DLL's sequence of calls, so the order of equal keys is the DLL's too. */
static int qs_cmp(CPU* c, uint32_t comp, uint32_t a, uint32_t b) {
    uint32_t args[2];
    args[0] = a;
    args[1] = b;
    return (int32_t)xrt_call_guest(c, comp, 2, args, 0);
}

static void qs_swap(uint32_t a, uint32_t b, uint32_t width) {
    if (a != b)
        for (; width; width--, a++, b++) {
            uint8_t t = rd8(a);
            wr8(a, rd8(b));
            wr8(b, t);
        }
}

static void hle_qsort(CPU* c) {
    uint32_t base = ARG(0), num = ARG(1), width = ARG(2), comp = ARG(3);
    uint32_t lo, hi, mid, loguy, higuy, size, lostk[30], histk[30];
    int stkptr = 0;
    if (num < 2 || width == 0) {
        RET_C_VOID();
        return;
    }
    lo = base;
    hi = base + width * (num - 1);
recurse:
    size = (hi - lo) / width + 1;
    if (size <= 8) {
        while (hi > lo) {                   /* shortsort */
            uint32_t max = lo, p;
            for (p = lo + width; p <= hi; p += width)
                if (qs_cmp(c, comp, p, max) > 0)
                    max = p;
            qs_swap(max, hi, width);
            hi -= width;
        }
    } else {
        mid = lo + (size / 2) * width;
        if (qs_cmp(c, comp, lo, mid) > 0)
            qs_swap(lo, mid, width);
        if (qs_cmp(c, comp, lo, hi) > 0)
            qs_swap(lo, hi, width);
        if (qs_cmp(c, comp, mid, hi) > 0)
            qs_swap(mid, hi, width);
        loguy = lo;
        higuy = hi;
        for (;;) {
            if (mid > loguy)
                do
                    loguy += width;
                while (loguy < mid && qs_cmp(c, comp, loguy, mid) <= 0);
            if (mid <= loguy)
                do
                    loguy += width;
                while (loguy <= hi && qs_cmp(c, comp, loguy, mid) <= 0);
            do
                higuy -= width;
            while (higuy > mid && qs_cmp(c, comp, higuy, mid) > 0);
            if (higuy < loguy)
                break;
            qs_swap(loguy, higuy, width);
            if (mid == higuy)
                mid = loguy;
        }
        higuy += width;
        if (mid < higuy)
            do
                higuy -= width;
            while (higuy > mid && qs_cmp(c, comp, higuy, mid) == 0);
        if (mid >= higuy)
            do
                higuy -= width;
            while (higuy > lo && qs_cmp(c, comp, higuy, mid) == 0);
        if ((int32_t)(higuy - lo) >= (int32_t)(hi - loguy)) {
            if (lo < higuy) {
                lostk[stkptr] = lo;
                histk[stkptr++] = higuy;
            }
            if (loguy < hi) {
                lo = loguy;
                goto recurse;
            }
        } else {
            if (loguy < hi) {
                lostk[stkptr] = loguy;
                histk[stkptr++] = hi;
            }
            if (lo < higuy) {
                hi = higuy;
                goto recurse;
            }
        }
    }
    if (--stkptr >= 0) {
        lo = lostk[stkptr];
        hi = histk[stkptr];
        goto recurse;
    }
    RET_C_VOID();
}

/* ---------------------------------------------------------------- floating point
 * _CIpow/_CIfmod take x in st(1) and y in st(0) and leave the result in st(0). Domain errors set errno in the DLL;
 * errno is not modelled. Special operands follow the DLL as measured (tools/xrt/tests/crt_gatef), not C99.
 *
 * _CIpow: with every x87 and SSE exception masked (the engine's control word 0x027F) and SSE2 present, msvcr70
 * takes its SSE2 pow, whose result is a double. That code runs translated (xrt_msvcr70img.c): host pow() is not
 * the same algorithm (one ulp apart on about 0.1% of finite operands, two of them among VMProbe's inputs).
 * _CIfmod: msvcr70's x87 dispatcher, then an fprem loop (exact, as fmod() is). Special operands as the DLL: a NaN
 * operand propagates as the x87 does (quieted; of two, the larger significand), a zero or infinite divisor or an
 * infinite dividend gives the indefinite NaN, and a zero dividend gives +0 whatever its sign. */
#define NAN_INDEFINITE 0xFFF8000000000000ull

static double from_bits(uint64_t b) {
    double x;
    memcpy(&x, &b, 8);
    return x;
}

static double x87_nan_result(double x, double y) {   /* x87 propagation for an operation with a NaN operand */
    uint64_t a = dbits(x), b = dbits(y), qa = a | 1ull << 51, qb = b | 1ull << 51;
    int na = isnan(x), nb = isnan(y);
    if (na && nb)
        return from_bits((qa & 0x7FFFFFFFFFFFFFFFull) >= (qb & 0x7FFFFFFFFFFFFFFFull) ? qa : qb);
    return from_bits(na ? qa : qb);
}

static void hle_CIpow(CPU* c) {
    double y = *ST(c, 0), x = *ST(c, 1), r;
    uint32_t err;
    fpop(c);
    r = xrt_msvcr70_pow(c, x, y, &err);   /* err: the DLL's math error type (errno is not modelled) */
    *ST(c, 0) = r;
    if (mlog())
        fprintf(math_log, "pow %016llx %016llx %016llx %u\n", dbits(x), dbits(y), dbits(r), err);
    RET_C_VOID();
}

static void hle_CIfmod(CPU* c) {
    double y = *ST(c, 0), x = *ST(c, 1), r;
    fpop(c);
    if (isnan(x) || isnan(y))
        r = x87_nan_result(x, y);
    else if (isinf(x) || y == 0.0 || isinf(y))
        r = from_bits(NAN_INDEFINITE);
    else if (x == 0.0)
        r = 0.0;
    else
        r = fmod(x, y);
    *ST(c, 0) = r;
    if (mlog())
        fprintf(math_log, "fmod %016llx %016llx %016llx\n", dbits(x), dbits(y), dbits(r));
    RET_C_VOID();
}

static void hle_isnan(CPU* c) {           /* the DLL's test of the high word: QNaN or SNaN (not infinity) */
    uint32_t lo = ARG(0), hi = ARG(1), e = (hi >> 16) & 0x7FF8u;
    uint32_t r = (e == 0x7FF0u && ((hi & 0x7FFFFu) || lo)) || e == 0x7FF8u ? 1u : 0u;
    if (mlog())
        fprintf(math_log, "isnan %08x%08x %u\n", hi, lo, r);
    RET_C(r);
}

/* atof: _fltin2 -> __strgtold12 -> _ld12tod, ported from the DLL ("C" locale, decimal point '.').
 * Up to 25 mantissa digits are kept; with more than 24 the DLL keeps 24 and increments the 24th digit if it is
 * >= 5 (its own rounding quirk; the digit may become 10). The digits become an 80-bit integer (__mtold12), are
 * scaled by the printf engine's powers of ten (__multtenpow12 with its extension word cleared), and _ld12cvt
 * rounds to 53 bits: up when the bits below the rounding bit are nonzero, a tie truncates. 'D'/'d' are exponent
 * markers too; no digits gives +0.0; no inf/nan words. */
static int a_isdigit(uint8_t ch) { return ch >= '0' && ch <= '9'; }

static void m96_shl(uint32_t d[3]) {
    d[2] = d[2] << 1 | d[1] >> 31;
    d[1] = d[1] << 1 | d[0] >> 31;
    d[0] <<= 1;
}

static void m96_add(uint32_t d[3], const uint32_t t[3]) {
    uint32_t s = d[0] + t[0];
    if (s < d[0]) {
        if (++d[1] == 0)
            d[2]++;
    }
    d[0] = s;
    s = d[1] + t[1];
    if (s < d[1])
        d[2]++;
    d[1] = s;
    d[2] += t[2];
}

static void mtold12(const uint8_t* man, int n, uint16_t w[6]) {
    uint32_t d[3] = {0, 0, 0}, t[3];
    uint16_t expn = 0x404E;
    for (; n > 0; n--, man++) {
        memcpy(t, d, sizeof t);
        m96_shl(d);
        m96_shl(d);
        m96_add(d, t);
        m96_shl(d);
        t[0] = *man;
        t[1] = t[2] = 0;
        m96_add(d, t);
    }
    while (!d[2]) {
        d[2] = d[1] >> 16;
        d[1] = d[1] << 16 | d[0] >> 16;
        d[0] <<= 16;
        expn = (uint16_t)(expn - 16);
    }
    while (!(d[2] & 0x8000u)) {
        m96_shl(d);
        expn--;
    }
    w[0] = (uint16_t)d[0];
    w[1] = (uint16_t)(d[0] >> 16);
    w[2] = (uint16_t)d[1];
    w[3] = (uint16_t)(d[1] >> 16);
    w[4] = (uint16_t)d[2];
    w[5] = expn;
}

/* _ld12cvt helpers on a 96-bit mantissa, m[0] most significant, bit positions counted from its MSB */
static int man_zerotail(const uint32_t m[3], int nbit) {    /* all bits after position nbit zero */
    int nl = nbit / 32, k;
    if (m[nl] & ~(0xFFFFFFFFu << (31 - nbit % 32)))
        return 0;
    for (k = nl + 1; k < 3; k++)
        if (m[k])
            return 0;
    return 1;
}

static uint32_t man_inc(uint32_t m[3], int nbit) {          /* add 1 at position nbit; carry out of m[0] */
    int nl = nbit / 32;
    uint32_t old = m[nl], carry;
    m[nl] += 1u << (31 - nbit % 32);
    carry = m[nl] < old;
    for (nl--; nl >= 0 && carry; nl--)
        carry = ++m[nl] == 0;
    return carry;
}

static uint32_t man_round(uint32_t m[3], int precision) {  /* _RoundMan */
    int pos = precision % 32, nl = precision / 32, k;
    uint32_t r = 0;
    if ((m[nl] & 1u << (31 - pos)) && !man_zerotail(m, precision))
        r = man_inc(m, precision - 1);
    m[nl] &= 0xFFFFFFFFu << (31 - pos);   /* the DLL keeps the rounding bit itself; it is shifted out later */
    for (k = nl + 1; k < 3; k++)
        m[k] = 0;
    return r;
}

static void man_shr(uint32_t m[3], int n) {                /* _ShrMan */
    int nl = n / 32, nb = n % 32, k;
    uint32_t carry = 0;
    for (k = 0; k < 3; k++) {
        uint32_t v = m[k];
        m[k] = v >> nb | carry;
        carry = nb ? v << (32 - nb) : 0;
    }
    for (k = 2; k >= 0; k--)
        m[k] = k >= nl ? m[k - nl] : 0;
}

static uint64_t ld12_to_double(const uint16_t w[6]) {      /* _ld12tod (format: 53 bits, exponent -1023..1024) */
    uint32_t man[3], saved[3], bexp = 0;
    int exponent = (w[5] & 0x7FFF) - 0x3FFF;
    man[0] = w[3] | (uint32_t)w[4] << 16;
    man[1] = w[1] | (uint32_t)w[2] << 16;
    man[2] = (uint32_t)w[0] << 16;
    if (exponent == -0x3FFF) {
        memset(man, 0, sizeof man);                         /* zero, or a denormal flushed to zero */
    } else {
        memcpy(saved, man, sizeof saved);
        if (man_round(man, 53))
            exponent++;
        if (exponent < -1023 - 53) {
            memset(man, 0, sizeof man);
        } else if (exponent <= -1023) {                     /* denormal */
            memcpy(man, saved, sizeof man);
            man_shr(man, -1023 - exponent);
            man_round(man, 53);
            man_shr(man, 12);
        } else if (exponent >= 1024) {                      /* overflow: infinity */
            memset(man, 0, sizeof man);
            man[0] = 0x80000000u;
            man_shr(man, 11);
            bexp = 1024 + 1023;
        } else {
            man[0] &= 0x7FFFFFFFu;
            bexp = (uint32_t)(exponent + 1023);
            man_shr(man, 11);
        }
    }
    return (uint64_t)(bexp << 20 | (w[5] & 0x8000u ? 0x80000000u : 0) | man[0]) << 32 | man[1];
}

static void hle_atof(CPU* c) {
    uint32_t p = ARG(0), savedp;
    uint8_t man[25], ch;
    int state = 0, manlen = 0, found_digit = 0, found_decpoint = 0, found_exponent = 0, expsign = 1, exp_adj = 0;
    int32_t exponent = 0;
    uint16_t sign = 0, w[6] = {0, 0, 0, 0, 0, 0};
    uint64_t bits;
    double r;
    while ((ch = rd8(p)) == ' ' || (ch >= 0x09 && ch <= 0x0D))   /* atof: isspace */
        p++;
    savedp = p;                     /* __strgtold12 skips ' ', '\t', '\n', '\r': nothing left to skip */
    for (;;) {
        ch = rd8(p++);
        switch (state) {
        case 0:                     /* start */
            if (ch >= '1' && ch <= '9') {
                state = 3;
                p--;
            } else if (ch == '.') {
                state = 5;
            } else if (ch == '+' || ch == '-') {
                sign = ch == '-' ? 0x8000 : 0;
                state = 2;
            } else if (ch == '0') {
                state = 1;
            } else {
                p--;
                goto end;
            }
            continue;
        case 1:                     /* leading zeros */
            found_digit = 1;
            if (ch >= '1' && ch <= '9') {
                state = 3;
                p--;
            } else if (ch == '.') {
                state = 4;
            } else if (ch == '+' || ch == '-') {
                goto sign_after_mantissa;
            } else if (ch != '0') {
                goto exponent_marker;
            }
            continue;
        case 2:                     /* after the sign */
            if (ch >= '1' && ch <= '9') {
                state = 3;
                p--;
            } else if (ch == '.') {
                state = 5;
            } else if (ch == '0') {
                state = 1;
            } else {
                p = savedp;
                goto end;
            }
            continue;
        case 3:                     /* integer digits */
            found_digit = 1;
            for (; a_isdigit(ch); ch = rd8(p++)) {
                if (manlen < 25)
                    man[manlen++] = (uint8_t)(ch - '0');
                else
                    exp_adj++;
            }
            if (ch == '.') {
                state = 4;
                continue;
            }
            goto after_digits;
        case 4:                     /* fraction digits */
            found_digit = 1;
            found_decpoint = 1;
            if (manlen == 0)
                for (; ch == '0'; ch = rd8(p++))
                    exp_adj--;
            for (; a_isdigit(ch); ch = rd8(p++))
                if (manlen < 25) {
                    man[manlen++] = (uint8_t)(ch - '0');
                    exp_adj--;
                }
            goto after_digits;
        case 5:                     /* a decimal point first */
            found_decpoint = 1;
            if (a_isdigit(ch)) {
                state = 4;
                p--;
                continue;
            }
            p = savedp;
            goto end;
        case 6:                     /* after the exponent marker */
            savedp = p - 2;
            if (ch >= '1' && ch <= '9') {
                state = 9;
                p--;
            } else if (ch == '+' || ch == '-') {
                if (ch == '-')
                    expsign = -1;
                state = 7;
            } else if (ch == '0') {
                state = 8;
            } else {
                p = savedp;
                goto end;
            }
            continue;
        case 7:                     /* after the exponent sign */
            if (ch >= '1' && ch <= '9') {
                state = 9;
                p--;
            } else if (ch == '0') {
                state = 8;
            } else {
                p = savedp;
                goto end;
            }
            continue;
        case 8:                     /* exponent leading zeros */
            found_exponent = 1;
            while (ch == '0')
                ch = rd8(p++);
            if (ch >= '1' && ch <= '9') {
                state = 9;
                p--;
                continue;
            }
            p--;
            goto end;
        case 9:                     /* exponent digits */
            found_exponent = 1;
            for (; a_isdigit(ch); ch = rd8(p++)) {
                exponent = exponent * 10 + (ch - '0');
                if (exponent > 5200) {
                    exponent = 5201;
                    break;
                }
            }
            while (a_isdigit(ch))
                ch = rd8(p++);
            p--;
            goto end;
        }
    after_digits:
        if (ch == '+' || ch == '-')
            goto sign_after_mantissa;
    exponent_marker:
        if (ch == 'D' || ch == 'E' || ch == 'd' || ch == 'e') {
            state = 6;
            continue;
        }
        p--;
        goto end;
    sign_after_mantissa:            /* the DLL's implicit-exponent state; atof passes implicit_E = 0 */
        p--;
        goto end;
    }
end:
    (void)found_decpoint;           /* scale and decpt are 0 for atof: no adjustment depends on these */
    (void)found_exponent;
    if (!found_digit) {
        r = 0.0;                    /* SLD_NODIGITS: _fltin2 returns +0.0 */
    } else {
        if (manlen > 24) {
            if (man[23] >= 5)
                man[23]++;
            manlen = 24;
            exp_adj++;
        }
        if (manlen > 0) {
            int32_t pw;
            while (man[manlen - 1] == 0) {
                manlen--;
                exp_adj++;
            }
            mtold12(man, manlen, w);
            pw = (expsign < 0 ? -exponent : exponent) + exp_adj;
            if (pw > 5200) {
                memset(w, 0, sizeof w);
                w[4] = 0x8000;
                w[5] = 0x7FFF;
            } else if (pw < -5200) {
                memset(w, 0, sizeof w);
            } else if (pw) {
                w[0] = 0;           /* __multtenpow12(..., mult12 = 0) clears the extension word */
                if (pw >= 512) {    /* >= 10^512: _ld12tod overflows to infinity whatever the product */
                    memset(w, 0, sizeof w);
                    w[4] = 0x8000;
                    w[5] = 0x7FFF;
                } else if (pw <= -512) {   /* < 10^24 * 10^-512: below the smallest denormal, zero */
                    memset(w, 0, sizeof w);
                } else {
                    xrt_ld12_multtenpow12(w, pw);
                }
            }
        }
        w[5] |= sign;
        bits = ld12_to_double(w);
        memcpy(&r, &bits, sizeof r);
    }
    if (mlog()) {
        uint32_t s = ARG(0), k;
        fputs("atof ", math_log);
        for (k = 0; k < 256 && rd8(s + k); k++)
            fprintf(math_log, "%02x", rd8(s + k));
        fprintf(math_log, "%s %016llx\n", k ? "" : "-", dbits(r));
    }
    fpush(c, r);
    RET_C_VOID();
}

/* ---------------------------------------------------------------- unsupported paths with diagnostics */
static void hle_purecall(CPU* c) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_purecall: pure virtual function called"); }

const XrtHle xrt_hle_msvcr70[] = {
    {"msvcr70.dll", "malloc", hle_malloc},
    {"msvcr70.dll", "free", hle_free},
    {"msvcr70.dll", "realloc", hle_realloc},
    {"msvcr70.dll", "_msize", hle_msize},
    {"msvcr70.dll", "_initterm", hle_initterm},
    {"msvcr70.dll", "_onexit", hle_onexit},
    {"msvcr70.dll", "__dllonexit", hle_dllonexit},
    {"msvcr70.dll", "exit", hle_exit},
    {"msvcr70.dll", "_exit", hle__exit},
    {"msvcr70.dll", "__set_app_type", hle_set_app_type},
    {"msvcr70.dll", "__p__fmode", hle_p_fmode},
    {"msvcr70.dll", "__p__commode", hle_p_commode},
    {"msvcr70.dll", "__p___initenv", hle_p_initenv},
    {"msvcr70.dll", "__getmainargs", hle_getmainargs},
    {"msvcr70.dll", "_controlfp", hle_controlfp},
    {"msvcr70.dll", "wprintf", hle_wprintf},
    {"msvcr70.dll", "fflush", hle_fflush},
    {"msvcr70.dll", "_vsnwprintf", hle_vsnwprintf},
    {"msvcr70.dll", "time", hle_time},
    {"msvcr70.dll", "_wstrdate", hle_wstrdate},
    {"msvcr70.dll", "_wstrtime", hle_wstrtime},
    {"msvcr70.dll", "_strdate", hle_strdate},
    {"msvcr70.dll", "_strtime", hle_strtime},
    {"msvcr70.dll", "srand", hle_srand},
    {"msvcr70.dll", "rand", hle_rand},
    {"msvcr70.dll", "memmove", hle_memmove},
    {"msvcr70.dll", "wcslen", hle_wcslen},
    {"msvcr70.dll", "wcscpy", hle_wcscpy},
    {"msvcr70.dll", "wcscat", hle_wcscat},
    {"msvcr70.dll", "wcsncpy", hle_wcsncpy},
    {"msvcr70.dll", "wcscmp", hle_wcscmp},
    {"msvcr70.dll", "wcsncmp", hle_wcsncmp},
    {"msvcr70.dll", "_wcsicmp", hle_wcsicmp},
    {"msvcr70.dll", "_wcsnicmp", hle_wcsnicmp},
    {"msvcr70.dll", "wcschr", hle_wcschr},
    {"msvcr70.dll", "wcsrchr", hle_wcsrchr},
    {"msvcr70.dll", "wcsstr", hle_wcsstr},
    {"msvcr70.dll", "_wcsupr", hle_wcsupr},
    {"msvcr70.dll", "_wtoi", hle_wtoi},
    {"msvcr70.dll", "toupper", hle_toupper},
    {"msvcr70.dll", "strchr", hle_strchr},
    {"msvcr70.dll", "_stricmp", hle_stricmp},
    {"msvcr70.dll", "atoi", hle_atoi},
    {"msvcr70.dll", "sprintf", hle_sprintf},
    {"msvcr70.dll", "qsort", hle_qsort},
    {"msvcr70.dll", "_CIpow", hle_CIpow},
    {"msvcr70.dll", "_CIfmod", hle_CIfmod},
    {"msvcr70.dll", "_isnan", hle_isnan},
    {"msvcr70.dll", "atof", hle_atof},
    {"msvcr70.dll", "_purecall", hle_purecall},
    {"msvcr70.dll", "_CxxThrowException", xrt_eh_throw},
    {"msvcr70.dll", "_iob", NULL, 20 * 32},
    {"msvcr70.dll", "_adjust_fdiv", NULL, 4},
    {0},
};

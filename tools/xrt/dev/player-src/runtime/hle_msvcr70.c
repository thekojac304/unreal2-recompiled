/* hle_msvcr70.c - host adapters for the MSVCR70.dll imports of the translated modules (cdecl).
 *
 * Semantics follow msvcr70 in the "C" locale (no translated module calls setlocale: it is unbound), not the
 * host UCRT: string functions fold only A-Z, wcscmp returns -1/0/1, rand() is the msvcr70 per-thread LCG,
 * _vsnwprintf returns -1 on truncation and omits the terminator when the output fills the buffer exactly,
 * wide stdout output skips characters the "C" locale cannot convert (> 0xFF) and wprintf then counts as
 * _woutput does (xrt_fmt.c), and stdout is a text-mode stream ('\n' -> "\r\n"). qsort and atof are ports of
 * the DLL's own code (read from the binary). errno uses per-guest-thread storage. C++ exception
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
    /* The GUI CRT startup reads the imported char* itself, rather than calling GetCommandLineA. */
    wr32(xrt_hle_data("msvcr70.dll", "_acmdln"), xrt_cmdline_a);
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
    if (!s->ptr)                      /* NULL destination: the CRT's write_char only counts (_IOSTRG, _base NULL) */
        return 1;
    s->cnt -= 2;
    if (s->cnt & 0x80000000u)
        return 0;
    wr16(s->ptr, ch);
    s->ptr += 2;
    return ch != 0xFFFF;
}

/* returns the character count, or -1 when a character did not fit; the terminator is written as two
 * single bytes, each only if it still fits (so none when the output fills the buffer exactly). With a NULL
 * destination nothing is stored and the full length is returned - but the terminator store still happens when
 * count*2 is a positive int, and faults, as in the DLL (measured by experiments/xrt/tests/crt_diff). */
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
/* Measured x86 msvcr70!tolower: C locale compares the FULL signed int,
 * including EOF and values outside the byte domain. Neither errno nor last-error
 * changes. setlocale and _setmbcp remain unbound and fail explicitly if encountered;
 * host CRT locale and code-page tables must never select this adapter's behavior.
 * See tests/tolower_boundary for the native oracle and actual-runtime differential. */
static void hle_tolower(CPU* c) {
    int32_t ch = (int32_t)ARG(0);
    RET_C((uint32_t)(ch >= 'A' && ch <= 'Z' ? ch + ('a' - 'A') : ch));
}

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
/* swprintf(buffer, format, ...): msvcr70's pre-C99 form without a count - _woutput into an unbounded wide string
 * stream, then the terminator, as sprintf. Engine.dll logs with it during shutdown (owner's run 20261101-214813). */
static int wstrout_put(void* ctx, uint16_t ch) {
    StrOut* s = (StrOut*)ctx;
    wr16(s->dst + 2u * s->n++, ch);
    return 1;
}
static void hle_swprintf(CPU* c) {
    StrOut s;
    int32_t r;
    s.dst = ARG(0);
    s.n = 0;
    r = xrt_woutput(ARG(1), c->r[ESP] + 12, wstrout_put, &s);
    wr16(s.dst + 2u * s.n, 0);
    RET_C((uint32_t)r);
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

static void set_errno(CPU* c, uint32_t e);

/* msvcr70+98db floor / +97c0 ceil SSE2 paths, measured with floor_boundary
 * and the original appRound/appCeil calls.
 * Compute entirely on binary64 bits, independently of host libm/rounding mode.
 * SSE truncation/subtraction adds no x87 precision flag; the final FLD clears
 * C1, preserves C0/C2/C3/sticky flags, and quiets SNaN with IE. NaNs set EDOM.
 * The runtime's supported guest CW is deliberately narrower than the CRT's. */
static void hle_round_integral(CPU* c, int ceiling) {
    uint64_t b = (uint64_t)ARG(0) | (uint64_t)ARG(1) << 32, result = b;
    uint64_t magnitude = b & 0x7fffffffffffffffull;
    unsigned exponent = (unsigned)(magnitude >> 52);
    uint16_t before = fstatus(c);
    static unsigned kept[2];
    if (c->fcw != 0x027f)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "%s: unmeasured x87 control word %04x", ceiling ? "ceil" : "floor", c->fcw);
    c->fsw &= (uint16_t)~0x0200; /* FLD C1=0 (no stack overflow in the measured ABI). */
    if (exponent == 0x7ff) {
        if (magnitude & 0xfffffffffffffull) {
            if (!(b & 0x8000000000000ull)) c->fsw |= 1;
            result |= 0x8000000000000ull;
            set_errno(c, 33);
        }
    } else if (exponent < 1023) {
        if (ceiling) result = b >> 63 ? 0x8000000000000000ull : (magnitude ? 0x3ff0000000000000ull : 0);
        else result = b >> 63 ? (magnitude ? 0xbff0000000000000ull : b) : 0;
    } else if (exponent < 1075) {
        uint64_t unit = 1ull << (1075 - exponent), mask = unit - 1;
        result = b & ~mask;
        if ((ceiling ? !(b >> 63) : (b >> 63)) && (b & mask)) result += unit;
    }
    fpush(c, from_bits(result));
    if (mlog()) fprintf(math_log, "%s %016llx %016llx %04x %04x %04x\n", ceiling ? "ceil" : "floor", b, result, c->fcw, before, fstatus(c));
    if (kept[ceiling]++ < 32)
        xrt_event(ceiling ? "crt_ceil" : "crt_floor", "\"input\":\"%016llx\",\"result\":\"%016llx\",\"cw\":\"%04x\",\"sw_before\":\"%04x\",\"sw_after\":\"%04x\",\"caller\":\"%08x\"",
                  b, result, c->fcw, before, fstatus(c), rd32(c->r[ESP]));
    RET_C_VOID();
}
static void hle_floor(CPU* c) { hle_round_integral(c, 0); }
static void hle_ceil(CPU* c) { hle_round_integral(c, 1); }

/* ldexp (vorbis.dll's codebook float unpacking): x * 2^n is exact in binary64 apart from the final rounding of a
 * subnormal or overflowing result, which IEEE round-to-nearest fixes; host ldexp computes exactly that. ERANGE
 * when a finite operand overflows to infinity or a nonzero one underflows to zero. Non-finite operands are
 * unmeasured (fatal) rather than guessed. */
static void hle_ldexp(CPU* c) {
    uint64_t b = (uint64_t)ARG(0) | (uint64_t)ARG(1) << 32;
    double x = from_bits(b), r;
    int n = (int)ARG(2);
    if (!isfinite(x))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "ldexp of a non-finite operand (%016llx) is unmeasured", b);
    r = ldexp(x, n);
    if (isinf(r) || (r == 0.0 && x != 0.0))
        set_errno(c, 34);
    c->fsw &= (uint16_t)~0x0200;
    fpush(c, r);
    RET_C_VOID();
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

/* _CIacos/_CIasin: x in st(0), result replaces it. Developer approximation: host
 * libm, not msvcr70's translated SSE2 path (may differ in the last ulp). NaN
 * operands propagate quieted; |x|>1 gives the indefinite NaN and EDOM. */
static void hle_inverse_trig(CPU* c, int arcsine) {
    double x = *ST(c, 0), r;
    static unsigned kept[2];
    if (isnan(x))
        r = from_bits(dbits(x) | 1ull << 51);
    else if (x > 1.0 || x < -1.0) {
        r = from_bits(NAN_INDEFINITE);
        set_errno(c, 33);
    } else
        r = arcsine ? asin(x) : acos(x);
    *ST(c, 0) = r;
    if (kept[arcsine]++ < 32)
        xrt_event(arcsine ? "crt_asin" : "crt_acos", "\"input\":\"%016llx\",\"result\":\"%016llx\",\"caller\":\"%08x\"",
                  dbits(x), dbits(r), rd32(c->r[ESP]));
    RET_C_VOID();
}
static void hle_CIacos(CPU* c) { hle_inverse_trig(c, 0); }
/* _CIsin/_CIcos/_CItan/_CIsqrt: st(0) -> st(0); _CIatan2: y in st(1), x in st(0).
 * Developer approximation via host libm (sqrt is exact). NaN propagates quieted;
 * infinite trig operands and negative sqrt give the indefinite NaN and EDOM. */
static void hle_unary_math(CPU* c, int op) {
    double x = *ST(c, 0), r;
    if (isnan(x))
        r = from_bits(dbits(x) | 1ull << 51);
    else if ((op < 3 && isinf(x)) || (op == 3 && x < 0.0)) {
        r = from_bits(NAN_INDEFINITE);
        set_errno(c, 33);
    } else
        r = op == 0 ? sin(x) : op == 1 ? cos(x) : op == 2 ? tan(x) : sqrt(x);
    *ST(c, 0) = r;
    RET_C_VOID();
}
static void hle_CIsin(CPU* c) { hle_unary_math(c, 0); }
static void hle_CIcos(CPU* c) { hle_unary_math(c, 1); }
static void hle_CItan(CPU* c) { hle_unary_math(c, 2); }
static void hle_CIsqrt(CPU* c) { hle_unary_math(c, 3); }
static void hle_CIatan2(CPU* c) {
    double x = *ST(c, 0), y = *ST(c, 1);
    fpop(c);
    *ST(c, 0) = isnan(x) || isnan(y) ? x87_nan_result(y, x) : atan2(y, x);
    RET_C_VOID();
}
static void hle_CIasin(CPU* c) { hle_inverse_trig(c, 1); }

/* _ftol: FISTP qword of st(0) with RC=chop (CW saved/restored), result in EDX:EAX,
 * st(0) popped. Out-of-range/NaN store the integer indefinite and set IE;
 * an inexact conversion sets PE, as the x87 store does. */
static void hle_ftol(CPU* c) {
    double x = *ST(c, 0), t;
    uint64_t r;
    fpop(c);
    if (isnan(x) || x >= 9223372036854775808.0 || x < -9223372036854775808.0) {
        r = 0x8000000000000000ull;
        c->fsw |= 1;
    } else {
        t = trunc(x);
        r = (uint64_t)(int64_t)t;
        if (t != x) c->fsw |= 0x20;
    }
    c->r[EDX] = (uint32_t)(r >> 32);
    RET_C((uint32_t)r);
}
static void hle_finite(CPU* c) {          /* exponent field not all ones */
    RET_C(((ARG(1) >> 20) & 0x7FFu) != 0x7FFu ? 1u : 0u);
}
static void hle_clock(CPU* c) { RET_C((uint32_t)clock()); }

/* C-locale ctype (msvcr70 _ctype masks); outside 0..255 (incl. EOF) is 0. */
static unsigned c_ctype(uint32_t ch) {
    if (ch > 255) return 0;
    if (ch >= '0' && ch <= '9') return 0x84;
    if (ch >= 'A' && ch <= 'Z') return ch <= 'F' ? 0x181 : 0x101;
    if (ch >= 'a' && ch <= 'z') return ch <= 'f' ? 0x182 : 0x102;
    if (ch == ' ') return 0x48;
    if (ch == 9) return 0x68;
    if (ch >= 10 && ch <= 13) return 0x28;
    return 0;
}
static void hle_isalpha(CPU* c) { RET_C(c_ctype(ARG(0)) & 0x103); }
static void hle_isdigit(CPU* c) { RET_C(c_ctype(ARG(0)) & 0x04); }
static void hle_isalnum(CPU* c) { RET_C(c_ctype(ARG(0)) & 0x107); }
static void hle_isspace(CPU* c) { RET_C(c_ctype(ARG(0)) & 0x08); }
static void hle_calloc(CPU* c) {
    uint64_t n = (uint64_t)ARG(0) * ARG(1);
    uint32_t p = n > 0xFFFFFFE0u ? 0 : xrt_heap_alloc(n ? (uint32_t)n : 1u);
    if (p) memset(G2H(p), 0, (size_t)n);
    RET_C(p);
}
static void hle_strdup(CPU* c) {
    uint32_t s = ARG(0), n = 0, p;
    if (!s) { RET_C(0); return; }
    while (rd8(s + n)) n++;
    p = xrt_heap_alloc(n + 1);
    if (p) memcpy(G2H(p), G2H(s), n + 1);
    RET_C(p);
}
static void hle_strstr(CPU* c) {
    uint32_t h = ARG(0), nd = ARG(1), i;
    if (!rd8(nd)) { RET_C(h); return; }
    for (; rd8(h); h++) {
        for (i = 0; rd8(nd + i) && rd8(h + i) == rd8(nd + i); i++) {}
        if (!rd8(nd + i)) { RET_C(h); return; }
    }
    RET_C(0);
}
static void hle_strnicmp(CPU* c) {         /* ASCII folding, unsigned, -1/0/1 like _stricmp */
    uint32_t a = ARG(0), b = ARG(1), n = ARG(2);
    for (; n; n--, a++, b++) {
        uint8_t x = afold(rd8(a)), y = afold(rd8(b));
        if (x != y) { RET_C(x < y ? 0xFFFFFFFFu : 1u); return; }
        if (!x) break;
    }
    RET_C(0);
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

/* ---------------------------------------------------------------- errno and the DOS-error map
 * errno is msvcr70's per-thread int (_tiddata + 8); _errno returns its address. The adapters below set it as the DLL
 * does; the older adapters do not touch it (their callers on the measured paths never read it). */
static uint32_t errno_va[64];
static uint32_t errno_addr(CPU* c) {
    int i = c->thread->index;
    if (!errno_va[i])
        errno_va[i] = xrt_rt_alloc(4, 4);
    return errno_va[i];
}
static void set_errno(CPU* c, uint32_t e) { wr32(errno_addr(c), e); }
static void hle_errno(CPU* c) { RET_C(errno_addr(c)); }

/* _dosmaperr: the DLL's own 45-entry {Win32 error, errno} table (msvcr70+0x4bb10, read from its SHA-checked image),
 * then 19..36 -> EACCES, 188..202 -> ENOEXEC, else EINVAL. _doserrno is not modelled (nothing imports it). */
static void dosmaperr(CPU* c, uint32_t oserr) {
    const uint8_t* img = xrt_msvcr70_image();
    uint32_t k, code, e;
    for (k = 0; k < 45; k++) {
        memcpy(&code, img + 0x4BB10 + 8 * k, 4);
        if (code == oserr) {
            memcpy(&e, img + 0x4BB14 + 8 * k, 4);
            set_errno(c, e);
            return;
        }
    }
    set_errno(c, oserr >= 19 && oserr <= 36 ? 13u : oserr >= 188 && oserr <= 202 ? 8u : 22u);
}

/* ---------------------------------------------------------------- FILETIME -> time_t (the _finddata_t time fields)
 * A port of the DLL's machine code: __timet_from_ft (msvcr70+0x17ee3), __loctotime_t (+0x31816), __tzset (+0x3ad5)
 * and _tzset_lk (+0x3b05), _isindst (+0x3316, +0x3336) and cvtdate (+0x3423), with the DLL's _days/_lpdays tables
 * and the initial _timezone/_daylight/_dstbias (28800, 1, -3600) read from its image.
 * - A zero FILETIME -> -1. FileTimeToLocalFileTime, then FileTimeToSystemTime (either failing -> -1, the Win32 error
 *   mirrored). FileTimeToLocalFileTime applies the bias in effect NOW, not the one at the file's date; both
 *   processes call it on the same machine, so the host call is the DLL's.
 * - __loctotime_t(local date, dstflag -1): a local year outside 1970..2038 -> -1; else the seconds of the local
 *   date as if UTC + _timezone, + _dstbias when _daylight and _isindst, all in 32-bit arithmetic (no clamp: local
 *   2038-01-18 23:14:07 with _timezone 18000 wraps to -2147480049).
 * - __tzset runs _tzset_lk once, at the first in-range conversion; the values stay fixed for the process (nothing
 *   else bound to the guest runs it: the DLL's time() is GetSystemTimeAsFileTime). TZ comes from the environment
 *   as the DLL's _environ has it (the process's startup environment; the host's getenv reads the same snapshot).
 *   TZ unset or empty: GetTimeZoneInformation; _timezone = 60 * (Bias, + StandardBias when StandardDate.wMonth);
 *   when DaylightDate.wMonth and DaylightBias are both non-zero _daylight = 1 and _dstbias = 60 * (DaylightBias -
 *   StandardBias), else both 0. If the call fails the DLL keeps its initial values and the USA rules.
 *   TZ set: "AAA[-]h[:m[:s]]..." parsed as the DLL does (its atol, 32-bit wraparound), _daylight = the character
 *   after the offset (non-zero: DST by the USA rules), _dstbias keeps -3600. A TZ shorter than 3 characters is
 *   fatal (the DLL then parses past the end of the string).
 * - _isindst (for the local date's year, cached per year as the DLL does): with GetTimeZoneInformation, DST starts
 *   at DaylightDate and ends at StandardDate (standard time, moved by _dstbias to daylight time), as day-in-month
 *   rules (wDay = week, 5 = last) when wYear is 0, else as that month and day in the converted year; the USA rules
 *   compiled into the DLL are the first Sunday of April 02:00 to the last Sunday of October 02:00. Both orders
 *   (southern hemisphere: start after end) as the DLL. On the start day DST from the transition's time of day on
 *   (>=), on the end day until it (<), so a repeated local hour at the end of DST counts as standard time.
 * Compared with the DLL's own __timet_from_ft in a 32-bit process (6.7 million FILETIMEs over 1969-12-25..2039-01-05,
 * minute steps around each year's transitions; TZ unset, empty and 13 TZ strings): identical. Only the host's time
 * zone (US Eastern, day-in-month rules) was exercised through GetTimeZoneInformation. */
typedef struct {
    int32_t yr, yd, ms;   /* the DLL's dststart/dstend: tm_year computed for (-1: none), year-day, ms of that day */
} DstTrans;
static SRWLOCK tz_lock = SRWLOCK_INIT;
static int tz_done, tz_apiused;
static int32_t tz_timezone, tz_daylight, tz_dstbias;
static TIME_ZONE_INFORMATION tz_info;
static DstTrans dst_start, dst_end;

static int32_t img32(uint32_t rva) {
    int32_t v;
    memcpy(&v, xrt_msvcr70_image() + rva, 4);
    return v;
}

/* _lpdays (rva 0x4ad40) / _days (rva 0x4ad74)[i]: the year-day of the last day of month i (0-based; [0] = -1) */
static int32_t month_days(int leap, int32_t i) {
    if (i < 0 || i > 12)
        xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "msvcr70 time conversion: month table index %d (not modelled)", i);
    return img32((leap ? 0x4AD40u : 0x4AD74u) + 4u * (uint32_t)i);
}

static int is_leap(int32_t y) { return (y % 4 == 0 && y % 100 != 0) || (y + 1900) % 400 == 0; }   /* y: tm_year */

/* atol in the "C" locale: isspace skipped, one sign, decimal digits, 32-bit wraparound */
static int32_t crt_atol(const char* s) {
    uint32_t t = 0;
    int ch, sign;
    while (*s == ' ' || (*s >= '\t' && *s <= '\r'))
        s++;
    ch = (unsigned char)*s++;
    sign = ch;
    if (ch == '-' || ch == '+')
        ch = (unsigned char)*s++;
    while (ch >= '0' && ch <= '9') {
        t = 10u * t + (uint32_t)(ch - '0');
        ch = (unsigned char)*s++;
    }
    return (int32_t)(sign == '-' ? 0u - t : t);
}

static void tzset_lk(void) {
    const char* tz = getenv("TZ");
    tz_timezone = img32(0x4903C);
    tz_daylight = img32(0x49040);
    tz_dstbias = img32(0x49048);
    dst_start.yr = dst_end.yr = -1;
    tz_apiused = 0;
    if (tz && *tz) {
        const char* p = tz + 3;
        uint32_t z;
        int neg = 0;
        if (strlen(tz) < 3)
            xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "TZ=\"%s\": msvcr70's _tzset parses past a TZ shorter than 3 "
                      "characters (not modelled)", tz);
        if (*p == '-') {
            neg = 1;
            p++;
        }
        z = (uint32_t)crt_atol(p) * 3600u;
        while (*p == '+' || (*p >= '0' && *p <= '9'))
            p++;
        if (*p == ':') {
            z += (uint32_t)crt_atol(++p) * 60u;
            while (*p >= '0' && *p <= '9')
                p++;
            if (*p == ':') {
                z += (uint32_t)crt_atol(++p);
                while (*p >= '0' && *p <= '9')
                    p++;
            }
        }
        tz_timezone = (int32_t)(neg ? 0u - z : z);
        tz_daylight = (signed char)*p;
        return;
    }
    if (GetTimeZoneInformation(&tz_info) == TIME_ZONE_ID_INVALID)
        return;
    tz_apiused = 1;
    tz_timezone = tz_info.Bias * 60;
    if (tz_info.StandardDate.wMonth)
        tz_timezone += tz_info.StandardBias * 60;
    if (tz_info.DaylightDate.wMonth && tz_info.DaylightBias) {
        tz_daylight = 1;
        tz_dstbias = (tz_info.DaylightBias - tz_info.StandardBias) * 60;
    } else {
        tz_daylight = 0;
        tz_dstbias = 0;
    }
}

/* trantype 1: DST start, 0: DST end; datetype 1: the week'th (5 = last) dayofweek of month, 0: day `date` of month */
static void cvtdate(int trantype, int datetype, int32_t year, int32_t month, int32_t week, int32_t dayofweek,
                    int32_t date, int32_t hour, int32_t min, int32_t sec, int32_t msec) {
    int leap = is_leap(year);
    int32_t yearday, monthdow, ms;
    if (datetype == 1) {
        yearday = 1 + month_days(leap, month - 1);
        monthdow = (yearday + year * 365 + (year - 1) / 4 - (year - 1) / 100 + (year + 299) / 400 - 25563) % 7;
        yearday += dayofweek - monthdow + (monthdow <= dayofweek ? week - 1 : week) * 7;
        if (week == 5 && yearday > month_days(leap, month))
            yearday -= 7;
    } else {
        yearday = month_days(leap, month - 1) + date;
    }
    ms = (hour * 60 + min) * 60;
    if (trantype == 1) {
        dst_start.yd = yearday;
        dst_start.ms = (ms + sec) * 1000 + msec;
        dst_start.yr = year;
    } else {
        ms = (ms + tz_dstbias + sec) * 1000 + msec;
        if (ms < 0) {
            ms += 86400000;
            yearday--;
        } else if (ms >= 86400000) {
            ms -= 86400000;
            yearday++;
        }
        dst_end.yd = yearday;
        dst_end.ms = ms;
        dst_end.yr = year;
    }
}

static void cvt_api_date(int trantype, int32_t year, const SYSTEMTIME* d) {
    if (d->wYear)
        cvtdate(trantype, 0, year, d->wMonth, 0, 0, d->wDay, d->wHour, d->wMinute, d->wSecond, d->wMilliseconds);
    else
        cvtdate(trantype, 1, year, d->wMonth, d->wDay, d->wDayOfWeek, 0, d->wHour, d->wMinute, d->wSecond,
                d->wMilliseconds);
}

static int isindst(int32_t year, int32_t yday, int32_t hour, int32_t min, int32_t sec) {
    int32_t ms;
    if (!tz_daylight)
        return 0;
    if (year != dst_start.yr || year != dst_end.yr) {
        if (tz_apiused) {
            cvt_api_date(1, year, &tz_info.DaylightDate);
            cvt_api_date(0, year, &tz_info.StandardDate);
        } else {
            cvtdate(1, 1, year, 4, 1, 0, 0, 2, 0, 0, 0);
            cvtdate(0, 1, year, 10, 5, 0, 0, 2, 0, 0, 0);
        }
    }
    if (dst_start.yd < dst_end.yd) {
        if (yday < dst_start.yd || yday > dst_end.yd)
            return 0;
        if (yday > dst_start.yd && yday < dst_end.yd)
            return 1;
    } else {
        if (yday < dst_end.yd || yday > dst_start.yd)
            return 1;
        if (yday > dst_end.yd && yday < dst_start.yd)
            return 0;
    }
    ms = ((hour * 60 + min) * 60 + sec) * 1000;
    return yday == dst_start.yd ? ms >= dst_start.ms : ms < dst_end.ms;
}

/* __loctotime_t with dstflag -1 (its only caller here); 0x7C558180 = -2208988800 (1900-01-01 .. 1970-01-01) */
static uint32_t loctotime(int32_t yr, int32_t mo, int32_t dy, int32_t hr, int32_t mn, int32_t sc) {
    int32_t y = yr - 1900, yday;
    uint32_t t;
    if (y < 70 || y > 138)
        return 0xFFFFFFFFu;
    yday = month_days(0, mo - 1) + dy;
    if (is_leap(y) && mo > 2)
        yday++;
    if (!tz_done) {
        tzset_lk();
        tz_done = 1;
    }
    t = (uint32_t)(y * 365 + (y - 1) / 4 - (y - 1) / 100 + (y + 299) / 400 + yday);
    t = ((t * 24u + (uint32_t)hr) * 60u + (uint32_t)mn) * 60u + (uint32_t)tz_timezone + (uint32_t)sc + 0x7C558180u;
    if (tz_daylight && isindst(y, yday, hr, mn, sc))
        t += (uint32_t)tz_dstbias;
    return t;
}

static uint32_t timet_from_ft(CPU* c, const FILETIME* ft) {
    FILETIME lft;
    SYSTEMTIME st;
    uint32_t t;
    if (!ft->dwLowDateTime && !ft->dwHighDateTime)
        return 0xFFFFFFFFu;
    if (!FileTimeToLocalFileTime(ft, &lft) || !FileTimeToSystemTime(&lft, &st)) {
        xrt_set_last_error(c, GetLastError());
        return 0xFFFFFFFFu;
    }
    AcquireSRWLockExclusive(&tz_lock);
    t = loctotime(st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    ReleaseSRWLockExclusive(&tz_lock);
    return t;
}

/* ---------------------------------------------------------------- directories (GlmLib's editor-mode file scans)
 * _findfirst/_findnext/_findclose: FindFirstFileA/FindNextFileA/FindClose and the DLL's _finddata_t {attrib (0 for
 * FILE_ATTRIBUTE_NORMAL), time_create, time_access, time_write (timet_from_ft above, in that order), size =
 * nFileSizeLow, name[260]}; errno: Win32 2, 3 and 18 -> ENOENT, 8 -> ENOMEM, else EINVAL. The handle is a guest
 * handle (the DLL returns the Win32 HANDLE). */
static void put_finddata(CPU* c, uint32_t fd, const WIN32_FIND_DATAA* w) {
    wr32(fd, w->dwFileAttributes == FILE_ATTRIBUTE_NORMAL ? 0 : w->dwFileAttributes);
    wr32(fd + 4, timet_from_ft(c, &w->ftCreationTime));
    wr32(fd + 8, timet_from_ft(c, &w->ftLastAccessTime));
    wr32(fd + 12, timet_from_ft(c, &w->ftLastWriteTime));
    wr32(fd + 16, w->nFileSizeLow);
    memcpy(G2H(fd + 20), w->cFileName, strlen(w->cFileName) + 1);
}

static void find_failed(CPU* c) {
    DWORD e = GetLastError();
    xrt_set_last_error(c, e);
    set_errno(c, e == 2 || e == 3 || e == 18 ? 2u : e == 8 ? 12u : 22u);
}

/* player content overlay (xrt_internal.h): a merged listing's wide entry in the ANSI form _finddata_t is built from */
static void finddata_a(WIN32_FIND_DATAA* a, const WIN32_FIND_DATAW* w) {
    memset(a, 0, sizeof *a);
    a->dwFileAttributes = w->dwFileAttributes;
    a->ftCreationTime = w->ftCreationTime;
    a->ftLastAccessTime = w->ftLastAccessTime;
    a->ftLastWriteTime = w->ftLastWriteTime;
    a->nFileSizeHigh = w->nFileSizeHigh;
    a->nFileSizeLow = w->nFileSizeLow;
    WideCharToMultiByte(CP_ACP, 0, w->cFileName, -1, a->cFileName, sizeof a->cFileName, NULL, NULL);
}
static void hle_findfirst(CPU* c) {
    WIN32_FIND_DATAA w;
    WIN32_FIND_DATAW fw;
    WCHAR pattern[MAX_PATH * 2];
    void* list = MultiByteToWideChar(CP_ACP, 0, (LPCSTR)G2H(ARG(0)), -1, pattern, MAX_PATH * 2)
                     ? xrt_overlay_find_first((const uint16_t*)pattern) : NULL;
    HANDLE h;
    if (list) {
        int ok = xrt_overlay_find_next(list, &fw);
        xrt_log("_findfirst(\"%s\") -> %ls (content overlay)", (const char*)G2H(ARG(0)), ok ? fw.cFileName : L"none");
        if (!ok) {
            xrt_overlay_find_close(list);
            SetLastError(ERROR_FILE_NOT_FOUND);
            find_failed(c);
            RET_C(0xFFFFFFFFu);
            return;
        }
        finddata_a(&w, &fw);
        put_finddata(c, ARG(1), &w);
        RET_C(xrt_handle_new(XH_FINDLIST, list));
        return;
    }
    h = FindFirstFileA((LPCSTR)G2H(ARG(0)), &w);
    xrt_log("_findfirst(\"%s\") -> %s", (const char*)G2H(ARG(0)), h == INVALID_HANDLE_VALUE ? "none" : w.cFileName);
    if (h == INVALID_HANDLE_VALUE) {
        find_failed(c);
        RET_C(0xFFFFFFFFu);
        return;
    }
    put_finddata(c, ARG(1), &w);
    RET_C(xrt_handle_new(XH_FIND, h));
}

static void hle_findnext(CPU* c) {
    WIN32_FIND_DATAA w;
    WIN32_FIND_DATAW fw;
    HANDLE h = (HANDLE)xrt_handle_get(ARG(0), XH_FIND);
    void* list = xrt_handle_get(ARG(0), XH_FINDLIST);
    if (list) {
        if (!xrt_overlay_find_next(list, &fw)) {
            SetLastError(ERROR_NO_MORE_FILES);
            find_failed(c);
            RET_C(0xFFFFFFFFu);
            return;
        }
        finddata_a(&w, &fw);
        put_finddata(c, ARG(1), &w);
        RET_C(0);
        return;
    }
    if (!h || !FindNextFileA(h, &w)) {
        if (!h)
            SetLastError(ERROR_INVALID_HANDLE);
        find_failed(c);
        RET_C(0xFFFFFFFFu);
        return;
    }
    put_finddata(c, ARG(1), &w);
    RET_C(0);
}

static void hle_findclose(CPU* c) {
    HANDLE h = (HANDLE)xrt_handle_get(ARG(0), XH_FIND);
    void* list = xrt_handle_get(ARG(0), XH_FINDLIST);
    if (list) {
        xrt_overlay_find_close(list);
        xrt_handle_free(ARG(0));
        RET_C(0);
        return;
    }
    if (!h || !FindClose(h)) {
        set_errno(c, 22);
        RET_C(0xFFFFFFFFu);
        return;
    }
    xrt_handle_free(ARG(0));
    RET_C(0);
}

/* _getcwd (_getdcwd for the current drive): GetCurrentDirectoryA into 260 bytes; a NULL buffer is malloc'ed with
 * max(length + 1, maxlen); a short buffer -> ERANGE; failure or a longer path -> NULL without errno, as the DLL */
static uint32_t getcwd_impl(CPU* c, uint32_t buf, int32_t maxlen) {
    char dir[0x104];
    DWORD r = GetCurrentDirectoryA(0x104, dir);
    int32_t len;
    if (!r || r + 1 > 0x104)
        return 0;
    len = (int32_t)r + 1;
    if (!buf) {
        buf = xrt_heap_alloc((uint32_t)(len > maxlen ? len : maxlen));
        if (!buf) {
            set_errno(c, 12);
            return 0;
        }
    } else if (len > maxlen) {
        set_errno(c, 34);
        return 0;
    }
    memcpy(G2H(buf), dir, (size_t)len);
    return buf;
}
static void hle_getcwd(CPU* c) { RET_C(getcwd_impl(c, ARG(0), (int32_t)ARG(1))); }

/* _fullpath: GetFullPathNameA; an empty or NULL path is _getcwd; a NULL buffer is malloc'ed (260 bytes) */
static void hle_fullpath(CPU* c) {
    uint32_t user = ARG(0), buf = ARG(0), rel = ARG(1), maxlen = ARG(2), r;
    if (!rel || !rd8(rel)) {
        RET_C(getcwd_impl(c, buf, (int32_t)maxlen));
        return;
    }
    if (!buf) {
        if (!(buf = xrt_heap_alloc(0x104))) {
            set_errno(c, 12);
            RET_C(0);
            return;
        }
        maxlen = 0x104;
    }
    r = GetFullPathNameA((LPCSTR)G2H(rel), maxlen, (LPSTR)G2H(buf), NULL);
    xrt_log("_fullpath(\"%s\") -> %u", (const char*)G2H(rel), r);
    if (r >= maxlen || !r) {
        DWORD e = GetLastError();
        if (!user)
            xrt_heap_free(c, buf);
        if (r)
            set_errno(c, 34);
        else
            dosmaperr(c, e);
        RET_C(0);
        return;
    }
    RET_C(buf);
}

/* _chdir (msvcr70+0x18c08): SetCurrentDirectoryA(path); then GetCurrentDirectoryA into 0x105 bytes and, unless that
 * is a UNC path (two equal leading '\\' or '/'), SetEnvironmentVariableA("=X:", directory) with X its drive letter
 * upper-cased by _mbctoupper (in the DLL's ANSI-code-page MBCS state: ASCII a-z -> A-Z, other ASCII unchanged; the
 * per-drive current directory that drive-relative paths resolve against). Any of the three failing -> -1, errno by
 * _dosmaperr(GetLastError()) (the Win32 error mirrored), else 0; a failure after SetCurrentDirectoryA keeps the
 * new directory, as in the DLL. Sandbox guard: a path that resolves outside the sandbox is fatal. A path the guard
 * cannot resolve (GetFullPathNameW fails, e.g. "" or blanks, or the path does not fit its buffers) is passed to
 * SetCurrentDirectoryA, which resolves it the same way and fails as in the DLL ("": ERROR_INVALID_NAME -> EINVAL);
 * should it succeed instead, that is fatal. A current directory longer than the DLL's buffer (whose contents are
 * then undefined) or starting with a non-ASCII byte is fatal (not modelled). */
static void chdir_failed(CPU* c) {
    DWORD e = GetLastError();
    xrt_set_last_error(c, e);
    dosmaperr(c, e);
    RET_C(0xFFFFFFFFu);
}

static void hle_chdir(CPU* c) {
    const char* p = (const char*)G2H(ARG(0));
    WCHAR w[MAX_PATH * 2], full[MAX_PATH * 2];
    char q[600], dir[0x105], var[4];
    DWORD n;
    int resolved = MultiByteToWideChar(CP_ACP, 0, p, -1, w, MAX_PATH * 2) != 0;
    if (resolved) {
        n = GetFullPathNameW(w, MAX_PATH * 2, full, NULL);
        resolved = n != 0 && n < MAX_PATH * 2;
    }
    if (resolved && !xrt_path_is_inside_sandbox(w))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_chdir outside the sandbox refused: \"%s\"", p);
    xrt_event("chdir", "\"path\": %s", xrt_jstr(q, sizeof q, p));
    if (!SetCurrentDirectoryA(p)) {
        chdir_failed(c);
        return;
    }
    if (!resolved)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_chdir(\"%.300s\"): the sandbox guard could not resolve the path but "
                  "SetCurrentDirectoryA accepted it", p);
    n = GetCurrentDirectoryA(sizeof dir, dir);
    if (!n) {
        chdir_failed(c);
        return;
    }
    if (n >= sizeof dir)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_chdir: a current directory of %u bytes does not fit the DLL's buffer "
                  "(not modelled)", n);
    if (dir[0] & 0x80)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_chdir: current directory \"%s\" starts with a non-ASCII byte (the DLL's "
                  "_mbctoupper of it is not modelled)", dir);
    if ((dir[0] == '\\' || dir[0] == '/') && dir[1] == dir[0]) {
        RET_C(0);
        return;
    }
    var[0] = '=';
    var[1] = dir[0] >= 'a' && dir[0] <= 'z' ? (char)(dir[0] - 'a' + 'A') : dir[0];
    var[2] = ':';
    var[3] = 0;
    if (!SetEnvironmentVariableA(var, dir)) {
        chdir_failed(c);
        return;
    }
    RET_C(0);
}

/* ---------------------------------------------------------------- fopen/fclose
 * msvcr70's fopen is _fsopen(.., _SH_DENYNO): a FILE from the static _iob entries 3..19 (the first free one, as
 * _getstream takes them) on a lowio descriptor (the first free from 3; 0..2 are the standard handles). Modes r, w,
 * a with '+', 'b', 't' as the DLL parses them; the other mode letters are not modelled (fatal). Only fopen and
 * fclose and bounded binary fread exist for such a FILE. Text reads, writes and
 * unmeasured stream modes remain explicit failures. A file opened for writing must be inside the sandbox. */
static HANDLE lowio[64];
static int lowio_binary[64];
static uint32_t lowio_buffer[64];

/* fopen and _wfopen: one implementation; the wide name (when given) reaches CreateFileW unchanged. */
static void open_stream(CPU* c, const char* name, const WCHAR* wname, const char* m);
static void hle_fopen(CPU* c) {
    open_stream(c, (const char*)G2H(ARG(0)), NULL, (const char*)G2H(ARG(1)));
}
/* _wfopen (ALAudio's GetOggDuration opens ..\Voice\ and ..\Music\ .ogg files for vorbisfile's ov_open). */
static void hle__wfopen(CPU* c) {
    char name[MAX_PATH * 2], mode[16];
    const WCHAR* w = (const WCHAR*)G2H(ARG(0));
    const WCHAR* wm = (const WCHAR*)G2H(ARG(1));
    if (wcslen(wm) >= sizeof mode || !WideCharToMultiByte(CP_ACP, 0, wm, -1, mode, sizeof mode, NULL, NULL) ||
        !WideCharToMultiByte(CP_ACP, 0, w, -1, name, sizeof name, NULL, NULL))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_wfopen: name or mode conversion failed");
    open_stream(c, name, w, mode);
}
static void open_stream(CPU* c, const char* name, const WCHAR* wname, const char* m) {
    const char* mode0 = m;
    DWORD access, disp, e;
    uint32_t stream = 0, flag, k;
    int fd = 0, rdwr = 0, more = 1,binary=0;
    char q[600];
    HANDLE h;
    WCHAR content[MAX_PATH * 2];   /* player: the installation path a read resolves to */
    switch (*m) {
    case 'r': access = GENERIC_READ; disp = OPEN_EXISTING; flag = 0x01; break;
    case 'w': access = GENERIC_WRITE; disp = CREATE_ALWAYS; flag = 0x02; break;
    case 'a': access = GENERIC_WRITE; disp = OPEN_ALWAYS; flag = 0x02;
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "fopen(\"%s\", \"%s\"): append mode is not modelled", name, m);
    default:
        set_errno(c, 22);
        RET_C(0);
        return;
    }
    for (m++; *m && more; m++) {
        if (*m == '+' && !rdwr) {
            rdwr = 1;
            access = GENERIC_READ | GENERIC_WRITE;
            flag = 0x80;
        } else if (*m == 'b' || *m == 't' || *m == '+') {
            if(*m=='b') binary=1;
            if(*m=='t') binary=0;
            /* A repeated '+' ends parsing, as in the measured CRT. */
            more = *m != '+';
        } else if (strchr("cnSRTD", *m)) {
            xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "fopen mode letter '%c' is not modelled", *m);
        } else {
            more = 0;
        }
    }
    if (access & GENERIC_WRITE) {
        WCHAR w[MAX_PATH * 2];
        if (wname ? !xrt_path_is_inside_sandbox(wname)
                  : (!MultiByteToWideChar(CP_ACP, 0, name, -1, w, MAX_PATH * 2) || !xrt_path_is_inside_sandbox(w)))
            xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "fopen for writing outside the sandbox refused: \"%s\"", name);
    } else if (xrt_content_root[0]) {
        /* player: a read of an installation file the private game root does not have (xrt_internal.h) */
        WCHAR w[MAX_PATH * 2];
        if ((wname || MultiByteToWideChar(CP_ACP, 0, name, -1, w, MAX_PATH * 2)) &&
            xrt_overlay_read_path((const uint16_t*)(wname ? wname : w), (uint16_t*)content, MAX_PATH * 2))
            wname = content;
    }
    for (k = 3; k < 20 && !stream; k++)
        if (!(rd32(iob + 32 * k + 12) & 0x83))
            stream = iob + 32 * k;
    for (k = 3; k < 64 && !fd; k++)
        if (!lowio[k])
            fd = (int)k;
    if (!stream || !fd)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "fopen: more open FILEs than the runtime models");
    h = wname ? CreateFileW(wname, access, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, disp, FILE_ATTRIBUTE_NORMAL, NULL)
              : CreateFileA(name, access, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, disp, FILE_ATTRIBUTE_NORMAL, NULL);
    xrt_event("fopen", "\"path\": %s, \"mode\": \"%s\", \"wide\": %s, \"ok\": %s", xrt_jstr(q, sizeof q, name),
              mode0, wname ? "true" : "false", h == INVALID_HANDLE_VALUE ? "false" : "true");
    if (h == INVALID_HANDLE_VALUE) {
        e = GetLastError();
        xrt_set_last_error(c, e);
        dosmaperr(c, e);
        RET_C(0);
        return;
    }
    lowio[fd] = h;
    lowio_binary[fd]=binary;
    lowio_buffer[fd]=0;
    memset(G2H(stream), 0, 32);
    wr32(stream + 12, flag);
    wr32(stream + 16, (uint32_t)fd);
    RET_C(stream);
}
static uint32_t file_descriptor(CPU* c,uint32_t f) {
    uint32_t fd;
    if(f<iob+3*32 || f>=iob+20*32 || (f-iob)%32 || !(rd32(f+12)&0x83) || (fd=rd32(f+16))>=64 || !lowio[fd])
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"binary stream was not returned by live fopen (%08x)",f);
    return fd;
}
static int binary_read(CPU* c,uint32_t f,uint32_t fd,uint32_t dst,uint32_t bytes) {
    DWORD got=0,error;
    SetLastError(xrt_get_last_error(c));
    if(!ReadFile(lowio[fd],G2H(dst),bytes,&got,NULL)) {
        error=GetLastError();xrt_set_last_error(c,error);dosmaperr(c,error);
        wr32(f+12,rd32(f+12)|0x20);return -1;
    }
    xrt_set_last_error(c,GetLastError());
    if(!got) wr32(f+12,rd32(f+12)|0x10);
    return (int)got;
}
static void hle_fread(CPU* c) {
    uint32_t dst=ARG(0),size=ARG(1),count=ARG(2),f=ARG(3),fd,remaining,total,buffer,capacity,n;
    int got;
    /* The CRT wrapper locks its FILE even for zero-sized reads. */
    fd=file_descriptor(c,f);
    if(!size || !count) {RET_C(0);return;}
    if((uint64_t)size*count>0x7fffffffu)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fread size overflow/large transfer is unmeasured");
    if(!lowio_binary[fd]) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fread text translation is not implemented");
    if(!(rd32(f+12)&1)) {
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fread requires a measured read-only binary stream");
    }
    total=remaining=size*count;
    while(remaining) {
        buffer=rd32(f+8);capacity=buffer?rd32(f+24):4096;
        if(buffer && (buffer!=lowio_buffer[fd] || (capacity!=4096 && capacity!=512) || rd32(f)<buffer || rd32(f)>buffer+capacity || rd32(f+4)>buffer+capacity-rd32(f)))
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fread FILE buffer layout was changed outside supported operations");
        if(buffer && (int32_t)rd32(f+4)>0) {
            n=rd32(f+4);if(n>remaining)n=remaining;
            memcpy(G2H(dst),G2H(rd32(f)),n);wr32(f,rd32(f)+n);wr32(f+4,rd32(f+4)-n);
        } else if(remaining>=capacity) {
            wr32(f+24,capacity);
            n=remaining/capacity*capacity;
            got=binary_read(c,f,fd,dst,n);if(got<=0)break;
            n=(uint32_t)got;
        } else {
            if(!buffer) {
                buffer=xrt_heap_alloc(4096);capacity=4096;
                lowio_buffer[fd]=buffer;
                wr32(f+8,buffer);wr32(f+24,capacity);wr32(f+12,rd32(f+12)|8);
            }
            wr32(f,buffer);wr32(f+4,0);
            got=binary_read(c,f,fd,buffer,capacity);
            wr32(f+24,4096); /* _filbuf restores the normal next-fill size after fseek's small read. */
            if(got<=0)break;
            wr32(f+4,(uint32_t)got);continue;
        }
        dst+=n;remaining-=n;
    }
    xrt_event("fread","\"stream\": %u, \"size\": %u, \"count\": %u, \"bytes\": %u, \"flags\": %u",f,size,count,total-remaining,rd32(f+12));
    RET_C((total-remaining)/size);
}
static void hle_fseek(CPU* c) {
    uint32_t f=ARG(0),fd=file_descriptor(c,f),origin=ARG(2),flags=rd32(f+12);
    LARGE_INTEGER distance,result;DWORD error;
    if(!lowio_binary[fd] || !(flags&1) || (flags&0x80))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fseek supports measured read-only binary streams");
    if(origin>2) {set_errno(c,22);RET_C(0xffffffffu);return;}
    distance.QuadPart=(int32_t)ARG(1);
    if(origin==1) distance.QuadPart-=(int32_t)rd32(f+4);
    wr32(f+12,flags&~0x10u);wr32(f,rd32(f+8));wr32(f+4,0);
    if(flags&8) wr32(f+24,512);
    SetLastError(xrt_get_last_error(c));
    if(!SetFilePointerEx(lowio[fd],distance,&result,origin)) {
        error=GetLastError();xrt_set_last_error(c,error);dosmaperr(c,error);RET_C(0xffffffffu);return;
    }
    xrt_set_last_error(c,GetLastError());
    if(result.QuadPart>0x7fffffff) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fseek beyond measured 32-bit file range");
    xrt_event("fseek","\"stream\": %u, \"offset\": %d, \"origin\": %u, \"position\": %u",f,(int32_t)ARG(1),origin,(uint32_t)result.QuadPart);
    RET_C(0);
}
/* ftell on the same measured read-only binary streams (vorbisfile's ov_open callbacks): the OS file position
 * minus the bytes still buffered (_cnt), as the CRT computes it for a binary read stream. */
static void hle_ftell(CPU* c) {
    uint32_t f=ARG(0),fd=file_descriptor(c,f),flags=rd32(f+12);
    LARGE_INTEGER zero,pos;DWORD error;int32_t cnt=(int32_t)rd32(f+4);
    if(!lowio_binary[fd] || !(flags&1) || (flags&0x80))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ftell supports measured read-only binary streams");
    zero.QuadPart=0;
    SetLastError(xrt_get_last_error(c));
    if(!SetFilePointerEx(lowio[fd],zero,&pos,FILE_CURRENT)) {
        error=GetLastError();xrt_set_last_error(c,error);dosmaperr(c,error);RET_C(0xffffffffu);return;
    }
    xrt_set_last_error(c,GetLastError());
    if(cnt<0 || pos.QuadPart<cnt || pos.QuadPart>0x7fffffff)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ftell: unmeasured stream state (position %lld, buffered %d)",pos.QuadPart,cnt);
    RET_C((uint32_t)(pos.QuadPart-cnt));
}

static void hle_fclose(CPU* c) {
    uint32_t f = ARG(0), fd;
    if (f < iob + 3 * 32 || f >= iob + 20 * 32 || (f - iob) % 32 || !(rd32(f + 12) & 0x83) || (fd = rd32(f + 16)) >= 64
        || !lowio[fd])
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "fclose of a FILE that fopen did not return (%08x)", f);
    CloseHandle(lowio[fd]);
    lowio[fd] = NULL;
    if((rd32(f+12)&8) && rd32(f+8)) xrt_heap_free(c,rd32(f+8));
    lowio_buffer[fd]=0;
    memset(G2H(f), 0, 32);
    RET_C(0);
}

/* ---------------------------------------------------------------- more narrow strings */
static void hle_vsprintf(CPU* c) {                   /* _output into an unbounded string stream, then the NUL */
    StrOut s;
    int32_t r;
    s.dst = ARG(0);
    s.n = 0;
    r = xrt_output(ARG(1), ARG(2), strout_put, &s);
    wr8(s.dst + s.n, 0);
    RET_C((uint32_t)r);
}

static void hle_strrchr(CPU* c) {
    uint32_t s = ARG(0), last = 0;
    uint8_t ch = (uint8_t)ARG(1), v;
    do {
        v = rd8(s);
        if (v == ch)
            last = s;
        s++;
    } while (v);
    RET_C(last);
}

static void hle_strncpy(CPU* c) {
    uint32_t d = ARG(0), s = ARG(1), n = ARG(2), k = 0;
    for (; k < n && rd8(s + k); k++)
        wr8(d + k, rd8(s + k));
    for (; k < n; k++)
        wr8(d + k, 0);
    RET_C(d);
}

/* _set_se_translator: msvcr70 keeps one translator per thread (_tiddata._translator) and returns the previous one.
 * Structured exceptions are not modelled - a hardware fault stays fatal and is never translated - so the translator
 * is recorded (and returned by the next call), never invoked. Editor.dll installs one during its initialisation. */
static uint32_t se_translator[64];
static void hle_set_se_translator(CPU* c) {
    uint32_t old = se_translator[c->thread->index];
    se_translator[c->thread->index] = ARG(0);
    xrt_event("se_translator", "\"translator\": \"0x%08x\"", ARG(0));
    RET_C(old);
}

/* ---------------------------------------------------------------- unsupported paths with diagnostics */
static void hle_purecall(CPU* c) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_purecall: pure virtual function called"); }

const XrtHle xrt_hle_msvcr70[] = {
    {"msvcr70.dll", "malloc", hle_malloc},
    {"msvcr70.dll", "free", hle_free},
    /* msvcr70 operator new/new[] are malloc (size 0 -> 1, NULL on failure); delete/delete[] are free. */
    {"msvcr70.dll", "??2@YAPAXI@Z", hle_malloc},
    {"msvcr70.dll", "??_U@YAPAXI@Z", hle_malloc},
    {"msvcr70.dll", "??3@YAXPAX@Z", hle_free},
    {"msvcr70.dll", "??_V@YAXPAX@Z", hle_free},
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
    {"msvcr70.dll", "_control87", hle_controlfp}, /* same modelled x87 control word, incl. _EM_DENORMAL */
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
    {"msvcr70.dll", "?_set_se_translator@@YAP6AXIPAU_EXCEPTION_POINTERS@@@ZP6AXI0@Z@Z", hle_set_se_translator},
    {"msvcr70.dll", "_errno", hle_errno},
    {"msvcr70.dll", "_findfirst", hle_findfirst},
    {"msvcr70.dll", "_findnext", hle_findnext},
    {"msvcr70.dll", "_findclose", hle_findclose},
    {"msvcr70.dll", "_getcwd", hle_getcwd},
    {"msvcr70.dll", "_fullpath", hle_fullpath},
    {"msvcr70.dll", "_chdir", hle_chdir},
    {"msvcr70.dll", "fopen", hle_fopen},
    {"msvcr70.dll", "fclose", hle_fclose},
    {"msvcr70.dll", "fread", hle_fread},
    {"msvcr70.dll", "fseek", hle_fseek},
    {"msvcr70.dll", "ftell", hle_ftell},
    {"msvcr70.dll", "_wfopen", hle__wfopen},
    {"msvcr70.dll", "ldexp", hle_ldexp},
    {"msvcr70.dll", "vsprintf", hle_vsprintf},
    {"msvcr70.dll", "strrchr", hle_strrchr},
    {"msvcr70.dll", "strncpy", hle_strncpy},
    {"msvcr70.dll", "tolower", hle_tolower},
    {"msvcr70.dll", "toupper", hle_toupper},
    {"msvcr70.dll", "strchr", hle_strchr},
    {"msvcr70.dll", "_stricmp", hle_stricmp},
    {"msvcr70.dll", "atoi", hle_atoi},
    {"msvcr70.dll", "sprintf", hle_sprintf},
    {"msvcr70.dll", "swprintf", hle_swprintf},
    {"msvcr70.dll", "qsort", hle_qsort},
    {"msvcr70.dll", "_CIpow", hle_CIpow},
    {"msvcr70.dll", "_CIfmod", hle_CIfmod},
    {"msvcr70.dll", "_ftol", hle_ftol},
    {"msvcr70.dll", "_CIsin", hle_CIsin},
    {"msvcr70.dll", "_CIcos", hle_CIcos},
    {"msvcr70.dll", "_CItan", hle_CItan},
    {"msvcr70.dll", "_CIsqrt", hle_CIsqrt},
    {"msvcr70.dll", "_CIatan2", hle_CIatan2},
    {"msvcr70.dll", "isalpha", hle_isalpha},
    {"msvcr70.dll", "isdigit", hle_isdigit},
    {"msvcr70.dll", "isalnum", hle_isalnum},
    {"msvcr70.dll", "isspace", hle_isspace},
    {"msvcr70.dll", "calloc", hle_calloc},
    {"msvcr70.dll", "_strdup", hle_strdup},
    {"msvcr70.dll", "strstr", hle_strstr},
    {"msvcr70.dll", "_strnicmp", hle_strnicmp},
    {"msvcr70.dll", "_finite", hle_finite},
    {"msvcr70.dll", "clock", hle_clock},
    {"msvcr70.dll", "_CIacos", hle_CIacos},
    {"msvcr70.dll", "_CIasin", hle_CIasin},
    {"msvcr70.dll", "floor", hle_floor},
    {"msvcr70.dll", "ceil", hle_ceil},
    {"msvcr70.dll", "_isnan", hle_isnan},
    {"msvcr70.dll", "atof", hle_atof},
    {"msvcr70.dll", "_purecall", hle_purecall},
    {"msvcr70.dll", "_CxxThrowException", xrt_eh_throw},
    {"msvcr70.dll", "_iob", NULL, 20 * 32},
    {"msvcr70.dll", "_adjust_fdiv", NULL, 4},
    {"msvcr70.dll", "_acmdln", NULL, 4},
    {0},
};

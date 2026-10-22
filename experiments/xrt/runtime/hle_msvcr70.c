/* hle_msvcr70.c - host adapters for the MSVCR70.dll imports of UCC.exe and Core.dll (cdecl).
 *
 * Semantics follow msvcr70 in the "C" locale (neither module calls setlocale), not the host UCRT:
 * string functions fold only A-Z, wcscmp returns -1/0/1, rand() is the msvcr70 per-thread LCG,
 * _vsnwprintf returns -1 on truncation and omits the terminator when the output fills the buffer exactly,
 * wide stdout output skips characters the "C" locale cannot convert (> 0xFF) and wprintf then counts as
 * _woutput does (xrt_fmt.c), and stdout is a text-mode stream ('\n' -> "\r\n"). Exception dispatch
 * (_CxxThrowException and the frame handlers) is not supported: reaching it is fatal with a description
 * of the thrown object. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <fcntl.h>
#include <io.h>
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

/* ---------------------------------------------------------------- heap */
static void hle_malloc(CPU* c) { RET_C(xrt_heap_alloc(ARG(0))); }
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
/* msvcr70 _woutput over a character sink (xrt_fmt.c). Declared here because only these adapters use it. */
int32_t xrt_woutput(uint32_t fmt, uint32_t va, int (*put)(void* ctx, uint16_t ch), void* ctx);

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

/* ---------------------------------------------------------------- unsupported paths with diagnostics */
static void hle_purecall(CPU* c) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_purecall: pure virtual function called"); }

static void hle_cxxthrow(CPU* c) {
    uint32_t obj = ARG(0), ti = ARG(1);
    char tname[128] = "?", what[512] = "";
    if (ti && xrt_is_committed(ti, 16)) {
        uint32_t cta = rd32(ti + 12);
        if (cta && xrt_is_committed(cta, 8)) {
            uint32_t ct = rd32(cta + 4);
            if (ct && xrt_is_committed(ct, 8)) {
                uint32_t td = rd32(ct + 4);
                if (td && xrt_is_committed(td + 8, 64))
                    snprintf(tname, sizeof tname, "%s", (const char*)G2H(td + 8));
            }
        }
    }
    if (obj && xrt_is_committed(obj, 4) && (!strncmp(tname, ".PAG", 4) || !strncmp(tname, ".PBG", 4))) {
        uint32_t s = rd32(obj);
        int i;
        for (i = 0; s && i < 200 && xrt_is_committed(s + 2u * (uint32_t)i, 2) && rd16(s + 2u * (uint32_t)i); i++)
            what[i] = (char)(rd16(s + 2u * (uint32_t)i) < 128 ? rd16(s + 2u * (uint32_t)i) : '?');
        what[i] = 0;
    }
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "C++ exception thrown (type %s%s%s%s); exception dispatch is not supported by this runtime",
              tname, what[0] ? ", message \"" : "", what, what[0] ? "\"" : "");
}

const XrtHle xrt_hle_msvcr70[] = {
    {"msvcr70.dll", "malloc", hle_malloc},
    {"msvcr70.dll", "free", hle_free},
    {"msvcr70.dll", "realloc", hle_realloc},
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
    {"msvcr70.dll", "_purecall", hle_purecall},
    {"msvcr70.dll", "_CxxThrowException", hle_cxxthrow},
    {"msvcr70.dll", "_iob", NULL, 20 * 32},
    {"msvcr70.dll", "_adjust_fdiv", NULL, 4},
    {0},
};

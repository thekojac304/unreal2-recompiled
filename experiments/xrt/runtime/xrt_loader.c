/* xrt_loader.c - guest module mapping, import binding, exports and the control-transfer dispatcher.
 *
 * The original PE files are read from the sandbox only as data (headers, .rdata, .data, and .text for
 * the constant tables code reads from it); their SHA-256 must equal the hash recorded when the code was
 * lifted. Nothing from them is ever executed: control only reaches lifted functions or host adapters.
 *
 * IAT slots receive what a Windows loader would put there, expressed as guest addresses:
 *   import from another translated module -> that module's export VA
 *   import implemented by a host adapter   -> a stub address in XRT_STUB_BASE.. that dispatches to it
 *   CRT data import (e.g. _iob)            -> a guest-memory object owned by the adapter
 *   anything else                          -> a named stub that is fatal when called */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <ctype.h>
#include <stdlib.h>
#include "xrt_internal.h"

#define MAX_MODULES 8
static XrtModule mods[MAX_MODULES];
static int nmods;

typedef struct Stub {
    char name[600];                /* "kernel32.dll!Sleep" */
    XrtFn fn;                      /* NULL: unbound import, fatal when called */
    uint64_t calls[MAX_MODULES + 1];
} Stub;
static Stub stubs[(XRT_STUB_END - XRT_STUB_BASE) / XRT_STUB_SIZE - 1];
static int nstubs;

typedef struct DataObj { char key[96]; uint32_t va; } DataObj;
static DataObj dataobjs[32];
static int ndata;

typedef struct ExportName { uint32_t va; const char* name; } ExportName;
static ExportName* exnames;
static int nexnames;

int xrt_module_count(void) { return nmods; }
XrtModule* xrt_module_get(int i) { return i >= 0 && i < nmods ? &mods[i] : NULL; }

XrtModule* xrt_module_by_addr(uint32_t va) {
    int i;
    for (i = 0; i < nmods; i++)
        if (va - mods[i].base < mods[i].size)
            return &mods[i];
    return NULL;
}

static const char* basename_of(const char* p) {
    const char* b = p;
    for (; *p; p++)
        if (*p == '\\' || *p == '/' || *p == ':')
            b = p + 1;
    return b;
}

XrtModule* xrt_module_by_name(const char* name) {
    char want[128];
    size_t n;
    int i;
    snprintf(want, sizeof want, "%s", basename_of(name));
    n = strlen(want);
    for (i = 0; i < nmods; i++) {
        const char* have = mods[i].name;
        size_t hn = strlen(have);
        if (!_stricmp(have, want))
            return &mods[i];
        if (hn > 4 && n == hn - 4 && !_strnicmp(have, want, n) && !_stricmp(have + n, ".dll"))
            return &mods[i];
    }
    return NULL;
}

static void sha256_hex(const uint8_t* data, size_t n, char out[65]) {
    uint8_t h[32];
    int i;
    if (BCryptHash(BCRYPT_SHA256_ALG_HANDLE, NULL, 0, (PUCHAR)data, (ULONG)n, h, 32) != 0) {
        fprintf(stderr, "xrt: SHA-256 unavailable\n");
        exit(XRT_EXIT_SETUP);
    }
    for (i = 0; i < 32; i++)
        sprintf(out + 2 * i, "%02x", h[i]);
}

static int cmp_exname(const void* a, const void* b) {
    uint32_t x = ((const ExportName*)a)->va, y = ((const ExportName*)b)->va;
    return x < y ? -1 : x > y;
}

XrtModule* xrt_module_load(const char* host_path, const XrtLiftedModule* lifted) {
    FILE* f = fopen(host_path, "rb");
    uint8_t* file;
    long len;
    char digest[65];
    XrtModule* m;
    uint32_t pe, nsec, opt, i, hdrsize;
    if (!f)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "cannot open %s", host_path);
    fseek(f, 0, SEEK_END);
    len = ftell(f);
    fseek(f, 0, SEEK_SET);
    file = (uint8_t*)malloc((size_t)len);
    if (!file || fread(file, 1, (size_t)len, f) != (size_t)len)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "cannot read %s", host_path);
    fclose(f);
    sha256_hex(file, (size_t)len, digest);
    if (strcmp(digest, lifted->sha256))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "%s has SHA-256 %s but the translated code was lifted from %s", host_path, digest,
                  lifted->sha256);
    if (nmods == MAX_MODULES)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "too many modules");
    m = &mods[nmods];
    memset(m, 0, sizeof *m);
    snprintf(m->path, sizeof m->path, "%s", host_path);
    snprintf(m->name, sizeof m->name, "%s", basename_of(host_path));
    m->lifted = lifted;
    pe = *(uint32_t*)(file + 0x3C);
    nsec = *(uint16_t*)(file + pe + 6);
    opt = pe + 24;
    if (*(uint32_t*)(file + opt + 28) != lifted->base || *(uint32_t*)(file + opt + 56) != lifted->size)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "%s: image base/size differ from the lifted image", host_path);
    m->base = lifted->base;
    m->size = lifted->size;
    m->entry = *(uint32_t*)(file + opt + 16) ? m->base + *(uint32_t*)(file + opt + 16) : 0;
    m->is_dll = (*(uint16_t*)(file + pe + 22) & 0x2000) != 0;
    if (!m->is_dll)
        xrt_default_stack_reserve = *(uint32_t*)(file + opt + 72);
    m->export_dir = *(uint32_t*)(file + opt + 96);
    m->export_dir_size = *(uint32_t*)(file + opt + 100);
    hdrsize = *(uint32_t*)(file + opt + 60);
    /* map at the preferred base: the lifted code contains absolute addresses for exactly this base */
    xrt_commit(m->base, m->size);
    memcpy(G2H(m->base), file, hdrsize);
    for (i = 0; i < nsec; i++) {
        uint8_t* s = file + opt + *(uint16_t*)(file + pe + 20) + 40 * i;
        uint32_t vsize = *(uint32_t*)(s + 8), rva = *(uint32_t*)(s + 12), raw = *(uint32_t*)(s + 16),
                 ptr = *(uint32_t*)(s + 20);
        uint32_t n = raw < vsize || !vsize ? raw : vsize;
        if (n && (uint64_t)ptr + n <= (uint64_t)len)
            memcpy(G2H(m->base + rva), file + ptr, n);
    }
    free(file);
    nmods++;
    /* export names (diagnostics) */
    if (m->export_dir) {
        uint32_t ed = m->base + m->export_dir, nnames = rd32(ed + 24), funcs = m->base + rd32(ed + 28),
                 names = m->base + rd32(ed + 32), ords = m->base + rd32(ed + 36);
        exnames = (ExportName*)realloc(exnames, (nexnames + nnames) * sizeof *exnames);
        for (i = 0; i < nnames; i++) {
            exnames[nexnames].va = m->base + rd32(funcs + 4 * rd16(ords + 2 * i));
            exnames[nexnames].name = (const char*)G2H(m->base + rd32(names + 4 * i));
            nexnames++;
        }
        qsort(exnames, nexnames, sizeof *exnames, cmp_exname);
    }
    xrt_log("mapped %s at %08x size %x entry %08x sha256 %s (%u lifted functions, %u static traps)", m->name, m->base,
            m->size, m->entry, digest, lifted->nfuncs, lifted->ntraps);
    return m;
}

const char* xrt_export_name_at(uint32_t va) {
    int lo = 0, hi = nexnames - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (exnames[mid].va == va)
            return exnames[mid].name;
        if (exnames[mid].va < va)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return NULL;
}

uint32_t xrt_module_export(XrtModule* m, const char* name, uint32_t ordinal) {
    uint32_t ed, nnames, funcs, names, ords, nfuncs, base_ord, rva = 0, i;
    if (!m->export_dir)
        return 0;
    ed = m->base + m->export_dir;
    base_ord = rd32(ed + 16);
    nfuncs = rd32(ed + 20);
    nnames = rd32(ed + 24);
    funcs = m->base + rd32(ed + 28);
    names = m->base + rd32(ed + 32);
    ords = m->base + rd32(ed + 36);
    if (name) {
        int lo = 0, hi = (int)nnames - 1;    /* export names are sorted (binary search, as the loader does) */
        while (lo <= hi) {
            int mid = (lo + hi) / 2, r = strcmp((const char*)G2H(m->base + rd32(names + 4 * mid)), name);
            if (!r) {
                rva = rd32(funcs + 4 * rd16(ords + 2 * mid));
                break;
            }
            if (r < 0)
                lo = mid + 1;
            else
                hi = mid - 1;
        }
    } else {
        i = ordinal - base_ord;
        if (i < nfuncs)
            rva = rd32(funcs + 4 * i);
    }
    if (!rva)
        return 0;
    if (rva >= m->export_dir && rva < m->export_dir + m->export_dir_size)
        xrt_fatal(NULL, XRT_EXIT_IMPORT, "%s: forwarded export %s is not supported", m->name, name ? name : "(ordinal)");
    return m->base + rva;
}

/* ---------------------------------------------------------------- import binding */
static const XrtHle* hle_find(const char* dll, const char* name) {
    const XrtHle* tabs[3] = {xrt_hle_kernel32, xrt_hle_msvcr70, xrt_hle_misc};
    int t;
    for (t = 0; t < 3; t++) {
        const XrtHle* h;
        for (h = tabs[t]; h->dll; h++)
            if (!_stricmp(h->dll, dll) && !strcmp(h->name, name))
                return h;
    }
    return NULL;
}

static uint32_t stub_for(const char* key, XrtFn fn) {
    int i;
    for (i = 0; i < nstubs; i++)
        if (!strcmp(stubs[i].name, key))
            return XRT_STUB_BASE + XRT_STUB_SIZE * (uint32_t)i;
    if (nstubs == (int)(sizeof stubs / sizeof stubs[0]))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "out of import stubs");
    snprintf(stubs[nstubs].name, sizeof stubs[nstubs].name, "%s", key);
    stubs[nstubs].fn = fn;
    return XRT_STUB_BASE + XRT_STUB_SIZE * (uint32_t)nstubs++;
}

uint32_t xrt_hle_data(const char* dll, const char* name) {
    char key[96];
    const XrtHle* h;
    int i;
    snprintf(key, sizeof key, "%s!%s", dll, name);
    for (i = 0; i < ndata; i++)
        if (!_stricmp(dataobjs[i].key, key))
            return dataobjs[i].va;
    h = hle_find(dll, name);
    if (!h || h->fn || ndata == (int)(sizeof dataobjs / sizeof dataobjs[0]))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "no data object %s", key);
    snprintf(dataobjs[ndata].key, sizeof dataobjs[ndata].key, "%s", key);
    dataobjs[ndata].va = xrt_rt_alloc(h->data_size, 16);
    return dataobjs[ndata++].va;
}

void xrt_module_bind_imports(XrtModule* m) {
    uint8_t* hdr = (uint8_t*)G2H(m->base);
    uint32_t pe = *(uint32_t*)(hdr + 0x3C), opt = pe + 24, dir = *(uint32_t*)(hdr + opt + 104), d;
    int nmod = 0, nhle = 0, ndat = 0, nunb = 0;
    if (!dir)
        return;
    for (d = m->base + dir; rd32(d + 12); d += 20) {
        const char* dll = (const char*)G2H(m->base + rd32(d + 12));
        uint32_t lookup = rd32(d) ? m->base + rd32(d) : m->base + rd32(d + 16), iat = m->base + rd32(d + 16), k;
        XrtModule* target = xrt_module_by_name(dll);
        char dll_lc[64];
        size_t j;
        snprintf(dll_lc, sizeof dll_lc, "%s", dll);
        for (j = 0; dll_lc[j]; j++)
            dll_lc[j] = (char)tolower((unsigned char)dll_lc[j]);
        for (k = 0; rd32(lookup + 4 * k); k++) {
            uint32_t th = rd32(lookup + 4 * k), value;
            char name[512], key[600];
            if (th & 0x80000000u)
                snprintf(name, sizeof name, "#%u", th & 0xFFFF);
            else
                snprintf(name, sizeof name, "%s", (const char*)G2H(m->base + th + 2));
            snprintf(key, sizeof key, "%s!%s", dll_lc, name);
            if (target) {
                value = xrt_module_export(target, (th & 0x80000000u) ? NULL : name, th & 0xFFFF);
                if (!value)
                    xrt_fatal(NULL, XRT_EXIT_IMPORT, "%s imports %s, which %s does not export", m->name, key, target->name);
                nmod++;
            } else {
                const XrtHle* h = hle_find(dll_lc, name);
                if (h && h->fn) {
                    value = stub_for(key, h->fn);
                    nhle++;
                } else if (h) {
                    value = xrt_hle_data(dll_lc, name);
                    ndat++;
                } else {
                    value = stub_for(key, NULL);
                    nunb++;
                }
            }
            wr32(iat + 4 * k, value);
        }
    }
    xrt_log("bound imports of %s: %d to translated modules, %d to host adapters, %d data objects, %d unbound (fatal if called)",
            m->name, nmod, nhle, ndat, nunb);
}

const char* xrt_stub_name(uint32_t va) {
    uint32_t i;
    if (va - XRT_STUB_BASE >= XRT_STUB_END - XRT_STUB_BASE || (va & (XRT_STUB_SIZE - 1)))
        return NULL;
    i = (va - XRT_STUB_BASE) / XRT_STUB_SIZE;
    return (int)i < nstubs ? stubs[i].name : NULL;
}

/* ---------------------------------------------------------------- dispatch */
static int nsite_names;
static void site_count(int stub, uint32_t ret);

/* --watch: value changes of guest dwords, observed at import calls (evidence timelines) */
static uint32_t watch_addr[8], watch_last[8];
static int nwatch;
void xrt_watch_add(uint32_t a) {
    if (nwatch < 8) {
        watch_addr[nwatch] = a;
        watch_last[nwatch] = 0xDEADBEEFu;
        nwatch++;
    }
}
static void watch_check(CPU* c, int stub, uint32_t site) {
    int k;
    for (k = 0; k < nwatch; k++) {
        uint32_t v;
        if (!xrt_is_committed(watch_addr[k], 4))
            continue;
        v = rd32(watch_addr[k]);
        if (v != watch_last[k]) {
            char d[512];
            xrt_describe(d, sizeof d, site);
            xrt_log("watch %08x: %d -> %d, first observed by thread %d at its call to %s from %s", watch_addr[k],
                    (int)watch_last[k], (int)v, c->thread->index, stubs[stub].name, d);
            watch_last[k] = v;
        }
    }
}
static XrtFn lookup_lifted(uint32_t va) {
    XrtModule* m = xrt_module_by_addr(va);
    const XrtFuncEntry* f;
    int lo, hi;
    if (!m)
        return NULL;
    f = m->lifted->funcs;
    lo = 0;
    hi = (int)m->lifted->nfuncs - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (f[mid].va == va)
            return f[mid].fn;
        if (f[mid].va < va)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return NULL;
}

uint32_t xrt_lookup_containing(uint32_t va) {
    XrtModule* m = xrt_module_by_addr(va);
    const XrtFuncEntry* f;
    int lo, hi, best = -1;
    if (!m)
        return 0;
    f = m->lifted->funcs;
    lo = 0;
    hi = (int)m->lifted->nfuncs - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (f[mid].va <= va) {
            best = mid;
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return best >= 0 ? f[best].va : 0;
}

XrtFn xrt_lookup(uint32_t va, const char** stub_name) {
    if (stub_name)
        *stub_name = NULL;
    if (va - XRT_STUB_BASE < XRT_STUB_END - XRT_STUB_BASE) {
        uint32_t i = (va - XRT_STUB_BASE) / XRT_STUB_SIZE;
        if ((va & (XRT_STUB_SIZE - 1)) || (int)i >= nstubs)
            return NULL;
        if (stub_name)
            *stub_name = stubs[i].name;
        return stubs[i].fn;
    }
    return lookup_lifted(va);
}

static void dispatch(CPU* c, uint32_t target, uint32_t site, const char* what) {
    XrtFn fn;
    if (target - XRT_STUB_BASE < XRT_STUB_END - XRT_STUB_BASE) {
        uint32_t i = (target - XRT_STUB_BASE) / XRT_STUB_SIZE;
        XrtModule* caller = xrt_module_by_addr(site);
        if (!(target & (XRT_STUB_SIZE - 1)) && (int)i < nstubs) {
            stubs[i].calls[caller ? caller - mods : MAX_MODULES]++;
            if (nsite_names)
                site_count((int)i, rd32(c->r[ESP]));
            if (nwatch)
                watch_check(c, (int)i, site);
            xrt_watches_check(c, stubs[i].name, site);
            if (xrt_preempt_req)          /* import calls are preemption points too (e.g. spin loops on timeGetTime) */
                xrt_preempt(c);
            if (!stubs[i].fn) {
                char d[512];
                xrt_describe(d, sizeof d, site);
                xrt_fatal(c, XRT_EXIT_IMPORT, "call to import %s, which has no host implementation (from %s)", stubs[i].name, d);
            }
            stubs[i].fn(c);
            return;
        }
    }
    fn = lookup_lifted(target);
    if (!fn) {
        char d[512], t[512];
        xrt_describe(d, sizeof d, site);
        xrt_describe(t, sizeof t, target);
        xrt_fatal(c, XRT_EXIT_TRAP, "%s at %s to %s, which is not a translated function entry or import", what, d, t);
    }
    fn(c);
}

void xrt_icall(CPU* c, uint32_t target, uint32_t site) { dispatch(c, target, site, "indirect call"); }
void xrt_ijmp(CPU* c, uint32_t target, uint32_t site) { dispatch(c, target, site, "indirect jump"); }

uint32_t xrt_call_guest(CPU* c, uint32_t va, int nargs, const uint32_t* args, int stdcall) {
    uint32_t esp0 = c->r[ESP];
    int i;
    for (i = nargs - 1; i >= 0; i--)
        push32(c, args[i]);
    push32(c, XRT_HOST_RETURN);
    dispatch(c, va, XRT_HOST_RETURN, "host-to-guest call");
    if (c->rv != XRT_HOST_RETURN)
        xrt_badret(c, va, XRT_HOST_RETURN);
    if (!stdcall)
        c->r[ESP] += 4u * (uint32_t)nargs;
    if (c->r[ESP] != esp0) {
        char d[512];
        xrt_describe(d, sizeof d, va);
        xrt_fatal(c, XRT_EXIT_BADRET, "stack imbalance after calling guest %s (%s): esp %08x, expected %08x", d,
                  stdcall ? "stdcall" : "cdecl", c->r[ESP], esp0);
    }
    return c->r[EAX];
}

void xrt_imports_report(FILE* f) {
    int i, j, first = 1;
    fputs("{", f);
    for (i = 0; i < nstubs; i++) {
        uint64_t total = 0;
        for (j = 0; j <= MAX_MODULES; j++)
            total += stubs[i].calls[j];
        if (!total)
            continue;
        fprintf(f, "%s\n  \"%s\": {\"calls\": %llu, \"by_module\": {", first ? "" : ",", stubs[i].name, total);
        first = 0;
        {
            int f2 = 1;
            for (j = 0; j < nmods; j++)
                if (stubs[i].calls[j]) {
                    fprintf(f, "%s\"%s\": %llu", f2 ? "" : ", ", mods[j].name, stubs[i].calls[j]);
                    f2 = 0;
                }
        }
        fputs("}}", f);
    }
    fputs("\n }", f);
}

/* ---------------------------------------------------------------- call-site histograms (--count-sites)
 * For selected imports, count calls per return address (the guest return address on the stack when the
 * stub is entered, which for thunk tail-jumps is the original caller - the same convention as uctrace). */
static char site_names[8][64];
typedef struct Site { int stub; uint32_t ret, ret2; uint64_t count; } Site;
static int site_extra_off = -1;   /* XRT_SITE_EXTRA=<byte offset>: also key by the dword at [esp+offset] */
static Site* sites;
static int nsites, cap_sites;

void xrt_sites_enable(const char* names) {
    if (getenv("XRT_SITE_EXTRA"))
        site_extra_off = atoi(getenv("XRT_SITE_EXTRA"));
    while (names && *names && nsite_names < 8) {
        const char* comma = strchr(names, ',');
        size_t n = comma ? (size_t)(comma - names) : strlen(names);
        if (n > 63)
            n = 63;
        memcpy(site_names[nsite_names], names, n);
        site_names[nsite_names][n] = 0;
        nsite_names++;
        names = comma ? comma + 1 : NULL;
    }
}

static void site_count(int stub, uint32_t ret) {
    int i, k;
    for (k = 0; k < nsite_names; k++)
        if (strstr(stubs[stub].name, site_names[k]))
            break;
    if (k == nsite_names)
        return;
    uint32_t ret2 = site_extra_off >= 0 ? rd32(xrt_cur->cpu.r[ESP] + (uint32_t)site_extra_off) : 0;
    for (i = 0; i < nsites; i++)
        if (sites[i].stub == stub && sites[i].ret == ret && sites[i].ret2 == ret2) {
            sites[i].count++;
            return;
        }
    if (nsites == cap_sites) {
        cap_sites = cap_sites ? 2 * cap_sites : 256;
        sites = (Site*)realloc(sites, cap_sites * sizeof *sites);
    }
    sites[nsites].stub = stub;
    sites[nsites].ret = ret;
    sites[nsites].ret2 = ret2;
    sites[nsites].count = 1;
    nsites++;
}

void xrt_sites_report(FILE* f) {
    int i;
    fputs("[", f);
    for (i = 0; i < nsites; i++)
        fprintf(f, "%s\n  {\"import\": \"%s\", \"return_address\": \"0x%08x\", \"extra\": \"0x%08x\", \"count\": %llu}",
                i ? "," : "", stubs[sites[i].stub].name, sites[i].ret, sites[i].ret2, sites[i].count);
    fputs("\n ]", f);
}

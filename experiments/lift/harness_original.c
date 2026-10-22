/* Calls the ORIGINAL Unreal II Core.dll (32-bit) and prints results for the
 * lifting experiment. Build as x86 with MSVC. Usage: harness_original <System dir> */
#include <stdio.h>
#include <windows.h>

#include "testvec.h"

typedef unsigned long(__cdecl* MemCrcFn)(const void*, int, unsigned long);
typedef unsigned long(__cdecl* StrCrcCapsFn)(const unsigned short*);
typedef void(__cdecl* MD5TransformFn)(unsigned long*, unsigned char*);
typedef float(__cdecl* Float3Fn)(float, float, float);
typedef int(__cdecl* IntOfFloatFn)(float);
typedef void(__cdecl* SRandInitFn)(int);
typedef float(__cdecl* SRandFn)(void);

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: harness_original <System dir>\n"); return 2; }
    SetDllDirectoryA(argv[1]);
    char path[MAX_PATH];
    snprintf(path, sizeof path, "%s\\Core.dll", argv[1]);
    HMODULE core = LoadLibraryA(path);
    if (!core) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 1; }
    unsigned long* crcTable = (unsigned long*)GetProcAddress(core, "?GCRCTable@@3PAKA");
    MemCrcFn memCrc = (MemCrcFn)GetProcAddress(core, "?appMemCrc@@YAKPBXHK@Z");
    StrCrcCapsFn strCrcCaps = (StrCrcCapsFn)GetProcAddress(core, "?appStrCrcCaps@@YAKPBG@Z");
    MD5TransformFn md5 = (MD5TransformFn)GetProcAddress(core, "?appMD5Transform@@YAXPAKPAE@Z");
    Float3Fn blend = (Float3Fn)GetProcAddress(core, "?appBlend@@YAMMMM@Z");
    Float3Fn ablend = (Float3Fn)GetProcAddress(core, "?appAblend@@YAMMMM@Z");
    IntOfFloatFn roundF = (IntOfFloatFn)GetProcAddress(core, "?appRound@@YAHM@Z");
    IntOfFloatFn floorF = (IntOfFloatFn)GetProcAddress(core, "?appFloor@@YAHM@Z");
    IntOfFloatFn ceilF = (IntOfFloatFn)GetProcAddress(core, "?appCeil@@YAHM@Z");
    SRandInitFn srandInit = (SRandInitFn)GetProcAddress(core, "?appSRandInit@@YAXH@Z");
    SRandFn srand_ = (SRandFn)GetProcAddress(core, "?appSRand@@YAMXZ");
    if (!crcTable || !memCrc || !strCrcCaps || !md5 || !blend || !ablend || !roundF || !floorF || !ceilF || !srandInit || !srand_) {
        fprintf(stderr, "missing export\n");
        return 1;
    }
    fill_crc_table((uint32_t*)crcTable);
    unsigned char buf[512];
    unsigned short wbuf[64];
    for (int i = 0; i < N_CASES; i++) {
        int len = (int)(rng() % 300);
        for (int k = 0; k < len; k++) buf[k] = (unsigned char)rng();
        uint32_t seed = rng();
        printf("memcrc %d %08lx\n", i, memCrc(buf, len, seed));
        int wl = (int)(rng() % 40);
        for (int k = 0; k < wl; k++) wbuf[k] = (unsigned short)(0x20 + rng() % 0x60);
        wbuf[wl] = 0;
        printf("strcrccaps %d %08lx\n", i, strCrcCaps(wbuf));
        unsigned long st[4];
        unsigned char blk[64];
        for (int k = 0; k < 4; k++) st[k] = rng();
        for (int k = 0; k < 64; k++) blk[k] = (unsigned char)rng();
        md5(st, blk);
        printf("md5 %d %08lx%08lx%08lx%08lx\n", i, st[0], st[1], st[2], st[3]);
        float a = rngf(), b = rngf(), p = rngf();
        printf("blend %d %08x %08x\n", i, f2bits(blend(a, b, p)), f2bits(ablend(a, b, p)));
        float x = rngf();
        printf("round %d %08x %08x %08x\n", i, (uint32_t)roundF(x), (uint32_t)floorF(x), (uint32_t)ceilF(x));
    }
    srandInit(12345);
    for (int i = 0; i < 2000; i++) printf("srand %d %08x\n", i, f2bits(srand_()));
    return 0;
}

/* xrt_msvcr70img.c - msvcr70.dll functions that run as translated code instead of host adapters.
 *
 * msvcr70's _CIpow takes its SSE2 path in the measured configuration (SSE2 present, every x87 and SSE exception
 * masked). That path is translated from the DLL by tools/xrt/lift_sse2.py into gen/msvcr70/pow_sse2.c (git-ignored);
 * it reads its constant tables from the DLL's image, which is loaded here from the sandbox copy as data (SHA-256
 * checked against the file the code was translated from). Nothing of the DLL is executed. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdlib.h>
#include "xrt_internal.h"

extern const char xrt_msvcr70_pow_sse2_sha256[];
double xrt_msvcr70_pow_sse2(double x, double y, const uint8_t* img, uint32_t* error_type);

static uint8_t* image;

static const uint8_t* msvcr70_image(void) {
    char path[600], digest[65];
    FILE* f;
    uint8_t *file, h[32];
    long len;
    uint32_t pe, opt, nsec, size, hdr, i;
    if (image)
        return image;
    snprintf(path, sizeof path, "%s\\System\\msvcr70.dll", xrt_sandbox_root);
    if (!(f = fopen(path, "rb")))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "cannot open %s (translated _CIpow reads its tables from it)", path);
    fseek(f, 0, SEEK_END);
    len = ftell(f);
    fseek(f, 0, SEEK_SET);
    file = (uint8_t*)malloc((size_t)len);
    if (!file || fread(file, 1, (size_t)len, f) != (size_t)len)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "cannot read %s", path);
    fclose(f);
    if (BCryptHash(BCRYPT_SHA256_ALG_HANDLE, NULL, 0, file, (ULONG)len, h, 32) != 0)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "SHA-256 unavailable");
    for (i = 0; i < 32; i++)
        sprintf(digest + 2 * i, "%02x", h[i]);
    if (strcmp(digest, xrt_msvcr70_pow_sse2_sha256))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "%s has SHA-256 %s but _CIpow was translated from %s", path, digest,
                  xrt_msvcr70_pow_sse2_sha256);
    pe = *(uint32_t*)(file + 0x3C);
    nsec = *(uint16_t*)(file + pe + 6);
    opt = pe + 24;
    size = *(uint32_t*)(file + opt + 56);
    hdr = *(uint32_t*)(file + opt + 60);
    image = (uint8_t*)calloc(size, 1);
    if (!image)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "out of memory");
    memcpy(image, file, hdr);
    for (i = 0; i < nsec; i++) {
        uint8_t* s = file + opt + *(uint16_t*)(file + pe + 20) + 40 * i;
        uint32_t vsize = *(uint32_t*)(s + 8), rva = *(uint32_t*)(s + 12), raw = *(uint32_t*)(s + 16),
                 ptr = *(uint32_t*)(s + 20);
        uint32_t n = raw < vsize || !vsize ? raw : vsize;
        if (n && (uint64_t)ptr + n <= (uint64_t)len && (uint64_t)rva + n <= size)
            memcpy(image + rva, file + ptr, n);
    }
    free(file);
    xrt_log("msvcr70.dll image loaded as data for translated _CIpow (sha256 %s)", digest);
    return image;
}

/* The SSE2 core hands special results to the DLL's math error handler (not translated: it sets errno and calls
 * _matherr, whose default returns 0 and changes nothing). Its effect on the result, read from the DLL for the types
 * the pow core passes: 0x1a (pow(0, 0)) stores 1.0 and 0x1d (pow(NaN, 0)) stores x; 0x18 (overflow), 0x19
 * (underflow), 0x1b, 0x1c and 0x3ee keep the value the core computed. Any other type is not expected: fatal. */
double xrt_msvcr70_pow(CPU* c, double x, double y, uint32_t* error_type) {
    double r;
    if ((c->fcw & 0x7F) != 0x7F)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_CIpow with x87 control word %04x: msvcr70 would take its x87 path, which "
                  "is not translated", c->fcw);
    r = xrt_msvcr70_pow_sse2(x, y, msvcr70_image(), error_type);
    switch (*error_type) {
    case 0:
    case 0x18:
    case 0x19:
    case 0x1b:
    case 0x1c:
    case 0x3ee:
        return r;
    case 0x1a:
        return 1.0;
    case 0x1d:
        return x;
    default:
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "_CIpow: math error type %#x is not modelled", *error_type);
    }
}

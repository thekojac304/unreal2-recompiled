/* Owned test (round 3): the D3D8 buffer validity bitmap (runtime d8_valid_bits.h) gives the same answers as the former
 * byte-per-byte map (memset 1 per uploaded byte, memset 0 on DISCARD, memchr for a zero byte) under random Lock/Unlock/
 * DISCARD/draw-range sequences on buffers of odd and even sizes, and its range operations never touch bytes outside
 * the (length + 7) / 8 map (guard bytes around it must stay intact). Also times both forms on draw-sized ranges.
 *   run.cmd   (exit 0 = pass) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include "d8_valid_bits.h"

static unsigned long long rng = 88172645463325252ull;
static unsigned long long rnd(unsigned long long n) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return n ? rng % n : 0; }

int main(void) {
    static const unsigned sizes[] = {1, 7, 8, 9, 63, 64, 65, 1000, 4096, 65537, 1u << 20};
    unsigned long long checks = 0, ops = 0;
    unsigned si, iter;
    for (si = 0; si < sizeof sizes / sizeof sizes[0]; si++) {
        unsigned len = sizes[si];
        unsigned char *bytes = calloc(len, 1), *raw = malloc(d8_valid_bytes(len) + 32), *bits = raw + 16;
        memset(raw, 0xA5, d8_valid_bytes(len) + 32);
        memset(bits, 0, d8_valid_bytes(len));
        for (iter = 0; iter < 20000; iter++) {
            unsigned at = (unsigned)rnd(len), n = (unsigned)rnd(len - at + 1), op = (unsigned)rnd(10);
            if (op < 4) { memset(bytes + at, 1, n); d8_valid_set(bits, at, n); ops++; }
            else if (op == 4) { memset(bytes, 0, len); memset(bits, 0, d8_valid_bytes(len)); ops++; }
            else {
                int want = !n || !memchr(bytes + at, 0, n), got = d8_valid_all(bits, at, n);
                if (want != got) { printf("FAIL len %u at %u n %u: byte map %d bitmap %d\n", len, at, n, want, got); return 1; }
                checks++;
            }
            if (memcmp(raw, "\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5", 16) ||
                memcmp(bits + d8_valid_bytes(len), "\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5\xA5", 16)) {
                printf("FAIL len %u: guard bytes changed\n", len); return 1;
            }
        }
        {   /* every bit position: the map equals the byte map bit for bit */
            unsigned i;
            for (i = 0; i < len; i++) if (((bits[i >> 3] >> (i & 7)) & 1) != bytes[i]) { printf("FAIL len %u bit %u\n", len, i); return 1; }
        }
        free(bytes); free(raw);
    }
    {   /* timing: 64 KB draw-range checks on a fully valid 1 MB buffer */
        unsigned len = 1u << 20, i; volatile int sink = 0; LARGE_INTEGER f, t0, t1;
        unsigned char *bytes = malloc(len), *bits = malloc(d8_valid_bytes(len));
        memset(bytes, 1, len); memset(bits, 0xFF, d8_valid_bytes(len));
        QueryPerformanceFrequency(&f);
        QueryPerformanceCounter(&t0);
        for (i = 0; i < 20000; i++) sink += memchr(bytes + (i * 4096u) % (len - 65536), 0, 65536) == NULL;
        QueryPerformanceCounter(&t1);
        printf("byte map: %.1f ns per 64 KB range check\n", (double)(t1.QuadPart - t0.QuadPart) * 1e9 / f.QuadPart / 20000);
        QueryPerformanceCounter(&t0);
        for (i = 0; i < 20000; i++) sink += d8_valid_all(bits, (i * 4096u) % (len - 65536), 65536);
        QueryPerformanceCounter(&t1);
        printf("bitmap:   %.1f ns per 64 KB range check\n", (double)(t1.QuadPart - t0.QuadPart) * 1e9 / f.QuadPart / 20000);
        free(bytes); free(bits);
    }
    printf("PASS: %llu range checks, %llu set/clear operations, guard bytes intact\n", checks, ops);
    return 0;
}

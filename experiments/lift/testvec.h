/* Shared deterministic test-vector generation for the lifting experiment.
 * Both harnesses (original Core.dll on x86, lifted C on x64/ARM64) include this,
 * so they see identical inputs. Results are printed as hex bit patterns. */
#ifndef TESTVEC_H
#define TESTVEC_H
#include <stdint.h>
#include <string.h>

static uint32_t g_rng = 0x12345678u;
static uint32_t rng(void) {
    uint32_t x = g_rng;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return g_rng = x;
}
static float bits2f(uint32_t u) { float f; memcpy(&f, &u, 4); return f; }
static uint32_t f2bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

/* Floats: mix of "ordinary" values, halves (rounding edge cases) and raw bit patterns. */
static float rngf(void) {
    uint32_t k = rng() % 8;
    if (k < 3) return (float)((int32_t)(rng() % 2000001) - 1000000) / 1000.0f;
    if (k < 5) return (float)((int32_t)(rng() % 201) - 100) + 0.5f;
    if (k < 7) return (float)((int32_t)rng()) / 65536.0f;
    { uint32_t u = rng(); uint32_t e = (u >> 23) & 0xFF; if (e == 0xFF || e < 0x40 || e > 0xBE) u ^= 0x40000000u; return bits2f(u); }
}

static void fill_crc_table(uint32_t* t) {  /* Unreal CRC32 table, MSB-first, poly 0x04C11DB7 */
    uint32_t i, j, c;
    for (i = 0; i < 256; i++) {
        for (c = i << 24, j = 8; j != 0; j--) c = (c & 0x80000000u) ? (c << 1) ^ 0x04C11DB7u : (c << 1);
        t[i] = c;
    }
}

#define N_CASES 20000
#endif

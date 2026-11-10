/* D3D8 buffer upload validity, one bit per buffer byte (bit at&7 of byte at>>3): set by Unlock for the uploaded
 * range, cleared for the whole buffer by a DISCARD Lock, required for every byte a draw reads. Same answers as the
 * former byte-per-byte map (memchr for a zero byte / memset to 1) with an eighth of the memory traffic.
 * The map is (length + 7) / 8 bytes; callers keep at + n <= length. */
#ifndef D8_VALID_BITS_H
#define D8_VALID_BITS_H
#include <stdint.h>
#include <string.h>
static size_t d8_valid_bytes(uint64_t length) { return (size_t)((length + 7) >> 3); }
static int d8_valid_all(const unsigned char *m, uint64_t at, uint64_t n) {
    const unsigned char *p;
    uint64_t k, w;
    while (n && (at & 7)) { if (!((m[at >> 3] >> (at & 7)) & 1)) return 0; at++; n--; }
    p = m + (at >> 3);
    for (k = n >> 3; k >= 8; k -= 8, p += 8) { memcpy(&w, p, 8); if (w != ~0ull) return 0; }
    for (; k; k--, p++) if (*p != 0xFF) return 0;
    at += n & ~(uint64_t)7; n &= 7;
    while (n) { if (!((m[at >> 3] >> (at & 7)) & 1)) return 0; at++; n--; }
    return 1;
}
static void d8_valid_set(unsigned char *m, uint64_t at, uint64_t n) {
    while (n && (at & 7)) { m[at >> 3] |= (unsigned char)(1u << (at & 7)); at++; n--; }
    if (n >> 3) { memset(m + (at >> 3), 0xFF, (size_t)(n >> 3)); at += n & ~(uint64_t)7; n &= 7; }
    while (n) { m[at >> 3] |= (unsigned char)(1u << (at & 7)); at++; n--; }
}
#endif

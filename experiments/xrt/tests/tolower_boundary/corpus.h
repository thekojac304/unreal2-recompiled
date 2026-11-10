/* Deterministic full-width int partitions, exhaustive bytes/EOF, and random bits. */
static uint32_t sample(unsigned i) {
    if (i < 131072) return i - 65536u;
    if (i < 393216) {
        static const unsigned low[] = {0x41, 0xc0, 0xffff, 0x824f};
        unsigned j = i - 131072;
        return ((j / 4) << 16) | low[j % 4];
    }
    if (i == 393216) return 0x80000000u;
    if (i == 393217) return 0x7fffffffu;
    { uint32_t x = i * 747796405u + 2891336453u; x ^= x >> 16; x *= 2246822519u; return x ^ (x >> 13); }
}
#define CASES 397314u

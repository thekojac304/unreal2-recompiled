/* Developer cost counters (dev_support.c defines them and writes counters.csv at every scripted "cpu"/"shot" step).
 * Counts are plain increments on the paths that own them. The tsc_* times (rdtsc ticks; counters.csv carries the
 * ticks-per-ms calibration) are taken only when xrt_perf_timing is set, i.e. in sampled runs (XRT_DEV_SAMPLE_HZ > 0),
 * so benchmark runs pay one predictable branch per site and no timestamp reads. */
#ifndef XRT_PERF_COUNTERS_H
#define XRT_PERF_COUNTERS_H
#include <intrin.h>
#define XRT_PERF_FIELDS(X) \
    X(d3d_calls) X(draw_calls) X(present) \
    X(buf_lock) X(buf_lock_bytes) X(buf_lock_discard) X(buf_lock_nooverwrite) X(buf_lock_undefined) \
    X(buf_valid_scan_bytes) X(buf_valid_clear_bytes) X(buf_unlock) X(buf_unlock_bytes) \
    X(tex_lock) X(tex_lock_bytes) X(tex_unlock) X(tex_unlock_bytes) \
    X(staging_alloc) X(staging_alloc_bytes) X(staging_free) X(draw_copy_bytes) \
    X(tsc_d3d) X(tsc_native) X(tsc_present) X(tsc_buf_lock) X(tsc_buf_unlock) X(tsc_tex_lock) X(tsc_tex_unlock) \
    X(tsc_staging_alloc) X(tsc_staging_free)
#define XRT_PERF_FIELD(name) unsigned long long name;
typedef struct XrtPerfCounters { XRT_PERF_FIELDS(XRT_PERF_FIELD) } XrtPerfCounters;
#undef XRT_PERF_FIELD
extern XrtPerfCounters xrt_perf;
extern int xrt_perf_timing;
#define XRT_PERF_T0() (xrt_perf_timing ? __rdtsc() : 0ull)
#define XRT_PERF_ADD(field, t0) do { if (xrt_perf_timing) xrt_perf.field += __rdtsc() - (t0); } while (0)
#endif

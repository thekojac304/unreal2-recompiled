/* Development-only trace compaction for the verified Core CPU calibration loop.
 * Every import still executes, with the normal checks and preemption points.
 * Keep one complete BEGIN/END pair per batch of at most 256 calls and summarize
 * ALL results. Other sites and the forensic profile retain full tracing.
 * This is diagnostic sampling, never qualification evidence.
 */
static __declspec(thread) struct {
    unsigned count, first, last, advances, backwards, pass, baseline;
    LARGE_INTEGER start;
} dev_calibration;

static int dev_calibration_match(uint32_t site, const char *name) {
    return xm_enabled() && xm_profile == 1 && site == 0x1015bd39u &&
        !strcmp(name, "winmm.dll!timeGetTime");
}

static void dev_calibration_flush(CPU *c) {
    DWORD saved = GetLastError();
    LARGE_INTEGER end, frequency;
    XmValue v[12];
    if (!dev_calibration.count) return;
    QueryPerformanceCounter(&end);
    QueryPerformanceFrequency(&frequency);
    /* Ordered fields: site, calls, first/last timer, advances/backwards,
     * zero-based pass, guest baseline, guest elapsed, host QPC start/end/hz.
     * UINT_MAX pass/baseline means the diagnostic local range was unavailable.
     */
    v[0]=(XmValue){XM_U32,4,0x1015bd39u};
    v[1]=(XmValue){XM_U32,4,dev_calibration.count};
    v[2]=(XmValue){XM_U32,4,dev_calibration.first};
    v[3]=(XmValue){XM_U32,4,dev_calibration.last};
    v[4]=(XmValue){XM_U32,4,dev_calibration.advances};
    v[5]=(XmValue){XM_U32,4,dev_calibration.backwards};
    v[6]=(XmValue){XM_U32,4,dev_calibration.pass};
    v[7]=(XmValue){XM_U32,4,dev_calibration.baseline};
    v[8]=(XmValue){XM_U32,4,(uint32_t)(dev_calibration.last-dev_calibration.baseline)};
    v[9]=(XmValue){XM_U32,8,(uint64_t)dev_calibration.start.QuadPart};
    v[10]=(XmValue){XM_U32,8,(uint64_t)end.QuadPart};
    v[11]=(XmValue){XM_U32,8,(uint64_t)frequency.QuadPart};
    xm_values(c,"dev.calibration.timeGetTime.batch",12,v);
    memset(&dev_calibration,0,sizeof dev_calibration);
    SetLastError(saved);
}

static int dev_calibration_begin(void) {
    DWORD saved = GetLastError();
    int sample = dev_calibration.count == 0;
    if (sample) QueryPerformanceCounter(&dev_calibration.start);
    SetLastError(saved);
    return sample;
}

static void dev_calibration_end(CPU *c) {
    DWORD saved = GetLastError();
    uint32_t value = c->r[EAX], frame = c->r[EBP];
    if (!dev_calibration.count) dev_calibration.first = value;
    else {
        dev_calibration.advances += value > dev_calibration.last;
        dev_calibration.backwards += value < dev_calibration.last;
    }
    dev_calibration.last = value;
    dev_calibration.pass = dev_calibration.baseline = UINT32_MAX;
    if (frame >= 0x6c && xrt_is_committed(frame-0x6c,0x20)) {
        dev_calibration.baseline = rd32(frame-0x6c);
        dev_calibration.pass = rd32(frame-0x50);
    }
    if (++dev_calibration.count == 256) dev_calibration_flush(c);
    SetLastError(saved);
}

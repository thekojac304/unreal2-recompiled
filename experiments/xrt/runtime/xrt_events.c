/* xrt_events.c - ordered evidence timeline for the runtime report.
 *
 * Every event receives a global sequence number in the order the runtime records it. Translated code runs only
 * while its thread holds the execution baton (xrt_thread.c), so for events recorded by guest threads the sequence
 * is the guest execution order. Kinds: process model (dll_attach, exe_entry, crt_exit, process_exit, dll_detach,
 * ...), threads (thread_create, thread_start, exit_thread, thread_end), files (file_open), evidence marks and
 * watches compiled into the translated code from tools/xrt/marks.json (mark, watch_initial, watch_store,
 * watch_unattributed), and failures (fatal, timeout).
 *
 * Marks keep their first XRT_MARK_KEEP occurrences in the timeline and count all of them. A watch records every
 * store the translated code makes to the watched global through a constant address; at every import call the
 * value is compared with the last recorded one, and a change no instrumented store explains is recorded as
 * watch_unattributed (e.g. a store through a computed pointer), so a missing store event cannot go unnoticed. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

#define MAX_EVENTS 8192
#define EVENT_LEN 448
#define XRT_MARK_KEEP 8
#define XRT_WATCH_KEEP 64

static char (*events)[EVENT_LEN];
static volatile LONG64 event_seq;
static volatile long watches_armed;

/* s is an ANSI (CP_ACP) string, as the guest and the host adapters use them; the JSON text stays pure ASCII:
 * every character outside printable ASCII becomes a \uXXXX escape of its UTF-16 value. Truncated to fit n. */
const char* xrt_jstr(char* out, size_t n, const char* s) {
    size_t k = 0, bytes = strlen(s) + 1;
    int i, len;
    WCHAR* w;
    if (n < 3 || !(w = (WCHAR*)malloc(bytes * sizeof(WCHAR))))
        return "\"\"";
    len = MultiByteToWideChar(CP_ACP, 0, s, -1, w, (int)bytes);
    if (len <= 0) {                       /* unconvertible: keep the bytes, as Latin-1 */
        for (len = 0; s[len]; len++)
            w[len] = (unsigned char)s[len];
        w[len++] = 0;
    }
    out[k++] = '"';
    for (i = 0; i < len - 1 && k + 8 < n; i++) {
        WCHAR ch = w[i];
        if (ch == '"' || ch == '\\') {
            out[k++] = '\\';
            out[k++] = (char)ch;
        } else if (ch < 0x20 || ch >= 0x7F) {
            k += (size_t)snprintf(out + k, n - k, "\\u%04x", (unsigned)ch);
        } else {
            out[k++] = (char)ch;
        }
    }
    out[k++] = '"';
    out[k] = 0;
    free(w);
    return out;
}

void xrt_events_init(void) {
    events = calloc(MAX_EVENTS, EVENT_LEN);
    if (!events) {
        fprintf(stderr, "xrt: cannot allocate the event timeline\n");
        exit(XRT_EXIT_SETUP);
    }
}

/* The event is formatted in a large buffer first; one that does not fit its slot is stored as a valid,
 * explicitly truncated record (its kind and order are kept, its details are not). */
void xrt_event(const char* kind, const char* fmt, ...) {
    LONG64 seq = InterlockedIncrement64(&event_seq);
    char buf[4096];
    int n, m = 0;
    va_list ap;
    int thread = xrt_cur ? xrt_cur->index : -1;
    if (!events || seq > MAX_EVENTS)
        return;                           /* counted (events_dropped in the report), not stored */
    n = snprintf(buf, sizeof buf, "{\"seq\": %lld, \"thread\": %d, \"kind\": \"%s\"", seq, thread, kind);
    if (fmt && *fmt && n > 0) {
        va_start(ap, fmt);
        m = vsnprintf(buf + n + 2, sizeof buf - (size_t)n - 4, fmt, ap);
        va_end(ap);
        if (m >= 0 && (size_t)(n + 2 + m) < sizeof buf - 2) {
            buf[n] = ',';
            buf[n + 1] = ' ';
            n += 2 + m;
        } else {
            m = -1;
        }
    }
    if (n > 0 && m >= 0 && n + 2 <= EVENT_LEN) {
        buf[n] = '}';
        buf[n + 1] = 0;
        memcpy(events[seq - 1], buf, (size_t)n + 2);
    } else {
        snprintf(events[seq - 1], EVENT_LEN, "{\"seq\": %lld, \"thread\": %d, \"kind\": \"%s\", \"truncated\": true}", seq,
                 thread, kind);
    }
}

/* Kept in the timeline: the first XRT_MARK_KEEP occurrences, and the first occurrence for each distinct value at
 * [esp] (at a function entry: each distinct caller), up to XRT_MARK_CALLERS of them. */
void xrt_mark(CPU* c, XrtMark* m) {
    long k = InterlockedIncrement(&m->count);
    char nm[160], mod[96];
    XrtModule* owner;
    uint32_t top = rd32(c->r[ESP]);
    int i, fresh = 0;
    for (i = 0; i < m->ncallers && m->callers[i] != top; i++) {}
    if (i == m->ncallers && m->ncallers < XRT_MARK_CALLERS) {
        m->callers[m->ncallers++] = top;
        fresh = 1;
    }
    if (k > XRT_MARK_KEEP && !fresh)
        return;
    owner = xrt_module_by_addr(m->va);
    xrt_jstr(nm, sizeof nm, m->name);
    xrt_jstr(mod, sizeof mod, owner ? owner->name : "?");
    if (m->capture >= 0)
        xrt_event("mark", "\"name\": %s, \"module\": %s, \"va\": \"0x%08x\", \"occurrence\": %ld, \"stack_top\": \"0x%08x\", "
                          "\"captured\": %u", nm, mod, m->va, k, rd32(c->r[ESP]), c->r[m->capture]);
    else
        xrt_event("mark", "\"name\": %s, \"module\": %s, \"va\": \"0x%08x\", \"occurrence\": %ld, \"stack_top\": \"0x%08x\"",
                  nm, mod, m->va, k, rd32(c->r[ESP]));
}

static uint32_t watch_read(const XrtWatchDef* w) {
    return w->size == 1 ? rd8(w->addr) : w->size == 2 ? rd16(w->addr) : rd32(w->addr);
}

void xrt_watch_store(CPU* c, XrtWatchDef* w, uint32_t site) {
    uint32_t v = watch_read(w);
    char nm[160], where[600], d[512];
    (void)c;
    if (!w->armed)
        xrt_fatal(c, XRT_EXIT_SETUP, "watched global %s stored before the watches were armed", w->name);
    w->stores++;
    if (w->stores <= XRT_WATCH_KEEP) {
        xrt_describe(d, sizeof d, site);
        xrt_event("watch_store", "\"name\": %s, \"addr\": \"0x%08x\", \"old\": %d, \"new\": %d, \"site\": \"0x%08x\", \"where\": %s",
                  xrt_jstr(nm, sizeof nm, w->name), w->addr, (int32_t)w->last, (int32_t)v, site, xrt_jstr(where, sizeof where, d));
    }
    w->last = v;
}

void xrt_watches_arm_module(XrtModule* m) {
    uint32_t k;
    char nm[160];
    for (k = 0; k < m->lifted->nwatches; k++) {
        XrtWatchDef* w = &m->lifted->watches[k];
        w->last = watch_read(w);
        w->armed = 1;
        xrt_event("watch_initial", "\"name\": %s, \"addr\": \"0x%08x\", \"value\": %d", xrt_jstr(nm, sizeof nm, w->name),
                  w->addr, (int32_t)w->last);
    }
}

void xrt_watches_arm(void) {
    int i;
    for (i = 0; i < xrt_module_count(); i++)
        xrt_watches_arm_module(xrt_module_get(i));
    InterlockedExchange(&watches_armed, 1);
}

static uint64_t unattributed;
void xrt_watches_check(CPU* c, const char* import, uint32_t site) {
    int i;
    uint32_t k;
    if (!watches_armed)
        return;
    for (i = 0; i < xrt_module_count(); i++) {
        XrtModule* m = xrt_module_get(i);
        for (k = 0; k < m->lifted->nwatches; k++) {
            XrtWatchDef* w = &m->lifted->watches[k];
            uint32_t v;
            if (!w->armed)
                continue;
            v = watch_read(w);
            if (v != w->last) {
                char nm[160], d[512], where[600], imp[300];
                xrt_describe(d, sizeof d, site);
                unattributed++;
                xrt_event("watch_unattributed", "\"name\": %s, \"addr\": \"0x%08x\", \"expected\": %d, \"observed\": %d, "
                          "\"observed_at_import\": %s, \"from\": %s", xrt_jstr(nm, sizeof nm, w->name), w->addr,
                          (int32_t)w->last, (int32_t)v, xrt_jstr(imp, sizeof imp, import), xrt_jstr(where, sizeof where, d));
                w->last = v;
            }
        }
    }
    (void)c;
}

void xrt_events_report(FILE* f) {
    LONG64 n = event_seq, i, kept = n < MAX_EVENTS ? n : MAX_EVENTS;
    int m, first = 1;
    uint32_t k;
    char nm[160], mod[96];
    fputs(",\n \"marks\": [", f);
    for (m = 0; m < xrt_module_count(); m++) {
        XrtModule* mo = xrt_module_get(m);
        for (k = 0; k < mo->lifted->nmarks; k++) {
            XrtMark* mk = &mo->lifted->marks[k];
            fprintf(f, "%s\n  {\"module\": %s, \"va\": \"0x%08x\", \"name\": %s, \"count\": %ld, \"distinct_stack_tops\": %d%s}",
                    first ? "" : ",", xrt_jstr(mod, sizeof mod, mo->name), mk->va, xrt_jstr(nm, sizeof nm, mk->name), mk->count,
                    mk->ncallers, mk->ncallers == XRT_MARK_CALLERS ? ", \"distinct_stack_tops_capped\": true" : "");
            first = 0;
        }
    }
    fputs("\n ],\n \"watches\": [", f);
    first = 1;
    for (m = 0; m < xrt_module_count(); m++) {
        XrtModule* mo = xrt_module_get(m);
        for (k = 0; k < mo->lifted->nwatches; k++) {
            XrtWatchDef* w = &mo->lifted->watches[k];
            fprintf(f, "%s\n  {\"module\": %s, \"name\": %s, \"addr\": \"0x%08x\", \"armed\": %d, \"final\": %d, \"stores\": %llu}",
                    first ? "" : ",", xrt_jstr(mod, sizeof mod, mo->name), xrt_jstr(nm, sizeof nm, w->name), w->addr, w->armed,
                    w->armed ? (int32_t)watch_read(w) : 0, w->stores);
            first = 0;
        }
    }
    fprintf(f, "\n ],\n \"watch_unattributed_changes\": %llu,\n \"events_recorded\": %lld,\n \"events_dropped\": %lld,\n \"events\": [",
            unattributed, n, n - kept);
    for (i = 0; i < kept && events; i++)
        fprintf(f, "%s\n  %s", i ? "," : "", events[i][0] ? events[i] : "{\"kind\": \"incomplete\"}");
    fputs("\n ]", f);
}

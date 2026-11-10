/* Focused owned test for protocol v2 asynchronous tool callbacks (no game code).
 * Usage: async_test <dev dmusic_helper.exe> <sandbox root>
 * Drives the helper's --test DMB_TEST_ASYNC: a real native LYRIC PMSG (AllocPMsg) is
 * delivered to the inserted tool from a new native thread. This host answers like the
 * game's tool (ATTIME, LYRIC/SCRIPTLYRIC), stamps through the nested channel, retains
 * the message (S_OK), frees it with DMB_FREE_PMSG, then checks a stale handle is refused. */
#include <windows.h>
#include <stdio.h>
#include "../runtime/dmusic_pipe.h"
static DmbConnection conn;
static int no_reply;   /* "deadline" mode: never answer ProcessPMsg */
static uint32_t graph_id, seen_handle, seen_stamp, seen_type, async_calls, nested_calls;
static HRESULT stamp_hr = E_FAIL;
static wchar_t seen_text[8];
static int sync_cb(void *ctx, const DmbMessage *q, DmbMessage *r) {
    (void)ctx;
    memset(r->v, 0, sizeof r->v);
    switch (q->op) {
    case 0: r->v[0] = 0x80004002; break;            /* E_NOINTERFACE, as the game */
    case 1: case 2: r->v[0] = 1; break;
    case 3: r->v[0] = 0x80004001; break;            /* E_NOTIMPL */
    case 4: r->v[0] = 0; r->v[1] = 0x10; break;     /* DMUS_PMSGF_TOOL_ATTIME */
    case 5: r->v[0] = 0; r->v[1] = 2; break;
    case 6: r->v[0] = 0; r->v[1] = 13; r->v[2] = 14; break;
    default: return 0;
    }
    return 1;
}
static DWORD WINAPI async_thread(void *unused) {
    DmbMessage q = {0}, r, n, nr = {0};
    DWORD got, total;
    (void)unused;
    for (;;) {
        for (total = 0; total < sizeof q; total += got)
            if (!ReadFile(conn.async_input, (BYTE *)&q + total, sizeof q - total, &got, NULL) || !got) return 0;
        async_calls++;
        r = q; r.kind = DMB_ASYNC_REPLY; memset(r.v, 0, sizeof r.v);
        if (q.op == 7 && no_reply) continue;
        if (q.op == 7) {
            seen_handle = q.v[0];
            seen_type = *(uint32_t *)(q.data + DMB_PMSG_TYPE);
            memcpy(seen_text, q.data + DMB_PMSG_HEADER, 8);
            dmb_message(&n, DMB_STAMP_PMSG, q.v[1]);
            n.kind = DMB_ASYNC_NESTED; n.sequence = q.sequence; n.v[0] = q.v[0];
            if (!WriteFile(conn.async_output, &n, sizeof n, &got, NULL)) return 0;
            for (;;) {   /* StampPMsg re-targets pTool: Release/AddRef arrive first, recursively */
                for (total = 0; total < sizeof nr; total += got)
                    if (!ReadFile(conn.async_input, (BYTE *)&nr + total, sizeof nr - total, &got, NULL) || !got) return 0;
                if (nr.kind != DMB_ASYNC_CALLBACK) break;
                async_calls++; nested_calls++;
                { DmbMessage cr = nr; cr.kind = DMB_ASYNC_REPLY; memset(cr.v, 0, sizeof cr.v); cr.v[0] = 1;
                  if (!WriteFile(conn.async_output, &cr, sizeof cr, &got, NULL)) return 0; }
            }
            seen_stamp = nr.kind == DMB_ASYNC_NESTED_REPLY && nr.sequence == q.sequence;
            stamp_hr = (HRESULT)nr.v[0];
            r.v[0] = S_OK;                                       /* retain, like the game's queue */
        } else if (q.op == 1 || q.op == 2) {
            r.v[0] = 1;
        } else {
            r.v[0] = 0x80004001;
        }
        if (!WriteFile(conn.async_output, &r, sizeof r, &got, NULL)) return 0;
    }
}
#define STEP(label, cond) do { int ok_ = (cond); printf("%s %s\n", ok_ ? "PASS" : "FAIL", label); if (!ok_) return 1; } while (0)
int wmain(int argc, wchar_t **argv) {
    static const GUID toolgraph = {0x2befc277, 0x5497, 0x11d2, {0xbc, 0xcb, 0, 0xa0, 0xc9, 0x22, 0xe6, 0xeb}};
    DmbMessage m;
    uint32_t perf, path, handle;
    HANDLE th;
    if (argc != 3 && !(argc == 4 && !wcscmp(argv[3], L"deadline"))) return 2;
    no_reply = argc == 4;
    STEP("connect v2 helper", dmb_connect(&conn, argv[1], argv[2], 1, sync_cb, NULL));
    th = CreateThread(NULL, 0, async_thread, NULL, 0, NULL);
    dmb_message(&m, DMB_CREATE, 0); m.v[0] = DMB_PERFORMANCE;
    STEP("create performance", dmb_exchange(&conn, &m) && m.v[0] == 0); perf = m.v[1];
    dmb_message(&m, DMB_INIT_AUDIO, perf); m.v[0] = 8; m.v[1] = 128; m.v[2] = 0x3f;
    STEP("InitAudio", dmb_exchange(&conn, &m) && m.v[0] == 0);
    dmb_message(&m, DMB_PATH, perf);
    STEP("default audiopath", dmb_exchange(&conn, &m) && m.v[0] == 0); path = m.v[1];
    dmb_message(&m, DMB_GRAPH, path); m.v[1] = 0x3200; memcpy(m.guid[1], &toolgraph, 16);
    STEP("tool graph", dmb_exchange(&conn, &m) && m.v[0] == 0); graph_id = m.v[1];
    dmb_message(&m, DMB_INSERT, graph_id); m.v[0] = 1;
    STEP("insert tool", dmb_exchange(&conn, &m) && m.v[0] == 0);
    dmb_message(&m, DMB_TEST_ASYNC, perf); m.v[0] = graph_id;
    if (no_reply) {
        ULONGLONG start = GetTickCount64(); int ok = dmb_exchange(&conn, &m);
        printf("elapsed %llu ms: %s\n", GetTickCount64() - start, ok ? "unexpected reply" : conn.error);
        STEP("unanswered callback ends the helper within the deadline", !ok && GetTickCount64() - start < 12000);
        return 0;
    }
    STEP("async ProcessPMsg delivered and retained", dmb_exchange(&conn, &m) && m.v[1] == S_OK);
    handle = m.v[2];
    STEP("guest copy is LYRIC \"xrt\"", seen_type == 13 && !wcscmp(seen_text, L"xrt") && seen_handle == handle);
    STEP("nested StampPMsg on the DirectMusic thread", seen_stamp && SUCCEEDED(stamp_hr));
    dmb_message(&m, DMB_FREE_PMSG, perf); m.v[0] = handle;
    STEP("FreePMsg of retained message", dmb_exchange(&conn, &m) && m.v[0] == 0);
    dmb_message(&m, DMB_FREE_PMSG, perf); m.v[0] = handle;
    STEP("stale PMSG handle refused", !dmb_exchange(&conn, &m) && strstr(conn.error, "status 2"));
    printf("async callbacks observed: %u (nested inside StampPMsg: %u)\n", async_calls, nested_calls);
    (void)th;
    return 0;
}

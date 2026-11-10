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

#define MAX_EVENTS 262144 /* Retain the complete input/UI initialization after Golem startup. */
#define EVENT_LEN 448
#define XRT_MARK_KEEP 8
#define XRT_WATCH_KEEP 64

static char (*events)[EVENT_LEN];
static volatile LONG64 event_seq;
static volatile long watches_armed;
/* Optional owner-supervisor evidence sink. Synchronous fixed records survive
 * terminate-before-continue and watchdog cleanup; disabled for ordinary runs. */
static HANDLE event_stream=INVALID_HANDLE_VALUE;

typedef struct {
    const char* kind;
    const char* stage;
    uint32_t self,world,esp,ret,popped,arg0,arg1;
} WorldCall;
/* Developer movement diagnostic (dev.py build --diag-move + XRT_DEV_MOVE_DIAG=1): after ULevel::MoveActor returns for
 * the player's pawn with a blocking hit, log the moving actor, the hit actor and primitive (class and object names
 * read from the guest's FName table: UObject Name at +0x20, Class at +0x24, FName::Names data at 0x10275e18, entry
 * text at +0xc, as the translated UObject::GetName reads them) and FCheckResult Location/Normal/Time (Actor +4,
 * Location +8, Normal +0x14, Primitive +0x20, Time +0x24). Read-only; bounded. */
static int move_diag(void) { static int v=-1; if(v<0){const char*e=getenv("XRT_DEV_MOVE_DIAG");v=e&&*e=='1';} return v; }
static void guest_name(uint32_t obj,char*out,size_t n) {
    uint32_t idx,data,entry;size_t i;
    snprintf(out,n,"None");
    if(!obj||!xrt_is_committed(obj+0x20,8))return;
    idx=rd32(obj+0x20);
    if(!xrt_is_committed(0x10275e18u,4))return;
    data=rd32(0x10275e18u);
    if(idx>0x100000u||!xrt_is_committed(data+idx*4,4))return;
    entry=rd32(data+idx*4);
    if(!entry||!xrt_is_committed(entry+0xc,128))return;
    for(i=0;i+1<n&&i<63;i++){uint16_t ch=*(uint16_t*)G2H(entry+0xc+(uint32_t)i*2);if(!ch)break;out[i]=ch<128?(char)ch:'?';}
    out[i]=0;
}
static void guest_class_name(uint32_t obj,char*out,size_t n){snprintf(out,n,"None");if(obj&&xrt_is_committed(obj+0x24,4))guest_name(rd32(obj+0x24),out,n);}
static void move_diag_return(WorldCall*p) {
    static unsigned logged,repeats;static uint32_t last_hit;char mover[64],mcls[64],hit[64],hcls[64],prim[64];
    uint32_t h=p->arg1,actor=p->arg0,hit_actor,primitive;float loc[3],nrm[3],t;
    if(!h||!xrt_is_committed(h,0x28))return;
    memcpy(&t,G2H(h+0x24),4);hit_actor=rd32(h+4);primitive=rd32(h+0x20);
    if(!(t<1.0f)||!hit_actor)return;
    guest_class_name(actor,mcls,sizeof mcls);
    if(!strstr(mcls,"Player")&&!strstr(mcls,"player")) {
        static unsigned others;   /* the first hits of other classes, so the pawn's class is discoverable */
        if(others++>=40)return;
    }
    if(hit_actor==last_hit&&(++repeats%64))return;
    last_hit=hit_actor;if(logged++>=400)return;
    guest_name(actor,mover,sizeof mover);guest_name(hit_actor,hit,sizeof hit);guest_class_name(hit_actor,hcls,sizeof hcls);
    guest_class_name(primitive,prim,sizeof prim);memcpy(loc,G2H(h+8),12);memcpy(nrm,G2H(h+0x14),12);
    xrt_log("DEV move hit: %s (%s) blocked by %s (%s) primitive %s at %.0f,%.0f,%.0f normal %.2f,%.2f,%.2f time %.3f",
            mover,mcls,hit,hcls,prim,loc[0],loc[1],loc[2],nrm[0],nrm[1],nrm[2],t);
}
static __declspec(thread) WorldCall world_calls[128];
/* Pending entries on this thread: returns skip the 128-slot scan when none is pending,
 * and scan only below world_top (one past the highest occupied slot) otherwise. */
static __declspec(thread) unsigned world_pending,world_top;
/* Developer first-scene counters, read and reset by the D3D8 Present handler. */
int xrt_scene_level_depth,xrt_scene_camera_depth;unsigned xrt_scene_level_renders,xrt_scene_camera_renders,xrt_scene_engine_ticks,xrt_scene_level_ticks;

void xrt_world_enter(CPU*c,uint32_t target) {
    const char*kind=NULL,*stage="";uint32_t popped=4,self=c->r[ECX],world=0;unsigned i;
    /* Engine is lifted at 10300000, checked against its native image by the build. */
    switch(target-0x10300000u) {
    case 0x6630:kind="actor_lifecycle";stage="PreBeginPlay";break;
    case 0x66a0:kind="actor_lifecycle";stage="BeginPlay";break;
    case 0x6600:kind="actor_lifecycle";stage="PostBeginPlay";break;
    case 0x8f460:xm_scope(c,XM_BEGIN,XM_ADAPTER,"UGameEngine.Init",target);kind="engine_init";break;
    case 0x938f0:kind="engine_tick";popped=8;break; /* thiscall Tick(float), RET 4 */
    case 0xb5be0:kind="level_tick";world=self;popped=12;break;
    /* Developer first-scene evidence: Engine exports, thiscall. */
    case 0x8ed60:kind="game_draw";popped=20;break;      /* UGameEngine::Draw(UViewport*,int,BYTE*,int*), RET 10 */
    case 0xfc4b0:kind="level_render";popped=8;xrt_scene_level_depth++;break; /* FLevelSceneNode::Render(FRenderInterface*) */
    case 0xfcc80:kind="camera_render";popped=8;xrt_scene_camera_depth++;break; /* FCameraSceneNode::Render */
    case 0xfd280:kind="player_render";popped=8;break;   /* FPlayerSceneNode::Render */
    /* ULevel::MoveActor(AActor*,FVector,FRotator,FCheckResult&,int,int,int,int), thiscall, RET 30: diagnostic only. */
    case 0xaf160:if(!move_diag())return;kind="move_actor";popped=52;break;
    default:return;
    }
    if(!strcmp(kind,"move_actor")) {   /* no per-call event: called every tick for every moving actor */
        unsigned moves=0;
        /* A missed return must never fill the table the scene observers need: drop entries whose frame has been
         * unwound (their esp is below the current one) and keep at most 16 pending diagnostic calls. */
        for(i=0;i<world_top;i++)if(world_calls[i].kind&&!strcmp(world_calls[i].kind,"move_actor")) {
            if(world_calls[i].esp<c->r[ESP]){world_calls[i].kind=NULL;world_pending--;} else moves++;
        }
        if(moves>=16)return;
        for(i=0;i<128;i++)if(!world_calls[i].kind) {
            WorldCall*p=&world_calls[i];
            p->kind=kind;p->stage=stage;p->self=self;p->world=0;p->esp=c->r[ESP];p->ret=rd32(p->esp);p->popped=popped;
            p->arg0=rd32(p->esp+4);p->arg1=rd32(p->esp+0x20);world_pending++;
            if(i>=world_top)world_top=i+1;
            if(!c->world_floor||(uint64_t)p->esp+p->popped<c->world_floor)
                c->world_floor=(uint32_t)((uint64_t)p->esp+p->popped);
            return;
        }
        return;   /* table full: skip this call (diagnostic only) */
    }
    /* Native GetLevel is MOV EAX,[ECX+d4]; RET. Never infer world from call context. */
    if(*stage && xrt_is_committed(self+0xd4,4))world=rd32(self+0xd4);
    for(i=0;i<128;i++)if(!world_calls[i].kind) {
        WorldCall*p=&world_calls[i];char event[64];
        p->kind=kind;p->stage=stage;p->self=self;p->world=world;p->esp=c->r[ESP];p->ret=rd32(p->esp);p->popped=popped;world_pending++;
        if(i>=world_top)world_top=i+1;
        if(!c->world_floor||(uint64_t)p->esp+p->popped<c->world_floor)
            c->world_floor=(uint32_t)((uint64_t)p->esp+p->popped);
        snprintf(event,sizeof event,"%s_call",kind);
        xrt_event(event,"\"stage\":\"%s\",\"this\":%u,\"world\":%u,\"esp\":%u,\"return\":%u",stage,self,world,p->esp,p->ret);
        return;
    }
    xrt_fatal(c,XRT_EXIT_SETUP,"world observer pending-call bound exceeded");
}
/* Called after translated calls return while c->r[ESP] >= c->world_floor (0: unknown); a pending
 * call can only complete at esp == its esp + popped, so returns below the floor are skipped by the caller. */
void xrt_world_return(CPU*c) {
    unsigned i;uint64_t floor=~0ull;
    if(!world_pending){c->world_floor=0xFFFFFFFFu;return;}
    for(i=0;i<world_top;i++) {
        WorldCall*p=&world_calls[i];char event[64];
        if(!p->kind || c->rv!=p->ret || c->r[ESP]!=p->esp+p->popped)continue;
        if(!strcmp(p->kind,"move_actor")){move_diag_return(p);p->kind=NULL;world_pending--;continue;}
        snprintf(event,sizeof event,"%s_return",p->kind);
        xrt_event(event,"\"stage\":\"%s\",\"this\":%u,\"world\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",p->stage,p->self,p->world,p->esp,c->r[ESP],p->ret,c->rv);
        if(!strcmp(p->kind,"engine_init"))xm_scope(c,XM_END,XM_ADAPTER,"UGameEngine.Init",c->r[EAX]);
        if(!strcmp(p->kind,"level_render")){xrt_scene_level_depth--;xrt_scene_level_renders++;}
        if(!strcmp(p->kind,"camera_render")){xrt_scene_camera_depth--;xrt_scene_camera_renders++;}
        if(!strcmp(p->kind,"engine_tick"))xrt_scene_engine_ticks++;
        if(!strcmp(p->kind,"level_tick"))xrt_scene_level_ticks++;
        p->kind=NULL;world_pending--;
    }
    while(world_top&&!world_calls[world_top-1].kind)world_top--;
    for(i=0;i<world_top;i++)if(world_calls[i].kind&&(uint64_t)world_calls[i].esp+world_calls[i].popped<floor)
        floor=(uint64_t)world_calls[i].esp+world_calls[i].popped;
    c->world_floor=(uint32_t)floor;
}
int xrt_event_room(void){return events&&event_seq<MAX_EVENTS;}
void xrt_event_skip(void){InterlockedIncrement64(&event_seq);}   /* what xrt_event does with a full timeline */

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
    char stream_path[32768];DWORD length;
    events = calloc(MAX_EVENTS, EVENT_LEN);
    if (!events) {
        fprintf(stderr, "xrt: cannot allocate the event timeline\n");
        exit(XRT_EXIT_SETUP);
    }
    length=GetEnvironmentVariableA("XRT_EVENT_STREAM",stream_path,sizeof stream_path);
    if(length) {
        if(length>=sizeof stream_path ||
           (event_stream=CreateFileA(stream_path,FILE_APPEND_DATA,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL))==INVALID_HANDLE_VALUE) {
            fprintf(stderr,"xrt: cannot create exclusive supervisor event stream\n");
            exit(XRT_EXIT_SETUP);
        }
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
    if(event_stream!=INVALID_HANDLE_VALUE) {
        DWORD written=0;
        if(!WriteFile(event_stream,events[seq-1],EVENT_LEN,&written,NULL) || written!=EVENT_LEN) {
            /* Avoid recursive xrt_fatal/xrt_event after an evidence write error. */
            fprintf(stderr,"xrt: supervisor event stream write failed\n");
            ExitProcess(XRT_EXIT_SETUP);
        }
    }
    /* Owner-requested continuation bound. The observer emits this event only at
     * a paired return. Stop before another guest instruction; the report checks
     * selected-world identity independently. Disabled outside bounded clients. */
    if(!strcmp(kind,"viewport_open_return") || !strcmp(kind,"engine_init_return")) {
        char bound[2];
        if(GetEnvironmentVariableA("XRT_STOP_VIEWPORT_INIT",bound,sizeof bound)==1 && bound[0]=='1')
            xrt_fatal(xrt_cur ? &xrt_cur->cpu : NULL,XRT_EXIT_UNSUPPORTED,"bounded checkpoint: %s",kind);
    }
    if(!strcmp(kind,"level_tick_return")) {
        char bound[2];
        if(GetEnvironmentVariableA("XRT_STOP_FIRST_LEVEL_TICK",bound,sizeof bound)==1 && bound[0]=='1')
            xrt_fatal(xrt_cur ? &xrt_cur->cpu : NULL,XRT_EXIT_UNSUPPORTED,"bounded checkpoint: first level Tick returned");
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

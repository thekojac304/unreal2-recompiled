/* Measured COM apartment and native Loader8 boundary. Performance8 is a hard
 * capability gate: a missing x64 class never becomes a successful guest object.
 * No script, audio-path, scheduling or playback behavior is invented here. */
static const GUID dm_clsid_loader={0xd2ac2892,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID dm_iid_loader8={0x19e7c08c,0x0a44,0x4e6a,{0xa1,0x16,0x59,0x5a,0x7c,0xd5,0xde,0x8c}};
static const GUID dm_clsid_performance={0xd2ac2881,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID dm_iid_performance8={0x679c4137,0xc62e,0x4147,{0xb2,0xb4,0x9d,0x56,0x9a,0xcb,0x25,0x4c}};
/* Only the three IUnknown slots are callable in this phase. The remaining
 * twelve native Loader8 methods retain named guest traps. */
typedef struct DmLoader8 DmLoader8;
typedef struct {
    HRESULT (WINAPI*QueryInterface)(DmLoader8*,REFIID,void**);
    ULONG (WINAPI*AddRef)(DmLoader8*);
    ULONG (WINAPI*Release)(DmLoader8*);
    void* unmeasured[12];
} DmLoader8Vtbl;
struct DmLoader8 {const DmLoader8Vtbl*lpVtbl;};
#include "monitor_dmusic.inc"
typedef struct {uint32_t guest,refs;DWORD owner;DmLoader8*host;} DmObject;
static DmObject dm_objects[128];static uint32_t dm_vtable;
static void dmipc_thread_cleanup(CPU*c);
static int dmipc_factory(CPU*c,const GUID*cls,const GUID*iid);
static int dm_equal(const GUID*a,const GUID*b){return !memcmp(a,b,16);}
static void dm_owner(CPU*c,DWORD owner) {
    if(owner!=xm_win_GetCurrentThreadId() || !c->thread || c->thread->host_tid!=owner)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic: COM interface used outside its owning host apartment");
}
void xrt_com_thread_cleanup(CPU*c) {
    unsigned i,released=0,balanced=0;
    if(!c || !c->thread)return;
    dm_owner(c,c->thread->host_tid);
    dmipc_thread_cleanup(c);
    for(i=0;i<128;i++)if(dm_objects[i].owner==xm_win_GetCurrentThreadId()) {
        DmObject*o=&dm_objects[i];
        while(o->refs){xm_dm_Release(c,o->host);o->refs--;xm_resource(c,5,o->guest,(unsigned)(o-dm_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,0,"cleanup-release");released++;}
        o->host=NULL;
    }
    while(c->thread->com_initializations){xm_win_CoUninitialize();c->thread->com_initializations--;balanced++;}
    if(released || balanced)xrt_event("com_cleanup","\"references_released\": %u, \"apartment_references_balanced\": %u",released,balanced);
}
static void dm_cleanup(void){if(xrt_cur)xrt_com_thread_cleanup(&xrt_cur->cpu);}
static void dm_initialize(CPU*c,int extended) {
    HRESULT hr;DWORD flags=extended?ARG(1):COINIT_APARTMENTTHREADED;
    if(ARG(0) || (extended && flags!=COINIT_APARTMENTTHREADED && flags!=COINIT_MULTITHREADED))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CoInitialize: unmeasured reserved pointer or apartment flags %u",flags);
    dm_owner(c,c->thread->host_tid);
    hr=extended?xm_win_CoInitializeEx(NULL,flags):xm_win_CoInitialize(NULL);
    if(SUCCEEDED(hr)){c->thread->com_initializations++;xrt_cleanup_register(dm_cleanup);}
    xrt_event("com_initialize","\"extended\": %d, \"flags\": %u, \"result\": %u, \"owned\": %u",extended,flags,(uint32_t)hr,c->thread->com_initializations);
    RET_STD(extended?2:1,hr);
}
static void hle_CoInitialize(CPU*c){dm_initialize(c,0);}
static void hle_CoInitializeEx(CPU*c){dm_initialize(c,1);}
static void hle_CoUninitialize(CPU*c) {
    dm_owner(c,c->thread->host_tid);
    if(!c->thread->com_initializations)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CoUninitialize: no apartment reference owned by this guest thread");
    xm_win_CoUninitialize();c->thread->com_initializations--;
    xrt_event("com_uninitialize","\"owned\": %u",c->thread->com_initializations);RET_STD(0,0);
}
static DmObject*dm_object(CPU*c,uint32_t p) {
    unsigned i;
    for(i=0;i<128;i++)if(dm_objects[i].guest==p && dm_objects[i].refs){dm_owner(c,dm_objects[i].owner);xm_resource(c,5,p,i+1,(uint64_t)(uintptr_t)dm_objects[i].host,dm_objects[i].refs,0,"receiver");return &dm_objects[i];}
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic: stale or unknown guest COM interface %08x",p);
}
static void dm_QueryInterface(CPU*c) {
    DmObject*o=dm_object(c,ARG(0));GUID iid;void*q=NULL;HRESULT hr;
    com_memory(c,ARG(1),16,"DirectMusic");com_memory(c,ARG(2),4,"DirectMusic");memcpy(&iid,G2H(ARG(1)),16);
    hr=xm_dm_QueryInterface(c,o->host,&iid,&q);
    if(SUCCEEDED(hr)) {
        if(!q || (!dm_equal(&iid,&dm_iid_loader8) && !dm_equal(&iid,&com_iunknown)) || q!=o->host) {
            if(q)XM_Release(c,(IUnknown*)q);
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic Loader8 QueryInterface: unmeasured successful IID/identity %08lx",iid.Data1);
        }
        o->refs++;
    } else if(q)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic QueryInterface: failure returned a non-null native interface");
    wr32(ARG(2),SUCCEEDED(hr)?o->guest:0);
    xrt_event("dmusic_loader","\"method\": \"QueryInterface\", \"result\": %u, \"owned\": %u",(uint32_t)hr,o->refs);RET_STD(3,hr);
}
static void dm_AddRef(CPU*c) {
    DmObject*o=dm_object(c,ARG(0));ULONG n=xm_dm_AddRef(c,o->host);o->refs++;
    xrt_event("dmusic_loader","\"method\": \"AddRef\", \"result\": %lu, \"owned\": %u",n,o->refs);RET_STD(1,n);
}
static void dm_Release(CPU*c) {
    DmObject*o=dm_object(c,ARG(0));ULONG n=xm_dm_Release(c,o->host);o->refs--;xm_resource(c,5,o->guest,(unsigned)(o-dm_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,0,"released");if(!o->refs)o->host=NULL;
    xrt_event("dmusic_loader","\"method\": \"Release\", \"result\": %lu, \"owned\": %u",n,o->refs);RET_STD(1,n);
}
#define DM_TRAP(name) static void dm_##name(CPU*c){DmObject*o=dm_object(c,ARG(0));xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirectMusicLoader8::" #name " is unsupported (interface %08x)",o->guest);}
DM_TRAP(GetObject) DM_TRAP(SetObject) DM_TRAP(SetSearchDirectory) DM_TRAP(ScanDirectory)
DM_TRAP(CacheObject) DM_TRAP(ReleaseObject) DM_TRAP(ClearCache) DM_TRAP(EnableCache)
DM_TRAP(EnumObject) DM_TRAP(CollectGarbage) DM_TRAP(ReleaseObjectByUnknown) DM_TRAP(LoadObjectFromFile)
static DmObject*dm_wrap(CPU*c,DmLoader8*host) {
    static const char*names[]={"DM.QueryInterface","DM.AddRef","DM.Release","DM.GetObject","DM.SetObject","DM.SetSearchDirectory",
        "DM.ScanDirectory","DM.CacheObject","DM.ReleaseObject","DM.ClearCache","DM.EnableCache","DM.EnumObject",
        "DM.CollectGarbage","DM.ReleaseObjectByUnknown","DM.LoadObjectFromFile"};
    unsigned i;DmObject*o=NULL;
    if(!dm_vtable)dm_vtable=com_vtable(names,15);
    for(i=0;i<128;i++)if(!dm_objects[i].guest){o=&dm_objects[i];break;}
    if(!o){xm_dm_Release(c,host);xrt_fatal(c,XRT_EXIT_SETUP,"DirectMusic object table exhausted");}
    o->guest=xrt_rt_alloc(4,4);o->refs=1;o->owner=xm_win_GetCurrentThreadId();o->host=host;wr32(o->guest,dm_vtable);
    xm_resource(c,5,o->guest,(unsigned)(o-dm_objects)+1,(uint64_t)(uintptr_t)host,o->refs,0,"created");
    xrt_cleanup_register(dm_cleanup);return o;
}
static void hle_CoCreateInstance(CPU*c) {
    GUID cls,iid;void*host=NULL;DmObject*o=NULL;HRESULT hr;int performance;
    com_memory(c,ARG(0),16,"CoCreateInstance");com_memory(c,ARG(3),16,"CoCreateInstance");com_memory(c,ARG(4),4,"CoCreateInstance");
    memcpy(&cls,G2H(ARG(0)),16);memcpy(&iid,G2H(ARG(3)),16);
    if(ARG(1) || ARG(2)!=3)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CoCreateInstance: unmeasured aggregation or class context");
    if(dmipc_factory(c,&cls,&iid))return;
    performance=dm_equal(&cls,&dm_clsid_performance) && dm_equal(&iid,&dm_iid_performance8);
    if(!performance && !(dm_equal(&cls,&dm_clsid_loader) && dm_equal(&iid,&dm_iid_loader8)))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"CoCreateInstance: unsupported CLSID %08lx / IID %08lx",cls.Data1,iid.Data1);
    dm_owner(c,c->thread->host_tid);
    hr=xm_win_CoCreateInstance(&cls,NULL,ARG(2),&iid,&host);
    if(!performance && SUCCEEDED(hr)) {
        if(!host)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic Loader8: native success with null output");
        o=dm_wrap(c,(DmLoader8*)host);
    }
    wr32(ARG(4),o?o->guest:0);
    xrt_event("com_factory","\"class\": \"%s\", \"context\": %u, \"result\": %u, \"native_nonnull\": %d, \"object\": %u",
        performance?"DirectMusicPerformance8":"DirectMusicLoader8",ARG(2),(uint32_t)hr,host!=NULL,o?o->guest:0);
    if(performance) {
        if(host)XM_Release(c,(IUnknown*)host);
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic Performance8 compatibility gate: native x64 HRESULT %08lx, output %s; original x86 succeeds. Backend approval required before script/audio integration",(unsigned long)hr,host?"non-null":"NULL");
    }
    if(FAILED(hr) && host)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectMusic Loader8: failure with non-null output");
    RET_STD(5,hr);
}
#define XRT_DMUSIC_BINDINGS \
    {"ole32.dll","CoInitialize",hle_CoInitialize}, \
    {"ole32.dll","CoInitializeEx",hle_CoInitializeEx}, \
    {"ole32.dll","CoUninitialize",hle_CoUninitialize}, \
    {"ole32.dll","CoCreateInstance",hle_CoCreateInstance}, \
    {"xrt.com","DM.QueryInterface",dm_QueryInterface}, \
    {"xrt.com","DM.AddRef",dm_AddRef}, \
    {"xrt.com","DM.Release",dm_Release}, \
    {"xrt.com","DM.GetObject",dm_GetObject}, {"xrt.com","DM.SetObject",dm_SetObject}, \
    {"xrt.com","DM.SetSearchDirectory",dm_SetSearchDirectory}, {"xrt.com","DM.ScanDirectory",dm_ScanDirectory}, \
    {"xrt.com","DM.CacheObject",dm_CacheObject}, {"xrt.com","DM.ReleaseObject",dm_ReleaseObject}, \
    {"xrt.com","DM.ClearCache",dm_ClearCache}, {"xrt.com","DM.EnableCache",dm_EnableCache}, \
    {"xrt.com","DM.EnumObject",dm_EnumObject}, {"xrt.com","DM.CollectGarbage",dm_CollectGarbage}, \
    {"xrt.com","DM.ReleaseObjectByUnknown",dm_ReleaseObjectByUnknown}, {"xrt.com","DM.LoadObjectFromFile",dm_LoadObjectFromFile},

#include "dmusic_backend_pipe.inc"
#include "hle_dmusic_guest.inc"

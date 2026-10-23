/* Measured DirectInput 8W COM boundary. Included by hle_misc.c so all oracle
 * hosts link the same implementation. Host interfaces never enter guest memory.
 * Translated module code resides in the host EXE: its real HINSTANCE is used by
 * DirectInput, while the original guest module/generation remains provenance.
 * A resource-only PE32 HINSTANCE was measured and rejected by DirectInput. */
#define DIRECTINPUT_VERSION 0x0800
#include <dinput.h>

static const GUID di_iid8w={0xbf798031,0x483a,0x4da2,{0xaa,0x99,0x5d,0x64,0xed,0x36,0x97,0x00}};
static const GUID di_iunknown={0,0,0,{0xc0,0,0,0,0,0,0,0x46}};
typedef struct DiObject {
    uint32_t guest, refs, owner, generation;
    IDirectInput8W *input;
} DiObject;
static DiObject di_objects[128];
static uint32_t di_vtable;
static void di_cleanup(void) {
    unsigned i;
    uint32_t count=0;
    for(i=0;i<128;i++) while(di_objects[i].refs) {
        di_objects[i].input->lpVtbl->Release(di_objects[i].input);
        count++;
        if(!--di_objects[i].refs) di_objects[i].input=NULL;
    }
    xrt_event("dinput_cleanup","\"references_released\": %u",count);
}

static int di_guid_equal(const GUID *a,const GUID *b) { return !memcmp(a,b,sizeof *a); }
static void di_memory(CPU*c,uint32_t p,uint32_t size) {
    if(!p || !xrt_is_committed(p,size))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput: invalid guest range %08x size %u",p,size);
}
static DiObject *di_object(CPU*c,uint32_t p) {
    unsigned i;
    for(i=0;i<128;i++) if(di_objects[i].guest==p && di_objects[i].refs) return &di_objects[i];
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput: stale or unknown guest COM interface %08x",p);
}
static void di_result(const char*method,DiObject*o,HRESULT hr) {
    xrt_event("dinput","\"method\": \"%s\", \"object\": %u, \"result\": %u",method,o?o->guest:0,(uint32_t)hr);
}
static void di_QueryInterface(CPU*c) {
    DiObject*o=di_object(c,ARG(0));
    GUID iid;
    void *q=NULL;
    HRESULT hr;
    di_memory(c,ARG(1),16); di_memory(c,ARG(2),4);
    memcpy(&iid,G2H(ARG(1)),16);
    hr=o->input->lpVtbl->QueryInterface(o->input,&iid,&q);
    if(SUCCEEDED(hr)) {
        if(!di_guid_equal(&iid,&di_iid8w) && !di_guid_equal(&iid,&di_iunknown)) {
            ((IUnknown*)q)->lpVtbl->Release((IUnknown*)q);
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput QueryInterface: successful unmodelled IID %08lx",iid.Data1);
        }
        if(q!=o->input) {
            ((IUnknown*)q)->lpVtbl->Release((IUnknown*)q);
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput QueryInterface: unmeasured host identity");
        }
        o->refs++;
    }
    wr32(ARG(2),SUCCEEDED(hr)?o->guest:0);
    di_result("QueryInterface",o,hr);
    RET_STD(3,hr);
}
static void di_AddRef(CPU*c) {
    DiObject*o=di_object(c,ARG(0));
    ULONG n=o->input->lpVtbl->AddRef(o->input);
    o->refs++;
    di_result("AddRef",o,(HRESULT)n); RET_STD(1,n);
}
static void di_Release(CPU*c) {
    DiObject*o=di_object(c,ARG(0));
    ULONG n=o->input->lpVtbl->Release(o->input);
    o->refs--;
    if(!o->refs) o->input=NULL; /* guest allocation is a non-recycled tombstone */
    di_result("Release",o,(HRESULT)n); RET_STD(1,n);
}
#define DI_UNSUPPORTED(name) static void di_##name(CPU*c) { \
    DiObject*o=di_object(c,ARG(0)); \
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirectInput8W::" #name " is unmeasured (interface %08x, caller %08x)",o->guest,rd32(c->r[ESP])); }
DI_UNSUPPORTED(CreateDevice)
DI_UNSUPPORTED(EnumDevices)
DI_UNSUPPORTED(GetDeviceStatus)
DI_UNSUPPORTED(RunControlPanel)
DI_UNSUPPORTED(Initialize)
DI_UNSUPPORTED(FindDevice)
DI_UNSUPPORTED(EnumDevicesBySemantics)
DI_UNSUPPORTED(ConfigureDevices)
static DiObject*di_wrap(CPU*c,IDirectInput8W*input,uint32_t owner) {
    unsigned i;
    DiObject*o=NULL;
    const char*names[]={"DI.QueryInterface","DI.AddRef","DI.Release","DI.CreateDevice","DI.EnumDevices",
        "DI.GetDeviceStatus","DI.RunControlPanel","DI.Initialize","DI.FindDevice","DI.EnumDevicesBySemantics","DI.ConfigureDevices"};
    if(!di_vtable) {
        di_vtable=xrt_rt_alloc(sizeof names/sizeof *names*4,4);
        for(i=0;i<sizeof names/sizeof *names;i++) wr32(di_vtable+4*i,xrt_hle_proc("xrt.com",names[i]));
    }
    for(i=0;i<128;i++) if(!di_objects[i].guest) {o=&di_objects[i];break;}
    if(!o) xrt_fatal(c,XRT_EXIT_SETUP,"DirectInput object table exhausted");
    o->guest=xrt_rt_alloc(4,4); o->refs=1; o->input=input; o->owner=owner;
    xrt_cleanup_register(di_cleanup);
    o->generation=owner?xrt_module_by_addr(owner)->generation:0;
    wr32(o->guest,di_vtable);
    return o;
}
static void hle_DirectInput8Create(CPU*c) {
    typedef HRESULT (WINAPI*Fn)(HINSTANCE,DWORD,REFIID,LPVOID*,LPUNKNOWN);
    static HMODULE library;
    Fn fn;
    GUID iid;
    void*input=NULL;
    HRESULT hr;
    HINSTANCE instance=NULL;
    XrtModule*m;
    DiObject*o=NULL;
    uint32_t owner=ARG(0),version=ARG(1),outer=ARG(4);
    di_memory(c,ARG(2),16); di_memory(c,ARG(3),4);
    memcpy(&iid,G2H(ARG(2)),16);
    if(outer) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput8Create: COM aggregation is unmeasured (outer %08x)",outer);
    if(owner) {
        m=xrt_module_by_addr(owner);
        if(!m || m->base!=owner) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput8Create: unknown guest HINSTANCE %08x",owner);
        instance=GetModuleHandleW(NULL); /* actual module containing the translated caller */
    }
    if(!library) library=LoadLibraryExW(L"dinput8.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);
    fn=library?(Fn)GetProcAddress(library,"DirectInput8Create"):NULL;
    if(!fn) xrt_fatal(c,XRT_EXIT_SETUP,"host DirectInput8Create unavailable");
    hr=fn(instance,version,&iid,&input,NULL);
    if(SUCCEEDED(hr)) {
        if(!di_guid_equal(&iid,&di_iid8w)) {
            ((IUnknown*)input)->lpVtbl->Release((IUnknown*)input);
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput8Create: unmodelled successful IID %08lx",iid.Data1);
        }
        o=di_wrap(c,(IDirectInput8W*)input,owner);
    }
    wr32(ARG(3),o?o->guest:0);
    xrt_event("dinput_create","\"owner\": %u, \"version\": %u, \"iid\": %u, \"outer\": %u, \"object\": %u, \"result\": %u",
        owner,version,iid.Data1,outer,o?o->guest:0,(uint32_t)hr);
    RET_STD(5,hr);
}
#define XRT_DINPUT_BINDINGS \
    {"dinput8.dll","DirectInput8Create",hle_DirectInput8Create}, \
    {"xrt.com","DI.QueryInterface",di_QueryInterface}, \
    {"xrt.com","DI.AddRef",di_AddRef}, \
    {"xrt.com","DI.Release",di_Release}, \
    {"xrt.com","DI.CreateDevice",di_CreateDevice}, \
    {"xrt.com","DI.EnumDevices",di_EnumDevices}, \
    {"xrt.com","DI.GetDeviceStatus",di_GetDeviceStatus}, \
    {"xrt.com","DI.RunControlPanel",di_RunControlPanel}, \
    {"xrt.com","DI.Initialize",di_Initialize}, \
    {"xrt.com","DI.FindDevice",di_FindDevice}, \
    {"xrt.com","DI.EnumDevicesBySemantics",di_EnumDevicesBySemantics}, \
    {"xrt.com","DI.ConfigureDevices",di_ConfigureDevices},

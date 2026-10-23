/* Measured DirectInput 8W COM boundary. Included by hle_misc.c so all oracle
 * hosts link the same implementation. Host interfaces never enter guest memory.
 * Translated module code resides in the host EXE: its real HINSTANCE is used by
 * DirectInput, while the original guest module/generation remains provenance.
 * A resource-only PE32 HINSTANCE was measured and rejected by DirectInput. */
#define DIRECTINPUT_VERSION 0x0800
#include <dinput.h>

static const GUID di_iid8w={0xbf798031,0x483a,0x4da2,{0xaa,0x99,0x5d,0x64,0xed,0x36,0x97,0x00}};
typedef struct DiObject {
    uint32_t guest, refs, owner, generation;
    IDirectInput8W *input;
} DiObject;
static DiObject di_objects[128];
static uint32_t di_vtable;
typedef struct DiDevice {
    uint32_t guest,refs;
    IDirectInputDevice8W *input;
} DiDevice;
static DiDevice di_devices[128];
static uint32_t did_vtable;
static const GUID did_iid8w={0x54d41081,0xdc15,0x4833,{0xa4,0x1b,0x74,0x8f,0x73,0xa3,0x81,0x79}};
static void di_cleanup(void) {
    unsigned i;
    uint32_t count=0,devices=0;
    for(i=0;i<128;i++) while(di_devices[i].refs) {
        di_devices[i].input->lpVtbl->Release(di_devices[i].input);
        devices++;
        if(!--di_devices[i].refs)di_devices[i].input=NULL;
    }
    for(i=0;i<128;i++) while(di_objects[i].refs) {
        di_objects[i].input->lpVtbl->Release(di_objects[i].input);
        count++;
        if(!--di_objects[i].refs) di_objects[i].input=NULL;
    }
    xrt_event("dinput_cleanup","\"references_released\": %u,\"device_references_released\":%u",count,devices);
}

static int di_guid_equal(const GUID *a,const GUID *b) { return !memcmp(a,b,sizeof *a); }
static void di_memory(CPU*c,uint32_t p,uint32_t size) {
    com_memory(c,p,size,"DirectInput");
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
        if(!di_guid_equal(&iid,&di_iid8w) && !di_guid_equal(&iid,&com_iunknown)) {
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
DI_UNSUPPORTED(EnumDevices)
DI_UNSUPPORTED(GetDeviceStatus)
DI_UNSUPPORTED(RunControlPanel)
DI_UNSUPPORTED(Initialize)
DI_UNSUPPORTED(FindDevice)
DI_UNSUPPORTED(EnumDevicesBySemantics)
DI_UNSUPPORTED(ConfigureDevices)
static DiDevice*did_object(CPU*c,uint32_t p) {
    unsigned i;
    for(i=0;i<128;i++)if(di_devices[i].guest==p && di_devices[i].refs)return &di_devices[i];
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput device: stale or unknown guest COM interface %08x",p);
}
static void did_result(const char*method,DiDevice*o,HRESULT hr) {
    xrt_event("dinput_device","\"method\":\"%s\",\"object\":%u,\"result\":%u",method,o->guest,(uint32_t)hr);
}
static void did_QueryInterface(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));GUID iid;void*q=NULL;HRESULT hr;
    di_memory(c,ARG(1),16);di_memory(c,ARG(2),4);memcpy(&iid,G2H(ARG(1)),16);
    hr=o->input->lpVtbl->QueryInterface(o->input,&iid,&q);
    if(SUCCEEDED(hr)) {
        if((!di_guid_equal(&iid,&did_iid8w) && !di_guid_equal(&iid,&com_iunknown)) || q!=o->input) {
            ((IUnknown*)q)->lpVtbl->Release((IUnknown*)q);
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput device QI: successful unmodelled IID/identity %08lx",iid.Data1);
        }
        o->refs++;
    }
    wr32(ARG(2),SUCCEEDED(hr)?o->guest:0);did_result("QueryInterface",o,hr);RET_STD(3,hr);
}
static void did_AddRef(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));ULONG n=o->input->lpVtbl->AddRef(o->input);
    o->refs++;did_result("AddRef",o,(HRESULT)n);RET_STD(1,n);
}
static void did_Release(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));ULONG n=o->input->lpVtbl->Release(o->input);
    if(!--o->refs)o->input=NULL;
    did_result("Release",o,(HRESULT)n);RET_STD(1,n);
}
static void did_Acquire(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));HRESULT hr=o->input->lpVtbl->Acquire(o->input);
    did_result("Acquire",o,hr);RET_STD(1,hr);
}
static void did_SetDataFormat(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));uint32_t p=ARG(1),count,objects,i;
    DIDATAFORMAT format;DIOBJECTDATAFORMAT data[256];GUID guids[256];HRESULT hr;
    di_memory(c,p,24);count=rd32(p+16);objects=rd32(p+20);
    if(rd32(p)!=24 || rd32(p+4)!=16 || count>256)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput SetDataFormat: unmeasured guest layout/count");
    if(count)di_memory(c,objects,count*16);
    memset(&format,0,sizeof format);memset(data,0,sizeof data);
    format.dwSize=sizeof format;format.dwObjSize=sizeof data[0];format.dwFlags=rd32(p+8);
    format.dwDataSize=rd32(p+12);format.dwNumObjs=count;format.rgodf=objects?data:NULL;
    for(i=0;i<count;i++) {
        uint32_t q=objects+i*16,guid=rd32(q);
        if(guid) {di_memory(c,guid,16);memcpy(&guids[i],G2H(guid),16);data[i].pguid=&guids[i];}
        data[i].dwOfs=rd32(q+4);data[i].dwType=rd32(q+8);data[i].dwFlags=rd32(q+12);
    }
    hr=o->input->lpVtbl->SetDataFormat(o->input,&format);
    xrt_event("dinput_format","\"object\":%u,\"guest_size\":24,\"host_size\":%u,\"guest_object_size\":16,\"host_object_size\":%u,\"flags\":%u,\"data_bytes\":%u,\"objects\":%u,\"result\":%u",o->guest,(unsigned)sizeof format,(unsigned)sizeof data[0],format.dwFlags,format.dwDataSize,count,(uint32_t)hr);
    RET_STD(2,hr);
}
static void did_SetProperty(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));uint32_t property=ARG(1),p=ARG(2);DIPROPDWORD value;HRESULT hr;
    if(property!=1 && property!=2)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput SetProperty: unmeasured property %08x",property);
    di_memory(c,p,20);memcpy(&value,G2H(p),20);
    if(value.diph.dwSize!=20 || value.diph.dwHeaderSize!=16)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput SetProperty: unmeasured guest layout");
    hr=o->input->lpVtbl->SetProperty(o->input,(const GUID*)(uintptr_t)property,&value.diph);
    xrt_event("dinput_property","\"object\":%u,\"property\":%u,\"how\":%u,\"offset\":%u,\"value\":%u,\"result\":%u",o->guest,property,value.diph.dwHow,value.diph.dwObj,value.dwData,(uint32_t)hr);
    RET_STD(3,hr);
}
static void did_GetDeviceData(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));uint32_t size=ARG(1),p=ARG(2),pc=ARG(3),flags=ARG(4),i,capacity;
    DIDEVICEOBJECTDATA data[256];DWORD count;HRESULT hr;
    di_memory(c,pc,4);capacity=count=rd32(pc);
    if(size!=20 || capacity>256 || flags>1)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput GetDeviceData: unmeasured layout/count/flags");
    if(p && capacity)di_memory(c,p,capacity*20);
    memset(data,0,sizeof data);
    if(p)for(i=0;i<capacity;i++) {
        uint32_t q=p+i*20;
        data[i].dwOfs=rd32(q);data[i].dwData=rd32(q+4);data[i].dwTimeStamp=rd32(q+8);
        data[i].dwSequence=rd32(q+12);data[i].uAppData=rd32(q+16);
    }
    hr=o->input->lpVtbl->GetDeviceData(o->input,sizeof data[0],p?data:NULL,&count,flags);
    if(p && count>capacity)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput GetDeviceData: host exceeded caller capacity");
    if(p)for(i=0;i<capacity;i++) {
        uint32_t q=p+i*20;ULONG_PTR app=data[i].uAppData;
        if(app>UINT32_MAX && app!=~(ULONG_PTR)0)
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput GetDeviceData: unmapped host application data");
        wr32(q,data[i].dwOfs);wr32(q+4,data[i].dwData);wr32(q+8,data[i].dwTimeStamp);
        wr32(q+12,data[i].dwSequence);wr32(q+16,(uint32_t)app);
    }
    wr32(pc,count);
    xrt_event("dinput_data","\"object\":%u,\"capacity\":%u,\"count\":%u,\"guest_size\":20,\"host_size\":%u,\"result\":%u",o->guest,capacity,count,(unsigned)sizeof data[0],(uint32_t)hr);
    RET_STD(5,hr);
}
static void did_Unsupported(CPU*c) {
    DiDevice*o=did_object(c,ARG(0));
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirectInputDevice8W method is unmeasured (interface %08x, caller %08x)",o->guest,rd32(c->r[ESP]));
}
static DiDevice*did_wrap(CPU*c,IDirectInputDevice8W*input) {
    unsigned i;DiDevice*o=NULL;
    const char*names[32];
    for(i=0;i<32;i++)names[i]="DID.Unsupported";
    names[0]="DID.QueryInterface";names[1]="DID.AddRef";names[2]="DID.Release";
    names[6]="DID.SetProperty";names[7]="DID.Acquire";names[10]="DID.GetDeviceData";names[11]="DID.SetDataFormat";
    if(!did_vtable)did_vtable=com_vtable(names,32);
    for(i=0;i<128;i++)if(!di_devices[i].guest){o=&di_devices[i];break;}
    if(!o)xrt_fatal(c,XRT_EXIT_SETUP,"DirectInput device table exhausted");
    o->guest=xrt_rt_alloc(4,4);o->refs=1;o->input=input;wr32(o->guest,did_vtable);return o;
}
static void di_CreateDevice(CPU*c) {
    DiObject*o=di_object(c,ARG(0));GUID guid;IDirectInputDevice8W*input=NULL;DiDevice*device=NULL;HRESULT hr;
    di_memory(c,ARG(1),16);di_memory(c,ARG(2),4);memcpy(&guid,G2H(ARG(1)),16);
    if(ARG(3))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput CreateDevice: aggregation is unmeasured");
    hr=o->input->lpVtbl->CreateDevice(o->input,&guid,&input,NULL);
    if(SUCCEEDED(hr))device=did_wrap(c,input);
    else if(input)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"DirectInput CreateDevice: unexpected failure output");
    wr32(ARG(2),device?device->guest:0);
    xrt_event("dinput_device_create","\"parent\":%u,\"guid_data1\":%u,\"object\":%u,\"result\":%u",o->guest,guid.Data1,device?device->guest:0,(uint32_t)hr);
    RET_STD(4,hr);
}
static DiObject*di_wrap(CPU*c,IDirectInput8W*input,uint32_t owner) {
    unsigned i;
    DiObject*o=NULL;
    const char*names[]={"DI.QueryInterface","DI.AddRef","DI.Release","DI.CreateDevice","DI.EnumDevices",
        "DI.GetDeviceStatus","DI.RunControlPanel","DI.Initialize","DI.FindDevice","DI.EnumDevicesBySemantics","DI.ConfigureDevices"};
    if(!di_vtable) {
        di_vtable=com_vtable(names,sizeof names/sizeof *names);
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
    {"xrt.com","DID.QueryInterface",did_QueryInterface}, \
    {"xrt.com","DID.AddRef",did_AddRef}, \
    {"xrt.com","DID.Release",did_Release}, \
    {"xrt.com","DID.SetDataFormat",did_SetDataFormat}, \
    {"xrt.com","DID.SetProperty",did_SetProperty}, \
    {"xrt.com","DID.Acquire",did_Acquire}, \
    {"xrt.com","DID.GetDeviceData",did_GetDeviceData}, \
    {"xrt.com","DID.Unsupported",did_Unsupported}, \
    {"xrt.com","DI.EnumDevices",di_EnumDevices}, \
    {"xrt.com","DI.GetDeviceStatus",di_GetDeviceStatus}, \
    {"xrt.com","DI.RunControlPanel",di_RunControlPanel}, \
    {"xrt.com","DI.Initialize",di_Initialize}, \
    {"xrt.com","DI.FindDevice",di_FindDevice}, \
    {"xrt.com","DI.EnumDevicesBySemantics",di_EnumDevicesBySemantics}, \
    {"xrt.com","DI.ConfigureDevices",di_ConfigureDevices},

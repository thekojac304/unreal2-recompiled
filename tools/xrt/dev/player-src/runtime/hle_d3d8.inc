#include "monitor_com.inc"
/* Measured D3D8 creation/query boundary. Explicit host backend only, no
 * substituted caps. Guest COM pointers/vtables remain 32-bit. */
#include "d3d8_abi.h"
static void d8_device_memory(CPU*,uint32_t,uint32_t,int);
static LONG d8_api_entry(CPU*,unsigned,unsigned);
typedef struct D8Object {
    uint32_t guest,refs,children,pending;
    D8Interface *host;
} D8Object;
static D8Object d8_objects[128];
static uint32_t d8_vtable;
static HMODULE d8_library,d8_dependency;
static void d8_device_cleanup(void);
static int d8_cleanup_must_retain(void);
static void d8_cleanup(void) {
    unsigned i,n=0;
    if(d8_cleanup_must_retain()) {
        xrt_event("d3d8_failure_containment","\"modules_retained\":true,\"retry_permitted\":false,\"cleanup\":\"process_teardown\"");
        return;
    }
    d8_device_cleanup();
    for(i=0;i<128;i++) while(d8_objects[i].refs) {
        XM_Release(NULL,d8_objects[i].host);n++;
        if(!--d8_objects[i].refs)d8_objects[i].host=NULL;xm_resource(NULL,1,d8_objects[i].guest,i+1,(uint64_t)(uintptr_t)d8_objects[i].host,d8_objects[i].refs,d8_objects[i].children,"cleanup-release");
    }
    xrt_event("d3d8_cleanup","\"references_released\": %u",n);
    if(d8_library)FreeLibrary(d8_library);
    if(d8_dependency)FreeLibrary(d8_dependency);
    d8_library=d8_dependency=NULL;
    xrt_event("d3d8_unload","\"d3d8_loaded\":%s,\"d3d9_loaded\":%s",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false");
}
static D8Object*d8_object(CPU*c,uint32_t p) {
    unsigned i;
    for(i=0;i<128;i++)if(d8_objects[i].guest==p && d8_objects[i].refs && d8_objects[i].host){xm_resource(c,1,p,i+1,(uint64_t)(uintptr_t)d8_objects[i].host,d8_objects[i].refs,0,"receiver");return &d8_objects[i];}
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"Direct3D8: stale or unknown guest COM interface %08x",p);
}
static void d8_result(CPU*c,const char*method,D8Object*o,uint32_t adapter,uint32_t arg,HRESULT hr) {
    if(o)xm_resource(c,1,o->guest,(unsigned)(o-d8_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,o->children+o->pending,method);
    xrt_event("d3d8","\"method\": \"%s\", \"object\": %u, \"adapter\": %u, \"argument\": %u, \"result\": %u, \"caller\": %u",
        method,o?o->guest:0,adapter,arg,(uint32_t)hr,rd32(c->r[ESP]));
}
static void d8_words(const char*name,const void*p,unsigned count) {
    unsigned i,j;
    const DWORD*w=p;
    char buf[160];
    for(i=0;i<count;i+=8) {
        unsigned pos=0;
        for(j=i;j<count && j<i+8;j++)pos+=(unsigned)snprintf(buf+pos,sizeof buf-pos,"%s%08lx",j==i?"":",",w[j]);
        xrt_event("d3d8_data","\"name\": \"%s\", \"offset\": %u, \"words\": \"%s\"",name,i*4,buf);
    }
}
static void d8_QueryInterface(CPU*c) {
    d8_api_entry(c,200,3);
    D8Object*o=d8_object(c,ARG(0));GUID iid;void*q=NULL;HRESULT hr;DWORD error;
    static const GUID iid8={0x1dd9e8da,0x1c77,0x4d40,{0xb0,0xcf,0x98,0xfe,0xfd,0xff,0x95,0x12}};
    d8_device_memory(c,ARG(1),16,0);d8_device_memory(c,ARG(2),4,1);
    memcpy(&iid,G2H(ARG(1)),16);SetLastError(xrt_get_last_error(c));hr=XM_QueryInterface(c,o->host,&iid,&q);error=GetLastError();
    if(SUCCEEDED(hr)) {
        if((memcmp(&iid,&iid8,16) && memcmp(&iid,&com_iunknown,16)) || q!=o->host) {
            XM_Release(c,(IUnknown*)q);
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"Direct3D8 QueryInterface: unmodelled successful interface");
        }
        o->refs++;
    }
    wr32(ARG(2),SUCCEEDED(hr)?o->guest:0);d8_result(c,"QueryInterface",o,0,iid.Data1,hr);xrt_set_last_error(c,error);RET_STD(3,hr);
}
static void d8_AddRef(CPU*c) {
    d8_api_entry(c,201,1);
    D8Object*o=d8_object(c,ARG(0));ULONG n;DWORD error;SetLastError(xrt_get_last_error(c));n=XM_AddRef(c,o->host);error=GetLastError();o->refs++;
    d8_result(c,"AddRef",o,0,0,(HRESULT)n);xrt_set_last_error(c,error);RET_STD(1,n);
}
static void d8_Release(CPU*c) {
    d8_api_entry(c,202,1);
    D8Object*o=d8_object(c,ARG(0));ULONG n;DWORD error;
    SetLastError(xrt_get_last_error(c));n=XM_Release(c,o->host);error=GetLastError();
    if(!--o->refs && !o->children && !o->pending)o->host=NULL;
    xrt_set_last_error(c,error);
    d8_result(c,"Release",o,0,0,(HRESULT)n);RET_STD(1,n);
}
static void d8_GetAdapterCount(CPU*c) {
    d8_api_entry(c,204,1);
    D8Object*o=d8_object(c,ARG(0));UINT n;DWORD error;SetLastError(xrt_get_last_error(c));n=XM_GetAdapterCount(c,o->host);error=GetLastError();
    d8_result(c,"GetAdapterCount",o,0,0,(HRESULT)n);xrt_set_last_error(c,error);RET_STD(1,n);
}
static void d8_GetAdapterModeCount(CPU*c) {
    d8_api_entry(c,206,2);
    D8Object*o=d8_object(c,ARG(0));UINT adapter=ARG(1);
    uint32_t esp=c->r[ESP],ret=rd32(esp);
    UINT adapters,n;
    xrt_event("d3d8_mode_count_call","\"this\":%u,\"adapter\":%u,\"esp\":%u,\"return\":%u",o->guest,adapter,esp,ret);
    adapters=XM_GetAdapterCount(c,o->host);
    /* DXVK 3.1.1 indexes its cached vector without checking Adapter. Native
     * invalid-index observations are undefined reads, not guest results. */
    if(adapter>=adapters) {
        xrt_event("d3d8_invalid_adapter","\"method\":\"GetAdapterModeCount\",\"object\":%u,\"adapter\":%u,\"adapter_count\":%u,\"native_mode_count_called\":false,\"caller\":%u",
            o->guest,adapter,adapters,rd32(c->r[ESP]));
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirect3D8::GetAdapterModeCount: invalid adapter %u (DXVK adapter count %u); unchecked native access refused",adapter,adapters);
    }
    DWORD error;SetLastError(xrt_get_last_error(c));n=XM_GetAdapterModeCount(c,o->host,adapter);error=GetLastError();
    d8_result(c,"GetAdapterModeCount",o,adapter,0,(HRESULT)n);xrt_set_last_error(c,error);RET_STD(2,n);
    xrt_event("d3d8_mode_count_return","\"this\":%u,\"adapter\":%u,\"result\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        o->guest,adapter,n,esp,c->r[ESP],ret,c->rv);
}
static void d8_mode_output(CPU*c,uint32_t p) {
    uint64_t cursor=p,end=(uint64_t)p+16;
    if(!p)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirect3D8::EnumAdapterModes: NULL output is unmeasured");
    if(end>0x100000000ull)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"Direct3D8 mode: invalid guest range %08x size 16",p);
    d8_device_memory(c,p,16,1);
    while(cursor<end) {
        MEMORY_BASIC_INFORMATION mbi;DWORD protection;
        if(!VirtualQuery(xrt_g+cursor,&mbi,sizeof mbi))
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"Direct3D8 mode: invalid guest range %08x size 16",p);
        protection=mbi.Protect & 0xff;
        if((mbi.Protect & PAGE_GUARD) || (protection!=PAGE_READWRITE && protection!=PAGE_WRITECOPY &&
                protection!=PAGE_EXECUTE_READWRITE && protection!=PAGE_EXECUTE_WRITECOPY))
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"Direct3D8 mode: nonwritable guest range %08x size 16",p);
        cursor=(uint64_t)((uint8_t*)mbi.BaseAddress-xrt_g)+mbi.RegionSize;
    }
}
static void d8_EnumAdapterModes(CPU*c) {
    d8_api_entry(c,207,4);
    D8Object*o=d8_object(c,ARG(0));UINT adapter=ARG(1),index=ARG(2),adapters,count=0;
    uint32_t output=ARG(3),esp=c->r[ESP],ret=rd32(esp);D8Mode mode;HRESULT hr;DWORD error;
    d8_mode_output(c,output);
    adapters=XM_GetAdapterCount(c,o->host);
    /* Only valid adapters may reach DXVK's unchecked cached mode-count access.
     * EnumAdapterModes itself has measured bounds checks for both indices. Call
     * it even on invalid indices to retain the actual backend HRESULT/error. */
    if(adapter<adapters)count=XM_GetAdapterModeCount(c,o->host,adapter);
    mode.width=rd32(output);mode.height=rd32(output+4);
    mode.refresh=rd32(output+8);mode.format=rd32(output+12);
    xrt_event("d3d8_enum_call","\"this\":%u,\"adapter\":%u,\"mode\":%u,\"output\":%u,\"adapter_count\":%u,\"mode_count\":%u,\"valid_adapter\":%s,\"valid_mode\":%s,\"esp\":%u,\"return\":%u",
        o->guest,adapter,index,output,adapters,count,adapter<adapters?"true":"false",adapter<adapters && index<count?"true":"false",esp,ret);
    SetLastError(xrt_get_last_error(c));
    hr=XM_EnumAdapterModes(c,o->host,adapter,index,&mode);error=GetLastError();
    xrt_set_last_error(c,error);
    /* Pointer-free DWORD fields, exactly sixteen bytes; no native layout/pointer
     * is copied. Measured failure leaves the caller's output entirely untouched. */
    if(SUCCEEDED(hr)) {
        wr32(output,mode.width);wr32(output+4,mode.height);
        wr32(output+8,mode.refresh);wr32(output+12,mode.format);
    }
    d8_result(c,"EnumAdapterModes",o,adapter,index,hr);d8_words("display_mode",&mode,4);
    RET_STD(4,hr);
    xrt_event("d3d8_enum_return","\"this\":%u,\"adapter\":%u,\"mode\":%u,\"output\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        o->guest,adapter,index,output,(uint32_t)hr,error,esp,c->r[ESP],ret,c->rv);
}
static void d8_GetAdapterDisplayMode(CPU*c) {
    d8_api_entry(c,208,3);
    D8Object*o=d8_object(c,ARG(0));UINT adapter=ARG(1),adapters;
    uint32_t output=ARG(2),esp=c->r[ESP],ret=rd32(esp);
    D8Mode mode;HRESULT hr;DWORD error;
    /* Valid native adapters fault on NULL/nonwritable outputs. Keep those
     * pointer cases explicit unsupported stops, rather than faulting the host. */
    if(!output)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirect3D8::GetAdapterDisplayMode: NULL output is unsupported (measured native write access violation)");
    d8_mode_output(c,output);
    adapters=XM_GetAdapterCount(c,o->host);
    mode.width=rd32(output);mode.height=rd32(output+4);
    mode.refresh=rd32(output+8);mode.format=rd32(output+12);
    xrt_event("d3d8_display_call","\"this\":%u,\"adapter\":%u,\"output\":%u,\"adapter_count\":%u,\"valid_adapter\":%s,\"esp\":%u,\"return\":%u",
        o->guest,adapter,output,adapters,adapter<adapters?"true":"false",esp,ret);
    SetLastError(xrt_get_last_error(c));
    /* Unlike GetAdapterModeCount, this method checks invalid adapters safely.
     * Preserve its measured actual failure HRESULT and untouched local output. */
    hr=XM_GetAdapterDisplayMode(c,o->host,adapter,&mode);error=GetLastError();
    xrt_set_last_error(c,error);
    wr32(output,mode.width);wr32(output+4,mode.height);
    wr32(output+8,mode.refresh);wr32(output+12,mode.format);
    d8_result(c,"GetAdapterDisplayMode",o,adapter,0,hr);d8_words("adapter_display_mode",&mode,4);
    RET_STD(3,hr);
    xrt_event("d3d8_display_return","\"this\":%u,\"adapter\":%u,\"output\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        o->guest,adapter,output,(uint32_t)hr,error,esp,c->r[ESP],ret,c->rv);
}
static void d8_CheckDepthStencilMatch(CPU*c) {
    d8_api_entry(c,212,6);
    D8Object*o=d8_object(c,ARG(0));
    UINT adapter=ARG(1),type=ARG(2),af=ARG(3),rt=ARG(4),ds=ARG(5);
    UINT adapters=XM_GetAdapterCount(c,o->host);
    uint32_t esp=c->r[ESP],ret=rd32(esp);HRESULT hr;
    DWORD seed=xrt_get_last_error(c),error;
    xrt_event("d3d8_depth_call","\"this\":%u,\"adapter\":%u,\"type\":%u,\"adapter_format\":%u,\"render_target_format\":%u,\"depth_stencil_format\":%u,\"adapter_count\":%u,\"valid_adapter\":%s,\"last_error_seed\":%u,\"esp\":%u,\"return\":%u",
        o->guest,adapter,type,af,rt,ds,adapters,adapter<adapters?"true":"false",seed,esp,ret);
    /* Both pinned native architectures safely reject invalid adapters here.
     * Forward them to retain the actual HRESULT. DeviceType and AdapterFormat
     * are not rejected by this backend query, including measured invalid enums.
     * All five arguments are scalar UINTs; no guest/native pointer is marshalled. */
    SetLastError(seed);
    hr=XM_CheckDepthStencilMatch(c,o->host,adapter,type,af,rt,ds);error=GetLastError();
    xrt_set_last_error(c,error);
    d8_result(c,"CheckDepthStencilMatch",o,adapter,ds,hr);RET_STD(6,hr);
    xrt_event("d3d8_depth_return","\"this\":%u,\"adapter\":%u,\"type\":%u,\"adapter_format\":%u,\"render_target_format\":%u,\"depth_stencil_format\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        o->guest,adapter,type,af,rt,ds,(uint32_t)hr,error,esp,c->r[ESP],ret,c->rv);
}
static void d8_GetAdapterIdentifier(CPU*c) {
    d8_api_entry(c,205,4);
    D8Object*o=d8_object(c,ARG(0));D8Identifier id;HRESULT hr;DWORD error;
    d8_device_memory(c,ARG(3),D8_IDENTIFIER_BYTES,1);
    memset(&id,0,sizeof id);memcpy(&id,G2H(ARG(3)),D8_IDENTIFIER_BYTES);
    SetLastError(xrt_get_last_error(c));hr=XM_GetAdapterIdentifier(c,o->host,ARG(1),ARG(2),&id);error=GetLastError();
    memcpy(G2H(ARG(3)),&id,D8_IDENTIFIER_BYTES);
    d8_result(c,"GetAdapterIdentifier",o,ARG(1),ARG(2),hr);d8_words("identifier",&id,D8_IDENTIFIER_BYTES/4);xrt_set_last_error(c,error);RET_STD(4,hr);
}
static void d8_GetDeviceCaps(CPU*c) {
    d8_api_entry(c,213,4);
    D8Object*o=d8_object(c,ARG(0));D8Caps caps;HRESULT hr;DWORD error;
    d8_device_memory(c,ARG(3),sizeof caps,1);memcpy(&caps,G2H(ARG(3)),sizeof caps);
    SetLastError(xrt_get_last_error(c));hr=XM_GetDeviceCaps(c,o->host,ARG(1),ARG(2),&caps);error=GetLastError();
    memcpy(G2H(ARG(3)),&caps,sizeof caps);
    d8_result(c,"GetDeviceCaps",o,ARG(1),ARG(2),hr);d8_words("caps",&caps,53);xrt_set_last_error(c,error);RET_STD(4,hr);
}
static void d8_CheckDeviceFormat(CPU*c) {
    d8_api_entry(c,210,7);
    D8Object*o=d8_object(c,ARG(0));
    HRESULT hr;DWORD error;SetLastError(xrt_get_last_error(c));hr=XM_CheckDeviceFormat(c,o->host,ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),ARG(6));error=GetLastError();
    xrt_event("d3d8_format","\"adapter\": %u, \"type\": %u, \"adapter_format\": %u, \"usage\": %u, \"resource\": %u, \"format\": %u, \"result\": %u, \"caller\": %u",
        ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),ARG(6),(uint32_t)hr,rd32(c->r[ESP]));xrt_set_last_error(c,error);RET_STD(7,hr);
}
#define D8_UNSUPPORTED(name,n) static void d8_##name(CPU*c) { \
    d8_api_entry(c,299,n); \
    D8Object*o=d8_object(c,ARG(0)); \
    xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"IDirect3D8::" #name " requires implementation (interface %08x, site %08x)",o->guest,c->pc); }
D8_UNSUPPORTED(RegisterSoftwareDevice,2)
D8_UNSUPPORTED(GetAdapterMonitor,2)
#include "hle_d3d8_device.inc"
#include "semantic_parent.inc"
static int d8_cleanup_must_retain(void) { return d8_native_failed || d8_creating || d8_rendering || d8_locks; }
static D8Object*d8_wrap(CPU*c,D8Interface*host) {
    unsigned i;D8Object*o=NULL;
    const char*names[]={"D8.QueryInterface","D8.AddRef","D8.Release","D8.RegisterSoftwareDevice","D8.GetAdapterCount",
        "D8.GetAdapterIdentifier","D8.GetAdapterModeCount","D8.EnumAdapterModes","D8.GetAdapterDisplayMode",
        "D8.CheckDeviceType","D8.CheckDeviceFormat","D8.CheckDeviceMultiSampleType","D8.CheckDepthStencilMatch",
        "D8.GetDeviceCaps","D8.GetAdapterMonitor","D8.CreateDevice"};
    if(!d8_vtable)d8_vtable=com_vtable(names,16);
    for(i=0;i<128;i++)if(!d8_objects[i].guest){o=&d8_objects[i];break;}
    if(!o){XM_Release(NULL,host);xrt_fatal(c,XRT_EXIT_SETUP,"Direct3D8 object table exhausted");}
    o->guest=xrt_rt_alloc(4,4);o->refs=1;o->host=host;wr32(o->guest,d8_vtable);xm_resource(c,1,o->guest,(unsigned)(o-d8_objects)+1,(uint64_t)(uintptr_t)o->host,o->refs,0,"created");return o;
}
static void hle_Direct3DCreate8(CPU*c) {
    D8Factory fn;D8Interface*host;D8Object*o=NULL;DWORD error;
    d8_api_entry(c,300,1); /* Known UINT API; backend supplies its actual pointer/NULL result. */
    if(!d8_library) {
        char dir[1024],path[1100],quoted[1200];DWORD n=GetEnvironmentVariableA("XRT_D3D8_DIR",dir,sizeof dir);
        if(!n || n>=sizeof dir || !((dir[0] && dir[1]==':' && (dir[2]=='\\' || dir[2]=='/'))))
            xrt_fatal(c,XRT_EXIT_SETUP,"Direct3DCreate8 requires explicit absolute XRT_D3D8_DIR (verified x64 DXVK D3D8/D3D9 pair)");
        if(GetModuleHandleW(L"d3d8.dll") || GetModuleHandleW(L"d3d9.dll"))
            xrt_fatal(c,XRT_EXIT_SETUP,"Direct3DCreate8: conflicting preloaded graphics library");
        snprintf(path,sizeof path,"%s/d3d9.dll",dir);
        d8_dependency=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
        if(!d8_dependency)xrt_fatal(c,XRT_EXIT_SETUP,"Direct3D8 host D3D9 dependency load failed: %lu",GetLastError());
        xrt_cleanup_register(d8_cleanup);
        snprintf(path,sizeof path,"%s/d3d8.dll",dir);
        d8_library=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
        if(!d8_library)xrt_fatal(c,XRT_EXIT_SETUP,"Direct3D8 host library load failed: %lu",GetLastError());
        if(!GetModuleFileNameA(d8_library,path,sizeof path))xrt_fatal(c,XRT_EXIT_SETUP,"cannot identify loaded D3D8 backend");
        xrt_event("d3d8_backend","\"module\": \"d3d8.dll\", \"path\": %s",xrt_jstr(quoted,sizeof quoted,path));
        if(!GetModuleFileNameA(d8_dependency,path,sizeof path))xrt_fatal(c,XRT_EXIT_SETUP,"cannot identify loaded D3D9 dependency");
        xrt_event("d3d8_backend","\"module\": \"d3d9.dll\", \"path\": %s",xrt_jstr(quoted,sizeof quoted,path));
    }
    fn=(D8Factory)GetProcAddress(d8_library,"Direct3DCreate8");
    if(!fn)xrt_fatal(c,XRT_EXIT_SETUP,"host Direct3DCreate8 export missing");
    SetLastError(xrt_get_last_error(c));xm_native(c,XM_BEGIN,"D3D8.Direct3DCreate8",0,0);{XmValue v={XM_U32,4,ARG(0)};xm_values(c,"factory.sdk",1,&v);}host=fn(ARG(0));xm_native(c,XM_END,"D3D8.Direct3DCreate8",0,(uint64_t)(uintptr_t)host);error=GetLastError();if(host)o=d8_wrap(c,host);xrt_set_last_error(c,error);
    xrt_event("d3d8_create","\"version\": %u, \"object\": %u, \"non_null\": %s, \"caller\": %u",
        ARG(0),o?o->guest:0,o?"true":"false",rd32(c->r[ESP]));RET_STD(1,o?o->guest:0);
}
#define XRT_D3D8_BINDINGS \
    XRT_D3D8_DEVICE_BINDINGS \
    {"xrt.com","D8R.Unsupported",d8_resource_Unsupported}, \
    {"xrt.com","D8R.QueryInterface",d8_resource_QueryInterface}, \
    {"xrt.com","D8R.AddRef",d8_resource_AddRef}, \
    {"xrt.com","D8R.Release",d8_resource_Release}, \
    {"xrt.com","D8R.GetDevice",d8_resource_GetDevice}, \
    {"xrt.com","D8R.GetContainer",d8_resource_GetContainer}, \
    {"xrt.com","D8R.GetDesc",d8_resource_GetDesc}, \
    {"xrt.com","D8R.GetLevelDesc",d8_resource_GetLevelDesc}, \
    {"xrt.com","D8R.GetSurfaceLevel",d8_resource_GetSurfaceLevel}, \
    {"xrt.com","D8R.GetCubeMapSurface",d8_resource_GetCubeMapSurface}, \
    {"xrt.com","D8R.LockRect",d8_resource_LockRect}, \
    {"xrt.com","D8R.UnlockRect",d8_resource_UnlockRect}, \
    {"xrt.com","D8R.Lock",d8_resource_Lock}, \
    {"xrt.com","D8R.Unlock",d8_resource_Unlock}, \
    {"xrt.com","D8R.SetPriority",d8_resource_SetPriority}, \
    {"xrt.com","D8R.GetPriority",d8_resource_GetPriority}, \
    {"xrt.com","D8R.PreLoad",d8_resource_PreLoad}, \
    {"xrt.com","D8R.GetType",d8_resource_GetType}, \
    {"xrt.com","D8R.SetLOD",d8_resource_SetLOD}, \
    {"xrt.com","D8R.GetLOD",d8_resource_GetLOD}, \
    {"xrt.com","D8R.GetLevelCount",d8_resource_GetLevelCount}, \
    {"xrt.com","D8R.AddDirtyRect",d8_resource_AddDirtyRect}, \
    {"d3d8.dll","Direct3DCreate8",hle_Direct3DCreate8}, \
    {"xrt.com","D8.QueryInterface",d8_QueryInterface}, \
    {"xrt.com","D8.AddRef",d8_AddRef}, \
    {"xrt.com","D8.Release",d8_Release}, \
    {"xrt.com","D8.RegisterSoftwareDevice",d8_RegisterSoftwareDevice}, \
    {"xrt.com","D8.GetAdapterCount",d8_GetAdapterCount}, \
    {"xrt.com","D8.GetAdapterIdentifier",d8_GetAdapterIdentifier}, \
    {"xrt.com","D8.GetAdapterModeCount",d8_GetAdapterModeCount}, \
    {"xrt.com","D8.EnumAdapterModes",d8_EnumAdapterModes}, \
    {"xrt.com","D8.GetAdapterDisplayMode",d8_GetAdapterDisplayMode}, \
    {"xrt.com","D8.CheckDeviceType",d8_CheckDeviceType}, \
    {"xrt.com","D8.CheckDeviceFormat",d8_CheckDeviceFormat}, \
    {"xrt.com","D8.CheckDeviceMultiSampleType",d8_CheckDeviceMultiSampleType}, \
    {"xrt.com","D8.CheckDepthStencilMatch",d8_CheckDepthStencilMatch}, \
    {"xrt.com","D8.GetDeviceCaps",d8_GetDeviceCaps}, \
    {"xrt.com","D8.GetAdapterMonitor",d8_GetAdapterMonitor}, \
    {"xrt.com","D8.CreateDevice",d8_CreateDevice},

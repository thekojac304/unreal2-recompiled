/* INCLUDED ONLY by a generated copy of hle_misc.c in the fixture build.
 * Production D8.CreateDevice is still the unchanged fatal guard.
 * New entry point: fixture.dll!FixtureCreateDevice; never a game import. */
typedef struct FD {uint32_t guest,refs;IUnknown*host;D8Object*parent;D8Interface*parent_host;} FD;
static FD fixture_devices[32];static uint32_t fixture_vtable,fixture_window_token;static HWND fixture_window;
static const GUID fixture_device_iid={0x7385e5df,0x8fe8,0x41d5,{0x86,0xb6,0xd7,0xb4,0x85,0x47,0xb6,0xcf}};
static FD*fixture_object(CPU*c,uint32_t guest){unsigned i;for(i=0;i<32;i++)if(fixture_devices[i].guest==guest&&fixture_devices[i].refs)return &fixture_devices[i];xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fixture device stale or unknown %08x",guest);}
static void fixture_memory(CPU*c,uint32_t p,uint32_t size){
    uint64_t at=p,end=(uint64_t)p+size;if(!p||end>0x100000000ull||!xrt_is_committed(p,size))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"fixture invalid writable guest range %08x size %u",p,size);
    while(at<end){MEMORY_BASIC_INFORMATION m;DWORD prot;if(!VirtualQuery(G2H((uint32_t)at),&m,sizeof m))xrt_fatal(c,76,"fixture range query failed");prot=m.Protect&255;
    if(m.State!=MEM_COMMIT||(m.Protect&PAGE_GUARD)||(prot!=PAGE_READWRITE&&prot!=PAGE_WRITECOPY&&prot!=PAGE_EXECUTE_READWRITE&&prot!=PAGE_EXECUTE_WRITECOPY))xrt_fatal(c,76,"fixture invalid writable guest range %08x size %u",p,size);
    at=(uint64_t)((BYTE*)m.BaseAddress-xrt_g)+m.RegionSize;}
}
static void fixture_cleanup(void){unsigned i,n=0;for(i=0;i<32;i++)while(fixture_devices[i].refs){fixture_devices[i].host->lpVtbl->Release(fixture_devices[i].host);fixture_devices[i].refs--;n++;}if(fixture_window){DestroyWindow(fixture_window);xrt_handle_free(fixture_window_token);fixture_window=NULL;UnregisterClassW(L"XRT_FixtureOnlyDevice",GetModuleHandleW(NULL));}xrt_event("fixture_device_cleanup","\"references_released\":%u",n);}
static void fixture_open(CPU*c){WNDCLASSW wc;memset(&wc,0,sizeof wc);wc.lpfnWndProc=DefWindowProcW;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XRT_FixtureOnlyDevice";RegisterClassW(&wc);fixture_window=CreateWindowExW(0,wc.lpszClassName,L"Fixture only translated device",WS_OVERLAPPEDWINDOW,0,0,1560,1000,NULL,NULL,wc.hInstance,NULL);if(!fixture_window)xrt_fatal(c,78,"fixture owned window failed");fixture_window_token=xrt_handle_new(XH_WINDOW,fixture_window);xrt_cleanup_register(fixture_cleanup);RET_STD(0,fixture_window_token);}
static void fixture_qi(CPU*c){FD*o=fixture_object(c,ARG(0));GUID iid;void*q=NULL;HRESULT hr;DWORD error;fixture_memory(c,ARG(1),16);fixture_memory(c,ARG(2),4);memcpy(&iid,G2H(ARG(1)),16);SetLastError(xrt_get_last_error(c));hr=o->host->lpVtbl->QueryInterface(o->host,&iid,&q);error=GetLastError();if(SUCCEEDED(hr)){if(q!=o->host||(memcmp(&iid,&fixture_device_iid,16)&&memcmp(&iid,&com_iunknown,16)))xrt_fatal(c,76,"fixture unknown successful QI");o->refs++;}wr32(ARG(2),SUCCEEDED(hr)?o->guest:0);xrt_set_last_error(c,error);RET_STD(3,hr);}
static void fixture_add(CPU*c){FD*o=fixture_object(c,ARG(0));ULONG n=o->host->lpVtbl->AddRef(o->host);o->refs++;RET_STD(1,n);}
static void fixture_release(CPU*c){FD*o=fixture_object(c,ARG(0));ULONG n=o->host->lpVtbl->Release(o->host);if(!--o->refs)o->host=NULL;xrt_event("fixture_device_release","\"object\":%u,\"remaining_guest_refs\":%u,\"native_count\":%lu",o->guest,o->refs,n);RET_STD(1,n);}
static void fixture_parent(CPU*c){FD*o=fixture_object(c,ARG(0));D8Interface*q=NULL;HRESULT hr;typedef HRESULT(WINAPI*Fn)(IUnknown*,D8Interface**);fixture_memory(c,ARG(1),4);hr=((Fn)(*(void***)o->host)[6])(o->host,&q);if(SUCCEEDED(hr)){if(q!=o->parent_host)xrt_fatal(c,76,"fixture parent identity differs");o->parent->host=q;o->parent->refs++;}wr32(ARG(1),SUCCEEDED(hr)?o->parent->guest:0);RET_STD(2,hr);}
static void fixture_creation(CPU*c){FD*o=fixture_object(c,ARG(0));struct{UINT adapter,type;HWND focus;DWORD flags;}cp;HRESULT hr;typedef HRESULT(WINAPI*Fn)(IUnknown*,void*);fixture_memory(c,ARG(1),16);hr=((Fn)(*(void***)o->host)[9])(o->host,&cp);if(SUCCEEDED(hr)){if(cp.focus!=fixture_window)xrt_fatal(c,76,"fixture creation focus mismatch");wr32(ARG(1),cp.adapter);wr32(ARG(1)+4,cp.type);wr32(ARG(1)+8,fixture_window_token);wr32(ARG(1)+12,cp.flags);}RET_STD(2,hr);}
#include "fixture_slots.inc"
static void fixture_create(CPU*c){
    D8Object*p=d8_object(c,ARG(0));uint32_t focus=ARG(3),pp=ARG(5),out=ARG(6),esp=c->r[ESP],ret=rd32(esp),i,slot;D8Present native;D8Device*host=NULL;HRESULT hr;DWORD error;FD*o=NULL;HWND w;
    fixture_memory(c,pp,52);fixture_memory(c,out,4);
    w=(HWND)xrt_handle_get(focus,XH_WINDOW);if(!w||w!=fixture_window||GetWindowThreadProcessId(w,NULL)!=GetCurrentThreadId())xrt_fatal(c,76,"fixture window mapping or thread mismatch");
    native.width=rd32(pp);native.height=rd32(pp+4);native.format=rd32(pp+8);native.count=rd32(pp+12);native.multisample=rd32(pp+16);native.swap=rd32(pp+20);
    native.window=(HWND)xrt_handle_get(rd32(pp+24),XH_WINDOW);if(native.window!=w)xrt_fatal(c,76,"fixture device window mapping mismatch");
    native.windowed=rd32(pp+28);native.depth=rd32(pp+32);native.depthformat=rd32(pp+36);native.flags=rd32(pp+40);native.refresh=rd32(pp+44);native.interval=rd32(pp+48);
    SetLastError(xrt_get_last_error(c));hr=p->host->vt->CreateDevice(p->host,ARG(1),ARG(2),w,ARG(4),&native,&host);error=GetLastError();
    if(SUCCEEDED(hr)){for(slot=0;slot<32;slot++)if(!fixture_devices[slot].guest){o=&fixture_devices[slot];break;}if(!o){((IUnknown*)host)->lpVtbl->Release((IUnknown*)host);xrt_fatal(c,78,"fixture device table exhausted");}
    if(!fixture_vtable){fixture_vtable=xrt_rt_alloc(97*4,4);for(i=0;i<97;i++)wr32(fixture_vtable+4*i,xrt_hle_proc("fixture.dll",fixture_slot_names[i]));}
    o->guest=xrt_rt_alloc(4,4);o->refs=1;o->host=(IUnknown*)host;o->parent=p;o->parent_host=p->host;wr32(o->guest,fixture_vtable);}
    /* Native HWNDs never escape; preserve original guest token after identity check. */
    if(native.window!=w)xrt_fatal(c,76,"fixture unexpected native presentation window mutation");
    wr32(pp,native.width);wr32(pp+4,native.height);wr32(pp+8,native.format);wr32(pp+12,native.count);wr32(pp+16,native.multisample);wr32(pp+20,native.swap);
    wr32(pp+24,focus);wr32(pp+28,native.windowed);wr32(pp+32,native.depth);wr32(pp+36,native.depthformat);wr32(pp+40,native.flags);wr32(pp+44,native.refresh);wr32(pp+48,native.interval);wr32(out,o?o->guest:0);
    xrt_set_last_error(c,error);RET_STD(7,hr);
    xrt_event("fixture_create_return","\"result\":%lu,\"last_error\":%lu,\"device\":%u,\"host_non_null\":%s,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u,\"typed_slots\":97",(DWORD)hr,error,o?o->guest:0,host?"true":"false",esp,c->r[ESP],ret,c->rv);
    if(o)for(i=0;i<97;i++)if(rd32(fixture_vtable+4*i)!=xrt_hle_proc("fixture.dll",fixture_slot_names[i]))xrt_fatal(c,78,"fixture device slot audit failed");
    if(o)xrt_event("fixture_device_audit","\"object\":%u,\"vtable\":%u,\"typed_slots\":97,\"passed\":true,\"owned_window_mapped\":true,\"same_thread\":true");
}

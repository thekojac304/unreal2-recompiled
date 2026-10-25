/* One measured windowed CreateDevice; bounded target Clear and NULL Present. */
#include "d3d8_device_abi.h"
#include <xmmintrin.h>
typedef struct D8DeviceObject {
    uint32_t guest,refs,focus,window,presents;
    D8Device* host;
    D8Object* parent;
} D8DeviceObject;
static D8DeviceObject d8_device;
static volatile LONG d8_attempted;
static int d8_native_failed,d8_creating,d8_rendering;
static uint32_t d8_device_vtable;
static const GUID d8_device_iid={0x7385e5df,0x8fe8,0x41d5,{0x86,0xb6,0xd7,0xb4,0x85,0x47,0xb6,0xcf}};

/* A writable Windows page is also readable. Check the entire range, including
 * the last scalar/page; com_memory alone checks commitment, not protection. */
static void d8_device_memory(CPU*c,uint32_t p,uint32_t size,int writable) {
    uint64_t at=p,end=(uint64_t)p+size;
    if(!p || end>0x100000000ull || !xrt_is_committed(p,size))
        xrt_fatal(c,76,"D3D8 device: invalid %s guest range %08x size %u",writable?"writable":"readable",p,size);
    while(at<end) {
        MEMORY_BASIC_INFORMATION m;DWORD prot;int ok;
        if(!VirtualQuery(G2H((uint32_t)at),&m,sizeof m))xrt_fatal(c,76,"D3D8 device: guest range query failed");
        prot=m.Protect&255;
        ok=prot==PAGE_READWRITE || prot==PAGE_WRITECOPY || prot==PAGE_EXECUTE_READWRITE || prot==PAGE_EXECUTE_WRITECOPY;
        if(!writable)ok=ok || prot==PAGE_READONLY || prot==PAGE_EXECUTE_READ;
        if(m.State!=MEM_COMMIT || (m.Protect&PAGE_GUARD) || !ok)
            xrt_fatal(c,76,"D3D8 device: invalid %s guest range %08x size %u",writable?"writable":"readable",p,size);
        at=(uint64_t)((BYTE*)m.BaseAddress-xrt_g)+m.RegionSize;
    }
}
static D8DeviceObject* d8_device_object(CPU*c,uint32_t p) {
    if(p && p==d8_device.guest && d8_device.refs && d8_device.host)return &d8_device;
    xrt_fatal(c,76,"Direct3DDevice8: stale or unknown guest COM interface %08x",p);
}
static void d8_device_dead(D8DeviceObject*o) {
    o->host=NULL;
    if(!--o->parent->children && !o->parent->refs)o->parent->host=NULL;
    xrt_gui_window_unpin(o->focus);xrt_gui_window_unpin(o->window);
}
static void d8_device_cleanup(void) {
    unsigned n=0;ULONG count=0;CPU*previous;
    previous=xrt_gui_callback_enter(xrt_cur?&xrt_cur->cpu:NULL);
    while(d8_device.refs) {
        count=d8_device.host->vt->Release(d8_device.host);d8_device.refs--;n++;
        if(!d8_device.refs)d8_device_dead(&d8_device);
    }
    xrt_gui_callback_leave(previous);
    xrt_event("d3d8_device_cleanup","\"references_released\":%u,\"final_native_count\":%lu",n,count);
}
static void d8_device_QueryInterface(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));GUID iid;void*q=NULL;HRESULT hr;DWORD error;uint32_t out=ARG(2);
    d8_device_memory(c,ARG(1),16,0);if(out)d8_device_memory(c,out,4,1);
    memcpy(&iid,G2H(ARG(1)),16);SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->QueryInterface(o->host,&iid,out?&q:NULL);error=GetLastError();
    if(SUCCEEDED(hr)) {
        if(q!=o->host || (memcmp(&iid,&com_iunknown,16) && memcmp(&iid,&d8_device_iid,16))) {
            /* QI may have acquired an unmodelled reference. Keep its code alive
             * until process teardown rather than unloading beneath that object. */
            d8_native_failed=1;
            xrt_fatal(c,76,"Direct3DDevice8: unmodelled successful QI identity");
        }
        o->refs++;
    } else if(q) {d8_native_failed=1;xrt_fatal(c,76,"Direct3DDevice8: unexpected failed QI output");}
    if(out)wr32(out,SUCCEEDED(hr)?o->guest:0);
    xrt_set_last_error(c,error);RET_STD(3,hr);
}
static void d8_device_AddRef(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));ULONG n;DWORD error;
    SetLastError(xrt_get_last_error(c));n=o->host->vt->AddRef(o->host);error=GetLastError();o->refs++;
    xrt_set_last_error(c,error);RET_STD(1,n);
}
static void d8_device_Release(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));ULONG n;DWORD error;CPU*previous;
    if(d8_rendering)xrt_fatal(c,76,"Direct3DDevice8: Release during native rendering unsupported");
    previous=xrt_gui_callback_enter(c);
    SetLastError(xrt_get_last_error(c));n=o->host->vt->Release(o->host);error=GetLastError();
    xrt_gui_callback_leave(previous);
    if(!--o->refs)d8_device_dead(o);
    xrt_event("d3d8_device_release","\"object\":%u,\"guest_refs\":%u,\"native_count\":%lu",o->guest,o->refs,n);
    xrt_set_last_error(c,error);RET_STD(1,n);
}
static void d8_device_GetDirect3D(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));D8Interface*q=NULL;HRESULT hr;DWORD error;
    d8_device_memory(c,ARG(1),4,1);SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->GetDirect3D(o->host,&q);error=GetLastError();
    if(SUCCEEDED(hr)) {
        if(q!=o->parent->host) {d8_native_failed=1;xrt_fatal(c,76,"Direct3DDevice8: parent identity changed");}
        o->parent->refs++;
    } else if(q) {d8_native_failed=1;xrt_fatal(c,76,"Direct3DDevice8: unexpected failed parent output");}
    wr32(ARG(1),SUCCEEDED(hr)?o->parent->guest:0);xrt_set_last_error(c,error);RET_STD(2,hr);
}
static void d8_device_GetCreationParameters(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));D8Creation cp;HRESULT hr;DWORD error;
    d8_device_memory(c,ARG(1),16,1);memset(&cp,0,sizeof cp);
    SetLastError(xrt_get_last_error(c));hr=o->host->vt->GetCreationParameters(o->host,&cp);error=GetLastError();
    if(SUCCEEDED(hr)) {
        uint32_t focus=xrt_gui_window_identity(c,cp.focus);
        wr32(ARG(1),cp.adapter);wr32(ARG(1)+4,cp.type);wr32(ARG(1)+8,focus);wr32(ARG(1)+12,cp.flags);
    }
    xrt_set_last_error(c,error);RET_STD(2,hr);
}
/* HWND pins prevent guest destruction; same-thread resolution is rechecked on
 * every call. While inside DXVK, nested rendering and final Release are refused.
 * Fatal callbacks retain the backend rather than unloading an active frame. */
static void d8_render_ready(CPU*c,D8DeviceObject*o) {
    if(d8_rendering)xrt_fatal(c,76,"Direct3DDevice8: reentrant rendering unsupported");
    if(!o->focus || !o->window || o->focus!=o->window)
        xrt_fatal(c,76,"Direct3DDevice8: unsupported rendering window tuple (native call refused)");
    xrt_gui_device_window(c,o->focus);xrt_gui_device_window(c,o->window);
}
static void d8_device_Clear(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));
    uint32_t count=ARG(1),rects=ARG(2),flags=ARG(3),color=ARG(4),zbits=ARG(5),stencil=ARG(6);
    uint32_t esp=c->r[ESP],ret=rd32(esp);D8Rect rect;const D8Rect*nrect=NULL;float z;
    HRESULT hr;DWORD error,before,after;CPU*previous;
    if(count>1 || (count && !rects) || flags!=1 || zbits!=0 || stencil!=0)
        xrt_fatal(c,76,"IDirect3DDevice8::Clear: unsupported argument combination (native call refused)");
    if(rects) {
        d8_device_memory(c,rects,16,0);memcpy(&rect,G2H(rects),16);nrect=&rect;
        if(count && (rect.left<0 || rect.top<0 || rect.right<=rect.left || rect.bottom<=rect.top || rect.right>1540 || rect.bottom>945))
            xrt_fatal(c,76,"IDirect3DDevice8::Clear: unsupported rectangle bounds (native call refused)");
    }
    memcpy(&z,&zbits,4);d8_render_ready(c,o);
    xrt_event("d3d8_render_call","\"method\":\"Clear\",\"slot\":36,\"this\":%u,\"count\":%u,\"rects\":%u,\"flags\":%u,\"color\":%u,\"z_bits\":%u,\"stencil\":%u,\"esp\":%u,\"return\":%u",o->guest,count,rects,flags,color,zbits,stencil,esp,ret);
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));before=_mm_getcsr();
    hr=o->host->vt->Clear(o->host,count,nrect,flags,color,z,stencil);error=GetLastError();after=_mm_getcsr();
    d8_rendering=0;xrt_gui_callback_leave(previous);
    xrt_set_last_error(c,error);RET_STD(7,hr);
    xrt_event("d3d8_render_return","\"method\":\"Clear\",\"this\":%u,\"result\":%lu,\"last_error\":%lu,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u,\"mxcsr_before\":%lu,\"mxcsr_after\":%lu",o->guest,(DWORD)hr,error,esp,c->r[ESP],ret,c->rv,before,after);
}
static void d8_device_Present(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));uint32_t esp=c->r[ESP],ret=rd32(esp),fsw=c->fsw;
    HRESULT hr;DWORD error,before,after;CPU*previous;
    if(ARG(1) || ARG(2) || ARG(3) || ARG(4))
        xrt_fatal(c,76,"IDirect3DDevice8::Present: only four NULL arguments measured (native call refused)");
    d8_render_ready(c,o);
    xrt_event("d3d8_render_call","\"method\":\"Present\",\"slot\":15,\"this\":%u,\"source\":0,\"destination\":0,\"override\":0,\"dirty\":0,\"esp\":%u,\"return\":%u",o->guest,esp,ret);
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));before=_mm_getcsr();
    hr=o->host->vt->Present(o->host,NULL,NULL,NULL,NULL);error=GetLastError();after=_mm_getcsr();
    d8_rendering=0;xrt_gui_callback_leave(previous);
    /* Pinned DXVK x86, live window, CW=027f: first successful Present sets
     * sticky x87 PE while retaining TOP, values and control. x64 uses SSE for
     * that calculation, so reproduce the independently measured guest effect.
     * Subsequent Presents leave the guest status alone, including fnclex. */
    if(hr==S_OK && !o->presents)c->fsw|=0x20;
    if(SUCCEEDED(hr))o->presents++;
    xrt_set_last_error(c,error);RET_STD(5,hr);
    xrt_event("d3d8_render_return","\"method\":\"Present\",\"this\":%u,\"result\":%lu,\"last_error\":%lu,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u,\"mxcsr_before\":%lu,\"mxcsr_after\":%lu,\"guest_fsw_before\":%u,\"guest_fsw_after\":%u",o->guest,(DWORD)hr,error,esp,c->r[ESP],ret,c->rv,before,after,fsw,c->fsw);
}
/* Exact genuine scalar tuples only. Native x86/x64 and translated fixtures
 * measure HRESULT, last-error, readback, ABI/FPU, identity and ownership. */
static void d8_device_SetRenderState(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));
    uint32_t state=ARG(1),value=ARG(2),esp=c->r[ESP],ret=rd32(esp);
    HRESULT hr;DWORD error,before,after;CPU*previous;
    if(!(state==7 && value==1))
        xrt_fatal(c,76,"IDirect3DDevice8::SetRenderState: unsupported state=%u value=%u (native call refused)",state,value);
    d8_render_ready(c,o);
    xrt_event("d3d8_state_call","\"method\":\"SetRenderState\",\"slot\":50,\"this\":%u,\"state\":%u,\"value\":%u,\"esp\":%u,\"return\":%u",o->guest,state,value,esp,ret);
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));before=_mm_getcsr();
    hr=o->host->vt->SetRenderState(o->host,state,value);error=GetLastError();after=_mm_getcsr();
    d8_rendering=0;xrt_gui_callback_leave(previous);
    xrt_set_last_error(c,error);RET_STD(3,hr);
    xrt_event("d3d8_state_return","\"method\":\"SetRenderState\",\"this\":%u,\"result\":%lu,\"last_error\":%lu,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u,\"mxcsr_before\":%lu,\"mxcsr_after\":%lu",o->guest,(DWORD)hr,error,esp,c->r[ESP],ret,c->rv,before,after);
}
#include "d3d8_device_slots.inc"
static void d8_CreateDevice(CPU*c) {
    D8Object*p=d8_object(c,ARG(0));D8DeviceObject*o=&d8_device;
    uint32_t adapter=ARG(1),type=ARG(2),focus=ARG(3),flags=ARG(4),pp=ARG(5),out=ARG(6);
    uint32_t esp=c->r[ESP],ret=rd32(esp),window;D8Present n;D8Device*host=NULL;D8Interface*parent=p->host;
    HRESULT hr;DWORD error,mxcsr_before,mxcsr_after;CPU*previous;unsigned i;
    d8_device_memory(c,pp,52,1);d8_device_memory(c,out,4,1);
    /* Overlap cannot represent two independently mutable outputs. */
    if((uint64_t)out<(uint64_t)pp+52 && (uint64_t)pp<(uint64_t)out+4)
        xrt_fatal(c,76,"IDirect3D8::CreateDevice: overlapping presentation/output unsupported");
    if(adapter!=0 || type!=1 || flags!=0x42 || rd32(pp)!=1540 || rd32(pp+4)!=945 || rd32(pp+8)!=22 ||
       rd32(pp+12)!=1 || rd32(pp+16)!=0 || rd32(pp+20)!=1 || rd32(pp+28)!=1 || rd32(pp+32)!=1 ||
       rd32(pp+36)!=77 || rd32(pp+40)!=1 || rd32(pp+44)!=0 || rd32(pp+48)!=0)
        xrt_fatal(c,76,"IDirect3D8::CreateDevice: unsupported captured tuple (native call refused)");
    window=rd32(pp+24);memset(&n,0,sizeof n);
    n.width=rd32(pp);n.height=rd32(pp+4);n.format=rd32(pp+8);n.count=rd32(pp+12);n.multisample=rd32(pp+16);n.swap=rd32(pp+20);
    n.window=xrt_gui_device_window(c,window);n.windowed=rd32(pp+28);n.depth=rd32(pp+32);n.depthformat=rd32(pp+36);
    n.flags=rd32(pp+40);n.refresh=rd32(pp+44);n.interval=rd32(pp+48);
    {
        HWND focus_host=xrt_gui_device_window(c,focus);
        if(InterlockedCompareExchange(&d8_attempted,1,0))
            xrt_fatal(c,76,"IDirect3D8::CreateDevice: one native attempt per process; retry refused");
        /* Allocate all guest state before invoking the host. The reserved object
         * has zero refs and is unreachable through the guest output in callbacks. */
        if(!d8_device_vtable)d8_device_vtable=com_vtable(d8_device_slot_names,97);
        o->guest=xrt_rt_alloc(4,4);wr32(o->guest,d8_device_vtable);
        o->parent=p;o->focus=focus;o->window=window;
        xrt_gui_window_pin(c,focus);xrt_gui_window_pin(c,window);
        wr32(out,0);d8_creating=1;p->pending++;
        parent->vt->AddRef(parent); /* private guard against a parent-first callback */
        xrt_event("d3d8_device_call","\"this\":%u,\"adapter\":%u,\"type\":%u,\"focus\":%u,\"window\":%u,\"flags\":%u,\"parameters\":%u,\"output\":%u,\"esp\":%u,\"return\":%u,\"attempt\":1",p->guest,adapter,type,focus,window,flags,pp,out,esp,ret);
        previous=xrt_gui_callback_enter(c);SetLastError(xrt_get_last_error(c));
        mxcsr_before=_mm_getcsr();
        hr=parent->vt->CreateDevice(parent,adapter,type,focus_host,flags,&n,&host);error=GetLastError();mxcsr_after=_mm_getcsr();
        xrt_event("d3d8_device_mxcsr","\"before\":%lu,\"after\":%lu",mxcsr_before,mxcsr_after);
        xrt_gui_callback_leave(previous);
    }
    /* Mark failed initialization before any operation that can stop execution:
     * cleanup must retain both modules and all possibly live backend resources. */
    d8_native_failed=FAILED(hr) || !host;
    if(!d8_native_failed) { o->host=host;o->refs=1;p->children++; }
    parent->vt->Release(parent);p->pending--;d8_creating=0;
    if(!p->refs && !p->children && !p->pending)p->host=NULL;
    d8_device_memory(c,pp,52,1);d8_device_memory(c,out,4,1);
    window=xrt_gui_window_identity(c,n.window);
    wr32(pp,n.width);wr32(pp+4,n.height);wr32(pp+8,n.format);wr32(pp+12,n.count);wr32(pp+16,n.multisample);wr32(pp+20,n.swap);
    wr32(pp+24,window);wr32(pp+28,n.windowed);wr32(pp+32,n.depth);wr32(pp+36,n.depthformat);wr32(pp+40,n.flags);wr32(pp+44,n.refresh);wr32(pp+48,n.interval);
    wr32(out,o->refs?o->guest:0);xrt_set_last_error(c,error);RET_STD(7,hr);
    xrt_event("d3d8_device_return","\"this\":%u,\"result\":%lu,\"last_error\":%lu,\"device\":%u,\"host_non_null\":%s,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",p->guest,(DWORD)hr,error,o->refs?o->guest:0,host?"true":"false",esp,c->r[ESP],ret,c->rv);
    d8_words("create_device_parameters",G2H(pp),13);
    if(d8_native_failed)
        xrt_fatal(c,76,"IDirect3D8::CreateDevice: native initialization failed hr=%08lx last-error=%lu host-output=%s; process teardown required, no retry",(DWORD)hr,error,host?"non-null":"NULL");
    for(i=0;i<97;i++)if(!rd32(d8_device_vtable+i*4) || rd32(d8_device_vtable+i*4)!=xrt_hle_proc("xrt.com",d8_device_slot_names[i]))
        xrt_fatal(c,77,"Direct3DDevice8: guest vtable audit failed at %u",i);
    xrt_event("d3d8_device_audit","\"object\":%u,\"vtable\":%u,\"typed_slots\":97,\"passed\":true",o->guest,d8_device_vtable);
}

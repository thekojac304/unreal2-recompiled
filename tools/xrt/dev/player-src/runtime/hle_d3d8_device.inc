#include "monitor_com.inc"
/* One measured windowed CreateDevice; bounded target Clear and NULL Present. */
#include "d3d8_device_abi.h"
#include <xmmintrin.h>
typedef struct D8DeviceObject {
    uint32_t guest,refs,focus,window,presents,children;
    D8Device* host;
    D8Object* parent;
    D8Caps caps;int caps_valid;
    unsigned width,height,depth,depthformat,behavior;
} D8DeviceObject;
static D8DeviceObject d8_device;
static volatile LONG d8_attempted;
static int d8_native_failed,d8_creating,d8_rendering;
static unsigned d8_locks;
static uint32_t d8_device_vtable;
static const GUID d8_device_iid={0x7385e5df,0x8fe8,0x41d5,{0x86,0xb6,0xd7,0xb4,0x85,0x47,0xb6,0xcf}};

#include "semantic_evidence.inc"

/* A writable Windows page is also readable. Check the entire range, including
 * the last scalar/page; com_memory alone checks commitment, not protection. */
/* Hints: the last eight whole regions verified committed, writable and not guard pages (valid for both
 * modes) until an overlapping guest range is decommitted (xrt_mem_hint_valid). */
static struct {uint64_t lo,hi;long gen;} d8_memory_hint[8];static unsigned d8_memory_next;
/* A staging block the HLE has just committed (xrt_virtual_alloc / xrt_staging_take) is committed, read-write and not a
 * guard page: hint it in both tables instead of querying it (the answer VirtualQuery would give). */
/* Round 4: staging blocks go to two slots of their own, so a frame's buffer Locks no longer evict the guest stack/heap
 * argument hints (each eviction cost two VirtualQuery calls at the next device call). */
static struct {uint64_t lo,hi;long gen;} d8_staging_slot[2];static unsigned d8_staging_next;
static void d8_staging_hint(uint32_t p,uint32_t size) {
    uint64_t lo=p&~0xFFFull,hi=((uint64_t)p+size+0xFFF)&~0xFFFull;
    xrt_hint_committed(p,size);
    d8_staging_slot[d8_staging_next].lo=lo;d8_staging_slot[d8_staging_next].hi=hi;d8_staging_slot[d8_staging_next].gen=xrt_mem_generation;
    d8_staging_next=(d8_staging_next+1)&1;
}
static void d8_device_memory(CPU*c,uint32_t p,uint32_t size,int writable) {
    uint64_t at=p,end=(uint64_t)p+size;unsigned h;long gen=xrt_mem_generation;
    if(!p || end>0x100000000ull)
        xrt_fatal(c,76,"D3D8 device: invalid %s guest range %08x size %u",writable?"writable":"readable",p,size);
    for(h=0;h<8;h++)
        if(at>=d8_memory_hint[h].lo && end<=d8_memory_hint[h].hi &&
           xrt_mem_hint_valid(d8_memory_hint[h].lo,d8_memory_hint[h].hi,&d8_memory_hint[h].gen))return;
    for(h=0;h<2;h++)
        if(at>=d8_staging_slot[h].lo && end<=d8_staging_slot[h].hi &&
           xrt_mem_hint_valid(d8_staging_slot[h].lo,d8_staging_slot[h].hi,&d8_staging_slot[h].gen))return;
    if(!xrt_is_committed(p,size))
        xrt_fatal(c,76,"D3D8 device: invalid %s guest range %08x size %u",writable?"writable":"readable",p,size);
    while(at<end) {
        MEMORY_BASIC_INFORMATION m;DWORD prot;int ok,rw;uint64_t lo;
        if(!VirtualQuery(G2H((uint32_t)at),&m,sizeof m))xrt_fatal(c,76,"D3D8 device: guest range query failed");
        prot=m.Protect&255;
        ok=rw=prot==PAGE_READWRITE || prot==PAGE_WRITECOPY || prot==PAGE_EXECUTE_READWRITE || prot==PAGE_EXECUTE_WRITECOPY;
        if(!writable)ok=ok || prot==PAGE_READONLY || prot==PAGE_EXECUTE_READ;
        if(m.State!=MEM_COMMIT || (m.Protect&PAGE_GUARD) || !ok)
            xrt_fatal(c,76,"D3D8 device: invalid %s guest range %08x size %u",writable?"writable":"readable",p,size);
        lo=(uint64_t)((BYTE*)m.BaseAddress-xrt_g);
        at=lo+m.RegionSize;
        if(rw && p>=lo && end<=at){d8_memory_hint[d8_memory_next].lo=lo;d8_memory_hint[d8_memory_next].hi=at;
            d8_memory_hint[d8_memory_next].gen=gen;d8_memory_next=(d8_memory_next+1)&7;}
    }
}
static D8DeviceObject* d8_device_object(CPU*c,uint32_t p) {
    if(p && p==d8_device.guest && d8_device.refs && d8_device.host){xm_resource(c,2,p,1,(uint64_t)(uintptr_t)d8_device.host,d8_device.refs,0,"receiver");return &d8_device;}
    xrt_fatal(c,76,"Direct3DDevice8: stale or unknown guest COM interface %08x",p);
}
static void d8_declaration_device_dead(void);
static void d8_layout_requirements(CPU*,D8DeviceObject*,unsigned,unsigned[16]);
static void d8_resource_device_dead(void);
static void d8_resource_up_reset(int);
#include "d3d8_borderless.inc"
static void d8_device_dead(D8DeviceObject*o) {
    d8_bl_end("device destroyed",NULL,0);   /* the runtime's own render target/depth surface held the native device */
    d8_declaration_device_dead();d8_resource_device_dead();
    o->host=NULL;xm_resource(NULL,2,o->guest,1,0,o->refs,o->children,"destroyed");
    if(!--o->parent->children && !o->parent->refs)o->parent->host=NULL;xm_resource(NULL,1,o->parent->guest,0,(uint64_t)(uintptr_t)o->parent->host,o->parent->refs,o->parent->children,"child-destroyed");
    xrt_gui_window_unpin(o->focus);xrt_gui_window_unpin(o->window);
}
static void d8_resource_cleanup(void);
static void d8_device_cleanup(void) {
    unsigned n=0;ULONG count=0;CPU*previous;
    previous=xrt_gui_callback_enter(xrt_cur?&xrt_cur->cpu:NULL);
    d8_rendering=1;d8_resource_cleanup();d8_bl_release();
    while(d8_device.refs) {
        count=XM_Release(NULL,d8_device.host);d8_device.refs--;n++;
        if(!d8_device.refs)d8_device_dead(&d8_device);
    }
    d8_rendering=0;xrt_gui_callback_leave(previous);
    xrt_event("d3d8_device_cleanup","\"references_released\":%u,\"final_native_count\":%lu",n,count);
}
static void d8_device_QueryInterface(CPU*c) {
    d8_api_entry(c,0,3);
    if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"D3D8 device COM: reentrant/failed native operation");
    D8DeviceObject*o=d8_device_object(c,ARG(0));GUID iid;void*q=NULL;HRESULT hr;DWORD error;CPU*previous;uint32_t out=ARG(2);
    d8_device_memory(c,ARG(1),16,0);if(out)d8_device_memory(c,out,4,1);
    memcpy(&iid,G2H(ARG(1)),16);previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=XM_QueryInterface(c,o->host,&iid,out?&q:NULL);error=GetLastError();d8_rendering=0;xrt_gui_callback_leave(previous);
    if(SUCCEEDED(hr)) {
        if(q!=o->host || (memcmp(&iid,&com_iunknown,16) && memcmp(&iid,&d8_device_iid,16))) {
            /* QI may have acquired an unmodelled reference. Keep its code alive
             * until process teardown rather than unloading beneath that object. */
            d8_native_failed=1;
            xrt_fatal(c,76,"Direct3DDevice8: unmodelled successful QI identity");
        }
        o->refs++;
    } else if(q) {d8_native_failed=1;xrt_fatal(c,76,"Direct3DDevice8: unexpected failed QI output");}
    if(out){d8_device_memory(c,out,4,1);wr32(out,SUCCEEDED(hr)?o->guest:0);}
    xrt_set_last_error(c,error);RET_STD(3,hr);
}
static void d8_device_AddRef(CPU*c) {
    d8_api_entry(c,1,1);
    if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"D3D8 device COM: reentrant/failed native operation");
    D8DeviceObject*o=d8_device_object(c,ARG(0));ULONG n;DWORD error;CPU*previous;
    if(o->refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 device reference overflow");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));n=XM_AddRef(c,o->host);error=GetLastError();d8_rendering=0;xrt_gui_callback_leave(previous);o->refs++;
    xrt_set_last_error(c,error);RET_STD(1,n);
}
static void d8_device_Release(CPU*c) {
    d8_api_entry(c,2,1);
    if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"D3D8 device COM: reentrant/failed native operation");
    D8DeviceObject*o=d8_device_object(c,ARG(0));ULONG n;DWORD error;CPU*previous;
    if(d8_rendering||d8_locks)xrt_fatal(c,76,"Direct3DDevice8: Release during native rendering or map unsupported");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;
    if(o->refs==1 && !o->children)d8_bl_release();   /* the game's last reference: native count reaches 0 as before */
    SetLastError(xrt_get_last_error(c));n=XM_Release(c,o->host);error=GetLastError();d8_rendering=0;xrt_gui_callback_leave(previous);
    if(!--o->refs && !o->children)d8_device_dead(o);xm_resource(c,2,o->guest,1,(uint64_t)(uintptr_t)o->host,o->refs,o->children,"released");
    xrt_event("d3d8_device_release","\"object\":%u,\"guest_refs\":%u,\"native_count\":%lu",o->guest,o->refs,n);
    xrt_set_last_error(c,error);RET_STD(1,n);
}
static void d8_device_GetDirect3D(CPU*c) {
    d8_api_entry(c,6,2);
    if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"D3D8 device COM: reentrant/failed native operation");
    D8DeviceObject*o=d8_device_object(c,ARG(0));D8Interface*q=NULL;HRESULT hr;DWORD error;CPU*previous;
    d8_device_memory(c,ARG(1),4,1);previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=XM_GetDirect3D(c,o->host,&q);error=GetLastError();d8_rendering=0;xrt_gui_callback_leave(previous);
    if(SUCCEEDED(hr)) {
        if(q!=o->parent->host) {d8_native_failed=1;xrt_fatal(c,76,"Direct3DDevice8: parent identity changed");}
        o->parent->refs++;
    } else if(q) {d8_native_failed=1;xrt_fatal(c,76,"Direct3DDevice8: unexpected failed parent output");}
    d8_device_memory(c,ARG(1),4,1);wr32(ARG(1),SUCCEEDED(hr)?o->parent->guest:0);xrt_set_last_error(c,error);RET_STD(2,hr);
}
static void d8_device_GetCreationParameters(CPU*c) {
    d8_api_entry(c,9,2);
    D8DeviceObject*o=d8_device_object(c,ARG(0));D8Creation cp;HRESULT hr;DWORD error;
    d8_device_memory(c,ARG(1),16,1);memset(&cp,0,sizeof cp);
    SetLastError(xrt_get_last_error(c));hr=XM_GetCreationParameters(c,o->host,&cp);error=GetLastError();
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
    if(d8_rendering||d8_native_failed)xrt_fatal(c,76,"Direct3DDevice8: reentrant or failed native operation");
    if(!o->window)
        xrt_fatal(c,76,"Direct3DDevice8: unsupported rendering window tuple (native call refused)");
    /* At shutdown the game destroys the window first and then flushes and releases the device (owner's run
     * 20261101-222030): those calls need no window. Present to the destroyed window is refused in d8_device_Present. */
    if(!xrt_gui_window_destroyed(o->focus))xrt_gui_device_window(c,o->focus);
    /* (round 4) the device window is usually the focus window itself: the same token was just checked, on this thread,
     * with nothing in between (only the owning thread can destroy it), so a second check could only repeat the answer */
    if(o->window!=o->focus && !xrt_gui_window_destroyed(o->window))xrt_gui_device_window(c,o->window);
}
/* Developer first-scene evidence: successful native draws since the previous
 * Present, and those issued inside FLevelSceneNode::Render. Never guest-visible. */
static unsigned d8_frame_draws,d8_frame_prims,d8_scene_draws,d8_scene_prims,d8_level_draws;
/* Developer draw dump (XRT_DEV_DRAW_FRAMES): states the guest set, shadowed
 * as forwarded, logged per draw for a few chosen world frames only. */
static DWORD d8_dev_rs[256],d8_dev_tss[8][32],d8_dev_shader;
static void d8_dev_draw_log(HRESULT hr,unsigned primitives);
static void d8_count_draw(HRESULT hr,unsigned primitives) {
    if(xrt_dev_draw_dump())d8_dev_draw_log(hr,primitives);
    if(FAILED(hr))return;
    d8_frame_draws++;d8_frame_prims+=primitives;
    /* World scene nodes: FLevelSceneNode or FCameraSceneNode (HUD is FPlayerSceneNode). */
    if(xrt_scene_level_depth>0||xrt_scene_camera_depth>0){d8_scene_draws++;d8_scene_prims+=primitives;}
    if(xrt_scene_level_depth>0)d8_level_draws++;
}
/* Copies the back buffer about to be presented into a private system-memory
 * surface. Host-only objects; guest last-error and MXCSR are restored. */
static void d8_dev_readback(CPU*c,D8DeviceObject*o,unsigned frame) {
    D8Surface*bb=NULL,*sys=NULL;D8SurfaceDesc d;D8Locked l;HRESULT hr;DWORD saved=GetLastError(),csr=_mm_getcsr();
    hr=XM_GetBackBuffer(c,o->host,0,0,&bb);
    if(SUCCEEDED(hr))hr=XM_GetDesc(c,bb,&d);
    if(SUCCEEDED(hr))hr=XM_CreateImageSurface(c,o->host,d.width,d.height,d.format,&sys);
    if(SUCCEEDED(hr))hr=XM_CopyRects(c,o->host,bb,NULL,0,sys,NULL);
    if(SUCCEEDED(hr))hr=XM_LockRect(c,sys,&l,NULL,0x10);
    if(SUCCEEDED(hr)){xrt_dev_scene_frame(frame,d.width,d.height,d.format,l.bits,l.pitch);XM_UnlockRect(c,sys);}
    else xrt_log("DEV scene readback for world frame %u failed: hr=%08lx",frame,(unsigned long)hr);
    if(sys)XM_Release(c,(D8Unknown*)sys);
    if(bb)XM_Release(c,(D8Unknown*)bb);
    _mm_setcsr(csr);SetLastError(saved);
}
static void d8_device_Present(CPU*c) {
    d8_api_entry(c,15,5);
    D8DeviceObject*o=d8_device_object(c,ARG(0));uint32_t esp=c->r[ESP],ret=rd32(esp),fsw=c->fsw;
    HRESULT hr;DWORD error,before,after;CPU*previous;RECT rects[2];HWND override=NULL;unsigned i;
    /* Source/destination RECTs are copied; the window override is a validated
     * same-thread GUI token. A dirty region still requires RGNDATA marshalling. */
    if(ARG(4))
        xrt_fatal(c,76,"IDirect3DDevice8::Present: dirty region requires marshalling (native call refused)");
    for(i=0;i<2;i++)if(ARG(1+i)){d8_device_memory(c,ARG(1+i),16,0);memcpy(&rects[i],G2H(ARG(1+i)),16);}
    d8_render_ready(c,o);
    if(xrt_gui_window_destroyed(o->window)) {
        /* nothing to present to: D3D's own answer for an invalid presentation, without a native call */
        xrt_log("D3D8 Present after the device window was destroyed: D3DERR_INVALIDCALL");
        RET_STD(5,0x8876086Cu);return;
    }
    if(ARG(3))override=(HWND)xrt_gui_device_window(c,ARG(3));
    if(d8_bl.active && d8_bl.tex) {
        /* Borderless fullscreen: the game's frame is the render-target texture; its source/destination RECTs describe
         * that virtual back buffer, so the native Present shows the whole composited back buffer. */
        CPU*bp=xrt_gui_callback_enter(c);d8_rendering=1;d8_bl_composite(c,o->host);d8_rendering=0;xrt_gui_callback_leave(bp);
        wr32(esp+8,0);wr32(esp+12,0);
    }
    {unsigned frame=xrt_dev_scene_capture(xrt_scene_level_renders+xrt_scene_camera_renders,d8_scene_draws);if(frame)d8_dev_readback(c,o,frame);}
    xrt_event("d3d8_render_call","\"method\":\"Present\",\"slot\":15,\"this\":%u,\"source\":%u,\"destination\":%u,\"override\":%u,\"dirty\":0,\"esp\":%u,\"return\":%u",o->guest,ARG(1),ARG(2),ARG(3),esp,ret);
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));before=_mm_getcsr();
    d8_semantic_checkpoint(c,1,15,NULL,0,0,xrt_get_last_error(c));SetLastError(xrt_get_last_error(c));
    {unsigned long long t0=XRT_PERF_T0();
    hr=XM_Present(c,o->host,ARG(1)?&rects[0]:NULL,ARG(2)?&rects[1]:NULL,override,NULL);error=GetLastError();after=_mm_getcsr();
    XRT_PERF_ADD(tsc_present,t0);XRT_PERF_ADD(tsc_native,t0);xrt_perf.present++;}
    d8_semantic_checkpoint(c,2,15,NULL,0,(unsigned)hr,error);
    d8_rendering=0;xrt_gui_callback_leave(previous);
    /* Pinned DXVK x86, live window, CW=027f: first successful Present sets
     * sticky x87 PE while retaining TOP, values and control. x64 uses SSE for
     * that calculation, so reproduce the independently measured guest effect.
     * Subsequent Presents leave the guest status alone, including fnclex. */
    if(hr==S_OK && !o->presents)c->fsw|=0x20;
    if(SUCCEEDED(hr))o->presents++;
    XRT_PERF_ADD(tsc_d3d,d8_perf_t_api);
    xrt_dev_scene_present(c,hr,d8_frame_draws,d8_frame_prims,d8_scene_draws,d8_scene_prims,d8_level_draws);
    d8_frame_draws=d8_frame_prims=d8_scene_draws=d8_scene_prims=d8_level_draws=0;
    xrt_set_last_error(c,error);RET_STD(5,hr);
    d8_semantic_checkpoint(c,3,15,NULL,0,(unsigned)hr,error);
    xrt_event("d3d8_render_return","\"method\":\"Present\",\"this\":%u,\"result\":%lu,\"last_error\":%lu,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u,\"mxcsr_before\":%lu,\"mxcsr_after\":%lu,\"guest_fsw_before\":%u,\"guest_fsw_after\":%u",o->guest,(DWORD)hr,error,esp,c->r[ESP],ret,c->rv,before,after,fsw,c->fsw);
}
#include "semantic_renderer.inc"
#include "semantic_clear.inc"
#include "semantic_create.inc"
#include "scene_draw.inc"
#include "resources.inc"
static void d8_dev_draw_log(HRESULT hr,unsigned primitives) {
    {unsigned s;const D8Resource*t[2];for(s=0;s<2;s++)t[s]=d8_bound_textures[s];
        xrt_log("DEV draw %u hr=%08lx prims=%u scene=%d level=%d vs=%lx z=%lu/%lu atest=%lu blend=%lu src=%lu dst=%lu cull=%lu fog=%lu light=%lu tfactor=%08lx"
                " | s0 tex=%x k%u f%u cop=%lu a1=%lu a2=%lu aop=%lu | s1 tex=%x k%u f%u cop=%lu a1=%lu a2=%lu aop=%lu",
                d8_frame_draws+1,(unsigned long)hr,primitives,xrt_scene_camera_depth>0||xrt_scene_level_depth>0,xrt_scene_level_depth>0,d8_dev_shader,
                d8_dev_rs[7],d8_dev_rs[14],d8_dev_rs[15],d8_dev_rs[27],d8_dev_rs[19],d8_dev_rs[20],d8_dev_rs[22],d8_dev_rs[28],d8_dev_rs[137],d8_dev_rs[60],
                t[0]?t[0]->guest:0,t[0]?t[0]->kind:0,t[0]?t[0]->format:0,d8_dev_tss[0][1],d8_dev_tss[0][2],d8_dev_tss[0][3],d8_dev_tss[0][4],
                t[1]?t[1]->guest:0,t[1]?t[1]->kind:0,t[1]?t[1]->format:0,d8_dev_tss[1][1],d8_dev_tss[1][2],d8_dev_tss[1][3],d8_dev_tss[1][4]);}
}
#include "resource_storage.inc"
#include "vertex_declaration.inc"
#include "resource_draw.inc"
#include "surface_transfer.inc"
#include "fixed_function.inc"
/* VSync (port setting, port_settings.c xrt_port_vsync). D3DDrv asks for a presentation interval only for exclusive full
 * screen (UseVSync -> D3DPRESENT_INTERVAL_ONE, else IMMEDIATE); this port always presents windowed (borderless full
 * screen included), where D3D8 has no interval, only the swap effect D3DSWAPEFFECT_COPY_VSYNC (4), which DXVK's D3D8
 * layer turns into a vsync'd (FIFO) swap chain - every other windowed swap effect presents immediately. So with VSync
 * on a windowed device gets COPY_VSYNC (needs a single back buffer), with VSync off the game's own effect (COPY_VSYNC
 * would become DISCARD). The game reads back the swap effect it asked for. A change applies at the next CreateDevice/
 * Reset; the menu asks for one through the window's resize path (dev_support.c xrt_dev_input_window_actions). */
static void d8_vsync_apply(D8Present*n,const char*where){
    int on=xrt_port_vsync();DEVMODEW dm;unsigned hz=0;uint32_t asked=n->swap;
    if(!n->windowed)return;
    if(on&&n->count<=1)n->swap=4;else if(!on&&n->swap==4)n->swap=1;
    memset(&dm,0,sizeof dm);dm.dmSize=sizeof dm;
    {MONITORINFOEXW mi;HMONITOR m=MonitorFromWindow(n->window,MONITOR_DEFAULTTONEAREST);mi.cbSize=sizeof mi;
     if(m&&GetMonitorInfoW(m,(MONITORINFO*)&mi)&&EnumDisplaySettingsW(mi.szDevice,ENUM_CURRENT_SETTINGS,&dm))hz=dm.dmDisplayFrequency;}
    xrt_log("D3D8 %s: VSync %s%s (swap effect %u, game asked %u, back buffers %u; monitor refresh %u Hz)",where,on?"on":"off",
            on&&n->count>1?" NOT APPLIED (more than one back buffer)":"",n->swap,asked,n->count,hz);
    xrt_event("d3d8_vsync","\"where\":\"%s\",\"on\":%d,\"swap\":%u,\"asked\":%u,\"refresh_hz\":%u",where,on,n->swap,asked,hz);
}
/* Windowed IDirect3DDevice8::Reset (window resize: the renderer resets its device to the new back buffer size).
 * The 52-byte presentation tuple is mapped as in CreateDevice; it must stay windowed on the device's own window.
 * Native D3D8 (DXVK) itself refuses the call while D3DPOOL_DEFAULT resources, extra render targets or depth surfaces
 * are still referenced, so live resource records stay valid. A successful reset leaves the device in default state
 * with no stream/index/texture bindings: the runtime's binding records go as the native device dropped them. */
static void d8_device_Reset(CPU*c) {
    LONG id=d8_api_entry(c,14,2);D8DeviceObject*o=d8_semantic_frame(c);uint32_t pp=ARG(1),window;D8Present n;CPU*prev;HRESULT hr;DWORD error;
    uint32_t bl_saved[13],swap_asked;int bl;unsigned i;
    if(d8_locks)xrt_fatal(c,76,"IDirect3DDevice8::Reset with mapped resources (native call refused)");
    d8_device_memory(c,pp,52,1);
    /* Borderless fullscreen: the runtime's own default-pool objects go before the native Reset (as D3D8 requires);
     * a fullscreen request is translated like CreateDevice's, a windowed one ends borderless mode. */
    d8_bl_release();
    bl=d8_bl_translate(c,pp,rd32(pp+24)?rd32(pp+24):o->window,bl_saved);
    if(!bl)d8_bl_end("windowed reset",c,1);
    window=rd32(pp+24);memset(&n,0,sizeof n);
    n.width=rd32(pp);n.height=rd32(pp+4);n.format=rd32(pp+8);n.count=rd32(pp+12);n.multisample=rd32(pp+16);n.swap=rd32(pp+20);
    n.windowed=rd32(pp+28);n.depth=rd32(pp+32);n.depthformat=rd32(pp+36);n.flags=rd32(pp+40);n.refresh=rd32(pp+44);n.interval=rd32(pp+48);
    if(!n.windowed)xrt_fatal(c,76,"IDirect3DDevice8::Reset: fullscreen presentation is outside the windowed scope (native call refused)");
    if(window && window!=o->window && window!=o->focus)
        xrt_fatal(c,76,"IDirect3DDevice8::Reset: presentation window change %08x -> %08x unsupported",o->window,window);
    n.window=window?xrt_gui_device_window(c,window):NULL;
    swap_asked=n.swap;d8_vsync_apply(&n,"Reset");
    xrt_log("D3D8 Reset: %ux%u format %u count %u swap %u depth %u/%u flags %x interval %x (device was %ux%u)",
            n.width,n.height,n.format,n.count,n.swap,n.depth,n.depthformat,n.flags,n.interval,o->width,o->height);
    prev=d8_native_enter(c,14,&n,sizeof n);hr=XM_Reset(c,o->host,&n);error=GetLastError();
    if(SUCCEEDED(hr)){o->width=n.width;o->height=n.height;o->depth=n.depth;o->depthformat=n.depthformat;d8_resource_device_dead();}
    if(SUCCEEDED(hr)&&bl){d8_bl_create(c,o->host);o->width=d8_bl.vw;o->height=d8_bl.vh;o->depth=d8_bl.depth;o->depthformat=d8_bl.depthformat;}
    d8_device_memory(c,pp,52,1);
    wr32(pp,n.width);wr32(pp+4,n.height);wr32(pp+8,n.format);wr32(pp+12,n.count);wr32(pp+16,n.multisample);wr32(pp+20,swap_asked);
    wr32(pp+24,xrt_gui_window_identity(c,n.window));wr32(pp+28,n.windowed);wr32(pp+32,n.depth);wr32(pp+36,n.depthformat);
    wr32(pp+40,n.flags);wr32(pp+44,n.refresh);wr32(pp+48,n.interval);
    if(bl)for(i=0;i<13;i++)if(i!=6)wr32(pp+4*i,bl_saved[i]);   /* the game sees the parameters it asked for */
    xrt_log("D3D8 Reset result %08lx: back buffer %ux%u",(unsigned long)hr,n.width,n.height);
    xrt_event("d3d8_device_reset","\"this\":%u,\"width\":%u,\"height\":%u,\"result\":%u",o->guest,n.width,n.height,(unsigned)hr);
    d8_semantic_return(c,prev,id,2,hr,error);
}
#include "d3d8_device_slots.inc"
static void d8_create_device_body(CPU*c,D8Object*p,D8DeviceObject*o,uint32_t adapter,uint32_t type,uint32_t focus,uint32_t flags,
                                  uint32_t pp,uint32_t out,int bl,const uint32_t*bl_saved);
static void d8_CreateDevice(CPU*c) {
    d8_api_entry(c,100,7);
    if(d8_creating || d8_rendering)xrt_fatal(c,76,"SAFETY: reentrant CreateDevice");
    D8Object*p=d8_object(c,ARG(0));D8DeviceObject*o=&d8_device;
    uint32_t adapter=ARG(1),type=ARG(2),focus=ARG(3),flags=ARG(4),pp=ARG(5),out=ARG(6);
    d8_device_memory(c,pp,52,1);d8_device_memory(c,out,4,1);
    /* Overlap cannot represent two independently mutable outputs. */
    if((uint64_t)out<(uint64_t)pp+52 && (uint64_t)pp<(uint64_t)out+4)
        xrt_fatal(c,76,"IDirect3D8::CreateDevice: overlapping presentation/output unsupported");
    if(!focus && !rd32(pp+24))xrt_fatal(c,76,"SAFETY: CreateDevice requires an owned presentation/focus window");
    /* Borderless fullscreen: a fullscreen request becomes a windowed native request on the monitor-sized window. */
    {uint32_t bl_saved[13];int bl=d8_bl_translate(c,pp,rd32(pp+24)?rd32(pp+24):focus,bl_saved);
     if(!bl)d8_bl_end("windowed device requested",c,1);
     d8_create_device_body(c,p,o,adapter,type,focus,flags,pp,out,bl,bl_saved);}
}
static void d8_create_device_body(CPU*c,D8Object*p,D8DeviceObject*o,uint32_t adapter,uint32_t type,uint32_t focus,uint32_t flags,
                                  uint32_t pp,uint32_t out,int bl,const uint32_t*bl_saved) {
    uint32_t esp=c->r[ESP],ret=rd32(esp),window;D8Present n;D8Device*host=NULL;D8Interface*parent=p->host;
    HRESULT hr;DWORD error,mxcsr_before,mxcsr_after;CPU*previous;unsigned i;uint32_t swap_asked;
    d8_creation_domain(c,p,adapter,type,flags,pp);
    window=rd32(pp+24);memset(&n,0,sizeof n);
    n.width=rd32(pp);n.height=rd32(pp+4);n.format=rd32(pp+8);n.count=rd32(pp+12);n.multisample=rd32(pp+16);n.swap=rd32(pp+20);
    n.window=window?xrt_gui_device_window(c,window):NULL;n.windowed=rd32(pp+28);n.depth=rd32(pp+32);n.depthformat=rd32(pp+36);
    n.flags=rd32(pp+40);n.refresh=rd32(pp+44);n.interval=rd32(pp+48);
    swap_asked=n.swap;d8_vsync_apply(&n,"CreateDevice");
    {
        HWND focus_host=xrt_gui_device_window(c,focus);
        xrt_dev_input_window(focus_host?focus_host:n.window); /* developer input script target */
        if(InterlockedCompareExchange(&d8_attempted,1,0)) {
            /* Sequential re-creation only: D3DDrv released its device to native count 0
             * (observed: DeleteVertexShader..., Release->0, CreateDevice). A device that is
             * still referenced, has live children, is mapped or failed keeps the refusal. */
            if(o->host || o->refs || o->children || d8_native_failed || d8_locks)
                xrt_fatal(c,76,"IDirect3D8::CreateDevice: previous device still live (refs %u children %u); simultaneous devices refused",o->refs,o->children);
            xrt_log("D3D8 CreateDevice: sequential re-creation after previous device destroyed");
            xrt_event("d3d8_device_recreate","\"previous_guest\":%u,\"presents\":%u",o->guest,o->presents);
        }
        /* Allocate all guest state before invoking the host. The reserved object
         * has zero refs and is unreachable through the guest output in callbacks. */
        if(!d8_device_vtable)d8_device_vtable=com_vtable(d8_device_slot_names,97);
        o->guest=xrt_rt_alloc(4,4);wr32(o->guest,d8_device_vtable);
        o->parent=p;o->focus=focus;o->window=window?window:focus;
        o->width=n.width;o->height=n.height;o->depth=n.depth;o->depthformat=n.depthformat;o->behavior=flags;
        xrt_gui_window_pin(c,focus);xrt_gui_window_pin(c,o->window);
        wr32(out,0);d8_creating=1;p->pending++;
        XM_AddRef(c,parent); /* private guard against a parent-first callback */
        xrt_event("d3d8_device_call","\"this\":%u,\"adapter\":%u,\"type\":%u,\"focus\":%u,\"window\":%u,\"flags\":%u,\"parameters\":%u,\"output\":%u,\"esp\":%u,\"return\":%u,\"attempt\":1",p->guest,adapter,type,focus,window,flags,pp,out,esp,ret);
        previous=xrt_gui_callback_enter(c);SetLastError(xrt_get_last_error(c));
        mxcsr_before=_mm_getcsr();
        d8_semantic_checkpoint(c,1,100,&n,sizeof n,0,xrt_get_last_error(c));
        SetLastError(xrt_get_last_error(c));
        hr=XM_CreateDevice(c,parent,adapter,type,focus_host,flags,&n,&host);error=GetLastError();mxcsr_after=_mm_getcsr();
        d8_semantic_checkpoint(c,2,100,&n,sizeof n,(unsigned)hr,error);
        xrt_event("d3d8_device_mxcsr","\"before\":%lu,\"after\":%lu",mxcsr_before,mxcsr_after);
        xrt_gui_callback_leave(previous);
    }
    /* Mark failed initialization before any operation that can stop execution:
     * cleanup must retain both modules and all possibly live backend resources. */
    d8_native_failed=FAILED(hr) || !host;
    if(!d8_native_failed) { o->host=host;o->refs=1;p->children++;xm_resource(c,2,o->guest,1,(uint64_t)(uintptr_t)o->host,o->refs,0,"created"); }
    XM_Release(c,parent);p->pending--;d8_creating=0;
    if(!p->refs && !p->children && !p->pending)p->host=NULL;
    d8_device_memory(c,pp,52,1);d8_device_memory(c,out,4,1);
    window=xrt_gui_window_identity(c,n.window);
    wr32(pp,n.width);wr32(pp+4,n.height);wr32(pp+8,n.format);wr32(pp+12,n.count);wr32(pp+16,n.multisample);wr32(pp+20,swap_asked);
    wr32(pp+24,window);wr32(pp+28,n.windowed);wr32(pp+32,n.depth);wr32(pp+36,n.depthformat);wr32(pp+40,n.flags);wr32(pp+44,n.refresh);wr32(pp+48,n.interval);
    if(bl && !d8_native_failed) {
        /* Borderless fullscreen: the game's back buffer is the runtime's render target of the size it asked for. */
        CPU*bp=xrt_gui_callback_enter(c);d8_bl_create(c,host);xrt_gui_callback_leave(bp);
        o->width=d8_bl.vw;o->height=d8_bl.vh;o->depth=d8_bl.depth;o->depthformat=d8_bl.depthformat;
        for(i=0;i<13;i++)if(i!=6)wr32(pp+4*i,bl_saved[i]);   /* the game sees the parameters it asked for */
    }
    wr32(out,o->refs?o->guest:0);xrt_set_last_error(c,error);RET_STD(7,hr);
    d8_semantic_checkpoint(c,3,100,&n,sizeof n,(unsigned)hr,error);
    xrt_event("d3d8_device_return","\"this\":%u,\"result\":%lu,\"last_error\":%lu,\"device\":%u,\"host_non_null\":%s,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",p->guest,(DWORD)hr,error,o->refs?o->guest:0,host?"true":"false",esp,c->r[ESP],ret,c->rv);
    d8_words("create_device_parameters",G2H(pp),13);
    if(d8_native_failed)
        xrt_fatal(c,76,"IDirect3D8::CreateDevice: native initialization failed hr=%08lx last-error=%lu host-output=%s; process teardown required, no retry",(DWORD)hr,error,host?"non-null":"NULL");
    for(i=0;i<97;i++)if(!rd32(d8_device_vtable+i*4) || rd32(d8_device_vtable+i*4)!=xrt_hle_proc("xrt.com",d8_device_slot_names[i]))
        xrt_fatal(c,77,"Direct3DDevice8: guest vtable audit failed at %u",i);
    xrt_event("d3d8_device_audit","\"object\":%u,\"vtable\":%u,\"typed_slots\":97,\"passed\":true",o->guest,d8_device_vtable);
}

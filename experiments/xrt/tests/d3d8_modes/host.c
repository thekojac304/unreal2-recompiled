#include "xrt_internal.h"
static uint32_t checked_call(CPU*c,uint32_t va,int nargs,const uint32_t*args,int stdcall) {
    uint32_t result=xrt_call_guest(c,va,nargs,args,stdcall),p,vt,i;
    const char*names[]={"D8.QueryInterface","D8.AddRef","D8.Release","D8.RegisterSoftwareDevice","D8.GetAdapterCount",
        "D8.GetAdapterIdentifier","D8.GetAdapterModeCount","D8.EnumAdapterModes","D8.GetAdapterDisplayMode",
        "D8.CheckDeviceType","D8.CheckDeviceFormat","D8.CheckDeviceMultiSampleType","D8.CheckDepthStencilMatch",
        "D8.GetDeviceCaps","D8.GetAdapterMonitor","D8.CreateDevice"};
    p=rd32(xrt_module_export(xrt_module_by_name("d3dprobe.dll"),"probe_pointer_object",0));
    if(p) {
        if(!xrt_is_committed(p,4))xrt_fatal(c,XRT_EXIT_SETUP,"fixture object outside guest memory");
        vt=rd32(p);
        if(!xrt_is_committed(vt,64))xrt_fatal(c,XRT_EXIT_SETUP,"fixture vtable outside guest memory");
        for(i=0;i<16;i++) {
            uint32_t fn=rd32(vt+4*i);
            if(fn<XRT_STUB_BASE||fn>=XRT_STUB_END||fn!=xrt_hle_proc("xrt.com",names[i]))
                xrt_fatal(c,XRT_EXIT_SETUP,"fixture guest COM slot %u is not its typed guest stub",i);
        }
        xrt_event("d3d8_guest_pointer_audit","\"object\":%u,\"vtable\":%u,\"slots\":16,\"passed\":true",p,vt);
    }
    return result;
}
#define xrt_call_guest checked_call
#define xrt_mod_ehprobe xrt_mod_d3dprobe
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"

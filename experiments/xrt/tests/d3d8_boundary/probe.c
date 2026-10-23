/* Same project-owned query client compiled as PE32 and PE32+. */
#define WIN32_LEAN_AND_MEAN
#include "../../runtime/d3d8_abi.h"
#include <string.h>
#pragma function(memcpy)
void* __cdecl memcpy(void*dst,const void*src,size_t n) {
    size_t i;for(i=0;i<n;i++)((volatile BYTE*)dst)[i]=((const volatile BYTE*)src)[i];return dst;
}
__declspec(dllimport) D8Interface* WINAPI Direct3DCreate8(UINT);
__declspec(dllexport) int probe_log[4096],probe_log_n;
static void logv(DWORD v) { probe_log[probe_log_n++]=(int)v; }
static void fill(void*p,UINT n) { UINT i;for(i=0;i<n;i++) ((volatile BYTE*)p)[i]=0xa5; }
static void words(const void*p,UINT n) { UINT i;for(i=0;i<n;i++) logv(((const DWORD*)p)[i]); }
__declspec(dllexport) int probe_queries(void) {
    D8Interface*d=Direct3DCreate8(120);
    UINT count,a;
    D8Identifier id;
    D8Caps caps;
    HRESULT hr;
    probe_log_n=0;logv(d!=NULL);
    if(!d) return 1;
    count=d->vt->GetAdapterCount(d);logv(count);
    if(count>8) {d->vt->Release(d);return 2;}
    /* Exact initial Unreal II sequence: all identifiers with flag 2, then
     * selected adapter 0, HAL=1. The original copies 0x42c identifier bytes. */
    for(a=0;a<count;a++) {
        fill(&id,sizeof id);
        hr=d->vt->GetAdapterIdentifier(d,a,2,&id);logv(hr);
        words(&id,D8_IDENTIFIER_BYTES/4);
    }
    fill(&caps,sizeof caps);
    hr=d->vt->GetDeviceCaps(d,0,1,&caps);logv(hr);words(&caps,53);
    logv(d->vt->Release(d));
    return count && SUCCEEDED(hr)?0:3;
}
static const GUID iid8={0x1dd9e8da,0x1c77,0x4d40,{0xb0,0xcf,0x98,0xfe,0xfd,0xff,0x95,0x12}};
static const GUID unknown={0,0,0,{0xc0,0,0,0,0,0,0,0x46}};
static const GUID missing={0x12345678,0,0,{1,2,3,4,5,6,7,8}};
__declspec(dllexport) int probe_lifetime(void) {
    D8Interface*d=Direct3DCreate8(120),*b=Direct3DCreate8(120),*q=NULL;
    probe_log_n=0;logv(d!=NULL);logv(b!=NULL);if(!d||!b)return 1;
    logv(d!=b);logv(d->vt->AddRef(d));logv(d->vt->Release(d));
    logv(d->vt->QueryInterface(d,&iid8,(void**)&q));logv(q==d);logv(q->vt->Release(q));
    logv(d->vt->QueryInterface(d,&unknown,(void**)&q));logv(q==d);logv(q->vt->Release(q));
    q=(D8Interface*)0x55555555;
    logv(d->vt->QueryInterface(d,&missing,(void**)&q));logv(q==NULL);
    logv(d->vt->Release(d));logv(b->vt->GetAdapterCount(b));logv(b->vt->Release(b));return 0;
}
__declspec(dllexport) int probe_leak(void) {
    D8Interface*d=Direct3DCreate8(120);probe_log_n=0;logv(d!=NULL);
    if(!d)return 1;logv(d->vt->AddRef(d));return 0;
}
__declspec(dllexport) int probe_formats(void) {
    D8Interface*d=Direct3DCreate8(120);static const DWORD formats[]={0x31545844,0x33545844,0x35545844};UINT i;
    probe_log_n=0;if(!d)return 1;
    for(i=0;i<3;i++)logv(d->vt->CheckDeviceFormat(d,0,1,22,0,3,formats[i]));
    logv(d->vt->Release(d));return 0;
}
__declspec(dllexport) int probe_errors(void) {
    D8Interface*d=Direct3DCreate8(120);D8Identifier id;D8Caps caps;
    probe_log_n=0;if(!d)return 1;
    fill(&id,sizeof id);logv(d->vt->GetAdapterIdentifier(d,0xffff,2,&id));words(&id,D8_IDENTIFIER_BYTES/4);
    fill(&caps,sizeof caps);logv(d->vt->GetDeviceCaps(d,0xffff,1,&caps));words(&caps,53);
    logv(d->vt->Release(d));return 0;
}
__declspec(dllexport) int probe_guards(void) {
    struct {DWORD before;D8Identifier value;DWORD after;} id;
    struct {DWORD before;D8Caps value;DWORD after;} caps;
    D8Interface*d=Direct3DCreate8(120);
    probe_log_n=0;if(!d)return 1;
    id.before=caps.before=0x11223344;id.after=caps.after=0x55667788;
    fill(&id.value,sizeof id.value);fill(&caps.value,sizeof caps.value);
    logv(d->vt->GetAdapterIdentifier(d,0,2,&id.value));logv(id.before);logv(id.after);
    logv(d->vt->GetDeviceCaps(d,0,1,&caps.value));logv(caps.before);logv(caps.after);
    logv(d->vt->Release(d));return 0;
}
__declspec(dllexport) int probe_stale(void) {
    D8Interface*d=Direct3DCreate8(120);d->vt->Release(d);return (int)d->vt->GetAdapterCount(d);
}
__declspec(dllexport) int probe_unmeasured(void) {
    D8Interface*d=Direct3DCreate8(120);return (int)d->vt->RegisterSoftwareDevice(d,NULL);
}

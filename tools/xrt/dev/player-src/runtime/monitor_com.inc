#ifndef XM_COM_WRAPPERS
#define XM_COM_WRAPPERS
#ifndef DIRECTINPUT_VERSION
#define DIRECTINPUT_VERSION 0x0800
#endif
#include <dinput.h>
#include "d3d8_device_abi.h"
#include "monitor.h"
typedef char xm_slot_D8Interface_QueryInterface[offsetof(D8Vtable,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_QueryInterface(CPU*c,D8Interface* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->QueryInterface(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.QueryInterface";q.slot=0;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Interface.QueryInterface.input1",a1,16);
 ret=a0->vt->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Interface.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_AddRef[offsetof(D8Vtable,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_D8Interface_AddRef(CPU*c,D8Interface* a0) {
 if(xm_quiet)return a0->vt->AddRef(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.AddRef";q.slot=1;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_Release[offsetof(D8Vtable,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_D8Interface_Release(CPU*c,D8Interface* a0) {
 if(xm_quiet)return a0->vt->Release(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.Release";q.slot=2;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_RegisterSoftwareDevice[offsetof(D8Vtable,RegisterSoftwareDevice)==3*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_RegisterSoftwareDevice(CPU*c,D8Interface* a0, void* a1) {
 if(xm_quiet)return a0->vt->RegisterSoftwareDevice(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.RegisterSoftwareDevice";q.slot=3;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->RegisterSoftwareDevice(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_GetAdapterCount[offsetof(D8Vtable,GetAdapterCount)==4*sizeof(void*)?1:-1];
static UINT xm_D8Interface_GetAdapterCount(CPU*c,D8Interface* a0) {
 if(xm_quiet)return a0->vt->GetAdapterCount(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; UINT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.GetAdapterCount";q.slot=4;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetAdapterCount(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_GetAdapterIdentifier[offsetof(D8Vtable,GetAdapterIdentifier)==5*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_GetAdapterIdentifier(CPU*c,D8Interface* a0, UINT a1, DWORD a2, D8Identifier* a3) {
 if(xm_quiet)return a0->vt->GetAdapterIdentifier(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.GetAdapterIdentifier";q.slot=5;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->GetAdapterIdentifier(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_GetAdapterModeCount[offsetof(D8Vtable,GetAdapterModeCount)==6*sizeof(void*)?1:-1];
static UINT xm_D8Interface_GetAdapterModeCount(CPU*c,D8Interface* a0, UINT a1) {
 if(xm_quiet)return a0->vt->GetAdapterModeCount(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; UINT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.GetAdapterModeCount";q.slot=6;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetAdapterModeCount(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_EnumAdapterModes[offsetof(D8Vtable,EnumAdapterModes)==7*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_EnumAdapterModes(CPU*c,D8Interface* a0, UINT a1, UINT a2, D8Mode* a3) {
 if(xm_quiet)return a0->vt->EnumAdapterModes(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.EnumAdapterModes";q.slot=7;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->EnumAdapterModes(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a3)xm_span(c,"D8Interface.EnumAdapterModes.output3",a3,sizeof(*a3));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_GetAdapterDisplayMode[offsetof(D8Vtable,GetAdapterDisplayMode)==8*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_GetAdapterDisplayMode(CPU*c,D8Interface* a0, UINT a1, D8Mode* a2) {
 if(xm_quiet)return a0->vt->GetAdapterDisplayMode(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.GetAdapterDisplayMode";q.slot=8;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetAdapterDisplayMode(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Interface.GetAdapterDisplayMode.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_CheckDeviceType[offsetof(D8Vtable,CheckDeviceType)==9*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_CheckDeviceType(CPU*c,D8Interface* a0, UINT a1, UINT a2, UINT a3, UINT a4, BOOL a5) {
 if(xm_quiet)return a0->vt->CheckDeviceType(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.CheckDeviceType";q.slot=9;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_I32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->CheckDeviceType(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_CheckDeviceFormat[offsetof(D8Vtable,CheckDeviceFormat)==10*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_CheckDeviceFormat(CPU*c,D8Interface* a0, UINT a1, UINT a2, UINT a3, DWORD a4, UINT a5, UINT a6) {
 if(xm_quiet)return a0->vt->CheckDeviceFormat(a0,a1,a2,a3,a4,a5,a6);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.CheckDeviceFormat";q.slot=10;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=7;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_U32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 q.values[6].type=XM_U32;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)a6;
 xm_probe(c,&q);
 ret=a0->vt->CheckDeviceFormat(a0,a1,a2,a3,a4,a5,a6);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_CheckDeviceMultiSampleType[offsetof(D8Vtable,CheckDeviceMultiSampleType)==11*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_CheckDeviceMultiSampleType(CPU*c,D8Interface* a0, UINT a1, UINT a2, UINT a3, BOOL a4, UINT a5) {
 if(xm_quiet)return a0->vt->CheckDeviceMultiSampleType(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.CheckDeviceMultiSampleType";q.slot=11;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_I32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_U32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->CheckDeviceMultiSampleType(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_CheckDepthStencilMatch[offsetof(D8Vtable,CheckDepthStencilMatch)==12*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_CheckDepthStencilMatch(CPU*c,D8Interface* a0, UINT a1, UINT a2, UINT a3, UINT a4, UINT a5) {
 if(xm_quiet)return a0->vt->CheckDepthStencilMatch(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.CheckDepthStencilMatch";q.slot=12;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_U32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->CheckDepthStencilMatch(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_GetDeviceCaps[offsetof(D8Vtable,GetDeviceCaps)==13*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_GetDeviceCaps(CPU*c,D8Interface* a0, UINT a1, UINT a2, D8Caps* a3) {
 if(xm_quiet)return a0->vt->GetDeviceCaps(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.GetDeviceCaps";q.slot=13;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->GetDeviceCaps(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a3)xm_span(c,"D8Interface.GetDeviceCaps.output3",a3,sizeof(*a3));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_GetAdapterMonitor[offsetof(D8Vtable,GetAdapterMonitor)==14*sizeof(void*)?1:-1];
static HMONITOR xm_D8Interface_GetAdapterMonitor(CPU*c,D8Interface* a0, UINT a1) {
 if(xm_quiet)return a0->vt->GetAdapterMonitor(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HMONITOR ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.GetAdapterMonitor";q.slot=14;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetAdapterMonitor(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Interface_CreateDevice[offsetof(D8Vtable,CreateDevice)==15*sizeof(void*)?1:-1];
static HRESULT xm_D8Interface_CreateDevice(CPU*c,D8Interface* a0, UINT a1, UINT a2, HWND a3, DWORD a4, D8Present* a5, D8Device** a6) {
 if(xm_quiet)return a0->vt->CreateDevice(a0,a1,a2,a3,a4,a5,a6);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Interface.CreateDevice";q.slot=15;q.interface_id=1;q.host=(uint64_t)(uintptr_t)a0;q.count=7;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 xm_probe(c,&q);
 if(a5)xm_span(c,"D8Interface.CreateDevice.input5",a5,sizeof(*a5));
 if(a6)xm_span(c,"D8Interface.CreateDevice.input6",a6,sizeof(*a6));
 ret=a0->vt->CreateDevice(a0,a1,a2,a3,a4,a5,a6);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a5)xm_span(c,"D8Interface.CreateDevice.output5",a5,sizeof(*a5));
 if(a6)xm_span(c,"D8Interface.CreateDevice.output6",a6,sizeof(*a6));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_QueryInterface[offsetof(D8DeviceVtable,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_QueryInterface(CPU*c,D8Device* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->QueryInterface(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.QueryInterface";q.slot=0;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Device.QueryInterface.input1",a1,16);
 ret=a0->vt->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Device.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_AddRef[offsetof(D8DeviceVtable,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_D8Device_AddRef(CPU*c,D8Device* a0) {
 if(xm_quiet)return a0->vt->AddRef(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.AddRef";q.slot=1;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_Release[offsetof(D8DeviceVtable,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_D8Device_Release(CPU*c,D8Device* a0) {
 if(xm_quiet)return a0->vt->Release(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.Release";q.slot=2;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_TestCooperativeLevel[offsetof(D8DeviceVtable,TestCooperativeLevel)==3*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_TestCooperativeLevel(CPU*c,D8Device* a0) {
 if(xm_quiet)return a0->vt->TestCooperativeLevel(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.TestCooperativeLevel";q.slot=3;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->TestCooperativeLevel(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetAvailableTextureMem[offsetof(D8DeviceVtable,GetAvailableTextureMem)==4*sizeof(void*)?1:-1];
static UINT xm_D8Device_GetAvailableTextureMem(CPU*c,D8Device* a0) {
 if(xm_quiet)return a0->vt->GetAvailableTextureMem(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; UINT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetAvailableTextureMem";q.slot=4;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetAvailableTextureMem(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_ResourceManagerDiscardBytes[offsetof(D8DeviceVtable,ResourceManagerDiscardBytes)==5*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_ResourceManagerDiscardBytes(CPU*c,D8Device* a0, DWORD a1) {
 if(xm_quiet)return a0->vt->ResourceManagerDiscardBytes(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.ResourceManagerDiscardBytes";q.slot=5;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->ResourceManagerDiscardBytes(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetDirect3D[offsetof(D8DeviceVtable,GetDirect3D)==6*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetDirect3D(CPU*c,D8Device* a0, D8Interface** a1) {
 if(xm_quiet)return a0->vt->GetDirect3D(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetDirect3D";q.slot=6;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDirect3D(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetDirect3D.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetDeviceCaps[offsetof(D8DeviceVtable,GetDeviceCaps)==7*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetDeviceCaps(CPU*c,D8Device* a0, D8Caps* a1) {
 if(xm_quiet)return a0->vt->GetDeviceCaps(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetDeviceCaps";q.slot=7;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDeviceCaps(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetDeviceCaps.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetDisplayMode[offsetof(D8DeviceVtable,GetDisplayMode)==8*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetDisplayMode(CPU*c,D8Device* a0, D8Mode* a1) {
 if(xm_quiet)return a0->vt->GetDisplayMode(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetDisplayMode";q.slot=8;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDisplayMode(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetDisplayMode.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetCreationParameters[offsetof(D8DeviceVtable,GetCreationParameters)==9*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetCreationParameters(CPU*c,D8Device* a0, D8Creation* a1) {
 if(xm_quiet)return a0->vt->GetCreationParameters(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetCreationParameters";q.slot=9;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetCreationParameters(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetCreationParameters.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_Present[offsetof(D8DeviceVtable,Present)==15*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_Present(CPU*c,D8Device* a0, const RECT* a1, const RECT* a2, HWND a3, const RGNDATA* a4) {
 if(xm_quiet)return a0->vt->Present(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.Present";q.slot=15;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_OPAQUE;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)(uintptr_t)a4;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Device.Present.input1",a1,sizeof(*a1));
 if(a2)xm_span(c,"D8Device.Present.input2",a2,sizeof(*a2));
 ret=a0->vt->Present(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_Reset[offsetof(D8DeviceVtable,Reset)==14*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_Reset(CPU*c,D8Device* a0, D8Present* a1) {
 if(xm_quiet)return a0->vt->Reset(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.Reset";q.slot=14;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Device.Reset.input1",a1,sizeof(*a1));
 ret=a0->vt->Reset(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.Reset.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
#define XM_Reset(cpu,self,...) xm_D8Device_Reset((cpu),(self),##__VA_ARGS__)
typedef char xm_slot_D8Device_GetBackBuffer[offsetof(D8DeviceVtable,GetBackBuffer)==16*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetBackBuffer(CPU*c,D8Device* a0, UINT a1, DWORD a2, D8Surface** a3) {
 if(xm_quiet)return a0->vt->GetBackBuffer(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetBackBuffer";q.slot=16;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->GetBackBuffer(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a3)xm_span(c,"D8Device.GetBackBuffer.output3",a3,sizeof(*a3));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetGammaRamp[offsetof(D8DeviceVtable,SetGammaRamp)==18*sizeof(void*)?1:-1];
static void xm_D8Device_SetGammaRamp(CPU*c,D8Device* a0, DWORD a1, const D8Gamma* a2) {
 if(xm_quiet){a0->vt->SetGammaRamp(a0,a1,a2);return;}   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0};
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetGammaRamp";q.slot=18;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a2)xm_span(c,"D8Device.SetGammaRamp.input2",a2,sizeof(*a2));
 a0->vt->SetGammaRamp(a0,a1,a2);
 q.event=XM_END;q.result=0;
 xm_probe(c,&q);
}
typedef char xm_slot_D8Device_GetGammaRamp[offsetof(D8DeviceVtable,GetGammaRamp)==19*sizeof(void*)?1:-1];
static void xm_D8Device_GetGammaRamp(CPU*c,D8Device* a0, D8Gamma* a1) {
 if(xm_quiet){a0->vt->GetGammaRamp(a0,a1);return;}   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0};
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetGammaRamp";q.slot=19;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 a0->vt->GetGammaRamp(a0,a1);
 q.event=XM_END;q.result=0;
 if(a1)xm_span(c,"D8Device.GetGammaRamp.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
}
typedef char xm_slot_D8Device_CreateTexture[offsetof(D8DeviceVtable,CreateTexture)==20*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateTexture(CPU*c,D8Device* a0, UINT a1, UINT a2, UINT a3, DWORD a4, DWORD a5, DWORD a6, D8Texture** a7) {
 if(xm_quiet)return a0->vt->CreateTexture(a0,a1,a2,a3,a4,a5,a6,a7);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateTexture";q.slot=20;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=8;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_U32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 q.values[6].type=XM_U32;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)a6;
 q.values[7].type=XM_OPAQUE;q.values[7].bytes=sizeof(a7);
 q.values[7].value=(uint64_t)(uintptr_t)a7;
 xm_probe(c,&q);
 ret=a0->vt->CreateTexture(a0,a1,a2,a3,a4,a5,a6,a7);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a7)xm_span(c,"D8Device.CreateTexture.output7",a7,sizeof(*a7));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CreateVertexBuffer[offsetof(D8DeviceVtable,CreateVertexBuffer)==23*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateVertexBuffer(CPU*c,D8Device* a0, UINT a1, DWORD a2, DWORD a3, DWORD a4, D8Buffer** a5) {
 if(xm_quiet)return a0->vt->CreateVertexBuffer(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateVertexBuffer";q.slot=23;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->CreateVertexBuffer(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a5)xm_span(c,"D8Device.CreateVertexBuffer.output5",a5,sizeof(*a5));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CreateIndexBuffer[offsetof(D8DeviceVtable,CreateIndexBuffer)==24*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateIndexBuffer(CPU*c,D8Device* a0, UINT a1, DWORD a2, DWORD a3, DWORD a4, D8Buffer** a5) {
 if(xm_quiet)return a0->vt->CreateIndexBuffer(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateIndexBuffer";q.slot=24;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->CreateIndexBuffer(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a5)xm_span(c,"D8Device.CreateIndexBuffer.output5",a5,sizeof(*a5));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CreateRenderTarget[offsetof(D8DeviceVtable,CreateRenderTarget)==25*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateRenderTarget(CPU*c,D8Device* a0, UINT a1, UINT a2, DWORD a3, DWORD a4, BOOL a5, D8Surface** a6) {
 if(xm_quiet)return a0->vt->CreateRenderTarget(a0,a1,a2,a3,a4,a5,a6);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateRenderTarget";q.slot=25;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=7;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_I32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 xm_probe(c,&q);
 ret=a0->vt->CreateRenderTarget(a0,a1,a2,a3,a4,a5,a6);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a6)xm_span(c,"D8Device.CreateRenderTarget.output6",a6,sizeof(*a6));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CreateDepthStencilSurface[offsetof(D8DeviceVtable,CreateDepthStencilSurface)==26*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateDepthStencilSurface(CPU*c,D8Device* a0, UINT a1, UINT a2, DWORD a3, DWORD a4, D8Surface** a5) {
 if(xm_quiet)return a0->vt->CreateDepthStencilSurface(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateDepthStencilSurface";q.slot=26;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->CreateDepthStencilSurface(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a5)xm_span(c,"D8Device.CreateDepthStencilSurface.output5",a5,sizeof(*a5));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CreateImageSurface[offsetof(D8DeviceVtable,CreateImageSurface)==27*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateImageSurface(CPU*c,D8Device* a0, UINT a1, UINT a2, DWORD a3, D8Surface** a4) {
 if(xm_quiet)return a0->vt->CreateImageSurface(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateImageSurface";q.slot=27;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_OPAQUE;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)(uintptr_t)a4;
 xm_probe(c,&q);
 ret=a0->vt->CreateImageSurface(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a4)xm_span(c,"D8Device.CreateImageSurface.output4",a4,sizeof(*a4));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CopyRects[offsetof(D8DeviceVtable,CopyRects)==28*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CopyRects(CPU*c,D8Device* a0, D8Surface* a1, const RECT* a2, UINT a3, D8Surface* a4, const POINT* a5) {
 if(xm_quiet)return a0->vt->CopyRects(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CopyRects";q.slot=28;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_OPAQUE;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)(uintptr_t)a4;
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 if(a2)xm_span(c,"D8Device.CopyRects.input2",a2,sizeof(*a2));
 ret=a0->vt->CopyRects(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_UpdateTexture[offsetof(D8DeviceVtable,UpdateTexture)==29*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_UpdateTexture(CPU*c,D8Device* a0, D8Texture* a1, D8Texture* a2) {
 if(xm_quiet)return a0->vt->UpdateTexture(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.UpdateTexture";q.slot=29;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->UpdateTexture(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetFrontBuffer[offsetof(D8DeviceVtable,GetFrontBuffer)==30*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetFrontBuffer(CPU*c,D8Device* a0, D8Surface* a1) {
 if(xm_quiet)return a0->vt->GetFrontBuffer(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetFrontBuffer";q.slot=30;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetFrontBuffer(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetRenderTarget[offsetof(D8DeviceVtable,SetRenderTarget)==31*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetRenderTarget(CPU*c,D8Device* a0, D8Surface* a1, D8Surface* a2) {
 if(xm_quiet)return a0->vt->SetRenderTarget(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetRenderTarget";q.slot=31;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->SetRenderTarget(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetRenderTarget[offsetof(D8DeviceVtable,GetRenderTarget)==32*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetRenderTarget(CPU*c,D8Device* a0, D8Surface** a1) {
 if(xm_quiet)return a0->vt->GetRenderTarget(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetRenderTarget";q.slot=32;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetRenderTarget(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetRenderTarget.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetDepthStencilSurface[offsetof(D8DeviceVtable,GetDepthStencilSurface)==33*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetDepthStencilSurface(CPU*c,D8Device* a0, D8Surface** a1) {
 if(xm_quiet)return a0->vt->GetDepthStencilSurface(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetDepthStencilSurface";q.slot=33;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDepthStencilSurface(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetDepthStencilSurface.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_BeginScene[offsetof(D8DeviceVtable,BeginScene)==34*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_BeginScene(CPU*c,D8Device* a0) {
 if(xm_quiet)return a0->vt->BeginScene(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.BeginScene";q.slot=34;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->BeginScene(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_EndScene[offsetof(D8DeviceVtable,EndScene)==35*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_EndScene(CPU*c,D8Device* a0) {
 if(xm_quiet)return a0->vt->EndScene(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.EndScene";q.slot=35;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->EndScene(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_Clear[offsetof(D8DeviceVtable,Clear)==36*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_Clear(CPU*c,D8Device* a0, DWORD a1, const D8Rect* a2, DWORD a3, DWORD a4, float a5, DWORD a6) {
 if(xm_quiet)return a0->vt->Clear(a0,a1,a2,a3,a4,a5,a6);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.Clear";q.slot=36;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=7;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_U32;q.values[5].bytes=sizeof(a5);
 memcpy(&q.values[5].value,&a5,sizeof a5);
 q.values[6].type=XM_U32;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)a6;
 xm_probe(c,&q);
 if(a2)xm_span(c,"D8Device.Clear.input2",a2,sizeof(*a2));
 ret=a0->vt->Clear(a0,a1,a2,a3,a4,a5,a6);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetTransform[offsetof(D8DeviceVtable,SetTransform)==37*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetTransform(CPU*c,D8Device* a0, DWORD a1, const D8Matrix* a2) {
 if(xm_quiet)return a0->vt->SetTransform(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetTransform";q.slot=37;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a2)xm_span(c,"D8Device.SetTransform.input2",a2,sizeof(*a2));
 ret=a0->vt->SetTransform(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetTransform[offsetof(D8DeviceVtable,GetTransform)==38*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetTransform(CPU*c,D8Device* a0, DWORD a1, D8Matrix* a2) {
 if(xm_quiet)return a0->vt->GetTransform(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetTransform";q.slot=38;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetTransform(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Device.GetTransform.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetViewport[offsetof(D8DeviceVtable,SetViewport)==40*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetViewport(CPU*c,D8Device* a0, const D8Viewport* a1) {
 if(xm_quiet)return a0->vt->SetViewport(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetViewport";q.slot=40;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Device.SetViewport.input1",a1,sizeof(*a1));
 ret=a0->vt->SetViewport(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetViewport[offsetof(D8DeviceVtable,GetViewport)==41*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetViewport(CPU*c,D8Device* a0, D8Viewport* a1) {
 if(xm_quiet)return a0->vt->GetViewport(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetViewport";q.slot=41;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetViewport(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetViewport.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetMaterial[offsetof(D8DeviceVtable,SetMaterial)==42*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetMaterial(CPU*c,D8Device* a0, const D8Material* a1) {
 if(xm_quiet)return a0->vt->SetMaterial(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetMaterial";q.slot=42;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Device.SetMaterial.input1",a1,sizeof(*a1));
 ret=a0->vt->SetMaterial(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetRenderState[offsetof(D8DeviceVtable,SetRenderState)==50*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetRenderState(CPU*c,D8Device* a0, DWORD a1, DWORD a2) {
 if(xm_quiet)return a0->vt->SetRenderState(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetRenderState";q.slot=50;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->SetRenderState(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetRenderState[offsetof(D8DeviceVtable,GetRenderState)==51*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetRenderState(CPU*c,D8Device* a0, DWORD a1, DWORD* a2) {
 if(xm_quiet)return a0->vt->GetRenderState(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetRenderState";q.slot=51;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetRenderState(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetTexture[offsetof(D8DeviceVtable,GetTexture)==60*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetTexture(CPU*c,D8Device* a0, DWORD a1, void** a2) {
 if(xm_quiet)return a0->vt->GetTexture(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetTexture";q.slot=60;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetTexture(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Device.GetTexture.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetTexture[offsetof(D8DeviceVtable,SetTexture)==61*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetTexture(CPU*c,D8Device* a0, DWORD a1, void* a2) {
 if(xm_quiet)return a0->vt->SetTexture(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetTexture";q.slot=61;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->SetTexture(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetTextureStageState[offsetof(D8DeviceVtable,GetTextureStageState)==62*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetTextureStageState(CPU*c,D8Device* a0, DWORD a1, DWORD a2, DWORD* a3) {
 if(xm_quiet)return a0->vt->GetTextureStageState(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetTextureStageState";q.slot=62;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->GetTextureStageState(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetTextureStageState[offsetof(D8DeviceVtable,SetTextureStageState)==63*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetTextureStageState(CPU*c,D8Device* a0, DWORD a1, DWORD a2, DWORD a3) {
 if(xm_quiet)return a0->vt->SetTextureStageState(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetTextureStageState";q.slot=63;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->SetTextureStageState(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_DrawPrimitive[offsetof(D8DeviceVtable,DrawPrimitive)==70*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_DrawPrimitive(CPU*c,D8Device* a0, DWORD a1, UINT a2, UINT a3) {
 if(xm_quiet)return a0->vt->DrawPrimitive(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.DrawPrimitive";q.slot=70;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->DrawPrimitive(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_DrawIndexedPrimitive[offsetof(D8DeviceVtable,DrawIndexedPrimitive)==71*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_DrawIndexedPrimitive(CPU*c,D8Device* a0, DWORD a1, UINT a2, UINT a3, UINT a4, UINT a5) {
 if(xm_quiet)return a0->vt->DrawIndexedPrimitive(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.DrawIndexedPrimitive";q.slot=71;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=6;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_U32;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)a5;
 xm_probe(c,&q);
 ret=a0->vt->DrawIndexedPrimitive(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_DrawPrimitiveUP[offsetof(D8DeviceVtable,DrawPrimitiveUP)==72*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_DrawPrimitiveUP(CPU*c,D8Device* a0, DWORD a1, UINT a2, const void* a3, UINT a4) {
 if(xm_quiet)return a0->vt->DrawPrimitiveUP(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.DrawPrimitiveUP";q.slot=72;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 xm_probe(c,&q);
 ret=a0->vt->DrawPrimitiveUP(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_DrawIndexedPrimitiveUP[offsetof(D8DeviceVtable,DrawIndexedPrimitiveUP)==73*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_DrawIndexedPrimitiveUP(CPU*c,D8Device* a0, DWORD a1, UINT a2, UINT a3, UINT a4, const void* a5, DWORD a6, const void* a7, UINT a8) {
 if(xm_quiet)return a0->vt->DrawIndexedPrimitiveUP(a0,a1,a2,a3,a4,a5,a6,a7,a8);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.DrawIndexedPrimitiveUP";q.slot=73;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=9;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_U32;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)a6;
 q.values[7].type=XM_OPAQUE;q.values[7].bytes=sizeof(a7);
 q.values[7].value=(uint64_t)(uintptr_t)a7;
 q.values[8].type=XM_U32;q.values[8].bytes=sizeof(a8);
 q.values[8].value=(uint64_t)a8;
 xm_probe(c,&q);
 ret=a0->vt->DrawIndexedPrimitiveUP(a0,a1,a2,a3,a4,a5,a6,a7,a8);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_CreateVertexShader[offsetof(D8DeviceVtable,CreateVertexShader)==75*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_CreateVertexShader(CPU*c,D8Device* a0, const DWORD* a1, const DWORD* a2, DWORD* a3, DWORD a4) {
 if(xm_quiet)return a0->vt->CreateVertexShader(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.CreateVertexShader";q.slot=75;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 xm_probe(c,&q);
 ret=a0->vt->CreateVertexShader(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetVertexShader[offsetof(D8DeviceVtable,SetVertexShader)==76*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetVertexShader(CPU*c,D8Device* a0, DWORD a1) {
 if(xm_quiet)return a0->vt->SetVertexShader(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetVertexShader";q.slot=76;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->SetVertexShader(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetVertexShader[offsetof(D8DeviceVtable,GetVertexShader)==77*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetVertexShader(CPU*c,D8Device* a0, DWORD* a1) {
 if(xm_quiet)return a0->vt->GetVertexShader(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetVertexShader";q.slot=77;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetVertexShader(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_DeleteVertexShader[offsetof(D8DeviceVtable,DeleteVertexShader)==78*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_DeleteVertexShader(CPU*c,D8Device* a0, DWORD a1) {
 if(xm_quiet)return a0->vt->DeleteVertexShader(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.DeleteVertexShader";q.slot=78;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->DeleteVertexShader(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetStreamSource[offsetof(D8DeviceVtable,SetStreamSource)==83*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetStreamSource(CPU*c,D8Device* a0, DWORD a1, void* a2, DWORD a3) {
 if(xm_quiet)return a0->vt->SetStreamSource(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetStreamSource";q.slot=83;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->SetStreamSource(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetStreamSource[offsetof(D8DeviceVtable,GetStreamSource)==84*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetStreamSource(CPU*c,D8Device* a0, DWORD a1, void** a2, DWORD* a3) {
 if(xm_quiet)return a0->vt->GetStreamSource(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetStreamSource";q.slot=84;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->vt->GetStreamSource(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Device.GetStreamSource.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_SetIndices[offsetof(D8DeviceVtable,SetIndices)==85*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_SetIndices(CPU*c,D8Device* a0, void* a1, DWORD a2) {
 if(xm_quiet)return a0->vt->SetIndices(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.SetIndices";q.slot=85;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->SetIndices(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Device_GetIndices[offsetof(D8DeviceVtable,GetIndices)==86*sizeof(void*)?1:-1];
static HRESULT xm_D8Device_GetIndices(CPU*c,D8Device* a0, void** a1, DWORD* a2) {
 if(xm_quiet)return a0->vt->GetIndices(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Device.GetIndices";q.slot=86;q.interface_id=2;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetIndices(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Device.GetIndices.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Unknown_QueryInterface[offsetof(D8UnknownVtable,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_D8Unknown_QueryInterface(CPU*c,D8Unknown* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->QueryInterface(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Unknown.QueryInterface";q.slot=0;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Unknown.QueryInterface.input1",a1,16);
 ret=a0->vt->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Unknown.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Unknown_AddRef[offsetof(D8UnknownVtable,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_D8Unknown_AddRef(CPU*c,D8Unknown* a0) {
 if(xm_quiet)return a0->vt->AddRef(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Unknown.AddRef";q.slot=1;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Unknown_Release[offsetof(D8UnknownVtable,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_D8Unknown_Release(CPU*c,D8Unknown* a0) {
 if(xm_quiet)return a0->vt->Release(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Unknown.Release";q.slot=2;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Unknown_GetDevice[offsetof(D8UnknownVtable,GetDevice)==3*sizeof(void*)?1:-1];
static HRESULT xm_D8Unknown_GetDevice(CPU*c,D8Unknown* a0, D8Device** a1) {
 if(xm_quiet)return a0->vt->GetDevice(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Unknown.GetDevice";q.slot=3;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDevice(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Unknown.GetDevice.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_QueryInterface[offsetof(D8SurfaceVtable,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_D8Surface_QueryInterface(CPU*c,D8Surface* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->QueryInterface(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.QueryInterface";q.slot=0;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Surface.QueryInterface.input1",a1,16);
 ret=a0->vt->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Surface.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_AddRef[offsetof(D8SurfaceVtable,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_D8Surface_AddRef(CPU*c,D8Surface* a0) {
 if(xm_quiet)return a0->vt->AddRef(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.AddRef";q.slot=1;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_Release[offsetof(D8SurfaceVtable,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_D8Surface_Release(CPU*c,D8Surface* a0) {
 if(xm_quiet)return a0->vt->Release(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.Release";q.slot=2;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_GetDevice[offsetof(D8SurfaceVtable,GetDevice)==3*sizeof(void*)?1:-1];
static HRESULT xm_D8Surface_GetDevice(CPU*c,D8Surface* a0, D8Device** a1) {
 if(xm_quiet)return a0->vt->GetDevice(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.GetDevice";q.slot=3;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDevice(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Surface.GetDevice.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_GetContainer[offsetof(D8SurfaceVtable,GetContainer)==7*sizeof(void*)?1:-1];
static HRESULT xm_D8Surface_GetContainer(CPU*c,D8Surface* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->GetContainer(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.GetContainer";q.slot=7;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Surface.GetContainer.input1",a1,16);
 ret=a0->vt->GetContainer(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Surface.GetContainer.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_GetDesc[offsetof(D8SurfaceVtable,GetDesc)==8*sizeof(void*)?1:-1];
static HRESULT xm_D8Surface_GetDesc(CPU*c,D8Surface* a0, D8SurfaceDesc* a1) {
 if(xm_quiet)return a0->vt->GetDesc(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.GetDesc";q.slot=8;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDesc(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Surface.GetDesc.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_LockRect[offsetof(D8SurfaceVtable,LockRect)==9*sizeof(void*)?1:-1];
static HRESULT xm_D8Surface_LockRect(CPU*c,D8Surface* a0, D8Locked* a1, const RECT* a2, DWORD a3) {
 if(xm_quiet)return a0->vt->LockRect(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.LockRect";q.slot=9;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_U32;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)a3;
 xm_probe(c,&q);
 if(a2)xm_span(c,"D8Surface.LockRect.input2",a2,sizeof(*a2));
 ret=a0->vt->LockRect(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Surface.LockRect.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Surface_UnlockRect[offsetof(D8SurfaceVtable,UnlockRect)==10*sizeof(void*)?1:-1];
static HRESULT xm_D8Surface_UnlockRect(CPU*c,D8Surface* a0) {
 if(xm_quiet)return a0->vt->UnlockRect(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Surface.UnlockRect";q.slot=10;q.interface_id=101;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->UnlockRect(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_QueryInterface[offsetof(D8TextureVtable,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_QueryInterface(CPU*c,D8Texture* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->QueryInterface(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.QueryInterface";q.slot=0;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Texture.QueryInterface.input1",a1,16);
 ret=a0->vt->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Texture.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_AddRef[offsetof(D8TextureVtable,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_D8Texture_AddRef(CPU*c,D8Texture* a0) {
 if(xm_quiet)return a0->vt->AddRef(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.AddRef";q.slot=1;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_Release[offsetof(D8TextureVtable,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_D8Texture_Release(CPU*c,D8Texture* a0) {
 if(xm_quiet)return a0->vt->Release(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.Release";q.slot=2;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_GetDevice[offsetof(D8TextureVtable,GetDevice)==3*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_GetDevice(CPU*c,D8Texture* a0, D8Device** a1) {
 if(xm_quiet)return a0->vt->GetDevice(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetDevice";q.slot=3;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDevice(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Texture.GetDevice.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_SetPriority[offsetof(D8TextureVtable,SetPriority)==7*sizeof(void*)?1:-1];
static DWORD xm_D8Texture_SetPriority(CPU*c,D8Texture* a0, DWORD a1) {
 if(xm_quiet)return a0->vt->SetPriority(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.SetPriority";q.slot=7;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->SetPriority(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_GetPriority[offsetof(D8TextureVtable,GetPriority)==8*sizeof(void*)?1:-1];
static DWORD xm_D8Texture_GetPriority(CPU*c,D8Texture* a0) {
 if(xm_quiet)return a0->vt->GetPriority(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetPriority";q.slot=8;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetPriority(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_PreLoad[offsetof(D8TextureVtable,PreLoad)==9*sizeof(void*)?1:-1];
static void xm_D8Texture_PreLoad(CPU*c,D8Texture* a0) {
 if(xm_quiet){a0->vt->PreLoad(a0);return;}   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0};
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.PreLoad";q.slot=9;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 a0->vt->PreLoad(a0);
 q.event=XM_END;q.result=0;
 xm_probe(c,&q);
}
typedef char xm_slot_D8Texture_GetType[offsetof(D8TextureVtable,GetType)==10*sizeof(void*)?1:-1];
static DWORD xm_D8Texture_GetType(CPU*c,D8Texture* a0) {
 if(xm_quiet)return a0->vt->GetType(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetType";q.slot=10;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetType(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_SetLOD[offsetof(D8TextureVtable,SetLOD)==11*sizeof(void*)?1:-1];
static DWORD xm_D8Texture_SetLOD(CPU*c,D8Texture* a0, DWORD a1) {
 if(xm_quiet)return a0->vt->SetLOD(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.SetLOD";q.slot=11;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->SetLOD(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_GetLOD[offsetof(D8TextureVtable,GetLOD)==12*sizeof(void*)?1:-1];
static DWORD xm_D8Texture_GetLOD(CPU*c,D8Texture* a0) {
 if(xm_quiet)return a0->vt->GetLOD(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetLOD";q.slot=12;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetLOD(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_GetLevelCount[offsetof(D8TextureVtable,GetLevelCount)==13*sizeof(void*)?1:-1];
static DWORD xm_D8Texture_GetLevelCount(CPU*c,D8Texture* a0) {
 if(xm_quiet)return a0->vt->GetLevelCount(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetLevelCount";q.slot=13;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetLevelCount(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_GetLevelDesc[offsetof(D8TextureVtable,GetLevelDesc)==14*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_GetLevelDesc(CPU*c,D8Texture* a0, UINT a1, D8SurfaceDesc* a2) {
 if(xm_quiet)return a0->vt->GetLevelDesc(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetLevelDesc";q.slot=14;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetLevelDesc(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Texture.GetLevelDesc.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_GetSurfaceLevel[offsetof(D8TextureVtable,GetSurfaceLevel)==15*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_GetSurfaceLevel(CPU*c,D8Texture* a0, UINT a1, D8Surface** a2) {
 if(xm_quiet)return a0->vt->GetSurfaceLevel(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.GetSurfaceLevel";q.slot=15;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=a0->vt->GetSurfaceLevel(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Texture.GetSurfaceLevel.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_LockRect[offsetof(D8TextureVtable,LockRect)==16*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_LockRect(CPU*c,D8Texture* a0, UINT a1, D8Locked* a2, const RECT* a3, DWORD a4) {
 if(xm_quiet)return a0->vt->LockRect(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.LockRect";q.slot=16;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 xm_probe(c,&q);
 if(a3)xm_span(c,"D8Texture.LockRect.input3",a3,sizeof(*a3));
 ret=a0->vt->LockRect(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Texture.LockRect.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_UnlockRect[offsetof(D8TextureVtable,UnlockRect)==17*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_UnlockRect(CPU*c,D8Texture* a0, UINT a1) {
 if(xm_quiet)return a0->vt->UnlockRect(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.UnlockRect";q.slot=17;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->UnlockRect(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Texture_AddDirtyRect[offsetof(D8TextureVtable,AddDirtyRect)==18*sizeof(void*)?1:-1];
static HRESULT xm_D8Texture_AddDirtyRect(CPU*c,D8Texture* a0, const RECT* a1) {
 if(xm_quiet)return a0->vt->AddDirtyRect(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Texture.AddDirtyRect";q.slot=18;q.interface_id=103;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Texture.AddDirtyRect.input1",a1,sizeof(*a1));
 ret=a0->vt->AddDirtyRect(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_QueryInterface[offsetof(D8BufferVtable,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_D8Buffer_QueryInterface(CPU*c,D8Buffer* a0, REFIID a1, void** a2) {
 if(xm_quiet)return a0->vt->QueryInterface(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.QueryInterface";q.slot=0;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"D8Buffer.QueryInterface.input1",a1,16);
 ret=a0->vt->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"D8Buffer.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_AddRef[offsetof(D8BufferVtable,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_D8Buffer_AddRef(CPU*c,D8Buffer* a0) {
 if(xm_quiet)return a0->vt->AddRef(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.AddRef";q.slot=1;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_Release[offsetof(D8BufferVtable,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_D8Buffer_Release(CPU*c,D8Buffer* a0) {
 if(xm_quiet)return a0->vt->Release(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.Release";q.slot=2;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_GetDevice[offsetof(D8BufferVtable,GetDevice)==3*sizeof(void*)?1:-1];
static HRESULT xm_D8Buffer_GetDevice(CPU*c,D8Buffer* a0, D8Device** a1) {
 if(xm_quiet)return a0->vt->GetDevice(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.GetDevice";q.slot=3;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDevice(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Buffer.GetDevice.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_SetPriority[offsetof(D8BufferVtable,SetPriority)==7*sizeof(void*)?1:-1];
static DWORD xm_D8Buffer_SetPriority(CPU*c,D8Buffer* a0, DWORD a1) {
 if(xm_quiet)return a0->vt->SetPriority(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.SetPriority";q.slot=7;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->SetPriority(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_GetPriority[offsetof(D8BufferVtable,GetPriority)==8*sizeof(void*)?1:-1];
static DWORD xm_D8Buffer_GetPriority(CPU*c,D8Buffer* a0) {
 if(xm_quiet)return a0->vt->GetPriority(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.GetPriority";q.slot=8;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetPriority(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_PreLoad[offsetof(D8BufferVtable,PreLoad)==9*sizeof(void*)?1:-1];
static void xm_D8Buffer_PreLoad(CPU*c,D8Buffer* a0) {
 if(xm_quiet){a0->vt->PreLoad(a0);return;}   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0};
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.PreLoad";q.slot=9;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 a0->vt->PreLoad(a0);
 q.event=XM_END;q.result=0;
 xm_probe(c,&q);
}
typedef char xm_slot_D8Buffer_GetType[offsetof(D8BufferVtable,GetType)==10*sizeof(void*)?1:-1];
static DWORD xm_D8Buffer_GetType(CPU*c,D8Buffer* a0) {
 if(xm_quiet)return a0->vt->GetType(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.GetType";q.slot=10;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->GetType(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_Lock[offsetof(D8BufferVtable,Lock)==11*sizeof(void*)?1:-1];
static HRESULT xm_D8Buffer_Lock(CPU*c,D8Buffer* a0, UINT a1, UINT a2, BYTE** a3, DWORD a4) {
 if(xm_quiet)return a0->vt->Lock(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.Lock";q.slot=11;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 xm_probe(c,&q);
 ret=a0->vt->Lock(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a3)xm_span(c,"D8Buffer.Lock.output3",a3,sizeof(*a3));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_Unlock[offsetof(D8BufferVtable,Unlock)==12*sizeof(void*)?1:-1];
static HRESULT xm_D8Buffer_Unlock(CPU*c,D8Buffer* a0) {
 if(xm_quiet)return a0->vt->Unlock(a0);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.Unlock";q.slot=12;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->vt->Unlock(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_D8Buffer_GetDesc[offsetof(D8BufferVtable,GetDesc)==13*sizeof(void*)?1:-1];
static HRESULT xm_D8Buffer_GetDesc(CPU*c,D8Buffer* a0, D8BufferDesc* a1) {
 if(xm_quiet)return a0->vt->GetDesc(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="D8Buffer.GetDesc";q.slot=13;q.interface_id=106;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=a0->vt->GetDesc(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"D8Buffer.GetDesc.output1",a1,sizeof(*a1));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IUnknown_QueryInterface[offsetof(IUnknownVtbl,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_IUnknown_QueryInterface(CPU*c,IUnknown* a0, REFIID a1, void** a2) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IUnknown.QueryInterface";q.slot=0;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"IUnknown.QueryInterface.input1",a1,16);
 ret=a0->lpVtbl->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"IUnknown.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IUnknown_AddRef[offsetof(IUnknownVtbl,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_IUnknown_AddRef(CPU*c,IUnknown* a0) {
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IUnknown.AddRef";q.slot=1;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IUnknown_Release[offsetof(IUnknownVtbl,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_IUnknown_Release(CPU*c,IUnknown* a0) {
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IUnknown.Release";q.slot=2;q.interface_id=0;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInput8W_QueryInterface[offsetof(IDirectInput8WVtbl,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInput8W_QueryInterface(CPU*c,IDirectInput8W* a0, REFIID a1, void** a2) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInput8W.QueryInterface";q.slot=0;q.interface_id=3;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"IDirectInput8W.QueryInterface.input1",a1,16);
 ret=a0->lpVtbl->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"IDirectInput8W.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInput8W_AddRef[offsetof(IDirectInput8WVtbl,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_IDirectInput8W_AddRef(CPU*c,IDirectInput8W* a0) {
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInput8W.AddRef";q.slot=1;q.interface_id=3;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInput8W_Release[offsetof(IDirectInput8WVtbl,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_IDirectInput8W_Release(CPU*c,IDirectInput8W* a0) {
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInput8W.Release";q.slot=2;q.interface_id=3;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInput8W_CreateDevice[offsetof(IDirectInput8WVtbl,CreateDevice)==3*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInput8W_CreateDevice(CPU*c,IDirectInput8W* a0, REFGUID a1, IDirectInputDevice8W** a2, IUnknown* a3) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInput8W.CreateDevice";q.slot=3;q.interface_id=3;q.host=(uint64_t)(uintptr_t)a0;q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=a0->lpVtbl->CreateDevice(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a1)xm_span(c,"IDirectInput8W.CreateDevice.output1",a1,16);
 if(a2)xm_span(c,"IDirectInput8W.CreateDevice.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_QueryInterface[offsetof(IDirectInputDevice8WVtbl,QueryInterface)==0*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_QueryInterface(CPU*c,IDirectInputDevice8W* a0, REFIID a1, void** a2) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.QueryInterface";q.slot=0;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a1)xm_span(c,"IDirectInputDevice8W.QueryInterface.input1",a1,16);
 ret=a0->lpVtbl->QueryInterface(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2)xm_span(c,"IDirectInputDevice8W.QueryInterface.output2",a2,sizeof(*a2));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_AddRef[offsetof(IDirectInputDevice8WVtbl,AddRef)==1*sizeof(void*)?1:-1];
static ULONG xm_IDirectInputDevice8W_AddRef(CPU*c,IDirectInputDevice8W* a0) {
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.AddRef";q.slot=1;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->AddRef(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_Release[offsetof(IDirectInputDevice8WVtbl,Release)==2*sizeof(void*)?1:-1];
static ULONG xm_IDirectInputDevice8W_Release(CPU*c,IDirectInputDevice8W* a0) {
 XmRequest q={0}; ULONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.Release";q.slot=2;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->Release(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_SetProperty[offsetof(IDirectInputDevice8WVtbl,SetProperty)==6*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_SetProperty(CPU*c,IDirectInputDevice8W* a0, REFGUID a1, LPCDIPROPHEADER a2) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.SetProperty";q.slot=6;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a2)xm_span(c,"IDirectInputDevice8W.SetProperty.input2",a2,sizeof(DIPROPHEADER));
 ret=a0->lpVtbl->SetProperty(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_Acquire[offsetof(IDirectInputDevice8WVtbl,Acquire)==7*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_Acquire(CPU*c,IDirectInputDevice8W* a0) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.Acquire";q.slot=7;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->Acquire(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_Unacquire[offsetof(IDirectInputDevice8WVtbl,Unacquire)==8*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_Unacquire(CPU*c,IDirectInputDevice8W* a0) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.Unacquire";q.slot=8;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=a0->lpVtbl->Unacquire(a0);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_GetDeviceData[offsetof(IDirectInputDevice8WVtbl,GetDeviceData)==10*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_GetDeviceData(CPU*c,IDirectInputDevice8W* a0, DWORD a1, LPDIDEVICEOBJECTDATA a2, LPDWORD a3, DWORD a4) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.GetDeviceData";q.slot=10;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=5;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_U32;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 q.values[4].type=XM_U32;q.values[4].bytes=sizeof(a4);
 q.values[4].value=(uint64_t)a4;
 xm_probe(c,&q);
 DWORD xm_capacity=a3?*a3:0;if(xm_capacity>256||a1!=sizeof(DIDEVICEOBJECTDATA))xm_failure(24);
 if(a2&&xm_capacity)xm_span(c,"DID.data.input",a2,xm_capacity*sizeof *a2);
 ret=a0->lpVtbl->GetDeviceData(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)ret;
 if(a2&&xm_capacity)xm_span(c,"DID.data.output",a2,xm_capacity*sizeof *a2);
 if(a3)xm_span(c,"IDirectInputDevice8W.GetDeviceData.output3",a3,sizeof(*a3));
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_SetDataFormat[offsetof(IDirectInputDevice8WVtbl,SetDataFormat)==11*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_SetDataFormat(CPU*c,IDirectInputDevice8W* a0, LPCDIDATAFORMAT a1) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.SetDataFormat";q.slot=11;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 if(a1){unsigned i;if(a1->dwNumObjs>256||a1->dwObjSize!=sizeof(DIOBJECTDATAFORMAT))xm_failure(23);
 if(a1->dwNumObjs&&a1->rgodf){xm_span(c,"DID.format.objects",a1->rgodf,a1->dwNumObjs*sizeof(DIOBJECTDATAFORMAT));
 for(i=0;i<a1->dwNumObjs;i++)if(a1->rgodf[i].pguid)xm_blob(c,"DID.format.object-guid",a1->rgodf[i].pguid,16);}}
 if(a1)xm_span(c,"IDirectInputDevice8W.SetDataFormat.input1",a1,sizeof(DIDATAFORMAT));
 ret=a0->lpVtbl->SetDataFormat(a0,a1);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
typedef char xm_slot_IDirectInputDevice8W_SetCooperativeLevel[offsetof(IDirectInputDevice8WVtbl,SetCooperativeLevel)==13*sizeof(void*)?1:-1];
static HRESULT xm_IDirectInputDevice8W_SetCooperativeLevel(CPU*c,IDirectInputDevice8W* a0, HWND a1, DWORD a2) {
 XmRequest q={0}; HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="IDirectInputDevice8W.SetCooperativeLevel";q.slot=13;q.interface_id=4;q.host=(uint64_t)(uintptr_t)a0;q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_U32;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)a2;
 xm_probe(c,&q);
 ret=a0->lpVtbl->SetCooperativeLevel(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)ret;
 xm_probe(c,&q);
 return ret;
}
#define XM_QueryInterface(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_QueryInterface,D8Device*:xm_D8Device_QueryInterface,D8Unknown*:xm_D8Unknown_QueryInterface,D8Surface*:xm_D8Surface_QueryInterface,D8Texture*:xm_D8Texture_QueryInterface,D8Buffer*:xm_D8Buffer_QueryInterface,IUnknown*:xm_IUnknown_QueryInterface,IDirectInput8W*:xm_IDirectInput8W_QueryInterface,IDirectInputDevice8W*:xm_IDirectInputDevice8W_QueryInterface)((cpu),(self),##__VA_ARGS__)
#define XM_AddRef(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_AddRef,D8Device*:xm_D8Device_AddRef,D8Unknown*:xm_D8Unknown_AddRef,D8Surface*:xm_D8Surface_AddRef,D8Texture*:xm_D8Texture_AddRef,D8Buffer*:xm_D8Buffer_AddRef,IUnknown*:xm_IUnknown_AddRef,IDirectInput8W*:xm_IDirectInput8W_AddRef,IDirectInputDevice8W*:xm_IDirectInputDevice8W_AddRef)((cpu),(self),##__VA_ARGS__)
#define XM_Release(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_Release,D8Device*:xm_D8Device_Release,D8Unknown*:xm_D8Unknown_Release,D8Surface*:xm_D8Surface_Release,D8Texture*:xm_D8Texture_Release,D8Buffer*:xm_D8Buffer_Release,IUnknown*:xm_IUnknown_Release,IDirectInput8W*:xm_IDirectInput8W_Release,IDirectInputDevice8W*:xm_IDirectInputDevice8W_Release)((cpu),(self),##__VA_ARGS__)
#define XM_RegisterSoftwareDevice(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_RegisterSoftwareDevice)((cpu),(self),##__VA_ARGS__)
#define XM_GetAdapterCount(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_GetAdapterCount)((cpu),(self),##__VA_ARGS__)
#define XM_GetAdapterIdentifier(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_GetAdapterIdentifier)((cpu),(self),##__VA_ARGS__)
#define XM_GetAdapterModeCount(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_GetAdapterModeCount)((cpu),(self),##__VA_ARGS__)
#define XM_EnumAdapterModes(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_EnumAdapterModes)((cpu),(self),##__VA_ARGS__)
#define XM_GetAdapterDisplayMode(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_GetAdapterDisplayMode)((cpu),(self),##__VA_ARGS__)
#define XM_CheckDeviceType(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_CheckDeviceType)((cpu),(self),##__VA_ARGS__)
#define XM_CheckDeviceFormat(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_CheckDeviceFormat)((cpu),(self),##__VA_ARGS__)
#define XM_CheckDeviceMultiSampleType(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_CheckDeviceMultiSampleType)((cpu),(self),##__VA_ARGS__)
#define XM_CheckDepthStencilMatch(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_CheckDepthStencilMatch)((cpu),(self),##__VA_ARGS__)
#define XM_GetDeviceCaps(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_GetDeviceCaps,D8Device*:xm_D8Device_GetDeviceCaps)((cpu),(self),##__VA_ARGS__)
#define XM_GetAdapterMonitor(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_GetAdapterMonitor)((cpu),(self),##__VA_ARGS__)
#define XM_CreateDevice(cpu,self,...) _Generic((self),D8Interface*:xm_D8Interface_CreateDevice,IDirectInput8W*:xm_IDirectInput8W_CreateDevice)((cpu),(self),##__VA_ARGS__)
#define XM_TestCooperativeLevel(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_TestCooperativeLevel)((cpu),(self),##__VA_ARGS__)
#define XM_GetAvailableTextureMem(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetAvailableTextureMem)((cpu),(self),##__VA_ARGS__)
#define XM_ResourceManagerDiscardBytes(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_ResourceManagerDiscardBytes)((cpu),(self),##__VA_ARGS__)
#define XM_GetDirect3D(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetDirect3D)((cpu),(self),##__VA_ARGS__)
#define XM_GetDisplayMode(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetDisplayMode)((cpu),(self),##__VA_ARGS__)
#define XM_GetCreationParameters(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetCreationParameters)((cpu),(self),##__VA_ARGS__)
#define XM_Present(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_Present)((cpu),(self),##__VA_ARGS__)
#define XM_GetBackBuffer(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetBackBuffer)((cpu),(self),##__VA_ARGS__)
#define XM_SetGammaRamp(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetGammaRamp)((cpu),(self),##__VA_ARGS__)
#define XM_GetGammaRamp(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetGammaRamp)((cpu),(self),##__VA_ARGS__)
#define XM_CreateTexture(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateTexture)((cpu),(self),##__VA_ARGS__)
#define XM_CreateVertexBuffer(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateVertexBuffer)((cpu),(self),##__VA_ARGS__)
#define XM_CreateIndexBuffer(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateIndexBuffer)((cpu),(self),##__VA_ARGS__)
#define XM_CreateRenderTarget(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateRenderTarget)((cpu),(self),##__VA_ARGS__)
#define XM_CreateDepthStencilSurface(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateDepthStencilSurface)((cpu),(self),##__VA_ARGS__)
#define XM_CreateImageSurface(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateImageSurface)((cpu),(self),##__VA_ARGS__)
#define XM_CopyRects(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CopyRects)((cpu),(self),##__VA_ARGS__)
#define XM_UpdateTexture(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_UpdateTexture)((cpu),(self),##__VA_ARGS__)
#define XM_GetFrontBuffer(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetFrontBuffer)((cpu),(self),##__VA_ARGS__)
#define XM_SetRenderTarget(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetRenderTarget)((cpu),(self),##__VA_ARGS__)
#define XM_GetRenderTarget(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetRenderTarget)((cpu),(self),##__VA_ARGS__)
#define XM_GetDepthStencilSurface(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetDepthStencilSurface)((cpu),(self),##__VA_ARGS__)
#define XM_BeginScene(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_BeginScene)((cpu),(self),##__VA_ARGS__)
#define XM_EndScene(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_EndScene)((cpu),(self),##__VA_ARGS__)
#define XM_Clear(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_Clear)((cpu),(self),##__VA_ARGS__)
#define XM_SetTransform(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetTransform)((cpu),(self),##__VA_ARGS__)
#define XM_GetTransform(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetTransform)((cpu),(self),##__VA_ARGS__)
#define XM_SetViewport(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetViewport)((cpu),(self),##__VA_ARGS__)
#define XM_GetViewport(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetViewport)((cpu),(self),##__VA_ARGS__)
#define XM_SetMaterial(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetMaterial)((cpu),(self),##__VA_ARGS__)
#define XM_SetRenderState(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetRenderState)((cpu),(self),##__VA_ARGS__)
#define XM_GetRenderState(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetRenderState)((cpu),(self),##__VA_ARGS__)
#define XM_GetTexture(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetTexture)((cpu),(self),##__VA_ARGS__)
#define XM_SetTexture(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetTexture)((cpu),(self),##__VA_ARGS__)
#define XM_GetTextureStageState(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetTextureStageState)((cpu),(self),##__VA_ARGS__)
#define XM_SetTextureStageState(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetTextureStageState)((cpu),(self),##__VA_ARGS__)
#define XM_DrawPrimitive(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_DrawPrimitive)((cpu),(self),##__VA_ARGS__)
#define XM_DrawIndexedPrimitive(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_DrawIndexedPrimitive)((cpu),(self),##__VA_ARGS__)
#define XM_DrawPrimitiveUP(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_DrawPrimitiveUP)((cpu),(self),##__VA_ARGS__)
#define XM_DrawIndexedPrimitiveUP(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_DrawIndexedPrimitiveUP)((cpu),(self),##__VA_ARGS__)
#define XM_CreateVertexShader(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_CreateVertexShader)((cpu),(self),##__VA_ARGS__)
#define XM_SetVertexShader(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetVertexShader)((cpu),(self),##__VA_ARGS__)
#define XM_GetVertexShader(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetVertexShader)((cpu),(self),##__VA_ARGS__)
#define XM_DeleteVertexShader(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_DeleteVertexShader)((cpu),(self),##__VA_ARGS__)
#define XM_SetStreamSource(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetStreamSource)((cpu),(self),##__VA_ARGS__)
#define XM_GetStreamSource(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetStreamSource)((cpu),(self),##__VA_ARGS__)
#define XM_SetIndices(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_SetIndices)((cpu),(self),##__VA_ARGS__)
#define XM_GetIndices(cpu,self,...) _Generic((self),D8Device*:xm_D8Device_GetIndices)((cpu),(self),##__VA_ARGS__)
#define XM_GetDevice(cpu,self,...) _Generic((self),D8Unknown*:xm_D8Unknown_GetDevice,D8Surface*:xm_D8Surface_GetDevice,D8Texture*:xm_D8Texture_GetDevice,D8Buffer*:xm_D8Buffer_GetDevice)((cpu),(self),##__VA_ARGS__)
#define XM_GetContainer(cpu,self,...) _Generic((self),D8Surface*:xm_D8Surface_GetContainer)((cpu),(self),##__VA_ARGS__)
#define XM_GetDesc(cpu,self,...) _Generic((self),D8Surface*:xm_D8Surface_GetDesc,D8Buffer*:xm_D8Buffer_GetDesc)((cpu),(self),##__VA_ARGS__)
#define XM_LockRect(cpu,self,...) _Generic((self),D8Surface*:xm_D8Surface_LockRect,D8Texture*:xm_D8Texture_LockRect)((cpu),(self),##__VA_ARGS__)
#define XM_UnlockRect(cpu,self,...) _Generic((self),D8Surface*:xm_D8Surface_UnlockRect,D8Texture*:xm_D8Texture_UnlockRect)((cpu),(self),##__VA_ARGS__)
#define XM_SetPriority(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_SetPriority,D8Buffer*:xm_D8Buffer_SetPriority)((cpu),(self),##__VA_ARGS__)
#define XM_GetPriority(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_GetPriority,D8Buffer*:xm_D8Buffer_GetPriority)((cpu),(self),##__VA_ARGS__)
#define XM_PreLoad(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_PreLoad,D8Buffer*:xm_D8Buffer_PreLoad)((cpu),(self),##__VA_ARGS__)
#define XM_GetType(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_GetType,D8Buffer*:xm_D8Buffer_GetType)((cpu),(self),##__VA_ARGS__)
#define XM_SetLOD(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_SetLOD)((cpu),(self),##__VA_ARGS__)
#define XM_GetLOD(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_GetLOD)((cpu),(self),##__VA_ARGS__)
#define XM_GetLevelCount(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_GetLevelCount)((cpu),(self),##__VA_ARGS__)
#define XM_GetLevelDesc(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_GetLevelDesc)((cpu),(self),##__VA_ARGS__)
#define XM_GetSurfaceLevel(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_GetSurfaceLevel)((cpu),(self),##__VA_ARGS__)
#define XM_AddDirtyRect(cpu,self,...) _Generic((self),D8Texture*:xm_D8Texture_AddDirtyRect)((cpu),(self),##__VA_ARGS__)
#define XM_Lock(cpu,self,...) _Generic((self),D8Buffer*:xm_D8Buffer_Lock)((cpu),(self),##__VA_ARGS__)
#define XM_Unlock(cpu,self,...) _Generic((self),D8Buffer*:xm_D8Buffer_Unlock)((cpu),(self),##__VA_ARGS__)
#define XM_SetProperty(cpu,self,...) _Generic((self),IDirectInputDevice8W*:xm_IDirectInputDevice8W_SetProperty)((cpu),(self),##__VA_ARGS__)
#define XM_Acquire(cpu,self,...) _Generic((self),IDirectInputDevice8W*:xm_IDirectInputDevice8W_Acquire)((cpu),(self),##__VA_ARGS__)
#define XM_Unacquire(cpu,self,...) _Generic((self),IDirectInputDevice8W*:xm_IDirectInputDevice8W_Unacquire)((cpu),(self),##__VA_ARGS__)
#define XM_GetDeviceData(cpu,self,...) _Generic((self),IDirectInputDevice8W*:xm_IDirectInputDevice8W_GetDeviceData)((cpu),(self),##__VA_ARGS__)
#define XM_SetDataFormat(cpu,self,...) _Generic((self),IDirectInputDevice8W*:xm_IDirectInputDevice8W_SetDataFormat)((cpu),(self),##__VA_ARGS__)
#define XM_SetCooperativeLevel(cpu,self,...) _Generic((self),IDirectInputDevice8W*:xm_IDirectInputDevice8W_SetCooperativeLevel)((cpu),(self),##__VA_ARGS__)
#endif

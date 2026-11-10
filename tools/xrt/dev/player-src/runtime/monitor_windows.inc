#ifndef XM_WINDOWS_WRAPPERS
#define XM_WINDOWS_WRAPPERS
#include <windows.h>
#include <imm.h>
#include <objbase.h>
#include "monitor.h"
static BOOL xm_win_AdjustWindowRect(LPRECT a0, DWORD a1, BOOL a2) {
 if(xm_quiet)return AdjustWindowRect(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.AdjustWindowRect";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 if(a0)xm_span(c,"WIN.AdjustWindowRect.input0",a0,sizeof(RECT));
 ret=AdjustWindowRect(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 if(ret && a0)xm_span(c,"WIN.AdjustWindowRect.output0",a0,sizeof(RECT));
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_AttachThreadInput(DWORD a0, DWORD a1, BOOL a2) {
 if(xm_quiet)return AttachThreadInput(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.AttachThreadInput";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=AttachThreadInput(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LRESULT xm_win_CallWindowProcA(WNDPROC a0, HWND a1, UINT a2, WPARAM a3, LPARAM a4) {
 if(xm_quiet)return CallWindowProcA(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CallWindowProcA";q.count=5;
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
 ret=CallWindowProcA(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LRESULT xm_win_CallWindowProcW(WNDPROC a0, HWND a1, UINT a2, WPARAM a3, LPARAM a4) {
 if(xm_quiet)return CallWindowProcW(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CallWindowProcW";q.count=5;
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
 ret=CallWindowProcW(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_ClipCursor(const RECT * a0) {
 if(xm_quiet)return ClipCursor(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.ClipCursor";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=ClipCursor(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HRESULT xm_win_CoCreateInstance(const IID * const a0, LPUNKNOWN a1, DWORD a2, const IID * const a3, LPVOID * a4) {
 if(xm_quiet)return CoCreateInstance(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CoCreateInstance";q.count=5;
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
 if(a0)xm_span(c,"WIN.CoCreateInstance.input0",a0,sizeof(GUID));
 if(a3)xm_span(c,"WIN.CoCreateInstance.input3",a3,sizeof(GUID));
 ret=CoCreateInstance(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 if(SUCCEEDED(ret) && a4)xm_span(c,"WIN.CoCreateInstance.output4",a4,sizeof(void*));
 xm_probe(c,&q);
 return ret;
}
static HRESULT xm_win_CoGetApartmentType(APTTYPE* a0, APTTYPEQUALIFIER* a1) {
 if(xm_quiet)return CoGetApartmentType(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CoGetApartmentType";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=CoGetApartmentType(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HRESULT xm_win_CoInitialize(LPVOID a0) {
 if(xm_quiet)return CoInitialize(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CoInitialize";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=CoInitialize(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HRESULT xm_win_CoInitializeEx(LPVOID a0, DWORD a1) {
 if(xm_quiet)return CoInitializeEx(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CoInitializeEx";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=CoInitializeEx(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static void xm_win_CoUninitialize(void) {
 if(xm_quiet){CoUninitialize();return;}   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CoUninitialize";q.count=0;
 xm_probe(c,&q);
 CoUninitialize();
 q.event=XM_END;q.result=0;
 xm_probe(c,&q);
}
static HBITMAP xm_win_CreateBitmap(int a0, int a1, UINT a2, UINT a3, const void * a4) {
 if(xm_quiet)return CreateBitmap(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HBITMAP ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateBitmap";q.count=5;
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
 ret=CreateBitmap(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HBITMAP xm_win_CreateDIBitmap(HDC a0, const BITMAPINFOHEADER * a1, DWORD a2, const void * a3, const BITMAPINFO * a4, UINT a5) {
 if(xm_quiet)return CreateDIBitmap(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HBITMAP ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateDIBitmap";q.count=6;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 ret=CreateDIBitmap(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_CreateDialogParamA(HINSTANCE a0, LPCSTR a1, HWND a2, DLGPROC a3, LPARAM a4) {
 if(xm_quiet)return CreateDialogParamA(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateDialogParamA";q.count=5;
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
 ret=CreateDialogParamA(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_CreateDialogParamW(HINSTANCE a0, LPCWSTR a1, HWND a2, DLGPROC a3, LPARAM a4) {
 if(xm_quiet)return CreateDialogParamW(a0,a1,a2,a3,a4);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateDialogParamW";q.count=5;
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
 ret=CreateDialogParamW(a0,a1,a2,a3,a4);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HBRUSH xm_win_CreatePatternBrush(HBITMAP a0) {
 if(xm_quiet)return CreatePatternBrush(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HBRUSH ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreatePatternBrush";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=CreatePatternBrush(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HBRUSH xm_win_CreateSolidBrush(COLORREF a0) {
 if(xm_quiet)return CreateSolidBrush(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HBRUSH ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateSolidBrush";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=CreateSolidBrush(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_CreateWindowExA(DWORD a0, LPCSTR a1, LPCSTR a2, DWORD a3, int a4, int a5, int a6, int a7, HWND a8, HMENU a9, HINSTANCE a10, LPVOID a11) {
 if(xm_quiet)return CreateWindowExA(a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateWindowExA";q.count=12;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 q.values[7].type=XM_OPAQUE;q.values[7].bytes=sizeof(a7);
 q.values[7].value=(uint64_t)(uintptr_t)a7;
 q.values[8].type=XM_OPAQUE;q.values[8].bytes=sizeof(a8);
 q.values[8].value=(uint64_t)(uintptr_t)a8;
 q.values[9].type=XM_OPAQUE;q.values[9].bytes=sizeof(a9);
 q.values[9].value=(uint64_t)(uintptr_t)a9;
 q.values[10].type=XM_OPAQUE;q.values[10].bytes=sizeof(a10);
 q.values[10].value=(uint64_t)(uintptr_t)a10;
 q.values[11].type=XM_OPAQUE;q.values[11].bytes=sizeof(a11);
 q.values[11].value=(uint64_t)(uintptr_t)a11;
 xm_probe(c,&q);
 ret=CreateWindowExA(a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_CreateWindowExW(DWORD a0, LPCWSTR a1, LPCWSTR a2, DWORD a3, int a4, int a5, int a6, int a7, HWND a8, HMENU a9, HINSTANCE a10, LPVOID a11) {
 if(xm_quiet)return CreateWindowExW(a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.CreateWindowExW";q.count=12;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 q.values[7].type=XM_OPAQUE;q.values[7].bytes=sizeof(a7);
 q.values[7].value=(uint64_t)(uintptr_t)a7;
 q.values[8].type=XM_OPAQUE;q.values[8].bytes=sizeof(a8);
 q.values[8].value=(uint64_t)(uintptr_t)a8;
 q.values[9].type=XM_OPAQUE;q.values[9].bytes=sizeof(a9);
 q.values[9].value=(uint64_t)(uintptr_t)a9;
 q.values[10].type=XM_OPAQUE;q.values[10].bytes=sizeof(a10);
 q.values[10].value=(uint64_t)(uintptr_t)a10;
 q.values[11].type=XM_OPAQUE;q.values[11].bytes=sizeof(a11);
 q.values[11].value=(uint64_t)(uintptr_t)a11;
 xm_probe(c,&q);
 ret=CreateWindowExW(a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LRESULT xm_win_DefWindowProcA(HWND a0, UINT a1, WPARAM a2, LPARAM a3) {
 if(xm_quiet)return DefWindowProcA(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.DefWindowProcA";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=DefWindowProcA(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LRESULT xm_win_DefWindowProcW(HWND a0, UINT a1, WPARAM a2, LPARAM a3) {
 if(xm_quiet)return DefWindowProcW(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.DefWindowProcW";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=DefWindowProcW(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_DeleteObject(HGDIOBJ a0) {
 if(xm_quiet)return DeleteObject(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.DeleteObject";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=DeleteObject(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_DestroyWindow(HWND a0) {
 if(xm_quiet)return DestroyWindow(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.DestroyWindow";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=DestroyWindow(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_FreeLibrary(HMODULE a0) {
 if(xm_quiet)return FreeLibrary(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.FreeLibrary";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=FreeLibrary(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_GetActiveWindow(void) {
 if(xm_quiet)return GetActiveWindow();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetActiveWindow";q.count=0;
 xm_probe(c,&q);
 ret=GetActiveWindow();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_support_GetActiveWindow(void) {
 if(xm_quiet)return GetActiveWindow();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetActiveWindow";q.count=0;
 xm_probe(c,&q);
 ret=GetActiveWindow();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_GetClassInfoExA(HINSTANCE a0, LPCSTR a1, LPWNDCLASSEXA a2) {
 if(xm_quiet)return GetClassInfoExA(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetClassInfoExA";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetClassInfoExA(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 if(ret && a2)xm_span(c,"WIN.GetClassInfoExA.output2",a2,sizeof(WNDCLASSEXA));
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_GetClassInfoExW(HINSTANCE a0, LPCWSTR a1, LPWNDCLASSEXW a2) {
 if(xm_quiet)return GetClassInfoExW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetClassInfoExW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetClassInfoExW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 if(ret && a2)xm_span(c,"WIN.GetClassInfoExW.output2",a2,sizeof(WNDCLASSEXW));
 xm_probe(c,&q);
 return ret;
}
static ULONG_PTR xm_win_GetClassLongPtrW(HWND a0, int a1) {
 if(xm_quiet)return GetClassLongPtrW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};ULONG_PTR ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetClassLongPtrW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetClassLongPtrW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_GetClientRect(HWND a0, LPRECT a1) {
 if(xm_quiet)return GetClientRect(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetClientRect";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetClientRect(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 if(ret && a1)xm_span(c,"WIN.GetClientRect.output1",a1,sizeof(RECT));
 xm_probe(c,&q);
 return ret;
}
static int xm_win_GetClipboardFormatNameW(UINT a0, LPWSTR a1, int a2) {
 if(xm_quiet)return GetClipboardFormatNameW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetClipboardFormatNameW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetClipboardFormatNameW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_support_GetClipboardFormatNameW(UINT a0, LPWSTR a1, int a2) {
 if(xm_quiet)return GetClipboardFormatNameW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetClipboardFormatNameW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetClipboardFormatNameW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetCurrentProcessId(void) {
 if(xm_quiet)return GetCurrentProcessId();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetCurrentProcessId";q.count=0;
 xm_probe(c,&q);
 ret=GetCurrentProcessId();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_support_GetCurrentProcessId(void) {
 if(xm_quiet)return GetCurrentProcessId();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetCurrentProcessId";q.count=0;
 xm_probe(c,&q);
 ret=GetCurrentProcessId();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetCurrentThreadId(void) {
 if(xm_quiet)return GetCurrentThreadId();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetCurrentThreadId";q.count=0;
 xm_probe(c,&q);
 ret=GetCurrentThreadId();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_support_GetCurrentThreadId(void) {
 if(xm_quiet)return GetCurrentThreadId();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetCurrentThreadId";q.count=0;
 xm_probe(c,&q);
 ret=GetCurrentThreadId();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HDC xm_win_GetDC(HWND a0) {
 if(xm_quiet)return GetDC(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HDC ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetDC";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=GetDC(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_GetDIBits(HDC a0, HBITMAP a1, UINT a2, UINT a3, LPVOID a4, LPBITMAPINFO a5, UINT a6) {
 if(xm_quiet)return GetDIBits(a0,a1,a2,a3,a4,a5,a6);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetDIBits";q.count=7;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 xm_probe(c,&q);
 ret=GetDIBits(a0,a1,a2,a3,a4,a5,a6);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_GetDesktopWindow(void) {
 if(xm_quiet)return GetDesktopWindow();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetDesktopWindow";q.count=0;
 xm_probe(c,&q);
 ret=GetDesktopWindow();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_GetDeviceCaps(HDC a0, int a1) {
 if(xm_quiet)return GetDeviceCaps(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetDeviceCaps";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetDeviceCaps(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_GetDlgItem(HWND a0, int a1) {
 if(xm_quiet)return GetDlgItem(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetDlgItem";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetDlgItem(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_GetFocus(void) {
 if(xm_quiet)return GetFocus();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetFocus";q.count=0;
 xm_probe(c,&q);
 ret=GetFocus();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_support_GetFocus(void) {
 if(xm_quiet)return GetFocus();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetFocus";q.count=0;
 xm_probe(c,&q);
 ret=GetFocus();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_GetForegroundWindow(void) {
 if(xm_quiet)return GetForegroundWindow();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetForegroundWindow";q.count=0;
 xm_probe(c,&q);
 ret=GetForegroundWindow();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_support_GetForegroundWindow(void) {
 if(xm_quiet)return GetForegroundWindow();   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetForegroundWindow";q.count=0;
 xm_probe(c,&q);
 ret=GetForegroundWindow();
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetFullPathNameW(LPCWSTR a0, DWORD a1, LPWSTR a2, LPWSTR* a3) {
 if(xm_quiet)return GetFullPathNameW(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetFullPathNameW";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=GetFullPathNameW(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static SHORT xm_win_GetKeyState(int a0) {
 if(xm_quiet)return GetKeyState(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};SHORT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetKeyState";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=GetKeyState(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetModuleFileNameW(HMODULE a0, LPWSTR a1, DWORD a2) {
 if(xm_quiet)return GetModuleFileNameW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetModuleFileNameW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetModuleFileNameW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_support_GetModuleFileNameW(HMODULE a0, LPWSTR a1, DWORD a2) {
 if(xm_quiet)return GetModuleFileNameW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetModuleFileNameW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetModuleFileNameW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_GetModuleHandleExW(DWORD a0, LPCWSTR a1, HMODULE* a2) {
 if(xm_quiet)return GetModuleHandleExW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetModuleHandleExW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetModuleHandleExW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_support_GetModuleHandleExW(DWORD a0, LPCWSTR a1, HMODULE* a2) {
 if(xm_quiet)return GetModuleHandleExW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetModuleHandleExW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=GetModuleHandleExW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetObjectType(HGDIOBJ a0) {
 if(xm_quiet)return GetObjectType(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetObjectType";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=GetObjectType(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static FARPROC xm_win_GetProcAddress(HMODULE a0, LPCSTR a1) {
 if(xm_quiet)return GetProcAddress(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};FARPROC ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetProcAddress";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetProcAddress(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetProcessId(HANDLE a0) {
 if(xm_quiet)return GetProcessId(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetProcessId";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=GetProcessId(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HANDLE xm_win_GetPropA(HWND a0, LPCSTR a1) {
 if(xm_quiet)return GetPropA(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HANDLE ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetPropA";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetPropA(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HANDLE xm_win_GetPropW(HWND a0, LPCWSTR a1) {
 if(xm_quiet)return GetPropW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HANDLE ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetPropW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetPropW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HGDIOBJ xm_win_GetStockObject(int a0) {
 if(xm_quiet)return GetStockObject(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HGDIOBJ ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetStockObject";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=GetStockObject(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_GetSystemMetrics(int a0) {
 if(xm_quiet)return GetSystemMetrics(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetSystemMetrics";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=GetSystemMetrics(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LONG xm_win_GetWindowLongA(HWND a0, int a1) {
 if(xm_quiet)return GetWindowLongA(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetWindowLongA";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowLongA(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LONG_PTR xm_win_GetWindowLongPtrW(HWND a0, int a1) {
 if(xm_quiet)return GetWindowLongPtrW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LONG_PTR ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetWindowLongPtrW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowLongPtrW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LONG_PTR xm_support_GetWindowLongPtrW(HWND a0, int a1) {
 if(xm_quiet)return GetWindowLongPtrW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LONG_PTR ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetWindowLongPtrW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowLongPtrW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LONG xm_win_GetWindowLongW(HWND a0, int a1) {
 if(xm_quiet)return GetWindowLongW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetWindowLongW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowLongW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_GetWindowRect(HWND a0, LPRECT a1) {
 if(xm_quiet)return GetWindowRect(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetWindowRect";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowRect(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 if(ret && a1)xm_span(c,"WIN.GetWindowRect.output1",a1,sizeof(RECT));
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_GetWindowThreadProcessId(HWND a0, LPDWORD a1) {
 if(xm_quiet)return GetWindowThreadProcessId(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.GetWindowThreadProcessId";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowThreadProcessId(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_support_GetWindowThreadProcessId(HWND a0, LPDWORD a1) {
 if(xm_quiet)return GetWindowThreadProcessId(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.GetWindowThreadProcessId";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=GetWindowThreadProcessId(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HIMC xm_win_ImmAssociateContext(HWND a0, HIMC a1) {
 if(xm_quiet)return ImmAssociateContext(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HIMC ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.ImmAssociateContext";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=ImmAssociateContext(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_InSendMessageEx(LPVOID a0) {
 if(xm_quiet)return InSendMessageEx(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.InSendMessageEx";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=InSendMessageEx(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_support_InSendMessageEx(LPVOID a0) {
 if(xm_quiet)return InSendMessageEx(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.InSendMessageEx";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=InSendMessageEx(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_IsWindow(HWND a0) {
 if(xm_quiet)return IsWindow(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.IsWindow";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=IsWindow(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_IsWindowUnicode(HWND a0) {
 if(xm_quiet)return IsWindowUnicode(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.IsWindowUnicode";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=IsWindowUnicode(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HCURSOR xm_win_LoadCursorA(HINSTANCE a0, LPCSTR a1) {
 if(xm_quiet)return LoadCursorA(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HCURSOR ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.LoadCursorA";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=LoadCursorA(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HCURSOR xm_win_LoadCursorW(HINSTANCE a0, LPCWSTR a1) {
 if(xm_quiet)return LoadCursorW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HCURSOR ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.LoadCursorW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=LoadCursorW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HICON xm_win_LoadIconA(HINSTANCE a0, LPCSTR a1) {
 if(xm_quiet)return LoadIconA(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HICON ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.LoadIconA";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=LoadIconA(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HICON xm_win_LoadIconW(HINSTANCE a0, LPCWSTR a1) {
 if(xm_quiet)return LoadIconW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HICON ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.LoadIconW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=LoadIconW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HMODULE xm_win_LoadLibraryExW(LPCWSTR a0, HANDLE a1, DWORD a2) {
 if(xm_quiet)return LoadLibraryExW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HMODULE ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.LoadLibraryExW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=LoadLibraryExW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_MapWindowPoints(HWND a0, HWND a1, LPPOINT a2, UINT a3) {
 if(xm_quiet)return MapWindowPoints(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.MapWindowPoints";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=MapWindowPoints(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_MoveWindow(HWND a0, int a1, int a2, int a3, int a4, BOOL a5) {
 if(xm_quiet)return MoveWindow(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.MoveWindow";q.count=6;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 ret=MoveWindow(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_MultiByteToWideChar(UINT a0, DWORD a1, LPCCH a2, int a3, LPWSTR a4, int a5) {
 if(xm_quiet)return MultiByteToWideChar(a0,a1,a2,a3,a4,a5);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.MultiByteToWideChar";q.count=6;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 xm_probe(c,&q);
 ret=MultiByteToWideChar(a0,a1,a2,a3,a4,a5);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_PostMessageA(HWND a0, UINT a1, WPARAM a2, LPARAM a3) {
 if(xm_quiet)return PostMessageA(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.PostMessageA";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=PostMessageA(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_PostMessageW(HWND a0, UINT a1, WPARAM a2, LPARAM a3) {
 if(xm_quiet)return PostMessageW(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.PostMessageW";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=PostMessageW(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_QueryPerformanceCounter(LARGE_INTEGER* a0) {
 if(xm_quiet)return QueryPerformanceCounter(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.QueryPerformanceCounter";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=QueryPerformanceCounter(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_support_QueryPerformanceCounter(LARGE_INTEGER* a0) {
 if(xm_quiet)return QueryPerformanceCounter(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_SUPPORT;q.name="PROBE.QueryPerformanceCounter";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=QueryPerformanceCounter(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static ATOM xm_win_RegisterClassExA(const WNDCLASSEXA * a0) {
 if(xm_quiet)return RegisterClassExA(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};ATOM ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.RegisterClassExA";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 if(a0)xm_span(c,"WIN.RegisterClassExA.input0",a0,sizeof(WNDCLASSEXA));
 ret=RegisterClassExA(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static ATOM xm_win_RegisterClassExW(const WNDCLASSEXW * a0) {
 if(xm_quiet)return RegisterClassExW(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};ATOM ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.RegisterClassExW";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 if(a0)xm_span(c,"WIN.RegisterClassExW.input0",a0,sizeof(WNDCLASSEXW));
 ret=RegisterClassExW(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_ReleaseDC(HWND a0, HDC a1) {
 if(xm_quiet)return ReleaseDC(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.ReleaseDC";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=ReleaseDC(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HANDLE xm_win_RemovePropA(HWND a0, LPCSTR a1) {
 if(xm_quiet)return RemovePropA(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HANDLE ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.RemovePropA";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=RemovePropA(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HANDLE xm_win_RemovePropW(HWND a0, LPCWSTR a1) {
 if(xm_quiet)return RemovePropW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HANDLE ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.RemovePropW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=RemovePropW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LRESULT xm_win_SendMessageA(HWND a0, UINT a1, WPARAM a2, LPARAM a3) {
 if(xm_quiet)return SendMessageA(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SendMessageA";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=SendMessageA(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LRESULT xm_win_SendMessageW(HWND a0, UINT a1, WPARAM a2, LPARAM a3) {
 if(xm_quiet)return SendMessageW(a0,a1,a2,a3);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LRESULT ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SendMessageW";q.count=4;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 q.values[3].type=XM_OPAQUE;q.values[3].bytes=sizeof(a3);
 q.values[3].value=(uint64_t)(uintptr_t)a3;
 xm_probe(c,&q);
 ret=SendMessageW(a0,a1,a2,a3);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_SetActiveWindow(HWND a0) {
 if(xm_quiet)return SetActiveWindow(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetActiveWindow";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=SetActiveWindow(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_SetCapture(HWND a0) {
 if(xm_quiet)return SetCapture(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetCapture";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=SetCapture(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HCURSOR xm_win_SetCursor(HCURSOR a0) {
 if(xm_quiet)return SetCursor(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HCURSOR ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetCursor";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=SetCursor(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static HWND xm_win_SetFocus(HWND a0) {
 if(xm_quiet)return SetFocus(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};HWND ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetFocus";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=SetFocus(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_SetForegroundWindow(HWND a0) {
 if(xm_quiet)return SetForegroundWindow(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetForegroundWindow";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=SetForegroundWindow(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_SetKeyboardState(LPBYTE a0) {
 if(xm_quiet)return SetKeyboardState(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetKeyboardState";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=SetKeyboardState(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_SetMenu(HWND a0, HMENU a1) {
 if(xm_quiet)return SetMenu(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetMenu";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=SetMenu(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_SetPropA(HWND a0, LPCSTR a1, HANDLE a2) {
 if(xm_quiet)return SetPropA(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetPropA";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=SetPropA(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_SetPropW(HWND a0, LPCWSTR a1, HANDLE a2) {
 if(xm_quiet)return SetPropW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetPropW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=SetPropW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LONG xm_win_SetWindowLongA(HWND a0, int a1, LONG a2) {
 if(xm_quiet)return SetWindowLongA(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetWindowLongA";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=SetWindowLongA(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static LONG xm_win_SetWindowLongW(HWND a0, int a1, LONG a2) {
 if(xm_quiet)return SetWindowLongW(a0,a1,a2);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};LONG ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetWindowLongW";q.count=3;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 q.values[2].type=XM_OPAQUE;q.values[2].bytes=sizeof(a2);
 q.values[2].value=(uint64_t)(uintptr_t)a2;
 xm_probe(c,&q);
 ret=SetWindowLongW(a0,a1,a2);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_SetWindowPos(HWND a0, HWND a1, int a2, int a3, int a4, int a5, UINT a6) {
 if(xm_quiet)return SetWindowPos(a0,a1,a2,a3,a4,a5,a6);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.SetWindowPos";q.count=7;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 xm_probe(c,&q);
 ret=SetWindowPos(a0,a1,a2,a3,a4,a5,a6);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_ShowWindow(HWND a0, int a1) {
 if(xm_quiet)return ShowWindow(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.ShowWindow";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=ShowWindow(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_UnregisterClassA(LPCSTR a0, HINSTANCE a1) {
 if(xm_quiet)return UnregisterClassA(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.UnregisterClassA";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=UnregisterClassA(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_UnregisterClassW(LPCWSTR a0, HINSTANCE a1) {
 if(xm_quiet)return UnregisterClassW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.UnregisterClassW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=UnregisterClassW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static BOOL xm_win_UpdateWindow(HWND a0) {
 if(xm_quiet)return UpdateWindow(a0);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};BOOL ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.UpdateWindow";q.count=1;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 xm_probe(c,&q);
 ret=UpdateWindow(a0);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static DWORD xm_win_WaitForSingleObject(HANDLE a0, DWORD a1) {
 if(xm_quiet)return WaitForSingleObject(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};DWORD ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.WaitForSingleObject";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=WaitForSingleObject(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_WideCharToMultiByte(UINT a0, DWORD a1, LPCWCH a2, int a3, LPSTR a4, int a5, LPCCH a6, LPBOOL a7) {
 if(xm_quiet)return WideCharToMultiByte(a0,a1,a2,a3,a4,a5,a6,a7);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.WideCharToMultiByte";q.count=8;
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
 q.values[5].type=XM_OPAQUE;q.values[5].bytes=sizeof(a5);
 q.values[5].value=(uint64_t)(uintptr_t)a5;
 q.values[6].type=XM_OPAQUE;q.values[6].bytes=sizeof(a6);
 q.values[6].value=(uint64_t)(uintptr_t)a6;
 q.values[7].type=XM_OPAQUE;q.values[7].bytes=sizeof(a7);
 q.values[7].value=(uint64_t)(uintptr_t)a7;
 xm_probe(c,&q);
 ret=WideCharToMultiByte(a0,a1,a2,a3,a4,a5,a6,a7);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
static int xm_win_lstrcmpW(LPCWSTR a0, LPCWSTR a1) {
 if(xm_quiet)return lstrcmpW(a0,a1);   /* quiet profile: every record below is dropped (round 4) */
 CPU*c=xm_current_cpu();XmRequest q={0};int ret;
 q.event=XM_BEGIN;q.domain=XM_NATIVE;q.name="WIN.lstrcmpW";q.count=2;
 q.values[0].type=XM_OPAQUE;q.values[0].bytes=sizeof(a0);
 q.values[0].value=(uint64_t)(uintptr_t)a0;
 q.values[1].type=XM_OPAQUE;q.values[1].bytes=sizeof(a1);
 q.values[1].value=(uint64_t)(uintptr_t)a1;
 xm_probe(c,&q);
 ret=lstrcmpW(a0,a1);
 q.event=XM_END;q.result=(uint64_t)(uintptr_t)ret;
 xm_probe(c,&q);
 return ret;
}
#endif

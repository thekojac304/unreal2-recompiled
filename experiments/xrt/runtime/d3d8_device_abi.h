/* Native slots through measured SetRenderState. Never install in guest memory. */
#ifndef XRT_D3D8_DEVICE_ABI_H
#define XRT_D3D8_DEVICE_ABI_H
#include "d3d8_abi.h"
typedef struct D8Creation { UINT adapter,type; HWND focus; DWORD flags; } D8Creation;
typedef struct D8Rect { LONG left,top,right,bottom; } D8Rect;
typedef struct D8DeviceVtable {
    HRESULT (WINAPI *QueryInterface)(D8Device*,REFIID,void**);
    ULONG (WINAPI *AddRef)(D8Device*);
    ULONG (WINAPI *Release)(D8Device*);
    HRESULT (WINAPI *TestCooperativeLevel)(D8Device*);
    UINT (WINAPI *GetAvailableTextureMem)(D8Device*);
    HRESULT (WINAPI *ResourceManagerDiscardBytes)(D8Device*,DWORD);
    HRESULT (WINAPI *GetDirect3D)(D8Device*,D8Interface**);
    HRESULT (WINAPI *GetDeviceCaps)(D8Device*,D8Caps*);
    HRESULT (WINAPI *GetDisplayMode)(D8Device*,D8Mode*);
    HRESULT (WINAPI *GetCreationParameters)(D8Device*,D8Creation*);
    void* unsupported10_14[5];
    HRESULT (WINAPI *Present)(D8Device*,const RECT*,const RECT*,HWND,const RGNDATA*);
    void* unsupported16_35[20];
    HRESULT (WINAPI *Clear)(D8Device*,DWORD,const D8Rect*,DWORD,DWORD,float,DWORD);
    void* unsupported37_49[13];
    HRESULT (WINAPI *SetRenderState)(D8Device*,DWORD,DWORD);
} D8DeviceVtable;
struct D8Device { const D8DeviceVtable *vt; };
typedef char d8_present_size[sizeof(D8Present)==(sizeof(void*)==4?52:56)?1:-1];
typedef char d8_present_window[offsetof(D8Present,window)==24?1:-1];
typedef char d8_present_windowed[offsetof(D8Present,windowed)==(sizeof(void*)==4?28:32)?1:-1];
typedef char d8_present_interval[offsetof(D8Present,interval)==(sizeof(void*)==4?48:52)?1:-1];
typedef char d8_creation_size[sizeof(D8Creation)==(sizeof(void*)==4?16:24)?1:-1];
typedef char d8_creation_flags[offsetof(D8Creation,flags)==(sizeof(void*)==4?12:16)?1:-1];
typedef char d8_device_creation_slot[offsetof(D8DeviceVtable,GetCreationParameters)==9*sizeof(void*)?1:-1];
typedef char d8_device_present_slot[offsetof(D8DeviceVtable,Present)==15*sizeof(void*)?1:-1];
typedef char d8_device_clear_slot[offsetof(D8DeviceVtable,Clear)==36*sizeof(void*)?1:-1];
typedef char d8_device_state_slot[offsetof(D8DeviceVtable,SetRenderState)==50*sizeof(void*)?1:-1];
typedef char d8_rect_size[sizeof(D8Rect)==16?1:-1];
#endif

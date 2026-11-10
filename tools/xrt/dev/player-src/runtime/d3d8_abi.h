/* The pointer-free D3D8 query ABI, plus the sixteen typed IDirect3D8 slots.
 * The x86 identifier has 1068 bytes; the x64 host has four extra tail-padding
 * bytes. Its meaningful fields have identical offsets. Never copy host padding
 * into the guest. Layout checked against MinGW's D3D8 declarations and DXVK
 * v3.1.1's interface. Numeric enums remain original 32-bit D3D8 enum values. */
#ifndef XRT_D3D8_ABI_H
#define XRT_D3D8_ABI_H
#include <windows.h>
#include <stddef.h>
#define D8_IDENTIFIER_BYTES 1068
#if defined(_M_IX86) || defined(__i386__)
#pragma pack(push,4)
#endif
typedef struct D8Identifier {
    char driver[512], description[512];
    LARGE_INTEGER version;
    DWORD vendor, device, subsystem, revision;
    GUID guid;
    DWORD whql;
} D8Identifier;
typedef struct D8Mode { UINT width,height,refresh,format; } D8Mode;
typedef struct D8Caps { DWORD words[53]; } D8Caps;
typedef struct D8Present {
    UINT width,height,format,count,multisample,swap;
    HWND window;
    BOOL windowed,depth;
    UINT depthformat,flags,refresh,interval;
} D8Present;
#if defined(_M_IX86) || defined(__i386__)
#pragma pack(pop)
#endif
typedef struct D8Interface D8Interface;
typedef struct D8Device D8Device;
typedef struct D8Vtable {
    HRESULT (WINAPI *QueryInterface)(D8Interface*,REFIID,void**);
    ULONG (WINAPI *AddRef)(D8Interface*);
    ULONG (WINAPI *Release)(D8Interface*);
    HRESULT (WINAPI *RegisterSoftwareDevice)(D8Interface*,void*);
    UINT (WINAPI *GetAdapterCount)(D8Interface*);
    HRESULT (WINAPI *GetAdapterIdentifier)(D8Interface*,UINT,DWORD,D8Identifier*);
    UINT (WINAPI *GetAdapterModeCount)(D8Interface*,UINT);
    HRESULT (WINAPI *EnumAdapterModes)(D8Interface*,UINT,UINT,D8Mode*);
    HRESULT (WINAPI *GetAdapterDisplayMode)(D8Interface*,UINT,D8Mode*);
    HRESULT (WINAPI *CheckDeviceType)(D8Interface*,UINT,UINT,UINT,UINT,BOOL);
    HRESULT (WINAPI *CheckDeviceFormat)(D8Interface*,UINT,UINT,UINT,DWORD,UINT,UINT);
    HRESULT (WINAPI *CheckDeviceMultiSampleType)(D8Interface*,UINT,UINT,UINT,BOOL,UINT);
    HRESULT (WINAPI *CheckDepthStencilMatch)(D8Interface*,UINT,UINT,UINT,UINT,UINT);
    HRESULT (WINAPI *GetDeviceCaps)(D8Interface*,UINT,UINT,D8Caps*);
    HMONITOR (WINAPI *GetAdapterMonitor)(D8Interface*,UINT);
    HRESULT (WINAPI *CreateDevice)(D8Interface*,UINT,UINT,HWND,DWORD,D8Present*,D8Device**);
} D8Vtable;
struct D8Interface { const D8Vtable *vt; };
typedef D8Interface* (WINAPI *D8Factory)(UINT);
typedef char d8_id_size_check[sizeof(D8Identifier)==(sizeof(void*)==4?1068:1072)?1:-1];
typedef char d8_id_payload_check[offsetof(D8Identifier,whql)==1064?1:-1];
typedef char d8_caps_size_check[sizeof(D8Caps)==212?1:-1];
typedef char d8_mode_size_check[sizeof(D8Mode)==16?1:-1];
typedef char d8_vtable_size_check[sizeof(D8Vtable)==16*sizeof(void*)?1:-1];
#endif

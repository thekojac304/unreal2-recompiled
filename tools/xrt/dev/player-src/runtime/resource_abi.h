#ifndef XRT_RESOURCE_ABI_H
#define XRT_RESOURCE_ABI_H
/* Native-only layouts. Guest interfaces are four-byte tokens, never these. */
typedef struct D8Unknown D8Unknown;
typedef struct D8Surface D8Surface;
typedef struct D8Texture D8Texture;
typedef struct D8Buffer D8Buffer;
typedef struct D8SurfaceDesc {DWORD format,type,usage,pool,size,multisample,width,height;} D8SurfaceDesc;
typedef struct D8BufferDesc {DWORD format,type,usage,pool,size,fvf;} D8BufferDesc;
typedef struct D8Locked {INT pitch;void*bits;} D8Locked;
#define D8_COMMON(T) HRESULT(WINAPI*QueryInterface)(T*,REFIID,void**); ULONG(WINAPI*AddRef)(T*); ULONG(WINAPI*Release)(T*); HRESULT(WINAPI*GetDevice)(T*,D8Device**)
typedef struct D8UnknownVtable {D8_COMMON(D8Unknown);} D8UnknownVtable;
struct D8Unknown {const D8UnknownVtable*vt;};
typedef struct D8SurfaceVtable {
 D8_COMMON(D8Surface);
 void*private_data[3];
 HRESULT(WINAPI*GetContainer)(D8Surface*,REFIID,void**);
 HRESULT(WINAPI*GetDesc)(D8Surface*,D8SurfaceDesc*);
 HRESULT(WINAPI*LockRect)(D8Surface*,D8Locked*,const RECT*,DWORD);
 HRESULT(WINAPI*UnlockRect)(D8Surface*);
} D8SurfaceVtable;
struct D8Surface {const D8SurfaceVtable*vt;};
#define D8_RESOURCE(T) D8_COMMON(T); void*private_data[3]; DWORD(WINAPI*SetPriority)(T*,DWORD); DWORD(WINAPI*GetPriority)(T*); void(WINAPI*PreLoad)(T*); DWORD(WINAPI*GetType)(T*)
typedef struct D8TextureVtable {
 D8_RESOURCE(D8Texture);
 DWORD(WINAPI*SetLOD)(D8Texture*,DWORD);
 DWORD(WINAPI*GetLOD)(D8Texture*);
 DWORD(WINAPI*GetLevelCount)(D8Texture*);
 HRESULT(WINAPI*GetLevelDesc)(D8Texture*,UINT,D8SurfaceDesc*);
 HRESULT(WINAPI*GetSurfaceLevel)(D8Texture*,UINT,D8Surface**);
 HRESULT(WINAPI*LockRect)(D8Texture*,UINT,D8Locked*,const RECT*,DWORD);
 HRESULT(WINAPI*UnlockRect)(D8Texture*,UINT);
 HRESULT(WINAPI*AddDirtyRect)(D8Texture*,const RECT*);
} D8TextureVtable;
struct D8Texture {const D8TextureVtable*vt;};
typedef struct D8BufferVtable {
 D8_RESOURCE(D8Buffer);
 HRESULT(WINAPI*Lock)(D8Buffer*,UINT,UINT,BYTE**,DWORD);
 HRESULT(WINAPI*Unlock)(D8Buffer*);
 HRESULT(WINAPI*GetDesc)(D8Buffer*,D8BufferDesc*);
} D8BufferVtable;
struct D8Buffer {const D8BufferVtable*vt;};
typedef char resource_surface_desc_size[sizeof(D8SurfaceDesc)==32?1:-1];
typedef char resource_surface_lock_slot[offsetof(D8SurfaceVtable,LockRect)==9*sizeof(void*)?1:-1];
typedef char resource_texture_lock_slot[offsetof(D8TextureVtable,LockRect)==16*sizeof(void*)?1:-1];
typedef char resource_buffer_lock_slot[offsetof(D8BufferVtable,Lock)==11*sizeof(void*)?1:-1];
typedef char resource_lock_pointer[offsetof(D8Locked,bits)==sizeof(void*)?1:-1];
#undef D8_COMMON
#undef D8_RESOURCE
#endif

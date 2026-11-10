/* Bounded storage: native descriptors determine mip extents and lock pitches.
 * A single outstanding map prevents texture/surface alias-lock ambiguity.
 * This explicit capacity trap can be expanded after game-path evidence.
 */
static void d8_device_CreateTexture(CPU*c) {
 LONG id=d8_api_entry(c,20,8);D8DeviceObject*o=d8_semantic_frame(c);D8Texture*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(7);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_TEXTURE);
 if(ARG(1)>o->caps.words[22]||ARG(2)>o->caps.words[23]||ARG(3)>32||ARG(6)>3)xrt_fatal(c,76,"CreateTexture: dimensions/levels/pool outside bounded domain");
 prev=d8_native_enter(c,20,NULL,0);hr=XM_CreateTexture(c,o->host,ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),ARG(6),out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"CreateTexture: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_TEXTURE);d8_semantic_return(c,prev,id,8,hr,error);
}
typedef HRESULT(WINAPI*D8CreateCubeFn)(D8Device*,UINT,UINT,DWORD,DWORD,DWORD,D8Texture**);
typedef HRESULT(WINAPI*D8CubeSurfaceFn)(D8Texture*,DWORD,UINT,D8Surface**);
typedef HRESULT(WINAPI*D8CubeLockFn)(D8Texture*,DWORD,UINT,D8Locked*,const RECT*,DWORD);
typedef HRESULT(WINAPI*D8CubeUnlockFn)(D8Texture*,DWORD,UINT);
typedef HRESULT(WINAPI*D8CubeDirtyFn)(D8Texture*,DWORD,const RECT*);
/* IDirect3DCubeTexture8 rows 15..18 differ from the texture wrappers; called directly. */
static void*d8_cube_row(D8Resource*r,unsigned slot){return (*(void*const**)r->host)[slot];}
static void d8_cube_probe(XmRequest*q,int event,const char*name,void*host,uint64_t a,uint64_t result) {
 q->event=event;q->domain=XM_NATIVE;q->name=name;q->host=(uint64_t)(uintptr_t)host;q->count=1;
 q->values[0].type=XM_U32;q->values[0].bytes=4;q->values[0].value=a;q->result=result;xm_probe(xm_current_cpu(),q);
}
static void d8_device_CreateCubeTexture(CPU*c) {
 LONG id=d8_api_entry(c,22,7);D8DeviceObject*o=d8_semantic_frame(c);D8Texture*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(6);XmRequest x={0};
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_CUBE);
 if(ARG(1)>o->caps.words[22]||ARG(2)>32||ARG(5)>3)xrt_fatal(c,76,"CreateCubeTexture: edge/levels/pool outside bounded domain");
 prev=d8_native_enter(c,22,NULL,0);d8_cube_probe(&x,XM_BEGIN,"D8Device.CreateCubeTexture",o->host,ARG(1),0);
 hr=((D8CreateCubeFn)((void*const*)o->host->vt)[22])(o->host,ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),out?&q:NULL);error=GetLastError();
 d8_cube_probe(&x,XM_END,"D8Device.CreateCubeTexture",o->host,ARG(1),(uint64_t)hr);
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"CreateCubeTexture: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_CUBE);d8_semantic_return(c,prev,id,7,hr,error);
}
static void d8_resource_GetCubeMapSurface(CPU*c) {
 LONG id=d8_api_entry(c,315,4);D8Resource*r=d8_resource(c,ARG(0),D8_CUBE);D8Surface*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(3);XmRequest x={0};
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 if(ARG(1)>5)xrt_fatal(c,76,"GetCubeMapSurface: face outside domain");
 prev=d8_native_enter(c,315,NULL,0);d8_cube_probe(&x,XM_BEGIN,"D8Cube.GetCubeMapSurface",r->host,ARG(1),0);
 hr=((D8CubeSurfaceFn)d8_cube_row(r,15))((D8Texture*)r->host,ARG(1),ARG(2),out?&q:NULL);error=GetLastError();
 d8_cube_probe(&x,XM_END,"D8Cube.GetCubeMapSurface",r->host,ARG(1),(uint64_t)hr);
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"GetCubeMapSurface: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_SURFACE);d8_semantic_return(c,prev,id,4,hr,error);
}
static void d8_create_buffer(CPU*c,unsigned kind) {
 unsigned slot=kind==D8_VERTEX?23:24;LONG id=d8_api_entry(c,slot,6);D8DeviceObject*o=d8_semantic_frame(c);D8Buffer*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(5);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,kind);
 if(ARG(1)>64u*1024u*1024u||ARG(4)>3)xrt_fatal(c,76,"CreateBuffer: size/pool exceeds implementation capacity");
 prev=d8_native_enter(c,slot,NULL,0);
 hr=kind==D8_VERTEX?XM_CreateVertexBuffer(c,o->host,ARG(1),ARG(2),ARG(3),ARG(4),out?&q:NULL):XM_CreateIndexBuffer(c,o->host,ARG(1),ARG(2),ARG(3),ARG(4),out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"CreateBuffer: NULL native success");}
 d8_resource_output(c,out,hr,q,kind);d8_semantic_return(c,prev,id,6,hr,error);
}
static void d8_device_CreateVertexBuffer(CPU*c){d8_create_buffer(c,D8_VERTEX);}
static void d8_device_CreateIndexBuffer(CPU*c){d8_create_buffer(c,D8_INDEX);}
static void d8_resource_GetSurfaceLevel(CPU*c) {
 LONG id=d8_api_entry(c,315,3);D8Resource*r=d8_resource(c,ARG(0),D8_TEXTURE);D8Surface*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 prev=d8_native_enter(c,315,NULL,0);hr=XM_GetSurfaceLevel(c,(D8Texture*)r->host,ARG(1),out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"GetSurfaceLevel: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_SURFACE);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_resource_GetLevelDesc(CPU*c) {
 LONG id=d8_api_entry(c,314,3);D8Resource*r=d8_resource(c,ARG(0),0);D8SurfaceDesc desc;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);
 if(!D8_TEXLIKE(r->kind))xrt_fatal(c,76,"GetLevelDesc: wrong resource type");
 d8_device_memory(c,out,32,1);memcpy(&desc,G2H(out),32);
 prev=d8_native_enter(c,314,NULL,0);hr=XM_GetLevelDesc(c,(D8Texture*)r->host,ARG(1),&desc);error=GetLastError();
 d8_device_memory(c,out,32,1);memcpy(G2H(out),&desc,32);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_lock_flags(CPU*c,unsigned flags) {
 /* Maps of distinct resources may overlap (each owns its staging copy); d8_locks counts them. */
 if(flags&~(0x10u|0x20u|0x1000u|0x2000u|0x8000u))xrt_fatal(c,76,"D3D8 map: unsupported flags");
}
static void d8_map_size(CPU*c,unsigned format,unsigned width,unsigned height,unsigned*bytes,unsigned*rows) {
 unsigned bpp=0;uint64_t n;
 switch(format){
 case 20:bpp=3;break;case 21:case 22:case 31:case 32:case 33:case 35:case 62:case 63:case 64:case 65:case 67:bpp=4;break;
 case 23:case 24:case 25:case 26:case 29:case 30:case 40:case 51:case 60:case 61:bpp=2;break;
 case 27:case 28:case 41:case 50:case 52:bpp=1;break;
 case 0x31545844:case 0x32545844:case 0x33545844:case 0x34545844:case 0x35545844:
  n=((uint64_t)width+3)/4*(format==0x31545844?8:16);*rows=(height+3)/4;goto done;
 default:xrt_fatal(c,76,"D3D8 map: unimplemented pixel format %08x",format);
 }
 n=(uint64_t)width*bpp;*rows=height;
done:
 if(!n||!*rows||n>64u*1024u*1024u||n**rows>64u*1024u*1024u)xrt_fatal(c,76,"D3D8 map: extent exceeds capacity");
 *bytes=(unsigned)n;
}
static HRESULT d8_desc_native(D8Resource*r,unsigned level,D8SurfaceDesc*d) {
 return r->kind==D8_SURFACE?XM_GetDesc(NULL,(D8Surface*)r->host,d):XM_GetLevelDesc(NULL,(D8Texture*)r->host,level,d);
}
static void d8_resource_LockRect(CPU*c) {
 LONG id;D8Resource*r;unsigned level,out,rectarg,flags,n,rowbytes,rows,y;RECT rect;D8SurfaceDesc desc;D8Locked lock;
 CPU*prev;HRESULT hr;DWORD error,saved=GetLastError();uint32_t stage;uint64_t size;unsigned long long t0=XRT_PERF_T0(),t1;
 /* Read this only after validating a minimum complete surface frame. */
 id=d8_api_entry(c,316,4);r=d8_resource(c,ARG(0),0);
 if(r->kind!=D8_SURFACE&&!D8_TEXLIKE(r->kind))xrt_fatal(c,76,"LockRect: wrong resource type");
 n=r->kind==D8_CUBE?6:r->kind==D8_TEXTURE?5:4;d8_device_memory(c,c->r[ESP],4*(n+1),0);
 level=r->kind==D8_CUBE?ARG(2):r->kind==D8_TEXTURE?ARG(1):0;out=ARG(n-3);rectarg=ARG(n-2);flags=ARG(n-1);d8_lock_flags(c,flags);
 if(r->locked)xrt_fatal(c,76,"LockRect: resource already mapped");
 if(r->kind==D8_CUBE&&ARG(1)>5)xrt_fatal(c,76,"LockRect: cube face outside domain");d8_device_memory(c,out,8,1);
 if(rectarg){d8_device_memory(c,rectarg,16,0);memcpy(&rect,G2H(rectarg),16);}
 prev=xrt_gui_callback_enter(c);d8_rendering=1;hr=d8_desc_native(r,level,&desc);d8_rendering=0;xrt_gui_callback_leave(prev);SetLastError(saved);
 if(FAILED(hr))xrt_fatal(c,76,"LockRect: cannot obtain native mip descriptor");
 if(!rectarg){rect.left=rect.top=0;rect.right=desc.width;rect.bottom=desc.height;}
 if(rect.left<0||rect.top<0||rect.right<=rect.left||rect.bottom<=rect.top||(uint32_t)rect.right>desc.width||(uint32_t)rect.bottom>desc.height)xrt_fatal(c,76,"LockRect: unsafe rectangle");
 if((desc.format&0xffffff)==0x545844 && ((rect.left|rect.top)&3))xrt_fatal(c,76,"LockRect: compressed origin alignment");
 d8_map_size(c,desc.format,rect.right-rect.left,rect.bottom-rect.top,&rowbytes,&rows);
 lock.pitch=(INT)rd32(out);lock.bits=(void*)(uintptr_t)1; /* distinguish untouched from native NULL output */
 prev=d8_native_enter(c,316,&rect,16);hr=r->kind==D8_SURFACE?XM_LockRect(c,(D8Surface*)r->host,&lock,rectarg?&rect:NULL,flags):r->kind==D8_CUBE?((D8CubeLockFn)d8_cube_row(r,16))((D8Texture*)r->host,ARG(1),level,&lock,rectarg?&rect:NULL,flags):XM_LockRect(c,(D8Texture*)r->host,level,&lock,rectarg?&rect:NULL,flags);error=GetLastError();
 if(SUCCEEDED(hr)) {
  /* Native map remains owned until matching successful Unlock. */
  d8_locks++;r->locked=lock.bits;r->pitch=lock.pitch;r->level=level;r->face=r->kind==D8_CUBE?ARG(1):0;r->flags=flags;r->rows=rows;r->rowbytes=rowbytes;
  size=(uint64_t)(unsigned)lock.pitch*rows;
  if(!lock.bits||lock.pitch<=0||(unsigned)lock.pitch<rowbytes||size>64u*1024u*1024u){d8_native_failed=1;xrt_fatal(c,76,"LockRect: unsafe native layout");}
  t1=XRT_PERF_T0();stage=xrt_virtual_alloc(c,(unsigned)size);XRT_PERF_ADD(tsc_staging_alloc,t1);xrt_perf.staging_alloc++;xrt_perf.staging_alloc_bytes+=size;xrt_perf.tex_lock++;xrt_perf.tex_lock_bytes+=size;if(!stage)xrt_fatal(c,76,"LockRect: staging allocation failed");d8_staging_hint(stage,(unsigned)size);r->staging=stage;r->bytes=(unsigned)size;xm_d8_resource(c,r,"mapped");
  d8_device_memory(c,stage,(unsigned)size,1);
  /* every row is copied; only its pitch padding is zeroed (the whole block used to be zeroed first) */
  for(y=0;y<rows;y++){memcpy((BYTE*)G2H(stage)+y*lock.pitch,(BYTE*)lock.bits+y*lock.pitch,rowbytes);
   if((unsigned)lock.pitch>rowbytes)memset((BYTE*)G2H(stage)+y*lock.pitch+rowbytes,0,(unsigned)lock.pitch-rowbytes);}
  xm_span(c,"resource.map.download",G2H(stage),r->bytes);d8_device_memory(c,out,8,1);wr32(out,(unsigned)lock.pitch);wr32(out+4,stage);
 } else {if(lock.bits&&(uintptr_t)lock.bits!=1){d8_native_failed=1;xrt_fatal(c,76,"LockRect: failed call returned map");}d8_device_memory(c,out,8,1);wr32(out,(unsigned)lock.pitch);if(!lock.bits)wr32(out+4,0);}
 XRT_PERF_ADD(tsc_tex_lock,t0);
 d8_semantic_return(c,prev,id,n,hr,error);
}
#include "d8_valid_bits.h"
/* Buffer map staging. Strict (default): a fresh guest block per Lock, decommitted at Unlock, so a guest pointer kept
 * past Unlock faults at once (bug detection beyond the D3D contract). XRT_DEV_STAGING=reuse (developer runs only,
 * dev.py --staging reuse): Unlock leaves the block committed ("warm", xrt_mem.c xrt_staging_put) and the next buffer
 * Lock of the same size class takes it (xrt_staging_take): no commit, decommit or re-validation per map, and the pool
 * holds no more blocks than in strict mode. Unchanged: staging is guest memory (guest code cannot reach host memory
 * through it), handle/type/ownership lookups, offset/size checks against the native descriptor, the checked
 * guest-range snapshot and exact-length copies at Unlock, and the data the guest sees at Lock (the host shadow).
 * Relaxed (diagnostics only): a guest pointer kept past Unlock no longer faults. It reads/writes a committed staging
 * block that the next Lock of ANY vertex/index buffer of the same size class may receive, so a stale write can change
 * the bytes another buffer's Lock handed out (and is then uploaded into that buffer), and a stale read can see another
 * buffer's data - corruption confined to guest memory and guest-supplied buffer contents. Bytes of a block past the
 * locked range keep earlier contents instead of zero. Textures/surfaces (LockRect) stay strict. */
static int d8_staging_reuse(void) {
 static int mode=-1;
 if(mode<0){char v[16];DWORD n=GetEnvironmentVariableA("XRT_DEV_STAGING",v,sizeof v);mode=n&&n<sizeof v&&!strcmp(v,"reuse");
  if(mode)xrt_log("DEV D3D8 buffer staging: reuse (per-buffer block; stale pointers until the next Lock are not trapped)");}
 return mode;
}
/* XRT_DEV_STAGING=guard (dev.py --staging guard): strict's guarantee at lower cost. Unlock leaves the block committed but
 * PAGE_NOACCESS (xrt_mem.c xrt_staging_guard_put) instead of decommitting it, so a stale guest pointer faults exactly as
 * in strict mode; the next buffer Lock of the same size class re-opens it read-write, zero past the locked bytes, and
 * receives the shadow bytes as always. Saved: the page faults and zero-filling of fresh pages and the decommit's page
 * freeing; kept: one protection change per Lock and per Unlock. Textures/surfaces stay strict. */
static int d8_staging_guard(void) {
 static int mode=-1;
 if(mode<0){char v[16];DWORD n=GetEnvironmentVariableA("XRT_DEV_STAGING",v,sizeof v);mode=n&&n<sizeof v&&!strcmp(v,"guard");
  if(mode)xrt_log("DEV D3D8 buffer staging: guard (blocks PAGE_NOACCESS between uses; stale pointers fault as in strict)");}
 return mode;
}
static void d8_resource_Lock(CPU*c) {
 LONG id=d8_api_entry(c,311,5);D8Resource*r=d8_resource(c,ARG(0),0);D8BufferDesc desc={0};unsigned offset=ARG(1),size=ARG(2),out=ARG(3),flags=ARG(4);BYTE*data=(BYTE*)(uintptr_t)1;CPU*prev;HRESULT hr;DWORD error,saved=GetLastError();unsigned long long t0=XRT_PERF_T0(),t1;
 if(r->kind!=D8_VERTEX&&r->kind!=D8_INDEX)xrt_fatal(c,76,"Lock: wrong resource type");
 d8_lock_flags(c,flags);d8_device_memory(c,out,4,1);
 if(r->locked)xrt_fatal(c,76,"Lock: resource already mapped");
 prev=xrt_gui_callback_enter(c);d8_rendering=1;hr=XM_GetDesc(c,(D8Buffer*)r->host,&desc);d8_rendering=0;xrt_gui_callback_leave(prev);SetLastError(saved);
 if(FAILED(hr)||offset>desc.size)xrt_fatal(c,76,"Lock: unsafe buffer descriptor/range");
 if(!r->shadow){
  if(!desc.size||desc.size>64u*1024u*1024u)xrt_fatal(c,76,"Lock: buffer capacity");
  if(d8_shadow_bytes+2ull*desc.size>256u*1024u*1024u)xrt_fatal(c,76,"Lock: 256 MiB host mirror budget exceeded");
  r->shadow=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,desc.size);r->valid=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,d8_valid_bytes(desc.size));
  if(!r->shadow||!r->valid){if(r->shadow)HeapFree(GetProcessHeap(),0,r->shadow);if(r->valid)HeapFree(GetProcessHeap(),0,r->valid);r->shadow=r->valid=NULL;xrt_fatal(c,76,"Lock: host mirror allocation failed");}r->length=desc.size;r->format=desc.format;d8_shadow_bytes+=2ull*desc.size;
 }
 if(desc.size!=r->length||desc.format!=r->format)xrt_fatal(c,76,"Lock: native buffer descriptor changed");
 if(!size)size=desc.size-offset;
 if(!size||(uint64_t)offset+size>desc.size||size>64u*1024u*1024u)xrt_fatal(c,76,"Lock: unsafe buffer range");
 prev=d8_native_enter(c,311,NULL,0);hr=XM_Lock(c,(D8Buffer*)r->host,offset,ARG(2),&data,flags);error=GetLastError();
 if(SUCCEEDED(hr)) {
  d8_locks++;r->locked=data;r->flags=flags;r->offset=offset;r->bytes=size;r->rows=1;r->rowbytes=size;r->pitch=size;
  if(!data){d8_native_failed=1;xrt_fatal(c,76,"Lock: NULL native map");}
  t1=XRT_PERF_T0();r->staging=d8_staging_reuse()?xrt_staging_take(c,size):d8_staging_guard()?xrt_staging_guard_take(c,size):xrt_virtual_alloc(c,size);XRT_PERF_ADD(tsc_staging_alloc,t1);
  xrt_perf.staging_alloc++;xrt_perf.staging_alloc_bytes+=size;xrt_perf.buf_lock++;xrt_perf.buf_lock_bytes+=size;xrt_perf.buf_valid_scan_bytes+=d8_valid_bytes(size);
  if(flags&0x2000){xrt_perf.buf_lock_discard++;xrt_perf.buf_valid_clear_bytes+=d8_valid_bytes(r->length);}if(flags&0x1000)xrt_perf.buf_lock_nooverwrite++;
  if(!r->staging)xrt_fatal(c,76,"Lock: staging allocation failed");d8_staging_hint(r->staging,size);d8_device_memory(c,r->staging,size,1);
  /* Reads from the native map hit GPU-visible (uncached) memory and dominated Lock.
   * Only our Unlock writes these buffers natively (ProcessVertices is refused), so
   * valid shadow bytes equal the native ones and every other byte is undefined by
   * D3D (never written, or invalidated by DISCARD): the staging copy comes from the
   * host shadow. Invalid bytes are counted for evidence. */
  {static unsigned locks,undefined_locks;
   if(!d8_valid_all(r->valid,offset,size)){undefined_locks++;xrt_perf.buf_lock_undefined++;}
   memcpy(G2H(r->staging),r->shadow+offset,size);
   if(!(++locks&0xffff))xrt_log("D3D8 buffer Lock downloads from shadow: %u (%u with D3D-undefined bytes)",locks,undefined_locks);}
  if(flags&0x2000)memset(r->valid,0,d8_valid_bytes(r->length));
  d8_device_memory(c,out,4,1);wr32(out,r->staging);xm_d8_resource(c,r,"mapped");xm_span(c,"resource.map.download",G2H(r->staging),r->bytes);
 } else {if(data&&(uintptr_t)data!=1){d8_native_failed=1;xrt_fatal(c,76,"Lock: failed native map");}if(!data){d8_device_memory(c,out,4,1);wr32(out,0);}}
 XRT_PERF_ADD(tsc_buf_lock,t0);
 d8_semantic_return(c,prev,id,5,hr,error);
}
static void d8_unlock(CPU*c,int rectangle) {
 LONG id=d8_api_entry(c,rectangle?317:312,1);D8Resource*r=d8_resource(c,ARG(0),0);unsigned n=rectangle&&r->kind==D8_CUBE?3:rectangle&&r->kind==D8_TEXTURE?2:1,y;BYTE*copy=NULL;CPU*prev;HRESULT hr;DWORD error;unsigned long long t0=XRT_PERF_T0(),t1;
 d8_device_memory(c,c->r[ESP],4*(n+1),0);
 if((rectangle&&(!D8_TEXLIKE(r->kind)&&r->kind!=D8_SURFACE))||(!rectangle&&(r->kind!=D8_VERTEX&&r->kind!=D8_INDEX)))xrt_fatal(c,76,"Unlock: wrong resource type");
 if(!r->locked||!r->staging||(n==2&&ARG(1)!=r->level)||(n==3&&(ARG(1)!=r->face||ARG(2)!=r->level)))xrt_fatal(c,76,"Unlock: missing or mismatched map");
 if(!(r->flags&0x10)&&!rectangle&&r->shadow) {
  /* Buffers: the snapshot is taken straight into the host shadow (revalidated guest range, before native code),
   * then uploaded from there: same bytes in the shadow and the native buffer, no heap block, one copy less. */
  d8_device_memory(c,r->staging,r->bytes,0);memcpy(r->shadow+r->offset,G2H(r->staging),r->bytes);xrt_perf.draw_copy_bytes+=r->bytes;
  xm_span(c,"resource.map.upload",r->shadow+r->offset,r->bytes);
  memcpy(r->locked,r->shadow+r->offset,r->bytes);d8_valid_set(r->valid,r->offset,r->bytes);
 } else if(!(r->flags&0x10)) {
  /* Snapshot before entering native code; revalidate even if callback changed pages. */
  copy=d8_draw_copy(c,r->staging,r->bytes);xm_span(c,"resource.map.upload",copy,r->bytes);
  for(y=0;y<r->rows;y++)memcpy(r->locked+(size_t)y*r->pitch,copy+(size_t)y*r->pitch,r->rowbytes);
  if(r->shadow){memcpy(r->shadow+r->offset,copy,r->bytes);d8_valid_set(r->valid,r->offset,r->bytes);}
  HeapFree(GetProcessHeap(),0,copy);
 }
 prev=d8_native_enter(c,rectangle?317:312,NULL,0);
 hr=!rectangle?XM_Unlock(c,(D8Buffer*)r->host):r->kind==D8_SURFACE?XM_UnlockRect(c,(D8Surface*)r->host):r->kind==D8_CUBE?((D8CubeUnlockFn)d8_cube_row(r,17))((D8Texture*)r->host,r->face,r->level):XM_UnlockRect(c,(D8Texture*)r->host,r->level);error=GetLastError();
 if(rectangle){xrt_perf.tex_unlock++;xrt_perf.tex_unlock_bytes+=r->bytes;}else{xrt_perf.buf_unlock++;xrt_perf.buf_unlock_bytes+=r->bytes;}
 if(SUCCEEDED(hr)){t1=XRT_PERF_T0();if(!(!rectangle&&d8_staging_reuse()?xrt_staging_put(c,r->staging):!rectangle&&d8_staging_guard()?xrt_staging_guard_put(c,r->staging):xrt_virtual_free(c,r->staging)))xrt_fatal(c,76,"Unlock: staging invalidation failed");XRT_PERF_ADD(tsc_staging_free,t1);xrt_perf.staging_free++;r->staging=0;r->locked=NULL;d8_locks--;xm_d8_resource(c,r,"unlocked");}
 else {d8_native_failed=1; /* Preserve failure HRESULT; retain mapping until process teardown. */}
 if(rectangle)XRT_PERF_ADD(tsc_tex_unlock,t0);else XRT_PERF_ADD(tsc_buf_unlock,t0);
 d8_semantic_return(c,prev,id,n,hr,error);
}
static void d8_resource_UnlockRect(CPU*c){d8_unlock(c,1);}
static void d8_resource_Unlock(CPU*c){d8_unlock(c,0);}
static void d8_resource_AddDirtyRect(CPU*c) {
 D8Resource*r=d8_resource(c,ARG(0),0);int cube=r->kind==D8_CUBE;LONG id=d8_api_entry(c,318,cube?3:2);RECT rect;CPU*prev;HRESULT hr;DWORD error;uint32_t ra=ARG(cube?2:1);
 if(!D8_TEXLIKE(r->kind))xrt_fatal(c,76,"AddDirtyRect: wrong resource type");
 if(ra){d8_device_memory(c,ra,16,0);memcpy(&rect,G2H(ra),16);}
 if(cube){prev=d8_native_enter(c,318,NULL,0);hr=((D8CubeDirtyFn)d8_cube_row(r,18))((D8Texture*)r->host,ARG(1),ra?&rect:NULL);error=GetLastError();d8_semantic_return(c,prev,id,3,hr,error);return;}
 prev=d8_native_enter(c,318,NULL,0);hr=XM_AddDirtyRect(c,(D8Texture*)r->host,ra?&rect:NULL);error=GetLastError();d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_resource_scalar(CPU*c,unsigned slot,unsigned n) {
 LONG id=d8_api_entry(c,slot+300,n);D8Resource*r=d8_resource(c,ARG(0),0);D8Texture*t=(D8Texture*)r->host;D8Buffer*b=(D8Buffer*)r->host;CPU*prev;DWORD value,error;
 if(r->kind==D8_SURFACE||(slot>=11&&!D8_TEXLIKE(r->kind)))xrt_fatal(c,76,"D3D8 resource: scalar method type mismatch");
 prev=d8_native_enter(c,slot+300,NULL,0);
 switch(slot){
 case 7:value=D8_TEXLIKE(r->kind)?XM_SetPriority(c,t,ARG(1)):XM_SetPriority(c,b,ARG(1));break;
 case 8:value=D8_TEXLIKE(r->kind)?XM_GetPriority(c,t):XM_GetPriority(c,b);break;
 case 9:
  if(D8_TEXLIKE(r->kind))XM_PreLoad(c,t);else XM_PreLoad(c,b);error=GetLastError();
  d8_semantic_checkpoint(c,2,309,NULL,0,0,error);d8_rendering=0;xrt_gui_callback_leave(prev);
  xrt_set_last_error(c,error);c->rv=pop32(c);c->r[ESP]+=4;
  d8_semantic_checkpoint(c,3,309,NULL,0,0,error);
  xrt_event("d3d8_resource_void_return","\"id\":%ld,\"method\":\"PreLoad\",\"last_error\":%lu,\"esp\":%u,\"return\":%u",id,error,c->r[ESP],c->rv);
  d8_evidence_blob(id,"guest_cpu_return",c,sizeof *c);return;
 case 10:value=D8_TEXLIKE(r->kind)?XM_GetType(c,t):XM_GetType(c,b);break;
 case 11:value=XM_SetLOD(c,t,ARG(1));break;case 12:value=XM_GetLOD(c,t);break;default:value=XM_GetLevelCount(c,t);break;
 }
 error=GetLastError();d8_semantic_return(c,prev,id,n,(HRESULT)value,error);
}
static void d8_resource_SetPriority(CPU*c){d8_resource_scalar(c,7,2);}
static void d8_resource_GetPriority(CPU*c){d8_resource_scalar(c,8,1);}
static void d8_resource_PreLoad(CPU*c){d8_resource_scalar(c,9,1);}
static void d8_resource_GetType(CPU*c){d8_resource_scalar(c,10,1);}
static void d8_resource_SetLOD(CPU*c){d8_resource_scalar(c,11,2);}
static void d8_resource_GetLOD(CPU*c){d8_resource_scalar(c,12,1);}
static void d8_resource_GetLevelCount(CPU*c){d8_resource_scalar(c,13,1);}

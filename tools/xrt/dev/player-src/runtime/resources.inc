/* Native COM ownership, typed handles and copied lock transport.
 * No private native AddRef pins: they would change public reference counts.
 * Retired guest handles are never reassigned, even if the native address is reused;
 * a retired host-side slot is recycled with a fresh guest token.
 * Native bindings retain native resources; lookups always acquire a real ref.
 */
enum {D8_SURFACE=1,D8_TEXTURE=3,D8_CUBE=5,D8_VERTEX=6,D8_INDEX=7,D8_RESOURCE_LIMIT=4096};
/* Cube textures share the texture vtable layout; slots 15..18 add a face argument. */
#define D8_TEXLIKE(k) ((k)==D8_TEXTURE||(k)==D8_CUBE)
typedef struct D8Resource {
 uint32_t guest,refs,kind,bindings;
 D8Unknown*host;
 BYTE*shadow,*valid;unsigned length,format;   /* valid: one bit per buffer byte (d8_valid_bits.h) */
 /* One outstanding lock per object. Guest staging is never a host pointer. */
 uint32_t staging,bytes,rows,rowbytes,level,flags,offset,face;
 INT pitch;BYTE*locked;
} D8Resource;
static D8Resource d8_resources[D8_RESOURCE_LIMIT];
static unsigned d8_resource_used,d8_resource_adoptions;
/* A slot is free once retired: no native object, references or bindings. */
static D8Resource*d8_resource_free_slot(void) {
 unsigned i;for(i=0;i<d8_resource_used;i++)if(!d8_resources[i].host&&!d8_resources[i].refs&&!d8_resources[i].bindings)return &d8_resources[i];
 return d8_resource_used<D8_RESOURCE_LIMIT?&d8_resources[d8_resource_used]:NULL;
}
static void xm_d8_resource(CPU*c,D8Resource*r,const char*event) {
 if(xm_quiet)return;   /* quiet profile: both records below are routine and dropped (round 4) */
 xm_resource(c,100+r->kind,r->guest,(unsigned)(r-d8_resources)+1,
   (uint64_t)(uintptr_t)r->host,r->refs,r->bindings,event);
 /* Registry-owned scalars; locked/native pointers remain opaque. */
 {XmValue v[11]={{XM_U32,4,r->staging},{XM_U32,4,r->bytes},{XM_U32,4,r->rows},
 {XM_U32,4,r->rowbytes},{XM_U32,4,r->level},{XM_U32,4,r->flags},
 {XM_I32,4,(uint32_t)r->pitch},{XM_OPAQUE,8,(uint64_t)(uintptr_t)r->locked},{XM_U32,4,r->offset},{XM_U32,4,r->length},{XM_U32,4,r->format}};
 xm_values(c,"resource.map",11,v);}
}

static uint64_t d8_shadow_bytes;
static uint32_t d8_resource_vtables[8];
static D8Resource*d8_bound_streams[16],*d8_bound_indices,*d8_bound_textures[8];
static const GUID d8_surface_iid={0xb96eebca,0xb326,0x4ea5,{0x88,0x2f,0x2f,0xf5,0xba,0xe0,0x21,0xdd}};
static const GUID d8_texture_iid={0xe4cdd575,0x2866,0x4f01,{0xb1,0x2e,0x7e,0xec,0xe1,0xec,0x93,0x58}};
static const GUID d8_cube_iid={0x3ee5b968,0x2aca,0x4c34,{0x8b,0xb5,0x7e,0x0c,0x3d,0x19,0xb7,0x50}};
static const GUID d8_vertex_iid={0x8aeeeac7,0x05f9,0x44d4,{0xb5,0x91,0x00,0x0b,0x0d,0xf1,0xcb,0x95}};
static const GUID d8_index_iid={0x0e689c9a,0x053d,0x44a0,{0x9d,0x92,0xdb,0x0e,0x3d,0x75,0x0f,0x86}};
static const GUID d8_resource_iid={0x1b36bb7b,0x09b7,0x410a,{0xb4,0x45,0x7d,0x14,0x30,0xd7,0xb3,0x3f}};
static const GUID d8_base_texture_iid={0xb4211cfa,0x51b9,0x4a9f,{0xab,0x78,0xdb,0x99,0xb2,0xbb,0x67,0x8e}};
static const char* d8_surface_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.GetContainer","D8R.GetDesc","D8R.LockRect","D8R.UnlockRect"};
static const char* d8_texture_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.SetPriority","D8R.GetPriority","D8R.PreLoad","D8R.GetType","D8R.SetLOD","D8R.GetLOD","D8R.GetLevelCount","D8R.GetLevelDesc","D8R.GetSurfaceLevel","D8R.LockRect","D8R.UnlockRect","D8R.AddDirtyRect"};
static const char* d8_cube_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.SetPriority","D8R.GetPriority","D8R.PreLoad","D8R.GetType","D8R.SetLOD","D8R.GetLOD","D8R.GetLevelCount","D8R.GetLevelDesc","D8R.GetCubeMapSurface","D8R.LockRect","D8R.UnlockRect","D8R.AddDirtyRect"};
static const char* d8_buffer_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.SetPriority","D8R.GetPriority","D8R.PreLoad","D8R.GetType","D8R.Lock","D8R.Unlock","D8R.GetDesc"};
static void d8_resource_guard(CPU*c) {
 if(d8_rendering||d8_creating||d8_native_failed)xrt_fatal(c,76,"D3D8 resource: reentrant or failed native operation");
 /* resources are released after the game destroyed the window at shutdown (d8_render_ready) */
 if(d8_device.host){if(!xrt_gui_window_destroyed(d8_device.focus))xrt_gui_device_window(c,d8_device.focus);
   if(!xrt_gui_window_destroyed(d8_device.window))xrt_gui_device_window(c,d8_device.window);}
}
/* Slot hint per guest token (index+1). Tokens are fresh xrt_rt_alloc cells, never reused, so at most one
 * live slot holds a token; a hint is used only after the same live-slot test as the scan. */
static unsigned d8_resource_hint[1024];
static D8Resource*d8_resource(CPU*c,uint32_t guest,unsigned kind) {
 unsigned i,h=(guest>>2)&1023;D8Resource*r;d8_resource_guard(c);
 i=d8_resource_hint[h]-1;
 if(i<d8_resource_used&&(r=&d8_resources[i],guest&&r->guest==guest&&r->refs&&r->host)) {
  if(kind&&r->kind!=kind)xrt_fatal(c,76,"D3D8 resource: wrong interface type");
  xm_d8_resource(c,r,"receiver");return r;
 }
 for(i=0;i<d8_resource_used;i++) {r=&d8_resources[i];
  if(guest&&r->guest==guest&&r->refs&&r->host) {
   if(kind&&r->kind!=kind)xrt_fatal(c,76,"D3D8 resource: wrong interface type");
   d8_resource_hint[h]=i+1;
   xm_d8_resource(c,r,"receiver");return r;
  }
 }
 xrt_fatal(c,76,"D3D8 resource: stale or unknown handle %08x",guest);
}
static void d8_resource_reserve(CPU*c,unsigned kind) {
 d8_resource_guard(c);
 if(!d8_resource_free_slot())xrt_fatal(c,76,"D3D8 resource: handle capacity (%u live)",d8_resource_used);
 if(!d8_resource_vtables[kind])d8_resource_vtables[kind]=com_vtable(kind==D8_SURFACE?d8_surface_names:kind==D8_TEXTURE?d8_texture_names:kind==D8_CUBE?d8_cube_names:d8_buffer_names,kind==D8_SURFACE?11:D8_TEXLIKE(kind)?19:14);
}
/* Called inside the native scope, adopting exactly the returned reference. */
static uint32_t d8_resource_adopt(CPU*c,void*host,unsigned kind) {
 unsigned i;D8Resource*r;
 if(!host)return 0;
 for(i=0;i<d8_resource_used;i++)if(d8_resources[i].host==host&&(d8_resources[i].refs||d8_resources[i].bindings)) {
  r=&d8_resources[i];if(r->kind!=kind||r->refs==UINT32_MAX){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: identity/type/reference inconsistency");}
  if(!r->refs)d8_device.children++;r->refs++;xm_d8_resource(c,r,"reference-acquired");return r->guest;
 }
 if(!(r=d8_resource_free_slot())){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: adoption capacity");}
 if(r==&d8_resources[d8_resource_used])d8_resource_used++;memset(r,0,sizeof *r);
 if(!(++d8_resource_adoptions%512)){unsigned n[8]={0};for(i=0;i<d8_resource_used;i++)if(d8_resources[i].host)n[d8_resources[i].kind&7]++;
  xrt_log("D3D8 resources: %u adoptions, %u slots, live surface %u texture %u cube %u vertex %u index %u",
          d8_resource_adoptions,d8_resource_used,n[D8_SURFACE],n[D8_TEXTURE],n[D8_CUBE],n[D8_VERTEX],n[D8_INDEX]);}
 r->guest=xrt_rt_alloc(4,4);wr32(r->guest,d8_resource_vtables[kind]);r->kind=kind;r->host=host;r->refs=1;d8_device.children++;
 xrt_event("d3d8_resource_adopt","\"guest\":%u,\"type\":%u,\"generation\":%u",r->guest,kind,d8_resource_adoptions);
 xm_d8_resource(c,r,"created");return r->guest;
}
static void d8_resource_output(CPU*c,uint32_t out,HRESULT hr,void*q,unsigned kind) {
 uint32_t token=0;
 if(FAILED(hr)&&q){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: failed native call returned an owned object");}
 if(q)token=d8_resource_adopt(c,q,kind);
 if(out){d8_device_memory(c,out,4,1);wr32(out,token);}
}
static void d8_resource_retire(D8Resource*r) {
 xm_d8_resource(NULL,r,"retire-before");
 if(!r->refs&&!r->bindings){r->host=NULL;if(r->shadow){d8_shadow_bytes-=2ull*r->length;HeapFree(GetProcessHeap(),0,r->shadow);}if(r->valid)HeapFree(GetProcessHeap(),0,r->valid);r->shadow=r->valid=NULL;xm_d8_resource(NULL,r,"destroyed");}
}
static void d8_resource_bind(D8Resource**binding,D8Resource*r) {
 if(r)xm_d8_resource(NULL,r,"bind-before");if(*binding)xm_d8_resource(NULL,*binding,"unbind-before");
 unsigned xm_kind=0,xm_index=0,xm_i;XmValue xm_v[4];
 for(xm_i=0;xm_i<16;xm_i++)if(binding==&d8_bound_streams[xm_i]){xm_kind=1;xm_index=xm_i;}
 for(xm_i=0;xm_i<8;xm_i++)if(binding==&d8_bound_textures[xm_i]){xm_kind=2;xm_index=xm_i;}
 if(binding==&d8_bound_indices)xm_kind=3;
 xm_v[0]=(XmValue){XM_U32,4,xm_kind};xm_v[1]=(XmValue){XM_U32,4,xm_index};
 xm_v[2]=(XmValue){XM_GUEST_ADDRESS,4,*binding?(*binding)->guest:0};
 xm_v[3]=(XmValue){XM_GUEST_ADDRESS,4,r?r->guest:0};xm_values(NULL,"resource.binding-location",4,xm_v);
 if(!xm_kind&&xm_enabled())xm_failure(22);
 D8Resource*old=*binding;if(r)r->bindings++;*binding=r;if(old){old->bindings--;d8_resource_retire(old);xm_d8_resource(NULL,old,"unbound");}if(r)xm_d8_resource(NULL,r,"bound");
}
static void d8_resource_device_dead(void) {
 unsigned i;for(i=0;i<16;i++)d8_resource_bind(&d8_bound_streams[i],NULL);
 for(i=0;i<8;i++)d8_resource_bind(&d8_bound_textures[i],NULL);d8_resource_bind(&d8_bound_indices,NULL);
}
static void d8_resource_up_reset(int indexed) {
 d8_resource_bind(&d8_bound_streams[0],NULL);if(indexed)d8_resource_bind(&d8_bound_indices,NULL);
}
static void d8_resource_drop(D8Resource*r) {
 xm_d8_resource(NULL,r,"release-before");
 if(!--r->refs){d8_device.children--;d8_resource_retire(r);if(!d8_device.refs&&!d8_device.children)d8_device_dead(&d8_device);}
 xm_d8_resource(NULL,r,"released");
}
static int d8_resource_iid_known(D8Resource*r,const GUID*iid) {
 const GUID*own=r->kind==D8_SURFACE?&d8_surface_iid:r->kind==D8_TEXTURE?&d8_texture_iid:r->kind==D8_CUBE?&d8_cube_iid:r->kind==D8_VERTEX?&d8_vertex_iid:&d8_index_iid;
 return !memcmp(iid,&com_iunknown,16)||!memcmp(iid,own,16)||(r->kind!=D8_SURFACE&&!memcmp(iid,&d8_resource_iid,16))||(D8_TEXLIKE(r->kind)&&!memcmp(iid,&d8_base_texture_iid,16));
}
static void d8_resource_Unsupported(CPU*c){xrt_fatal(c,76,"D3D8 resource: private data interface unsupported");}
static void d8_resource_QueryInterface(CPU*c) {
 LONG id=d8_api_entry(c,300,3);D8Resource*r=d8_resource(c,ARG(0),0);GUID iid;void*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);
 d8_device_memory(c,ARG(1),16,0);memcpy(&iid,G2H(ARG(1)),16);if(out)d8_device_memory(c,out,4,1);
 if(r->refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 resource: reference overflow");
 prev=d8_native_enter(c,300,&iid,16);hr=XM_QueryInterface(c,r->host,&iid,out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&(!d8_resource_iid_known(r,&iid)||q!=r->host)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: unmodelled successful QI");}
 d8_resource_output(c,out,hr,q,r->kind);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_resource_AddRef(CPU*c) {
 LONG id=d8_api_entry(c,301,1);D8Resource*r=d8_resource(c,ARG(0),0);CPU*prev;ULONG n;DWORD error;
 if(r->refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 resource: reference overflow");
 prev=d8_native_enter(c,301,NULL,0);n=XM_AddRef(c,r->host);error=GetLastError();r->refs++;xm_d8_resource(c,r,"addref");d8_semantic_return(c,prev,id,1,(HRESULT)n,error);
}
static void d8_resource_Release(CPU*c) {
 LONG id=d8_api_entry(c,302,1);D8Resource*r=d8_resource(c,ARG(0),0);CPU*prev;ULONG n;DWORD error;
 if(d8_locks)xrt_fatal(c,76,"D3D8 resource: Release while mapped resources exist");
 prev=d8_native_enter(c,302,NULL,0);n=XM_Release(c,r->host);error=GetLastError();d8_resource_drop(r);d8_semantic_return(c,prev,id,1,(HRESULT)n,error);
}
static void d8_resource_GetDevice(CPU*c) {
 LONG id=d8_api_entry(c,303,2);D8Resource*r=d8_resource(c,ARG(0),0);D8Device*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(1);
 if(out)d8_device_memory(c,out,4,1);if(d8_device.refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 device: reference overflow");
 prev=d8_native_enter(c,303,NULL,0);hr=XM_GetDevice(c,r->host,out?&q:NULL);error=GetLastError();
 if((SUCCEEDED(hr)&&q!=d8_device.host)||(FAILED(hr)&&q)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: device identity mismatch");}
 if(q)d8_device.refs++;if(out){d8_device_memory(c,out,4,1);wr32(out,q?d8_device.guest:0);}d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_device_surface(CPU*c,unsigned slot) {
 LONG id=d8_api_entry(c,slot,2);D8DeviceObject*o=d8_semantic_frame(c);D8Surface*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(1);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 prev=d8_native_enter(c,slot,NULL,0);hr=slot==32?XM_GetRenderTarget(c,o->host,out?&q:NULL):XM_GetDepthStencilSurface(c,o->host,out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"D3D8 surface getter: NULL success");}
 d8_resource_output(c,out,hr,q,D8_SURFACE);d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_device_GetRenderTarget(CPU*c){d8_device_surface(c,32);}
static void d8_device_GetDepthStencilSurface(CPU*c){d8_device_surface(c,33);}
static void d8_resource_GetContainer(CPU*c) {
 LONG id=d8_api_entry(c,307,3);D8Resource*r=d8_resource(c,ARG(0),D8_SURFACE);GUID iid;void*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);unsigned kind;
 d8_device_memory(c,ARG(1),16,0);memcpy(&iid,G2H(ARG(1)),16);if(out)d8_device_memory(c,out,4,1);
 /* Container IUnknown is ambiguous; require the exact typed interface. */
 kind=!memcmp(&iid,&d8_texture_iid,16)?D8_TEXTURE:!memcmp(&iid,&d8_cube_iid,16)?D8_CUBE:0;
 if(!kind&&memcmp(&iid,&d8_device_iid,16))xrt_fatal(c,76,"D3D8 surface: untyped container IID");
 if(kind)d8_resource_reserve(c,kind);
 prev=d8_native_enter(c,307,&iid,16);hr=XM_GetContainer(c,(D8Surface*)r->host,&iid,out?&q:NULL);error=GetLastError();
 if(kind)d8_resource_output(c,out,hr,q,kind);
 else {if((SUCCEEDED(hr)&&q!=d8_device.host)||(FAILED(hr)&&q)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 surface: container identity");}if(q)d8_device.refs++;if(out){d8_device_memory(c,out,4,1);wr32(out,q?d8_device.guest:0);}}
 d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_resource_GetDesc(CPU*c) {
 LONG id=d8_api_entry(c,308,2);D8Resource*r=d8_resource(c,ARG(0),0);D8SurfaceDesc desc;CPU*prev;HRESULT hr;DWORD error;unsigned n=r->kind==D8_SURFACE?32:r->kind==D8_VERTEX?24:20;uint32_t out=ARG(1);
 if(D8_TEXLIKE(r->kind))xrt_fatal(c,76,"D3D8 texture: use GetLevelDesc");
 d8_device_memory(c,out,n,1);memcpy(&desc,G2H(out),n);
 prev=d8_native_enter(c,308,NULL,0);hr=r->kind==D8_SURFACE?XM_GetDesc(c,(D8Surface*)r->host,&desc):XM_GetDesc(c,(D8Buffer*)r->host,(D8BufferDesc*)&desc);error=GetLastError();
 d8_device_memory(c,out,n,1);memcpy(G2H(out),&desc,n);d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_resource_cleanup(void) {
 unsigned i;if(d8_locks){d8_native_failed=1;return;}
 for(i=d8_resource_used;i;i--){D8Resource*r=&d8_resources[i-1];while(r->refs){XM_Release(NULL,r->host);d8_resource_drop(r);}}
}

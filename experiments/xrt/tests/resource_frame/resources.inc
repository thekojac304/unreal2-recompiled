/* Native COM ownership, typed handles and copied lock transport.
 * No private native AddRef pins: they would change public reference counts.
 * Retired handles are never reassigned, even if the native address is reused.
 * Native bindings retain native resources; lookups always acquire a real ref.
 */
enum {D8_SURFACE=1,D8_TEXTURE=3,D8_VERTEX=6,D8_INDEX=7,D8_RESOURCE_LIMIT=4096};
typedef struct D8Resource {
 uint32_t guest,refs,kind,bindings;
 D8Unknown*host;
 BYTE*shadow,*valid;unsigned length,format;
 /* One outstanding lock per object. Guest staging is never a host pointer. */
 uint32_t staging,bytes,rows,rowbytes,level,flags,offset;
 INT pitch;BYTE*locked;
} D8Resource;
static D8Resource d8_resources[D8_RESOURCE_LIMIT];
static unsigned d8_resource_used,d8_locks;
static uint64_t d8_shadow_bytes;
static uint32_t d8_resource_vtables[8];
static D8Resource*d8_bound_streams[16],*d8_bound_indices,*d8_bound_textures[8];
static const GUID d8_surface_iid={0xb96eebca,0xb326,0x4ea5,{0x88,0x2f,0x2f,0xf5,0xba,0xe0,0x21,0xdd}};
static const GUID d8_texture_iid={0xe4cdd575,0x2866,0x4f01,{0xb1,0x2e,0x7e,0xec,0xe1,0xec,0x93,0x58}};
static const GUID d8_vertex_iid={0x8aeeeac7,0x05f9,0x44d4,{0xb5,0x91,0x00,0x0b,0x0d,0xf1,0xcb,0x95}};
static const GUID d8_index_iid={0x0e689c9a,0x053d,0x44a0,{0x9d,0x92,0xdb,0x0e,0x3d,0x75,0x0f,0x86}};
static const GUID d8_resource_iid={0x1b36bb7b,0x09b7,0x410a,{0xb4,0x45,0x7d,0x14,0x30,0xd7,0xb3,0x3f}};
static const GUID d8_base_texture_iid={0xb4211cfa,0x51b9,0x4a9f,{0xab,0x78,0xdb,0x99,0xb2,0xbb,0x67,0x8e}};
static const char* d8_surface_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.GetContainer","D8R.GetDesc","D8R.LockRect","D8R.UnlockRect"};
static const char* d8_texture_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.SetPriority","D8R.GetPriority","D8R.PreLoad","D8R.GetType","D8R.SetLOD","D8R.GetLOD","D8R.GetLevelCount","D8R.GetLevelDesc","D8R.GetSurfaceLevel","D8R.LockRect","D8R.UnlockRect","D8R.AddDirtyRect"};
static const char* d8_buffer_names[]={"D8R.QueryInterface","D8R.AddRef","D8R.Release","D8R.GetDevice","D8R.Unsupported","D8R.Unsupported","D8R.Unsupported","D8R.SetPriority","D8R.GetPriority","D8R.PreLoad","D8R.GetType","D8R.Lock","D8R.Unlock","D8R.GetDesc"};
static void d8_resource_guard(CPU*c) {
 if(d8_rendering||d8_creating||d8_native_failed)xrt_fatal(c,76,"D3D8 resource: reentrant or failed native operation");
 if(d8_device.host){xrt_gui_device_window(c,d8_device.focus);xrt_gui_device_window(c,d8_device.window);}
}
static D8Resource*d8_resource(CPU*c,uint32_t guest,unsigned kind) {
 unsigned i;d8_resource_guard(c);
 for(i=0;i<d8_resource_used;i++) {D8Resource*r=&d8_resources[i];
  if(guest&&r->guest==guest&&r->refs&&r->host) {
   if(kind&&r->kind!=kind)xrt_fatal(c,76,"D3D8 resource: wrong interface type");
   return r;
  }
 }
 xrt_fatal(c,76,"D3D8 resource: stale or unknown handle %08x",guest);
}
static void d8_resource_reserve(CPU*c,unsigned kind) {
 d8_resource_guard(c);
 if(d8_resource_used==D8_RESOURCE_LIMIT)xrt_fatal(c,76,"D3D8 resource: handle capacity");
 if(!d8_resource_vtables[kind])d8_resource_vtables[kind]=com_vtable(kind==D8_SURFACE?d8_surface_names:kind==D8_TEXTURE?d8_texture_names:d8_buffer_names,kind==D8_SURFACE?11:kind==D8_TEXTURE?19:14);
}
/* Called inside the native scope, adopting exactly the returned reference. */
static uint32_t d8_resource_adopt(CPU*c,void*host,unsigned kind) {
 unsigned i;D8Resource*r;
 if(!host)return 0;
 for(i=0;i<d8_resource_used;i++)if(d8_resources[i].host==host&&(d8_resources[i].refs||d8_resources[i].bindings)) {
  r=&d8_resources[i];if(r->kind!=kind||r->refs==UINT32_MAX){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: identity/type/reference inconsistency");}
  if(!r->refs)d8_device.children++;r->refs++;return r->guest;
 }
 if(d8_resource_used==D8_RESOURCE_LIMIT){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: adoption capacity");}
 r=&d8_resources[d8_resource_used++];memset(r,0,sizeof *r);
 r->guest=xrt_rt_alloc(4,4);wr32(r->guest,d8_resource_vtables[kind]);r->kind=kind;r->host=host;r->refs=1;d8_device.children++;
 xrt_event("d3d8_resource_adopt","\"guest\":%u,\"type\":%u,\"generation\":%u",r->guest,kind,d8_resource_used);
 return r->guest;
}
static void d8_resource_output(CPU*c,uint32_t out,HRESULT hr,void*q,unsigned kind) {
 uint32_t token=0;
 if(FAILED(hr)&&q){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: failed native call returned an owned object");}
 if(q)token=d8_resource_adopt(c,q,kind);
 if(out){d8_device_memory(c,out,4,1);wr32(out,token);}
}
static void d8_resource_retire(D8Resource*r) {
 if(!r->refs&&!r->bindings){r->host=NULL;if(r->shadow){d8_shadow_bytes-=2ull*r->length;HeapFree(GetProcessHeap(),0,r->shadow);}if(r->valid)HeapFree(GetProcessHeap(),0,r->valid);r->shadow=r->valid=NULL;}
}
static void d8_resource_bind(D8Resource**binding,D8Resource*r) {
 D8Resource*old=*binding;if(r)r->bindings++;*binding=r;if(old){old->bindings--;d8_resource_retire(old);}
}
static void d8_resource_device_dead(void) {
 unsigned i;for(i=0;i<16;i++)d8_resource_bind(&d8_bound_streams[i],NULL);
 for(i=0;i<8;i++)d8_resource_bind(&d8_bound_textures[i],NULL);d8_resource_bind(&d8_bound_indices,NULL);
}
static void d8_resource_up_reset(int indexed) {
 d8_resource_bind(&d8_bound_streams[0],NULL);if(indexed)d8_resource_bind(&d8_bound_indices,NULL);
}
static void d8_resource_drop(D8Resource*r) {
 if(!--r->refs){d8_device.children--;d8_resource_retire(r);if(!d8_device.refs&&!d8_device.children)d8_device_dead(&d8_device);}
}
static int d8_resource_iid_known(D8Resource*r,const GUID*iid) {
 const GUID*own=r->kind==D8_SURFACE?&d8_surface_iid:r->kind==D8_TEXTURE?&d8_texture_iid:r->kind==D8_VERTEX?&d8_vertex_iid:&d8_index_iid;
 return !memcmp(iid,&com_iunknown,16)||!memcmp(iid,own,16)||(r->kind!=D8_SURFACE&&!memcmp(iid,&d8_resource_iid,16))||(r->kind==D8_TEXTURE&&!memcmp(iid,&d8_base_texture_iid,16));
}
static void d8_resource_Unsupported(CPU*c){xrt_fatal(c,76,"D3D8 resource: private data interface unsupported");}
static void d8_resource_QueryInterface(CPU*c) {
 LONG id=d8_api_entry(c,300,3);D8Resource*r=d8_resource(c,ARG(0),0);GUID iid;void*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);
 d8_device_memory(c,ARG(1),16,0);memcpy(&iid,G2H(ARG(1)),16);if(out)d8_device_memory(c,out,4,1);
 if(r->refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 resource: reference overflow");
 prev=d8_native_enter(c,300,&iid,16);hr=r->host->vt->QueryInterface(r->host,&iid,out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&(!d8_resource_iid_known(r,&iid)||q!=r->host)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: unmodelled successful QI");}
 d8_resource_output(c,out,hr,q,r->kind);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_resource_AddRef(CPU*c) {
 LONG id=d8_api_entry(c,301,1);D8Resource*r=d8_resource(c,ARG(0),0);CPU*prev;ULONG n;DWORD error;
 if(r->refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 resource: reference overflow");
 prev=d8_native_enter(c,301,NULL,0);n=r->host->vt->AddRef(r->host);error=GetLastError();r->refs++;d8_semantic_return(c,prev,id,1,(HRESULT)n,error);
}
static void d8_resource_Release(CPU*c) {
 LONG id=d8_api_entry(c,302,1);D8Resource*r=d8_resource(c,ARG(0),0);CPU*prev;ULONG n;DWORD error;
 if(d8_locks)xrt_fatal(c,76,"D3D8 resource: Release while mapped resources exist");
 prev=d8_native_enter(c,302,NULL,0);n=r->host->vt->Release(r->host);error=GetLastError();d8_resource_drop(r);d8_semantic_return(c,prev,id,1,(HRESULT)n,error);
}
static void d8_resource_GetDevice(CPU*c) {
 LONG id=d8_api_entry(c,303,2);D8Resource*r=d8_resource(c,ARG(0),0);D8Device*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(1);
 if(out)d8_device_memory(c,out,4,1);if(d8_device.refs==UINT32_MAX)xrt_fatal(c,76,"D3D8 device: reference overflow");
 prev=d8_native_enter(c,303,NULL,0);hr=r->host->vt->GetDevice(r->host,out?&q:NULL);error=GetLastError();
 if((SUCCEEDED(hr)&&q!=d8_device.host)||(FAILED(hr)&&q)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 resource: device identity mismatch");}
 if(q)d8_device.refs++;if(out){d8_device_memory(c,out,4,1);wr32(out,q?d8_device.guest:0);}d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_device_surface(CPU*c,unsigned slot) {
 LONG id=d8_api_entry(c,slot,2);D8DeviceObject*o=d8_semantic_frame(c);D8Surface*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(1);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 prev=d8_native_enter(c,slot,NULL,0);hr=slot==32?o->host->vt->GetRenderTarget(o->host,out?&q:NULL):o->host->vt->GetDepthStencilSurface(o->host,out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"D3D8 surface getter: NULL success");}
 d8_resource_output(c,out,hr,q,D8_SURFACE);d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_device_GetRenderTarget(CPU*c){d8_device_surface(c,32);}
static void d8_device_GetDepthStencilSurface(CPU*c){d8_device_surface(c,33);}
static void d8_resource_GetContainer(CPU*c) {
 LONG id=d8_api_entry(c,307,3);D8Resource*r=d8_resource(c,ARG(0),D8_SURFACE);GUID iid;void*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);unsigned kind;
 d8_device_memory(c,ARG(1),16,0);memcpy(&iid,G2H(ARG(1)),16);if(out)d8_device_memory(c,out,4,1);
 /* Container IUnknown is ambiguous; require the exact typed interface. */
 kind=!memcmp(&iid,&d8_texture_iid,16)?D8_TEXTURE:0;
 if(!kind&&memcmp(&iid,&d8_device_iid,16))xrt_fatal(c,76,"D3D8 surface: untyped container IID");
 if(kind)d8_resource_reserve(c,kind);
 prev=d8_native_enter(c,307,&iid,16);hr=((D8Surface*)r->host)->vt->GetContainer((D8Surface*)r->host,&iid,out?&q:NULL);error=GetLastError();
 if(kind)d8_resource_output(c,out,hr,q,kind);
 else {if((SUCCEEDED(hr)&&q!=d8_device.host)||(FAILED(hr)&&q)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 surface: container identity");}if(q)d8_device.refs++;if(out){d8_device_memory(c,out,4,1);wr32(out,q?d8_device.guest:0);}}
 d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_resource_GetDesc(CPU*c) {
 LONG id=d8_api_entry(c,308,2);D8Resource*r=d8_resource(c,ARG(0),0);D8SurfaceDesc desc;CPU*prev;HRESULT hr;DWORD error;unsigned n=r->kind==D8_SURFACE?32:r->kind==D8_VERTEX?24:20;uint32_t out=ARG(1);
 if(r->kind==D8_TEXTURE)xrt_fatal(c,76,"D3D8 texture: use GetLevelDesc");
 d8_device_memory(c,out,n,1);memcpy(&desc,G2H(out),n);
 prev=d8_native_enter(c,308,NULL,0);hr=r->kind==D8_SURFACE?((D8Surface*)r->host)->vt->GetDesc((D8Surface*)r->host,&desc):((D8Buffer*)r->host)->vt->GetDesc((D8Buffer*)r->host,(D8BufferDesc*)&desc);error=GetLastError();
 d8_device_memory(c,out,n,1);memcpy(G2H(out),&desc,n);d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_resource_cleanup(void) {
 unsigned i;if(d8_locks){d8_native_failed=1;return;}
 for(i=d8_resource_used;i;i--){D8Resource*r=&d8_resources[i-1];while(r->refs){r->host->vt->Release(r->host);d8_resource_drop(r);}}
}

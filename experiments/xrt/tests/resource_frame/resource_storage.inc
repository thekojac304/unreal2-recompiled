/* Bounded storage: native descriptors determine mip extents and lock pitches.
 * A single outstanding map prevents texture/surface alias-lock ambiguity.
 * This explicit capacity trap can be expanded after game-path evidence.
 */
static void d8_device_CreateTexture(CPU*c) {
 LONG id=d8_api_entry(c,20,8);D8DeviceObject*o=d8_semantic_frame(c);D8Texture*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(7);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_TEXTURE);
 if(ARG(1)>o->caps.words[22]||ARG(2)>o->caps.words[23]||ARG(3)>32||ARG(6)>3)xrt_fatal(c,76,"CreateTexture: dimensions/levels/pool outside bounded domain");
 prev=d8_native_enter(c,20,NULL,0);hr=o->host->vt->CreateTexture(o->host,ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),ARG(6),out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"CreateTexture: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_TEXTURE);d8_semantic_return(c,prev,id,8,hr,error);
}
static void d8_create_buffer(CPU*c,unsigned kind) {
 unsigned slot=kind==D8_VERTEX?23:24;LONG id=d8_api_entry(c,slot,6);D8DeviceObject*o=d8_semantic_frame(c);D8Buffer*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(5);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,kind);
 if(ARG(1)>64u*1024u*1024u||ARG(4)>3)xrt_fatal(c,76,"CreateBuffer: size/pool exceeds implementation capacity");
 prev=d8_native_enter(c,slot,NULL,0);
 hr=kind==D8_VERTEX?o->host->vt->CreateVertexBuffer(o->host,ARG(1),ARG(2),ARG(3),ARG(4),out?&q:NULL):o->host->vt->CreateIndexBuffer(o->host,ARG(1),ARG(2),ARG(3),ARG(4),out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"CreateBuffer: NULL native success");}
 d8_resource_output(c,out,hr,q,kind);d8_semantic_return(c,prev,id,6,hr,error);
}
static void d8_device_CreateVertexBuffer(CPU*c){d8_create_buffer(c,D8_VERTEX);}
static void d8_device_CreateIndexBuffer(CPU*c){d8_create_buffer(c,D8_INDEX);}
static void d8_resource_GetSurfaceLevel(CPU*c) {
 LONG id=d8_api_entry(c,315,3);D8Resource*r=d8_resource(c,ARG(0),D8_TEXTURE);D8Surface*q=NULL;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 prev=d8_native_enter(c,315,NULL,0);hr=((D8Texture*)r->host)->vt->GetSurfaceLevel((D8Texture*)r->host,ARG(1),out?&q:NULL);error=GetLastError();
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"GetSurfaceLevel: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_SURFACE);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_resource_GetLevelDesc(CPU*c) {
 LONG id=d8_api_entry(c,314,3);D8Resource*r=d8_resource(c,ARG(0),D8_TEXTURE);D8SurfaceDesc desc;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(2);
 d8_device_memory(c,out,32,1);memcpy(&desc,G2H(out),32);
 prev=d8_native_enter(c,314,NULL,0);hr=((D8Texture*)r->host)->vt->GetLevelDesc((D8Texture*)r->host,ARG(1),&desc);error=GetLastError();
 d8_device_memory(c,out,32,1);memcpy(G2H(out),&desc,32);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_lock_flags(CPU*c,unsigned flags) {
 if(d8_locks)xrt_fatal(c,76,"D3D8 map: one outstanding resource map supported");
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
 return r->kind==D8_SURFACE?((D8Surface*)r->host)->vt->GetDesc((D8Surface*)r->host,d):((D8Texture*)r->host)->vt->GetLevelDesc((D8Texture*)r->host,level,d);
}
static void d8_resource_LockRect(CPU*c) {
 LONG id;D8Resource*r;unsigned level,out,rectarg,flags,n,rowbytes,rows,y;RECT rect;D8SurfaceDesc desc;D8Locked lock;
 CPU*prev;HRESULT hr;DWORD error,saved=GetLastError();uint32_t stage;uint64_t size;
 /* Read this only after validating a minimum complete surface frame. */
 id=d8_api_entry(c,316,4);r=d8_resource(c,ARG(0),0);
 if(r->kind!=D8_SURFACE&&r->kind!=D8_TEXTURE)xrt_fatal(c,76,"LockRect: wrong resource type");
 n=r->kind==D8_TEXTURE?5:4;d8_device_memory(c,c->r[ESP],4*(n+1),0);
 level=r->kind==D8_TEXTURE?ARG(1):0;out=ARG(n-3);rectarg=ARG(n-2);flags=ARG(n-1);d8_lock_flags(c,flags);d8_device_memory(c,out,8,1);
 if(rectarg){d8_device_memory(c,rectarg,16,0);memcpy(&rect,G2H(rectarg),16);}
 prev=xrt_gui_callback_enter(c);d8_rendering=1;hr=d8_desc_native(r,level,&desc);d8_rendering=0;xrt_gui_callback_leave(prev);SetLastError(saved);
 if(FAILED(hr))xrt_fatal(c,76,"LockRect: cannot obtain native mip descriptor");
 if(!rectarg){rect.left=rect.top=0;rect.right=desc.width;rect.bottom=desc.height;}
 if(rect.left<0||rect.top<0||rect.right<=rect.left||rect.bottom<=rect.top||(uint32_t)rect.right>desc.width||(uint32_t)rect.bottom>desc.height)xrt_fatal(c,76,"LockRect: unsafe rectangle");
 if((desc.format&0xffffff)==0x545844 && ((rect.left|rect.top)&3))xrt_fatal(c,76,"LockRect: compressed origin alignment");
 d8_map_size(c,desc.format,rect.right-rect.left,rect.bottom-rect.top,&rowbytes,&rows);
 lock.pitch=(INT)rd32(out);lock.bits=(void*)(uintptr_t)1; /* distinguish untouched from native NULL output */
 prev=d8_native_enter(c,316,&rect,16);hr=r->kind==D8_SURFACE?((D8Surface*)r->host)->vt->LockRect((D8Surface*)r->host,&lock,rectarg?&rect:NULL,flags):((D8Texture*)r->host)->vt->LockRect((D8Texture*)r->host,level,&lock,rectarg?&rect:NULL,flags);error=GetLastError();
 if(SUCCEEDED(hr)) {
  /* Native map remains owned until matching successful Unlock. */
  d8_locks=1;r->locked=lock.bits;r->pitch=lock.pitch;r->level=level;r->flags=flags;r->rows=rows;r->rowbytes=rowbytes;
  size=(uint64_t)(unsigned)lock.pitch*rows;
  if(!lock.bits||lock.pitch<=0||(unsigned)lock.pitch<rowbytes||size>64u*1024u*1024u){d8_native_failed=1;xrt_fatal(c,76,"LockRect: unsafe native layout");}
  stage=xrt_virtual_alloc(c,(unsigned)size);if(!stage)xrt_fatal(c,76,"LockRect: staging allocation failed");r->staging=stage;r->bytes=(unsigned)size;
  d8_device_memory(c,stage,(unsigned)size,1);memset(G2H(stage),0,(size_t)size);
  for(y=0;y<rows;y++)memcpy((BYTE*)G2H(stage)+y*lock.pitch,(BYTE*)lock.bits+y*lock.pitch,rowbytes);
  d8_device_memory(c,out,8,1);wr32(out,(unsigned)lock.pitch);wr32(out+4,stage);
 } else {if(lock.bits&&(uintptr_t)lock.bits!=1){d8_native_failed=1;xrt_fatal(c,76,"LockRect: failed call returned map");}d8_device_memory(c,out,8,1);wr32(out,(unsigned)lock.pitch);if(!lock.bits)wr32(out+4,0);}
 d8_semantic_return(c,prev,id,n,hr,error);
}
static void d8_resource_Lock(CPU*c) {
 LONG id=d8_api_entry(c,311,5);D8Resource*r=d8_resource(c,ARG(0),0);D8BufferDesc desc={0};unsigned offset=ARG(1),size=ARG(2),out=ARG(3),flags=ARG(4);BYTE*data=(BYTE*)(uintptr_t)1;CPU*prev;HRESULT hr;DWORD error,saved=GetLastError();
 if(r->kind!=D8_VERTEX&&r->kind!=D8_INDEX)xrt_fatal(c,76,"Lock: wrong resource type");
 d8_lock_flags(c,flags);d8_device_memory(c,out,4,1);
 prev=xrt_gui_callback_enter(c);d8_rendering=1;hr=((D8Buffer*)r->host)->vt->GetDesc((D8Buffer*)r->host,&desc);d8_rendering=0;xrt_gui_callback_leave(prev);SetLastError(saved);
 if(FAILED(hr)||offset>desc.size)xrt_fatal(c,76,"Lock: unsafe buffer descriptor/range");
 if(!r->shadow){
  if(!desc.size||desc.size>64u*1024u*1024u)xrt_fatal(c,76,"Lock: buffer capacity");
  if(d8_shadow_bytes+2ull*desc.size>256u*1024u*1024u)xrt_fatal(c,76,"Lock: 256 MiB host mirror budget exceeded");
  r->shadow=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,desc.size);r->valid=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,desc.size);
  if(!r->shadow||!r->valid){if(r->shadow)HeapFree(GetProcessHeap(),0,r->shadow);if(r->valid)HeapFree(GetProcessHeap(),0,r->valid);r->shadow=r->valid=NULL;xrt_fatal(c,76,"Lock: host mirror allocation failed");}r->length=desc.size;r->format=desc.format;d8_shadow_bytes+=2ull*desc.size;
 }
 if(desc.size!=r->length||desc.format!=r->format)xrt_fatal(c,76,"Lock: native buffer descriptor changed");
 if(!size)size=desc.size-offset;
 if(!size||(uint64_t)offset+size>desc.size||size>64u*1024u*1024u)xrt_fatal(c,76,"Lock: unsafe buffer range");
 prev=d8_native_enter(c,311,NULL,0);hr=((D8Buffer*)r->host)->vt->Lock((D8Buffer*)r->host,offset,ARG(2),&data,flags);error=GetLastError();
 if(SUCCEEDED(hr)) {
  d8_locks=1;r->locked=data;r->flags=flags;r->offset=offset;r->bytes=size;r->rows=1;r->rowbytes=size;r->pitch=size;
  if(!data){d8_native_failed=1;xrt_fatal(c,76,"Lock: NULL native map");}
  r->staging=xrt_virtual_alloc(c,size);if(!r->staging)xrt_fatal(c,76,"Lock: staging allocation failed");d8_device_memory(c,r->staging,size,1);memcpy(G2H(r->staging),data,size);
  if(flags&0x2000)memset(r->valid,0,r->length);
  d8_device_memory(c,out,4,1);wr32(out,r->staging);
 } else {if(data&&(uintptr_t)data!=1){d8_native_failed=1;xrt_fatal(c,76,"Lock: failed native map");}if(!data){d8_device_memory(c,out,4,1);wr32(out,0);}}
 d8_semantic_return(c,prev,id,5,hr,error);
}
static void d8_unlock(CPU*c,int rectangle) {
 LONG id=d8_api_entry(c,rectangle?317:312,1);D8Resource*r=d8_resource(c,ARG(0),0);unsigned n=rectangle&&r->kind==D8_TEXTURE?2:1,y;BYTE*copy=NULL;CPU*prev;HRESULT hr;DWORD error;
 d8_device_memory(c,c->r[ESP],4*(n+1),0);
 if((rectangle&&(r->kind!=D8_TEXTURE&&r->kind!=D8_SURFACE))||(!rectangle&&(r->kind!=D8_VERTEX&&r->kind!=D8_INDEX)))xrt_fatal(c,76,"Unlock: wrong resource type");
 if(!r->locked||!r->staging||(n==2&&ARG(1)!=r->level))xrt_fatal(c,76,"Unlock: missing or mismatched map");
 if(!(r->flags&0x10)) {
  /* Snapshot before entering native code; revalidate even if callback changed pages. */
  copy=d8_draw_copy(c,r->staging,r->bytes);
  for(y=0;y<r->rows;y++)memcpy(r->locked+(size_t)y*r->pitch,copy+(size_t)y*r->pitch,r->rowbytes);
  if(r->shadow){memcpy(r->shadow+r->offset,copy,r->bytes);memset(r->valid+r->offset,1,r->bytes);}
  HeapFree(GetProcessHeap(),0,copy);
 }
 prev=d8_native_enter(c,rectangle?317:312,NULL,0);
 hr=!rectangle?((D8Buffer*)r->host)->vt->Unlock((D8Buffer*)r->host):r->kind==D8_SURFACE?((D8Surface*)r->host)->vt->UnlockRect((D8Surface*)r->host):((D8Texture*)r->host)->vt->UnlockRect((D8Texture*)r->host,r->level);error=GetLastError();
 if(SUCCEEDED(hr)){if(!xrt_virtual_free(c,r->staging))xrt_fatal(c,76,"Unlock: staging invalidation failed");r->staging=0;r->locked=NULL;d8_locks=0;}
 else {d8_native_failed=1; /* Preserve failure HRESULT; retain mapping until process teardown. */}
 d8_semantic_return(c,prev,id,n,hr,error);
}
static void d8_resource_UnlockRect(CPU*c){d8_unlock(c,1);}
static void d8_resource_Unlock(CPU*c){d8_unlock(c,0);}
static void d8_resource_AddDirtyRect(CPU*c) {
 LONG id=d8_api_entry(c,318,2);D8Resource*r=d8_resource(c,ARG(0),D8_TEXTURE);RECT rect;CPU*prev;HRESULT hr;DWORD error;
 if(ARG(1)){d8_device_memory(c,ARG(1),16,0);memcpy(&rect,G2H(ARG(1)),16);}
 prev=d8_native_enter(c,318,NULL,0);hr=((D8Texture*)r->host)->vt->AddDirtyRect((D8Texture*)r->host,ARG(1)?&rect:NULL);error=GetLastError();d8_semantic_return(c,prev,id,2,hr,error);
}
static void d8_resource_scalar(CPU*c,unsigned slot,unsigned n) {
 LONG id=d8_api_entry(c,slot+300,n);D8Resource*r=d8_resource(c,ARG(0),0);D8Texture*t=(D8Texture*)r->host;D8Buffer*b=(D8Buffer*)r->host;CPU*prev;DWORD value,error;
 if(r->kind==D8_SURFACE||(slot>=11&&r->kind!=D8_TEXTURE))xrt_fatal(c,76,"D3D8 resource: scalar method type mismatch");
 prev=d8_native_enter(c,slot+300,NULL,0);
 switch(slot){
 case 7:value=r->kind==D8_TEXTURE?t->vt->SetPriority(t,ARG(1)):b->vt->SetPriority(b,ARG(1));break;
 case 8:value=r->kind==D8_TEXTURE?t->vt->GetPriority(t):b->vt->GetPriority(b);break;
 case 9:
  if(r->kind==D8_TEXTURE)t->vt->PreLoad(t);else b->vt->PreLoad(b);error=GetLastError();
  d8_semantic_checkpoint(c,2,309,NULL,0,0,error);d8_rendering=0;xrt_gui_callback_leave(prev);
  xrt_set_last_error(c,error);c->rv=pop32(c);c->r[ESP]+=4;
  d8_semantic_checkpoint(c,3,309,NULL,0,0,error);
  xrt_event("d3d8_resource_void_return","\"id\":%ld,\"method\":\"PreLoad\",\"last_error\":%lu,\"esp\":%u,\"return\":%u",id,error,c->r[ESP],c->rv);
  d8_evidence_blob(id,"guest_cpu_return",c,sizeof *c);return;
 case 10:value=r->kind==D8_TEXTURE?t->vt->GetType(t):b->vt->GetType(b);break;
 case 11:value=t->vt->SetLOD(t,ARG(1));break;case 12:value=t->vt->GetLOD(t);break;default:value=t->vt->GetLevelCount(t);break;
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

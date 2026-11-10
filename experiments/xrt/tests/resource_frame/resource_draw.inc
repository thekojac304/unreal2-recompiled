static D8Resource*d8_optional(CPU*c,unsigned token,unsigned kind){return token?d8_resource(c,token,kind):NULL;}
static void d8_device_SetTexture(CPU*c) {
 LONG id=d8_api_entry(c,61,3);D8DeviceObject*o=d8_semantic_frame(c);D8Resource*r;CPU*prev;HRESULT hr;DWORD error;unsigned stage=ARG(1);
 if(stage>=8)xrt_fatal(c,76,"SetTexture: stage outside capacity");r=d8_optional(c,ARG(2),D8_TEXTURE);
 prev=d8_native_enter(c,61,NULL,0);hr=o->host->vt->SetTexture(o->host,stage,r?r->host:NULL);error=GetLastError();if(SUCCEEDED(hr))d8_resource_bind(&d8_bound_textures[stage],r);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_device_SetStreamSource(CPU*c) {
 LONG id=d8_api_entry(c,83,4);D8DeviceObject*o=d8_semantic_frame(c);D8Resource*r;CPU*prev;HRESULT hr;DWORD error;unsigned stream=ARG(1);
 if(stream>=16||stream>=o->caps.words[47]||ARG(3)>o->caps.words[48])xrt_fatal(c,76,"SetStreamSource: stream/stride outside capacity");r=d8_optional(c,ARG(2),D8_VERTEX);
 prev=d8_native_enter(c,83,NULL,0);hr=o->host->vt->SetStreamSource(o->host,stream,r?r->host:NULL,ARG(3));error=GetLastError();if(SUCCEEDED(hr))d8_resource_bind(&d8_bound_streams[stream],r);d8_semantic_return(c,prev,id,4,hr,error);
}
static void d8_device_SetIndices(CPU*c) {
 LONG id=d8_api_entry(c,85,3);D8DeviceObject*o=d8_semantic_frame(c);D8Resource*r=d8_optional(c,ARG(1),D8_INDEX);CPU*prev;HRESULT hr;DWORD error;
 prev=d8_native_enter(c,85,NULL,0);hr=o->host->vt->SetIndices(o->host,r?r->host:NULL,ARG(2));error=GetLastError();if(SUCCEEDED(hr))d8_resource_bind(&d8_bound_indices,r);d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_binding_get(CPU*c,unsigned slot) {
 unsigned nargs=slot==84?4:3,kind=slot==60?D8_TEXTURE:slot==84?D8_VERTEX:D8_INDEX;
 LONG id=d8_api_entry(c,slot,nargs);D8DeviceObject*o=d8_semantic_frame(c);unsigned out=ARG(slot==86?1:2),extra=slot==84?ARG(3):slot==86?ARG(2):0;void*q=NULL;DWORD value=0,error;CPU*prev;HRESULT hr;
 if(out)d8_device_memory(c,out,4,1);if(extra)d8_device_memory(c,extra,4,1);
 if(out&&extra&&((uint64_t)out<(uint64_t)extra+4&&(uint64_t)extra<(uint64_t)out+4))xrt_fatal(c,76,"D3D8 binding getter: overlapping outputs");
 d8_resource_reserve(c,kind);prev=d8_native_enter(c,slot,NULL,0);
 hr=slot==60?o->host->vt->GetTexture(o->host,ARG(1),out?&q:NULL):slot==84?o->host->vt->GetStreamSource(o->host,ARG(1),out?&q:NULL,extra?&value:NULL):o->host->vt->GetIndices(o->host,out?&q:NULL,extra?&value:NULL);error=GetLastError();
 d8_resource_output(c,out,hr,q,kind);if(extra){d8_device_memory(c,extra,4,1);wr32(extra,value);}d8_semantic_return(c,prev,id,nargs,hr,error);
}
static void d8_device_GetTexture(CPU*c){d8_binding_get(c,60);}
static void d8_device_GetStreamSource(CPU*c){d8_binding_get(c,84);}
static void d8_device_GetIndices(CPU*c){d8_binding_get(c,86);}
static void d8_device_SetRenderTarget(CPU*c) {
 LONG id=d8_api_entry(c,31,3);D8DeviceObject*o=d8_semantic_frame(c);D8Resource*rt=d8_optional(c,ARG(1),D8_SURFACE),*ds=d8_optional(c,ARG(2),D8_SURFACE);CPU*prev;HRESULT hr;DWORD error;
 if(d8_locks)xrt_fatal(c,76,"SetRenderTarget: mapped resource");
 prev=d8_native_enter(c,31,NULL,0);hr=o->host->vt->SetRenderTarget(o->host,(D8Surface*)(rt?rt->host:NULL),(D8Surface*)(ds?ds->host:NULL));error=GetLastError();
 /* Do not cache target state: native may update RT before failing depth. */
 d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_device_UpdateTexture(CPU*c) {
 LONG id=d8_api_entry(c,29,3);D8DeviceObject*o=d8_semantic_frame(c);D8Resource*s=d8_optional(c,ARG(1),D8_TEXTURE),*t=d8_optional(c,ARG(2),D8_TEXTURE);CPU*prev;HRESULT hr;DWORD error;
 if(d8_locks)xrt_fatal(c,76,"UpdateTexture: mapped resource");
 prev=d8_native_enter(c,29,NULL,0);hr=o->host->vt->UpdateTexture(o->host,(D8Texture*)(s?s->host:NULL),(D8Texture*)(t?t->host:NULL));error=GetLastError();d8_semantic_return(c,prev,id,3,hr,error);
}
static void d8_buffer_readable(CPU*c,D8Resource*r,uint64_t start,uint64_t size) {
 uint64_t i;if(!r||!r->shadow||start+size<start||start+size>r->length)xrt_fatal(c,76,"D3D8 draw: buffer range outside owned upload");
 for(i=start;i<start+size;i++)if(!r->valid[i])xrt_fatal(c,76,"D3D8 draw: buffer range has no validated upload");
}
static void d8_buffer_draw(CPU*c,int indexed) {
 unsigned n=indexed?6:4,slot=indexed?71:70;LONG id=d8_api_entry(c,slot,n);D8DeviceObject*o=d8_semantic_frame(c);
 unsigned type=ARG(1),count=ARG(indexed?5:3),nv=d8_draw_vertices(c,type,count),min=indexed?ARG(2):ARG(2),num=indexed?ARG(3):nv,start=indexed?ARG(4):0,i,ix;
 D8Resource*b=d8_bound_indices;void*vs=NULL,*ib=NULL;DWORD strides[16]={0},base=0,error,saved=GetLastError();unsigned required[16],stream;CPU*prev;HRESULT hr;uint64_t end;
 if(d8_locks)xrt_fatal(c,76,"D3D8 draw: mapped resource");
 if(indexed&&!b)xrt_fatal(c,76,"D3D8 draw: requires owned index binding");
 d8_layout_requirements(c,o,count,required);
 for(stream=0;stream<16;stream++)if(required[stream]&&!d8_bound_streams[stream])xrt_fatal(c,76,"D3D8 draw: missing declared stream binding");
 /* Query actual bindings and release exactly the query references. No stale cache. */
 prev=xrt_gui_callback_enter(c);d8_rendering=1;
 for(stream=0;stream<16;stream++)if(required[stream]) {
  vs=NULL;hr=o->host->vt->GetStreamSource(o->host,stream,&vs,&strides[stream]);
  if(vs)((D8Unknown*)vs)->vt->Release((D8Unknown*)vs);
  if(FAILED(hr)||vs!=d8_bound_streams[stream]->host){d8_native_failed=1;xrt_fatal(c,76,"D3D8 draw: native stream identity mismatch");}
 }
 if(indexed){hr=o->host->vt->GetIndices(o->host,&ib,&base);if(ib)((D8Unknown*)ib)->vt->Release((D8Unknown*)ib);if(FAILED(hr)||ib!=b->host){d8_native_failed=1;xrt_fatal(c,76,"D3D8 draw: native index identity mismatch");}}
 d8_rendering=0;xrt_gui_callback_leave(prev);SetLastError(saved);
 end=(uint64_t)base+min+num;if(end>UINT32_MAX||(num&&end-1>o->caps.words[46]))xrt_fatal(c,76,"D3D8 draw: vertex range/caps overflow");
 for(stream=0;stream<16;stream++)if(required[stream]) {
  DWORD stride=strides[stream];
  if(!stride||stride<required[stream]||stride>o->caps.words[48])xrt_fatal(c,76,"D3D8 draw: declared stream stride/caps mismatch");
  d8_buffer_readable(c,d8_bound_streams[stream],((uint64_t)base+min)*stride,num?(uint64_t)(num-1)*stride+required[stream]:0);
 }
 if(indexed){unsigned isize=b->format==101?2:b->format==102?4:0;if(!isize)xrt_fatal(c,76,"D3D8 draw: unknown index format");
  d8_buffer_readable(c,b,(uint64_t)start*isize,(uint64_t)nv*isize);
  for(i=0;i<nv;i++){if(isize==2){WORD value;memcpy(&value,b->shadow+((size_t)start+i)*2,2);ix=value;}else memcpy(&ix,b->shadow+((size_t)start+i)*4,4);
   if(ix<min||(uint64_t)ix>=((uint64_t)min+num))xrt_fatal(c,76,"D3D8 draw: index outside declared vertices");}
 }
 prev=d8_native_enter(c,slot,NULL,0);hr=indexed?o->host->vt->DrawIndexedPrimitive(o->host,type,min,num,start,count):o->host->vt->DrawPrimitive(o->host,type,min,count);error=GetLastError();d8_semantic_return(c,prev,id,n,hr,error);
}
static void d8_device_DrawPrimitive(CPU*c){d8_buffer_draw(c,0);}
static void d8_device_DrawIndexedPrimitive(CPU*c){d8_buffer_draw(c,1);}

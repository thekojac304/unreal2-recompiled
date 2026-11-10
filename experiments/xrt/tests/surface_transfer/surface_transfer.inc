/* Surface creation, backbuffer access, transfer and readback share the existing
 * typed resource registry. Native HRESULT/last-error and untouched out parameters
 * remain observable. The sentinel is private; it is never written to the guest. */
static void d8_surface_result(CPU*c,uint32_t out,HRESULT hr,D8Surface*q) {
 if(q==(D8Surface*)(uintptr_t)1) {
  if(SUCCEEDED(hr)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 surface: success left output untouched");}
  return;
 }
 if(SUCCEEDED(hr)&&!q){d8_native_failed=1;xrt_fatal(c,76,"D3D8 surface: NULL native success");}
 d8_resource_output(c,out,hr,q,D8_SURFACE);
}
static void d8_device_GetBackBuffer(CPU*c) {
 LONG id=d8_api_entry(c,16,4);D8DeviceObject*o=d8_semantic_frame(c);D8Surface*q=(D8Surface*)(uintptr_t)1;
 CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(3);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 prev=d8_native_enter(c,16,NULL,0);hr=o->host->vt->GetBackBuffer(o->host,ARG(1),ARG(2),out?&q:NULL);error=GetLastError();
 d8_surface_result(c,out,hr,q);d8_semantic_return(c,prev,id,4,hr,error);
}
static void d8_create_surface(CPU*c,unsigned slot) {
 unsigned n=slot==25?7:slot==26?6:5;LONG id=d8_api_entry(c,slot,n);D8DeviceObject*o=d8_semantic_frame(c);
 D8Surface*q=(D8Surface*)(uintptr_t)1;CPU*prev;HRESULT hr;DWORD error;uint32_t out=ARG(n-1);
 if(out)d8_device_memory(c,out,4,1);d8_resource_reserve(c,D8_SURFACE);
 /* Explicit allocation capacity; zero/invalid formats are still native errors. */
 if(ARG(1)>16384||ARG(2)>16384||(uint64_t)ARG(1)*ARG(2)>16u*1024u*1024u)
  xrt_fatal(c,76,"CreateSurface: extent exceeds allocation capacity");
 prev=d8_native_enter(c,slot,NULL,0);
 if(slot==25)hr=o->host->vt->CreateRenderTarget(o->host,ARG(1),ARG(2),ARG(3),ARG(4),(BOOL)ARG(5),out?&q:NULL);
 else if(slot==26)hr=o->host->vt->CreateDepthStencilSurface(o->host,ARG(1),ARG(2),ARG(3),ARG(4),out?&q:NULL);
 else hr=o->host->vt->CreateImageSurface(o->host,ARG(1),ARG(2),ARG(3),out?&q:NULL);
 error=GetLastError();d8_surface_result(c,out,hr,q);d8_semantic_return(c,prev,id,n,hr,error);
}
static void d8_device_CreateRenderTarget(CPU*c){d8_create_surface(c,25);}
static void d8_device_CreateDepthStencilSurface(CPU*c){d8_create_surface(c,26);}
static void d8_device_CreateImageSurface(CPU*c){d8_create_surface(c,27);}
static void d8_device_CopyRects(CPU*c) {
 LONG id=d8_api_entry(c,28,6);D8DeviceObject*o=d8_semantic_frame(c);
 D8Resource*s=d8_optional(c,ARG(1),D8_SURFACE),*t=d8_optional(c,ARG(4),D8_SURFACE);
 unsigned n=ARG(3);RECT rects[256];POINT points[256];CPU*prev;HRESULT hr;DWORD error;
 if(d8_locks)xrt_fatal(c,76,"CopyRects: outstanding resource map");
 if(n>256)xrt_fatal(c,76,"CopyRects: rectangle count exceeds capacity");
 /* Validate both ranges before copying. NULL arrays and zero count retain their
  * actual native semantics; even unused non-NULL arrays get safe local storage. */
 if(ARG(2)&&n)d8_device_memory(c,ARG(2),n*sizeof(RECT),0);
 if(ARG(5)&&n)d8_device_memory(c,ARG(5),n*sizeof(POINT),0);
 memset(rects,0,sizeof rects);memset(points,0,sizeof points);
 if(ARG(2)&&n)memcpy(rects,G2H(ARG(2)),n*sizeof(RECT));
 if(ARG(5)&&n)memcpy(points,G2H(ARG(5)),n*sizeof(POINT));
 prev=d8_native_enter(c,28,rects,ARG(2)?n*sizeof(RECT):0);
 hr=o->host->vt->CopyRects(o->host,(D8Surface*)(s?s->host:NULL),ARG(2)?rects:NULL,n,(D8Surface*)(t?t->host:NULL),ARG(5)?points:NULL);error=GetLastError();
 d8_semantic_return(c,prev,id,6,hr,error);
}
static void d8_device_GetFrontBuffer(CPU*c) {
 LONG id=d8_api_entry(c,30,2);D8DeviceObject*o=d8_semantic_frame(c);D8Resource*r=d8_optional(c,ARG(1),D8_SURFACE);
 CPU*prev;HRESULT hr;DWORD error;
 if(d8_locks)xrt_fatal(c,76,"GetFrontBuffer: outstanding resource map");
 prev=d8_native_enter(c,30,NULL,0);hr=o->host->vt->GetFrontBuffer(o->host,(D8Surface*)(r?r->host:NULL));error=GetLastError();
 d8_semantic_return(c,prev,id,2,hr,error);
}

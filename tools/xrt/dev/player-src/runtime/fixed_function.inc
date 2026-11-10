/* Fixed-function lighting, clip planes and transform queries reached by the
 * first world frames. Plain value structures: D3DLIGHT8 is 26 dwords, a clip
 * plane 4 floats, a matrix 16 floats. The native vtable rows are called
 * directly (no generated monitor wrapper exists for slots 39 and 43..49). */
typedef HRESULT(WINAPI*D8SetLightFn)(D8Device*,DWORD,const void*);
typedef HRESULT(WINAPI*D8GetLightFn)(D8Device*,DWORD,void*);
typedef HRESULT(WINAPI*D8LightEnableFn)(D8Device*,DWORD,BOOL);
typedef HRESULT(WINAPI*D8GetLightEnableFn)(D8Device*,DWORD,BOOL*);
typedef HRESULT(WINAPI*D8MultiplyFn)(D8Device*,DWORD,const D8Matrix*);
static void*d8_vt_row(D8DeviceObject*o,unsigned slot){return ((void*const*)o->host->vt)[slot];}
static const char*d8_ff_name(unsigned slot) {
    switch(slot){case 39:return "D8Device.MultiplyTransform";case 44:return "D8Device.SetLight";case 45:return "D8Device.GetLight";
    case 46:return "D8Device.LightEnable";case 47:return "D8Device.GetLightEnable";case 48:return "D8Device.SetClipPlane";default:return "D8Device.GetClipPlane";}
}
static void d8_ff_probe(XmRequest*q,int event,unsigned slot,uint64_t a,uint64_t result) {
    q->event=event;q->domain=XM_NATIVE;q->name=d8_ff_name(slot);q->slot=slot;q->interface_id=2;q->count=1;
    q->values[0].type=XM_U32;q->values[0].bytes=4;q->values[0].value=a;q->result=result;xm_probe(xm_current_cpu(),q);
}
static void d8_device_SetLight(CPU*c) {
    LONG id=d8_api_entry(c,44,3);D8DeviceObject*o=d8_semantic_frame(c);uint32_t w[26];unsigned i;CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    d8_device_memory(c,ARG(2),sizeof w,0);memcpy(w,G2H(ARG(2)),sizeof w);
    d8_evidence_blob(id,"light",w,sizeof w);
    d8_domain(c,w[0]>=1&&w[0]<=3?D8_VALID:D8_INVALID,"SetLight type");
    for(i=1;i<26;i++)d8_domain(c,d8_finite(w[i])?D8_VALID:D8_UNIMPLEMENTED,"SetLight nonfinite input");
    previous=d8_native_enter(c,44,w,sizeof w);d8_ff_probe(&q,XM_BEGIN,44,ARG(1),0);
    hr=((D8SetLightFn)d8_vt_row(o,44))(o->host,ARG(1),w);error=GetLastError();d8_ff_probe(&q,XM_END,44,ARG(1),(uint64_t)hr);
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_GetLight(CPU*c) {
    LONG id=d8_api_entry(c,45,3);D8DeviceObject*o=d8_semantic_frame(c);uint32_t w[26],out=ARG(2);CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    d8_device_memory(c,out,sizeof w,1);memcpy(w,G2H(out),sizeof w);
    previous=d8_native_enter(c,45,w,sizeof w);d8_ff_probe(&q,XM_BEGIN,45,ARG(1),0);
    hr=((D8GetLightFn)d8_vt_row(o,45))(o->host,ARG(1),w);error=GetLastError();d8_ff_probe(&q,XM_END,45,ARG(1),(uint64_t)hr);
    d8_device_memory(c,out,sizeof w,1);memcpy(G2H(out),w,sizeof w);d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_LightEnable(CPU*c) {
    LONG id=d8_api_entry(c,46,3);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    previous=d8_native_enter(c,46,NULL,0);d8_ff_probe(&q,XM_BEGIN,46,ARG(1),0);
    hr=((D8LightEnableFn)d8_vt_row(o,46))(o->host,ARG(1),(BOOL)ARG(2));error=GetLastError();d8_ff_probe(&q,XM_END,46,ARG(1),(uint64_t)hr);
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_GetLightEnable(CPU*c) {
    LONG id=d8_api_entry(c,47,3);D8DeviceObject*o=d8_semantic_frame(c);uint32_t out=ARG(2);BOOL v;CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    d8_device_memory(c,out,4,1);v=(BOOL)rd32(out);
    previous=d8_native_enter(c,47,NULL,0);d8_ff_probe(&q,XM_BEGIN,47,ARG(1),0);
    hr=((D8GetLightEnableFn)d8_vt_row(o,47))(o->host,ARG(1),&v);error=GetLastError();d8_ff_probe(&q,XM_END,47,ARG(1),(uint64_t)hr);
    d8_device_memory(c,out,4,1);wr32(out,(uint32_t)v);d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_SetClipPlane(CPU*c) {
    LONG id=d8_api_entry(c,48,3);D8DeviceObject*o=d8_semantic_frame(c);uint32_t w[4];unsigned i;CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    d8_device_memory(c,ARG(2),sizeof w,0);memcpy(w,G2H(ARG(2)),sizeof w);
    for(i=0;i<4;i++)d8_domain(c,d8_finite(w[i])?D8_VALID:D8_UNIMPLEMENTED,"SetClipPlane nonfinite input");
    previous=d8_native_enter(c,48,w,sizeof w);d8_ff_probe(&q,XM_BEGIN,48,ARG(1),0);
    hr=((D8SetLightFn)d8_vt_row(o,48))(o->host,ARG(1),w);error=GetLastError();d8_ff_probe(&q,XM_END,48,ARG(1),(uint64_t)hr);
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_GetClipPlane(CPU*c) {
    LONG id=d8_api_entry(c,49,3);D8DeviceObject*o=d8_semantic_frame(c);uint32_t w[4],out=ARG(2);CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    d8_device_memory(c,out,sizeof w,1);memcpy(w,G2H(out),sizeof w);
    previous=d8_native_enter(c,49,w,sizeof w);d8_ff_probe(&q,XM_BEGIN,49,ARG(1),0);
    hr=((D8GetLightFn)d8_vt_row(o,49))(o->host,ARG(1),w);error=GetLastError();d8_ff_probe(&q,XM_END,49,ARG(1),(uint64_t)hr);
    d8_device_memory(c,out,sizeof w,1);memcpy(G2H(out),w,sizeof w);d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_GetTransform(CPU*c) {
    LONG id=d8_api_entry(c,38,3);D8DeviceObject*o=d8_semantic_frame(c);D8Matrix m;uint32_t out=ARG(2);CPU*previous;HRESULT hr;DWORD error;
    d8_device_memory(c,out,sizeof m,1);memcpy(&m,G2H(out),sizeof m);
    d8_domain(c,d8_transform_domain(ARG(1))?D8_VALID:D8_INVALID,"GetTransform identifier");
    previous=d8_native_enter(c,38,&m,sizeof m);hr=XM_GetTransform(c,o->host,ARG(1),&m);error=GetLastError();
    d8_device_memory(c,out,sizeof m,1);memcpy(G2H(out),&m,sizeof m);d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_MultiplyTransform(CPU*c) {
    LONG id=d8_api_entry(c,39,3);D8DeviceObject*o=d8_semantic_frame(c);D8Matrix m;unsigned i;CPU*previous;HRESULT hr;DWORD error;XmRequest q={0};
    d8_device_memory(c,ARG(2),sizeof m,0);memcpy(&m,G2H(ARG(2)),sizeof m);
    d8_domain(c,d8_transform_domain(ARG(1))?D8_VALID:D8_INVALID,"MultiplyTransform identifier");
    for(i=0;i<16;i++)d8_domain(c,d8_finite(m.bits[i])?D8_VALID:D8_UNIMPLEMENTED,"MultiplyTransform nonfinite input");
    previous=d8_native_enter(c,39,&m,sizeof m);d8_ff_probe(&q,XM_BEGIN,39,ARG(1),0);
    hr=((D8MultiplyFn)d8_vt_row(o,39))(o->host,ARG(1),&m);error=GetLastError();d8_ff_probe(&q,XM_END,39,ARG(1),(uint64_t)hr);
    d8_semantic_return(c,previous,id,3,hr,error);
}

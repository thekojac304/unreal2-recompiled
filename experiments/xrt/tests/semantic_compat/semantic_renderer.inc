/* Typed semantic D3D8 adapters. No renderer callsite, raw property profile,
 * exact native success, ordering, or synthetic-fixture tuple is an admission rule.
 * Unknown resources/shader handles still require ownership implementations.
 */
#include "semantic_policy.h"
static void d8_domain(CPU*c,int verdict,const char*method) {
    if(verdict!=D8_VALID) {
        xrt_event("d3d8_semantic_rejection","\"method\":\"%s\",\"classification\":%d,\"site\":%u",method,verdict,c->pc);
        xrt_fatal(c,76,"%s: %s (native operation not called)",method,
            verdict==D8_INVALID?"invalid argument domain":verdict==D8_CAPABILITY?"unsupported live device capability":"valid feature requires implementation/characterization");
    }
}
__declspec(noinline) static D8DeviceObject* d8_semantic_frame(CPU*c) {
    D8DeviceObject*o=d8_device_object(c,ARG(0));CPU*previous;HRESULT hr;DWORD error;
    d8_render_ready(c,o);
    if(!o->caps_valid) {
        previous=xrt_gui_callback_enter(c);d8_rendering=1;error=GetLastError();
        hr=o->host->vt->GetDeviceCaps(o->host,&o->caps);
        d8_rendering=0;xrt_gui_callback_leave(previous);SetLastError(error);
        xrt_event("d3d8_live_caps","\"result\":%u,\"object\":%u",(unsigned)hr,o->guest);
        d8_evidence_blob(0,"live_caps",&o->caps,sizeof o->caps);
        if(FAILED(hr))xrt_fatal(c,76,"GetDeviceCaps failed during semantic validation: %08x",(unsigned)hr);
        o->caps_valid=1;
    }
    return o;
}
static unsigned d8_semantic_slot,d8_semantic_size;
static const void*d8_semantic_input;
static CPU* d8_native_enter(CPU*c,unsigned slot,const void*input,unsigned size) {
    CPU*previous=xrt_gui_callback_enter(c);d8_rendering=1;
    d8_semantic_slot=slot;d8_semantic_input=input;d8_semantic_size=size;
    d8_semantic_checkpoint(c,1,slot,input,size,0,xrt_get_last_error(c));
    SetLastError(xrt_get_last_error(c));return previous;
}
static void d8_semantic_return(CPU*c,CPU*previous,LONG id,unsigned n,HRESULT hr,DWORD error) {
    d8_semantic_checkpoint(c,2,d8_semantic_slot,d8_semantic_input,d8_semantic_size,(unsigned)hr,error);
    d8_rendering=0;xrt_gui_callback_leave(previous);xrt_set_last_error(c,error);RET_STD(n,hr);
    d8_semantic_checkpoint(c,3,d8_semantic_slot,d8_semantic_input,d8_semantic_size,(unsigned)hr,error);
    xrt_event("d3d8_semantic_return","\"id\":%ld,\"result\":%u,\"last_error\":%lu,\"esp\":%u,\"return\":%u,\"outcome\":\"%s\"",id,(unsigned)hr,error,c->r[ESP],c->rv,SUCCEEDED(hr)?"supported":"native-failure");
    d8_evidence_blob(id,"guest_cpu_return",c,sizeof *c);
}
static void d8_device_SetRenderState(CPU*c) {
    LONG id=d8_api_entry(c,50,3);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    d8_domain(c,d8_render_domain(ARG(1),ARG(2),o->caps.words),"SetRenderState");
    if(ARG(1)==153 && ARG(2) && !(o->behavior&0xa0u))
        d8_domain(c,D8_CAPABILITY,"SetRenderState software vertex processing requires software/mixed creation");
    previous=d8_native_enter(c,50,NULL,0);hr=o->host->vt->SetRenderState(o->host,ARG(1),ARG(2));error=GetLastError();
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_SetTextureStageState(CPU*c) {
    LONG id=d8_api_entry(c,63,4);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    d8_domain(c,d8_stage_domain(ARG(1),ARG(2),ARG(3),o->caps.words),"SetTextureStageState");
    previous=d8_native_enter(c,63,NULL,0);hr=o->host->vt->SetTextureStageState(o->host,ARG(1),ARG(2),ARG(3));error=GetLastError();
    d8_semantic_return(c,previous,id,4,hr,error);
}
static void d8_device_SetMaterial(CPU*c) {
    LONG id=d8_api_entry(c,42,2);D8DeviceObject*o=d8_semantic_frame(c);D8Material local;
    CPU*previous;HRESULT hr;DWORD error;unsigned words[17],i;
    d8_device_memory(c,ARG(1),sizeof local,0);memcpy(&local,G2H(ARG(1)),sizeof local);
    d8_evidence_blob(id,"material",&local,sizeof local);memcpy(words,&local,sizeof words);
    for(i=0;i<17;i++)d8_domain(c,d8_finite(words[i])?D8_VALID:D8_UNIMPLEMENTED,"SetMaterial nonfinite input");
    d8_domain(c,d8_float_nonnegative(words[16])?D8_VALID:D8_INVALID,"SetMaterial power");
    previous=d8_native_enter(c,42,&local,sizeof local);hr=o->host->vt->SetMaterial(o->host,&local);error=GetLastError();
    d8_semantic_return(c,previous,id,2,hr,error);
}
static void d8_device_SetTransform(CPU*c) {
    LONG id=d8_api_entry(c,37,3);D8DeviceObject*o=d8_semantic_frame(c);D8Matrix local;
    CPU*previous;HRESULT hr;DWORD error;unsigned i;
    d8_device_memory(c,ARG(2),sizeof local,0);memcpy(&local,G2H(ARG(2)),sizeof local);
    d8_evidence_blob(id,"matrix",&local,sizeof local);
    d8_domain(c,d8_transform_domain(ARG(1))?D8_VALID:D8_INVALID,"SetTransform identifier");
    for(i=0;i<16;i++)d8_domain(c,d8_finite(local.bits[i])?D8_VALID:D8_UNIMPLEMENTED,"SetTransform nonfinite input");
    previous=d8_native_enter(c,37,&local,sizeof local);hr=o->host->vt->SetTransform(o->host,ARG(1),&local);error=GetLastError();
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_SetTexture(CPU*c) {
    LONG id=d8_api_entry(c,61,3);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    d8_domain(c,ARG(1)<8?D8_VALID:D8_INVALID,"SetTexture stage");
    if(ARG(2))xrt_fatal(c,76,"SAFETY: SetTexture non-NULL resource needs typed ownership; unknown token %08x",ARG(2));
    previous=d8_native_enter(c,61,NULL,0);hr=o->host->vt->SetTexture(o->host,ARG(1),NULL);error=GetLastError();
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_SetStreamSource(CPU*c) {
    LONG id=d8_api_entry(c,83,4);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    d8_domain(c,ARG(1)<o->caps.words[47]?D8_VALID:D8_CAPABILITY,"SetStreamSource stream");
    if(ARG(2))xrt_fatal(c,76,"SAFETY: SetStreamSource non-NULL resource needs typed ownership");
    d8_domain(c,ARG(3)<=o->caps.words[48]?D8_VALID:D8_CAPABILITY,"SetStreamSource stride");
    previous=d8_native_enter(c,83,NULL,0);hr=o->host->vt->SetStreamSource(o->host,ARG(1),NULL,ARG(3));error=GetLastError();
    d8_semantic_return(c,previous,id,4,hr,error);
}
static void d8_device_SetIndices(CPU*c) {
    LONG id=d8_api_entry(c,85,3);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    if(ARG(1))xrt_fatal(c,76,"SAFETY: SetIndices non-NULL resource needs typed ownership");
    /* BaseVertexIndex is a scalar even when unbinding the index buffer. */
    previous=d8_native_enter(c,85,NULL,0);hr=o->host->vt->SetIndices(o->host,NULL,ARG(2));error=GetLastError();
    d8_semantic_return(c,previous,id,3,hr,error);
}
static void d8_device_SetVertexShader(CPU*c) {
    LONG id=d8_api_entry(c,76,2);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    d8_domain(c,d8_fvf_domain(ARG(1)),"SetVertexShader FVF/owned shader");
    d8_domain(c,((ARG(1)>>8)&15u)<=(o->caps.words[35]&0xffffu)?D8_VALID:D8_CAPABILITY,"SetVertexShader texture coordinate capability");
    d8_domain(c,!(ARG(1)&0x20u) || (o->caps.words[35]&0x100000u)?D8_VALID:D8_CAPABILITY,"SetVertexShader point size capability");
    previous=d8_native_enter(c,76,NULL,0);hr=o->host->vt->SetVertexShader(o->host,ARG(1));error=GetLastError();
    d8_semantic_return(c,previous,id,2,hr,error);
}
static void d8_device_SetGammaRamp(CPU*c) {
    LONG id=d8_api_entry(c,18,3);D8DeviceObject*o=d8_semantic_frame(c);D8Gamma local;CPU*previous;DWORD error;
    unsigned before,after;
    d8_device_memory(c,ARG(2),sizeof local,0);memcpy(&local,G2H(ARG(2)),sizeof local);
    d8_evidence_blob(id,"gamma",&local,sizeof local);
    d8_domain(c,ARG(1)<=1?D8_VALID:D8_INVALID,"SetGammaRamp flags");
    d8_domain(c,(o->caps.words[3]&0x20000u)?D8_VALID:D8_CAPABILITY,"SetGammaRamp capability");
    previous=d8_native_enter(c,18,&local,sizeof local);before=_mm_getcsr();o->host->vt->SetGammaRamp(o->host,ARG(1),&local);
    error=GetLastError();after=_mm_getcsr();d8_semantic_checkpoint(c,2,18,&local,sizeof local,0,error);
    d8_rendering=0;xrt_gui_callback_leave(previous);
    /* RET() also returns from C, so pair the void-call evidence explicitly
     * after the guest stack update and before leaving this adapter. */
    xrt_set_last_error(c,error);c->rv=pop32(c);c->r[ESP]+=12;
    d8_semantic_checkpoint(c,3,18,&local,sizeof local,0,error);
    xrt_event("d3d8_semantic_void_return","\"id\":%ld,\"last_error\":%lu,\"mxcsr_before\":%u,\"mxcsr_after\":%u,\"esp\":%u,\"return\":%u",id,error,before,after,c->r[ESP],c->rv);
    d8_evidence_blob(id,"guest_cpu_return",c,sizeof *c);
}

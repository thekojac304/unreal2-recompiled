/* PROVISIONAL boundary adapter. Exact fixture cases only, no GPU qualification.
 * Not part of the accepted runtime. No host pointers are stored in guest memory. */
#define D8_BATCH_GROUP BATCH_GROUP_VALUE
#include "batch_cases.inc"
static const BatchCase* batch_case;
static uint32_t batch_ramp[384]; /* Explicitly sealed fixture bytes, NOT computed game gamma. */
static const DWORD batch_identity[16]={0x3f800000,0,0,0,0,0x3f800000,0,0,0,0,0x3f800000,0,0,0,0,0x3f800000};
static D8DeviceObject* batch_frame(CPU*c,unsigned n,unsigned slot) {
    D8DeviceObject*o;
    d8_device_memory(c,c->r[ESP],4*(n+1),0);
    o=d8_device_object(c,ARG(0));
    if(!batch_case || batch_case->group!=D8_BATCH_GROUP || batch_case->slot!=slot)
        xrt_fatal(c,76,"batch profile not sealed for method/group");
    d8_render_ready(c,o);return o;
}
static void batch_tuple(CPU*c,unsigned a,unsigned b,unsigned d) {
    if(a!=batch_case->a || b!=batch_case->b || d!=batch_case->c)
        xrt_fatal(c,76,"batch exact tuple refused");
}
static void batch_result(CPU*c,unsigned n,HRESULT hr,DWORD error) {
    xrt_set_last_error(c,error);RET_STD(n,hr);
}
#if D8_BATCH_GROUP==1 || D8_BATCH_GROUP==3
static void d8_device_SetRenderState(CPU*c) {
    D8DeviceObject*o=batch_frame(c,3,50);CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),ARG(2),0);
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetRenderState(o->host,ARG(1),ARG(2));error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,3,hr,error);
}
#elif D8_BATCH_GROUP==2 || D8_BATCH_GROUP==5
static void d8_device_SetTextureStageState(CPU*c) {
    D8DeviceObject*o=batch_frame(c,4,63);CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),ARG(2),ARG(3));
    if(ARG(1)>=8)xrt_fatal(c,76,"batch stage bound");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetTextureStageState(o->host,ARG(1),ARG(2),ARG(3));error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,4,hr,error);
}
#elif D8_BATCH_GROUP==4
static void d8_device_SetTransform(CPU*c) {
    D8DeviceObject*o=batch_frame(c,3,37);D8Matrix local;CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),0,0);d8_device_memory(c,ARG(2),sizeof local,0);
    memcpy(&local,G2H(ARG(2)),sizeof local);
    if(memcmp(&local,batch_identity,sizeof local))xrt_fatal(c,76,"batch identity matrix refused");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetTransform(o->host,ARG(1),&local);error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,3,hr,error);
}
#elif D8_BATCH_GROUP==6
static void d8_device_SetTexture(CPU*c) {
    D8DeviceObject*o=batch_frame(c,3,61);CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),ARG(2),0);
    if(ARG(1)>=8 || ARG(2))xrt_fatal(c,76,"batch NULL texture refused");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetTexture(o->host,ARG(1),NULL);error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,3,hr,error);
}
static void d8_device_SetStreamSource(CPU*c) {
    D8DeviceObject*o=batch_frame(c,4,83);CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),ARG(2),ARG(3));
    if(ARG(1)>=16 || ARG(2) || ARG(3))xrt_fatal(c,76,"batch NULL stream refused");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetStreamSource(o->host,ARG(1),NULL,0);error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,4,hr,error);
}
static void d8_device_SetIndices(CPU*c) {
    D8DeviceObject*o=batch_frame(c,3,85);CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),ARG(2),0);
    if(ARG(1)||ARG(2))xrt_fatal(c,76,"batch NULL indices refused");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetIndices(o->host,NULL,0);error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,3,hr,error);
}
#elif D8_BATCH_GROUP==7
static void d8_device_SetVertexShader(CPU*c) {
    D8DeviceObject*o=batch_frame(c,2,76);CPU*previous;HRESULT hr;DWORD error;
    batch_tuple(c,ARG(1),0,0);
    if(ARG(1)!=2)xrt_fatal(c,76,"batch FVF refused");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    hr=o->host->vt->SetVertexShader(o->host,2);error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);batch_result(c,2,hr,error);
}
#elif D8_BATCH_GROUP==8
static void d8_device_SetGammaRamp(CPU*c) {
    D8DeviceObject*o=batch_frame(c,3,18);D8Gamma local;CPU*previous;DWORD error;
    batch_tuple(c,ARG(1),0,0);d8_device_memory(c,ARG(2),sizeof local,0);
    memcpy(&local,G2H(ARG(2)),sizeof local);
    if(ARG(1)!=1 || memcmp(&local,batch_ramp,sizeof local))xrt_fatal(c,76,"batch gamma bytes refused");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;SetLastError(xrt_get_last_error(c));
    o->host->vt->SetGammaRamp(o->host,1,&local);error=GetLastError();
    d8_rendering=0;xrt_gui_callback_leave(previous);xrt_set_last_error(c,error);
    /* Void ABI: preserve guest EAX. Native volatile EAX has no promised value. */
    RET(12);
}
#elif D8_BATCH_GROUP==9
typedef uint32_t (*BatchGuestInvoke)(CPU*,uint32_t,uint32_t,uint32_t,uint32_t);
static BatchGuestInvoke batch_guest_invoke;
static uint32_t batch_viewport=0x8000,batch_resize_target=0x11104f20;
static void batch_ResizeViewport(CPU*c) {
    uint32_t flags,width,height,value;
    d8_device_memory(c,c->r[ESP],16,0);
    if(!batch_case || batch_case->group!=9 || c->r[ECX]!=batch_viewport || !batch_guest_invoke)
        xrt_fatal(c,76,"batch viewport identity/dispatch refused");
    d8_device_memory(c,batch_viewport,4,0);
    if(rd32(batch_viewport)!=0x9000)xrt_fatal(c,76,"batch viewport vtable identity refused");
    d8_device_memory(c,0x9088,4,0);
    if(rd32(0x9088)!=batch_resize_target)xrt_fatal(c,76,"batch viewport callback target refused");
    flags=ARG(0);width=ARG(1);height=ARG(2);batch_tuple(c,flags,width,height);
    value=batch_guest_invoke(c,batch_resize_target,flags,width,height);
    RET_STD(3,value);
}
#endif

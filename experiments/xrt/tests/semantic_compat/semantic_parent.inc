/* Known pointer-free capability queries: propagate backend failure normally.
 * RegisterSoftwareDevice callbacks and HMONITOR results still need models. */
static CPU*d8_parent_query_enter(CPU*c,D8Object*o) {
    if(d8_creating || d8_rendering)xrt_fatal(c,76,"SAFETY: reentrant parent D3D query");
    d8_creating=1;o->pending++;o->host->vt->AddRef(o->host);return xrt_gui_callback_enter(c);
}
static void d8_parent_query_leave(CPU*previous,D8Object*o) {
    xrt_gui_callback_leave(previous);o->host->vt->Release(o->host);o->pending--;d8_creating=0;
    if(!o->refs && !o->children && !o->pending)o->host=NULL;
}
static void d8_CheckDeviceType(CPU*c) {
    D8Object*o;D8Interface*host;CPU*previous;HRESULT hr;DWORD error;
    d8_api_entry(c,209,6);o=d8_object(c,ARG(0));host=o->host;previous=d8_parent_query_enter(c,o);
    if(ARG(1)>=host->vt->GetAdapterCount(host))xrt_fatal(c,76,"SAFETY: CheckDeviceType adapter outside live inventory");
    SetLastError(xrt_get_last_error(c));hr=host->vt->CheckDeviceType(host,ARG(1),ARG(2),ARG(3),ARG(4),(BOOL)ARG(5));error=GetLastError();
    d8_parent_query_leave(previous,o);d8_result(c,"CheckDeviceType",o,ARG(1),ARG(4),hr);xrt_set_last_error(c,error);RET_STD(6,hr);
}
static void d8_CheckDeviceMultiSampleType(CPU*c) {
    D8Object*o;D8Interface*host;CPU*previous;HRESULT hr;DWORD error;
    d8_api_entry(c,211,6);o=d8_object(c,ARG(0));host=o->host;previous=d8_parent_query_enter(c,o);
    if(ARG(1)>=host->vt->GetAdapterCount(host))xrt_fatal(c,76,"SAFETY: CheckDeviceMultiSampleType adapter outside live inventory");
    SetLastError(xrt_get_last_error(c));hr=host->vt->CheckDeviceMultiSampleType(host,ARG(1),ARG(2),ARG(3),(BOOL)ARG(4),ARG(5));error=GetLastError();
    d8_parent_query_leave(previous,o);d8_result(c,"CheckDeviceMultiSampleType",o,ARG(1),ARG(5),hr);xrt_set_last_error(c,error);RET_STD(6,hr);
}

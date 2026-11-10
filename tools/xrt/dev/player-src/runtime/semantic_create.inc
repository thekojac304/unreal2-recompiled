/* Windowed HAL creation: validate live combinations, not a captured profile. */
static void d8_creation_query(CPU*c,const char*name,HRESULT hr) {
    xrt_event("d3d8_creation_query","\"query\":\"%s\",\"result\":%u,\"last_error\":%lu",name,(unsigned)hr,GetLastError());
    if(FAILED(hr))xrt_fatal(c,76,"CreateDevice: live %s rejected combination hr=%08x; no device created",name,(unsigned)hr);
}
static void d8_creation_domain(CPU*c,D8Object*p,unsigned adapter,unsigned type,unsigned flags,unsigned pp) {
    D8Caps caps={0};D8Mode mode={0};D8Interface*host=p->host;DWORD saved=GetLastError();CPU*previous;
    unsigned format=rd32(pp+8),count=rd32(pp+12),multi=rd32(pp+16),swap=rd32(pp+20),vp=flags&0xe0u;
    unsigned depth=rd32(pp+32),df=rd32(pp+36),effective_format=format?format:22;
    /* Private pending reference protects a parent-first callback during any
     * native query. A fatal callback retains modules until process teardown. */
    d8_creating=1;p->pending++;XM_AddRef(c,host);previous=xrt_gui_callback_enter(c);
    if(adapter>=XM_GetAdapterCount(c,host))xrt_fatal(c,76,"SAFETY: CreateDevice adapter outside live inventory");
    d8_domain(c,type==1?D8_VALID:D8_UNIMPLEMENTED,"CreateDevice backend HAL scope");
    d8_domain(c,rd32(pp+28)?D8_VALID:D8_UNIMPLEMENTED,"CreateDevice fullscreen requires separate display scope");
    d8_domain(c,!(flags&0x10u)?D8_VALID:D8_UNIMPLEMENTED,"CreateDevice pure-device mode");
    d8_domain(c,!(flags&~0x1e6u) && (vp==0x20 || vp==0x40 || vp==0x80)?D8_VALID:D8_INVALID,"CreateDevice behavior/vertex processing");
    d8_domain(c,(flags&2)?D8_VALID:D8_UNIMPLEMENTED,"CreateDevice host FPU preservation");
    d8_domain(c,format==0 || (format>=20&&format<=26)?D8_VALID:D8_UNIMPLEMENTED,"CreateDevice RGB format");
    d8_domain(c,count<=3 && multi<=16 && swap>=1 && swap<=4?D8_VALID:D8_INVALID,"CreateDevice presentation enums");
    d8_domain(c,(multi==0 || swap==1) && (swap<=2 || count<=1)?D8_VALID:D8_INVALID,"CreateDevice multisample/swap/count");
    d8_domain(c,!(rd32(pp+40)&~3u) && rd32(pp+44)==0 && rd32(pp+48)==0?D8_VALID:D8_INVALID,"CreateDevice windowed flags/refresh/interval");
    d8_creation_query(c,"GetDeviceCaps",XM_GetDeviceCaps(c,host,adapter,type,&caps));
    d8_evidence_blob(0,"creation_caps",&caps,sizeof caps);
    d8_domain(c,(vp==0x20 || (caps.words[7]&0x10000u))?D8_VALID:D8_CAPABILITY,"CreateDevice hardware vertex processing");
    /* Zero dimensions ask the native API for the windowed default. */
    d8_domain(c,rd32(pp)<=caps.words[22] && rd32(pp+4)<=caps.words[23]?D8_VALID:D8_CAPABILITY,"CreateDevice dimensions");
    d8_creation_query(c,"GetAdapterDisplayMode",XM_GetAdapterDisplayMode(c,host,adapter,&mode));
    d8_evidence_blob(0,"creation_display_mode",&mode,sizeof mode);
    d8_creation_query(c,"CheckDeviceType",XM_CheckDeviceType(c,host,adapter,type,mode.format,effective_format,(BOOL)rd32(pp+28)));
    d8_creation_query(c,"CheckDeviceMultiSampleType",XM_CheckDeviceMultiSampleType(c,host,adapter,type,effective_format,(BOOL)rd32(pp+28),multi));
    if(depth) {
        d8_domain(c,df==70 || df==71 || df==73 || df==75 || df==77 || df==79 || df==80?D8_VALID:D8_UNIMPLEMENTED,"CreateDevice depth format");
        d8_creation_query(c,"CheckDepthStencilMatch",XM_CheckDepthStencilMatch(c,host,adapter,type,mode.format,effective_format,df));
        d8_creation_query(c,"CheckDepthMultiSample",XM_CheckDeviceMultiSampleType(c,host,adapter,type,df,(BOOL)rd32(pp+28),multi));
    }
    xrt_gui_callback_leave(previous);XM_Release(c,host);p->pending--;d8_creating=0;
    if(!p->refs && !p->children && !p->pending)p->host=NULL;
    if(!p->refs)xrt_fatal(c,76,"SAFETY: CreateDevice parent released during preflight callback");
    SetLastError(saved);
}

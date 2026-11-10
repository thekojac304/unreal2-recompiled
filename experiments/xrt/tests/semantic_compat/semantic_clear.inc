/* D3DRECT array marshalling; never forward guest memory to the host. */
static void d8_device_Clear(CPU*c) {
    LONG id=d8_api_entry(c,36,7);D8DeviceObject*o=d8_semantic_frame(c);
    unsigned count=ARG(1),pointer=ARG(2),flags=ARG(3),bits=ARG(5),i;
    uint64_t bytes=(uint64_t)count*sizeof(D8Rect);D8Rect*local=NULL;float z;
    CPU*previous;HRESULT hr;DWORD error;
    d8_domain(c,(flags && !(flags&~7u))?D8_VALID:D8_INVALID,"Clear flags");
    if((flags&6u) && !o->depth)d8_domain(c,D8_CAPABILITY,"Clear requires depth/stencil surface");
    if((flags&4u) && o->depthformat!=73 && o->depthformat!=75 && o->depthformat!=79)
        d8_domain(c,D8_CAPABILITY,"Clear requires stencil format");
    if(flags&2u)d8_domain(c,d8_float_nonnegative(bits) && (bits&0x7fffffffu)<=0x3f800000u?D8_VALID:D8_INVALID,"Clear depth range");
    if(bytes>0xffffffffu)xrt_fatal(c,76,"SAFETY: Clear rectangle array size overflow");
    if(count) {
        d8_device_memory(c,pointer,(unsigned)bytes,0);
        local=(D8Rect*)malloc((size_t)bytes);
        if(!local)xrt_fatal(c,76,"Clear host rectangle allocation failed");
        memcpy(local,G2H(pointer),(size_t)bytes);d8_evidence_blob(id,"clear_rectangles",local,(unsigned)bytes);
        for(i=0;i<count;i++)if(local[i].right<local[i].left || local[i].bottom<local[i].top) {
            free(local);d8_domain(c,D8_INVALID,"Clear inverted rectangle");
        }
    }
    memcpy(&z,&bits,4);previous=d8_native_enter(c,36,local,(unsigned)bytes);
    hr=o->host->vt->Clear(o->host,count,local,flags,ARG(4),z,ARG(6));error=GetLastError();
    d8_semantic_return(c,previous,id,7,hr,error);free(local);
}

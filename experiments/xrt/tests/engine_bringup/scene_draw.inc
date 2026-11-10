/* Scene/viewport and UP drawing. No guest or guest COM pointer reaches native
 * D3D. The existing non-NULL resource and shader-handle guards remain. */
static uint32_t d8_draw_vertices(CPU*c,unsigned type,unsigned primitives) {
    uint64_t n;
    switch(type){
    case 1:n=primitives;break;case 2:n=2ull*primitives;break;
    case 3:n=primitives?1ull+primitives:0;break;case 4:n=3ull*primitives;break;
    case 5:case 6:n=primitives?2ull+primitives:0;break;
    default:xrt_fatal(c,76,"D3D8 draw: unknown primitive topology");
    }
    if(n>UINT32_MAX)xrt_fatal(c,76,"D3D8 draw: vertex count overflow");
    return (uint32_t)n;
}
static unsigned d8_fvf_bytes(CPU*c,unsigned fvf) {
    unsigned pos=fvf&14u,n=(fvf>>8)&15u,bytes,i;
    d8_domain(c,d8_fvf_domain(fvf),"Draw UP FVF");
    bytes=pos==2?12:pos==4?16:12+4*((pos-4)/2);
    if(fvf&0x10u)bytes+=12;if(fvf&0x20u)bytes+=4;
    if(fvf&0x40u)bytes+=4;if(fvf&0x80u)bytes+=4;
    for(i=0;i<n;i++){static const unsigned dims[]={2,3,4,1};bytes+=4*dims[(fvf>>(16+2*i))&3u];}
    return bytes;
}
static void d8_draw_layout(CPU*c,D8DeviceObject*o,unsigned primitives,unsigned stride) {
    DWORD fvf=0,error=GetLastError();HRESULT hr;CPU*previous;
    if(primitives>o->caps.words[45])xrt_fatal(c,76,"D3D8 draw: primitive count exceeds caps");
    previous=xrt_gui_callback_enter(c);d8_rendering=1;
    hr=o->host->vt->GetVertexShader(o->host,&fvf);
    d8_rendering=0;xrt_gui_callback_leave(previous);SetLastError(error);
    if(FAILED(hr))xrt_fatal(c,76,"D3D8 draw: cannot resolve native FVF");
    if(!stride || stride<d8_fvf_bytes(c,fvf) || stride>o->caps.words[48])
        xrt_fatal(c,76,"D3D8 draw: stride incompatible with FVF/caps");
}
static unsigned d8_draw_size(CPU*c,uint64_t count,unsigned stride) {
    uint64_t n=count*stride;
    /* Explicit implementation capacity, not an invented API success/failure. */
    if(n>64u*1024u*1024u)xrt_fatal(c,76,"D3D8 draw: copied input exceeds 64 MiB capacity");
    return (unsigned)n;
}
static void*d8_draw_copy(CPU*c,uint32_t p,unsigned n) {
    void*q;if(!n)return NULL;
    d8_device_memory(c,p,n,0);q=HeapAlloc(GetProcessHeap(),0,n);
    if(!q)xrt_fatal(c,76,"D3D8 draw: host staging allocation failed");
    memcpy(q,G2H(p),n);return q;
}
static unsigned d8_draw_hash(const void*p,unsigned n) {
    const BYTE*b=p;unsigned h=2166136261u,i;for(i=0;i<n;i++)h=(h^b[i])*16777619u;return h;
}
static void d8_device_TestCooperativeLevel(CPU*c) {
    LONG id=d8_api_entry(c,3,1);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    previous=d8_native_enter(c,3,NULL,0);hr=o->host->vt->TestCooperativeLevel(o->host);error=GetLastError();
    d8_semantic_return(c,previous,id,1,hr,error);
}
static void d8_device_BeginScene(CPU*c) {
    LONG id=d8_api_entry(c,34,1);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    previous=d8_native_enter(c,34,NULL,0);hr=o->host->vt->BeginScene(o->host);error=GetLastError();
    d8_semantic_return(c,previous,id,1,hr,error);
}
static void d8_device_EndScene(CPU*c) {
    LONG id=d8_api_entry(c,35,1);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    previous=d8_native_enter(c,35,NULL,0);hr=o->host->vt->EndScene(o->host);error=GetLastError();
    d8_semantic_return(c,previous,id,1,hr,error);
}
static void d8_device_SetViewport(CPU*c) {
    LONG id=d8_api_entry(c,40,2);D8DeviceObject*o=d8_semantic_frame(c);D8Viewport v;CPU*previous;HRESULT hr;DWORD error;
    d8_device_memory(c,ARG(1),sizeof v,0);memcpy(&v,G2H(ARG(1)),sizeof v);
    /* Render-target bounds and ordering are the native device's decision. */
    if(!d8_finite(v.minz)||!d8_finite(v.maxz))xrt_fatal(c,76,"SetViewport: nonfinite depth");
    previous=d8_native_enter(c,40,&v,sizeof v);hr=o->host->vt->SetViewport(o->host,&v);error=GetLastError();
    d8_semantic_return(c,previous,id,2,hr,error);
}
static void d8_device_GetViewport(CPU*c) {
    LONG id=d8_api_entry(c,41,2);D8DeviceObject*o=d8_semantic_frame(c);D8Viewport v;uint32_t out=ARG(1);CPU*previous;HRESULT hr;DWORD error;
    d8_device_memory(c,out,sizeof v,1);memcpy(&v,G2H(out),sizeof v);
    previous=d8_native_enter(c,41,&v,sizeof v);hr=o->host->vt->GetViewport(o->host,&v);error=GetLastError();
    /* Copy actual output even on failure, preserving partial native writes. */
    d8_device_memory(c,out,sizeof v,1); /* A callback may have changed protection. */
    memcpy(G2H(out),&v,sizeof v);d8_semantic_return(c,previous,id,2,hr,error);
}
static void d8_device_DrawPrimitiveUP(CPU*c) {
    LONG id=d8_api_entry(c,72,5);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    unsigned type=ARG(1),count=ARG(2),stride=ARG(4),n=d8_draw_vertices(c,type,count),size;
    void*vertices;DWORD evidence[6];
    d8_draw_layout(c,o,count,stride);size=d8_draw_size(c,n,stride);vertices=d8_draw_copy(c,ARG(3),size);
    evidence[0]=type;evidence[1]=count;evidence[2]=stride;evidence[3]=n;evidence[4]=size;evidence[5]=d8_draw_hash(vertices,size);
    previous=d8_native_enter(c,72,evidence,sizeof evidence);
    hr=o->host->vt->DrawPrimitiveUP(o->host,type,count,vertices,stride);error=GetLastError();
    if(vertices)HeapFree(GetProcessHeap(),0,vertices);
    d8_semantic_return(c,previous,id,5,hr,error);
}
static void d8_device_DrawIndexedPrimitiveUP(CPU*c) {
    LONG id=d8_api_entry(c,73,9);D8DeviceObject*o=d8_semantic_frame(c);CPU*previous;HRESULT hr;DWORD error;
    unsigned type=ARG(1),min=ARG(2),num=ARG(3),count=ARG(4),fmt=ARG(6),stride=ARG(8),ni,isz,vsz,i,index;
    uint64_t end=(uint64_t)min+num;void*indices=NULL,*vertices=NULL;DWORD evidence[9];
    if(type<4||type>6 || (fmt!=101&&fmt!=102))xrt_fatal(c,76,"DrawIndexedPrimitiveUP: unsupported topology/index format");
    ni=d8_draw_vertices(c,type,count);d8_draw_layout(c,o,count,stride);
    if(end>UINT32_MAX || (ni && (!num || end-1>o->caps.words[46])))xrt_fatal(c,76,"DrawIndexedPrimitiveUP: vertex range exceeds caps");
    isz=d8_draw_size(c,ni,fmt==101?2:4);vsz=d8_draw_size(c,ni?end:0,stride);
    /* Validate both complete ranges before allocating either staging block. */
    if(isz)d8_device_memory(c,ARG(5),isz,0);if(vsz)d8_device_memory(c,ARG(7),vsz,0);
    indices=d8_draw_copy(c,ARG(5),isz);
    for(i=0;i<ni;i++) {
        if(fmt==101){WORD v;memcpy(&v,(BYTE*)indices+2*i,2);index=v;}
        else memcpy(&index,(BYTE*)indices+4*i,4);
        if(index<min || (uint64_t)index>=end){HeapFree(GetProcessHeap(),0,indices);xrt_fatal(c,76,"DrawIndexedPrimitiveUP: index outside declared vertex range");}
    }
    vertices=d8_draw_copy(c,ARG(7),vsz);
    evidence[0]=type;evidence[1]=min;evidence[2]=num;evidence[3]=count;evidence[4]=fmt;evidence[5]=stride;
    evidence[6]=d8_draw_hash(indices,isz);evidence[7]=d8_draw_hash(vertices,vsz);evidence[8]=vsz;
    previous=d8_native_enter(c,73,evidence,sizeof evidence);
    hr=o->host->vt->DrawIndexedPrimitiveUP(o->host,type,min,num,count,indices,fmt,vertices,stride);error=GetLastError();
    if(indices)HeapFree(GetProcessHeap(),0,indices);if(vertices)HeapFree(GetProcessHeap(),0,vertices);
    d8_semantic_return(c,previous,id,9,hr,error);
}

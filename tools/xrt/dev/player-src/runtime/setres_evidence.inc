/* Raw observation only. Never assert arguments, change guest state, or admit methods. */
static volatile LONG setres_evidence_serial;
static void setres_evidence_bytes(LONG id,const char*phase,const char*area,const void*data,unsigned size) {
    const unsigned char*p=(const unsigned char*)data;unsigned offset,i,n;char hex[257];
    static const char digits[]="0123456789abcdef";
    for(offset=0;offset<size;offset+=128) {
        n=size-offset;if(n>128)n=128;
        for(i=0;i<n;i++){hex[2*i]=digits[p[offset+i]>>4];hex[2*i+1]=digits[p[offset+i]&15];}hex[2*n]=0;
        xrt_event("setres_raw","\"id\":%ld,\"phase\":\"%s\",\"area\":\"%s\",\"offset\":%u,\"size\":%u,\"hex\":\"%s\"",id,phase,area,offset,size,hex);
    }
}
static void setres_evidence(CPU*c,LONG id,const char*phase,uint32_t target,uint32_t site,uint32_t esp,uint32_t ret) {
    DWORD saved_error=GetLastError();
    xrt_event("setres_boundary","\"id\":%ld,\"phase\":\"%s\",\"target\":%u,\"site\":%u,\"esp_entry\":%u,\"return\":%u,\"esp\":%u,\"rv\":%u,\"pc\":%u,\"eax\":%u,\"this\":%u",id,phase,target,site,esp,ret,c->r[ESP],c->rv,c->pc,c->r[EAX],c->r[ECX]);
    setres_evidence_bytes(id,phase,"cpu",c,sizeof(*c));
    if((uint64_t)esp+24<=0x100000000ull && xrt_is_committed(esp,24))
        setres_evidence_bytes(id,phase,"frame",G2H(esp),24);
    else xrt_event("setres_unreadable_frame","\"id\":%ld,\"phase\":\"%s\",\"esp\":%u",id,phase,esp);
    SetLastError(saved_error);
}

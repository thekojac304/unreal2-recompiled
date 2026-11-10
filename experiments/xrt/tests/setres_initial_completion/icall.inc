void xrt_icall(CPU* c, uint32_t target, uint32_t site) {
    XrtModule*m=xrt_module_by_addr(target);
    int observed=m && !_stricmp(m->name,"D3DDrv.dll") && target-m->base==0xe890;
    LONG id=0;uint32_t esp=0,ret=0;
    if(observed) {
        DWORD saved_error=GetLastError();
        id=InterlockedIncrement(&setres_evidence_serial);esp=c->r[ESP];
        if((uint64_t)esp+4<=0x100000000ull && xrt_is_committed(esp,4))ret=rd32(esp);
        setres_evidence(c,id,"entry",target,site,esp,ret);SetLastError(saved_error);
    }
    dispatch(c,target,site,"indirect call");
    if(observed)setres_evidence(c,id,"return",target,site,esp,ret);
}

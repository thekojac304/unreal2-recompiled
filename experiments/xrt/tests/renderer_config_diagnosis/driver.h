static int drive(void) {
    static const DWORD masks[]={1,32,128};unsigned i,j,k;
    for(i=0;i<3;i++)for(j=0;j<2;j++)for(k=0;k<2;k++) {
        put(cfg_mask,masks[i]);put(cfg_enable,j);put(cfg_mips,k);put(cfg_word,j?0:masks[i]);
        call_probe();
        if(get(cfg_word,0)!=(j?masks[i]:0) || get(cfg_filter,0)!=(k?(j?2u:1u):0u))return 7;
        printf("{\"mask\":%lu,\"enabled\":%u,\"mips\":%u,\"word\":%lu,\"filter\":%lu}\n",masks[i],j,k,get(cfg_word,0),get(cfg_filter,0));
    }
    return 0;
}

static int drive(const char* mode) {
    static const DWORD values[]={0,1,2,0xffffffffu};
    static const DWORD seeds[]={0,18,0x5a17beefu};
    static const DWORD abi_values[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};
    unsigned i,j,k;BYTE before[256],after[256],saved[256];DWORD tid=GetCurrentThreadId();
    int queued=!strcmp(mode,"queue");HWND h=NULL;
    if(queued) {
        h=CreateWindowExA(0,"STATIC","owned AttachThreadInput fixture",WS_POPUP,0,0,64,64,NULL,NULL,GetModuleHandleA(NULL),NULL);
        if(!h || !GetKeyboardState(saved))return 3;
        memset(before,0,256);before[VK_F24]=0x80;
        if(!SetKeyboardState(before))return 4;
    }
    for(i=0;i<4;i++)for(j=0;j<3;j++) {
        DWORD from=tid,to=tid;
        if(!strcmp(mode,"unknown"))from=to=0xffffffffu;
        if(!strcmp(mode,"zero"))from=to=0;
        if(!strcmp(mode,"different"))to=0xffffffffu;
        if(queued && !SetKeyboardState(before))return 4;
        put(probe_from,from);put(probe_to,to);put(probe_attach,values[i]);put(probe_seed,seeds[j]);
        call_probe();
        if(get(probe_result,0)!=0 || get(probe_error,0)!=87)return 5;
        for(k=0;k<5;k++)if(get(probe_abi,k)!=abi_values[k])return 6;
        if(queued && !GetKeyboardState(after))return 7;
        printf("attach=%08lx seed=%08lx result=%lu error=%lu abi=ok keys=",values[i],seeds[j],get(probe_result,0),get(probe_error,0));
        if(queued)for(k=0;k<256;k++)printf("%02x",after[k]);
        else printf("not-queried");
        puts("");
    }
    if(queued) { if(!SetKeyboardState(saved) || !DestroyWindow(h))return 8; }
    puts("calls=12 failures=0");return 0;
}

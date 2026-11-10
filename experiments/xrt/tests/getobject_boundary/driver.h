static const IID iid_accessible={0x618736e0,0x3c3d,0x11cf,{0x81,0x0c,0x00,0xaa,0x00,0x38,0x9b,0x71}};
static void dump(void) {
    unsigned i,n=get(log_n,0);if(n>4096 || n%7)exit(9);
    for(i=0;i<n;i+=7)printf("callback %lu %lu %lu %08lx %08lx %lu %08lx\n",get(log_data,i),get(log_data,i+1),get(log_data,i+2),get(log_data,i+3),get(log_data,i+4),get(log_data,i+5),get(log_data,i+6));
}
int main(int argc,char** argv) {
    HWND h;unsigned m,repr,path;DWORD error;LRESULT r;HRESULT hr;
    if(argc<3)return 2;
    hr=CoInitialize(NULL);if(FAILED(hr))return 3;
    h=make(argv[1],argv[2]);if(!h)return 4;
    /* Destroy export takes the image's pointer-sized window slot. */
#ifdef _M_IX86
    *(DWORD*)GetProcAddress(module,"probe_window")=(DWORD)(UINT_PTR)h;
#else
#ifdef xrt_mod_ehprobe
    wr32(xrt_module_export(module,"probe_window",0),window_token(h));
#else
    /* x64 native DLL stores a DWORD handle, which Windows HWND permits. */
    *(DWORD*)GetProcAddress(module,"probe_window")=(DWORD)(UINT_PTR)h;
#endif
#endif
    if(argc>3) {
        DWORD object=strcmp(argv[3],"object")==0?0xfffffffeu:0xfffffffcu;
        WPARAM wp=strcmp(argv[3],"wparam")==0?1:0xffffffffu;
        LPARAM lp=(LPARAM)(ULONG_PTR)object;
        if(strcmp(argv[3],"nonzero")==0)put(mode,3);
        if(strcmp(argv[3],"upper")==0)lp=(LPARAM)0x12345678fffffffcll;
        SendMessageW(h,WM_GETOBJECT,wp,lp);return 10;
    }
    for(m=0;m<3;m++)for(repr=0;repr<2;repr++)for(path=0;path<3;path++) {
        LPARAM lp=repr?(LPARAM)(LONG)-4:(LPARAM)(ULONG_PTR)0xfffffffcu;
        fprintf(stderr,"representation %u %u %u wp=%016llx lp=%016llx\n",m,repr,path,(unsigned long long)(WPARAM)0xffffffffu,(unsigned long long)lp);
        put(mode,m);put(log_n,0);SetLastError(0x1234);
        if(path==0)r=SendMessageW(h,WM_GETOBJECT,(WPARAM)0xffffffffu,lp);
        else if(path==1)r=DefDlgProcW(h,WM_GETOBJECT,(WPARAM)0xffffffffu,lp);
        else r=DefWindowProcW(h,WM_GETOBJECT,(WPARAM)0xffffffffu,lp);
        error=GetLastError();
        printf("sample %u %u %u result=%lld error=%08lx\n",m,repr,path,(long long)r,error);dump();
    }
    for(m=0;m<3;m++) {
        IAccessible* a=NULL;VARIANT self,role,state;long count=-1;HWND from=NULL;
        HRESULT rh,sh,ch,wh;ULONG refs;
        put(mode,m);put(log_n,0);SetLastError(0x1234);
        hr=AccessibleObjectFromWindow(h,OBJID_CLIENT,&iid_accessible,(void**)&a);error=GetLastError();
        if(FAILED(hr)||!a)return 5;
        VariantInit(&self);V_VT(&self)=VT_I4;V_I4(&self)=CHILDID_SELF;
        VariantInit(&role);VariantInit(&state);
        rh=IAccessible_get_accRole(a,self,&role);sh=IAccessible_get_accState(a,self,&state);
        ch=IAccessible_get_accChildCount(a,&count);wh=WindowFromAccessibleObject(a,&from);
        printf("accessible %u hr=%08lx object=1 error=%08lx role=%08lx,%u,%ld state=%08lx,%u,%ld children=%08lx,%ld window=%08lx,%u\n",m,(DWORD)hr,error,(DWORD)rh,V_VT(&role),V_I4(&role),(DWORD)sh,V_VT(&state),V_I4(&state),(DWORD)ch,count,(DWORD)wh,from==h);
        VariantClear(&role);VariantClear(&state);refs=IAccessible_Release(a);
        printf("release %u window_alive=%u\n",refs==0,IsWindow(h));dump();
    }
    if(!destroy(h)||IsWindow(h))return 6;
    finish();CoUninitialize();puts("cleanup passed");return 0;
}

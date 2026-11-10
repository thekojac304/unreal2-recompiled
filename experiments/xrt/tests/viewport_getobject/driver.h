#include "abi.h"
static const IID iid_accessible={0x618736e0,0x3c3d,0x11cf,{0x81,0x0c,0x00,0xaa,0x00,0x38,0x9b,0x71}};
static HWND focus_window;static unsigned focus_calls;static LRESULT focus_result;static DWORD focus_error;
static LRESULT CALLBACK focus_ingress(int code,WPARAM wp,LPARAM lp) {
    if(code==HCBT_SETFOCUS && (HWND)wp==focus_window) {
        DWORD error=GetLastError();focus_calls++;
        focus_result=SendMessageW(focus_window,WM_GETOBJECT,0xffffffffu,(LPARAM)(LONG)-4);
        focus_error=GetLastError();SetLastError(error);
    }
    return CallNextHookEx(NULL,code,wp,lp);
}
static void dump(void) {
    unsigned i,n=get(log_n,0);if(n>4096||n%8)exit(9);
    for(i=0;i<n;i+=8)printf("callback %lu %lu %lu %08lx %08lx %lu %08lx hwnd=%lu\n",get(log_data,i),get(log_data,i+1),get(log_data,i+2),get(log_data,i+3),get(log_data,i+4),get(log_data,i+5),get(log_data,i+6),get(log_data,i+7));
}
int main(int argc,char** argv) {
    HWND h;HHOOK hook;unsigned m,repr,path;DWORD error;LRESULT r;HRESULT hr;
    if(argc<3)return 2;hr=CoInitialize(NULL);if(FAILED(hr))return 3;
    h=make(argv[1],argv[2],argc>3&&!strcmp(argv[3],"ansi"));if(!h)return 4;
    if(argc>3 && strcmp(argv[3],"messages") && strcmp(argv[3],"accessibility")) {
        DWORD object=!strcmp(argv[3],"object")?0xfffffffeu:0xfffffffcu;
        WPARAM wp=!strcmp(argv[3],"wparam")?1:0xffffffffu;LPARAM lp=(LPARAM)(ULONG_PTR)object;
        if(!strcmp(argv[3],"nonzero"))put(mode,3);
        if(!strcmp(argv[3],"upper"))lp=(LPARAM)0x12345678fffffffcll;
        if(!strcmp(argv[3],"upperwp"))wp=(WPARAM)0xffffffffffffffffull;
        if(!strcmp(argv[3],"queryclass")){wp=0;lp=(LPARAM)(LONG)-12;}
        if(!strcmp(argv[3],"uia"))lp=(LPARAM)(LONG)-25;
        if(!strcmp(argv[3],"mutated"))put(mode,5);
#ifdef xrt_mod_ehprobe
        if(!strcmp(argv[3],"unregistered"))invoke_gui_proc(h,WM_GETOBJECT,wp,lp,xrt_module_export(module,"probe_make",0));
#endif
        SendMessageW(h,!strcmp(argv[3],"message")?WM_GETTEXT:WM_GETOBJECT,wp,lp);return 10;
    }
    if(argc<4 || strcmp(argv[3],"accessibility"))for(m=0;m<3;m++)for(repr=0;repr<2;repr++)for(path=0;path<3;path++) {
        LPARAM lp=repr?(LPARAM)(LONG)-4:(LPARAM)(ULONG_PTR)0xfffffffcu;
        fprintf(stderr,"representation %u %u %u wp=%016llx lp=%016llx\n",m,repr,path,(unsigned long long)(WPARAM)0xffffffffu,(unsigned long long)lp);
        put(mode,m);put(log_n,0);SetLastError(0x1234);
        if(path==0)r=abi_call((void*)SendMessageW,h,(WPARAM)0xffffffffu,lp);
        else if(path==1)r=abi_call((void*)DefWindowProcW,h,(WPARAM)0xffffffffu,lp);
        else r=abi_call((void*)GetClassLongPtrW(h,GCLP_WNDPROC),h,(WPARAM)0xffffffffu,lp);
        error=GetLastError();printf("sample %u %u %u result=%lld error=%08lx\n",m,repr,path,(long long)r,error);dump();
    }
    if(argc<4 || strcmp(argv[3],"messages"))for(m=0;m<3;m++) {
        IAccessible* a=NULL;VARIANT self,role,state;long count=-1;HWND from=NULL;HRESULT rh,sh,ch,wh;ULONG refs;
        put(mode,m);put(log_n,0);SetLastError(0x1234);
        hr=AccessibleObjectFromWindow(h,OBJID_CLIENT,&iid_accessible,(void**)&a);error=GetLastError();if(FAILED(hr)||!a)return 5;
        fprintf(stderr,"accessible %u acquired log=%lu\n",m,get(log_n,0));
        VariantInit(&self);V_VT(&self)=VT_I4;V_I4(&self)=CHILDID_SELF;VariantInit(&role);VariantInit(&state);
        rh=IAccessible_get_accRole(a,self,&role);fprintf(stderr,"accessible %u role log=%lu\n",m,get(log_n,0));
        sh=IAccessible_get_accState(a,self,&state);fprintf(stderr,"accessible %u state log=%lu\n",m,get(log_n,0));
        ch=IAccessible_get_accChildCount(a,&count);fprintf(stderr,"accessible %u count log=%lu\n",m,get(log_n,0));
        wh=WindowFromAccessibleObject(a,&from);fprintf(stderr,"accessible %u hwnd log=%lu\n",m,get(log_n,0));
        printf("accessible %u hr=%08lx object=1 error=%08lx role=%08lx,%u,%ld state=%08lx,%u,%ld children=%08lx,%ld window=%08lx,%u\n",m,(DWORD)hr,error,(DWORD)rh,V_VT(&role),V_I4(&role),(DWORD)sh,V_VT(&state),V_I4(&state),(DWORD)ch,count,(DWORD)wh,from==h);
        VariantClear(&role);VariantClear(&state);refs=IAccessible_Release(a);printf("release %u window_alive=%u\n",refs==0,IsWindow(h));dump();
    }
    put(mode,0);put(log_n,0);focus_window=h;hook=SetWindowsHookExW(WH_CBT,focus_ingress,NULL,GetCurrentThreadId());if(!hook){fprintf(stderr,"hook failed error=%lu\n",GetLastError());return 8;}
    SetLastError(0x1234);
#ifdef xrt_mod_ehprobe
    {CPU saved=*cpu;
#endif
    SetFocus(h);error=GetLastError();
#ifdef xrt_mod_ehprobe
    if(memcmp(&saved,cpu,sizeof saved))xrt_fatal(cpu,XRT_EXIT_BADRET,"fixture: suspended focus CPU changed");
    xrt_event("fixture_suspended_focus_cpu","\"passed\":true");}
#endif
    if(!UnhookWindowsHookEx(hook)||!focus_calls){fprintf(stderr,"focus hook calls=%u error=%lu\n",focus_calls,GetLastError());return 8;}
    printf("focus identity=%u error=%08lx nested=%u result=%lld nested_error=%08lx\n",GetFocus()==h,error,focus_calls,(long long)focus_result,focus_error);dump();SetFocus(NULL);
    if(!destroy(h)||IsWindow(h))return 6;finish();CoUninitialize();puts("cleanup passed");return 0;
}

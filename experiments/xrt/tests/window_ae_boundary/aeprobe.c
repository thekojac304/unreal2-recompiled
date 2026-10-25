#define WIN32_LEAN_AND_MEAN
#include <windows.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) DWORD probe_window,probe_seed,probe_result,probe_error,probe_sp,probe_abi[5];
__declspec(dllexport) DWORD probe_wide,probe_style,probe_wp=8,probe_lp,probe_trigger,probe_log_n,probe_log[256];
static DWORD abi_call(void);
static LRESULT CALLBACK wndproc(HWND h,UINT m,WPARAM w,LPARAM l){
    LRESULT r;DWORD e;
    if(m==0xae){
        probe_window=(DWORD)h;probe_wp=(DWORD)w;probe_lp=(DWORD)l;
        probe_log[probe_log_n++]=m;probe_log[probe_log_n++]=(DWORD)w;probe_log[probe_log_n++]=(DWORD)l;probe_log[probe_log_n++]=GetLastError();
        r=abi_call();e=GetLastError();probe_error=e;
        probe_log[probe_log_n++]=m+0x10000;probe_log[probe_log_n++]=(DWORD)r;probe_log[probe_log_n++]=0;probe_log[probe_log_n++]=e;
        return r;
    }
    return probe_wide?DefWindowProcW(h,m,w,l):DefWindowProcA(h,m,w,l);
}
__declspec(dllexport) DWORD probe_make(void){
    WNDCLASSEXA a;WNDCLASSEXW w;unsigned i;volatile BYTE*p=(volatile BYTE*)&a;volatile BYTE*q=(volatile BYTE*)&w;
    for(i=0;i<sizeof a;i++)p[i]=0;for(i=0;i<sizeof w;i++)q[i]=0;
    if(probe_wide){w.cbSize=sizeof w;w.lpfnWndProc=wndproc;w.hInstance=(HINSTANCE)&__ImageBase;w.lpszClassName=L"XrtAeWide";RegisterClassExW(&w);
        return (DWORD)CreateWindowExW(0,L"XrtAeWide",L"window notification",probe_style,0,0,64,64,NULL,NULL,(HINSTANCE)&__ImageBase,NULL);}
    a.cbSize=sizeof a;a.lpfnWndProc=wndproc;a.hInstance=(HINSTANCE)&__ImageBase;a.lpszClassName="XrtAeNarrow";RegisterClassExA(&a);
    return (DWORD)CreateWindowExA(0,"XrtAeNarrow","window notification",probe_style,0,0,64,64,NULL,NULL,(HINSTANCE)&__ImageBase,NULL);
}
__declspec(dllexport) DWORD probe_destroy(void){return DestroyWindow((HWND)probe_window);}
__declspec(naked) static DWORD abi_call(void){__asm{
    push ebp
    push ebx
    push esi
    push edi
    mov probe_sp,esp
    mov ebp,0x12345678
    mov ebx,0x23456789
    mov esi,0x3456789a
    mov edi,0x456789ab
    push probe_lp
    push probe_wp
    push 0xae
    push probe_window
    cmp probe_wide,0
    je narrow
    call DefWindowProcW
    jmp done
narrow:
    call DefWindowProcA
done:
    mov probe_result,eax
    mov eax,esp
    sub eax,probe_sp
    mov probe_abi,eax
    mov probe_abi+4,ebp
    mov probe_abi+8,ebx
    mov probe_abi+12,esi
    mov probe_abi+16,edi
    pop edi
    pop esi
    pop ebx
    pop ebp
    mov eax,probe_result
    ret
}}
__declspec(dllexport) DWORD probe_run(void){return 0;}

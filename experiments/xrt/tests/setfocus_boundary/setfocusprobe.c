/* One owned x86 image: Windows executes it and xlift translates the same bytes. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) DWORD probe_window,probe_seed,probe_result,probe_error,probe_sp,probe_abi[5];
__declspec(dllexport) DWORD probe_mode,probe_trigger,probe_target,probe_log_n,probe_log[2048];
__declspec(dllexport) DWORD probe_parent;
static void record(UINT m,HWND h,HWND other,HWND focus,HWND result,DWORD error) {
    DWORD i=probe_log_n;
    if(i+6>2048)return;
    probe_log[i++]=m;probe_log[i++]=(DWORD)h;probe_log[i++]=(DWORD)other;
    probe_log[i++]=(DWORD)focus;probe_log[i++]=(DWORD)result;probe_log[i++]=error;
    probe_log_n=i;
}
static LRESULT CALLBACK wndproc(HWND h,UINT m,WPARAM w,LPARAM l) {
    if(m==WM_SETFOCUS || m==WM_KILLFOCUS) {
        DWORD error=GetLastError();HWND focus=GetFocus();
        record(m,h,(HWND)w,focus,NULL,error);
        if(probe_trigger==m) {
            HWND r;probe_trigger=0;r=SetFocus((HWND)probe_target);
            error=GetLastError();focus=GetFocus();record(m+0x10000,h,(HWND)w,focus,r,error);
        }
    }
    if((probe_mode==1 && m==WM_NCCREATE)||(probe_mode==2 && m==WM_CREATE)) {
        HWND r;DWORD error;probe_mode=0;r=SetFocus(h);error=GetLastError();
        record(m+0x20000,h,NULL,GetFocus(),r,error);
    }
    return DefWindowProcA(h,m,w,l);
}
__declspec(dllexport) int probe_init(void) {
    WNDCLASSEXA w;volatile BYTE* p=(volatile BYTE*)&w;unsigned i;
    for(i=0;i<sizeof w;i++)p[i]=0;
    w.cbSize=sizeof w;w.lpfnWndProc=wndproc;w.hInstance=(HINSTANCE)&__ImageBase;
    w.lpszClassName="XrtSetFocusBoundary";return RegisterClassExA(&w)!=0;
}
__declspec(dllexport) HWND probe_make(void) {
    return CreateWindowExA(0,"XrtSetFocusBoundary","focus boundary",probe_parent?WS_CHILD:WS_POPUP,0,0,16,16,(HWND)probe_parent,NULL,(HINSTANCE)&__ImageBase,NULL);
}
__declspec(naked) static DWORD abi_call(void) {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        mov probe_sp,esp
        mov ebp,0x12345678
        mov ebx,0x23456789
        mov esi,0x3456789a
        mov edi,0x456789ab
        push probe_window
        call SetFocus
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
    }
}
__declspec(dllexport) DWORD probe_run(void) {
    SetLastError(probe_seed);abi_call();probe_error=GetLastError();return probe_result;
}
__declspec(dllexport) HWND probe_read(void) {return GetFocus();}
__declspec(dllexport) BOOL probe_destroy(void) {return DestroyWindow((HWND)probe_window);}

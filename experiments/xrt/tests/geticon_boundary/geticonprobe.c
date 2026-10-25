/* The same owned x86 image runs under native USER32 and the translator. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) DWORD probe_window,probe_seed,probe_result,probe_error,probe_sp,probe_abi[5];
__declspec(dllexport) DWORD probe_selector,probe_dpi,probe_mode,probe_nested,probe_class;
__declspec(dllexport) DWORD probe_icons[3],probe_log_n,probe_log[4096];
static DWORD depth;
static void record(DWORD stage,DWORD w,DWORD l,DWORD r,DWORD e) {
    DWORD i=probe_log_n;
    if(i+6>4096){probe_log_n=0xffffffff;return;}
    probe_log[i++]=stage;probe_log[i++]=depth;probe_log[i++]=w;
    probe_log[i++]=l;probe_log[i++]=r;probe_log[i++]=e;probe_log_n=i;
}
static LRESULT CALLBACK wndproc(HWND h,UINT m,WPARAM w,LPARAM l) {
    LRESULT r;
    if(m!=WM_GETICON)return DefWindowProcW(h,m,w,l);
    depth++;record(0,w,(DWORD)l,0,GetLastError());
    if(probe_nested && depth==1) {
        r=SendMessageW(h,WM_GETICON,(w+1)%3,0);
        record(1,(w+1)%3,0,(DWORD)r,GetLastError());
    }
    if(probe_mode==0)r=DefWindowProcW(h,m,w,l);
    else if(probe_mode==1)r=0;
    else r=probe_icons[probe_mode-2];
    record(2,w,(DWORD)l,(DWORD)r,GetLastError());depth--;return r;
}
__declspec(dllexport) int probe_init(void) {
    WNDCLASSEXW c;volatile BYTE* p=(volatile BYTE*)&c;unsigned i;
    for(i=0;i<sizeof c;i++)p[i]=0;
    probe_icons[0]=(DWORD)LoadIconW(NULL,MAKEINTRESOURCEW(32512));
    probe_icons[1]=(DWORD)LoadIconW(NULL,MAKEINTRESOURCEW(32513));
    probe_icons[2]=(DWORD)LoadCursorW(NULL,MAKEINTRESOURCEW(32512));
    c.cbSize=sizeof c;c.lpfnWndProc=wndproc;c.hInstance=(HINSTANCE)&__ImageBase;
    c.lpszClassName=L"XrtGetIconBoundary";
    if(probe_class&1)c.hIcon=(HICON)probe_icons[0];
    if(probe_class&2)c.hIconSm=(HICON)probe_icons[1];
    return RegisterClassExW(&c)!=0;
}
__declspec(dllexport) HWND probe_make(void) {
    return CreateWindowExW(0,L"XrtGetIconBoundary",L"icon boundary",WS_OVERLAPPEDWINDOW,0,0,64,64,NULL,NULL,(HINSTANCE)&__ImageBase,NULL);
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
        push probe_dpi
        push probe_selector
        push WM_GETICON
        push probe_window
        call SendMessageW
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
__declspec(dllexport) HWND probe_focus(void) {return SetFocus((HWND)probe_window);}
__declspec(dllexport) BOOL probe_destroy(void) {return DestroyWindow((HWND)probe_window);}

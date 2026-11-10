/* The same project-owned registered WNDPROC runs as native PE32 and translated. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) DWORD probe_window,probe_mode,probe_log_n,probe_log[4096];
__declspec(dllexport) DWORD probe_abi_count,probe_abi_fail,probe_ansi;
static DWORD depth;
static void record(DWORD stage,HWND h,UINT msg,WPARAM wp,LPARAM lp,DWORD value) {
    DWORD i=probe_log_n;
    if(i+8>4096){probe_log_n=0xffffffff;return;}
    probe_log[i++]=stage;probe_log[i++]=depth;probe_log[i++]=msg;
    probe_log[i++]=(DWORD)wp;probe_log[i++]=(DWORD)lp;probe_log[i++]=value;
    probe_log[i++]=GetLastError();probe_log[i++]=(DWORD)(UINT_PTR)h==probe_window;probe_log_n=i;
}
static LRESULT CALLBACK window_impl(HWND h,UINT msg,WPARAM wp,LPARAM lp) {
    LRESULT result;DWORD error=GetLastError();
    if(msg==WM_GETOBJECT || (depth && msg==WM_GETTEXTLENGTH)) {
        depth++;record(0,h,msg,wp,lp,0);
        if(msg==WM_GETOBJECT && probe_mode==1) {
            result=SendMessageW(h,WM_GETTEXTLENGTH,0,0);record(1,h,WM_GETTEXTLENGTH,0,0,(DWORD)result);
        }
        if(probe_mode==2)SetLastError(0x5678);else SetLastError(error);
        result=probe_mode==3?1:DefWindowProcW(h,msg,wp+(probe_mode==5),lp);
        record(2,h,msg,wp,lp,(DWORD)result);depth--;return result;
    }
    return probe_ansi?DefWindowProcA(h,msg,wp,lp):DefWindowProcW(h,msg,wp,lp);
}
#ifdef _M_IX86
__declspec(naked) static LRESULT CALLBACK window_proc(HWND h,UINT msg,WPARAM wp,LPARAM lp) {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        mov ebp,0x12345678
        mov ebx,0x23456789
        mov esi,0x3456789a
        mov edi,0x456789ab
        push [esp+32]
        push [esp+32]
        push [esp+32]
        push [esp+32]
        call window_impl
        inc probe_abi_count
        cmp ebp,0x12345678
        jne bad
        cmp ebx,0x23456789
        jne bad
        cmp esi,0x3456789a
        jne bad
        cmp edi,0x456789ab
        je done
    bad:
        inc probe_abi_fail
    done:
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret 16
    }
}
#else
#define window_proc window_impl
#endif
__declspec(dllexport) UINT_PTR probe_make(void) {
    WNDCLASSEXW w={0};HWND h;
    w.cbSize=sizeof w;w.lpfnWndProc=window_proc;w.hInstance=(HMODULE)&__ImageBase;
    w.lpszClassName=L"XrtViewportGetObject";
    if(probe_ansi) {
        w.lpszClassName=(LPCWSTR)"XrtViewportGetObjectA";
        if(!RegisterClassExA((WNDCLASSEXA*)&w))return 0;
        h=CreateWindowExA(0,"XrtViewportGetObjectA","Viewport",WS_OVERLAPPEDWINDOW,0,0,320,200,NULL,NULL,w.hInstance,NULL);
    } else {
        if(!RegisterClassExW(&w))return 0;
        h=CreateWindowExW(0,w.lpszClassName,L"Viewport",WS_OVERLAPPEDWINDOW,0,0,320,200,NULL,NULL,w.hInstance,NULL);
    }
    probe_window=(DWORD)(UINT_PTR)h;return (UINT_PTR)h;
}
__declspec(dllexport) BOOL probe_destroy(void) {
    BOOL ok=DestroyWindow((HWND)(UINT_PTR)probe_window);
    return ok && (probe_ansi?UnregisterClassA("XrtViewportGetObjectA",(HMODULE)&__ImageBase):UnregisterClassW(L"XrtViewportGetObject",(HMODULE)&__ImageBase));
}

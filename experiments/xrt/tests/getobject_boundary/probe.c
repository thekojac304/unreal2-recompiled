/* Project-owned dialog. Exactly this x86 DLL is also lifted. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) DWORD probe_window, probe_mode, probe_log_n, probe_log[4096];
__declspec(dllexport) DWORD probe_abi_fail,probe_abi_count;
static DWORD depth;
static void record(DWORD stage, UINT msg, WPARAM wp, LPARAM lp, DWORD value) {
    DWORD i=probe_log_n;
    if(i+7>4096){probe_log_n=0xffffffff;return;}
    probe_log[i++]=stage;probe_log[i++]=depth;probe_log[i++]=msg;
    probe_log[i++]=(DWORD)wp;probe_log[i++]=(DWORD)lp;
    probe_log[i++]=value;probe_log[i++]=GetLastError();probe_log_n=i;
}
static INT_PTR CALLBACK dialog_impl(HWND h,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_GETOBJECT || (depth && msg==WM_GETTEXTLENGTH)) {
        DWORD error=GetLastError();depth++;record(0,msg,wp,lp,0);
        if(msg==WM_GETOBJECT && probe_mode==1) {
            LRESULT r=SendMessageW(h,WM_GETTEXTLENGTH,0,0);
            record(1,WM_GETTEXTLENGTH,0,0,(DWORD)r);
        }
        if(probe_mode==2)SetLastError(0x5678);
        else SetLastError(error);
        record(2,msg,wp,lp,0);depth--;
    }
    return probe_mode==3?TRUE:FALSE;
}
#ifdef _M_IX86
__declspec(naked) static INT_PTR CALLBACK dialog(HWND h,UINT msg,WPARAM wp,LPARAM lp) {
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
        call dialog_impl
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
#define dialog dialog_impl
#endif
__declspec(dllexport) UINT_PTR probe_make(void) {
    return (UINT_PTR)CreateDialogParamW((HMODULE)&__ImageBase,MAKEINTRESOURCEW(119),NULL,dialog,0);
}
__declspec(dllexport) BOOL probe_destroy(void) {return DestroyWindow((HWND)(UINT_PTR)probe_window);}

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
__declspec(dllexport) DWORD probe_window,probe_output,probe_seed,probe_result,probe_error,probe_sp,probe_abi[5],probe_pid,probe_tid;
__declspec(dllexport) HWND probe_make(void) {return CreateWindowExW(0,L"STATIC",L"window IDs",WS_POPUP,0,0,16,16,NULL,NULL,NULL,NULL);}
__declspec(dllexport) BOOL probe_destroy(void) {return DestroyWindow((HWND)probe_window);}
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
        push probe_output
        push probe_window
        call GetWindowThreadProcessId
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
    SetLastError(probe_seed);abi_call();probe_error=GetLastError();probe_pid=GetCurrentProcessId();probe_tid=GetCurrentThreadId();return probe_result;
}

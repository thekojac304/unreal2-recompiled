#define WIN32_LEAN_AND_MEAN
#include <windows.h>
__declspec(dllexport) DWORD probe_cursor,probe_seed,probe_result,probe_error,probe_sp,probe_abi[5],probe_cursors[4],probe_icon;
__declspec(dllexport) int probe_init(void) {
    probe_cursors[0]=(DWORD)LoadCursorW(NULL,MAKEINTRESOURCEW(32512));
    probe_cursors[1]=(DWORD)LoadCursorW(NULL,MAKEINTRESOURCEW(32513));
    probe_cursors[2]=(DWORD)LoadCursorW(NULL,MAKEINTRESOURCEW(32514));
    probe_cursors[3]=(DWORD)LoadCursorW(NULL,MAKEINTRESOURCEW(32515));
    probe_icon=(DWORD)LoadIconW(NULL,MAKEINTRESOURCEW(32512));return probe_cursors[3]!=0;
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
        push probe_cursor
        call SetCursor
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

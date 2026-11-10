/* Owned non-game x86 import/ABI fixture, executed natively and lifted. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
__declspec(dllexport) DWORD probe_from,probe_to,probe_attach,probe_seed;
__declspec(dllexport) DWORD probe_result,probe_error,probe_sp,probe_abi[5];
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
        push probe_attach
        push probe_to
        push probe_from
        call AttachThreadInput
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

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
__declspec(dllexport) DWORD cfg_word,cfg_mask,cfg_enable,cfg_mips,cfg_filter;
static DWORD property[28],renderer[0x4700/4];
#include "original_fragments.inc"
__declspec(dllexport) DWORD probe_run(void) {
    property[0x6c/4]=cfg_mask;
    __asm {
        lea eax,property
        push eax
        lea eax,cfg_word
        push eax
        cmp cfg_enable,0
        je disable
        call true_fragment
        jmp done
    disable:
        call false_fragment
    done:
    }
    renderer[0x40d0/4]=cfg_word;renderer[0x40d4/4]=cfg_mips;
    __asm {lea eax,renderer
        push eax
        call mip_fragment
        mov cfg_filter,eax
    }
    return cfg_filter;
}

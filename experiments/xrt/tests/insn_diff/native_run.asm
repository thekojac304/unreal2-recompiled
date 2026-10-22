; native_run.asm - executes one test snippet on the real x86 CPU (32-bit, MASM).
; State in: g_in_r (eax ecx edx ebx esp ebp esi edi), g_in_flags, g_fcw, g_nst/g_st (x87 stack, g_st[0] = ST(0)).
; The snippet is entered with a jump and ends with "jmp dword ptr [g_back]", which returns here with
; every register, EFLAGS and the x87 state exactly as the snippet left them.
; State out: g_out_r, g_out_flags, g_fsave (FNSAVE image: FCW, FSW, tag word, ST(0)..ST(7) as 80-bit).
; A hardware exception inside the snippet (#DE) is resumed by the harness's vectored handler at
; run_native_fault, which restores the host stack and returns.
        .686
        .model flat, C
        ASSUME FS:NOTHING

        .data
        PUBLIC g_in_r, g_in_flags, g_out_r, g_out_flags, g_fcw, g_nst, g_st, g_code, g_back, g_fsave, g_host_esp
        PUBLIC g_teb_after
g_in_r      DWORD 8 DUP (0)
g_in_flags  DWORD 2
g_out_r     DWORD 8 DUP (0)
g_out_flags DWORD 0
g_fcw       WORD 027Fh
            WORD 0
g_nst       DWORD 0
g_st        QWORD 8 DUP (0)
g_code      DWORD 0
g_back      DWORD 0
g_host_esp  DWORD 0
g_fsave     BYTE 108 DUP (0)
g_fs0       DWORD 0                     ; TEB ExceptionList and ArbitraryUserPointer, saved around the snippet
g_fs14      DWORD 0
g_teb_after BYTE 52 DUP (0)             ; TEB[0, 34h) as the snippet left it

        .code
        PUBLIC run_native, run_native_back, run_native_fault
run_native PROC
        push    ebp
        push    ebx
        push    esi
        push    edi
        mov     g_host_esp, esp
        mov     eax, fs:[0]
        mov     g_fs0, eax
        mov     eax, fs:[14h]
        mov     g_fs14, eax
        fninit
        fldcw   g_fcw
        mov     ecx, g_nst
        test    ecx, ecx
        jz      noload
ldloop: fld     QWORD PTR g_st[ecx*8-8]
        dec     ecx
        jnz     ldloop
noload:
        push    g_in_flags
        popfd
        mov     eax, g_in_r[0]
        mov     ecx, g_in_r[4]
        mov     edx, g_in_r[8]
        mov     ebx, g_in_r[12]
        mov     ebp, g_in_r[20]
        mov     esi, g_in_r[24]
        mov     edi, g_in_r[28]
        mov     esp, g_in_r[16]
        jmp     DWORD PTR [g_code]
run_native_back::
        mov     g_out_r[0], eax
        mov     g_out_r[4], ecx
        mov     g_out_r[8], edx
        mov     g_out_r[12], ebx
        mov     g_out_r[16], esp
        mov     g_out_r[20], ebp
        mov     g_out_r[24], esi
        mov     g_out_r[28], edi
        mov     esp, g_host_esp
        pushfd
        pop     g_out_flags
        cld
        xor     ecx, ecx
tebcopy:
        mov     eax, fs:[ecx]
        mov     DWORD PTR g_teb_after[ecx], eax
        add     ecx, 4
        cmp     ecx, 34h
        jb      tebcopy
        mov     eax, g_fs0
        mov     fs:[0], eax
        mov     eax, g_fs14
        mov     fs:[14h], eax
        fnsave  g_fsave
        fninit
        pop     edi
        pop     esi
        pop     ebx
        pop     ebp
        ret
run_native_fault::
        mov     esp, g_host_esp
        cld
        mov     eax, g_fs0
        mov     fs:[0], eax
        mov     eax, g_fs14
        mov     fs:[14h], eax
        fninit
        pop     edi
        pop     esi
        pop     ebx
        pop     ebp
        ret
run_native ENDP
        END

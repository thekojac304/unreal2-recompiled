; x64 probe boundary. Save before any C logging. No guest memory writes.
; fxsave/fxrstor include x87 values/tags/control/status and all SSE registers.
; AVX upper halves are not represented: candidate is compiled without AVX.
option casemap:none
EXTERN xm_emit:PROC
.code
xm_probe PROC FRAME
    pushfq
    .allocstack 8
    sub rsp, 704
    .allocstack 704
    .endprolog
    ; 32 bytes outgoing shadow, followed by XmHost, aligned fx state at +176.
    mov [rsp+32], rax
    mov [rsp+40], rcx
    mov [rsp+48], rdx
    mov [rsp+56], rbx
    lea rax, [rsp+712]
    mov [rsp+64], rax
    mov [rsp+72], rbp
    mov [rsp+80], rsi
    mov [rsp+88], rdi
    mov [rsp+96], r8
    mov [rsp+104], r9
    mov [rsp+112], r10
    mov [rsp+120], r11
    mov [rsp+128], r12
    mov [rsp+136], r13
    mov [rsp+144], r14
    mov [rsp+152], r15
    mov rax, [rsp+712]
    mov [rsp+160], rax
    mov rax, [rsp+704]
    mov [rsp+168], rax
    ; FXSAVE leaves reserved bytes untouched. Do not serialize old stack bytes.
    xor eax, eax
    lea rdi, [rsp+176]
    mov ecx, 64
    cld
    rep stosq
    fxsave64 [rsp+176]
    mov rcx, [rsp+40]
    mov rdx, [rsp+48]
    lea r8, [rsp+32]
    call xm_emit
    fxrstor64 [rsp+176]
    mov rax, [rsp+32]
    mov rcx, [rsp+40]
    mov rdx, [rsp+48]
    mov rbx, [rsp+56]
    mov rbp, [rsp+72]
    mov rsi, [rsp+80]
    mov rdi, [rsp+88]
    mov r8, [rsp+96]
    mov r9, [rsp+104]
    mov r10, [rsp+112]
    mov r11, [rsp+120]
    mov r12, [rsp+128]
    mov r13, [rsp+136]
    mov r14, [rsp+144]
    mov r15, [rsp+152]
    lea rsp, [rsp+704]
    popfq
    ret
xm_probe ENDP
END

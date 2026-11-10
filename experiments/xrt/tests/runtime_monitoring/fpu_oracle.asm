; Owned qualification only. Save original state, exercise non-default x87 stack,
; control/status and MXCSR, compare all 512 bytes around the actual trace probe.
option casemap:none
EXTERN xm_probe:PROC
.const
cw_test WORD 077fh
mx_test DWORD 03f80h
.code
xm_fpu_oracle PROC FRAME
    push rsi
    .pushreg rsi
    push rdi
    .pushreg rdi
    sub rsp,1640
    .allocstack 1640
    .endprolog
    mov [rsp+1568],rcx
    mov [rsp+1576],rdx
    lea rdi,[rsp+32]
    xor eax,eax
    mov ecx,192
    rep stosq
    fxsave64 [rsp+32]
    fninit
    fld1
    fldpi
    fldcw cw_test
    ldmxcsr mx_test
    pcmpeqb xmm0,xmm0
    pxor xmm7,xmm7
    fxsave64 [rsp+544]
    mov rcx,[rsp+1568]
    mov rdx,[rsp+1576]
    std
    call xm_probe
    pushfq
    pop r10
    cld
    fxsave64 [rsp+1056]
    lea rsi,[rsp+544]
    lea rdi,[rsp+1056]
    mov ecx,64
    repe cmpsq
    sete al
    movzx eax,al
    test r10,400h
    jnz direction_preserved
    xor eax,eax
direction_preserved:
    fxrstor64 [rsp+32]
    add rsp,1640
    pop rdi
    pop rsi
    ret
xm_fpu_oracle ENDP
END

option casemap:none
.const
align 16
seed128 DWORD 12345678h,23456789h,3456789ah,456789abh
cwseed WORD 077fh
mxseed DWORD 03f80h
.code
window_abi PROC
    push rbp
    push rbx
    push rsi
    push rdi
    push r12
    push r13
    push r14
    push r15
    sub rsp,792
    mov [rsp+64],rcx
    mov [rsp+72],rdx
    mov [rsp+80],rsp
    fxsave [rsp+272]
    ofs = 112
    IRP reg,<xmm6,xmm7,xmm8,xmm9,xmm10,xmm11,xmm12,xmm13,xmm14,xmm15>
        movdqa [rsp+ofs],reg
        movdqa reg,XMMWORD PTR seed128
        ofs = ofs+16
    ENDM
    fninit
    fld1
    fldpi
    fldcw cwseed
    ldmxcsr mxseed
    mov r10,[rsp+72]
    fxsave [r10+240]
    mov rbp,1111111112345678h
    mov rbx,2222222223456789h
    mov rsi,333333333456789ah
    mov rdi,44444444456789abh
    mov r12,5555555556789abch
    mov r13,666666666789abcdh
    mov r14,77777777789abcdeh
    mov r15,8888888889abcdefh
    mov r10,[rsp+64]
    mov rcx,[r10+8]
    mov edx,[r10+16]
    mov r8,[r10+24]
    mov r9,[r10+32]
    call QWORD PTR [r10]
    mov r10,[rsp+72]
    fxsave [r10+752]
    mov [r10],eax
    mov r11,rsp
    sub r11,[rsp+80]
    mov [r10+4],r11d
    ofs = 8
    IRP reg,<rbp,rbx,rsi,rdi,r12,r13,r14,r15>
        mov [r10+ofs],reg
        ofs = ofs+8
    ENDM
    ofs = 72
    IRP reg,<xmm6,xmm7,xmm8,xmm9,xmm10,xmm11,xmm12,xmm13,xmm14,xmm15>
        movdqu [r10+ofs],reg
        ofs = ofs+16
    ENDM
    fxrstor [rsp+272]
    add rsp,792
    pop r15
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
window_abi ENDP
END

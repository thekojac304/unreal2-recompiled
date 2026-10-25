; Native Windows x64 nonvolatile GPR/XMM and stack check around the real method.
option casemap:none
.const
align 16
seed128 DWORD 12345678h,23456789h,3456789ah,456789abh
.code
display_abi64 PROC
    push rbp
    push rbx
    push rsi
    push rdi
    push r12
    push r13
    push r14
    push r15
    sub rsp,248
    mov [rsp+32],rsp
    mov rax,[rsp+352]
    mov [rsp+40],rax
    mov [rsp+48],rcx
    mov [rsp+56],rdx
    mov [rsp+64],r8
    mov [rsp+72],r9
    ofs = 80
    IRP reg,<xmm6,xmm7,xmm8,xmm9,xmm10,xmm11,xmm12,xmm13,xmm14,xmm15>
        movdqa [rsp+ofs],reg
        movdqa reg,XMMWORD PTR seed128
        ofs = ofs+16
    ENDM
    mov rbp,1111111112345678h
    mov rbx,2222222223456789h
    mov rsi,333333333456789ah
    mov rdi,44444444456789abh
    mov r12,5555555556789abch
    mov r13,666666666789abcdh
    mov r14,77777777789abcdeh
    mov r15,8888888889abcdefh
    mov rcx,[rsp+56]
    mov rdx,[rsp+64]
    mov r8,[rsp+72]
    call QWORD PTR [rsp+48]
    mov r10,[rsp+40]
    mov [r10],eax
    mov r11,rsp
    sub r11,[rsp+32]
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
    ofs = 80
    IRP reg,<xmm6,xmm7,xmm8,xmm9,xmm10,xmm11,xmm12,xmm13,xmm14,xmm15>
        movdqa reg,[rsp+ofs]
        ofs = ofs+16
    ENDM
    add rsp,248
    pop r15
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
display_abi64 ENDP
END

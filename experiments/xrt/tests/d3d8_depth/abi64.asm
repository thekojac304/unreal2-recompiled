; Windows x64: this plus five UINTs; preserve all nonvolatile GPRs/XMMs.
option casemap:none
.const
align 16
seed128 DWORD 12345678h,23456789h,3456789ah,456789abh
.code
depth_abi64 PROC
    push rbp
    push rbx
    push rsi
    push rdi
    push r12
    push r13
    push r14
    push r15
    sub rsp,280
    mov [rsp+48],rsp
    mov [rsp+64],rcx
    mov [rsp+72],rdx
    mov [rsp+80],r8
    mov [rsp+88],r9
    mov rax,[rsp+384]
    mov [rsp+96],rax
    mov rax,[rsp+392]
    mov [rsp+32],rax
    mov rax,[rsp+400]
    mov [rsp+40],rax
    mov rax,[rsp+408]
    mov [rsp+56],rax
    ofs = 112
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
    mov rcx,[rsp+72]
    mov rdx,[rsp+80]
    mov r8,[rsp+88]
    mov r9,[rsp+96]
    call QWORD PTR [rsp+64]
    mov r10,[rsp+56]
    mov [r10],eax
    mov r11,rsp
    sub r11,[rsp+48]
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
    ofs = 112
    IRP reg,<xmm6,xmm7,xmm8,xmm9,xmm10,xmm11,xmm12,xmm13,xmm14,xmm15>
        movdqa reg,[rsp+ofs]
        ofs = ofs+16
    ENDM
    add rsp,280
    pop r15
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbx
    pop rbp
    ret
depth_abi64 ENDP
END

.code
PUBLIC paired_entry
paired_entry PROC
    ret
paired_entry ENDP
PUBLIC paired_return
paired_return PROC
    mov DWORD PTR [rdi+44h], ebx
    ret
paired_return ENDP
PUBLIC paired_invoke
paired_invoke PROC FRAME
    push rbx
    .pushreg rbx
    push rdi
    .pushreg rdi
    sub rsp,28h
    .allocstack 28h
    .endprolog
    mov rdi,rcx
    mov ebx,11104bf8h
    call paired_return
    add rsp,28h
    pop rdi
    pop rbx
    ret
paired_invoke ENDP
END

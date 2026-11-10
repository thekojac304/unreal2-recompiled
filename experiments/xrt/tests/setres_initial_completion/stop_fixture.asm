; Project-owned exact instruction semantics; no translated game body is called.
.code
PUBLIC owned_stop
owned_stop PROC
    mov DWORD PTR [rdi+44h], ebx
    ret
owned_stop ENDP
PUBLIC owned_invoke
owned_invoke PROC FRAME
    push rbx
    .pushreg rbx
    push rdi
    .pushreg rdi
    sub rsp,28h
    .allocstack 28h
    .endprolog
    mov rdi,rcx
    mov ebx,edx
    call owned_stop
    add rsp,28h
    pop rdi
    pop rbx
    ret
owned_invoke ENDP
END

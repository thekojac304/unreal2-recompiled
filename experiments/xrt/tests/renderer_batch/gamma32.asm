.686p
.model flat,c
.code
; Run an isolated, relocated copy of the original arithmetic loop. No DLL game entry.
gamma_native PROC
    push ebp
    push ebx
    push esi
    push edi
    mov eax,[esp+20]
    mov ebp,[esp+24]
    call eax
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
gamma_native ENDP
END

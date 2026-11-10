.686p
.model flat,c
EXTERN abi_data:DWORD
.data
cwseed WORD 027fh
one REAL8 1.0
onehalf REAL8 1.5
.code
bridge_abi PROC
    push ebp
    push ebx
    push esi
    push edi
    mov eax,[esp+20]
    mov ecx,[esp+24]
    mov edx,[esp+28]
    mov ebx,[esp+32]
    mov abi_data,esp
    fnclex
    fldcw cwseed
    fld QWORD PTR one
    fld QWORD PTR onehalf
    fnstcw WORD PTR abi_data+4
    fnstsw WORD PTR abi_data+6
    push ebx
    push edx
    push 042h
    push ecx
    push 1
    push 0
    push eax
    mov ebp,12345678h
    mov ebx,23456789h
    mov esi,3456789ah
    mov edi,456789abh
    mov edx,[eax]
    call DWORD PTR [edx+60]
    mov abi_data+8,eax
    mov eax,esp
    sub eax,abi_data
    mov abi_data+12,eax
    mov abi_data+16,ebp
    mov abi_data+20,ebx
    mov abi_data+24,esi
    mov abi_data+28,edi
    fnstcw WORD PTR abi_data+32
    fnstsw WORD PTR abi_data+34
    fstp QWORD PTR abi_data+40
    fstp QWORD PTR abi_data+48
    mov eax,abi_data+8
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
bridge_abi ENDP
END

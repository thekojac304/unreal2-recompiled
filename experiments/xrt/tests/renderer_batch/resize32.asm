.686p
.model flat,c
EXTERN resize_result:DWORD
EXTERN resize_bad:DWORD
.code
; Test-only stdcall entry -> original thiscall argument convention.
resize_adapter PROC
    mov edx,esp
    mov ecx,[edx+4]
    push DWORD PTR [edx+16]
    push DWORD PTR [edx+12]
    push DWORD PTR [edx+8]
    call resize_thiscall
    ret 16
resize_adapter ENDP
resize_thiscall PROC
    cmp ecx,8000h
    jne bad
    mov eax,[esp+4]
    cmp eax,10h
    je flags_ok
    cmp eax,11h
    jne bad
flags_ok:
    cmp DWORD PTR [esp+8],1540
    jne bad
    cmp DWORD PTR [esp+12],945
    jne bad
    mov eax,resize_result
    ret 12
bad:
    mov resize_bad,1
    mov eax,resize_result
    ret 12
resize_thiscall ENDP
END

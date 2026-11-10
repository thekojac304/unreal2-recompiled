.386
.model flat, C
EXTERN fixture_frame:DWORD, fixture_this:DWORD, entry_esp:DWORD
EXTERN before_esp:DWORD, after_esp:DWORD, expected_return:DWORD
EXTERN viewport:BYTE, renderer:BYTE, request_flags:DWORD
.code
owned_setres PROC
    mov fixture_this,ecx
    mov entry_esp,esp
    mov eax,[esp]
    mov fixture_frame,eax
    mov eax,[esp+4]
    mov fixture_frame[4],eax
    mov eax,[esp+8]
    mov fixture_frame[8],eax
    mov eax,[esp+12]
    mov fixture_frame[12],eax
    mov eax,[esp+16]
    mov fixture_frame[16],eax
    mov eax,[esp+20]
    mov fixture_frame[20],eax
    mov eax,1
    ret 20
owned_setres ENDP
PUBLIC frame_invoke
frame_invoke PROC
    push ebp
    mov ebp,esp
    push ebx
    push esi
    push edi
    mov before_esp,esp
    lea ecx,renderer
    lea eax,viewport
    cmp DWORD PTR [ebp+8],1
    je lock_call
    mov edx,DWORD PTR renderer[70h]
    or edx,request_flags
    push 20h
    push edx
    push DWORD PTR [eax+78h]
    push DWORD PTR [eax+74h]
    push eax
    mov expected_return,OFFSET initial_return
    call owned_setres
initial_return:
    jmp done
lock_call:
    push 20h
    push DWORD PTR renderer[4674h]
    push DWORD PTR [eax+78h]
    push DWORD PTR [eax+74h]
    push eax
    mov expected_return,OFFSET lock_return
    call owned_setres
lock_return:
done:
    mov after_esp,esp
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
frame_invoke ENDP
END

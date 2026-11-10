.686p
.xmm
.model flat,c
.const
cwseed WORD 077fh
mxseed DWORD 03f80h
.code
device_abi PROC
    push ebp
    push ebx
    push esi
    push edi
    mov eax,[esp+20]
    mov edx,[esp+24]
    mov ecx,esp
    and esp,0fffffff0h
    sub esp,560
    mov [esp+512],eax
    mov [esp+516],edx
    mov [esp+520],ecx
    mov [esp+524],esp
    fxsave [esp]
    fninit
    fld1
    fldpi
    fldcw cwseed
    ldmxcsr mxseed
    fxsave [edx+240]
    mov ebp,12345678h
    mov ebx,23456789h
    mov esi,3456789ah
    mov edi,456789abh
    push DWORD PTR [eax+28]
    push DWORD PTR [eax+24]
    push DWORD PTR [eax+20]
    push DWORD PTR [eax+16]
    push DWORD PTR [eax+12]
    push DWORD PTR [eax+8]
    push DWORD PTR [eax+4]
    call DWORD PTR [eax]
    mov edx,[esp+516]
    fxsave [edx+752]
    mov [edx],eax
    mov eax,esp
    sub eax,[esp+524]
    mov [edx+4],eax
    mov [edx+8],ebp
    mov [edx+16],ebx
    mov [edx+24],esi
    mov [edx+32],edi
    fxrstor [esp]
    mov esp,[esp+520]
    pop edi
    pop esi
    pop ebx
    pop ebp
    ret
device_abi ENDP
END

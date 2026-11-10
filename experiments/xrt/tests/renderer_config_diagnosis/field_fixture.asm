.code
PUBLIC field_stop
field_stop PROC
    mov DWORD PTR [rcx+44h],12345678h
    ret
field_stop ENDP
END

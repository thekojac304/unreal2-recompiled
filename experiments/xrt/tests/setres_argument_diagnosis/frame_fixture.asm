.code
PUBLIC owned_entry
owned_entry PROC
    mov DWORD PTR [rcx+44h], 12345678h
    ret
owned_entry ENDP
END

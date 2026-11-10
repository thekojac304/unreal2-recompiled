; xrt_eh_land.asm - ehframe C++ EH landing trampoline (runtime xrt_eh.c land_frame, xlift --opt ehframe).
; RtlUnwindEx ends here in the context of translated function F at its call site in progress (rsp = F's rsp, F's
; registers), with rax = the landing pad. The trampoline puts that call's return address (pad->host_ret, +32) back as a
; return address and jumps to xrt_eh_land_entry, which therefore runs as if F had called it from that site: stack walks
; through it reach F and F's caller, and it returns from F by unwinding F's frame.
option casemap:none
EXTERN xrt_eh_land_entry:PROC
.code
xrt_eh_land_tramp PROC
    mov rcx, rax
    mov rdx, [rax+32]
    sub rsp, 8
    mov [rsp], rdx
    jmp xrt_eh_land_entry
xrt_eh_land_tramp ENDP
END

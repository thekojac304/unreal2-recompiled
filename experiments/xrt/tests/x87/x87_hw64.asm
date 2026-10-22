; x87_hw64.asm - x87 reference kernels for the x64 harness (ml64).
;
; The x87 unit is the same hardware in 64-bit mode; these kernels let the x64 harness compare the
; runtime against the hardware in-process over all 2^32 float arguments. Their results are checked
; against the 32-bit inline-asm reference (x87_hw32.c) with per-chunk hashes over the whole input
; space (README.md), so they are a validated accelerator, not a separate reference.
;
; Kernel argument block (rcx):
;   +0 in (float*, float pairs for atan2)  +8 n  +16 r32 (float*)  +24 r64 (double*)
;   +32 r80 (16-byte stride)  +40 sw (uint16*)  +48 saved FCW  +50 working FCW
; Each element: <body> leaves the result in ST(0) (or an empty stack, like appTan out of range),
; then FSW, 80-bit, double and float stores are taken exactly like the engine's fstp.

        .code

KPROLOG macro
        fnstcw  word ptr [rcx+48]
        mov     word ptr [rcx+50], 027Fh
        fldcw   word ptr [rcx+50]
        mov     r8,  [rcx]
        mov     r9,  [rcx+8]
        mov     r10, [rcx+16]
        mov     r11, [rcx+24]
        mov     rdx, [rcx+32]
        mov     rax, [rcx+40]
        endm

KSTORE  macro stride
        fnstsw  word ptr [rax]
        fld     st(0)
        fstp    tbyte ptr [rdx]
        fld     st(0)
        fstp    qword ptr [r11]
        fstp    dword ptr [r10]
        add     r8, stride
        add     r10, 4
        add     r11, 8
        add     rdx, 16
        add     rax, 2
        endm

KERNEL  macro name, stride, body
name    proc
        KPROLOG
        test    r9, r9
        jz      name&_done
name&_loop:
        body
        KSTORE  stride
        dec     r9
        jnz     name&_loop
name&_done:
        fldcw   word ptr [rcx+48]
        ret
name    endp
        endm

B_SIN   macro
        fld     dword ptr [r8]
        fsin
        endm
B_COS   macro
        fld     dword ptr [r8]
        fcos
        endm
B_TAN   macro                       ; appTan: fld; fptan; fstp st(0)
        fld     dword ptr [r8]
        fptan
        fstp    st(0)
        endm
B_ATAN  macro                       ; appAtan: fld; fld1; fpatan
        fld     dword ptr [r8]
        fld1
        fpatan
        endm
B_SQRT  macro
        fld     dword ptr [r8]
        fsqrt
        endm
B_EXP   macro                       ; appExp
        fldl2e
        fmul    dword ptr [r8]
        fld     st(0)
        frndint
        fxch    st(1)
        fsub    st(0), st(1)
        f2xm1
        fld1
        faddp   st(1), st(0)
        fscale
        fstp    st(1)
        endm
B_LOGE  macro                       ; appLoge: fldln2; fld; fyl2x
        fldln2
        fld     dword ptr [r8]
        fyl2x
        endm
B_ATAN2 macro                       ; appAtan2(Y, X): fld Y; fld X; fpatan
        fld     dword ptr [r8]
        fld     dword ptr [r8+4]
        fpatan
        endm

KERNEL  x87k_sin, 4, B_SIN
KERNEL  x87k_cos, 4, B_COS
KERNEL  x87k_tan, 4, B_TAN
KERNEL  x87k_atan, 4, B_ATAN
KERNEL  x87k_sqrt, 4, B_SQRT
KERNEL  x87k_exp, 4, B_EXP
KERNEL  x87k_loge, 4, B_LOGE
KERNEL  x87k_atan2, 8, B_ATAN2

; ---------------------------------------------------------------- single instructions on doubles
; Used by the "host x87" alternative helper model (x87_alt.c). FCW must already be 0x027F
; (x87_setcw). Each returns FSW in ax.

x87_setcw proc                      ; void x87_setcw(uint16_t cw)
        mov     word ptr [rsp+8], cx    ; caller's home space
        fldcw   word ptr [rsp+8]
        ret
x87_setcw endp

x87_getcw proc                      ; uint16_t x87_getcw(void)
        fnstcw  word ptr [rsp+8]
        movzx   eax, word ptr [rsp+8]
        ret
x87_getcw endp

x87d_fsin proc                      ; uint16_t x87d_fsin(double* st0)
        fld     qword ptr [rcx]
        fsin
        fnstsw  ax
        fstp    qword ptr [rcx]
        ret
x87d_fsin endp

x87d_fcos proc
        fld     qword ptr [rcx]
        fcos
        fnstsw  ax
        fstp    qword ptr [rcx]
        ret
x87d_fcos endp

x87d_fptan proc                     ; uint16_t x87d_fptan(double* st0): tan if C2 = 0 (1.0 popped)
        fld     qword ptr [rcx]
        fptan
        fnstsw  ax
        test    ax, 0400h
        jnz     @F
        fstp    st(0)
@@:     fstp    qword ptr [rcx]
        ret
x87d_fptan endp

x87d_fpatan proc                    ; uint16_t x87d_fpatan(double* st1, double* st0) -> *st1
        fld     qword ptr [rcx]
        fld     qword ptr [rdx]
        fpatan
        fnstsw  ax
        fstp    qword ptr [rcx]
        ret
x87d_fpatan endp

x87d_fyl2x proc                     ; uint16_t x87d_fyl2x(double* st1, double* st0) -> *st1
        fld     qword ptr [rcx]
        fld     qword ptr [rdx]
        fyl2x
        fnstsw  ax
        fstp    qword ptr [rcx]
        ret
x87d_fyl2x endp

x87d_f2xm1 proc
        fld     qword ptr [rcx]
        f2xm1
        fnstsw  ax
        fstp    qword ptr [rcx]
        ret
x87d_f2xm1 endp

x87d_fscale proc                    ; uint16_t x87d_fscale(double* st0, double* st1) -> *st0
        fld     qword ptr [rdx]
        fld     qword ptr [rcx]
        fscale
        fnstsw  ax
        fstp    qword ptr [rcx]
        fstp    st(0)
        ret
x87d_fscale endp

x87d_fsqrt proc
        fld     qword ptr [rcx]
        fsqrt
        fnstsw  ax
        fstp    qword ptr [rcx]
        ret
x87d_fsqrt endp

        end

/* Minimal setjmp.h for the translated game code (see README.txt): jmp_buf has the Microsoft x64 layout (16 x 16-byte,
 * 16-aligned, 256 bytes), so structures that embed it match the runtime's. The ehframe builds do not call setjmp. */
#ifndef XRT_COMPAT_SETJMP_H
#define XRT_COMPAT_SETJMP_H
typedef struct __declspec(align(16)) { unsigned long long Part[2]; } XRT_JB_FLOAT128;
typedef XRT_JB_FLOAT128 jmp_buf[16];
int _setjmp(jmp_buf);
#define setjmp(b) _setjmp(b)
__declspec(noreturn) void longjmp(jmp_buf, int);
#endif

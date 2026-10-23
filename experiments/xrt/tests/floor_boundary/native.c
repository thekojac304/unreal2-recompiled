/* Calls the sandbox's actual x86 msvcr70 export; no compiler floor intrinsic. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef double (__cdecl *Floor)(double);
typedef int* (__cdecl *Errno)(void);
static Floor target;
static void run(uint64_t bits, unsigned cw, unsigned sw, unsigned depth, FILE* out, Errno ep) {
    unsigned char env[28];
    unsigned short before, after, control;
    uint64_t result, lower[4];
    double sentinel = 123.25;
    unsigned i;
    int err;
    __asm { fninit }
    for (i=0; i<depth; i++) { __asm { fld sentinel } }
    __asm { fnstenv env }
    memcpy(env, &cw, 2);
    /* Keep hardware TOP; seed only condition codes and masked sticky flags. */
    memcpy(&before, env+4, 2);
    before = (unsigned short)((before & 0x3800) | sw);
    memcpy(env+4, &before, 2);
    *ep() = 0x5a5a;
    __asm {
        fldenv env
        fnstsw before
        push dword ptr bits[4]
        push dword ptr bits[0]
        call target
        add esp, 8
        fnstsw after
        fnstcw control
        fstp qword ptr result
    }
    for (i=0; i<depth; i++) { uint64_t b; __asm { fstp qword ptr b } lower[i]=b; }
    __asm { fninit }
    err=*ep();
    fprintf(out,"%016llx %04x %04x %u %016llx %04x %04x %d",bits,cw,sw,depth,result,control,after,err);
    for(i=0;i<depth;i++) fprintf(out," %016llx",lower[i]);
    fputc('\n',out);
}
int main(int argc,char** argv) {
    HMODULE dll; FILE *in,*out; uint64_t bits; unsigned cw,sw,depth; Errno ep;
    if(argc!=4 && argc!=5) return 2;
    dll=LoadLibraryA(argv[1]);
    if(!dll || !(target=(Floor)GetProcAddress(dll,argc==5?argv[4]:"floor")) || !(ep=(Errno)GetProcAddress(dll,"_errno"))) return 3;
    in=fopen(argv[2],"r"); out=fopen(argv[3],"w"); if(!in||!out)return 4;
    while(fscanf(in,"%llx %x %x %u",&bits,&cw,&sw,&depth)==4) {
        if(depth>4 || (cw&0x3f)!=0x3f || (sw&~0x472f)) return 5;
        run(bits,cw,sw,depth,out,ep);
    }
    fclose(in); return fclose(out)!=0;
}

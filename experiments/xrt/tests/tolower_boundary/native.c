/* Real x86 msvcr70 export, never a compiler ctype intrinsic. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "corpus.h"
typedef int (__cdecl *Unary)(int);
typedef int* (__cdecl *Errno)(void);
typedef char* (__cdecl *Locale)(int,const char*);
static Unary target;
static Errno ep;
static int* thread_errno[2];
static HANDLE ready[2],release_threads;
static DWORD WINAPI worker(void* arg) {
    unsigned n=(unsigned)(uintptr_t)arg; int first,e; DWORD le;
    SetLastError(0x12345678); first=target('A'); le=GetLastError();
    thread_errno[n]=ep(); e=*thread_errno[n]; *thread_errno[n]=0x1357+(int)n;
    printf("thread %u first %x le %lx initial_errno %x\n",n,first,le,e);
    SetEvent(ready[n]); WaitForSingleObject(release_threads,INFINITE);
    if(*thread_errno[n]!=0x1357+(int)n)return 8;
    return 0;
}
static void one(FILE* out,uint32_t x,int* err) {
    uint32_t r=0,exception=0,sp0=0,sp1=0,b=0,s=0,d=0,bp0=0,bp1=0; DWORD le;
    *err=0x5a5a; SetLastError(0x12345678);
    __try {
        __asm {
            push ebx
            push esi
            push edi
            mov sp0,esp
            mov bp0,ebp
            mov ebx,0x12345671
            mov esi,0x12345672
            mov edi,0x12345673
            push x
            call target
            mov r,eax
            add esp,4
            mov sp1,esp
            mov bp1,ebp
            mov b,ebx
            mov s,esi
            mov d,edi
            pop edi
            pop esi
            pop ebx
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) { exception=GetExceptionCode(); }
    le=GetLastError();
    fprintf(out,"%08x %08x %08x %08x %08lx %u\n",x,r,exception,*err,le,
        sp0==sp1 && bp0==bp1 && b==0x12345671 && s==0x12345672 && d==0x12345673);
}
int main(int argc,char**argv) {
    HMODULE dll; Locale loc; Unary mb; FILE*out; unsigned i; int*err; HANDLE threads[2];
    if(argc!=5)return 2;
    dll=LoadLibraryA(argv[1]); if(!dll)return 3;
    target=(Unary)GetProcAddress(dll,"tolower");ep=(Errno)GetProcAddress(dll,"_errno");
    loc=(Locale)GetProcAddress(dll,"setlocale");mb=(Unary)GetProcAddress(dll,"_setmbcp");
    if(!target||!ep||!loc||!mb)return 4;
    printf("ACP %u locale %s\n",GetACP(),loc(2,NULL));
    /* New threads' first tolower call, before touching their CRT errno. */
    release_threads=CreateEvent(NULL,TRUE,FALSE,NULL);
    for(i=0;i<2;i++) { ready[i]=CreateEvent(NULL,TRUE,FALSE,NULL);threads[i]=CreateThread(NULL,0,worker,(void*)(uintptr_t)i,0,NULL);WaitForSingleObject(ready[i],INFINITE); }
    printf("thread errno distinct %u main_distinct %u\n",thread_errno[0]!=thread_errno[1],ep()!=thread_errno[0] && ep()!=thread_errno[1]);
    SetEvent(release_threads);WaitForMultipleObjects(2,threads,TRUE,INFINITE);
    if(!strcmp(argv[3],"sweep")) {
        uint32_t x=0;uint64_t differences=0;
        do {uint32_t r=(uint32_t)target((int)x);if(r!=(x-65u<26u?x+32u:x))differences++;}while(++x);
        printf("sweep 4294967296 differences %llu\n",differences);return differences!=0;
    }
    if(!loc(2,argv[3]))return 5;
    if(mb(atoi(argv[4]))!=0)return 6;
    printf("active %s mbcp %s\n",loc(2,NULL),argv[4]);
    err=ep();out=fopen(argv[2],"w");if(!out)return 7;
    for(i=0;i<CASES;i++)one(out,sample(i),err);
    return fclose(out)!=0;
}

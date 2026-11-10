/* Project-owned, non-game test. SEC_IMAGE_NO_EXECUTE never runs candidate code. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#ifndef CANDIDATE_PATH
#error fixed candidate path required
#endif
extern void owned_invoke(void*, unsigned);
extern void owned_stop(void);
static unsigned char cpu[128];
static DWORD WINAPI worker(void* ignored) {
    (void)ignored;
    owned_invoke(cpu, 0x11104bf8);
    return 9;
}
int main(void) {
    HANDLE file, mapping, thread; void* base; FILE* out;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    memset(cpu,0x55,sizeof(cpu));
    file=CreateFileA(CANDIDATE_PATH,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
    if(file==INVALID_HANDLE_VALUE)return 2;
    mapping=CreateFileMappingW(file,NULL,PAGE_READONLY|SEC_IMAGE_NO_EXECUTE,0,0,NULL);
    if(!mapping)return 3;
    base=MapViewOfFile(mapping,FILE_MAP_READ,0,0,0);
    if(!base)return 4;
    if(fopen_s(&out,"ready.json","w"))return 5;
    fprintf(out,"{\"pid\":%lu,\"candidate_base\":%llu,\"sentinel\":%llu,\"cpu\":%llu}",GetCurrentProcessId(),
       (unsigned long long)(uintptr_t)base,(unsigned long long)(uintptr_t)&owned_stop,(unsigned long long)(uintptr_t)cpu);
    fclose(out);
    DebugBreak();
    thread=CreateThread(NULL,0,worker,NULL,0,NULL);
    if(!thread)return 6;
    WaitForSingleObject(thread,3000);
    if(!fopen_s(&out,"FORBIDDEN.txt","w")){fputs("instruction executed",out);fclose(out);}
    return 7;
}

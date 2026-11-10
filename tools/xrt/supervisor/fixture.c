/* Project-owned non-game debugger/watchdog fixture. No shell or network. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    FILE *f; unsigned char buffer[32]; unsigned i;
    HMODULE n=GetModuleHandleW(L"ntdll.dll");
    void (WINAPI *zero)(void*,SIZE_T)=(void*)GetProcAddress(n,"RtlZeroMemory");
    if(argc!=2)return 2;
    if(!strcmp(argv[1],"routine-failure")){fputs("known disposable fixture defect\n",stderr);return 23;}
    if(!strcmp(argv[1],"sleep-child")){Sleep(120000);return 0;}
    if(!strcmp(argv[1],"tree")) {
        char exe[MAX_PATH],command[2*MAX_PATH];STARTUPINFOA si={sizeof si};PROCESS_INFORMATION pi={0};
        if(!GetModuleFileNameA(NULL,exe,sizeof exe))return 3;
        sprintf_s(command,sizeof command,"\"%s\" sleep-child",exe);
        if(!CreateProcessA(exe,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,NULL,&si,&pi))return 4;
        if(fopen_s(&f,"child.json","w"))return 5;
        fprintf(f,"{\"pid\":%lu}",pi.dwProcessId);fclose(f);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);
        Sleep(120000);return 0;
    }
    if(!strcmp(argv[1],"hang")){Sleep(120000);return 0;}
    if(!strcmp(argv[1],"hard-stop")||!strcmp(argv[1],"fatal-stop")) {
        memset(buffer,0x55,sizeof buffer);
        if(fopen_s(&f,"ready.json","w"))return 5;
        fprintf(f,"{\"pid\":%lu,\"target\":%llu,\"buffer\":%llu}",GetCurrentProcessId(),
                (unsigned long long)(ULONG_PTR)zero,(unsigned long long)(ULONG_PTR)buffer);fclose(f);
        DebugBreak();zero(buffer,sizeof buffer);
        if(fopen_s(&f,"FORBIDDEN.txt","w"))return 6;fputs("instruction executed",f);fclose(f);return 7;
    }
    if(strcmp(argv[1],"ok-a")&&strcmp(argv[1],"ok-b"))return 8;
    for(i=0;i<2;i++)OutputDebugStringA("supervisor fixture event\n");
    fprintf(stdout,"fixture %s complete\n",argv[1]);fprintf(stderr,"fixture stderr preserved\n");
    return 0;
}

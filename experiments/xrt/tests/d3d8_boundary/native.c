/* Explicitly load one backend; record actual module paths separately from
 * comparable probe values. All configuration/logs remain in the case folder. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
int main(int argc,char**argv) {
    HMODULE backend,m;
    int *log,*n,i,k,r;
    char path[2048];
    const char*names[]={"d3d8.dll","d3d9.dll","d3d11.dll","vulkan-1.dll"};
    if(argc<4)return 2;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    backend=LoadLibraryExA(argv[1],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!backend) {fprintf(stderr,"backend load error %lu\n",GetLastError());return 2;}
    m=LoadLibraryExA(argv[2],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!m) {fprintf(stderr,"probe load error %lu\n",GetLastError());return 2;}
    log=(int*)GetProcAddress(m,"probe_log");n=(int*)GetProcAddress(m,"probe_log_n");
    for(i=3;i<argc;i++) {
        int(*fn)(void)=(int(*)(void))GetProcAddress(m,argv[i]);
        if(!fn||!log||!n)return 2;
        r=fn();printf("%s returned %d log",argv[i],r);
        for(k=0;k<*n;k++)printf(" %d",log[k]);puts("");
    }
    for(i=0;i<4;i++) if((m=GetModuleHandleA(names[i]))!=NULL && GetModuleFileNameA(m,path,sizeof path))
        fprintf(stderr,"module %s %s\n",names[i],path);
    return 0;
}

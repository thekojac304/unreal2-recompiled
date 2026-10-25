/* Explicit paired backend loading, fixture lifetime cleanup and unload audit. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
int main(int argc,char**argv) {
    HMODULE backend,dep,m;int *log,*n,i,k,r;char path[2048];
    if(argc<4)return 2;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    snprintf(path,sizeof path,"%s\\d3d9.dll",argv[1]);
    dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path,sizeof path,"%s\\d3d8.dll",argv[1]);
    backend=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!dep||!backend)return 2;
    m=LoadLibraryExA(argv[2],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!m)return 2;
    log=(int*)GetProcAddress(m,"probe_log");n=(int*)GetProcAddress(m,"probe_log_n");
    for(i=3;i<argc;i++) {
        int(*fn)(void)=(int(*)(void))GetProcAddress(m,argv[i]);if(!fn||!log||!n)return 2;
        r=fn();printf("%s returned %d log",argv[i],r);
        for(k=0;k<*n;k++)printf(" %d",log[k]);puts("");if(r)return 3;
    }
    r=((int(*)(void))GetProcAddress(m,"probe_native_cleanup"))();
    fprintf(stderr,"cleanup outstanding final Release %d\n",r);if(r)return 4;
    if(GetModuleFileNameA(backend,path,sizeof path))fprintf(stderr,"d3d8 %s\n",path);
    if(GetModuleFileNameA(dep,path,sizeof path))fprintf(stderr,"d3d9 %s\n",path);
    FreeLibrary(m);FreeLibrary(backend);FreeLibrary(dep);
    r=GetModuleHandleA("d3d8.dll")!=NULL||GetModuleHandleA("d3d9.dll")!=NULL;
    fprintf(stderr,"shutdown backend modules remaining %d\n",r);return r?5:0;
}

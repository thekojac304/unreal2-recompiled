#define WIN32_LEAN_AND_MEAN
#include <windows.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllimport) void* __cdecl fopen(const char*,const char*);
__declspec(dllimport) int __cdecl fclose(void*);
__declspec(dllimport) unsigned __cdecl fread(void*,unsigned,unsigned,void*);
__declspec(dllimport) int __cdecl fseek(void*,long,int);
__declspec(dllexport) int probe_log[512],probe_log_n;
static int failures;
static BYTE data[10003],buffer[16384];
static char path[600];
static void check(unsigned got,unsigned want) {probe_log[probe_log_n++]=(int)got;if(got!=want) failures++;}
static void prepare(void) {
    HANDLE h;DWORD got;unsigned i,n;
    n=GetModuleFileNameA((HMODULE)&__ImageBase,path,sizeof path);
    while(n && path[n-1]!='\\')n--;
    for(i=0;"fread-oracle.bin"[i];i++)path[n+i]="fread-oracle.bin"[i];path[n+i]=0;
    for(i=0;i<sizeof data;i++)data[i]=(BYTE)(i*37+11);
    h=CreateFileA(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    check(h!=INVALID_HANDLE_VALUE,1);check(WriteFile(h,data,sizeof data,&got,NULL),1);check(got,sizeof data);check(CloseHandle(h),1);
}
static void state(void* file) {
    unsigned* f=(unsigned*)file;
    /* Normalize pointer identities, retain actual buffer offset/count/flags/capacity. */
    probe_log[probe_log_n++]=f[0]?f[0]-f[2]:0;
    probe_log[probe_log_n++]=f[1];probe_log[probe_log_n++]=f[3];probe_log[probe_log_n++]=f[4];
    probe_log[probe_log_n++]=f[5];probe_log[probe_log_n++]=f[6];check(f[7]==0,1);
}
__declspec(dllexport) int probe_file(void) {
    void* file;unsigned i,n,pos=0,sizes[]={0,1,3,1,7,1},counts[]={13,3,4,4096,900,9999};
    probe_log_n=failures=0;prepare();
    file=fopen(path,"rb");check(file!=NULL,1);
    for(i=0;i<6;i++) {
        unsigned j,bytes=sizes[i]*counts[i],expected=bytes;
        if(expected>sizeof data-pos)expected=sizeof data-pos;
        SetLastError(0x5555);n=fread(buffer,sizes[i],counts[i],file);
        check(n,sizes[i]?expected/sizes[i]:0);check(GetLastError(),0x5555);
        for(j=0;j<expected;j++) if(buffer[j]!=data[pos+j])failures++;
        check(j,expected);pos+=expected;state(file);
    }
    check(fread(NULL,0,13,file),0);check(fread(NULL,13,0,file),0);
    check(fclose(file),0);
    file=fopen(path,"rb");check(file!=NULL,1);
    check(fread(buffer,1,8192,file),8192);state(file);check(fclose(file),0);
    return failures; /* Keep the owned input in the fixture's isolated output directory. */
}
__declspec(dllexport) int probe_text_read(void) {
    void* file;probe_log_n=failures=0;prepare();file=fopen(path,"r");return (int)fread(buffer,1,1,file);
}
static void seek_to(void* file,int offset,int origin,int expected) {
    SetLastError(0x5555);*_errno()=0;
    check(fseek(file,offset,origin),expected);probe_log[probe_log_n++]=GetLastError();probe_log[probe_log_n++]=*_errno();state(file);
}
__declspec(dllexport) int probe_seek(void) {
    void* file;unsigned i;
    probe_log_n=failures=0;prepare();file=fopen(path,"rb");check(file!=NULL,1);
    check(fread(buffer,1,3,file),3);seek_to(file,2,1,0);
    check(fread(buffer,1,8,file),8);for(i=0;i<8;i++)check(buffer[i],data[5+i]);state(file);
    seek_to(file,-7,2,0);check(fread(buffer,3,4,file),2);state(file);
    seek_to(file,0,0,0);check(fread(buffer,1,1,file),1);check(buffer[0],data[0]);state(file);
    seek_to(file,0,9,-1);seek_to(file,-1,0,-1);check(fclose(file),0);
    file=fopen(path,"rb");check(fread(buffer,1,3,file),3);seek_to(file,0,0,0);
    check(fread(buffer,1,8192,file),8192);state(file);check(fclose(file),0);
    return failures;
}
__declspec(dllexport) int probe_invalid_file(void) {return (int)fread(buffer,1,1,NULL);}
__declspec(dllexport) int probe_large_read(void) {
    void* file;probe_log_n=failures=0;prepare();file=fopen(path,"rb");return (int)fread(buffer,0x80000000u,2,file);
}

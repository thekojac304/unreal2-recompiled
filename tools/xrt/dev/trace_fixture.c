/* Owned native calls only. No generated/game objects or runtime adapters. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "monitor.h"
uint8_t *xrt_g;
extern int xm_fpu_oracle(CPU*,const XmRequest*);
#define CHECK(x) do{if(!(x)){fprintf(stderr,"check %d: %s\n",__LINE__,#x);ExitProcess(91);}}while(0)
static volatile LONG calls;
static __declspec(noinline) void *owned_failure(unsigned requested) {
 CHECK(requested==123);SetLastError(ERROR_NOT_ENOUGH_MEMORY);return NULL;
}
static __declspec(noinline) unsigned owned_length(const wchar_t *s) {
 InterlockedIncrement(&calls);SetLastError(0x12345678);return (unsigned)wcslen(s);
}
static void event(CPU*c,unsigned kind,const char*name,uint64_t result,unsigned domain) {
 CPU before=*c;DWORD error=GetLastError();XmRequest q={0};
 q.event=kind;q.name=name;q.domain=domain;q.result=result;
 CHECK(xm_fpu_oracle(c,&q));CHECK(!memcmp(c,&before,sizeof before));CHECK(GetLastError()==error);
}
static void length(CPU*c,unsigned i) {
 wchar_t input[18];unsigned j,result;
 for(j=0;j<i%17;j++)input[j]=L'x';input[j]=0;
 c->pc=0x12340000+i;c->r[EAX]=i;
 event(c,XM_BEGIN,"msvcr70.dll!wcslen",0,XM_ADAPTER);
 result=owned_length(input);CHECK(result==i%17&&GetLastError()==0x12345678);
 c->r[EAX]=result;
 event(c,XM_END,"msvcr70.dll!wcslen",result,XM_ADAPTER);
}
static DWORD WINAPI worker(void*param) {
 CPU c={0};unsigned i;c.r[ESP]=0x2000;c.fs_base=0x1000;
 for(i=0;i<1003;i++)length(&c,i);return 0;
}
static void fileio(CPU*c,const char*path,unsigned count) {
 HANDLE f;DWORD got,error;BOOL ok;unsigned i;char byte='Q',out=0;
 f=CreateFileA(path,GENERIC_READ|GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_TEMPORARY,NULL);
 CHECK(f!=INVALID_HANDLE_VALUE);
 for(i=0;i<count;i++){
  c->pc=0x12340010;c->r[ESP]=0x2000;
  wr32(0x2004,0x1004);wr32(0x2008,0x3000);wr32(0x200c,1);wr32(0x2010,0x3100);wr32(0x2014,0);
  event(c,XM_BEGIN,"kernel32.dll!WriteFile",0,XM_ADAPTER);
  ok=WriteFile(f,&byte,1,&got,NULL);error=GetLastError();CHECK(ok&&got==1);
  wr32(0x3100,got);c->r[ESP]+=24;c->r[EAX]=ok;SetLastError(error);
  event(c,XM_END,"kernel32.dll!WriteFile",ok,XM_ADAPTER);
  c->r[ESP]=0x2000;wr32(0x2008,0);wr32(0x200c,0);wr32(0x2010,FILE_BEGIN);
  event(c,XM_BEGIN,"kernel32.dll!SetFilePointer",0,XM_ADAPTER);
  got=SetFilePointer(f,0,NULL,FILE_BEGIN);CHECK(got==0);wr32(0x1034,0);c->r[ESP]+=20;c->r[EAX]=got;
  event(c,XM_END,"kernel32.dll!SetFilePointer",got,XM_ADAPTER);
  c->r[ESP]=0x2000;wr32(0x2008,0x3000);wr32(0x200c,1);wr32(0x2010,0x3100);
  event(c,XM_BEGIN,"kernel32.dll!ReadFile",0,XM_ADAPTER);
  ok=ReadFile(f,&out,1,&got,NULL);error=GetLastError();CHECK(ok&&got==1&&out==byte);
  wr32(0x3100,got);c->r[ESP]+=24;c->r[EAX]=ok;SetLastError(error);
  event(c,XM_END,"kernel32.dll!ReadFile",ok,XM_ADAPTER);
 }
 /* Successful EOF/short read is not failure, even with stale LastError. */
 CHECK(SetFilePointer(f,0,NULL,FILE_END)!=INVALID_SET_FILE_POINTER);
 c->r[ESP]=0x2000;event(c,XM_BEGIN,"kernel32.dll!ReadFile",0,XM_ADAPTER);
 ok=ReadFile(f,&out,1,&got,NULL);CHECK(ok&&got==0);wr32(0x3100,got);c->r[ESP]+=24;
 event(c,XM_END,"kernel32.dll!ReadFile",ok,XM_ADAPTER);
 CHECK(CloseHandle(f));c->r[ESP]=0x2000;
 for(i=0;i<3;i++){
  event(c,XM_BEGIN,"kernel32.dll!ReadFile",0,XM_ADAPTER);
  ok=ReadFile(INVALID_HANDLE_VALUE,&out,1,&got,NULL);error=GetLastError();CHECK(!ok&&error==ERROR_INVALID_HANDLE);
  wr32(0x1034,error);wr32(0x3100,got);c->r[ESP]+=24;
  event(c,XM_END,"kernel32.dll!ReadFile",ok,XM_ADAPTER);c->r[ESP]=0x2000;
 }
 CHECK(DeleteFileA(path));
}
int main(int argc,char**argv) {
 CPU c={0};unsigned i,n;const char *mode;HANDLE threads[3];
 CHECK(argc==3);mode=argv[2];
 xrt_g=VirtualAlloc(NULL,0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);CHECK(xrt_g);
 c.r[ESP]=0x2000;c.fs_base=0x1000;c.fcw=0x27f;wr32(0x2000,0xabc123);wr32(0x1034,0x76543210);
 SetLastError(0x99887766);xm_init(argv[1]);CHECK(GetLastError()==0x99887766);
 n=!strcmp(mode,"large")||!strcmp(mode,"fatal")?200003:37;
 if(!strcmp(mode,"exhaust")||!strcmp(mode,"abrupt")){
  for(i=0;i<140003;i++)event(&c,XM_DATA,"owned.detail",i,0);
  if(!strcmp(mode,"abrupt"))TerminateProcess(GetCurrentProcess(),77);
  xm_close();return 0;
 }
 if(!strcmp(mode,"fileio")){
  char path[2048];snprintf(path,sizeof path,"%s.owned-file",argv[1]);fileio(&c,path,70003);
  event(&c,XM_BEGIN,"UGameEngine.Init",0,XM_ADAPTER);
  event(&c,XM_END,"UGameEngine.Init",1,XM_ADAPTER);
  xm_checkpoint(&c,"dev.Init.return");ExitProcess(10);
 }
 if(!strcmp(mode,"overflow")){
  char name[128];for(i=0;i<600;i++){
   snprintf(name,sizeof name,"owned.operation.%u",i);
   event(&c,XM_BEGIN,name,0,XM_ADAPTER);event(&c,XM_END,name,i,XM_ADAPTER);
  }xm_close();return 0;
 }
 if(!strcmp(mode,"unknown")){
  for(i=0;i<70003;i++){
   event(&c,XM_BEGIN,"owned.unclassified",0,XM_ADAPTER);
   event(&c,XM_END,"owned.unclassified",i==0?7:0x80001234,XM_ADAPTER);
  }xm_close();return 0;
 }
 if(!strcmp(mode,"seek-status")){
  /* Owned return fixtures exercise the ambiguous DWORD sentinel contract. */
  for(i=0;i<2;i++){
   wr32(0x1034,0);event(&c,XM_BEGIN,"kernel32.dll!SetFilePointer",0,XM_ADAPTER);
   wr32(0x1034,i?ERROR_INVALID_HANDLE:0);SetLastError(0x76543210);
   event(&c,XM_END,"kernel32.dll!SetFilePointer",0xffffffffu,XM_ADAPTER);
  }xm_close();return 0;
 }
 if(!strcmp(mode,"selected-nested")){
  const char payload[]="owned typed payload";
  c.pc=0xfeed1234;
  event(&c,XM_BEGIN,"owned.outer",0,XM_ADAPTER);c.pc++;
  event(&c,XM_BEGIN,"owned.inner",0,XM_NATIVE);
  xm_span(&c,"resource.map.upload",payload,sizeof payload);
  event(&c,XM_END,"owned.inner",1,XM_NATIVE);
  event(&c,XM_END,"owned.outer",1,XM_ADAPTER);xm_close();return 0;
 }
 if(!strcmp(mode,"threads")){
  for(i=0;i<3;i++){threads[i]=CreateThread(NULL,0,worker,NULL,0,NULL);CHECK(threads[i]);}
  CHECK(WaitForMultipleObjects(3,threads,TRUE,30000)==WAIT_OBJECT_0);CHECK(calls==3009);
 }else{for(i=0;i<n;i++)length(&c,i);CHECK(calls==(LONG)n);}
 if(!strcmp(mode,"fatal")){
  event(&c,XM_BEGIN,"msvcr70.dll!wcscpy",0,XM_ADAPTER);
  event(&c,XM_FATAL,"owned unsupported operation",76,0);ExitProcess(76);
 }
 if(!strcmp(mode,"failure")||!strcmp(mode,"failure-exit")){
  event(&c,XM_BEGIN,"msvcr70.dll!malloc",0,XM_ADAPTER);
  /* Deterministic owned allocation failure with a distinct LastError. */
  CHECK(!owned_failure(123));c.r[EAX]=0;
  event(&c,XM_END,"msvcr70.dll!malloc",0,XM_ADAPTER);
  if(!strcmp(mode,"failure-exit"))ExitProcess(0);
 }
 if(!strcmp(mode,"nested")){
  event(&c,XM_BEGIN,"msvcr70.dll!wcslen",0,XM_ADAPTER);
  event(&c,XM_BEGIN,"D3D8.owned.device",0,XM_NATIVE);
  event(&c,XM_END,"D3D8.owned.device",0x80004005,XM_NATIVE);
  event(&c,XM_END,"msvcr70.dll!wcslen",7,XM_ADAPTER);
  event(&c,XM_BEGIN,"msvcr70.dll!wcscpy",0,XM_ADAPTER);
  xm_unwind(&c,0,42);
 }
 if(!strcmp(mode,"unsupported")){
  event(&c,XM_BEGIN,"unknown.dll!Unsupported",0,XM_ADAPTER);
  event(&c,XM_FATAL,"import has no host implementation",78,0);ExitProcess(78);
 }
 event(&c,XM_BEGIN,"D3D8.owned.after-volume",0,XM_NATIVE);
 event(&c,XM_END,"D3D8.owned.after-volume",0,XM_NATIVE);
 xm_resource(&c,2,0x4000,1,123,1,0,"owned.resource");
#ifdef XRT_DEV_TRACE_TEST
 if(!strcmp(mode,"io-failure")){extern void xd_test_break_sink(void);xd_test_break_sink();}
#endif
 xm_checkpoint(&c,"owned.partial-batch");
 if(!strcmp(mode,"checkpoint"))ExitProcess(0);
 xm_close();printf("calls=%ld\n",calls);return 0;
}

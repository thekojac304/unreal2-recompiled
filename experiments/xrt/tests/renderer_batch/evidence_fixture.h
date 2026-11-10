/* Harness observations, separate from fixture stdout and from xrt runtime events. */
#ifndef XRT_EVIDENCE_FIXTURE_H
#define XRT_EVIDENCE_FIXTURE_H
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <d3d9.h>
static FILE* ev_stream;
static unsigned ev_attempted,ev_written,ev_errors;
static void ev_die(void){fprintf(stderr,"evidence collection failed: %lu\n",GetLastError());ExitProcess(94);}
static void ev_name(HANDLE h,char*b){DWORD n;if(!GetUserObjectInformationA(h,UOI_NAME,b,256,&n))ev_die();}
static void ev_path(char*b,const char*n){char root[1800];if(!GetEnvironmentVariableA("XRT_EVIDENCE_DIR",root,sizeof root))ev_die();if(snprintf(b,2048,"%s/%s",root,n)<0)ev_die();}
static void ev_event(const char*k,const char*fmt,...){
    DWORD error=GetLastError();char b[16384],path[2048];va_list ap;FILETIME t;int n;
    if(!GetEnvironmentVariableA("XRT_EVIDENCE_DIR",path,sizeof path)){SetLastError(error);return;}
    if(!ev_stream){ev_path(path,"runtime-events.jsonl");if(fopen_s(&ev_stream,path,"wb"))ev_die();}
    ev_attempted++;GetSystemTimePreciseAsFileTime(&t);va_start(ap,fmt);n=vsnprintf(b,sizeof b,fmt,ap);va_end(ap);
    if(n<0||n>=sizeof b)ev_die();
    if(fprintf(ev_stream,"{\"sequence\":%u,\"pid\":%lu,\"tid\":%lu,\"filetime\":%llu,\"event\":\"%s\",\"payload\":{%s}}\n",ev_attempted,GetCurrentProcessId(),GetCurrentThreadId(),((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime,k,b)<0||fflush(ev_stream))ev_errors++;else ev_written++;
    SetLastError(error);
}
static void ev_checkpoint(const char*phase){
    char path[2048],filename[128],station[256],desktop[256],input[256],name[256];DWORD session;FILE*f;HANDLE r,g;HDESK d;FILETIME t;
    if(!GetEnvironmentVariableA("XRT_EVIDENCE_DIR",path,sizeof path))return;
    ev_name(GetProcessWindowStation(),station);ev_name(GetThreadDesktop(GetCurrentThreadId()),desktop);
    d=OpenInputDesktop(0,FALSE,DESKTOP_READOBJECTS);if(d){ev_name(d,input);CloseDesktop(d);}else strcpy_s(input,sizeof input,"");
    ProcessIdToSessionId(GetCurrentProcessId(),&session);GetSystemTimePreciseAsFileTime(&t);
    snprintf(filename,sizeof filename,"%s-self.json",phase);ev_path(path,filename);if(fopen_s(&f,path,"wb"))ev_die();
    fprintf(f,"{\"phase\":\"%s\",\"pid\":%lu,\"tid\":%lu,\"session\":%lu,\"filetime\":%llu,\"window_station\":\"%s\",\"desktop\":\"%s\",\"input_desktop\":\"%s\",\"runtime_stream\":{\"attempted\":%u,\"written\":%u,\"write_errors\":%u,\"transport\":\"synchronous-file\",\"dropped_event_count\":null}}",phase,GetCurrentProcessId(),GetCurrentThreadId(),session,((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime,station,desktop,input,ev_attempted,ev_written,ev_errors);
    if(fclose(f))ev_die();
    if(!GetEnvironmentVariableA("XRT_EVIDENCE_READY",name,sizeof name))ev_die();r=OpenEventA(EVENT_MODIFY_STATE,FALSE,name);
    if(!GetEnvironmentVariableA("XRT_EVIDENCE_GATE",name,sizeof name))ev_die();g=OpenEventA(SYNCHRONIZE,FALSE,name);
    if(!r||!g||!SetEvent(r)||WaitForSingleObject(g,60000)!=WAIT_OBJECT_0)ev_die();CloseHandle(r);CloseHandle(g);
}
static void ev_backend_luid(HMODULE dep){
    typedef HRESULT(WINAPI*Create9Ex)(UINT,IDirect3D9Ex**);Create9Ex create=(Create9Ex)GetProcAddress(dep,"Direct3DCreate9Ex");
    IDirect3D9Ex*p=NULL;LUID id={0};HRESULT hr=create?create(32,&p):E_NOINTERFACE;ULONG refs=999;
    if(SUCCEEDED(hr)&&p){hr=p->lpVtbl->GetAdapterLUID(p,0,&id);refs=p->lpVtbl->Release(p);}
    printf("{\"kind\":\"backend-adapter\",\"hr\":%lu,\"ordinal\":0,\"luid_low\":%lu,\"luid_high\":%ld,\"query_parent_release\":%lu}\n",(DWORD)hr,id.LowPart,id.HighPart,refs);
}
#endif

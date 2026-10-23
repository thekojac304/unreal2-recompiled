/* Selected Windows child transport. One outstanding request; callback replies
 * share that request's absolute deadline and cannot extend it. The inherited
 * pipe capacity exceeds one frame. Only one frame is written before a read.
 * No helper-specific state is exposed to translated COM interfaces. */
#ifndef XRT_DMUSIC_PIPE_H
#define XRT_DMUSIC_PIPE_H
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "dmusic_backend.h"
typedef int (*DmbCallback)(void*,const DmbMessage*,DmbMessage*);
typedef struct {
 HANDLE input,output,process,job;DWORD owner;uint32_t sequence,timeout;
 DmbCallback callback;void*context;char error[160];int busy;
} DmbConnection;
static void dmb_disconnect(DmbConnection*c) {
 if(c->job)CloseHandle(c->job);c->job=NULL;
 if(c->process){WaitForSingleObject(c->process,2000);CloseHandle(c->process);}c->process=NULL;
 if(c->input)CloseHandle(c->input);if(c->output)CloseHandle(c->output);
 c->input=c->output=NULL;c->busy=0;
}
static int dmb_failed(DmbConnection*c,const char*why) {
 snprintf(c->error,sizeof c->error,"%s (Win32 %lu)",why,GetLastError());
 dmb_disconnect(c);return 0;
}
typedef struct {HANDLE pipe;DmbMessage message;DWORD bytes,error;BOOL ok;} DmbWrite;
static DWORD WINAPI dmb_writer(void*context){DmbWrite*w=(DmbWrite*)context;
 w->ok=WriteFile(w->pipe,&w->message,sizeof w->message,&w->bytes,NULL);w->error=GetLastError();return 0;
}
/* Anonymous pipe writes are synchronous. Run the single bounded frame write on
 * a cancellable worker so even a broken peer that stops draining cannot hang
 * the guest apartment. The worker never touches guest or COM state. */
static int dmb_write(DmbConnection*c,const DmbMessage*m,ULONGLONG deadline){
 DmbWrite*w=(DmbWrite*)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof *w);HANDLE thread;DWORD waited,remaining;int ok;
 ULONGLONG now=GetTickCount64();
 if(!w||now>=deadline){if(w)HeapFree(GetProcessHeap(),0,w);return dmb_failed(c,"DirectMusic write deadline exceeded");}
 w->pipe=c->input;w->message=*m;thread=CreateThread(NULL,0,dmb_writer,w,0,NULL);
 if(!thread){HeapFree(GetProcessHeap(),0,w);return dmb_failed(c,"DirectMusic writer unavailable");}
 remaining=(DWORD)(deadline-now);waited=WaitForSingleObject(thread,remaining);
 if(waited!=WAIT_OBJECT_0){
  CancelSynchronousIo(thread);dmb_failed(c,"DirectMusic write deadline exceeded");
  /* Closing the Job and pipe breaks the pending write. If Windows has not
   * returned it yet, retain its private buffer until process exit. */
  if(WaitForSingleObject(thread,2000)==WAIT_OBJECT_0)HeapFree(GetProcessHeap(),0,w);
  CloseHandle(thread);return 0;
 }
 ok=w->ok&&w->bytes==sizeof *m;SetLastError(w->error);HeapFree(GetProcessHeap(),0,w);CloseHandle(thread);
 return ok?1:dmb_failed(c,"DirectMusic IPC write failed");
}
static int dmb_read(DmbConnection*c,DmbMessage*m,ULONGLONG deadline) {
 DWORD have=0,n=0,total=0;
 while(total<sizeof *m) {
  if(GetTickCount64()>=deadline)return dmb_failed(c,"DirectMusic IPC deadline exceeded");
  if(!PeekNamedPipe(c->output,NULL,0,NULL,&have,NULL))return dmb_failed(c,"DirectMusic IPC disconnected");
  if(have){if(have>sizeof *m-total)have=(DWORD)sizeof *m-total;
   if(!ReadFile(c->output,(BYTE*)m+total,have,&n,NULL)||!n)return dmb_failed(c,"DirectMusic IPC read failed");total+=n;
  }else if(WaitForSingleObject(c->process,2)!=WAIT_TIMEOUT){
   if(!PeekNamedPipe(c->output,NULL,0,NULL,&have,NULL)||!have)return dmb_failed(c,"DirectMusic child exited");
  }
 }
 return 1;
}
static int dmb_exchange(DmbConnection*c,DmbMessage*m) {
 DmbMessage r,q=*m;unsigned callbacks=0;ULONGLONG deadline;
 if(!c->process || c->owner!=GetCurrentThreadId() || c->busy)return dmb_failed(c,"DirectMusic transport ownership/reentrancy violation");
 c->busy=1;q.sequence=++c->sequence;deadline=GetTickCount64()+c->timeout;
 if(!dmb_write(c,&q,deadline))return 0;
 for(;;){
  if(!dmb_read(c,&r,deadline))return 0;
  if(r.magic!=DMB_MAGIC||r.version!=DMB_VERSION||r.bytes!=sizeof r||r.sequence!=q.sequence)
   return dmb_failed(c,"DirectMusic invalid response identity");
  if(r.kind==DMB_CALLBACK){
   DmbMessage reply=r;
   if(++callbacks>128||!c->callback||!c->callback(c->context,&r,&reply))return dmb_failed(c,"DirectMusic unsupported callback");
   reply.kind=DMB_CALLBACK_REPLY;
   if(GetTickCount64()>=deadline)return dmb_failed(c,"DirectMusic callback deadline exceeded");
   if(!dmb_write(c,&reply,deadline))return 0;
  }else {
   if(r.kind!=DMB_REPLY||r.op!=q.op||r.object!=q.object)return dmb_failed(c,"DirectMusic response mismatch");
   c->busy=0;*m=r;
   if(r.status){char why[100];snprintf(why,sizeof why,"DirectMusic rejected op %u handle %u status %u",q.op,q.object,r.status);return dmb_failed(c,why);}
   return 1;
  }
 }
}
static int dmb_connect(DmbConnection*c,const WCHAR*exe,const WCHAR*root,int testing,DmbCallback cb,void*context) {
 SECURITY_ATTRIBUTES sa={sizeof sa,NULL,TRUE};HANDLE childin=NULL,childout=NULL,childlog=NULL,inherit[3];
 STARTUPINFOEXW si;PROCESS_INFORMATION pi;JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
 SIZE_T bytes=0;WCHAR cmd[2400],cwd[600];DmbMessage hello;int result=0;
 memset(c,0,sizeof *c);memset(&si,0,sizeof si);memset(&pi,0,sizeof pi);memset(&limits,0,sizeof limits);
 c->owner=GetCurrentThreadId();c->timeout=10000;c->callback=cb;c->context=context;
 if(!CreatePipe(&childin,&c->input,&sa,65536)||!CreatePipe(&c->output,&childout,&sa,65536))goto done;
 if(!SetHandleInformation(c->input,HANDLE_FLAG_INHERIT,0)||!SetHandleInformation(c->output,HANDLE_FLAG_INHERIT,0))goto done;
 c->job=CreateJobObjectW(NULL,NULL);limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
 limits.BasicLimitInformation.ActiveProcessLimit=1;
 if(!c->job||!SetInformationJobObject(c->job,JobObjectExtendedLimitInformation,&limits,sizeof limits))goto done;
 InitializeProcThreadAttributeList(NULL,1,0,&bytes);
 si.lpAttributeList=(LPPROC_THREAD_ATTRIBUTE_LIST)HeapAlloc(GetProcessHeap(),0,bytes);if(!si.lpAttributeList)goto done;
 if(!InitializeProcThreadAttributeList(si.lpAttributeList,1,0,&bytes))goto done;
 if(!DuplicateHandle(GetCurrentProcess(),GetStdHandle(STD_ERROR_HANDLE),GetCurrentProcess(),&childlog,0,TRUE,DUPLICATE_SAME_ACCESS))goto done;
 inherit[0]=childin;inherit[1]=childout;inherit[2]=childlog;
 if(!UpdateProcThreadAttribute(si.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherit,sizeof inherit,NULL,NULL))goto done;
 si.StartupInfo.cb=sizeof si;si.StartupInfo.dwFlags=STARTF_USESHOWWINDOW|STARTF_USESTDHANDLES;si.StartupInfo.wShowWindow=SW_HIDE;
 si.StartupInfo.hStdInput=childin;si.StartupInfo.hStdOutput=childout;si.StartupInfo.hStdError=childlog;
 if(wcschr(exe,L'"')||wcschr(root,L'"')||wcslen(exe)>600||wcslen(root)>500)goto done;
 swprintf(cmd,2400,L"\"%s\" --pipes %llu %llu --sandbox \"%s\"%s",exe,(unsigned long long)(uintptr_t)childin,(unsigned long long)(uintptr_t)childout,root,testing?L" --test":L"");
 swprintf(cwd,600,L"%s\\System",root);
 if(!CreateProcessW(exe,cmd,NULL,NULL,TRUE,CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,NULL,cwd,&si.StartupInfo,&pi))goto done;
 c->process=pi.hProcess;
 if(!AssignProcessToJobObject(c->job,pi.hProcess)){TerminateProcess(pi.hProcess,91);goto done;}
 if(ResumeThread(pi.hThread)==(DWORD)-1)goto done;
 result=1;
done:
 if(pi.hThread)CloseHandle(pi.hThread);if(childin)CloseHandle(childin);if(childout)CloseHandle(childout);if(childlog)CloseHandle(childlog);
 if(si.lpAttributeList){DeleteProcThreadAttributeList(si.lpAttributeList);HeapFree(GetProcessHeap(),0,si.lpAttributeList);}
 if(!result)return dmb_failed(c,"DirectMusic helper launch failed");
 dmb_message(&hello,DMB_HELLO,0);
 if(!dmb_exchange(c,&hello))return 0;
 if(hello.v[0]!=32||hello.v[1]!=DMB_LIMIT)return dmb_failed(c,"DirectMusic helper architecture mismatch");
 return 1;
}
#endif

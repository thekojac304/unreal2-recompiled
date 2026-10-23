/* x64 focused session over the very same backend transport used by the game.
 * The local tool fixture is identical to session.c; the native objects and
 * routine results are obtained exclusively from the x86 helper. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <string.h>
#include "../../runtime/dmusic_pipe.h"
static GUID g[13];static LONG refs=1;static unsigned callbacks;
static int callback(void*ctx,const DmbMessage*q,DmbMessage*r){
 (void)ctx;callbacks++;r->status=0;memset(r->v,0,sizeof r->v);
 if(q->object!=1)return 0;
 switch(q->op){
 case 0:
  if(IsEqualGUID((GUID*)q->guid[0],&IID_IUnknown)||IsEqualGUID((GUID*)q->guid[0],&g[12])){r->v[0]=S_OK;r->v[1]=1;refs++;}
  else r->v[0]=(uint32_t)E_NOINTERFACE;break;
 case 1:r->v[0]=++refs;break;
 case 2:r->v[0]=--refs;break;
 case 3:r->v[0]=(uint32_t)E_NOTIMPL;break;
 case 4:r->v[0]=S_OK;r->v[1]=0x10;break;
 case 5:r->v[0]=S_OK;r->v[1]=2;break;
 case 6:if(q->v[0]!=2)return 0;r->v[0]=S_OK;r->v[1]=13;r->v[2]=14;break;
 default:return 0;
 }return 1;
}
static void result(const char*n,uint32_t value){printf("%s %08x\n",n,value);fflush(stdout);}
int wmain(int argc,WCHAR**argv){
 DmbConnection c;DmbMessage m;FILE*f;uint32_t loader=0,perf=0,sound=0,path=0,graph=0,container=0,script=0,identity;
 WCHAR folder[600];const WCHAR*mode=argc==5?L"session":argc==6?argv[5]:L"";unsigned i;ULONGLONG start;DWORD n,exitcode;
 if(argc!=5&&argc!=6)return 2;
 f=_wfopen(argv[4],L"rb");if(!f)return 2;if(fread(g,sizeof g,1,f)!=1){fclose(f);return 2;}fclose(f);
 if(!dmb_connect(&c,argv[1],argv[2],1,callback,NULL)){fprintf(stderr,"%s\n",c.error);return 3;}
 /* argv[3] is reserved for explicit protocol version selection. */
 if(wcscmp(argv[3],L"1"))return 2;
#define BEGIN(op,id) dmb_message(&m,op,id)
#define SEND(label) do{if(!dmb_exchange(&c,&m)){fprintf(stderr,"%s\n",c.error);return 4;}if(label)result(label,m.v[0]);}while(0)
#define CREATE(type,id,label) BEGIN(DMB_CREATE,0);m.v[0]=type;SEND(label);id=m.v[1];if(!id)return 5
 if(!wcscmp(mode,L"crash")||!wcscmp(mode,L"timeout")){
  c.timeout=150;BEGIN(!wcscmp(mode,L"crash")?DMB_TEST_CRASH:DMB_TEST_STALL,0);start=GetTickCount64();
  if(dmb_exchange(&c,&m)||GetTickCount64()-start>3000)return 6;
  printf("bounded failure %s\n",c.error);return 0;
 }
 if(!wcscmp(mode,L"malformed")||!wcscmp(mode,L"badsize")||!wcscmp(mode,L"badsequence")||!wcscmp(mode,L"badkind")||!wcscmp(mode,L"truncated")){
  BEGIN(DMB_HELLO,0);m.sequence=2;start=GetTickCount64();
  if(!wcscmp(mode,L"malformed"))m.version=99;
  if(!wcscmp(mode,L"badsize"))m.bytes=1999;
  if(!wcscmp(mode,L"badsequence"))m.sequence=1;
  if(!wcscmp(mode,L"badkind"))m.kind=DMB_REPLY;
  if(!wcscmp(mode,L"truncated")){
   if(!WriteFile(c.input,&m,100,&n,NULL))return 7;
   CloseHandle(c.input);c.input=NULL;if(WaitForSingleObject(c.process,2000)!=WAIT_OBJECT_0)return 7;
   dmb_disconnect(&c);puts("truncated frame disconnect bounded");return 0;
  }
  if(!WriteFile(c.input,&m,sizeof m,&n,NULL)||!dmb_read(&c,&m,start+1000)||m.status!=DMB_BAD_FRAME)return 7;
  dmb_disconnect(&c);puts("malformed rejected");return 0;
 }
 if(!wcscmp(mode,L"invalid")){
  BEGIN(DMB_RELEASE,9999);
  if(dmb_exchange(&c,&m))return 8;printf("explicit failure %s\n",c.error);return 0;
 }
 if(!wcscmp(mode,L"guard")){
  const WCHAR*paths[]={L"E:\\Launchbox\\Games\\PC Games\\Unreal 2 - The Awakening\\singleplayer\\Music\\M03_fite_loop2.ogg",L"..\\..\\..\\CURRENT_STATUS.md",L"..\\Music\\Intro.con",L"..\\Music\\Intro.con"};
  for(i=0;i<4;i++){BEGIN(DMB_TEST_OPEN,0);wcscpy((WCHAR*)m.text,paths[i]);m.v[0]=i==3?GENERIC_WRITE:GENERIC_READ;SEND(NULL);if(m.v[0]!=(uint32_t)(i==2))return 15;}
  BEGIN(DMB_SHUTDOWN,0);SEND(NULL);dmb_disconnect(&c);puts("disk guard verified");return 0;
 }
 if(!wcscmp(mode,L"session"))result("CoInitialize",S_OK);
 CREATE(DMB_LOADER,loader,!wcscmp(mode,L"session")?"Loader8":NULL);
 if(!wcscmp(mode,L"unsupported")){
  BEGIN(999,loader);if(dmb_exchange(&c,&m))return 8;printf("explicit failure %s\n",c.error);return 0;
 }
 if(!wcscmp(mode,L"disconnect")){
  CloseHandle(c.input);c.input=NULL;
  if(WaitForSingleObject(c.process,2000)!=WAIT_OBJECT_0)return 9;
  GetExitCodeProcess(c.process,&exitcode);dmb_disconnect(&c);printf("disconnect exit %lu\n",exitcode);return exitcode?10:0;
 }
 if(!wcscmp(mode,L"host-exit")){
  printf("child %lu\n",GetProcessId(c.process));fflush(stdout);ExitProcess(0);
 }
 if(!wcscmp(mode,L"lifetime")){
  BEGIN(DMB_QI,loader);memcpy(m.guid[0],&IID_IUnknown,16);SEND("QI.IUnknown");identity=m.v[1];if(identity!=loader)return 11;
  BEGIN(DMB_QI,loader);memcpy(m.guid[0],&g[1],16);SEND("QI.Loader8");if(m.v[1]!=loader)return 11;
  BEGIN(DMB_ADDREF,loader);SEND("AddRef");if(m.v[0]!=4)return 11;
  for(i=3;i;i--){BEGIN(DMB_RELEASE,loader);SEND("Release");if(m.v[0]!=i)return 11;}
  BEGIN(DMB_RELEASE,loader);SEND("Release.final");if(m.v[0])return 11;
  BEGIN(DMB_RELEASE,loader);if(dmb_exchange(&c,&m))return 11;puts("stale handle rejected");return 0;
 }
 if(wcscmp(mode,L"session")&&wcscmp(mode,L"routine-block")&&wcscmp(mode,L"processpmsg")&&wcscmp(mode,L"callback"))return 2;
 CREATE(DMB_PERFORMANCE,perf,"Performance8");
 BEGIN(DMB_INIT_AUDIO,perf);m.v[0]=8;m.v[1]=128;m.v[2]=0x3f;SEND("InitAudio");sound=m.v[1];
 swprintf(folder,600,L"%s\\Music",argv[2]);
 BEGIN(DMB_SEARCH,loader);memcpy(m.guid[0],&g[4],16);wcscpy((WCHAR*)m.text,folder);SEND("SetSearchDirectory");
 BEGIN(DMB_PATH,perf);SEND("GetDefaultAudioPath");path=m.v[1];
 BEGIN(DMB_GRAPH,path);m.v[1]=0x3200;memcpy(m.guid[0],&g[10],16);memcpy(m.guid[1],&g[11],16);SEND("GetObjectInPath.Graph");graph=m.v[1];
 BEGIN(DMB_INSERT,graph);m.v[0]=1;SEND("InsertTool");result("Tool.Release.local",--refs);
 BEGIN(DMB_RELEASE,graph);SEND("Graph.Release.local");
 BEGIN(DMB_LOAD,loader);memcpy(m.guid[0],&g[6],16);memcpy(m.guid[1],&g[7],16);wcscpy((WCHAR*)m.text,L"Intro.con");SEND("LoadObjectFromFile");container=m.v[1];
 BEGIN(DMB_SCRIPT,loader);*(DWORD*)m.data=848;*(DWORD*)(m.data+4)=0x206;memcpy(m.data+24,&g[8],16);memcpy(m.data+56,L"Script1",16);memcpy(m.guid[0],&g[9],16);SEND("GetObject.Script1");script=m.v[1];
 BEGIN(DMB_SCRIPT_INIT,script);m.v[0]=perf;SEND("Script.Init");
 if(!wcscmp(mode,L"routine-block")||!wcscmp(mode,L"processpmsg")||!wcscmp(mode,L"callback")){
  BEGIN(!wcscmp(mode,L"routine-block")?DMB_ROUTINE:!wcscmp(mode,L"processpmsg")?DMB_TEST_PROCESS:DMB_TEST_CALLBACK,script);
  if(!wcscmp(mode,L"routine-block"))wcscpy((WCHAR*)m.text,L"dmInit");
  if(dmb_exchange(&c,&m))return 16;printf("unexpected operation stopped: %s\n",c.error);return 0;
 }
 BEGIN(DMB_RELEASE_OBJECT,loader);m.v[0]=container;SEND("ReleaseObjectByUnknown.container");
 BEGIN(DMB_RELEASE,container);SEND("Container.Release");
 BEGIN(DMB_VOLUME,perf);memcpy(m.guid[0],&g[5],16);m.v[0]=(uint32_t)-706;m.v[1]=4;SEND("SetGlobalParam.Volume");
 for(i=0;i<128;i++){
  char name[1024];BEGIN(DMB_ENUM,script);m.v[0]=i;SEND(NULL);
  if(m.v[0]!=S_OK){result("EnumRoutine.end",m.v[0]);break;}
  WideCharToMultiByte(CP_UTF8,0,(WCHAR*)m.text,-1,name,sizeof name,NULL,NULL);printf("routine %s\n",name);
 }
 BEGIN(DMB_ROUTINE,script);SEND("CallRoutine.empty");if(m.v[0]!=0x8878121b)return 12;
 BEGIN(DMB_ROUTINE,script);wcscpy((WCHAR*)m.text,L"__xrt_missing_routine__");SEND("CallRoutine.missing");if(m.v[0]!=0x8878121b)return 12;
 BEGIN(DMB_RELEASE_OBJECT,loader);m.v[0]=script;SEND("ReleaseObjectByUnknown.script");
 BEGIN(DMB_RELEASE,script);SEND("Script.Release");
 BEGIN(DMB_STOP,perf);SEND("Stop");BEGIN(DMB_CLOSE,perf);SEND("CloseDown");
 BEGIN(DMB_RELEASE,perf);SEND("Performance.Release");
 BEGIN(DMB_RELEASE,path);SEND("AudioPath.Release");
 BEGIN(DMB_RELEASE,sound);SEND("DirectSound.Release");
 BEGIN(DMB_RELEASE,loader);SEND("Loader.Release");
 printf("tool refs %ld unsupported 0\n",refs);
 BEGIN(DMB_SHUTDOWN,0);SEND(NULL);puts("CoUninitialize balanced 1");
 if(WaitForSingleObject(c.process,2000)!=WAIT_OBJECT_0)return 13;
 dmb_disconnect(&c);return refs||callbacks<5?14:0;
}

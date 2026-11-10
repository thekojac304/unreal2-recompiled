/* Owned x86 probe (no game): does the intro music's own script track advance
 * Script1's TrackIndex (dmPlayNext at each segment's QUEUE-timed event)?
 * Same native objects and call sequence as the helper for the intro music.
 * usage: chain_probe <sandbox root> <seconds> [sleep|pump|mta|dispatch|parse] [manual]
 *   dispatch: run the helper's script-track fallback (script_track.h) on this STA.
 *   parse:    parse and bind the container's script-track events, then exit. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <string.h>
static IUnknown*probe_script;
#define ST_FAIL(m) (fprintf(stderr,"script-track FAIL: %s\n",(m)),fflush(NULL),ExitProcess(3))
#define ST_LOG(...) (printf(__VA_ARGS__),fflush(stdout))
#include "script_track.h"
static IUnknown*st_game_script(const GUID*script){GUID g;return probe_script&&st_object_guid(probe_script,&g)&&IsEqualGUID(&g,script)?probe_script:NULL;}
static const GUID iid_loader={0x19e7c08c,0x0a44,0x4e6a,{0xa1,0x16,0x59,0x5a,0x7c,0xd5,0xde,0x8c}};
static const GUID iid_perf={0x679c4137,0xc62e,0x4147,{0xb2,0xb4,0x9d,0x56,0x9a,0xcb,0x25,0x4c}};
static const GUID iid_container={0x9301e386,0x1f22,0x11d3,{0x82,0x26,0xd2,0xfa,0x76,0x25,0x5d,0x47}};
static const GUID cls_loader={0xd2ac2892,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID cls_perf={0xd2ac2881,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID cls_container={0x9301e380,0x1f22,0x11d3,{0x82,0x26,0xd2,0xfa,0x76,0x25,0x5d,0x47}};
static const GUID all_types={0xd2ac2893,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static void*method(IUnknown*p,unsigned slot){return (*(void***)p)[slot];}
typedef HRESULT(WINAPI*InitAudio)(IUnknown*,IUnknown**,IUnknown**,HWND,DWORD,DWORD,DWORD,void*);
typedef HRESULT(WINAPI*Search)(IUnknown*,REFGUID,WCHAR*,BOOL);
typedef HRESULT(WINAPI*LoadFile)(IUnknown*,REFGUID,REFIID,WCHAR*,void**);
typedef HRESULT(WINAPI*LoaderObject)(IUnknown*,void*,REFIID,void**);
typedef HRESULT(WINAPI*ScriptInit)(IUnknown*,IUnknown*,void*);
typedef HRESULT(WINAPI*Routine)(IUnknown*,WCHAR*,void*);
typedef HRESULT(WINAPI*GetVarNum)(IUnknown*,WCHAR*,LONG*,void*);
typedef HRESULT(WINAPI*GetTimeFn)(IUnknown*,LONGLONG*,LONG*);
int wmain(int argc,WCHAR**argv){
 IUnknown*loader,*perf,*cont,*script;WCHAR folder[600],path[700];BYTE desc[848]={0};HRESULT hr;LONG v,last=-2,mt;LONGLONG rt;
 ULONGLONG begin,end,tick=0;const WCHAR*mode=argc>3?argv[3]:L"sleep";
 int pump=!wcscmp(mode,L"pump"),mta=!wcscmp(mode,L"mta"),dispatch=!wcscmp(mode,L"dispatch"),parse=!wcscmp(mode,L"parse");
 if(argc<3)return 2;
 hr=CoInitializeEx(NULL,mta?COINIT_MULTITHREADED:COINIT_APARTMENTTHREADED);printf("CoInitializeEx(%s) %08lx\n",mta?"MTA":"STA",hr);
 hr=CoCreateInstance(&cls_loader,NULL,3,&iid_loader,(void**)&loader);printf("loader %08lx\n",hr);if(FAILED(hr))return 1;
 hr=CoCreateInstance(&cls_perf,NULL,3,&iid_perf,(void**)&perf);printf("performance %08lx\n",hr);if(FAILED(hr))return 1;
 hr=((InitAudio)method(perf,44))(perf,NULL,NULL,NULL,8,128,0x3f,NULL);printf("InitAudio %08lx\n",hr);
 swprintf(folder,600,L"%s\\Music",argv[1]);swprintf(path,700,L"%s\\Intro.con",folder);
 hr=((Search)method(loader,5))(loader,&all_types,folder,FALSE);printf("SetSearchDirectory %08lx\n",hr);
 hr=((LoadFile)method(loader,14))(loader,&cls_container,&iid_container,L"Intro.con",(void**)&cont);printf("container %08lx\n",hr);
 if(dispatch||parse){st_load(path);st_bind(loader);if(parse)ExitProcess(0);}
 *(DWORD*)desc=848;*(DWORD*)(desc+4)=0x206;memcpy(desc+24,&st_cls_script,16);memcpy(desc+56,L"Script1",16);
 hr=((LoaderObject)method(loader,3))(loader,desc,&st_iid_script8,(void**)&script);printf("Script1 %08lx\n",hr);if(FAILED(hr))return 1;
 probe_script=script;
 hr=((ScriptInit)method(script,3))(script,perf,NULL);printf("Script Init %08lx\n",hr);
 if(dispatch){/* As the game does: drop the loader cache entries after obtaining them. */
  typedef HRESULT(WINAPI*Rel)(IUnknown*,IUnknown*);
  printf("ReleaseObject script %08lx container %08lx\n",((Rel)method(loader,13))(loader,script),((Rel)method(loader,13))(loader,cont));}
 hr=((Routine)method(script,4))(script,L"a001_Start",NULL);printf("a001_Start %08lx\n",hr);
 begin=GetTickCount64();end=begin+1000ull*_wtoi(argv[2]);
 while(GetTickCount64()<end){MSG m;unsigned n=0;ULONGLONG now=GetTickCount64();
  if(pump)while(PeekMessageW(&m,NULL,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);n++;}
  if(dispatch)st_tick(perf);
  if(now>=tick){tick=now+250;
   v=-1;hr=((GetVarNum)method(script,8))(script,L"TrackIndex",&v,NULL);
   ((GetTimeFn)method(perf,15))(perf,&rt,&mt);
   if(v!=last||n){printf("t=%.1fs mt=%ld TrackIndex=%ld (hr %08lx) messages=%u\n",(now-begin)/1000.0,mt,v,hr,n);last=v;}
   {static int done;if(argc>4&&!done&&now>=begin+5000){done=1;hr=((Routine)method(script,4))(script,L"dmPlayNext",NULL);printf("manual dmPlayNext %08lx\n",hr);}}
  }
  if(pump)MsgWaitForMultipleObjects(0,NULL,FALSE,5,QS_ALLINPUT);else Sleep(5);
 }
 printf("final TrackIndex=%ld dispatches=%u\n",last,st_dispatches);fflush(stdout);
 ExitProcess(0); /* skip teardown: probe only */
}

/* Owned x86 probe (no game): does the intro music's own script track advance
 * Script1's TrackIndex (dmPlayNext at each segment's QUEUE-timed event)?
 * Same native objects and call sequence as the helper for the intro music.
 * usage: chain_probe <sandbox root> <seconds> [pump|sleep|mta] [manual] */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <string.h>
static const GUID iid_loader={0x19e7c08c,0x0a44,0x4e6a,{0xa1,0x16,0x59,0x5a,0x7c,0xd5,0xde,0x8c}};
static const GUID iid_perf={0x679c4137,0xc62e,0x4147,{0xb2,0xb4,0x9d,0x56,0x9a,0xcb,0x25,0x4c}};
static const GUID iid_container={0x9301e386,0x1f22,0x11d3,{0x82,0x26,0xd2,0xfa,0x76,0x25,0x5d,0x47}};
static const GUID iid_script={0x2252373a,0x5814,0x489b,{0x82,9,0x31,0xfe,0xde,0xba,0xf1,0x37}};
static const GUID cls_loader={0xd2ac2892,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID cls_perf={0xd2ac2881,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID cls_container={0x9301e380,0x1f22,0x11d3,{0x82,0x26,0xd2,0xfa,0x76,0x25,0x5d,0x47}};
static const GUID cls_script={0x810b5013,0xe88d,0x11d2,{0x8b,0xc1,0,0x60,8,0x93,0xb1,0xb6}};
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
 IUnknown*loader,*perf,*cont,*script;WCHAR folder[600];BYTE desc[848]={0};HRESULT hr;LONG v,last=-2,mt;LONGLONG rt;
 ULONGLONG end;int pump=argc>3&&!wcscmp(argv[3],L"pump"),mta=argc>3&&!wcscmp(argv[3],L"mta");
 if(argc<3)return 2;
 hr=CoInitializeEx(NULL,mta?COINIT_MULTITHREADED:COINIT_APARTMENTTHREADED);printf("CoInitializeEx(%s) %08lx\n",mta?"MTA":"STA",hr);
 hr=CoCreateInstance(&cls_loader,NULL,3,&iid_loader,(void**)&loader);printf("loader %08lx\n",hr);if(FAILED(hr))return 1;
 hr=CoCreateInstance(&cls_perf,NULL,3,&iid_perf,(void**)&perf);printf("performance %08lx\n",hr);if(FAILED(hr))return 1;
 hr=((InitAudio)method(perf,44))(perf,NULL,NULL,NULL,8,128,0x3f,NULL);printf("InitAudio %08lx\n",hr);
 swprintf(folder,600,L"%s\\Music",argv[1]);
 hr=((Search)method(loader,5))(loader,&all_types,folder,FALSE);printf("SetSearchDirectory %08lx\n",hr);
 hr=((LoadFile)method(loader,14))(loader,&cls_container,&iid_container,L"Intro.con",(void**)&cont);printf("container %08lx\n",hr);
 *(DWORD*)desc=848;*(DWORD*)(desc+4)=0x206;memcpy(desc+24,&cls_script,16);memcpy(desc+56,L"Script1",16);
 hr=((LoaderObject)method(loader,3))(loader,desc,&iid_script,(void**)&script);printf("Script1 %08lx\n",hr);if(FAILED(hr))return 1;
 hr=((ScriptInit)method(script,3))(script,perf,NULL);printf("Script Init %08lx\n",hr);
 hr=((Routine)method(script,4))(script,L"a001_Start",NULL);printf("a001_Start %08lx\n",hr);
 end=GetTickCount64()+1000ull*_wtoi(argv[2]);
 while(GetTickCount64()<end){MSG m;unsigned n=0;
  if(pump)while(PeekMessageW(&m,NULL,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);n++;}
  v=-1;hr=((GetVarNum)method(script,8))(script,L"TrackIndex",&v,NULL);
  ((GetTimeFn)method(perf,15))(perf,&rt,&mt);
  if(v!=last||n){printf("t=%llus mt=%ld TrackIndex=%ld (hr %08lx) messages=%u\n",(GetTickCount64()+1000ull*_wtoi(argv[2])-end)/1000,mt,v,hr,n);last=v;}
  {static int done;if(argc>4&&!done&&GetTickCount64()+1000ull*(_wtoi(argv[2])-5)>=end){done=1;hr=((Routine)method(script,4))(script,L"dmPlayNext",NULL);printf("manual dmPlayNext %08lx\n",hr);}}
  if(pump)MsgWaitForMultipleObjects(0,NULL,FALSE,250,QS_ALLINPUT);else Sleep(250);
 }
 printf("final TrackIndex=%ld\n",last);fflush(stdout);
 ExitProcess(0); /* skip teardown: probe only */
}

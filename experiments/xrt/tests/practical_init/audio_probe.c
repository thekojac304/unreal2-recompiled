/* Owned PE32 client: the captured startup InitAudio tuple, no game code. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
__declspec(dllexport) int probe_log[1024],probe_log_n;
static void logv(int v){probe_log[probe_log_n++]=v;}
static const GUID cls={0xd2ac2881,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID iid={0x679c4137,0xc62e,0x4147,{0xb2,0xb4,0x9d,0x56,0x9a,0xcb,0x25,0x4c}};
typedef HRESULT(WINAPI*Audio)(IUnknown*,IUnknown**,IUnknown**,HWND,DWORD,DWORD,DWORD,void*);
typedef HRESULT(WINAPI*Close)(IUnknown*);
#include "tool_guids.h"
typedef struct Tool Tool;
typedef struct ToolTable {
 HRESULT(WINAPI*qi)(Tool*,REFIID,void**);ULONG(WINAPI*add)(Tool*);ULONG(WINAPI*release)(Tool*);
 HRESULT(WINAPI*init)(Tool*,IUnknown*);HRESULT(WINAPI*delivery)(Tool*,DWORD*);
 HRESULT(WINAPI*count)(Tool*,DWORD*);HRESULT(WINAPI*types)(Tool*,DWORD**,DWORD);
 HRESULT(WINAPI*message)(Tool*,IUnknown*,void*);HRESULT(WINAPI*flush)(Tool*,IUnknown*,void*,LONGLONG);
} ToolTable;
struct Tool {const ToolTable*vt;LONG refs;};
static HRESULT WINAPI tool_qi(Tool*t,REFIID g,void**out){
 logv(100);*out=NULL;
 if(IsEqualGUID(g,&IID_IUnknown)||IsEqualGUID(g,&tool_guid)){*out=t;t->refs++;return S_OK;}
 return E_NOINTERFACE;
}
static ULONG WINAPI tool_add(Tool*t){logv(101);return ++t->refs;}
static ULONG WINAPI tool_release(Tool*t){logv(102);return --t->refs;}
static HRESULT WINAPI tool_init(Tool*t,IUnknown*g){logv(103);return E_NOTIMPL;}
static HRESULT WINAPI tool_delivery(Tool*t,DWORD*p){logv(104);*p=0x10;return S_OK;}
static HRESULT WINAPI tool_count(Tool*t,DWORD*p){logv(105);*p=2;return S_OK;}
static HRESULT WINAPI tool_types(Tool*t,DWORD**p,DWORD n){logv(106);if(n!=2)return E_FAIL;(*p)[0]=13;(*p)[1]=14;return S_OK;}
static HRESULT WINAPI tool_message(Tool*t,IUnknown*p,void*m){logv(107);return E_NOTIMPL;}
static HRESULT WINAPI tool_flush(Tool*t,IUnknown*p,void*m,LONGLONG when){logv(108);return E_NOTIMPL;}
static const ToolTable tool_table={tool_qi,tool_add,tool_release,tool_init,tool_delivery,tool_count,tool_types,tool_message,tool_flush};
static IUnknown*create(void){IUnknown*p=NULL;CoInitialize(NULL);logv(CoCreateInstance(&cls,NULL,3,&iid,(void**)&p));logv(p!=NULL);return p;}
__declspec(dllexport) int probe_audio(void){
 IUnknown*p,*sound=NULL;HRESULT hr;probe_log_n=0;p=create();if(!p)return 1;
 hr=((Audio)(*(void***)p)[44])(p,NULL,&sound,NULL,8,128,63,NULL);logv(hr);logv(sound!=NULL);
 if(FAILED(hr)||!sound)return 2;
 logv(((Close)(*(void***)p)[38])(p));IUnknown_Release(p);IUnknown_Release(sound);CoUninitialize();return 0;
}
__declspec(dllexport) int probe_bad_audio(void){
 IUnknown*p,*sound=NULL;probe_log_n=0;p=create();if(!p)return 1;
 return ((Audio)(*(void***)p)[44])(p,(IUnknown**)1,&sound,NULL,8,128,63,NULL);
}
__declspec(dllexport) int probe_audio_unsupported(void){
 IUnknown*p;probe_log_n=0;p=create();if(!p)return 1;
 return ((Close)(*(void***)p)[3])(p);
}
static int run_tool(int script){
 typedef HRESULT(WINAPI*Out)(IUnknown*,IUnknown**);
 typedef HRESULT(WINAPI*Graph)(IUnknown*,DWORD,DWORD,DWORD,REFGUID,DWORD,REFIID,void**);
 typedef HRESULT(WINAPI*Insert)(IUnknown*,IUnknown*,DWORD*,DWORD,LONG);
 IUnknown*p,*sound=NULL,*path=NULL,*graph=NULL,*loader=NULL,*container=NULL,*code=NULL;HRESULT hr;Tool tool={&tool_table,1};
 probe_log_n=0;p=create();if(!p)return 1;
 hr=((Audio)(*(void***)p)[44])(p,NULL,&sound,NULL,8,128,63,NULL);logv(hr);if(FAILED(hr))return 2;
 hr=((Out)(*(void***)p)[51])(p,&path);logv(hr);if(FAILED(hr))return 3;
 hr=((Graph)(*(void***)path)[3])(path,0,0x3200,0,&GUID_NULL,0,&graph_guid,(void**)&graph);logv(hr);if(FAILED(hr))return 4;
 hr=((Insert)(*(void***)graph)[4])(graph,(IUnknown*)&tool,NULL,0,0);logv(hr);if(FAILED(hr))return 5;
 tool_release(&tool);IUnknown_Release(graph);
 if(script){
  typedef HRESULT(WINAPI*Search)(IUnknown*,REFGUID,WCHAR*,BOOL);
  typedef HRESULT(WINAPI*Load)(IUnknown*,REFGUID,REFIID,WCHAR*,void**);
  typedef HRESULT(WINAPI*Get)(IUnknown*,void*,REFIID,void**);
  typedef HRESULT(WINAPI*Init)(IUnknown*,IUnknown*,void*);
  typedef HRESULT(WINAPI*Routine)(IUnknown*,WCHAR*,void*);
  typedef HRESULT(WINAPI*Drop)(IUnknown*,IUnknown*);
#define CHECK_SCRIPT(expr) do{hr=(expr);logv(hr);if(FAILED(hr))return 8;}while(0)
  CHECK_SCRIPT(CoCreateInstance(&loader_class,NULL,3,&loader_guid,(void**)&loader));
  CHECK_SCRIPT(((Search)(*(void***)loader)[5])(loader,&alltypes_guid,music_folder,FALSE));
  CHECK_SCRIPT(((Load)(*(void***)loader)[14])(loader,&container_class,&container_guid,L"Intro.con",(void**)&container));
  CHECK_SCRIPT(((Get)(*(void***)loader)[3])(loader,script_descriptor,&script_guid,(void**)&code));
  CHECK_SCRIPT(((Init)(*(void***)code)[3])(code,p,NULL));
  hr=((Routine)(*(void***)code)[4])(code,L"",NULL);logv(hr);if(hr!=(HRESULT)0x8878121b)return 9;
  CHECK_SCRIPT(((Drop)(*(void***)loader)[13])(loader,container));IUnknown_Release(container);
  CHECK_SCRIPT(((Drop)(*(void***)loader)[13])(loader,code));IUnknown_Release(code);IUnknown_Release(loader);
 }
 logv(((Close)(*(void***)p)[38])(p));IUnknown_Release(p);IUnknown_Release(path);IUnknown_Release(sound);
 logv(tool.refs);CoUninitialize();return tool.refs?6:0;
}
__declspec(dllexport) int probe_tool(void){return run_tool(0);}
__declspec(dllexport) int probe_script(void){return run_tool(1);}

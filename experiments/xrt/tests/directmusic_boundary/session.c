/* Focused native DirectMusic session. GUID operands come from the isolated game
 * image. No registration, installation changes, synthetic interfaces or success
 * fallbacks. This is an oracle/helper feasibility experiment, not a game backend. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <string.h>
static GUID g[13];
static void result(const char*name,HRESULT hr){printf("%s %08lx\n",name,(unsigned long)hr);fflush(stdout);}
static void*method(IUnknown*p,unsigned slot){return (*(void***)p)[slot];}
typedef HRESULT(WINAPI*InitAudio)(IUnknown*,IUnknown**,IUnknown**,HWND,DWORD,DWORD,DWORD,void*);
typedef HRESULT(WINAPI*Search)(IUnknown*,REFGUID,WCHAR*,BOOL);
typedef HRESULT(WINAPI*Out)(IUnknown*,IUnknown**);
typedef HRESULT(WINAPI*InPath)(IUnknown*,DWORD,DWORD,DWORD,REFGUID,DWORD,REFIID,void**);
typedef HRESULT(WINAPI*Insert)(IUnknown*,IUnknown*,DWORD*,DWORD,LONG);
typedef HRESULT(WINAPI*LoadFile)(IUnknown*,REFGUID,REFIID,WCHAR*,void**);
typedef HRESULT(WINAPI*LoaderGetObject)(IUnknown*,void*,REFIID,void**);
typedef HRESULT(WINAPI*ScriptInit)(IUnknown*,IUnknown*,void*);
typedef HRESULT(WINAPI*Routine)(IUnknown*,WCHAR*,void*);
typedef HRESULT(WINAPI*EnumRoutine)(IUnknown*,DWORD,WCHAR*);
typedef HRESULT(WINAPI*Global)(IUnknown*,REFGUID,void*,DWORD);
typedef HRESULT(WINAPI*ReleaseObject)(IUnknown*,IUnknown*);
typedef HRESULT(WINAPI*Stop)(IUnknown*,IUnknown*,IUnknown*,LONG,DWORD);
typedef HRESULT(WINAPI*CloseDown)(IUnknown*);
typedef struct Tool Tool;
typedef struct {
    HRESULT(WINAPI*qi)(Tool*,REFIID,void**);
    ULONG(WINAPI*add)(Tool*);ULONG(WINAPI*release)(Tool*);
    HRESULT(WINAPI*init)(Tool*,IUnknown*);
    HRESULT(WINAPI*delivery)(Tool*,DWORD*);HRESULT(WINAPI*count)(Tool*,DWORD*);
    HRESULT(WINAPI*types)(Tool*,DWORD**,DWORD);
    HRESULT(WINAPI*message)(Tool*,IUnknown*,void*);
    HRESULT(WINAPI*flush)(Tool*,IUnknown*,void*,LONGLONG);
} ToolVtbl;
struct Tool {const ToolVtbl*vt;LONG refs;LONG unsupported;};
static HRESULT WINAPI tool_qi(Tool*t,REFIID iid,void**out){
    if(IsEqualGUID(iid,&IID_IUnknown) || IsEqualGUID(iid,&g[12])){*out=t;InterlockedIncrement(&t->refs);return S_OK;}
    *out=NULL;return E_NOINTERFACE;
}
static ULONG WINAPI tool_add(Tool*t){return InterlockedIncrement(&t->refs);}
static ULONG WINAPI tool_release(Tool*t){return InterlockedDecrement(&t->refs);}
static HRESULT WINAPI tool_init(Tool*t,IUnknown*graph){(void)t;(void)graph;return E_NOTIMPL;}
static HRESULT WINAPI tool_delivery(Tool*t,DWORD*p){(void)t;*p=0x10;return S_OK;}
static HRESULT WINAPI tool_count(Tool*t,DWORD*p){(void)t;*p=2;return S_OK;}
static HRESULT WINAPI tool_types(Tool*t,DWORD**p,DWORD n){(void)t;if(n!=2)return E_FAIL;(*p)[0]=13;(*p)[1]=14;return S_OK;}
static HRESULT WINAPI tool_message(Tool*t,IUnknown*perf,void*p){(void)perf;(void)p;InterlockedIncrement(&t->unsupported);result("UNSUPPORTED.Tool.ProcessPMsg",E_NOTIMPL);return E_NOTIMPL;}
static HRESULT WINAPI tool_flush(Tool*t,IUnknown*perf,void*p,LONGLONG time){(void)t;(void)perf;(void)p;(void)time;return E_NOTIMPL;}
static const ToolVtbl tool_vt={tool_qi,tool_add,tool_release,tool_init,tool_delivery,tool_count,tool_types,tool_message,tool_flush};
int main(int argc,char**argv){
    FILE*f;HRESULT hr;IUnknown*loader=NULL,*perf=NULL,*sound=NULL,*path=NULL,*graph=NULL,*container=NULL,*script=NULL;
    WCHAR folder[520],name[256];BYTE desc[0x350]={0};LONG volume=-706;unsigned i;Tool tool={&tool_vt,1,0};int status=0;
    if(argc!=3)return 2;f=fopen(argv[1],"rb");if(!f)return 2;
    if(fread(g,sizeof g,1,f)!=1){fclose(f);return 2;}fclose(f);
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,argv[2],-1,folder,520))return 2;
    hr=CoInitialize(NULL);result("CoInitialize",hr);if(FAILED(hr))return 3;
#define CHECK(label,expr) do{hr=(expr);result(label,hr);if(FAILED(hr)){status=4;goto done;}}while(0)
    CHECK("Loader8",CoCreateInstance(&g[0],NULL,3,&g[1],(void**)&loader));
    CHECK("Performance8",CoCreateInstance(&g[2],NULL,3,&g[3],(void**)&perf));
    CHECK("InitAudio",((InitAudio)method(perf,44))(perf,NULL,&sound,NULL,8,128,0x3f,NULL));
    CHECK("SetSearchDirectory",((Search)method(loader,5))(loader,&g[4],folder,FALSE));
    CHECK("GetDefaultAudioPath",((Out)method(perf,51))(perf,&path));
    CHECK("GetObjectInPath.Graph",((InPath)method(path,3))(path,0,0x3200,0,&GUID_NULL,0,&g[11],(void**)&graph));
    CHECK("InsertTool",((Insert)method(graph,4))(graph,(IUnknown*)&tool,NULL,0,0));
    result("Tool.Release.local",tool_release(&tool));
    result("Graph.Release.local",IUnknown_Release(graph));graph=NULL;
    CHECK("LoadObjectFromFile",((LoadFile)method(loader,14))(loader,&g[6],&g[7],L"Intro.con",(void**)&container));
    *(DWORD*)desc=sizeof desc;*(DWORD*)(desc+4)=0x206;memcpy(desc+24,&g[8],16);memcpy(desc+56,L"Script1",16);
    CHECK("GetObject.Script1",((LoaderGetObject)method(loader,3))(loader,desc,&g[9],(void**)&script));
    CHECK("Script.Init",((ScriptInit)method(script,3))(script,perf,NULL));
    CHECK("ReleaseObjectByUnknown.container",((ReleaseObject)method(loader,13))(loader,container));
    result("Container.Release",IUnknown_Release(container));container=NULL;
    CHECK("SetGlobalParam.Volume",((Global)method(perf,34))(perf,&g[5],&volume,4));
    /* Native enumeration measures the source-derived independent name oracle.
     * No present routine is invoked and no playback is requested by this probe. */
    for(i=0;i<128;i++){
        char utf8[1024];memset(name,0,sizeof name);
        hr=((EnumRoutine)method(script,11))(script,i,name);
        if(hr!=S_OK){result("EnumRoutine.end",hr);break;}
        WideCharToMultiByte(CP_UTF8,0,name,-1,utf8,sizeof utf8,NULL,NULL);printf("routine %s\n",utf8);
    }
    if(i==128){status=5;goto done;}
    hr=((Routine)method(script,4))(script,L"",NULL);result("CallRoutine.empty",hr);if(hr!=(HRESULT)0x8878121b)status=6;
    hr=((Routine)method(script,4))(script,L"__xrt_missing_routine__",NULL);result("CallRoutine.missing",hr);if(hr!=(HRESULT)0x8878121b)status=6;
done:
    if(container)IUnknown_Release(container);
    if(script){result("ReleaseObjectByUnknown.script",((ReleaseObject)method(loader,13))(loader,script));result("Script.Release",IUnknown_Release(script));}
    if(perf){result("Stop",((Stop)method(perf,5))(perf,NULL,NULL,0,0));result("CloseDown",((CloseDown)method(perf,38))(perf));result("Performance.Release",IUnknown_Release(perf));}
    if(path)result("AudioPath.Release",IUnknown_Release(path));
    if(graph)IUnknown_Release(graph);
    if(sound)result("DirectSound.Release",IUnknown_Release(sound));
    if(loader)result("Loader.Release",IUnknown_Release(loader));
    printf("tool refs %ld unsupported %ld\n",tool.refs,tool.unsupported);if(tool.unsupported)status=7;
    CoUninitialize();puts("CoUninitialize balanced 1");return status;
}

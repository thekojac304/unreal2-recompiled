/* Project-owned x86 DirectMusic backend. Every native COM call runs on this
 * process's main STA. Only measured methods are dispatchable. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "../runtime/dmusic_backend.h"
#include "file_guard.h"
static const GUID ids[]={
 {0},
 {0x19e7c08c,0x0a44,0x4e6a,{0xa1,0x16,0x59,0x5a,0x7c,0xd5,0xde,0x8c}},
 {0x679c4137,0xc62e,0x4147,{0xb2,0xb4,0x9d,0x56,0x9a,0xcb,0x25,0x4c}},
 {0x279afa83,0x4981,0x11ce,{0xa5,0x21,0,0x20,0xaf,0xb,0xe5,0x60}},
 {0xc87631f5,0x23be,0x4986,{0x88,0x36,5,0x83,0x2f,0xcc,0x48,0xf9}},
 {0x2befc277,0x5497,0x11d2,{0xbc,0xcb,0,0xa0,0xc9,0x22,0xe6,0xeb}},
 {0x9301e386,0x1f22,0x11d3,{0x82,0x26,0xd2,0xfa,0x76,0x25,0x5d,0x47}},
 {0x2252373a,0x5814,0x489b,{0x82,9,0x31,0xfe,0xde,0xba,0xf1,0x37}}
};
static const GUID cls_loader={0xd2ac2892,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID cls_perf={0xd2ac2881,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID cls_container={0x9301e380,0x1f22,0x11d3,{0x82,0x26,0xd2,0xfa,0x76,0x25,0x5d,0x47}};
static const GUID cls_script={0x810b5013,0xe88d,0x11d2,{0x8b,0xc1,0,0x60,8,0x93,0xb1,0xb6}};
static const GUID all_types={0xd2ac2893,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID volume_guid={0xd2ac28b1,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
typedef struct {IUnknown*p,*identity;uint32_t type,refs;} Object;
static Object objects[128];static unsigned used;
static HANDLE input,output;static DWORD owner;static uint32_t sequence;static int testing,disconnected;
static WCHAR sandbox[600];
static __declspec(noreturn) void die(const char*reason){fprintf(stderr,"DirectMusic helper fatal: %s\n",reason);fflush(stderr);ExitProcess(80);}
static int read_frame(DmbMessage*m){DWORD n,total=0;while(total<sizeof *m){if(!ReadFile(input,(BYTE*)m+total,sizeof *m-total,&n,NULL)||!n)return 0;total+=n;}return 1;}
static int write_frame(DmbMessage*m){DWORD n;return WriteFile(output,m,sizeof *m,&n,NULL)&&n==sizeof *m;}
static int valid(DmbMessage*m){return m->magic==DMB_MAGIC&&m->version==DMB_VERSION&&m->bytes==sizeof *m;}
static Object*get(uint32_t id,uint32_t type){if(!id||id>used||!objects[id-1].refs||(type&&objects[id-1].type!=type))return NULL;return &objects[id-1];}
static void*method(IUnknown*p,unsigned slot){return (*(void***)p)[slot];}
static uint32_t wrap(IUnknown*p,uint32_t type){
 IUnknown*identity=NULL;unsigned i;if(!p)return 0;
 if(FAILED(IUnknown_QueryInterface(p,&IID_IUnknown,(void**)&identity))||!identity)die("native identity query failed");
 IUnknown_Release(identity);
 for(i=0;i<used;i++)if(objects[i].refs&&objects[i].identity==identity&&objects[i].type==type){if(objects[i].p!=p)die("unmeasured interface alias");objects[i].refs++;return i+1;}
 if(used==128)die("object limit");objects[used].p=p;objects[used].identity=identity;objects[used].type=type;objects[used].refs=1;return ++used;
}
typedef struct Tool Tool;
typedef struct {
 HRESULT(WINAPI*qi)(Tool*,REFIID,void**);ULONG(WINAPI*add)(Tool*);ULONG(WINAPI*release)(Tool*);
 HRESULT(WINAPI*init)(Tool*,IUnknown*);HRESULT(WINAPI*delivery)(Tool*,DWORD*);HRESULT(WINAPI*count)(Tool*,DWORD*);
 HRESULT(WINAPI*types)(Tool*,DWORD**,DWORD);HRESULT(WINAPI*message)(Tool*,IUnknown*,void*);HRESULT(WINAPI*flush)(Tool*,IUnknown*,void*,LONGLONG);
} ToolVtbl;
struct Tool {const ToolVtbl*vt;uint32_t token,graph;LONG refs;};static Tool tools[8];static unsigned tool_count;
static DmbMessage tool_callback(Tool*t,unsigned slot,const GUID*iid,uint32_t n){
 DmbMessage m,r;
 if(GetCurrentThreadId()!=owner)die("tool callback outside STA");
 dmb_message(&m,slot,t->token);m.kind=DMB_CALLBACK;m.sequence=sequence;m.v[0]=n;
 if(iid)memcpy(m.guid[0],iid,16);
 if(disconnected){m.v[0]=0;return m;}
 if(!sequence)die("callback outside active request");
 if(!write_frame(&m)||!read_frame(&r)){disconnected=1;die("host disconnected during callback");}
 if(!valid(&r)||r.sequence!=sequence||r.kind!=DMB_CALLBACK_REPLY||r.op!=slot||r.object!=t->token||r.status)die("invalid callback reply");
 fprintf(stderr,"tool callback %u result %08x values %u %u\n",slot,r.v[0],r.v[1],r.v[2]);return r;
}
static HRESULT WINAPI tool_qi(Tool*t,REFIID iid,void**p){DmbMessage m=tool_callback(t,0,iid,0);*p=NULL;if(SUCCEEDED((HRESULT)m.v[0])){if(m.v[1]!=t->token)die("tool QI identity");t->refs++;*p=t;}return m.v[0];}
static ULONG WINAPI tool_add(Tool*t){DmbMessage m=tool_callback(t,1,NULL,0);t->refs++;return m.v[0];}
static ULONG WINAPI tool_release(Tool*t){DmbMessage m;if(t->refs<=0)die("tool reference underflow");m=tool_callback(t,2,NULL,0);t->refs--;return m.v[0];}
static HRESULT WINAPI tool_init(Tool*t,IUnknown*g){DmbMessage m;Object*o=get(t->graph,DMB_TOOLGRAPH);if(!o||o->p!=g)die("tool graph identity");m=tool_callback(t,3,NULL,t->graph);return m.v[0];}
static HRESULT WINAPI tool_delivery(Tool*t,DWORD*p){DmbMessage m=tool_callback(t,4,NULL,0);*p=m.v[1];return m.v[0];}
static HRESULT WINAPI tool_count_fn(Tool*t,DWORD*p){DmbMessage m=tool_callback(t,5,NULL,0);*p=m.v[1];return m.v[0];}
static HRESULT WINAPI tool_types(Tool*t,DWORD**p,DWORD n){DmbMessage m;if(n!=2||!p||!*p)die("unexpected tool media buffer");m=tool_callback(t,6,NULL,n);(*p)[0]=m.v[1];(*p)[1]=m.v[2];return m.v[0];}
static HRESULT WINAPI tool_message(Tool*t,IUnknown*p,void*m){(void)t;(void)p;(void)m;die("unsupported Tool.ProcessPMsg");}
static HRESULT WINAPI tool_flush(Tool*t,IUnknown*p,void*m,LONGLONG time){(void)t;(void)p;(void)m;(void)time;die("unsupported Tool.Flush");}
static const ToolVtbl tool_vt={tool_qi,tool_add,tool_release,tool_init,tool_delivery,tool_count_fn,tool_types,tool_message,tool_flush};
typedef HRESULT(WINAPI*InitAudio)(IUnknown*,IUnknown**,IUnknown**,HWND,DWORD,DWORD,DWORD,void*);
typedef HRESULT(WINAPI*Search)(IUnknown*,REFGUID,WCHAR*,BOOL);
typedef HRESULT(WINAPI*Out)(IUnknown*,IUnknown**);
typedef HRESULT(WINAPI*InPath)(IUnknown*,DWORD,DWORD,DWORD,REFGUID,DWORD,REFIID,void**);
typedef HRESULT(WINAPI*Insert)(IUnknown*,IUnknown*,DWORD*,DWORD,LONG);
typedef HRESULT(WINAPI*LoadFile)(IUnknown*,REFGUID,REFIID,WCHAR*,void**);
typedef HRESULT(WINAPI*LoaderObject)(IUnknown*,void*,REFIID,void**);
typedef HRESULT(WINAPI*ScriptInit)(IUnknown*,IUnknown*,void*);
typedef HRESULT(WINAPI*Routine)(IUnknown*,WCHAR*,void*);
typedef HRESULT(WINAPI*EnumRoutine)(IUnknown*,DWORD,WCHAR*);
typedef HRESULT(WINAPI*Global)(IUnknown*,REFGUID,void*,DWORD);
typedef HRESULT(WINAPI*ReleaseObject)(IUnknown*,IUnknown*);
typedef HRESULT(WINAPI*Stop)(IUnknown*,IUnknown*,IUnknown*,LONG,DWORD);
typedef HRESULT(WINAPI*CloseDown)(IUnknown*);
static void dispatch(DmbMessage*q,DmbMessage*r){
 Object*o=NULL,*other;IUnknown*p=NULL;HRESULT hr=E_NOTIMPL;uint32_t type=0;WCHAR folder[600];unsigned i;
 *r=*q;r->kind=DMB_REPLY;memset(r->v,0,sizeof r->v);memset(r->text,0,sizeof r->text);
 if(q->op==DMB_HELLO){r->v[0]=32;r->v[1]=sizeof *q;return;}
 if(q->op==DMB_TEST_CRASH&&testing)ExitProcess(93);
 if(q->op==DMB_TEST_STALL&&testing){Sleep(60000);return;}
 if(q->op==DMB_TEST_OPEN&&testing){HANDLE h=CreateFileW((WCHAR*)q->text,q->v[0],FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);r->v[0]=h!=INVALID_HANDLE_VALUE;r->v[1]=GetLastError();if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);return;}
 if(q->op==DMB_TEST_PROCESS&&testing&&tool_count)tool_message(&tools[0],NULL,NULL);
 if(q->op==DMB_TEST_CALLBACK&&testing&&tool_count){tool_callback(&tools[0],7,NULL,0);return;}
 if(q->op==DMB_SHUTDOWN){
  /* Release bridge-owned references in reverse acquisition order; native cached
   * references remain native-owned. CloseDown is never synthesized here. */
  for(i=used;i;i--)while(objects[i-1].refs){IUnknown_Release(objects[i-1].p);objects[i-1].refs--;}
  r->v[0]=S_OK;return;
 }
 if(q->op!=DMB_CREATE){o=get(q->object,0);if(!o){r->status=DMB_BAD_HANDLE;return;}}
#define REQUIRE(t) if(o->type!=(t)){r->status=DMB_BAD_HANDLE;return;}
 switch(q->op){
 case DMB_CREATE:
  type=q->v[0];if(type!=DMB_LOADER&&type!=DMB_PERFORMANCE){r->status=DMB_UNSUPPORTED;return;}
  hr=CoCreateInstance(type==DMB_LOADER?&cls_loader:&cls_perf,NULL,3,&ids[type],(void**)&p);break;
 case DMB_QI:
  hr=IUnknown_QueryInterface(o->p,(GUID*)q->guid[0],(void**)&p);
  if(SUCCEEDED(hr)&&(!IsEqualGUID((GUID*)q->guid[0],&IID_IUnknown)&&!IsEqualGUID((GUID*)q->guid[0],&ids[o->type]))){if(p)IUnknown_Release(p);r->status=DMB_UNSUPPORTED;return;}
  type=o->type;break;
 case DMB_ADDREF:r->v[0]=IUnknown_AddRef(o->p);o->refs++;return;
 case DMB_RELEASE:r->v[0]=IUnknown_Release(o->p);o->refs--;return;
 case DMB_INIT_AUDIO:
  REQUIRE(DMB_PERFORMANCE);if(q->v[0]!=8||q->v[1]!=128||q->v[2]!=0x3f){r->status=DMB_UNSUPPORTED;return;}
  hr=((InitAudio)method(o->p,44))(o->p,NULL,&p,NULL,q->v[0],q->v[1],q->v[2],NULL);type=DMB_SOUND;break;
 case DMB_SEARCH:
  REQUIRE(DMB_LOADER);swprintf(folder,600,L"%s\\Music",sandbox);
  if(_wcsicmp((WCHAR*)q->text,folder)||q->v[0]||!IsEqualGUID((GUID*)q->guid[0],&all_types)){r->status=DMB_SANDBOX;return;}
  hr=((Search)method(o->p,5))(o->p,(GUID*)q->guid[0],folder,FALSE);break;
 case DMB_PATH:REQUIRE(DMB_PERFORMANCE);hr=((Out)method(o->p,51))(o->p,&p);type=DMB_AUDIOPATH;break;
 case DMB_GRAPH:
  REQUIRE(DMB_AUDIOPATH);if(q->v[0]||q->v[1]!=0x3200||q->v[2]||q->v[3]||!IsEqualGUID((GUID*)q->guid[0],&GUID_NULL)||!IsEqualGUID((GUID*)q->guid[1],&ids[DMB_TOOLGRAPH])){r->status=DMB_UNSUPPORTED;return;}
  hr=((InPath)method(o->p,3))(o->p,0,0x3200,0,&GUID_NULL,0,&ids[DMB_TOOLGRAPH],(void**)&p);type=DMB_TOOLGRAPH;break;
 case DMB_INSERT:
  REQUIRE(DMB_TOOLGRAPH);if(!q->v[0]||tool_count==8){r->status=DMB_UNSUPPORTED;return;}
  for(i=0;i<tool_count;i++)if(tools[i].token==q->v[0]){r->status=DMB_UNSUPPORTED;return;}
  tools[tool_count].vt=&tool_vt;tools[tool_count].token=q->v[0];tools[tool_count].graph=q->object;
  hr=((Insert)method(o->p,4))(o->p,(IUnknown*)&tools[tool_count++],NULL,0,0);break;
 case DMB_LOAD:
  REQUIRE(DMB_LOADER);if(wcscmp((WCHAR*)q->text,L"Intro.con")||!IsEqualGUID((GUID*)q->guid[0],&cls_container)||!IsEqualGUID((GUID*)q->guid[1],&ids[DMB_CONTAINER])){r->status=DMB_UNSUPPORTED;return;}
  hr=((LoadFile)method(o->p,14))(o->p,&cls_container,&ids[DMB_CONTAINER],L"Intro.con",(void**)&p);type=DMB_CONTAINER;break;
 case DMB_SCRIPT:{BYTE expected[848]={0};
  REQUIRE(DMB_LOADER);*(DWORD*)expected=848;*(DWORD*)(expected+4)=0x206;memcpy(expected+24,&cls_script,16);memcpy(expected+56,L"Script1",16);
  if(memcmp(expected,q->data,848)||!IsEqualGUID((GUID*)q->guid[0],&ids[DMB_SCRIPT_OBJECT])){r->status=DMB_UNSUPPORTED;return;}
  hr=((LoaderObject)method(o->p,3))(o->p,expected,&ids[DMB_SCRIPT_OBJECT],(void**)&p);type=DMB_SCRIPT_OBJECT;break;}
 case DMB_SCRIPT_INIT:
  REQUIRE(DMB_SCRIPT_OBJECT);other=get(q->v[0],DMB_PERFORMANCE);if(!other){r->status=DMB_BAD_HANDLE;return;}
  hr=((ScriptInit)method(o->p,3))(o->p,other->p,NULL);break;
 case DMB_VOLUME:
  REQUIRE(DMB_PERFORMANCE);if(!IsEqualGUID((GUID*)q->guid[0],&volume_guid)||q->v[1]!=4){r->status=DMB_UNSUPPORTED;return;}
  hr=((Global)method(o->p,34))(o->p,&volume_guid,&q->v[0],4);break;
 case DMB_ROUTINE:
  REQUIRE(DMB_SCRIPT_OBJECT);if(q->text[0]&&!(testing&&!wcscmp((WCHAR*)q->text,L"__xrt_missing_routine__"))){r->status=DMB_UNSUPPORTED;return;}
  hr=((Routine)method(o->p,4))(o->p,(WCHAR*)q->text,NULL);break;
 case DMB_ENUM:
  REQUIRE(DMB_SCRIPT_OBJECT);if(!testing||q->v[0]>=128){r->status=DMB_UNSUPPORTED;return;}
  hr=((EnumRoutine)method(o->p,11))(o->p,q->v[0],(WCHAR*)r->text);break;
 case DMB_RELEASE_OBJECT:
  REQUIRE(DMB_LOADER);other=get(q->v[0],0);if(!other){r->status=DMB_BAD_HANDLE;return;}
  if(other->type!=DMB_CONTAINER&&other->type!=DMB_SCRIPT_OBJECT){r->status=DMB_UNSUPPORTED;return;}
  hr=((ReleaseObject)method(o->p,13))(o->p,other->p);break;
 case DMB_STOP:REQUIRE(DMB_PERFORMANCE);hr=((Stop)method(o->p,5))(o->p,NULL,NULL,0,0);break;
 case DMB_CLOSE:REQUIRE(DMB_PERFORMANCE);hr=((CloseDown)method(o->p,38))(o->p);break;
 default:r->status=DMB_UNSUPPORTED;return;
 }

 if(SUCCEEDED(hr)&&type){if(!p)die("native success with null output");r->v[1]=wrap(p,type);r->v[2]=type;}
 else if(p)die("native failure with nonnull output");
 r->v[0]=hr;
}
int wmain(int argc,WCHAR**argv){
 DmbMessage q,r;HRESULT hr;uint32_t last=0;
 if((argc!=6&&argc!=7)||wcscmp(argv[1],L"--pipes")||wcscmp(argv[4],L"--sandbox"))return 2;
 if(argc==7){if(wcscmp(argv[6],L"--test"))return 2;testing=1;}
 input=(HANDLE)(uintptr_t)_wcstoui64(argv[2],NULL,10);output=(HANDLE)(uintptr_t)_wcstoui64(argv[3],NULL,10);
 if(wcslen(argv[5])>=550||!GetFullPathNameW(argv[5],600,sandbox,NULL))return 2;
 owner=GetCurrentThreadId();SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 /* A noninherited Job owned by the parent kills us even during a stuck native
  * call. Outside a call, pipe EOF terminates the receive loop. */
 if(!guard_install(sandbox))die("cannot install isolated disk-open guard");
 hr=CoInitializeEx(NULL,COINIT_APARTMENTTHREADED);if(FAILED(hr))die("cannot initialize STA");
 while(read_frame(&q)){
  sequence=q.sequence;
  if(!valid(&q)||q.kind!=DMB_REQUEST||q.sequence!=last+1||q.status||q.text[511]){
   r=q;r.magic=DMB_MAGIC;r.version=DMB_VERSION;r.bytes=sizeof r;r.kind=DMB_REPLY;r.status=DMB_BAD_FRAME;
   write_frame(&r);fprintf(stderr,"DirectMusic malformed frame\n");break;
  }
  last=q.sequence;dispatch(&q,&r);
  fprintf(stderr,"DirectMusic IPC seq %u op %u id %u status %u result %08x out %u type %u\n",q.sequence,q.op,q.object,r.status,r.v[0],r.v[1],r.v[2]);fflush(stderr);
  if(!write_frame(&r))break;
  sequence=0;if(q.op==DMB_SHUTDOWN||r.status)break;
 }
 disconnected=1;
 /* On a broken connection no callback may call the dead host. Native teardown
  * still runs on the owner STA; the parent's Job bounds its duration. */
 for(last=used;last;last--)while(objects[last-1].refs){IUnknown_Release(objects[last-1].p);objects[last-1].refs--;}
 CoUninitialize();CloseHandle(input);CloseHandle(output);return 0;
}


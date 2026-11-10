#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "evidence_fixture.h"
#include "support.inc"
typedef struct Args {void*fn;uintptr_t a[4];DWORD count;} Args;
typedef __declspec(align(16)) struct ABI {DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];} ABI;
extern void batch_abi(Args*,ABI*);
static void bytes(const void*data,unsigned n){unsigned i;const BYTE*p=data;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static void**table(void*p){return *(void***)p;}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){CPU before;LRESULT result;callbacks++;if(active){before=*active;callback_active++;}result=DefWindowProcW(h,m,w,l);if(active)CHECK(!memcmp(&before,active,sizeof before));return result;}
static void readback(void){DWORD value=0xa5a5a5a5,extra=0xa5a5a5a5;void*p=NULL;HRESULT hr=E_FAIL;BYTE raw[68]={0};unsigned size=0;
 switch(sample->slot){
 case 50:hr=device->vt->GetRenderState(device,sample->a,&value);break;
 case 63:hr=device->vt->GetTextureStageState(device,sample->a,sample->b,&value);break;
 case 37:size=64;hr=device->vt->GetTransform(device,sample->a,(D8Matrix*)raw);break;
 case 42:{typedef HRESULT(WINAPI*Get)(D8Device*,D8Material*);size=68;hr=((Get)table(device)[43])(device,(D8Material*)raw);break;}
 case 61:hr=device->vt->GetTexture(device,sample->a,&p);break;
 case 83:hr=device->vt->GetStreamSource(device,sample->a,&p,&extra);break;
 case 85:hr=device->vt->GetIndices(device,&p,&extra);break;
 case 76:hr=device->vt->GetVertexShader(device,&value);break;
 }
 printf("{\"kind\":\"semantic-readback\",\"hr\":%lu,\"value\":%lu,\"extra\":%lu,\"nonnull\":%s,\"bytes\":",(DWORD)hr,value,extra,p?"true":"false");bytes(raw,size);puts("}");
 if(p){typedef ULONG(WINAPI*Release)(void*);((Release)table(p)[2])(p);}
}
static void invoke(unsigned index,DWORD seed){Args args;ABI out;DWORD error;unsigned i;setup();args.fn=table(device)[sample->slot];args.count=nargs();args.a[0]=(uintptr_t)device;args.a[1]=sample->a;args.a[2]=sample->b;args.a[3]=sample->c;
 if(sample->slot==37)args.a[2]=(uintptr_t)input_data;if(sample->slot==42)args.a[1]=(uintptr_t)input_data;
#if BATCH_TRANSLATED
 args.fn=args.count==2?(void*)wrap2:args.count==3?(void*)wrap3:(void*)wrap4;
#endif
 memset(&out,0,sizeof out);SetLastError(seed);batch_abi(&args,&out);error=GetLastError();
 printf("{\"kind\":\"semantic-call\",\"index\":%u,\"slot\":%u,\"a\":%u,\"b\":%u,\"c\":%u,\"input_kind\":%u,\"invalid\":%u,\"seed\":%lu,\"error\":%lu,\"rejected\":%s,\"hr\":",index,sample->slot,sample->a,sample->b,sample->c,sample->input_kind,sample->invalid,seed,error,rejected?"true":"false");if(rejected)printf("null");else printf("%lu",out.hr);
 printf(",\"stack_delta\":%lu,\"pre\":",out.delta);bytes(out.pre,512);printf(",\"post\":");bytes(out.post,512);printf(",\"regs\":[");for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)out.regs[i]);printf("],\"xmm\":");bytes(out.xmm,160);printf(",\"input\":");bytes(input_data,input_size);printf(",\"cpu\":");bytes(&cpu,sizeof cpu);printf(",\"expected_cpu\":");bytes(&expected,sizeof expected);printf(",\"rejection_utf8_hex\":");bytes(rejection,(unsigned)strlen(rejection));puts("}");readback();
}
int main(int argc,char**argv){WNDCLASSW wc={0};HMODULE lib,dep;char path[2048];D8Factory factory;D8Interface*p;D8Present pp={800,600,22,1,0,1,NULL,1,1,75,0,0,0};HRESULT hr;unsigned i,j,count=0;ULONG dr,pr;static const DWORD seeds[]={0,18,0x13572468,0xffffffff};
 setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 if(argc!=3||strcmp(argv[1],"--physical"))return 2;
 xrt_g=VirtualAlloc(NULL,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g);
 wc.hInstance=GetModuleHandleW(NULL);wc.lpfnWndProc=proc;wc.lpszClassName=L"SemanticPhysicalOwned";CHECK(RegisterClassW(&wc));owned_window=CreateWindowExW(0,wc.lpszClassName,L"Disposable semantic measurement",WS_POPUP,20,20,800,600,NULL,NULL,wc.hInstance,NULL);CHECK(owned_window);pp.window=owned_window;
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[2]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);snprintf(path,sizeof path,"%s/d3d8.dll",argv[2]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);CHECK(dep&&lib);factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");CHECK(factory);p=factory(120);CHECK(p);hr=p->vt->CreateDevice(p,0,1,owned_window,0x42,&pp,&device);CHECK(SUCCEEDED(hr)&&device);
 printf("{\"kind\":\"semantic-create\",\"hr\":%lu,\"width\":%u,\"height\":%u}\n",(DWORD)hr,pp.width,pp.height);
 memset(&parent,0,sizeof parent);parent.guest=0x3000;parent.refs=parent.children=1;parent.host=p;memset(&d8_device,0,sizeof d8_device);d8_device.guest=0x4000;d8_device.refs=1;d8_device.host=device;d8_device.parent=&parent;d8_device.focus=d8_device.window=0x1234;d8_device.depth=1;d8_device.depthformat=75;d8_device.behavior=0x42;
 CHECK(SUCCEEDED(device->vt->GetDeviceCaps(device,&live_caps)));d8_device.caps=live_caps;d8_device.caps_valid=1;
 {D8Interface*q=NULL;D8Creation cp={0};ULONG add=device->vt->AddRef(device),balance=device->vt->Release(device),qr;HRESULT ph=device->vt->GetDirect3D(device,&q),ch;CHECK(q);qr=q->vt->Release(q);ch=device->vt->GetCreationParameters(device,&cp);
 printf("{\"kind\":\"semantic-ownership\",\"add\":%lu,\"balance\":%lu,\"parent_hr\":%lu,\"same_parent\":%s,\"parent_release\":%lu,\"creation_hr\":%lu,\"same_window\":%s,\"flags\":%lu}\n",add,balance,(DWORD)ph,q==p?"true":"false",qr,(DWORD)ch,cp.focus==owned_window?"true":"false",cp.flags);}
 printf("{\"kind\":\"semantic-caps\",\"words\":[");for(i=0;i<53;i++)printf("%s%lu",i?",":"",live_caps.words[i]);puts("]}");ev_backend_luid(dep);ev_checkpoint("loaded");record_events=1;
 for(i=0;i<sizeof samples/sizeof samples[0];i++){sample=&samples[i];for(j=0;j<4;j++){invoke(i,seeds[j]);count++;}}
 record_events=0;dr=device->vt->Release(device);pr=p->vt->Release(p);CHECK(dr==0&&pr==0);
 {BOOL destroy=DestroyWindow(owned_window),unreg=UnregisterClassW(wc.lpszClassName,wc.hInstance),ul=FreeLibrary(lib),ud=FreeLibrary(dep),freed=VirtualFree(xrt_g,0,MEM_RELEASE);
 printf("{\"kind\":\"semantic-cleanup\",\"device_release\":%lu,\"parent_release\":%lu,\"destroyed\":%s,\"unregistered\":%s,\"window_valid\":%s,\"free_d3d8\":%s,\"free_d3d9\":%s,\"d3d8_loaded\":%s,\"d3d9_loaded\":%s,\"guest_freed\":%s,\"callbacks\":%u,\"active_callbacks\":%u}\n",dr,pr,destroy?"true":"false",unreg?"true":"false",IsWindow(owned_window)?"true":"false",ul?"true":"false",ud?"true":"false",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false",freed?"true":"false",callbacks,callback_active);}
 ev_checkpoint("cleaned");printf("{\"kind\":\"semantic-summary\",\"calls\":%u,\"translated\":%s,\"group\":%u}\n",count,BATCH_TRANSLATED?"true":"false",BATCH_GROUP);return 0;
}

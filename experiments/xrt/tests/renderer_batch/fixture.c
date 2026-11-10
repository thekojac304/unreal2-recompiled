/* Exact x86/x64 native and translated CPU-boundary differential fixture.
 * --contract-only uses declared COM doubles, never loads graphics DLLs.
 * --physical loads pinned DXVK only when invoked by the separate desktop runner. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "support.inc"
typedef struct Args {void*fn;uintptr_t a[4];DWORD count;} Args;
typedef __declspec(align(16)) struct ABI {DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];} ABI;
extern void batch_abi(Args*,ABI*);
static unsigned calls;
static DWORD observations_hash=2166136261u;
DWORD resize_result,resize_bad;
#if BATCH_GROUP==9
#if defined(_M_IX86)
extern DWORD WINAPI resize_adapter(uintptr_t,uintptr_t,uintptr_t,uintptr_t);
#else
static DWORD WINAPI resize_adapter(uintptr_t self,uintptr_t flags,uintptr_t width,uintptr_t height){
    CHECK(self==0x8000&&(flags==16||flags==17)&&width==1540&&height==945);return resize_result;
}
#endif
static DWORD WINAPI wrap_resize(uintptr_t self,uintptr_t flags,uintptr_t width,uintptr_t height){
    CHECK(self==0x8000&&flags==batch_case->a&&width==batch_case->b&&height==batch_case->c);
    guest_error=GetLastError();return translated_call();
}
#endif
static const DWORD seeds[]={18,0,0x13572468,0xffffffff};
static void bytes(const BYTE*p,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static void** table(void*p){return *(void***)p;}
static DWORD invoke(DWORD seed){
    Args args;ABI out;DWORD error;unsigned n=nargs(),i;void* fn=table(fixture_device)[batch_case->slot];
    int stable;uintptr_t b=batch_case->b;
    if(batch_case->slot==37)b=(uintptr_t)batch_identity;
    if(batch_case->slot==18)b=(uintptr_t)batch_ramp;
#if BATCH_TRANSLATED
    fn=n==2?(void*)wrap2:n==3?(void*)wrap3:(void*)wrap4;
#endif
    args.fn=fn;args.a[0]=(uintptr_t)fixture_device;args.a[1]=batch_case->a;args.a[2]=b;args.a[3]=batch_case->c;args.count=n;
#if BATCH_GROUP==9
    args.fn=BATCH_TRANSLATED?(void*)wrap_resize:(void*)resize_adapter;args.a[0]=0x8000;args.count=4;
#endif
    memset(&out,0,sizeof out);SetLastError(seed);batch_abi(&args,&out);error=GetLastError();calls++;
    stable=!memcmp(out.pre,out.post,5)&&!memcmp(out.pre+24,out.post+24,4)&&!memcmp(out.pre+32,out.post+32,10)&&!memcmp(out.pre+48,out.post+48,10);
    CHECK(!out.delta);CHECK(stable);
#if defined(_M_IX86)
    {const uint64_t expected[8]={0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0};CHECK(!memcmp(out.regs,expected,sizeof expected));}
#else
    {const uint64_t expected[8]={0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef};
    const DWORD xmm[]={0x12345678,0x23456789,0x3456789a,0x456789ab};CHECK(!memcmp(out.regs,expected,sizeof expected));for(i=0;i<10;i++)CHECK(!memcmp(out.xmm+i*16,xmm,16));}
#endif
    if(!graphics){CHECK(error==host_error);if(batch_case->slot!=18)CHECK(out.hr==(DWORD)host_result);}
    observations_hash=(observations_hash^seed)*16777619u;observations_hash=(observations_hash^error)*16777619u;
    observations_hash=(observations_hash^(batch_case->slot==18?0:out.hr))*16777619u;
    if(emit_calls){printf("{\"kind\":\"call\",\"group\":%u,\"site\":%u,\"config\":%u,\"slot\":%u,\"a\":%u,\"b\":%u,\"c\":%u,\"seed\":%lu,\"error\":%lu,\"hr\":",batch_case->group,batch_case->site,batch_case->config,batch_case->slot,batch_case->a,batch_case->b,batch_case->c,seed,error);
        if(batch_case->slot==18)printf("null");else printf("%lu",out.hr);
        printf(",\"stack_delta\":%lu,\"fpu_preserved\":true,\"pre\":",out.delta);bytes(out.pre,512);printf(",\"post\":");bytes(out.post,512);puts("}");}
    return out.hr;
}
static void readback(void){
    D8Device*d=fixture_device;HRESULT hr=S_OK;DWORD value=0xa5a5a5a5,extra=0xa5a5a5a5;void*p=NULL;D8Matrix m;D8Gamma ramp;int equal=0;
    switch(batch_case->slot){
    case 50:hr=d->vt->GetRenderState(d,batch_case->a,&value);equal=value==batch_case->b;break;
    case 63:hr=d->vt->GetTextureStageState(d,batch_case->a,batch_case->b,&value);equal=value==batch_case->c;break;
    case 37:hr=d->vt->GetTransform(d,batch_case->a,&m);equal=!memcmp(&m,batch_identity,64);break;
    case 61:hr=d->vt->GetTexture(d,batch_case->a,&p);equal=p==NULL;break;
    case 83:hr=d->vt->GetStreamSource(d,batch_case->a,&p,&extra);equal=p==NULL&&extra==0;break;
    case 85:hr=d->vt->GetIndices(d,&p,&extra);equal=p==NULL&&extra==0;break;
    case 76:hr=d->vt->GetVertexShader(d,&value);equal=value==2;break;
    case 18:d->vt->GetGammaRamp(d,&ramp);equal=!memcmp(&ramp,batch_ramp,1536);break;
    }
    if(p){typedef ULONG(WINAPI*Release)(void*);((Release)table(p)[2])(p);}
    printf("{\"kind\":\"readback\",\"slot\":%u,\"hr\":%lu,\"equal\":%s,\"value\":%lu,\"extra\":%lu}\n",batch_case->slot,(DWORD)hr,equal?"true":"false",value,extra);
    CHECK(SUCCEEDED(hr)&&equal);
}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){return DefWindowProcW(h,m,w,l);}
static int physical(const char*pair,int gamma_enabled){
    HMODULE lib,dep;D8Interface*p;D8Factory factory;WNDCLASSW wc={0};char path[2048];HRESULT hr;
    D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};D8Gamma saved,restored;unsigned i,j,k;ULONG dr,pr;int failed=0;
    if(BATCH_GROUP==9)return 95; /* Real ResizeViewport requires its generated/Win32 fixture, not this protocol double. */
    if(BATCH_GROUP==8&&!gamma_enabled)return 96;
    wc.hInstance=GetModuleHandleW(NULL);wc.lpfnWndProc=proc;wc.lpszClassName=L"XrtBatchPreparation";
    CHECK(RegisterClassW(&wc));fixture_window=CreateWindowExW(0,wc.lpszClassName,L"Disposable renderer measurement",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);CHECK(fixture_window!=NULL);pp.window=fixture_window;
    snprintf(path,sizeof path,"%s/d3d9.dll",pair);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path,sizeof path,"%s/d3d8.dll",pair);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);CHECK(lib&&dep);
    factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");CHECK(factory!=NULL);p=factory(120);CHECK(p!=NULL);fixture_device=NULL;
    hr=p->vt->CreateDevice(p,0,1,fixture_window,0x42,&pp,&fixture_device);
    printf("{\"kind\":\"create\",\"hr\":%lu,\"nonnull\":%s}\n",(DWORD)hr,fixture_device?"true":"false");
    if(FAILED(hr)||!fixture_device){p->vt->Release(p);DestroyWindow(fixture_window);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);return 7;}
    graphics=emit_calls=1;
    if(BATCH_GROUP==8)fixture_device->vt->GetGammaRamp(fixture_device,&saved);
    physical_guard=1;
    if(setjmp(stop))failed=1;
    else for(i=0;i<sizeof batch_cases/sizeof batch_cases[0];i++)if(batch_cases[i].group==BATCH_GROUP){
        batch_case=&batch_cases[i];for(j=0;j<4;j++)for(k=0;k<2;k++){invoke(seeds[j]);readback();}
    }
    physical_guard=0;
    if(BATCH_GROUP==8){int equal;fixture_device->vt->SetGammaRamp(fixture_device,0,&saved);fixture_device->vt->GetGammaRamp(fixture_device,&restored);equal=!memcmp(&saved,&restored,1536);if(!equal)failed=1;printf("{\"kind\":\"gamma-restored\",\"equal\":%s}\n",equal?"true":"false");}
    dr=fixture_device->vt->Release(fixture_device);pr=p->vt->Release(p);CHECK(dr==0&&pr==0);
    DestroyWindow(fixture_window);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);
    printf("{\"kind\":\"summary\",\"passed\":%s,\"calls\":%u,\"graphics\":true,\"translated\":%s}\n",failed?"false":"true",calls,BATCH_TRANSLATED?"true":"false");return failed?91:0;
}
int main(int argc,char**argv){
    unsigned i,j,k,r;WORD*words=(WORD*)batch_ramp;setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    for(i=0;i<768;i++)words[i]=(WORD)((i%256)*257);
    xrt_g=VirtualAlloc(NULL,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g!=NULL);
    vt.SetRenderState=state;vt.SetTextureStageState=stage_state;vt.SetTransform=transform;vt.SetTexture=texture;
    vt.SetStreamSource=stream;vt.SetIndices=indices;vt.SetVertexShader=fvf;vt.SetGammaRamp=gamma_set;
#if BATCH_GROUP==9
    batch_guest_invoke=resize_callback;
#endif
    if(argc>=3&&!strcmp(argv[1],"--physical"))return physical(argv[2],argc==4&&!strcmp(argv[3],"--gamma-physical"));
    if(argc!=2||strcmp(argv[1],"--contract-only"))return 2;
    for(i=0;i<sizeof batch_cases/sizeof batch_cases[0];i++)if(batch_cases[i].group==BATCH_GROUP){
        batch_case=&batch_cases[i];
        if(BATCH_GROUP==9){
            for(j=0;j<4;j++)for(k=0;k<3;k++){resize_result=(DWORD)(k==0?0:k==1?1:0x12345678);host_result=(HRESULT)resize_result;host_error=seeds[j];CHECK(invoke(seeds[j])==resize_result);CHECK(!resize_bad);}
        }else for(j=0;j<4;j++)for(k=0;k<2;k++)for(r=0;r<2;r++){
            host_result=k?E_FAIL:S_OK;host_error=seeds[(j+1)%4];invoke(seeds[j]);
        }
        negatives();
#if BATCH_TRANSLATED
        extra_contracts();
#endif
    }
    CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));
    printf("{\"kind\":\"summary\",\"passed\":true,\"group\":%d,\"checks\":%u,\"calls\":%u,\"callbacks\":%u,\"observations_hash\":%lu,\"graphics\":false,\"translated\":%s,\"double_only\":true}\n",BATCH_GROUP,checks,calls,callback_count,observations_hash,BATCH_TRANSLATED?"true":"false");return 0;
}

/* Prepared native disposable batches. No game, presentation, display changes,
 * resource allocation, gamma mutation, or production adapter implementation.
 * --abi-only exercises the trampoline with local functions and loads no DXVK. */
#define WIN32_LEAN_AND_MEAN
#include "../../runtime/d3d8_device_abi.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct Args { void*fn;uintptr_t a[4];DWORD count; } Args;
typedef __declspec(align(16))struct ABI { DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512]; } ABI;
extern void batch_abi(Args*,ABI*);
static unsigned calls,failures,callbacks,inside;
static DWORD current_seed=18;
static const DWORD seeds[]={18,0,0x13572468,0xffffffff};
static void bytes(const BYTE*p,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static DWORD invoke(void*fn,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d,DWORD count,const char*method,DWORD index){
 Args args={fn,{a,b,c,d},count};ABI out;DWORD e;unsigned j;int stable;
 memset(&out,0,sizeof out);SetLastError(current_seed);inside=1;batch_abi(&args,&out);e=GetLastError();inside=0;calls++;
 stable=!memcmp(out.pre,out.post,5)&&!memcmp(out.pre+24,out.post+24,4)&&!memcmp(out.pre+32,out.post+32,10)&&!memcmp(out.pre+48,out.post+48,10);
 if(out.delta||!stable||e!=current_seed)failures++;
 printf("{\"kind\":\"call\",\"method\":\"%s\",\"index\":%lu,\"hr\":%lu,\"last_error\":%lu,\"seed\":%lu,\"stack_delta\":%lu,\"fpu_preserved\":%s,\"regs\":[",method,index,out.hr,e,current_seed,out.delta,stable?"true":"false");
 for(j=0;j<8;j++)printf("%s%llu",j?",":"",(unsigned long long)out.regs[j]);printf("],\"xmm\":");bytes(out.xmm,160);printf(",\"pre\":");bytes(out.pre,512);printf(",\"post\":");bytes(out.post,512);puts("}");return out.hr;
}
static DWORD WINAPI two(uintptr_t a,uintptr_t b){if(a!=0x12345678||b!=0x23456789)ExitProcess(90);return 0x87654321;}
static DWORD WINAPI three(uintptr_t a,uintptr_t b,uintptr_t c){if(a!=0x12345678||b!=0x23456789||c!=0x3456789a)ExitProcess(90);return 0x87654321;}
static DWORD WINAPI four(uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d){if(a!=0x12345678||b!=0x23456789||c!=0x3456789a||d!=0x456789ab)ExitProcess(90);return 0x87654321;}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){if(inside)callbacks++;return DefWindowProcW(h,m,w,l);}
static void**table(void*p){return *(void***)p;}
static void readscalar(D8Device*d,int texture,DWORD stage,DWORD state,DWORD expected){DWORD value=0xa5a5a5a5;HRESULT hr;
 if(texture){typedef HRESULT(WINAPI*Get)(D8Device*,DWORD,DWORD,DWORD*);hr=((Get)table(d)[62])(d,stage,state,&value);}
 else{typedef HRESULT(WINAPI*Get)(D8Device*,DWORD,DWORD*);hr=((Get)table(d)[51])(d,state,&value);}
 printf("{\"kind\":\"readback\",\"texture\":%d,\"stage\":%lu,\"state\":%lu,\"hr\":%lu,\"value\":%lu,\"expected\":%lu}\n",texture,stage,state,(DWORD)hr,value,expected);
}
#include "batch_cases.inc"
static void states(D8Device*d){unsigned i,j,k;for(i=0;i<sizeof state_cases/sizeof state_cases[0];i++)for(j=0;j<4;j++){
 current_seed=seeds[j];for(k=0;k<2;k++){DWORD val=state_cases[i][1]^(k?0:1);invoke(table(d)[50],(uintptr_t)d,state_cases[i][0],val,0,3,"SetRenderState",i);readscalar(d,0,0,state_cases[i][0],val);}}}
static void samplers(D8Device*d){unsigned stage,i,j;const DWORD cases[][2]={{19,0},{19,0x3f000000},{16,2},{16,3},{17,2},{17,3},{18,0},{18,1},{18,2},{21,1},{21,2},{1,1},{2,2},{3,1},{4,1},{5,0},{6,1},{11,0},{13,1},{14,1},{24,0},{25,1},{19,0},{26,1},{27,1},{28,1}};
 for(stage=0;stage<8;stage++)for(i=0;i<sizeof cases/sizeof cases[0];i++)for(j=0;j<4;j++){current_seed=seeds[j];invoke(table(d)[63],(uintptr_t)d,stage,cases[i][0],cases[i][1],4,"SetTextureStageState",stage*100+i);readscalar(d,1,stage,cases[i][0],cases[i][1]);}}
static void bindings(D8Device*d){unsigned i,j;DWORD identity[16]={0x3f800000,0,0,0,0,0x3f800000,0,0,0,0,0x3f800000,0,0,0,0,0x3f800000};
 for(i=0;i<11;i++)for(j=0;j<4;j++){DWORD got[16]={0};HRESULT hr;typedef HRESULT(WINAPI*Get)(D8Device*,DWORD,void*);current_seed=seeds[j];invoke(table(d)[37],(uintptr_t)d,transform_cases[i],(uintptr_t)identity,0,3,"SetTransform",i);hr=((Get)table(d)[38])(d,transform_cases[i],got);printf("{\"kind\":\"transform\",\"type\":%lu,\"hr\":%lu,\"equal\":%s}\n",transform_cases[i],(DWORD)hr,!memcmp(got,identity,64)?"true":"false");}
 for(i=0;i<8;i++){void*q=NULL;HRESULT hr;typedef HRESULT(WINAPI*Get)(D8Device*,DWORD,void**);invoke(table(d)[61],(uintptr_t)d,i,0,0,3,"SetTexture",i);hr=((Get)table(d)[60])(d,i,&q);printf("{\"kind\":\"texture\",\"stage\":%u,\"hr\":%lu,\"null\":%s}\n",i,(DWORD)hr,q?"false":"true");if(q){typedef ULONG(WINAPI*Release)(void*);((Release)table(q)[2])(q);}}
 {DWORD value=0;HRESULT hr;typedef HRESULT(WINAPI*Get)(D8Device*,DWORD*);invoke(table(d)[76],(uintptr_t)d,2,0,0,2,"SetVertexShader",0);hr=((Get)table(d)[77])(d,&value);printf("{\"kind\":\"fvf\",\"hr\":%lu,\"value\":%lu}\n",(DWORD)hr,value);}
 for(i=0;i<16;i++){void*q=NULL;DWORD stride=0xa5a5a5a5;HRESULT hr;typedef HRESULT(WINAPI*Get)(D8Device*,DWORD,void**,DWORD*);invoke(table(d)[83],(uintptr_t)d,i,0,0,4,"SetStreamSource",i);hr=((Get)table(d)[84])(d,i,&q,&stride);printf("{\"kind\":\"stream\",\"stream\":%u,\"hr\":%lu,\"null\":%s,\"stride\":%lu}\n",i,(DWORD)hr,q?"false":"true",stride);if(q){typedef ULONG(WINAPI*Release)(void*);((Release)table(q)[2])(q);}}
 {void*q=NULL;DWORD base=0xa5a5a5a5;HRESULT hr;typedef HRESULT(WINAPI*Get)(D8Device*,void**,DWORD*);invoke(table(d)[85],(uintptr_t)d,0,0,0,3,"SetIndices",0);hr=((Get)table(d)[86])(d,&q,&base);printf("{\"kind\":\"indices\",\"hr\":%lu,\"null\":%s,\"base\":%lu}\n",(DWORD)hr,q?"false":"true",base);if(q){typedef ULONG(WINAPI*Release)(void*);((Release)table(q)[2])(q);}}
}
int main(int argc,char**argv){HMODULE lib,dep;D8Interface*p;D8Device*d=NULL;WNDCLASSW wc={0};HWND w;D8Factory factory;char path[2048];HRESULT hr;D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};ULONG dr,pr;unsigned n,j;
 setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 if(argc==2&&!strcmp(argv[1],"--abi-only")){void*fn[]={two,three,four};for(n=2;n<=4;n++)for(j=0;j<4;j++){current_seed=seeds[j];if(invoke(fn[n-2],0x12345678,0x23456789,0x3456789a,0x456789ab,n,"local-ABI-double",n)!=0x87654321)failures++;}printf("{\"kind\":\"summary\",\"calls\":%u,\"failures\":%u,\"graphics\":false}\n",calls,failures);return failures?91:0;}
 if(argc!=3||strcmp(argv[2],"states")&&strcmp(argv[2],"samplers")&&strcmp(argv[2],"bindings"))return 2;
 wc.hInstance=GetModuleHandleW(NULL);wc.lpfnWndProc=proc;wc.lpszClassName=L"XrtPreparedRendererBatch";if(!RegisterClassW(&wc))return 3;
 w=CreateWindowExW(0,wc.lpszClassName,L"Disposable renderer batch oracle",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!w)return 4;pp.window=w;
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
 snprintf(path,sizeof path,"%s/d3d8.dll",argv[1]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!lib||!dep)return 5;
 factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");p=factory(120);if(!p)return 6;hr=p->vt->CreateDevice(p,0,1,w,0x42,&pp,&d);
 printf("{\"kind\":\"create\",\"hr\":%lu,\"device_nonnull\":%s}\n",(DWORD)hr,d?"true":"false");if(FAILED(hr)||!d)return 7;
 if(!strcmp(argv[2],"states"))states(d);else if(!strcmp(argv[2],"samplers"))samplers(d);else bindings(d);
 dr=d->vt->Release(d);pr=p->vt->Release(p);DestroyWindow(w);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);
 printf("{\"kind\":\"summary\",\"calls\":%u,\"failures\":%u,\"callbacks\":%u,\"device_release\":%lu,\"parent_release\":%lu,\"graphics\":true}\n",calls,failures,callbacks,dr,pr);return failures?91:0;}

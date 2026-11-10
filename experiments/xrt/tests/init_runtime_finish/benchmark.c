#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <stdio.h>
#include "xrt_internal.h"
#include "monitor_com.inc"
uint8_t*xrt_g;
static CPU cpu;
static unsigned direct, callbacks, calls;
static D8DeviceVtable vt;
static D8Device device={&vt};
static __declspec(align(16)) unsigned char actual_native_fx[512];
static DWORD actual_native_error;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d %s\n",__LINE__,#x);ExitProcess(91);}}while(0)
static HRESULT WINAPI texture(D8Device*p,UINT w,UINT h,UINT levels,DWORD usage,DWORD format,DWORD pool,D8Texture**out){
 __declspec(align(16)) unsigned char fx[512];
 CHECK(p==&device&&w==32&&h==32&&levels==1&&usage==0&&format==21&&pool==1&&out);
 *out=NULL;calls++;_fxsave64(fx);fx[2]|=0x20;_fxrstor64(fx);
 SetLastError(0xaabbccdd);_fxsave64(actual_native_fx);actual_native_error=GetLastError();return E_FAIL;
}
static HRESULT WINAPI cooperative(D8Device*p){CHECK(p==&device);calls++;SetLastError(0x22446688);return S_FALSE;}
static LRESULT CALLBACK proc(HWND window,UINT msg,WPARAM wp,LPARAM lp){
 LRESULT result;
 if(msg!=WM_APP+31&&msg!=WM_APP+32)return DefWindowProcW(window,msg,wp,lp);
 if(!direct)xm_scope(&cpu,XM_BEGIN,XM_CALLBACK,"bench.WNDPROC",msg);
 callbacks++;
 if(msg==WM_APP+31){
  if(!direct)xm_native(&cpu,XM_BEGIN,"WIN.SendMessageW",0,0);
  result=SendMessageW(window,WM_APP+32,wp+1,lp);
  if(!direct)xm_native(&cpu,XM_END,"WIN.SendMessageW",0,result);
 }else result=direct?cooperative(&device):XM_TestCooperativeLevel(&cpu,&device);
 if(!direct)xm_scope(&cpu,XM_END,XM_CALLBACK,"bench.WNDPROC",result);
 return result;
}
int main(int argc,char**argv){
 WNDCLASSW wc={0};HWND window;LARGE_INTEGER start,end,freq;unsigned n,i;CPU before;
 __declspec(align(16)) unsigned char fx[512];
 CHECK(argc==4);n=atoi(argv[2]);direct=atoi(argv[3]);
 xrt_g=VirtualAlloc(NULL,0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);CHECK(xrt_g);
 cpu.r[ESP]=0x2000;cpu.fs_base=0x1000;cpu.fcw=0x27f;cpu.fsw=0x4020;cpu.pc=0x1098f460;
 wr32(cpu.r[ESP],0x1090ed5c);wr32(0x1034,0x55667788);before=cpu;
 vt.TestCooperativeLevel=cooperative;vt.CreateTexture=texture;
 wc.lpfnWndProc=proc;wc.lpszClassName=L"XrtInitMonitoringOwnedBenchmark";wc.hInstance=GetModuleHandleW(NULL);
 CHECK(RegisterClassW(&wc));window=CreateWindowW(wc.lpszClassName,L"",0,0,0,0,0,HWND_MESSAGE,0,wc.hInstance,0);CHECK(window);
 if(strcmp(argv[1],"off")){xm_init(argv[1]);xm_resource(&cpu,2,0x4000,1,(uint64_t)(uintptr_t)&device,1,0,"created");}
 QueryPerformanceFrequency(&freq);QueryPerformanceCounter(&start);
 for(i=0;i<n;i++){
  D8Texture*out=NULL;HRESULT hr;DWORD error;
  if(!direct)xm_scope(&cpu,XM_BEGIN,XM_ADAPTER,"owned.initialization-sequence",i);
  SetLastError(0x12345678);
  hr=direct?texture(&device,32,32,1,0,21,1,&out):XM_CreateTexture(&cpu,&device,32,32,1,0,21,1,&out);
  error=GetLastError();_fxsave64(fx);
  CHECK(hr==E_FAIL&&!out&&error==0xaabbccdd&&(fx[2]&0x20));
  CHECK(actual_native_error==error&&!memcmp(fx,actual_native_fx,5)&&!memcmp(fx+24,actual_native_fx+24,4)&&!memcmp(fx+32,actual_native_fx+32,128));
  if(!direct){xm_blob(&cpu,"native.return.fxsave.first256",fx,256);xm_blob(&cpu,"native.return.fxsave.last256",fx+256,256);}
  CHECK(SendMessageW(window,WM_APP+31,i,0)==S_FALSE);
  if(!direct)xm_scope(&cpu,XM_END,XM_ADAPTER,"owned.initialization-sequence",i);
  CHECK(!memcmp(&cpu,&before,sizeof cpu)&&rd32(0x1034)==0x55667788);
 }
 QueryPerformanceCounter(&end);CHECK(DestroyWindow(window));CHECK(UnregisterClassW(wc.lpszClassName,wc.hInstance));
 if(xm_enabled())xm_close();
 printf("{\"iterations\":%u,\"seconds\":%.9f,\"calls\":%u,\"callbacks\":%u,\"records\":%llu,\"native_error\":2864434397,\"precision_status_preserved\":true}\n",
 n,(double)(end.QuadPart-start.QuadPart)/freq.QuadPart,calls,callbacks,xm_committed);
 return 0;
}

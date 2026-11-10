/* Native-only first-Present lifecycle diagnostic. No input synthesis. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "../../runtime/d3d8_abi.h"
#define MARK (WM_APP+55)
static LARGE_INTEGER origin,frequency;
static const char* phase="startup";
static unsigned sequence,depth,marker_count,foreign,callbacks;
static DWORD owner;
static WNDPROC initial;
static double elapsed(void){LARGE_INTEGER t;QueryPerformanceCounter(&t);return (double)(t.QuadPart-origin.QuadPart)*1000.0/frequency.QuadPart;}
static void quoted(const WCHAR* s){putchar('"');for(;*s;s++){unsigned c=*s;if(c=='\\'||c=='"')putchar('\\');if(c<128)putchar(c);else printf("\\u%04x",c);}putchar('"');}
static LRESULT CALLBACK original(HWND h,UINT m,WPARAM w,LPARAM l){
 DWORD error=GetLastError();LRESULT r;unsigned n=++sequence;double t=elapsed();WNDPROC enter=(WNDPROC)GetWindowLongPtrW(h,GWLP_WNDPROC);depth++;callbacks++;
 if(GetCurrentThreadId()!=owner)foreign++;
 if(m==MARK){marker_count++;r=(LRESULT)(0x12340000u+(DWORD)w+(DWORD)l);}
 else r=DefWindowProcW(h,m,w,l);
 printf("{\"kind\":\"callback\",\"seq\":%u,\"phase\":\"%s\",\"ms_enter\":%.3f,\"ms_leave\":%.3f,\"depth\":%u,\"message\":%u,\"wp\":%llu,\"lp\":%lld,\"result\":%lld,\"thread\":%lu,\"installed_enter\":%llu,\"installed_leave\":%llu}\n",n,phase,t,elapsed(),depth,m,(unsigned long long)w,(long long)l,(long long)r,GetCurrentThreadId(),(unsigned long long)(uintptr_t)enter,(unsigned long long)(uintptr_t)GetWindowLongPtrW(h,GWLP_WNDPROC));
 depth--;SetLastError(error);return r;
}
static WNDPROC pointer(HWND h,const char* tag){
 WNDPROC p=(WNDPROC)GetWindowLongPtrW(h,GWLP_WNDPROC);HMODULE module=NULL;MEMORY_BASIC_INFORMATION mem;WCHAR name[2048]={0};DWORD error;
 SetLastError(0);GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCWSTR)p,&module);error=GetLastError();
 if(module)GetModuleFileNameW(module,name,2048);ZeroMemory(&mem,sizeof mem);VirtualQuery((void*)p,&mem,sizeof mem);
 printf("{\"kind\":\"pointer\",\"tag\":\"%s\",\"ms\":%.3f,\"valid\":%s,\"pointer\":%llu,\"base\":%llu,\"rva\":%llu,\"allocation_base\":%llu,\"memory_type\":%lu,\"protect\":%lu,\"module_error\":%lu,\"is_original\":%s,\"module\":",tag,elapsed(),IsWindow(h)?"true":"false",(unsigned long long)(uintptr_t)p,(unsigned long long)(uintptr_t)module,(unsigned long long)((uintptr_t)p-(uintptr_t)module),(unsigned long long)(uintptr_t)mem.AllocationBase,mem.Type,mem.Protect,error,p==initial?"true":"false");quoted(name);puts("}");return p;
}
static void forwarding(HWND h,WNDPROC previous,const char* tag){
 unsigned before=marker_count;LRESULT a,b,c,d;DWORD e;
 phase=tag;SetLastError(0x5555);a=SendMessageW(h,MARK,21,34);e=GetLastError();
 b=CallWindowProcW(previous,h,MARK,21,34);c=SendMessageW(h,WM_GETICON,ICON_BIG,96);d=SendMessageW(h,WM_NULL,0,0);
 printf("{\"kind\":\"forward\",\"tag\":\"%s\",\"installed_result\":%lld,\"previous_result\":%lld,\"marker_callbacks\":%u,\"last_error\":%lu,\"icon_result\":%lld,\"null_result\":%lld}\n",tag,(long long)a,(long long)b,marker_count-before,e,(long long)c,(long long)d);
}
static void pump(void){MSG m;unsigned n=0;while(n<64 && PeekMessageW(&m,NULL,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);n++;}printf("{\"kind\":\"pump\",\"phase\":\"%s\",\"messages\":%u,\"ms\":%.3f}\n",phase,n,elapsed());}
int main(int argc,char**argv){
 WNDCLASSW wc;HWND h;HMODULE d8,d9;char path[2048];D8Factory factory;D8Interface* parent;D8Device* device=NULL;
 D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};HRESULT hr;ULONG dr,pr;WNDPROC pre,post;unsigned cb;
 typedef HRESULT (WINAPI* Present)(D8Device*,const RECT*,const RECT*,HWND,const RGNDATA*);
 typedef ULONG (WINAPI* Release)(D8Device*);
 if(argc!=3)return 2;setvbuf(stdout,NULL,_IONBF,0);QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&origin);owner=GetCurrentThreadId();initial=original;
 ZeroMemory(&wc,sizeof wc);wc.lpfnWndProc=original;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XrtFirstPresentWndprocDiagnostic";
 if(!RegisterClassW(&wc))return 3;
 phase="create-window";h=CreateWindowExW(0,wc.lpszClassName,L"Disposable first Present diagnostic",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!h)return 4;
 phase="show-noactivate";ShowWindow(h,SW_SHOWNOACTIVATE);UpdateWindow(h);pointer(h,"window-created");
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[1]);d9=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
 snprintf(path,sizeof path,"%s/d3d8.dll",argv[1]);d8=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!d8||!d9)return 5;
 factory=(D8Factory)GetProcAddress(d8,"Direct3DCreate8");parent=factory(120);if(!parent)return 6;
 pp.window=h;phase="create-device";hr=parent->vt->CreateDevice(parent,0,1,h,0x42,&pp,&device);
 printf("{\"kind\":\"create\",\"hr\":%lu,\"device\":%s,\"ms\":%.3f}\n",(DWORD)hr,device?"true":"false",elapsed());if(FAILED(hr)||!device)return 7;
 pre=pointer(h,"before-first-present");phase="first-present";cb=callbacks;hr=((Present)(*(void***)device)[15])(device,NULL,NULL,NULL,NULL);
 printf("{\"kind\":\"present\",\"hr\":%lu,\"callbacks_during\":%u,\"ms\":%.3f}\n",(DWORD)hr,callbacks-cb,elapsed());
 post=pointer(h,"after-first-present-immediate");forwarding(h,pre,"after-present-forward");
 phase="post-present-pump";pump();pointer(h,"after-pump");
 if(atoi(argv[2])){
   phase="destroy-with-live-device";DestroyWindow(h);pointer(h,"after-window-destroy-live-device");
   phase="release-device-after-window";dr=((Release)(*(void***)device)[2])(device);
 }else{
   phase="release-device";dr=((Release)(*(void***)device)[2])(device);pointer(h,"after-device-release");forwarding(h,pre,"after-device-release-forward");
 }
 phase="release-parent";pr=parent->vt->Release(parent);if(IsWindow(h))pointer(h,"after-parent-release");
 if(IsWindow(h)){phase="unload-backend";FreeLibrary(d8);FreeLibrary(d9);pointer(h,"after-backend-unload");phase="destroy-window";DestroyWindow(h);}else{FreeLibrary(d8);FreeLibrary(d9);}
 UnregisterClassW(wc.lpszClassName,wc.hInstance);
 printf("{\"kind\":\"cleanup\",\"device_release\":%lu,\"parent_release\":%lu,\"window_valid\":%s,\"foreign_callbacks\":%u,\"proc_changed\":%s,\"d3d8_loaded\":%s,\"d3d9_loaded\":%s,\"ms\":%.3f}\n",dr,pr,IsWindow(h)?"true":"false",foreign,pre!=post?"true":"false",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false",elapsed());return FAILED(hr)?8:0;
}

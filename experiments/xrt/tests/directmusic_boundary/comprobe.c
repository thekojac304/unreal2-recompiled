/* Same PE32 client on native Windows and the translated runtime. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
__declspec(dllexport) int probe_log[1024],probe_log_n;
static void logv(int v){probe_log[probe_log_n++]=v;}
static const GUID cls={0xd2ac2892,0xb39b,0x11d1,{0x87,4,0,0x60,8,0x93,0xb1,0xbd}};
static const GUID iid={0x19e7c08c,0x0a44,0x4e6a,{0xa1,0x16,0x59,0x5a,0x7c,0xd5,0xde,0x8c}};
static const GUID missing={0x12345678,0x1234,0x5678,{1,2,3,4,5,6,7,8}};
static IUnknown*create(void){IUnknown*p=NULL;logv(CoCreateInstance(&cls,NULL,3,&iid,(void**)&p));logv(p!=NULL);return p;}
__declspec(dllexport) int probe_sta(void){
    probe_log_n=0;logv(CoInitialize(NULL));logv(CoInitialize(NULL));logv(CoInitializeEx(NULL,0));
    CoUninitialize();CoUninitialize();logv(CoInitialize(NULL));CoUninitialize();return 0;
}
__declspec(dllexport) int probe_mta(void){
    probe_log_n=0;logv(CoInitializeEx(NULL,0));logv(CoInitialize(NULL));logv(CoInitializeEx(NULL,0));
    CoUninitialize();CoUninitialize();return 0;
}
__declspec(dllexport) int probe_loader(void){
    IUnknown*a,*b,*q=NULL;HRESULT hr;
    probe_log_n=0;logv(CoInitialize(NULL));a=create();b=create();if(!a || !b)return 1;
    logv(a!=b);logv(IUnknown_QueryInterface(a,&iid,(void**)&q));logv(q==a);logv(IUnknown_Release(q));
    logv(IUnknown_QueryInterface(a,&IID_IUnknown,(void**)&q));logv(q==a);logv(IUnknown_Release(q));
    q=(IUnknown*)0x1234;hr=IUnknown_QueryInterface(a,&missing,(void**)&q);logv(hr);logv(q==NULL);
    logv(IUnknown_AddRef(a));logv(IUnknown_Release(a));logv(IUnknown_Release(a));logv(IUnknown_Release(b));
    CoUninitialize();return 0;
}
__declspec(dllexport) int probe_uninitialized(void){IUnknown*p=(IUnknown*)0x1234;
    probe_log_n=0;logv(CoCreateInstance(&cls,NULL,3,&iid,(void**)&p));logv(p==NULL);if(p && p!=(IUnknown*)0x1234)IUnknown_Release(p);return 0;}
__declspec(dllexport) int probe_cleanup(void){IUnknown*p;
    probe_log_n=0;logv(CoInitialize(NULL));logv(CoInitialize(NULL));p=create();if(!p)return 1;
    logv(IUnknown_AddRef(p));logv(IUnknown_AddRef(p));return 0;}
__declspec(dllexport) int probe_stale(void){IUnknown*p;CoInitialize(NULL);p=create();if(!p)return 1;IUnknown_Release(p);return IUnknown_AddRef(p);}
__declspec(dllexport) int probe_unsupported(void){IUnknown*p;typedef HRESULT(WINAPI*Fn)(IUnknown*);
    CoInitialize(NULL);p=create();if(!p)return 1;return ((Fn)(*(void***)p)[3])(p);}
__declspec(dllexport) int probe_unbalanced(void){CoUninitialize();return 0;}
static volatile LONG worker_done,worker_result;
static DWORD WINAPI worker(void*param){IUnknown*p;(void)param;logv(CoInitialize(NULL));logv(CoInitialize(NULL));p=create();if(!p){worker_result=1;worker_done=1;return 1;}logv(IUnknown_AddRef(p));worker_done=1;return 0;}
__declspec(dllexport) int probe_worker(void){HANDLE h;DWORD tid;
    probe_log_n=0;h=CreateThread(NULL,0,worker,NULL,0,&tid);if(!h)return 1;
    while(!worker_done)Sleep(1);CloseHandle(h);logv(worker_result);
    logv(CoInitialize(NULL));CoUninitialize();return 0;}
static DWORD WINAPI wrong_worker(void*p){DWORD n=IUnknown_AddRef((IUnknown*)p);worker_done=1;return n;}
__declspec(dllexport) int probe_wrong_thread(void){IUnknown*p;HANDLE h;DWORD tid;
    CoInitialize(NULL);p=create();if(!p)return 1;h=CreateThread(NULL,0,wrong_worker,p,0,&tid);if(!h)return 1;
    while(!worker_done)Sleep(1);CloseHandle(h);IUnknown_Release(p);CoUninitialize();return 0;}

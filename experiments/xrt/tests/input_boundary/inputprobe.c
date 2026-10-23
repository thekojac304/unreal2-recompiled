/* The identical PE32 COM client is run by Windows and by the real lifter. */
#define WIN32_LEAN_AND_MEAN
#define DIRECTINPUT_VERSION 0x0800
#define COBJMACROS
#include <windows.h>
#include <dinput.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllexport) int probe_log[1024], probe_log_n;
static void logv(int v) { probe_log[probe_log_n++] = v; }
static const GUID missing = {0x12345678,0x1234,0x5678,{1,2,3,4,5,6,7,8}};
__declspec(dllexport) int probe_sticky(void) {
    STICKYKEYS keys={sizeof keys,0},saved;
    int wide;
    probe_log_n=0;
    for(wide=0;wide<2;wide++) {
        SetLastError(0x5555);
        logv(wide?SystemParametersInfoW(SPI_GETSTICKYKEYS,8,&keys,0):SystemParametersInfoA(SPI_GETSTICKYKEYS,8,&keys,0));
        logv(GetLastError()); logv(keys.cbSize); saved=keys;
        logv(wide?SystemParametersInfoW(SPI_SETSTICKYKEYS,8,&saved,0):SystemParametersInfoA(SPI_SETSTICKYKEYS,8,&saved,0));
        logv(saved.cbSize); logv(saved.dwFlags==keys.dwFlags);
    }
    return 0;
}
__declspec(dllexport) int probe_creation(void) {
    IDirectInput8W *di = NULL, *q = NULL;
    IUnknown *u = NULL;
    HRESULT hr;
    int i;
    DWORD versions[] = {0x0800,0x0700,0x0801,0};
    probe_log_n=0;
    for(i=0;i<4;i++) {
        di=(IDirectInput8W*)0x55555555;
        hr=DirectInput8Create((HINSTANCE)&__ImageBase,versions[i],&IID_IDirectInput8W,(void**)&di,NULL);
        logv(hr); logv(di!=NULL); logv(di==(IDirectInput8W*)0x55555555);
        if(SUCCEEDED(hr)) {
            logv(IDirectInput8_QueryInterface(di,&IID_IDirectInput8W,(void**)&q));
            logv(q==di); logv(IDirectInput8_Release(q));
            logv(IDirectInput8_QueryInterface(di,&IID_IUnknown,(void**)&u));
            logv((void*)u==(void*)di); logv(IUnknown_Release(u));
            q=(IDirectInput8W*)0x55555555;
            logv(IDirectInput8_QueryInterface(di,&missing,(void**)&q)); logv(q==NULL);
            logv(IDirectInput8_AddRef(di)); logv(IDirectInput8_Release(di));
            logv(IDirectInput8_Release(di));
        }
    }
    di=(IDirectInput8W*)0x55555555;
    logv(DirectInput8Create(NULL,0x0800,&IID_IDirectInput8W,(void**)&di,NULL));
    logv(di==NULL); logv(di==(IDirectInput8W*)0x55555555);
    if(di && di!=(IDirectInput8W*)0x55555555) logv(IDirectInput8_Release(di));
    di=(IDirectInput8W*)0x55555555;
    logv(DirectInput8Create((HINSTANCE)&__ImageBase,0x0800,&missing,(void**)&di,NULL));
    logv(di==NULL); logv(di==(IDirectInput8W*)0x55555555);
    return 0;
}
static IDirectInput8W* create(void) {
    IDirectInput8W*di=NULL;
    HRESULT hr=DirectInput8Create((HINSTANCE)&__ImageBase,0x0800,&IID_IDirectInput8W,(void**)&di,NULL);
    logv(hr);
    return di;
}
__declspec(dllexport) int probe_lifetime(void) {
    IDirectInput8W*a,*b;
    probe_log_n=0;
    a=create(); b=create();
    if(!a || !b) return 1;
    logv(a!=b); logv(IDirectInput8_AddRef(a));
    logv(IDirectInput8_Release(b));
    logv(IDirectInput8_Release(a)); logv(IDirectInput8_Release(a));
    return 0;
}
__declspec(dllexport) int probe_leak(void) {
    IDirectInput8W*di;
    probe_log_n=0; di=create();
    if(!di) return 1;
    logv(IDirectInput8_AddRef(di)); /* translated shutdown must release both references */
    return 0;
}
__declspec(dllexport) int probe_stale(void) {
    IDirectInput8W*di=create();
    IDirectInput8_Release(di);
    return IDirectInput8_AddRef(di);
}
__declspec(dllexport) int probe_unmeasured(void) {
    IDirectInput8W*di=create();
    return IDirectInput8_GetDeviceStatus(di,&GUID_SysMouse);
}
__declspec(dllexport) int probe_ansi(void) {
    IDirectInput8W*di=create(); IDirectInput8A*a=NULL;
    return IDirectInput8_QueryInterface(di,&IID_IDirectInput8A,(void**)&a);
}
__declspec(dllexport) int probe_aggregate(void) {
    IDirectInput8W*di=create(); void*out=NULL;
    return DirectInput8Create((HINSTANCE)&__ImageBase,0x0800,&IID_IDirectInput8W,&out,(IUnknown*)di);
}

/* The original WinDrv trace uses GUID_SysMouse through the 8W factory, the
 * public seven-object c_dfDIMouse, buffer size 1024 and relative-axis mode. */
__declspec(dllexport) int probe_device_creation(void) {
    IDirectInput8W*di;IDirectInputDevice8W*a=NULL,*b=NULL,*q=NULL;IUnknown*u=NULL;
    struct {DWORD before;IDirectInputDevice8W*out;DWORD after;} guarded;
    probe_log_n=0;di=create();if(!di)return 1;
    logv(IDirectInput8_CreateDevice(di,&GUID_SysMouse,&a,NULL));logv(a!=NULL);
    logv(IDirectInput8_CreateDevice(di,&GUID_SysMouse,&b,NULL));logv(a!=b);
    if(!a||!b)return 2;
    logv(IDirectInputDevice8_QueryInterface(a,&IID_IDirectInputDevice8W,(void**)&q));
    logv(q==a);logv(IDirectInputDevice8_Release(q));
    logv(IDirectInputDevice8_QueryInterface(a,&IID_IUnknown,(void**)&u));
    logv((void*)u==(void*)a);logv(IUnknown_Release(u));
    q=(IDirectInputDevice8W*)0x55555555;
    logv(IDirectInputDevice8_QueryInterface(a,&missing,(void**)&q));logv(q==NULL);
    logv(IDirectInputDevice8_AddRef(a));logv(IDirectInputDevice8_Release(a));
    guarded.before=0x13579bdf;guarded.after=0x2468ace0;guarded.out=(IDirectInputDevice8W*)0x55555555;
    logv(IDirectInput8_CreateDevice(di,&missing,&guarded.out,NULL));
    logv(guarded.out==NULL);logv(guarded.out==(IDirectInputDevice8W*)0x55555555);
    logv(guarded.before);logv(guarded.after);
    logv(IDirectInput8_Release(di)); /* devices retain independent native lifetime */
    logv(IDirectInputDevice8_Release(b));logv(IDirectInputDevice8_Release(a));
    return 0;
}
__declspec(dllexport) int probe_device_setup(void) {
    IDirectInput8W*di;IDirectInputDevice8W*d=NULL;DIPROPDWORD property;
    struct {DWORD before;DIDEVICEOBJECTDATA data;DWORD after;} guarded;
    struct {DWORD before,count,after;} count;
    DWORD i;HRESULT hr;
    probe_log_n=0;di=create();if(!di)return 1;
    logv(IDirectInput8_CreateDevice(di,&GUID_SysMouse,&d,NULL));if(!d)return 2;
    logv(c_dfDIMouse.dwFlags);logv(c_dfDIMouse.dwDataSize);logv(c_dfDIMouse.dwNumObjs);
    logv(IDirectInputDevice8_SetDataFormat(d,&c_dfDIMouse));
    property.diph.dwSize=20;property.diph.dwHeaderSize=16;property.diph.dwObj=0;property.diph.dwHow=DIPH_DEVICE;
    property.dwData=1024;logv(IDirectInputDevice8_SetProperty(d,DIPROP_BUFFERSIZE,&property.diph));
    property.dwData=DIPROPAXISMODE_REL;logv(IDirectInputDevice8_SetProperty(d,DIPROP_AXISMODE,&property.diph));
    for(i=0;i<sizeof guarded/4;i++)((volatile DWORD*)&guarded)[i]=0xa5a5a5a5;
    count.before=0x13579bdf;count.count=1;count.after=0x2468ace0;
    hr=IDirectInputDevice8_GetDeviceData(d,sizeof guarded.data,&guarded.data,&count.count,0);
    logv(hr);logv(count.count);logv(count.before);logv(count.after);
    for(i=0;i<sizeof guarded/4;i++)logv(((DWORD*)&guarded)[i]);
    logv(IDirectInputDevice8_Acquire(d));logv(IDirectInputDevice8_Acquire(d));
    /* Zero capacity cannot consume a moving user's events; still exercises the
     * successful acquired API boundary and exact buffer/count preservation. */
    count.count=0;logv(IDirectInputDevice8_GetDeviceData(d,sizeof guarded.data,&guarded.data,&count.count,0));
    logv(count.count);for(i=0;i<sizeof guarded/4;i++)logv(((DWORD*)&guarded)[i]);
    logv(IDirectInputDevice8_Release(d));logv(IDirectInput8_Release(di));return 0;
}
__declspec(dllexport) int probe_device_stale(void) {
    IDirectInput8W*di=create();IDirectInputDevice8W*d=NULL;
    IDirectInput8_CreateDevice(di,&GUID_SysMouse,&d,NULL);IDirectInputDevice8_Release(d);
    return IDirectInputDevice8_AddRef(d);
}
__declspec(dllexport) int probe_device_leak(void) {
    IDirectInput8W*di;IDirectInputDevice8W*d=NULL;
    probe_log_n=0;di=create();if(!di)return 1;
    logv(IDirectInput8_CreateDevice(di,&GUID_SysMouse,&d,NULL));if(!d)return 2;
    logv(IDirectInput8_Release(di));logv(IDirectInputDevice8_AddRef(d));return 0;
}
__declspec(dllexport) int probe_device_unmeasured(void) {
    IDirectInput8W*di=create();IDirectInputDevice8W*d=NULL;
    IDirectInput8_CreateDevice(di,&GUID_SysMouse,&d,NULL);return IDirectInputDevice8_Poll(d);
}

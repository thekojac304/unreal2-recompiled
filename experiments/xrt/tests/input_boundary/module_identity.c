#define WIN32_LEAN_AND_MEAN
#define DIRECTINPUT_VERSION 0x0800
#define COBJMACROS
#include <windows.h>
#include <dinput.h>
#include <stdio.h>
int main(int argc,char**argv) {
    HMODULE m;
    IDirectInput8W *di=NULL;
    HRESULT hr;
    DWORD flags[]={LOAD_LIBRARY_AS_DATAFILE|LOAD_LIBRARY_AS_IMAGE_RESOURCE, DONT_RESOLVE_DLL_REFERENCES};
    int i;
    int failures=0;
    WCHAR path[1024];
    if(argc!=2 || !MultiByteToWideChar(CP_ACP,0,argv[1],-1,path,1024)) return 2;
    for(i=0;i<2;i++) {
        m=LoadLibraryExW(path,NULL,flags[i]);
        if(!m) { DWORD error=GetLastError(); printf("flags=%lx load error=%lu\n",flags[i],error); failures+=i!=1 || error!=ERROR_BAD_EXE_FORMAT; continue; }
        di=NULL;
        hr=DirectInput8Create(m,0x0800,&IID_IDirectInput8W,(void**)&di,NULL);
        printf("flags=%lx HRESULT=%08lx object=%d release=%lu\n",flags[i],hr,di!=NULL,di?IDirectInput8_Release(di):999);
        failures+=i!=0 || hr!=E_INVALIDARG;
        FreeLibrary(m);
    }
    return failures;
}

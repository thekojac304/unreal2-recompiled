/* Read-only initial DirectMusic dependency probe: no audio device or playback. */
#define COBJMACROS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <string.h>
static int guid(const char* text,GUID* out) {
    unsigned i,v; unsigned char* p=(unsigned char*)out;
    if(strlen(text)!=32) return 0;
    for(i=0;i<16;i++) { if(sscanf(text+2*i,"%2x",&v)!=1) return 0; p[i]=(unsigned char)v; }
    return 1;
}
int main(int argc,char** argv) {
    GUID cls[2],iid[2]; HRESULT hr,a,b; IUnknown* object; unsigned i;
    if(argc!=5 || !guid(argv[1],&cls[0]) || !guid(argv[2],&iid[0]) ||
       !guid(argv[3],&cls[1]) || !guid(argv[4],&iid[1]))return 2;
    a=CoInitialize(NULL); b=CoInitialize(NULL);
    printf("CoInitialize %08lx %08lx\n",(unsigned long)a,(unsigned long)b);
    if(FAILED(a) || FAILED(b)) return 3;
    for(i=0;i<2;i++) {
        object=(IUnknown*)(ULONG_PTR)0x1234;
        hr=CoCreateInstance(&cls[i],NULL,3,&iid[i],(void**)&object);
        printf("factory %u hr %08lx output_nonnull %u\n",i,(unsigned long)hr,object!=NULL);
        if(SUCCEEDED(hr)) { if(!object)return 4; IUnknown_Release(object); }
        else if(object) return 5;
    }
    CoUninitialize(); CoUninitialize();
    return 0;
}

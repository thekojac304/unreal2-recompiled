/* Identical PE32 corpus executes natively and through the typed bridge. */
#include "../d3d8_display/probe.c"
#include "corpus.h"
__declspec(dllexport) int probe_depth(void) {
    D8Interface*d=Direct3DCreate8(120),*q=NULL,*b;UINT n,a,k,r,s;
    static const DWORD seeds[]={0,18,0x13572468,0xffffffff};
    HRESULT hr;DWORD error;const UINT*p;
    probe_log_n=0;if(!d)return 1;probe_pointer_object=d;
    n=d->vt->GetAdapterCount(d);logv(n);logv(DEPTH_CASES);
    if((n+5)*DEPTH_CASES*8*10+32>D8_PROBE_LOG_CAPACITY)return 2;
    logv(d->vt->QueryInterface(d,&iid8,(void**)&q));logv(q==d);
    logv(d->vt->AddRef(d));logv(d->vt->Release(d));
    for(a=0;a<n+5;a++)for(k=0;k<DEPTH_CASES;k++)for(r=0;r<2;r++)for(s=0;s<4;s++) {
        UINT adapter=depth_adapter(a,n);p=depth_cases[k];SetLastError(seeds[s]);
        hr=q->vt->CheckDepthStencilMatch(q,adapter,p[0],p[1],p[2],p[3]);error=GetLastError();
        logv(adapter);logv(k);logv(r);logv(seeds[s]);logv(hr);logv(error);
        logv(p[0]);logv(p[1]);logv(p[2]);logv(p[3]);
    }
    logv(q->vt->Release(q));
    b=Direct3DCreate8(120);logv(b!=NULL);if(!b)return 3;logv(b!=d);
    SetLastError(18);hr=b->vt->CheckDepthStencilMatch(b,0,1,22,22,77);error=GetLastError();
    logv(hr);logv(error);logv(b->vt->Release(b));logv(d->vt->Release(d));return 0;
}
#if defined(_M_IX86)
static UINT depth_type,depth_af,depth_rt,depth_ds;
__declspec(naked) static DWORD depth_invoke(void) {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        mov abi_sp,esp
        mov ebp,0x12345678
        mov ebx,0x23456789
        mov esi,0x3456789a
        mov edi,0x456789ab
        push depth_ds
        push depth_rt
        push depth_af
        push depth_type
        push abi_adapter
        push abi_object
        call abi_fn
        mov abi_result,eax
        mov eax,esp
        sub eax,abi_sp
        mov abi_words,eax
        mov abi_words+4,ebp
        mov abi_words+8,ebx
        mov abi_words+12,esi
        mov abi_words+16,edi
        mov esp,abi_sp
        pop edi
        pop esi
        pop ebx
        pop ebp
        mov eax,abi_result
        ret
    }
}
#endif
__declspec(dllexport) int probe_depth_abi(void) {
#if defined(_M_IX86)
    UINT a,k,n;HRESULT hr;DWORD error;const UINT*p;
    probe_log_n=0;abi_object=Direct3DCreate8(120);if(!abi_object)return 1;
    n=abi_object->vt->GetAdapterCount(abi_object);if(n>8)return 2;
    abi_fn=(void*)abi_object->vt->CheckDepthStencilMatch;
    for(a=0;a<n+5;a++)for(k=0;k<DEPTH_CASES;k++) {
        abi_adapter=depth_adapter(a,n);p=depth_cases[k];
        depth_type=p[0];depth_af=p[1];depth_rt=p[2];depth_ds=p[3];SetLastError(18);
        hr=depth_invoke();error=GetLastError();
        logv(abi_adapter);logv(k);logv(hr);logv(error);words(abi_words,5);
    }
    logv(abi_object->vt->Release(abi_object));return 0;
#else
    return 99;
#endif
}
__declspec(dllexport) int probe_depth_stale(void) {
    D8Interface*d=Direct3DCreate8(120);d->vt->Release(d);return d->vt->CheckDepthStencilMatch(d,0,1,22,22,77);
}

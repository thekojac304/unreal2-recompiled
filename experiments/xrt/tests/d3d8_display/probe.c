/* The same PE32 code executes natively and through the typed guest bridge. */
#include "../d3d8_enum/probe.c"
__declspec(dllexport) int probe_display(void) {
    D8Interface*d=Direct3DCreate8(120),*q=NULL,*b;UINT n,a,r,s;
    static const DWORD seeds[]={0,18,0x13572468,0xffffffff};
    struct {DWORD before[4];D8Mode value;DWORD after[4];} m;
    HRESULT hr;DWORD error;
    probe_log_n=0;if(!d)return 1;probe_pointer_object=d;
    logv(sizeof(D8Mode));logv(offsetof(D8Mode,width));logv(offsetof(D8Mode,height));
    logv(offsetof(D8Mode,refresh));logv(offsetof(D8Mode,format));
    n=d->vt->GetAdapterCount(d);logv(n);if(n>8)return 2;
    logv(d->vt->QueryInterface(d,&iid8,(void**)&q));logv(q==d);
    logv(d->vt->AddRef(d));logv(d->vt->Release(d));
    for(a=0;a<n+5;a++)for(r=0;r<4;r++)for(s=0;s<4;s++) {
        UINT adapter=a<n+2?a:(a==n+2?0xffff:(a==n+3?0x7fffffff:0xffffffff));
        fill(&m,sizeof m);SetLastError(seeds[s]);
        hr=q->vt->GetAdapterDisplayMode(q,adapter,&m.value);error=GetLastError();
        logv(adapter);logv(r);logv(seeds[s]);logv(hr);logv(error);
        words(&m.value,4);words(m.before,4);words(m.after,4);
    }
    logv(q->vt->Release(q));
    b=Direct3DCreate8(120);logv(b!=NULL);if(!b)return 3;logv(b!=d);
    fill(&m,sizeof m);SetLastError(18);hr=b->vt->GetAdapterDisplayMode(b,0,&m.value);error=GetLastError();
    logv(hr);logv(error);words(&m.value,4);words(m.before,4);words(m.after,4);
    logv(b->vt->Release(b));logv(d->vt->Release(d));return 0;
}
#if defined(_M_IX86)
__declspec(naked) static DWORD display_invoke(void) {
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
        push abi_output
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
__declspec(dllexport) int probe_display_abi(void) {
#if defined(_M_IX86)
    UINT a,r,n;D8Mode m;HRESULT hr;DWORD error;
    probe_log_n=0;abi_object=Direct3DCreate8(120);if(!abi_object)return 1;
    n=abi_object->vt->GetAdapterCount(abi_object);if(n>8)return 2;
    abi_fn=(void*)abi_object->vt->GetAdapterDisplayMode;abi_output=&m;
    for(a=0;a<n+2;a++)for(r=0;r<4;r++) {
        abi_adapter=a<n+1?a:0xffffffff;fill(&m,16);SetLastError(18);
        hr=display_invoke();error=GetLastError();
        logv(abi_adapter);logv(hr);logv(error);words(abi_words,5);words(&m,4);
    }
    logv(abi_object->vt->Release(abi_object));return 0;
#else
    return 99;
#endif
}
__declspec(dllexport) int probe_display_null(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->GetAdapterDisplayMode(d,0,NULL);
}
__declspec(dllexport) int probe_display_bad_range(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->GetAdapterDisplayMode(d,0,(D8Mode*)0x00300000);
}
__declspec(dllexport) int probe_display_wrap(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->GetAdapterDisplayMode(d,0,(D8Mode*)(ULONG_PTR)0xfffffff8);
}
__declspec(dllexport) int probe_display_stale(void) {
    D8Mode m;D8Interface*d=Direct3DCreate8(120);d->vt->Release(d);return d->vt->GetAdapterDisplayMode(d,0,&m);
}

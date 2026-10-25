/* Extend the retained query/ownership fixture; enumeration is native-only. */
#define probe_leak probe_old_leak
#define D8_PROBE_LOG_CAPACITY 32768
#include "../d3d8_boundary/probe.c"
#undef probe_leak
static D8Interface* leaked;
__declspec(dllexport) D8Interface* probe_pointer_object;
__declspec(dllexport) int probe_leak(void) {
    leaked=Direct3DCreate8(120);probe_log_n=0;logv(leaked!=NULL);
    probe_pointer_object=leaked;
    if(!leaked)return 1;logv(leaked->vt->AddRef(leaked));return 0;
}
__declspec(dllexport) int probe_native_cleanup(void) {
    ULONG n=0;if(leaked){leaked->vt->Release(leaked);n=leaked->vt->Release(leaked);leaked=NULL;}return (int)n;
}
__declspec(dllexport) int probe_modes(void) {
    D8Interface*d=Direct3DCreate8(120),*q=NULL,*b;
    UINT n,a,r;
    probe_log_n=0;logv(d!=NULL);if(!d)return 1;
    probe_pointer_object=d;
    n=d->vt->GetAdapterCount(d);logv(n);if(n>8){d->vt->Release(d);return 2;}
    for(r=0;r<8;r++) {
        for(a=0;a<n;a++){logv(a);logv(d->vt->GetAdapterModeCount(d,a));}
    }
    logv(d->vt->QueryInterface(d,&iid8,(void**)&q));logv(q==d);
    logv(q->vt->GetAdapterModeCount(q,0));logv(q->vt->Release(q));
    b=Direct3DCreate8(120);logv(b!=NULL);if(!b){d->vt->Release(d);return 3;}
    logv(b!=d);logv(b->vt->GetAdapterModeCount(b,0));logv(b->vt->Release(b));
    logv(d->vt->GetAdapterModeCount(d,0));logv(d->vt->Release(d));return 0;
}
static D8Interface* abi_object;
static UINT abi_adapter,abi_index;
static D8Mode* abi_output;
static void* abi_fn;
static DWORD abi_sp,abi_result,abi_words[5];
#if defined(_M_IX86)
__declspec(naked) static DWORD abi_invoke(void) {
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
        cmp abi_index,0xfffffffe
        je count_call
        push abi_output
        push abi_index
    count_call:
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
__declspec(dllexport) int probe_count_abi(void) {
#if defined(_M_IX86)
    UINT i,n;abi_object=Direct3DCreate8(120);probe_log_n=0;if(!abi_object)return 1;
    n=abi_object->vt->GetAdapterCount(abi_object);if(n>8)return 2;
    abi_fn=(void*)abi_object->vt->GetAdapterModeCount;abi_index=0xfffffffe;
    for(i=0;i<n*4;i++) {
        abi_adapter=i%n;
        logv(abi_adapter);logv(abi_invoke());words(abi_words,5);
    }
    logv(abi_object->vt->Release(abi_object));return 0;
#else
    return 99; /* x86 guest ABI is measured on native x86 and translated x64. */
#endif
}
/* Log every native display mode twice, plus immediate invalid-index outputs.
 * A hard log bound stops characterization rather than truncating evidence. */
__declspec(dllexport) int probe_enumeration(void) {
    D8Interface*d=Direct3DCreate8(120);UINT n,a,c,i,r;HRESULT hr;
    struct {DWORD before;D8Mode value;DWORD after;} m;
    probe_log_n=0;if(!d)return 1;
    logv(sizeof(D8Mode));logv(offsetof(D8Mode,width));logv(offsetof(D8Mode,height));
    logv(offsetof(D8Mode,refresh));logv(offsetof(D8Mode,format));
    n=d->vt->GetAdapterCount(d);logv(n);if(n>8){d->vt->Release(d);return 2;}
    for(a=0;a<n+3;a++) {
        UINT adapter=a<n+1?a:(a==n+1?0xffff:0xffffffff);
        c=a<n?d->vt->GetAdapterModeCount(d,adapter):0;
        logv(adapter);logv(a<n);logv(c);
        if((c+2)*16u>(D8_PROBE_LOG_CAPACITY-(UINT)probe_log_n)){d->vt->Release(d);return 4;}
        for(r=0;r<2;r++)for(i=0;i<c+2;i++) {
            UINT index=i==c+1?0xffffffff:i;
            m.before=0x11223344;m.after=0x55667788;fill(&m.value,sizeof m.value);
            hr=d->vt->EnumAdapterModes(d,adapter,index,&m.value);
            logv(index);logv(hr);words(&m.value,4);logv(m.before);logv(m.after);
        }
    }
    logv(d->vt->Release(d));return 0;
}
__declspec(dllexport) int probe_enum_abi(void) {
#if defined(_M_IX86)
    D8Mode m;UINT i;static const UINT adapters[]={0,0,0xffff,0xffffffff};
    abi_object=Direct3DCreate8(120);probe_log_n=0;if(!abi_object)return 1;
    abi_fn=(void*)abi_object->vt->EnumAdapterModes;abi_output=&m;
    for(i=0;i<4;i++) {
        abi_adapter=adapters[i];abi_index=i==1?0xffffffff:0;fill(&m,sizeof m);
        logv(abi_invoke());words(abi_words,5);words(&m,4);
    }
    logv(abi_object->vt->Release(abi_object));return 0;
#else
    return 99;
#endif
}
__declspec(dllexport) int probe_enum_guard(void) {
    D8Mode m;D8Interface*d=Direct3DCreate8(120);return d->vt->EnumAdapterModes(d,0,0,&m);
}
__declspec(dllexport) int probe_device_guard(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->CreateDevice(d,0,1,NULL,0,NULL,NULL);
}
__declspec(dllexport) int probe_mode_stale(void) {
    D8Interface*d=Direct3DCreate8(120);d->vt->Release(d);return (int)d->vt->GetAdapterModeCount(d,0);
}
__declspec(dllexport) int probe_invalid_count(void) {
    D8Interface*d=Direct3DCreate8(120);return (int)d->vt->GetAdapterModeCount(d,d->vt->GetAdapterCount(d));
}
__declspec(dllexport) int probe_invalid_next(void) {
    D8Interface*d=Direct3DCreate8(120);return (int)d->vt->GetAdapterModeCount(d,d->vt->GetAdapterCount(d)+1);
}
__declspec(dllexport) int probe_invalid_ffff(void) {
    D8Interface*d=Direct3DCreate8(120);return (int)d->vt->GetAdapterModeCount(d,0xffff);
}
__declspec(dllexport) int probe_invalid_7fffffff(void) {
    D8Interface*d=Direct3DCreate8(120);return (int)d->vt->GetAdapterModeCount(d,0x7fffffff);
}
__declspec(dllexport) int probe_invalid_ffffffff(void) {
    D8Interface*d=Direct3DCreate8(120);return (int)d->vt->GetAdapterModeCount(d,0xffffffff);
}

/* Same PE32 fixture runs natively and lifted; retain all prior COM/count probes. */
#include "../d3d8_modes/probe.c"
__declspec(dllexport) int probe_enum_last_error(void) {
    D8Interface*d=Direct3DCreate8(120),*q=NULL;UINT n,a,r,i,count;
    static const DWORD seeds[]={0,0x13572468,0xffffffff};
    struct {DWORD before;D8Mode value;DWORD after;} m;
    HRESULT hr;DWORD error;
    probe_log_n=0;if(!d)return 1;
    n=d->vt->GetAdapterCount(d);if(n>8)return 2;
    logv(d->vt->QueryInterface(d,&unknown,(void**)&q));logv(q==d);
    for(a=0;a<n+5;a++) {
        UINT adapter=a<n+2?a:(a==n+2?0xffff:(a==n+3?0x7fffffff:0xffffffff));
        count=a<n?d->vt->GetAdapterModeCount(d,adapter):0;
        for(r=0;r<3;r++)for(i=0;i<4;i++) {
            UINT index=i==0?0:(i==1?(count?count-1:0):(i==2?count:0xffffffff));
            m.before=0x11223344;m.after=0x55667788;fill(&m.value,16);
            SetLastError(seeds[r]);
            hr=q->vt->EnumAdapterModes(q,adapter,index,&m.value);error=GetLastError();
            logv(adapter);logv(index);logv(seeds[r]);logv(hr);logv(error);
            words(&m.value,4);logv(m.before);logv(m.after);
        }
    }
    logv(q->vt->Release(q));logv(d->vt->Release(d));return 0;
}
__declspec(dllexport) int probe_enum_full_abi(void) {
#if defined(_M_IX86)
    UINT a,i,n,count;struct {DWORD before;D8Mode value;DWORD after;} m;
    abi_object=Direct3DCreate8(120);probe_log_n=0;if(!abi_object)return 1;
    n=abi_object->vt->GetAdapterCount(abi_object);if(n>8)return 2;
    abi_fn=(void*)abi_object->vt->EnumAdapterModes;abi_output=&m.value;
    for(a=0;a<n+3;a++) {
        abi_adapter=a<n+1?a:(a==n+1?0xffff:0xffffffff);
        count=a<n?abi_object->vt->GetAdapterModeCount(abi_object,a):0;
        for(i=0;i<4;i++) {
            abi_index=i==0?0:(i==1?(count?count-1:0):(i==2?count:0xffffffff));
            m.before=0x11223344;m.after=0x55667788;fill(&m.value,16);
            logv(abi_adapter);logv(abi_index);logv(abi_invoke());words(abi_words,5);
            words(&m.value,4);logv(m.before);logv(m.after);
        }
    }
    logv(abi_object->vt->Release(abi_object));return 0;
#else
    return 99;
#endif
}
__declspec(dllexport) int probe_enum_null(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->EnumAdapterModes(d,0,0,NULL);
}
__declspec(dllexport) int probe_enum_bad_range(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->EnumAdapterModes(d,0,0,(D8Mode*)0x00300000);
}
__declspec(dllexport) int probe_enum_wrap(void) {
    D8Interface*d=Direct3DCreate8(120);return d->vt->EnumAdapterModes(d,0,0,(D8Mode*)(ULONG_PTR)0xfffffff8);
}
__declspec(dllexport) int probe_enum_stale(void) {
    D8Mode m;D8Interface*d=Direct3DCreate8(120);d->vt->Release(d);return d->vt->EnumAdapterModes(d,0,0,&m);
}

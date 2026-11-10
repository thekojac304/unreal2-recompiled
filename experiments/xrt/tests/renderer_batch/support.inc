/* Boundary fixture services. Deliberate doubles; no OS callback qualification. */
#include "xrt_internal.h"
#include "d3d8_device_abi.h"
#include <xmmintrin.h>
#include <stdlib.h>
typedef struct D8Object { uint32_t guest,refs,children,pending;D8Interface*host; } D8Object;
static jmp_buf stop;
static int physical_guard;
static unsigned checks,failures,native_calls,enters,leaves,callback_count;
static int fatal_code,inside_adapter,nested_mode;
static DWORD guest_error,host_error;
static HRESULT host_result;
static CPU* active;
static CPU suspended;
static char fatal_message[512];
uint8_t* xrt_g;
__declspec(thread) XrtThread* xrt_cur;
#define CHECK(x) do { checks++;if(!(x)){fprintf(stderr,"check failed %s line %d\n",#x,__LINE__);if(physical_guard)longjmp(stop,1);ExitProcess(91);} }while(0)
XRT_NORETURN void xrt_fatal(CPU*c,int code,const char*fmt,...){va_list ap;(void)c;fatal_code=code;va_start(ap,fmt);vsnprintf(fatal_message,sizeof fatal_message,fmt,ap);va_end(ap);longjmp(stop,1);}
void xrt_event(const char*k,const char*f,...){(void)k;(void)f;}
uint32_t xrt_get_last_error(CPU*c){(void)c;return guest_error;}
void xrt_set_last_error(CPU*c,uint32_t e){(void)c;guest_error=e;}
int xrt_is_committed(uint32_t p,uint32_t n){return p>=0x1000&&(uint64_t)p+n<=0x20000;}
CPU* xrt_gui_callback_enter(CPU*c){CPU*p=active;active=c;enters++;return p;}
void xrt_gui_callback_leave(CPU*p){active=p;leaves++;}
static HWND fixture_window;
void* xrt_gui_device_window(CPU*c,uint32_t token){if(token!=0x1234)xrt_fatal(c,76,"test invalid window identity");return fixture_window?fixture_window:(void*)(uintptr_t)0x5678;}
void xrt_gui_window_unpin(uint32_t t){CHECK(t==0x1234);}
static const GUID com_iunknown={0};
static uint32_t com_vtable(const char**names,unsigned n){(void)names;(void)n;abort();}
static D8Object* d8_object(CPU*c,uint32_t p){(void)c;(void)p;abort();}
static void d8_words(const char*n,const void*p,unsigned c){(void)n;(void)p;(void)c;}
#include "hle_d3d8_device.inc"
static D8DeviceVtable vt;
static D8Device double_device={&vt};
static D8Object parent;
static D8Device* fixture_device=&double_device;
static int graphics,emit_calls;
static BYTE input_before[1536];
static unsigned input_size;
static unsigned fixture_slot;
static int readonly_input;
static uint32_t input_address=0x5000;
static void setup(CPU*c){
    fixture_slot=batch_case->slot;
    unsigned i;memset(c,0,sizeof *c);
    for(i=0;i<8;i++){c->r[i]=0x76543210+i;c->st[i]=i+0.5;}
    c->r[ESP]=0x2000;c->fcw=0x27f;c->fsw=0x4020;c->top=6;c->cf=1;c->df=1;
    c->pc=batch_case->site;c->hist[10]=0x1234;c->hpos=11;
    memset(&d8_device,0,sizeof d8_device);memset(&parent,0,sizeof parent);
    parent.children=1;parent.refs=1;d8_device.guest=0x4000;d8_device.refs=1;
    d8_device.host=fixture_device;d8_device.parent=&parent;d8_device.focus=d8_device.window=0x1234;
    memset(G2H(0x2000),0,64);wr32(0x2000,0x34567890);wr32(0x2004,0x4000);
    wr32(0x2008,batch_case->a);wr32(0x200c,batch_case->b);wr32(0x2010,batch_case->c);
    input_size=0;
    if(batch_case->slot==37){input_size=64;memcpy(G2H(input_address),batch_identity,64);wr32(0x200c,input_address);}
    if(batch_case->slot==18){input_size=1536;memcpy(G2H(input_address),batch_ramp,1536);wr32(0x200c,input_address);}
#if BATCH_GROUP==9
    {c->r[ECX]=batch_viewport;wr32(batch_viewport,0x9000);wr32(0x9088,batch_resize_target);
        wr32(0x2004,batch_case->a);wr32(0x2008,batch_case->b);wr32(0x200c,batch_case->c);}
#endif
    if(input_size)memcpy(input_before,G2H(input_address),input_size);
    active=NULL;enters=leaves=native_calls=0;fatal_code=0;d8_rendering=0;d8_native_failed=0;
}
static void dispatch(CPU*c){
#if BATCH_GROUP==1 || BATCH_GROUP==3
    d8_device_SetRenderState(c);
#elif BATCH_GROUP==2 || BATCH_GROUP==5
    d8_device_SetTextureStageState(c);
#elif BATCH_GROUP==4
    d8_device_SetTransform(c);
#elif BATCH_GROUP==6
    if(fixture_slot==61)d8_device_SetTexture(c);else if(fixture_slot==83)d8_device_SetStreamSource(c);else d8_device_SetIndices(c);
#elif BATCH_GROUP==7
    d8_device_SetVertexShader(c);
#elif BATCH_GROUP==8
    d8_device_SetGammaRamp(c);
#elif BATCH_GROUP==9
    batch_ResizeViewport(c);
#endif
}
static unsigned nargs(void){return batch_case->slot==63||batch_case->slot==83?4:batch_case->slot==76?2:3;}
static DWORD translated_call(void){
    CPU cpu,expected;BYTE frame[64];DWORD value,old=0;uint32_t protect_base=input_address&~4095u;
    setup(&cpu);suspended=cpu;expected=cpu;memcpy(frame,G2H(0x2000),64);
    expected.rv=rd32(0x2000);expected.r[ESP]+=4*(nargs()+1);
    if(readonly_input&&input_size)CHECK(VirtualProtect(G2H(protect_base),8192,PAGE_READONLY,&old));
    inside_adapter=1;dispatch(&cpu);inside_adapter=0;
    if(readonly_input&&input_size)CHECK(VirtualProtect(G2H(protect_base),8192,old,&old));
    value=cpu.r[EAX];expected.r[EAX]=batch_case->slot==18?expected.r[EAX]:value;
    CHECK(!memcmp(&cpu,&expected,sizeof cpu));CHECK(!memcmp(frame,G2H(0x2000),64));
    if(input_size)CHECK(!memcmp(input_before,G2H(input_address),input_size));
    CHECK(!active&&!d8_rendering);CHECK(enters==leaves);CHECK(d8_device.refs==1);
    SetLastError(guest_error);return value;
}
static DWORD WINAPI wrap2(uintptr_t d,uintptr_t a){CHECK((D8Device*)d==fixture_device);CHECK(a==batch_case->a);guest_error=GetLastError();return translated_call();}
static DWORD WINAPI wrap3(uintptr_t d,uintptr_t a,uintptr_t b){(void)b;CHECK((D8Device*)d==fixture_device);CHECK(a==batch_case->a);guest_error=GetLastError();return translated_call();}
static DWORD WINAPI wrap4(uintptr_t d,uintptr_t a,uintptr_t b,uintptr_t c){CHECK((D8Device*)d==fixture_device);CHECK(a==batch_case->a&&b==batch_case->b&&c==batch_case->c);guest_error=GetLastError();return translated_call();}
static void host_enter(D8Device*d){
    CHECK(d==&double_device);native_calls++;
    if(inside_adapter){CPU saved;CHECK(active!=NULL&&d8_rendering);CHECK(!memcmp(active,&suspended,sizeof suspended));
        saved=*active;callback_count++;active->r[EAX]^=1;active->st[3]=17.5;*active=saved;
        CHECK(!memcmp(active,&suspended,sizeof suspended));
        if(nested_mode==1)dispatch(active);if(nested_mode==2)d8_device_Release(active);
    }
}
static HRESULT WINAPI state(D8Device*d,DWORD a,DWORD b){host_enter(d);CHECK(a==batch_case->a&&b==batch_case->b);SetLastError(host_error);return host_result;}
static HRESULT WINAPI stage_state(D8Device*d,DWORD a,DWORD b,DWORD c){host_enter(d);CHECK(a==batch_case->a&&b==batch_case->b&&c==batch_case->c);SetLastError(host_error);return host_result;}
static HRESULT WINAPI transform(D8Device*d,DWORD a,const D8Matrix*p){host_enter(d);CHECK(a==batch_case->a);CHECK(!memcmp(p,batch_identity,64));if(inside_adapter)CHECK((const BYTE*)p<xrt_g||(const BYTE*)p>=xrt_g+0x20000);SetLastError(host_error);return host_result;}
static HRESULT WINAPI texture(D8Device*d,DWORD a,void*p){host_enter(d);CHECK(a==batch_case->a&&!p);SetLastError(host_error);return host_result;}
static HRESULT WINAPI stream(D8Device*d,DWORD a,void*p,DWORD stride){host_enter(d);CHECK(a==batch_case->a&&!p&&!stride);SetLastError(host_error);return host_result;}
static HRESULT WINAPI indices(D8Device*d,void*p,DWORD base){host_enter(d);CHECK(!p&&!base);SetLastError(host_error);return host_result;}
static HRESULT WINAPI fvf(D8Device*d,DWORD a){host_enter(d);CHECK(a==2);SetLastError(host_error);return host_result;}
static void WINAPI gamma_set(D8Device*d,DWORD flags,const D8Gamma*p){host_enter(d);CHECK(flags==1);CHECK(!memcmp(p,batch_ramp,1536));if(inside_adapter)CHECK((const BYTE*)p<xrt_g||(const BYTE*)p>=xrt_g+0x20000);SetLastError(host_error);}
#if BATCH_GROUP==9
static uint32_t resize_callback(CPU*c,uint32_t target,uint32_t flags,uint32_t width,uint32_t height){
    CPU saved=*c;CHECK(target==0x11104f20&&flags==batch_case->a&&width==1540&&height==945);
    CHECK(c->r[ECX]==0x8000);callback_count++;c->r[EBX]^=1;c->fsw^=0x20;*c=saved;
    CHECK(!memcmp(c,&saved,sizeof saved));return (DWORD)host_result;
}
#endif
static void negative(CPU*c){CPU before=*c;BYTE frame[64];unsigned previous_calls=native_calls;
    memcpy(frame,G2H(0x2000),64);
    if(!setjmp(stop)){inside_adapter=1;dispatch(c);fprintf(stderr,"missing strict rejection\n");ExitProcess(92);}
    inside_adapter=0;CHECK(fatal_code==76);CHECK(!memcmp(c,&before,sizeof before));CHECK(!memcmp(frame,G2H(0x2000),64));CHECK(native_calls==previous_calls);
}
static void negatives(void){
    CPU c;DWORD old;unsigned i;const BatchCase* sealed=batch_case;
    setup(&c);batch_case=NULL;negative(&c);batch_case=sealed;
    setup(&c);wr32(0x2004,0);if(BATCH_GROUP==9)c.r[ECX]=1;negative(&c);
    setup(&c);d8_device.refs=0;if(BATCH_GROUP==9)wr32(0x9088,0x11104f21);negative(&c);
    setup(&c);if(BATCH_GROUP==9)wr32(0x8000,0x9004);else d8_rendering=1;negative(&c);
    setup(&c);if(BATCH_GROUP==9)wr32(0x2004,18);else wr32(0x2008,batch_case->a^0x40000000);negative(&c);
#if BATCH_GROUP==9
    setup(&c);batch_guest_invoke=NULL;negative(&c);
    batch_guest_invoke=resize_callback;
#else
    setup(&c);d8_device.window=0x4444;negative(&c);
#endif
    setup(&c);c.r[ESP]=0xfffffff0;negative(&c);
    setup(&c);c.r[ESP]=0x7000-8;CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_NOACCESS,&old));negative(&c);CHECK(VirtualProtect(G2H(0x7000),4096,PAGE_READWRITE,&old));
    if(BATCH_GROUP!=9){
        setup(&c);d8_device.host=NULL;negative(&c);
        setup(&c);d8_device.focus=d8_device.window=0x4444;negative(&c);
        if(batch_case->slot!=76&&batch_case->slot!=18&&batch_case->slot!=37){setup(&c);wr32(0x200c,rd32(0x200c)^1);negative(&c);}
        if(batch_case->slot==63||batch_case->slot==83){setup(&c);wr32(0x2010,rd32(0x2010)^1);negative(&c);}
    }
    if(batch_case->slot==37||batch_case->slot==18){
        const DWORD bad[]={0,1,0xfffffff0,0x30000};
        for(i=0;i<4;i++){setup(&c);wr32(0x200c,bad[i]);negative(&c);}
        setup(&c);wr32(0x5000,rd32(0x5000)^1);negative(&c);
        setup(&c);wr32(0x200c,0x6000-input_size+2);memcpy(G2H(0x6000-input_size+2),input_before,input_size);
        CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_NOACCESS,&old));negative(&c);CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_READWRITE,&old));
        setup(&c);CHECK(VirtualProtect(G2H(0x5000),4096,PAGE_GUARD|PAGE_READWRITE,&old));negative(&c);CHECK(VirtualProtect(G2H(0x5000),4096,PAGE_READWRITE,&old));
    }
}
static void extra_contracts(void){
    CPU c;unsigned i;
    if(batch_case->slot==37||batch_case->slot==18){
        input_address=0x6000-16;readonly_input=1;host_result=S_OK;host_error=18;guest_error=18;
        CHECK(translated_call()==(batch_case->slot==18?0x76543210u:0));
        readonly_input=0;input_address=0x5000;
    }
    if(BATCH_GROUP!=9)for(i=1;i<=2;i++){
        setup(&c);suspended=c;nested_mode=(int)i;inside_adapter=1;
        if(!setjmp(stop)){dispatch(&c);fprintf(stderr,"missing callback reentry rejection\n");ExitProcess(93);}
        CHECK(fatal_code==76);CHECK(strstr(fatal_message,i==1?"reentrant":"Release during")!=NULL);
        CHECK(native_calls==1&&d8_device.refs==1&&enters==1&&leaves==0);
        nested_mode=0;inside_adapter=0;
    }
}

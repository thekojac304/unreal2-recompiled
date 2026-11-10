/* Declared COM protocol doubles. No backend DLL, GPU, game EXE or game DLL.
 * This checks the actual integrated adapters, not a parallel implementation.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xrt_internal.h"
#include "d3d8_device_abi.h"
#include <xmmintrin.h>
typedef struct D8Object {uint32_t guest,refs,children,pending;D8Interface*host;} D8Object;
static unsigned checks,native_calls,events_count,negative_count,enters,leaves;
static uint32_t guest_capacity=0x20000;
static unsigned cache_calls,caps_queries;
static unsigned hash=2166136261u,slot,a,b,d,input_size;
static BYTE input[1536];
static DWORD guest_error,host_error;
static HRESULT host_result;
static jmp_buf stop;
static CPU*active;
static CPU suspended;
static int reenter,allow_fatal,failed_code;
static int trace_callback,trace_corrupt;
static int trace_events;
static int optional_focus;
uint8_t*xrt_g;
__declspec(thread) XrtThread*xrt_cur;
#define CHECK(v) do {checks++;if(!(v)){fprintf(stderr,"check line %d: %s\n",__LINE__,#v);ExitProcess(91);}}while(0)
XRT_NORETURN void xrt_fatal(CPU*c,int code,const char*fmt,...) {
    va_list ap;(void)c;failed_code=code;
    if(!allow_fatal){va_start(ap,fmt);vfprintf(stderr,fmt,ap);va_end(ap);ExitProcess(92);}
    longjmp(stop,1);
}
void xrt_event(const char*k,const char*f,...){
    char buf[4096];int n,m;va_list ap;events_count++;
    n=snprintf(buf,sizeof buf,"{\"seq\": %u, \"thread\": -1, \"kind\": \"%s\", ",events_count,k);
    va_start(ap,f);m=vsnprintf(buf+n,sizeof buf-n-2,f,ap);va_end(ap);
    if(m<0 || n+m+2>448){fprintf(stderr,"event truncation: %s size %d\n",k,n+m+2);ExitProcess(93);}
    if(trace_events){FILE*out;buf[n+m]='}';buf[n+m+1]=0;if(!fopen_s(&out,"runtime-protocol.jsonl","a")){fprintf(out,"%s\n",buf);fclose(out);}}
}
uint32_t xrt_get_last_error(CPU*c){(void)c;return guest_error;}
void xrt_set_last_error(CPU*c,uint32_t e){guest_error=e;if(c->fs_base)wr32(c->fs_base+0x34,e);}
int xrt_is_committed(uint32_t p,uint32_t n){return p>=0x1000&&(uint64_t)p+n<=guest_capacity;}
CPU*xrt_gui_callback_enter(CPU*c){CPU*p=active;active=c;enters++;return p;}
void xrt_gui_callback_leave(CPU*p){active=p;leaves++;}
void*xrt_gui_device_window(CPU*c,uint32_t p){if(!p)return NULL;if(p!=0x1234&&p!=0x1235)xrt_fatal(c,76,"unknown window");return(void*)(uintptr_t)p;}
void xrt_gui_window_unpin(uint32_t p){(void)p;}
static const GUID com_iunknown={0};
static const char**owned_slots;
uint32_t xrt_hle_proc(const char*dll,const char*name){unsigned i;CHECK(!strcmp(dll,"xrt.com"));for(i=0;i<97;i++)if(!strcmp(name,owned_slots[i]))return 0x9000+4*i;return 0;}
static uint32_t com_vtable(const char**n,unsigned s){unsigned i;CHECK(s==97);owned_slots=n;for(i=0;i<s;i++)wr32(0x10000+4*i,xrt_hle_proc("xrt.com",n[i]));return 0x10000;}
uint32_t xrt_rt_alloc(uint32_t size,uint32_t align){CHECK(size==4&&align==4);memset(G2H(0x11000),0,size);return 0x11000;}
void xrt_gui_window_pin(CPU*c,uint32_t p){(void)xrt_gui_device_window(c,p);}
uint32_t xrt_gui_window_identity(CPU*c,void*p){uint32_t v=(uint32_t)(uintptr_t)p;CHECK((uintptr_t)p==v);(void)xrt_gui_device_window(c,v);return v;}
static D8Object parent;
static D8Object*d8_object(CPU*c,uint32_t p){if(p==parent.guest&&parent.refs)return &parent;xrt_fatal(c,76,"unknown parent");}
static void d8_result(CPU*c,const char*m,D8Object*p,uint32_t a,uint32_t b,HRESULT hr){(void)c;(void)m;(void)p;(void)a;(void)b;(void)hr;}
static void d8_words(const char*n,const void*p,unsigned s){(void)n;(void)p;(void)s;}
#include "hle_d3d8_device.inc"
#include "cases.inc"
static D8DeviceVtable vt;
static D8Device host={&vt};
static DWORD caps[53];
static void dispatch(CPU*c){switch(slot){
 case 18:d8_device_SetGammaRamp(c);break;case 37:d8_device_SetTransform(c);break;
 case 42:d8_device_SetMaterial(c);break;case 50:d8_device_SetRenderState(c);break;
 case 61:d8_device_SetTexture(c);break;case 63:d8_device_SetTextureStageState(c);break;
 case 76:d8_device_SetVertexShader(c);break;case 83:d8_device_SetStreamSource(c);break;
 case 85:d8_device_SetIndices(c);break;case 36:d8_device_Clear(c);break;default:abort();}}
static unsigned nargs(void){return slot==36?7:slot==63||slot==83?4:slot==76||slot==42?2:3;}
__declspec(noinline) static void invoke_gui_proc(CPU*c){CPU saved=*c;c->r[EAX]^=1;c->st[3]=2.5;*c=saved;}
static void host_enter(D8Device*p) {
    CPU saved;
    CHECK(p==&host);native_calls++;CHECK(active&&d8_rendering);CHECK(!memcmp(active,&suspended,sizeof suspended));
    saved=*active;active->r[EAX]^=1;active->st[3]=17.5;*active=saved;
    if(trace_callback)invoke_gui_proc(active);
    if(trace_corrupt)active->r[EBX]^=1;
    if(reenter==1)dispatch(active);
    if(reenter==2)d8_device_Release(active);
}
static HRESULT WINAPI getcaps(D8Device*p,D8Caps*q){CHECK(p==&host&&active&&d8_rendering);caps_queries++;memcpy(q,caps,sizeof caps);SetLastError(0xbadc0de);return S_OK;}
static HRESULT WINAPI state(D8Device*p,DWORD s,DWORD v){host_enter(p);CHECK(slot==50&&s==a&&v==b);SetLastError(host_error);return host_result;}
static HRESULT WINAPI stage(D8Device*p,DWORD s,DWORD t,DWORD v){host_enter(p);CHECK(slot==63&&s==a&&t==b&&v==d);SetLastError(host_error);return host_result;}
static void local_pointer(const void*p){CHECK((const BYTE*)p<xrt_g || (const BYTE*)p>=xrt_g+guest_capacity);CHECK(!memcmp(p,input,input_size));}
static HRESULT WINAPI matrix(D8Device*p,DWORD s,const D8Matrix*q){host_enter(p);CHECK(slot==37&&s==a);local_pointer(q);SetLastError(host_error);return host_result;}
static HRESULT WINAPI material(D8Device*p,const D8Material*q){host_enter(p);CHECK(slot==42);local_pointer(q);SetLastError(host_error);return host_result;}
static void WINAPI gamma_set(D8Device*p,DWORD f,const D8Gamma*q){host_enter(p);CHECK(slot==18&&f==a);local_pointer(q);SetLastError(host_error);}
static HRESULT WINAPI texture(D8Device*p,DWORD s,void*q){host_enter(p);CHECK(slot==61&&s==a&&!q);SetLastError(host_error);return host_result;}
static HRESULT WINAPI stream(D8Device*p,DWORD s,void*q,DWORD stride){host_enter(p);CHECK(slot==83&&s==a&&!q&&stride==d);SetLastError(host_error);return host_result;}
static HRESULT WINAPI indices(D8Device*p,void*q,DWORD base){host_enter(p);CHECK(slot==85&&!q&&base==b);SetLastError(host_error);return host_result;}
static HRESULT WINAPI shader(D8Device*p,DWORD fvf){host_enter(p);CHECK(slot==76&&fvf==a);SetLastError(host_error);return host_result;}
static HRESULT WINAPI clear(D8Device*p,DWORD count,const D8Rect*rects,DWORD flags,DWORD color,float z,DWORD stencil) {
    DWORD bits;host_enter(p);memcpy(&bits,&z,4);CHECK(count==a&&flags==b&&color==0xff123456&&bits==d&&!stencil);
    if(count)local_pointer(rects);else CHECK(!rects);SetLastError(host_error);return host_result;
}
static void setup(CPU*c) {
    unsigned i;
    memset(c,0,sizeof *c);for(i=0;i<8;i++){c->r[i]=0x76543210+i;c->st[i]=i+.5;}
    c->r[ESP]=0x2000;c->fcw=0x27f;c->fsw=0x4020;c->top=6;c->cf=1;c->df=1;c->pc=0x12345678;
    memset(&d8_device,0,sizeof d8_device);memset(&parent,0,sizeof parent);parent.children=1;parent.refs=1;
    d8_device.guest=0x4000;d8_device.refs=1;d8_device.host=&host;d8_device.parent=&parent;
    d8_device.focus=optional_focus?0:0x1234;d8_device.window=0x1235;d8_device.caps_valid=1;memcpy(&d8_device.caps,caps,sizeof caps);
    d8_device.depth=1;d8_device.depthformat=75;
    wr32(0x2000,0x98765432);wr32(0x2004,0x4000);wr32(0x2008,a);wr32(0x200c,b);wr32(0x2010,d);
    input_size=0;
    if(slot==37){input_size=64;wr32(0x200c,0x5ffdu);}
    if(slot==42){input_size=68;wr32(0x2008,0x5ffdu);}
    if(slot==18){input_size=1536;wr32(0x200c,0x5ffdu);}
    if(slot==36){input_size=a*16;wr32(0x200c,a?0x5ffdu:0);wr32(0x2010,b);wr32(0x2014,0xff123456);wr32(0x2018,d);wr32(0x201c,0);}
    if(input_size)memcpy(G2H(0x5ffd),input,input_size);
    active=NULL;enters=leaves=native_calls=events_count=0;d8_rendering=d8_native_failed=reenter=0;
    suspended=*c;
}
static void positive(int lazy) {
    CPU c,expected;BYTE frame[64];unsigned pre,post;DWORD old;
    setup(&c);if(lazy)d8_device.caps_valid=0;expected=c;memcpy(frame,G2H(0x2000),64);
    if(input_size)CHECK(VirtualProtect(G2H(0x5000),0x2000,PAGE_READONLY,&old));
    expected.rv=rd32(0x2000);expected.r[ESP]+=4*(nargs()+1);if(slot!=18)expected.r[EAX]=(DWORD)host_result;
    SetLastError(0x12345678);pre=_mm_getcsr();dispatch(&c);post=_mm_getcsr();
    CHECK(pre==post&&native_calls==1&&events_count>4);CHECK(!memcmp(&c,&expected,sizeof c));
    CHECK(!memcmp(frame,G2H(0x2000),64));CHECK(guest_error==host_error);CHECK(!active&&!d8_rendering&&enters==leaves);
    CHECK(d8_device.refs==1);if(input_size){CHECK(!memcmp(input,G2H(0x5ffd),input_size));CHECK(VirtualProtect(G2H(0x5000),0x2000,old,&old));}
    hash=(hash^(DWORD)host_result^host_error^slot^a^b^d)*16777619u;
}
static void reject(CPU*c,unsigned allowed_calls){CPU before=*c;unsigned previous=native_calls;
    allow_fatal=1;
    if(!setjmp(stop)){dispatch(c);CHECK(0);}
    allow_fatal=0;CHECK(failed_code==76&&events_count>0);CHECK(!memcmp(c,&before,sizeof before));
    CHECK(native_calls==previous+allowed_calls);negative_count++;d8_rendering=0;active=NULL;reenter=0;
}
/* Execute the unchanged generated cache body through these SAME integrated
 * semantic adapters on one persistent owned COM double. Helper dependencies
 * are explicit fixture services; this is not native GPU qualification. */
volatile long xrt_preempt_req;
void xrt_preempt(CPU*c){(void)c;ExitProcess(90);}
void xrt_badret(CPU*c,uint32_t site,uint32_t expected){(void)c;(void)site;(void)expected;ExitProcess(90);}
static unsigned char xrt_hits_D3DDrv[1024];
static void f_6961020(CPU*c){uint32_t s=c->r[ESP];memcpy(G2H(rd32(s+4)),G2H(rd32(s+8)),rd32(s+12));RET(0);}
static void f_697cda8(CPU*c){CHECK(*ST(c,0)==-.5);c->r[EAX]=c->r[EDX]=0;fpop(c);RET(0);}
void xrt_icall(CPU*c,uint32_t target,uint32_t site){
    (void)site;slot=target;a=ARG(1);b=nargs()>=3?ARG(2):0;d=nargs()>=4?ARG(3):0;
    input_size=slot==37?64:0;if(input_size)memcpy(input,G2H(ARG(2)),input_size);
    suspended=*c;dispatch(c);cache_calls++;
}
#include "cache_generated.inc"
static void integrated_cache(void) {
    CPU c;FILE*f;unsigned i;size_t bytes;
    CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));guest_capacity=0x7000000;
    xrt_g=VirtualAlloc(NULL,guest_capacity,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g!=NULL);
    CHECK(!fopen_s(&f,"original-data.bin","rb"));bytes=fread(G2H(0x6960000),1,0x50000,f);fclose(f);CHECK(bytes>=0x20000);
    slot=50;a=14;b=1;d=0;setup(&c);d8_device.guest=0x30000;d8_device.caps_valid=0;caps_queries=0;
    wr32(0x697e04c,0x60000);wr32(0x60000,0);wr32(0x20000,0x10000);wr32(0x14698,0x30000);wr32(0x30000,0x40000);
    wr32(0x141c8,8);wr32(0x141f0,16);wr32(0x14650,1);wr32(0x1412c,0xbf000000);
    for(i=0;i<97;i++)wr32(0x40000+i*4,i);
    c.r[ESP]=0x58000;c.r[ECX]=0x20000;wr32(0x58000,0x696f4c2);wr32(0x58004,0x10000);
    host_result=S_OK;host_error=0x13572468;f_6977800(&c);
    CHECK(c.rv==0x696f4c2&&c.r[ESP]==0x58008&&cache_calls==195&&native_calls==195&&caps_queries==1);
    CHECK(d8_device.refs==1&&!d8_rendering&&!active&&enters==leaves);
}
static D8Vtable creation_vt;
static D8Interface creation_parent={&creation_vt};
static ULONG creation_refs;
static unsigned creation_queries,creation_cases;
static ULONG WINAPI parent_add(D8Interface*p){CHECK(p==&creation_parent);return ++creation_refs;}
static ULONG WINAPI parent_release(D8Interface*p){CHECK(p==&creation_parent&&creation_refs>1);return --creation_refs;}
static UINT WINAPI parent_count(D8Interface*p){CHECK(p==&creation_parent);return 1;}
static DWORD expected_parent_seed;
static HRESULT WINAPI parent_caps(D8Interface*p,UINT adapter,UINT type,D8Caps*q){CHECK(p==&creation_parent&&!adapter&&type==1);if(expected_parent_seed)CHECK(GetLastError()==expected_parent_seed);if(SUCCEEDED(host_result))memcpy(q,caps,sizeof caps);creation_queries++;SetLastError(host_error);return host_result;}
static HRESULT WINAPI parent_mode(D8Interface*p,UINT adapter,D8Mode*q){CHECK(p==&creation_parent&&!adapter);q->width=1920;q->height=1080;q->format=22;creation_queries++;return host_result;}
static HRESULT WINAPI parent_type(D8Interface*p,UINT adapter,UINT type,UINT af,UINT bf,BOOL windowed){CHECK(p==&creation_parent&&!adapter&&type==1&&af==22&&bf>=20&&bf<=26&&windowed);creation_queries++;return host_result;}
static HRESULT WINAPI parent_multi(D8Interface*p,UINT adapter,UINT type,UINT format,BOOL windowed,UINT multi){(void)format;CHECK(p==&creation_parent&&!adapter&&type==1&&windowed&&multi<=16);creation_queries++;return host_result;}
static HRESULT WINAPI parent_depth(D8Interface*p,UINT adapter,UINT type,UINT af,UINT bf,UINT df){(void)bf;(void)df;CHECK(p==&creation_parent&&!adapter&&type==1&&af==22);creation_queries++;return host_result;}
static void creation_protocol(void) {
    CPU c;unsigned i;BYTE before[52];
    const unsigned formats[]={0,20,21,22,23,24,25,26},depths[]={70,71,73,75,77,79,80};
    creation_vt.AddRef=parent_add;creation_vt.Release=parent_release;creation_vt.GetAdapterCount=parent_count;
    creation_vt.GetDeviceCaps=parent_caps;creation_vt.GetAdapterDisplayMode=parent_mode;creation_vt.CheckDeviceType=parent_type;
    creation_vt.CheckDeviceMultiSampleType=parent_multi;creation_vt.CheckDepthStencilMatch=parent_depth;
    for(i=0;i<16;i++){
        slot=50;a=14;b=1;d=0;setup(&c);parent.host=&creation_parent;creation_refs=1;
        memset(G2H(0x7000),0,52);wr32(0x7000,i?800:0);wr32(0x7004,i?600:0);wr32(0x7008,formats[i%8]);
        wr32(0x700c,i%3);wr32(0x7010,i%2?0:2);wr32(0x7014,1);wr32(0x701c,32);wr32(0x7020,i%2?0:32);wr32(0x7024,depths[i%7]);
        memcpy(before,G2H(0x7000),52);SetLastError(0x76543210);host_result=S_OK;creation_queries=0;
        d8_creation_domain(&c,&parent,0,1,i%2?0x22:0x42,0x7000);
        CHECK(!memcmp(before,G2H(0x7000),52)&&creation_refs==1&&!parent.pending&&!d8_creating&&!active);
        CHECK(GetLastError()==0x76543210&&creation_queries==(i%2?4:6));creation_cases++;
    }
    /* Invalid/unsupported native query must diagnose before CreateDevice. */
    host_result=E_FAIL;allow_fatal=1;
    if(!setjmp(stop)){d8_creation_domain(&c,&parent,0,1,0x42,0x7000);CHECK(0);}
    allow_fatal=0;CHECK(failed_code==76);negative_count++;d8_creating=0;active=NULL;parent.pending=0;creation_refs=1;
}
#include "parent_query.inc"
static void parent_query_protocol(void){
    CPU c,expected;unsigned i;BYTE before[212];const unsigned results[]={0,0x80004005,0x8876086c};
    for(i=0;i<3;i++){
        slot=50;a=14;b=1;d=0;setup(&c);parent.guest=0x5000;parent.host=&creation_parent;
        wr32(0x2004,0x5000);wr32(0x2008,0);wr32(0x200c,1);wr32(0x2010,0x8000);
        memset(G2H(0x8000),0xa5,212);memcpy(before,G2H(0x8000),212);expected=c;
        expected.r[EAX]=results[i];expected.r[ESP]+=20;expected.rv=rd32(0x2000);
        guest_error=expected_parent_seed=0x12345678;host_error=87;host_result=(HRESULT)results[i];SetLastError(0xbad);
        d8_GetDeviceCaps(&c);CHECK(!memcmp(&c,&expected,sizeof c)&&guest_error==87);
        CHECK(!memcmp(G2H(0x8000),i?before:(BYTE*)caps,212));
    }
    for(i=0;i<6;i++){
        slot=50;a=14;b=1;d=0;setup(&c);parent.guest=0x5000;parent.host=&creation_parent;creation_refs=1;
        wr32(0x2004,0x5000);wr32(0x2008,0);wr32(0x200c,1);wr32(0x2010,22);
        wr32(0x2014,i<3?23:32);wr32(0x2018,i<3?32:2);
        expected=c;expected.r[ESP]+=28;expected.rv=rd32(0x2000);expected.r[EAX]=results[i%3];
        guest_error=0x12345678;host_result=(HRESULT)results[i%3];host_error=87;expected_parent_seed=0;
        if(i<3)d8_CheckDeviceType(&c);else d8_CheckDeviceMultiSampleType(&c);
        CHECK(!memcmp(&c,&expected,sizeof c)&&guest_error==0x12345678&&creation_refs==1&&!parent.pending&&!d8_creating&&!active);
    }
    expected_parent_seed=0;
}
static HRESULT create_result;
static unsigned created_calls,creation_adapter_cases;
static HWND expected_focus;
static HRESULT WINAPI parent_create(D8Interface*p,UINT adapter,UINT type,HWND focus,DWORD flags,D8Present*q,D8Device**out){
    CHECK(p==&creation_parent&&!adapter&&type==1&&focus==expected_focus&&flags==0x42);
    CHECK(d8_creating&&active&&!memcmp(active,&suspended,sizeof suspended)&&creation_refs==2&&parent.pending==1);
    CHECK((BYTE*)q<xrt_g||(BYTE*)q>=xrt_g+guest_capacity);CHECK((BYTE*)out<xrt_g||(BYTE*)out>=xrt_g+guest_capacity);
    CHECK(q->windowed==32&&q->depth==32&&q->depthformat==75&&q->count==0&&!*out);
    /* Model the documented mutable presentation/output contract. */
    q->width=800;q->height=600;q->count=1;q->format=22;
    if(!q->window)q->window=focus;
    *out=SUCCEEDED(create_result)?&host:NULL;created_calls++;SetLastError(host_error);return create_result;
}
static void setup_creation(CPU*c,unsigned variant){
    slot=100;a=b=d=0;setup(c);memset(&d8_device,0,sizeof d8_device);
    d8_attempted=d8_native_failed=d8_creating=0;d8_device_vtable=0;
    parent.guest=0x5000;parent.children=0;parent.host=&creation_parent;creation_refs=1;
    creation_vt.AddRef=parent_add;creation_vt.Release=parent_release;creation_vt.GetAdapterCount=parent_count;
    creation_vt.GetDeviceCaps=parent_caps;creation_vt.GetAdapterDisplayMode=parent_mode;creation_vt.CheckDeviceType=parent_type;
    creation_vt.CheckDeviceMultiSampleType=parent_multi;creation_vt.CheckDepthStencilMatch=parent_depth;creation_vt.CreateDevice=parent_create;
    memset(G2H(0x7000),0,52);wr32(0x7014,1);wr32(0x7018,variant==2?0:0x1235);wr32(0x701c,32);wr32(0x7020,32);wr32(0x7024,75);
    wr32(0x2004,0x5000);wr32(0x2008,0);wr32(0x200c,1);wr32(0x2010,variant==1?0:0x1234);wr32(0x2014,0x42);wr32(0x2018,0x7000);wr32(0x201c,0x8000);
    wr32(0x8000,0xdeadbeef);expected_focus=(HWND)(uintptr_t)rd32(0x2010);
    c->fs_base=0x1000;suspended=*c;guest_error=0x1234;host_result=S_OK;create_result=S_OK;host_error=87;created_calls=0;creation_queries=0;
}
static void creation_adapter_protocol(void){
    CPU c,expected;unsigned i;BYTE frame[32];
    for(i=0;i<4;i++){
        setup_creation(&c,i%3);expected=c;expected.r[ESP]+=32;expected.rv=rd32(0x2000);expected.r[EAX]=i==3?(DWORD)E_FAIL:0;
        memcpy(frame,G2H(0x2000),32);create_result=i==3?E_FAIL:S_OK;
        allow_fatal=i==3;
        if(!setjmp(stop)){d8_CreateDevice(&c);CHECK(i!=3);}else CHECK(i==3&&failed_code==76);
        allow_fatal=0;CHECK(!memcmp(&c,&expected,sizeof c)&&!memcmp(frame,G2H(0x2000),32));
        CHECK(created_calls==1&&d8_attempted==1&&!active&&!d8_creating&&creation_refs==1&&!parent.pending&&guest_error==87);
        CHECK(rd32(0x7000)==800&&rd32(0x7004)==600&&rd32(0x7008)==22&&rd32(0x700c)==1);
        CHECK(rd32(0x7018)==(i%3==2?0x1234:0x1235));
        if(i==3)CHECK(rd32(0x8000)==0&&!d8_device.refs&&!parent.children&&d8_native_failed);
        else CHECK(rd32(0x8000)==d8_device.guest&&d8_device.host==&host&&d8_device.refs==1&&parent.children==1);
        creation_adapter_cases++;
    }
    negative_count++; /* Actual failing CreateDevice requires teardown. */
}
__declspec(noinline) static void trace_stop(void){FILE*f;if(!fopen_s(&f,"FORBIDDEN.txt","w")){fputs("continued beyond owned marker",f);fclose(f);}}
static int debug_trace(const char*mode){
    static CPU cpu;FILE*f;unsigned i;
    slot=50;a=14;b=32;d=0;memset(input,0,sizeof input);
    if(!strcmp(mode,"matrix")){slot=37;a=256;for(i=0;i<16;i++)((float*)input)[i]=i%5==0?1:0;((float*)input)[12]=12.5f;}
    if(!strcmp(mode,"material")){slot=42;a=0;for(i=0;i<17;i++)((float*)input)[i]=i*.125f;}
    if(!strcmp(mode,"gamma")){slot=18;a=1;for(i=0;i<768;i++)((WORD*)input)[i]=(WORD)((i%256)*257);}
    if(!strcmp(mode,"clear")){slot=36;a=2;b=3;d=0x3f000000;for(i=0;i<2;i++){D8Rect*r=(D8Rect*)input+i;r->right=2000;r->bottom=2000;}}
    setup(&cpu);cpu.fs_base=0x1000;suspended=cpu;xrt_set_last_error(&cpu,0x1234);
    if(!strncmp(mode,"create",6)){setup_creation(&cpu,!strcmp(mode,"create-nullfocus")?1:0);if(!strcmp(mode,"create-failure"))create_result=E_FAIL;}
    trace_callback=!strcmp(mode,"callback");trace_corrupt=!strcmp(mode,"corrupt-cpu");
    host_result=!strcmp(mode,"native-failure")?E_FAIL:S_OK;host_error=87;
    CHECK(!fopen_s(&f,"ready.json","w"));
    fprintf(f,"{\"pid\":%lu,\"cpu\":%llu,\"guest_pointer\":%llu,\"registry\":%llu,\"checkpoint\":%llu,\"fatal\":%llu,\"callback\":%llu,\"stop\":%llu,\"parent\":%llu}",GetCurrentProcessId(),
      (unsigned long long)(uintptr_t)&cpu,(unsigned long long)(uintptr_t)&xrt_g,(unsigned long long)(uintptr_t)&d8_device,
      (unsigned long long)(uintptr_t)&d8_semantic_checkpoint,(unsigned long long)(uintptr_t)&xrt_fatal,
      (unsigned long long)(uintptr_t)&invoke_gui_proc,(unsigned long long)(uintptr_t)&trace_stop,(unsigned long long)(uintptr_t)&parent);fclose(f);
    trace_events=1;DebugBreak();if(slot==100)d8_CreateDevice(&cpu);else dispatch(&cpu);trace_stop();return 9;
}
int main(int argc,char**argv) {
    CPU c;unsigned i,j,k;DWORD old;const unsigned results[]={0,0x80004005,0x8876086c};
#ifdef _WIN64
    if(argc==2){
        /* Match the runtime's complete guest address reservation. A small
         * fixture allocation can otherwise place unrelated native locals in
         * the nominal 4 GiB guest range and mis-test the observer boundary. */
        xrt_g=VirtualAlloc(NULL,(SIZE_T)0x100000000ull,MEM_RESERVE,PAGE_NOACCESS);CHECK(xrt_g!=NULL);
        CHECK(VirtualAlloc(xrt_g,0x20000,MEM_COMMIT,PAGE_READWRITE)==xrt_g);
    }else
#endif
    {xrt_g=VirtualAlloc(NULL,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g!=NULL);}
    memcpy(caps,measured_caps,sizeof caps);
    vt.GetDeviceCaps=getcaps;vt.SetRenderState=state;vt.SetTextureStageState=stage;vt.SetTransform=matrix;
    vt.SetMaterial=material;vt.SetGammaRamp=gamma_set;vt.SetTexture=texture;vt.SetStreamSource=stream;vt.SetIndices=indices;vt.SetVertexShader=shader;vt.Clear=clear;
    if(argc==2)return debug_trace(argv[1]);
    for(i=0;i<sizeof cases/sizeof cases[0];i++) {
        slot=cases[i][0];a=cases[i][1];b=cases[i][2];d=cases[i][3];
        memset(input,0,sizeof input);
        if(slot==37){for(k=0;k<16;k++)((DWORD*)input)[k]=k%5==0?0x3f800000:0;}
        if(slot==42){for(k=0;k<16;k++)((float*)input)[k]=k*.125f;((float*)input)[16]=8;}
        if(slot==18){for(k=0;k<768;k++)((WORD*)input)[k]=(WORD)((k%256)*257);}
        if(slot==36){for(k=0;k<a;k++){D8Rect*r=(D8Rect*)input+k;r->left=-(LONG)k*20;r->top=0;r->right=2000;r->bottom=2000;}}
        for(j=0;j<3;j++){guest_error=0x13572468;host_error=j?0xffffffff:87;host_result=(HRESULT)results[j];positive(j==0);}
    }
    /* Valid values beyond the old profile. */
    slot=50;a=14;b=0xffffffff;positive(0);b=0x20;positive(0);b=0;positive(0);
    optional_focus=1;positive(0);optional_focus=0;
    slot=37;a=256;((float*)input)[12]=12.5f;positive(0);
    slot=76;a=0x152;positive(0);a=0x244;positive(0);
    slot=83;a=15;b=0;d=64;positive(0);
    slot=85;a=0;b=12345;d=0;positive(0);
    /* Safety and implementation stops must precede the native operation. */
    slot=50;a=14;b=1;setup(&c);wr32(0x2004,0);reject(&c,0);
    setup(&c);d8_device.refs=0;reject(&c,0);
    setup(&c);d8_device.host=NULL;reject(&c,0);
    setup(&c);d8_rendering=1;reject(&c,0);
    setup(&c);c.r[ESP]=0xfffffff0;reject(&c,0);
    setup(&c);CHECK(VirtualProtect(G2H(0x2000),4096,PAGE_NOACCESS,&old));reject(&c,0);CHECK(VirtualProtect(G2H(0x2000),4096,old,&old));
    setup(&c);a=999;wr32(0x2008,a);reject(&c,0);
    a=14;setup(&c);reenter=1;reject(&c,1);
    setup(&c);reenter=2;reject(&c,1);
    slot=61;a=0;b=1;setup(&c);reject(&c,0);
    slot=83;a=16;b=0;d=0;setup(&c);reject(&c,0);
    slot=85;a=1;setup(&c);reject(&c,0);
    slot=76;a=1;setup(&c);reject(&c,0);
    slot=63;a=8;b=16;d=2;setup(&c);reject(&c,0);
    a=0;b=16;d=3;setup(&c);d8_device.caps.words[16]=0;reject(&c,0);
    slot=37;a=2;b=0;setup(&c);wr32(0x200c,0x1fff0);reject(&c,0);
    setup(&c);CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_NOACCESS,&old));reject(&c,0);CHECK(VirtualProtect(G2H(0x6000),4096,old,&old));
    creation_protocol();parent_query_protocol();creation_adapter_protocol();integrated_cache();CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));
    printf("{\"passed\":true,\"checks\":%u,\"negative_cases\":%u,\"cases\":%u,\"hash\":%u,\"integrated_cache_calls\":%u,\"creation_cases\":%u,\"creation_adapter_cases\":%u,\"graphics\":false,\"double_only\":true}\n",checks,negative_count,(unsigned)(sizeof cases/sizeof cases[0]),hash,cache_calls,creation_cases,creation_adapter_cases);
    return 0;
}

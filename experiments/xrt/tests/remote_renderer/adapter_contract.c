/* Non-graphical contract tests of the exact staged adapter source.
 * The host COM object and GUI identity service below are test doubles.
 * These tests do not qualify any DXVK rendering behavior or Windows callback. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <xmmintrin.h>
#include <stdlib.h>
#include "xrt_internal.h"
#include "d3d8_device_abi.h"
typedef struct D8Object { uint32_t guest,refs,children,pending;D8Interface*host; } D8Object;
static jmp_buf stop;
static int fatal_code,native_calls,enters,leaves,unpins,nested,checks;
static uint32_t guest_error,expected_state,expected_value;
static HRESULT host_result;
static CPU* active;
static CPU suspended;
static char fatal_message[512];
uint8_t* xrt_g;
__declspec(thread) XrtThread* xrt_cur;
#define CHECK(x) do { if(!(x)){fprintf(stderr,"check failed %s line %d\n",#x,__LINE__);exit(91);}checks++; }while(0)
XRT_NORETURN void xrt_fatal(CPU*c,int code,const char*fmt,...){va_list ap;(void)c;fatal_code=code;va_start(ap,fmt);vsnprintf(fatal_message,sizeof fatal_message,fmt,ap);va_end(ap);longjmp(stop,1);}
void xrt_event(const char*k,const char*f,...){(void)k;(void)f;}
uint32_t xrt_get_last_error(CPU*c){(void)c;return guest_error;}
void xrt_set_last_error(CPU*c,uint32_t e){(void)c;guest_error=e;}
int xrt_is_committed(uint32_t p,uint32_t n){return p>=0x1000&&(uint64_t)p+n<=0x20000;}
CPU* xrt_gui_callback_enter(CPU*c){CPU*prev=active;active=c;enters++;return prev;}
void xrt_gui_callback_leave(CPU*p){active=p;leaves++;}
void* xrt_gui_device_window(CPU*c,uint32_t token){if(token!=0x1234)xrt_fatal(c,76,"test invalid window identity");return (void*)(uintptr_t)0x5678;}
void xrt_gui_window_unpin(uint32_t t){CHECK(t==0x1234);unpins++;}
static const GUID com_iunknown={0};
static uint32_t com_vtable(const char**names,unsigned n){(void)names;(void)n;abort();}
static D8Object* d8_object(CPU*c,uint32_t p){(void)c;(void)p;abort();}
static void d8_words(const char*n,const void*p,unsigned c){(void)n;(void)p;(void)c;}
#include "hle_d3d8_device.inc"
static D8DeviceVtable vt;
static D8Device host={&vt};
static D8Object parent;
static ULONG host_refs;
static const DWORD material_words[17]={0x3f000000,0x3f000000,0x3f000000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0,0,0,0,0,0,0,0,0};
static void host_enter(D8Device*d){CHECK(d==&host);CHECK(d8_rendering==1);CHECK(active!=NULL);CHECK(!memcmp(active,&suspended,sizeof suspended));native_calls++;if(nested==1)d8_device_Release(active);if(nested==2)d8_device_SetRenderState(active);}
static HRESULT WINAPI setstate(D8Device*d,DWORD s,DWORD v){host_enter(d);CHECK(s==expected_state&&v==expected_value);return host_result;}
static HRESULT WINAPI material(D8Device*d,const D8Material*m){host_enter(d);CHECK(!memcmp(m,material_words,68));CHECK((const BYTE*)m<xrt_g||(const BYTE*)m>=xrt_g+0x20000);return host_result;}
static HRESULT WINAPI clear(D8Device*d,DWORD count,const D8Rect*r,DWORD flags,DWORD color,float z,DWORD stencil){host_enter(d);CHECK(count==0&&r==NULL&&flags==1&&color==0x123456&&z==0&&stencil==0);return host_result;}
static HRESULT WINAPI present(D8Device*d,const RECT*s,const RECT*t,HWND h,const RGNDATA*r){host_enter(d);CHECK(!s&&!t&&!h&&!r);return host_result;}
static ULONG WINAPI release(D8Device*d){CHECK(d==&host&&host_refs>0);return --host_refs;}
static ULONG WINAPI addref(D8Device*d){CHECK(d==&host);return ++host_refs;}
static void setup(CPU*c){unsigned i;memset(c,0,sizeof *c);for(i=0;i<8;i++){c->r[i]=0x76543210+i;c->st[i]=i+0.5;}c->r[ESP]=0x2000;c->fcw=0x27f;c->fsw=0x4020;c->top=6;c->cf=1;c->df=1;c->pc=0x12345678;c->hist[10]=0x1234;c->hpos=11;
 memset(&d8_device,0,sizeof d8_device);memset(&parent,0,sizeof parent);parent.children=1;parent.refs=1;d8_device.guest=0x4000;d8_device.refs=1;d8_device.host=&host;d8_device.parent=&parent;d8_device.focus=d8_device.window=0x1234;
 memset(G2H(0x2000),0,64);wr32(0x2000,0x34567890);wr32(0x2004,0x4000);memcpy(G2H(0x5000),material_words,68);
 native_calls=enters=leaves=unpins=nested=fatal_code=0;active=NULL;host_refs=1;d8_rendering=d8_native_failed=d8_creating=0;host_result=S_OK;fatal_message[0]=0;_mm_setcsr(0x3f80);}
static void positive(CPU*c,XrtFn fn,unsigned nargs,DWORD seed,int present_first){CPU expected=*c;BYTE frame[64];unsigned oldrefs=d8_device.refs;memcpy(frame,G2H(c->r[ESP]),64);suspended=*c;guest_error=seed;SetLastError(0xbad);expected.r[EAX]=(DWORD)host_result;expected.rv=rd32(c->r[ESP]);expected.r[ESP]+=4*(nargs+1);if(present_first&&host_result==S_OK)expected.fsw|=0x20;
 if(setjmp(stop)){fprintf(stderr,"unexpected fatal %s\n",fatal_message);exit(92);}fn(c);
 CHECK(!memcmp(c,&expected,sizeof expected));CHECK(!memcmp(frame,G2H(0x2000),64));CHECK(guest_error==seed);CHECK(_mm_getcsr()==0x3f80);CHECK(native_calls==1&&enters==1&&leaves==1&&active==NULL);CHECK(d8_rendering==0&&d8_device.refs==oldrefs);}
static void negative(CPU*c,XrtFn fn,const char*part){CPU old=*c;BYTE frame[64];memcpy(frame,G2H(c->r[ESP]),64);suspended=*c;
 if(!setjmp(stop)){fn(c);fprintf(stderr,"missing guard %s\n",part);exit(93);}CHECK(fatal_code==76);CHECK(strstr(fatal_message,part)!=NULL);CHECK(!memcmp(c,&old,sizeof old));CHECK(!memcmp(frame,G2H(0x2000),64));CHECK(native_calls==0&&enters==0&&leaves==0);}
#include "contract_traps.inc"
int main(void){CPU c;unsigned i,j,k;DWORD seeds[]={0,18,0x13572468,0xffffffff};DWORD tuples[][2]={{7,1},{9,2},{29,0},{26,1},{143,1},{48,0},{35,3},{136,1}};DWORD refused[][2]={{148,1},{145,0},{8,3},{7,0},{136,0},{0,1},{255,1},{148,0xffffffff}};DWORD badthis[]={0,1,0x4004,0x7777};DWORD old;
 xrt_g=VirtualAlloc(NULL,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);CHECK(xrt_g!=NULL);vt.SetRenderState=setstate;vt.SetMaterial=material;vt.Clear=clear;vt.Present=present;vt.Release=release;vt.AddRef=addref;
 for(i=0;i<8;i++)for(j=0;j<4;j++)for(k=0;k<2;k++){setup(&c);expected_state=tuples[i][0];expected_value=tuples[i][1];wr32(0x2008,expected_state);wr32(0x200c,expected_value);host_result=k?E_FAIL:S_OK;positive(&c,d8_device_SetRenderState,3,seeds[j],0);}
 for(j=0;j<4;j++)for(k=0;k<2;k++){setup(&c);wr32(0x2008,0x5000);host_result=k?E_FAIL:S_OK;positive(&c,d8_device_SetMaterial,2,seeds[j],0);}
 for(j=0;j<4;j++){setup(&c);wr32(0x2010,1);wr32(0x2014,0x123456);positive(&c,d8_device_Clear,7,seeds[j],0);setup(&c);c.fsw=0x4000;positive(&c,d8_device_Present,5,seeds[j],1);CHECK(d8_device.presents==1);}
 for(i=0;i<8;i++){setup(&c);wr32(0x2008,refused[i][0]);wr32(0x200c,refused[i][1]);negative(&c,d8_device_SetRenderState,"unsupported state=");}
 for(i=0;i<4;i++){setup(&c);wr32(0x2004,badthis[i]);negative(&c,d8_device_SetRenderState,"stale or unknown");}
 for(i=0;i<sizeof traps/sizeof traps[0];i++){setup(&c);negative(&c,traps[i],"unsupported slot");setup(&c);wr32(0x2004,1);negative(&c,traps[i],"stale or unknown");}
 setup(&c);wr32(0x2008,0);negative(&c,d8_device_SetMaterial,"invalid readable");
 setup(&c);wr32(0x2008,0x5000);wr32(0x5040,1);negative(&c,d8_device_SetMaterial,"unsupported material");
 setup(&c);wr32(0x2008,0x6000-64);memcpy(G2H(0x6000-64),material_words,68);CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_NOACCESS,&old));negative(&c,d8_device_SetMaterial,"invalid readable");CHECK(VirtualProtect(G2H(0x6000),4096,PAGE_READWRITE,&old));
 setup(&c);wr32(0x2008,0x5000);CHECK(VirtualProtect(G2H(0x5000),4096,PAGE_READONLY,&old));positive(&c,d8_device_SetMaterial,2,18,0);CHECK(VirtualProtect(G2H(0x5000),4096,PAGE_READWRITE,&old));
 setup(&c);d8_rendering=1;wr32(0x2008,136);wr32(0x200c,1);negative(&c,d8_device_SetRenderState,"reentrant rendering");
 setup(&c);d8_device.focus=0x4321;wr32(0x2008,136);wr32(0x200c,1);negative(&c,d8_device_SetRenderState,"unsupported rendering window tuple");
 for(i=1;i<=2;i++){setup(&c);nested=i;wr32(0x2008,136);wr32(0x200c,1);suspended=c;if(!setjmp(stop)){d8_device_SetRenderState(&c);return 94;}CHECK(fatal_code==76);CHECK(strstr(fatal_message,i==1?"Release during native rendering":"reentrant rendering")!=NULL);CHECK(native_calls==1&&d8_device.refs==1&&host_refs==1&&d8_rendering==1);}
 setup(&c);suspended=c;if(setjmp(stop))return 95;d8_device_AddRef(&c);CHECK(host_refs==2&&d8_device.refs==2);c.r[ESP]=0x2000;d8_device_Release(&c);CHECK(host_refs==1&&d8_device.refs==1);c.r[ESP]=0x2000;d8_device_Release(&c);CHECK(host_refs==0&&d8_device.refs==0&&d8_device.host==NULL&&parent.children==0&&unpins==2);
 CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));printf("{\"passed\":true,\"checks\":%d,\"unsupported_slots\":%u,\"graphical_backend\":false,\"test_double_only\":true}\n",checks,(unsigned)(sizeof traps/sizeof traps[0]));return 0;}

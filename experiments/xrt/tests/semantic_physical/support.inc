/* Fixture services only. The included adapter implementation is source-exact. */
#include "xrt_internal.h"
#include "d3d8_device_abi.h"
#include <xmmintrin.h>
typedef struct D8Object {uint32_t guest,refs,children,pending;D8Interface*host;} D8Object;
static jmp_buf trap;
static int may_trap,rejected,record_events;
static unsigned checks,enters,leaves,callbacks,callback_active;
static DWORD guest_error;
static CPU*active;
static HWND owned_window;
static char rejection[512];
uint8_t*xrt_g;
__declspec(thread) XrtThread*xrt_cur;
#define CHECK(v) do{checks++;if(!(v)){fprintf(stderr,"check %d: %s\n",__LINE__,#v);ExitProcess(91);}}while(0)
XRT_NORETURN void xrt_fatal(CPU*c,int code,const char*fmt,...){va_list ap;(void)c;va_start(ap,fmt);vsnprintf(rejection,sizeof rejection,fmt,ap);va_end(ap);if(!may_trap){fprintf(stderr,"fatal %d: %s\n",code,rejection);ExitProcess(92);}CHECK(code==76);rejected=1;longjmp(trap,1);}
void xrt_event(const char*k,const char*f,...){DWORD error=GetLastError();char text[8192];va_list ap;int n;va_start(ap,f);n=vsnprintf(text,sizeof text,f,ap);va_end(ap);CHECK(n>=0&&n<sizeof text);if(record_events)ev_event(k,"%s",text);SetLastError(error);}
uint32_t xrt_get_last_error(CPU*c){(void)c;return guest_error;}
void xrt_set_last_error(CPU*c,uint32_t e){(void)c;guest_error=e;}
int xrt_is_committed(uint32_t p,uint32_t n){return p>=0x1000&&(uint64_t)p+n<=0x20000;}
CPU*xrt_gui_callback_enter(CPU*c){CPU*previous=active;active=c;enters++;return previous;}
void xrt_gui_callback_leave(CPU*c){active=c;leaves++;}
void*xrt_gui_device_window(CPU*c,uint32_t p){if(!p)return NULL;if(p!=0x1234||!IsWindow(owned_window)||GetWindowThreadProcessId(owned_window,NULL)!=GetCurrentThreadId())xrt_fatal(c,76,"fixture unknown/not-owned HWND");return owned_window;}
void xrt_gui_window_unpin(uint32_t p){CHECK(!p||p==0x1234);}
void xrt_gui_window_pin(CPU*c,uint32_t p){(void)xrt_gui_device_window(c,p);}
uint32_t xrt_gui_window_identity(CPU*c,void*p){if(!p)return 0;if(p!=owned_window)xrt_fatal(c,76,"fixture foreign HWND");return 0x1234;}
static const GUID com_iunknown={0};
static uint32_t com_vtable(const char**n,unsigned s){(void)n;(void)s;abort();}
static D8Object*d8_object(CPU*c,uint32_t p){(void)c;(void)p;abort();}
static void d8_words(const char*n,const void*p,unsigned s){(void)n;(void)p;(void)s;}
#include "hle_d3d8_device.inc"
typedef struct Sample {unsigned slot,a,b,c,input_kind,invalid;} Sample;
/* SAMPLES are measurement inputs only, never runtime admission policy. */
/* SAMPLE_ROWS */
static D8Device*device;
static D8Object parent;
static D8Caps live_caps;
static const Sample*sample;
static unsigned char input_data[68];
static unsigned input_size;
static CPU cpu,expected;
static BYTE saved_frame[32];
static unsigned nargs(void){return sample->slot==63||sample->slot==83?4:sample->slot==76||sample->slot==42?2:3;}
static void dispatch(CPU*c){switch(sample->slot){case 42:d8_device_SetMaterial(c);break;case 50:d8_device_SetRenderState(c);break;case 63:d8_device_SetTextureStageState(c);break;case 37:d8_device_SetTransform(c);break;case 61:d8_device_SetTexture(c);break;case 83:d8_device_SetStreamSource(c);break;case 85:d8_device_SetIndices(c);break;case 76:d8_device_SetVertexShader(c);break;default:abort();}}
static void setup(void){unsigned i;memset(&cpu,0,sizeof cpu);for(i=0;i<8;i++){cpu.r[i]=0x76543210+i;cpu.st[i]=i+.5;}cpu.r[ESP]=0x2000;cpu.fcw=0x27f;cpu.fsw=0x4020;cpu.top=6;cpu.cf=cpu.df=1;cpu.pc=0x12345678;
 memset(G2H(0x2000),0,32);wr32(0x2000,0x98765432);wr32(0x2004,0x4000);wr32(0x2008,sample->a);wr32(0x200c,sample->b);wr32(0x2010,sample->c);
 input_size=0;memset(input_data,0,sizeof input_data);
 if(sample->slot==37){input_size=64;for(i=0;i<16;i++)((float*)input_data)[i]=i%5==0?1.f:0.f;((float*)input_data)[12]=sample->input_kind?12.5f:0;((float*)input_data)[0]=sample->input_kind==2?2.f:1.f;wr32(0x200c,0x5ffd);}
 if(sample->slot==42){input_size=68;for(i=0;i<16;i++)((float*)input_data)[i]=(float)i*.125f;((float*)input_data)[16]=sample->input_kind==1?8.f:0.f;wr32(0x2008,0x5ffd);}
 if(input_size)memcpy(G2H(0x5ffd),input_data,input_size);memcpy(saved_frame,G2H(0x2000),32);expected=cpu;rejected=0;rejection[0]=0;
}
static DWORD translated(void){DWORD result,old=0;unsigned before_enter=enters,before_leave=leaves;
 if(input_size)CHECK(VirtualProtect(G2H(0x5000),8192,PAGE_READONLY,&old));
 may_trap=1;if(!setjmp(trap))dispatch(&cpu);may_trap=0;
 if(!rejected){expected.r[EAX]=cpu.r[EAX];expected.r[ESP]+=4*(nargs()+1);expected.rv=rd32(0x2000);}
 CHECK(!memcmp(&cpu,&expected,sizeof cpu));CHECK(!memcmp(saved_frame,G2H(0x2000),32));
 CHECK(!active&&!d8_rendering&&enters-before_enter==leaves-before_leave&&d8_device.refs==1&&parent.children==1);
 if(input_size){CHECK(!memcmp(G2H(0x5ffd),input_data,input_size));CHECK(VirtualProtect(G2H(0x5000),8192,old,&old));}
 result=cpu.r[EAX];SetLastError(guest_error);return result;
}
static DWORD WINAPI wrap2(uintptr_t p,uintptr_t a){(void)a;CHECK((void*)p==device);guest_error=GetLastError();return translated();}
static DWORD WINAPI wrap3(uintptr_t p,uintptr_t a,uintptr_t b){(void)a;(void)b;CHECK((void*)p==device);guest_error=GetLastError();return translated();}
static DWORD WINAPI wrap4(uintptr_t p,uintptr_t a,uintptr_t b,uintptr_t c){(void)a;(void)b;(void)c;CHECK((void*)p==device);guest_error=GetLastError();return translated();}

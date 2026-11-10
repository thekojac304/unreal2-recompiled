"""Owned windowed creation fixtures using the exact full semantic adapter."""
from recheck import HERE

CONFIGS = [
    # width,height,format,count,multisample,swap,focus,window,windowed,depth,depthformat,behavior
    [800,600,22,1,0,1,0x1234,0x1234,1,1,75,0x42],
    [0,0,0,0,0,1,0x1234,0x1234,32,32,75,0x42],
    [640,480,22,1,0,1,0x1234,0x1234,1,0,0,0x22],
    [640,480,22,1,0,1,0x1234,0x1235,1,1,77,0x82],
    [640,480,22,1,0,1,0,0x1235,1,1,75,0x42],
    [640,480,22,1,0,1,0x1234,0,1,1,75,0x42],
    [640,480,22,2,0,1,0x1234,0x1234,1,1,75,0x42],
    [640,480,22,1,2,1,0x1234,0x1234,1,1,75,0x42],
]


def sources(config):
    text=(HERE/'support.inc').read_text()
    def replace(old,new):
        nonlocal text
        assert old in text,old
        text=text.replace(old,new)
    replace('static HWND owned_window;', 'static HWND owned_window,owned_second;\nstatic unsigned pins[2];\nstatic D8Object parent;\nstatic int creation_logging;')
    replace('if(record_events)ev_event(k,"%s",text);', 'if(creation_logging)printf("{\\"kind\\":\\"creation-event\\",\\"event\\":\\"%s\\",\\"payload\\":{%s}}\\n",k,text);else if(record_events)ev_event(k,"%s",text);')
    start=text.index('void*xrt_gui_device_window(');end=text.index('static const GUID',start)
    text=text[:start]+'''void*xrt_gui_device_window(CPU*c,uint32_t p){HWND w;if(!p)return NULL;w=p==0x1234?owned_window:p==0x1235?owned_second:NULL;if(!w||!IsWindow(w)||GetWindowThreadProcessId(w,NULL)!=GetCurrentThreadId())xrt_fatal(c,76,"fixture unknown/not-owned HWND");return w;}
void xrt_gui_window_unpin(uint32_t p){if(!p)return;CHECK(p==0x1234||p==0x1235);CHECK(pins[p-0x1234]>0);pins[p-0x1234]--;}
void xrt_gui_window_pin(CPU*c,uint32_t p){(void)xrt_gui_device_window(c,p);if(p)pins[p-0x1234]++;}
uint32_t xrt_gui_window_identity(CPU*c,void*p){if(!p)return 0;if(p==owned_window)return 0x1234;if(p==owned_second)return 0x1235;xrt_fatal(c,76,"fixture foreign HWND");}
'''+text[end:]
    replace('static uint32_t com_vtable(const char**n,unsigned s){(void)n;(void)s;abort();}', '''static const char**slot_names;
uint32_t xrt_hle_proc(const char*dll,const char*name){unsigned i;CHECK(!strcmp(dll,"xrt.com"));for(i=0;i<97;i++)if(!strcmp(name,slot_names[i]))return 0x9000+4*i;return 0;}
static uint32_t com_vtable(const char**n,unsigned s){unsigned i;CHECK(s==97);slot_names=n;for(i=0;i<s;i++)wr32(0x10000+4*i,xrt_hle_proc("xrt.com",n[i]));return 0x10000;}
uint32_t xrt_rt_alloc(uint32_t n,uint32_t align){CHECK(n==4&&align==4);wr32(0x11000,0);return 0x11000;}''')
    replace('static D8Object*d8_object(CPU*c,uint32_t p){(void)c;(void)p;abort();}', 'static D8Object*d8_object(CPU*c,uint32_t p){if(p==parent.guest&&parent.refs&&parent.host)return &parent;xrt_fatal(c,76,"fixture unknown parent");}')
    # Keep exactly one parent definition before the adapter include.
    replace('static D8Device*device;\nstatic D8Object parent;', 'static D8Device*device;')
    text=text.replace('/* SAMPLE_ROWS */','static const Sample samples[]={{50,14,1,0,0,0}};')
    fixture=(HERE/'fixture.c').read_text();fixture=fixture[:fixture.index('int main(')]
    fixture+='\nstatic const unsigned cfg[12]={'+','.join(str(v)+'u' for v in config)+'};\n'
    fixture+=(HERE/'creation_main.inc').read_text()
    return fixture,text

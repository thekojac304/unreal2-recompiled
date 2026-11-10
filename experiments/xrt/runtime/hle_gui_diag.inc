/* Opt-in observation before callback validation. Never reads callback pointer
 * arguments, changes dispatch, or guesses a message's result/sender. */
#include <xmmintrin.h>
static volatile LONG gui_diagnostic_serial;
static void gui_diagnostic_bytes(LONG id,const char* field,const void* data,unsigned bytes)
{
    unsigned offset,i;const BYTE* p=(const BYTE*)data;char hex[129];
    for(offset=0;offset<bytes;offset+=64) {
        unsigned count=bytes-offset<64?bytes-offset:64;
        for(i=0;i<count;i++)sprintf(hex+2*i,"%02x",p[offset+i]);
        xrt_event("gui_callback_blob","\"id\":%ld,\"field\":\"%s\",\"offset\":%u,\"total\":%u,\"hex\":\"%s\"",id,field,offset,bytes,hex);
    }
}
static int gui_diagnostic_readable(const void* data,unsigned bytes)
{
    uintptr_t at=(uintptr_t)data,limit=at+bytes;
    while(at<limit) {
        MEMORY_BASIC_INFORMATION m;DWORD p;uintptr_t next;
        if(!VirtualQuery((void*)at,&m,sizeof m) || m.State!=MEM_COMMIT || (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return 0;
        p=m.Protect&255;
        if(p!=PAGE_READONLY && p!=PAGE_READWRITE && p!=PAGE_WRITECOPY && p!=PAGE_EXECUTE_READ && p!=PAGE_EXECUTE_READWRITE && p!=PAGE_EXECUTE_WRITECOPY)return 0;
        next=(uintptr_t)m.BaseAddress+m.RegionSize;if(next<=at)return 0;at=next;
    }
    return 1;
}
static LONG gui_diagnostic_ingress(HWND h,UINT msg,WPARAM wp,LPARAM lp,uint32_t explicit_proc)
{
    DWORD error=GetLastError(),mxcsr=_mm_getcsr(),owner=0,tid;char enabled[2];LONG id=0;
    if(GetEnvironmentVariableA("XRT_GUI_DIAGNOSTICS",enabled,sizeof enabled)==1 && enabled[0]=='1') {
        LARGE_INTEGER qpc;GuiCallbackFrame* f;unsigned depth=1,i;void* frames[24];USHORT count;
        WCHAR name[256]={0};int length=0;uint32_t token=0,proc=explicit_proc;
        id=InterlockedIncrement(&gui_diagnostic_serial);QueryPerformanceCounter(&qpc);
        for(f=callback_frame;f;f=f->previous)depth++;
        for(i=0;i<1024;i++)if(windows[i].host==h){token=windows[i].token;if(!proc)proc=windows[i].proc;break;}
        tid=GetWindowThreadProcessId(h,&owner);
        xrt_event("gui_callback_ingress","\"id\":%ld,\"qpc\":%lld,\"message\":%u,\"host_wp\":%llu,\"host_lp\":%llu,\"host_hwnd\":%llu,\"guest_hwnd\":%u,\"proc\":%u,\"depth\":%u,\"pid\":%lu,\"tid\":%lu,\"owner_pid\":%lu,\"owner_tid\":%lu,\"last_error\":%lu,\"active_cpu\":%s",
            id,qpc.QuadPart,msg,(unsigned long long)wp,(unsigned long long)lp,(unsigned long long)(uintptr_t)h,token,proc,depth,GetCurrentProcessId(),GetCurrentThreadId(),owner,tid,error,callback_cpu?"true":"false");
        xrt_event("gui_callback_context","\"id\":%ld,\"send_flags\":%lu,\"foreground\":%llu,\"active\":%llu,\"focus\":%llu,\"wndproc\":%llu,\"mxcsr\":%lu",id,InSendMessageEx(NULL),(unsigned long long)(uintptr_t)GetForegroundWindow(),(unsigned long long)(uintptr_t)GetActiveWindow(),(unsigned long long)(uintptr_t)GetFocus(),(unsigned long long)GetWindowLongPtrW(h,GWLP_WNDPROC),mxcsr);
        if(msg>=0xc000u && msg<=0xffffu)length=GetClipboardFormatNameW(msg,name,256);
        xrt_event("gui_callback_name","\"id\":%ld,\"registered\":%s,\"utf16_units\":%d,\"lookup_error\":%lu",id,msg>=0xc000u&&msg<=0xffffu?"true":"false",length,GetLastError());
        if(length>0)gui_diagnostic_bytes(id,"registered_name_utf16",name,2*(unsigned)length);
        if(callback_cpu) {
            CPU* c=callback_cpu;uint32_t at=c->r[ESP];unsigned bytes=0;
            gui_diagnostic_bytes(id,"suspended_cpu",c,sizeof *c);
            if(c->thread && at>=c->thread->stack_lo && at<=c->thread->stack_hi) {
                bytes=c->thread->stack_hi-at;if(bytes>128)bytes=128;
                if(bytes && !gui_diagnostic_readable(G2H(at),bytes))bytes=0;
            }
            xrt_event("gui_callback_stack","\"id\":%ld,\"esp\":%u,\"stack_lo\":%u,\"stack_hi\":%u,\"readable_bytes\":%u",id,at,c->thread?c->thread->stack_lo:0,c->thread?c->thread->stack_hi:0,bytes);
            if(bytes)gui_diagnostic_bytes(id,"suspended_stack",G2H(at),bytes);
        }
        count=CaptureStackBackTrace(0,24,frames,NULL);
        for(i=0;i<count;i++) {
            HMODULE module=NULL;WCHAR path[1024]={0};DWORD units=0;char field[40];
            if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCWSTR)frames[i],&module))units=GetModuleFileNameW(module,path,1024);
            xrt_event("gui_callback_host_frame","\"id\":%ld,\"index\":%u,\"address\":%llu,\"module_base\":%llu,\"rva\":%llu,\"path_units\":%lu",id,i,(unsigned long long)(uintptr_t)frames[i],(unsigned long long)(uintptr_t)module,(unsigned long long)((uintptr_t)frames[i]-(uintptr_t)module),units);
            sprintf(field,"host_module_%u_utf16",i);if(units)gui_diagnostic_bytes(id,field,path,units*2);
        }
        xrt_event("gui_callback_diagnostic_end","\"id\":%ld,\"host_frames\":%u",id,count);
    }
    _mm_setcsr(mxcsr);SetLastError(error);return id;
}

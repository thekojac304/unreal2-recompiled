/* Typed DirectInput lifecycle. HWND is owned and pinned until device release or
 * a successful replacement. Failed calls retain the old association. */
static int did_lifecycle_active;
static void did_memory_access(CPU*c,uint32_t p,uint32_t n,int writable) {
    uint64_t at=p,end=(uint64_t)p+n;
    if(!p || end>0x100000000ull || !xrt_is_committed(p,n))
        xrt_fatal(c,76,"DirectInput lifecycle: invalid guest range");
    while(at<end) {
        MEMORY_BASIC_INFORMATION m;DWORD prot;int ok;
        if(!VirtualQuery(G2H((uint32_t)at),&m,sizeof m))xrt_fatal(c,76,"DirectInput lifecycle: range query failed");
        prot=m.Protect&255;ok=prot==PAGE_READWRITE||prot==PAGE_WRITECOPY||prot==PAGE_EXECUTE_READWRITE||prot==PAGE_EXECUTE_WRITECOPY;
        if(!writable)ok=ok||prot==PAGE_READONLY||prot==PAGE_EXECUTE_READ;
        if(m.State!=MEM_COMMIT||(m.Protect&PAGE_GUARD)||!ok)xrt_fatal(c,76,"DirectInput lifecycle: protected guest range");
        at=(uint64_t)((BYTE*)m.BaseAddress-xrt_g)+m.RegionSize;
    }
}
static DiDevice*did_lifecycle_frame(CPU*c,unsigned slot,unsigned n) {
    xrt_event("dinput_lifecycle_entry","\"slot\":%u,\"esp\":%u,\"site\":%u",slot,c->r[ESP],c->pc);
    if(did_lifecycle_active)xrt_fatal(c,76,"DirectInput lifecycle: reentrant operation");
    did_memory_access(c,c->r[ESP],4*(n+1),0);
    return did_object(c,ARG(0));
}
static void did_lifecycle_return(CPU*c,DiDevice*o,CPU*previous,unsigned slot,unsigned n,HRESULT hr,DWORD error) {
    did_lifecycle_active=0;xrt_gui_callback_leave(previous);
    xm_resource(c,4,o->guest,(unsigned)(o-di_devices)+1,(uint64_t)(uintptr_t)o->input,o->refs,0,"lifecycle-return");
    {XmValue v[2]={{XM_GUEST_ADDRESS,4,o->window},{XM_U32,4,o->cooperative_flags}};xm_values(c,"DID.window-association",2,v);}
    xrt_event("dinput_lifecycle_native_return","\"slot\":%u,\"object\":%u,\"hwnd\":%u,\"result\":%u,\"last_error\":%lu",slot,o->guest,o->window,(unsigned)hr,error);
    xrt_set_last_error(c,error);RET_STD(n,hr);
    xrt_event("dinput_lifecycle_return","\"slot\":%u,\"esp\":%u,\"return\":%u,\"eax\":%u",slot,c->r[ESP],c->rv,c->r[EAX]);
}
static void did_Acquire(CPU*c) {
    DiDevice*o=did_lifecycle_frame(c,7,1);CPU*previous;HRESULT hr;DWORD error;
    if(o->window)xrt_gui_device_window(c,o->window);
    previous=xrt_gui_callback_enter(c);did_lifecycle_active=1;SetLastError(xrt_get_last_error(c));
    hr=XM_Acquire(c,o->input);error=GetLastError();
    did_lifecycle_return(c,o,previous,7,1,hr,error);
}
static void did_Unacquire(CPU*c) {
    DiDevice*o=did_lifecycle_frame(c,8,1);CPU*previous;HRESULT hr;DWORD error;
    previous=xrt_gui_callback_enter(c);did_lifecycle_active=1;SetLastError(xrt_get_last_error(c));
    hr=XM_Unacquire(c,o->input);error=GetLastError();
    did_lifecycle_return(c,o,previous,8,1,hr,error);
}
static void did_SetCooperativeLevel(CPU*c) {
    DiDevice*o=did_lifecycle_frame(c,13,3);uint32_t token=ARG(1),flags=ARG(2),old=o->window;
    HWND window=NULL;CPU*previous;HRESULT hr;DWORD error;
    /* Invalid scalar flag combinations are safe native inputs. Unknown bits
     * are unsupported. NULL follows the documented native error/default path. */
    if(flags&~31u)xrt_fatal(c,76,"DirectInput cooperative level: unknown flags");
    if(token) {
        window=xrt_gui_device_window(c,token);
        if(GetAncestor(window,GA_ROOT)!=window)xrt_fatal(c,76,"DirectInput cooperative level: top-level owned window required");
        xrt_gui_window_pin(c,token);
    }
    previous=xrt_gui_callback_enter(c);did_lifecycle_active=1;SetLastError(xrt_get_last_error(c));
    if(xrt_dev_background() && ((flags&3)==1||(flags&3)==2) && ((flags&12)==4||(flags&12)==8)) { /* valid combinations only */
        /* Developer background mode: the host device is acquired non-exclusive/background so it works without the
         * foreground (and never captures the owner's mouse); its physical data is still dropped by isolation and only
         * scripted records reach the guest (hle_dinput.inc). The guest's own flags stay recorded. */
        DWORD host=(flags&~(DWORD)(DISCL_EXCLUSIVE|DISCL_FOREGROUND|DISCL_NOWINKEY))|DISCL_NONEXCLUSIVE|DISCL_BACKGROUND;
        xrt_log("DEV background: DirectInput cooperative level %x -> host %lx",flags,host);
        hr=XM_SetCooperativeLevel(c,o->input,window,host);
    } else
    hr=XM_SetCooperativeLevel(c,o->input,window,flags);
    error=GetLastError();
    if(SUCCEEDED(hr)){o->window=token;o->cooperative_flags=flags;if(old)xrt_gui_window_unpin(old);}
    else if(token)xrt_gui_window_unpin(token);
    did_lifecycle_return(c,o,previous,13,3,hr,error);
}

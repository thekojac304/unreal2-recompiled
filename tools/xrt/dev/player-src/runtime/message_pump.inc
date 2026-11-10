/* Main-loop message pump. Guest MSG is 28 bytes: hwnd token, message, wParam,
 * lParam, time, pt.x, pt.y. The native MSG last returned by PeekMessage is kept,
 * so Translate/Dispatch of that unchanged guest copy forward the exact native
 * message (pointer-width parameters included). Another guest MSG crosses only
 * as 32-bit scalars with a validated window token. Native dispatch reaches the
 * guest WNDPROC through the existing typed callback marshalling. */
static MSG pump_last;
static uint32_t pump_guest, pump_words[7];
static int pump_valid;
static unsigned pump_events;
static void pump_probe(XmRequest*q,int event,const char*name,uint64_t a,uint64_t b,uint64_t result) {
    q->event=event;q->domain=XM_NATIVE;q->name=name;q->count=2;
    q->values[0].type=XM_OPAQUE;q->values[0].bytes=8;q->values[0].value=a;
    q->values[1].type=XM_OPAQUE;q->values[1].bytes=8;q->values[1].value=b;
    q->result=result;xm_probe(xm_current_cpu(),q);
}
static uint32_t pump_scalar(CPU*c,uint64_t v,UINT msg,const char*field) {
    if(v>0xffffffffull && (int64_t)v!=(int64_t)(int32_t)(uint32_t)v)
        xrt_fatal(c,76,"PeekMessage: message 0x%x %s %llx is not representable in a guest MSG",msg,field,(unsigned long long)v);
    return (uint32_t)v;
}
static void peek_message(CPU*c,int wide) {
    uint32_t out=ARG(0),filter=ARG(1),flags=ARG(4),words[7];HWND h=NULL;MSG m;BOOL r;CPU*prev;XmRequest q={0};
    gui_transition_memory(c,c->r[ESP],24,0);gui_transition_memory(c,out,28,1);
    if(flags&~(PM_REMOVE|PM_NOYIELD))xrt_fatal(c,76,"PeekMessage: queue-status flags %x unmodelled",flags);
    if(filter==0xffffffffu)h=(HWND)(LONG_PTR)-1;else if(filter)h=xrt_gui_device_window(c,filter);
    xrt_dev_input_tick(); /* developer input script: posts its scripted messages before this peek */
    prev=xrt_gui_callback_enter(c);begin(c);
    xrt_dev_input_window_actions(); /* developer input script: window resize, inside the callback region */
    pump_probe(&q,XM_BEGIN,wide?"WIN.PeekMessageW":"WIN.PeekMessageA",(uint64_t)(uintptr_t)h,flags,0);
    r=wide?PeekMessageW(&m,h,ARG(2),ARG(3),flags):PeekMessageA(&m,h,ARG(2),ARG(3),flags);
    pump_probe(&q,XM_END,q.name,(uint64_t)(uintptr_t)h,flags,(uint64_t)r);
    end(c);xrt_gui_callback_leave(prev);
    /* Developer input isolation: physical input messages reach the guest as WM_NULL. */
    if(r && ((m.message>=WM_KEYFIRST&&m.message<=WM_KEYLAST)||(m.message>=WM_MOUSEFIRST&&m.message<=WM_MOUSELAST)||
             (m.message>=WM_NCMOUSEMOVE&&m.message<=WM_NCXBUTTONDBLCLK)||m.message==WM_INPUT) && xrt_dev_input_blocked(NULL) &&
       !xrt_dev_input_allowed(m.hwnd,m.message,(unsigned long long)m.wParam,(long long)m.lParam)) {
        xrt_dev_input_blocked("window input message");m.message=WM_NULL;m.wParam=0;m.lParam=0;
    }
    if(r) {
        words[0]=window_token(m.hwnd);words[1]=m.message;
        words[2]=pump_scalar(c,m.wParam,m.message,"wParam");
        if(m.message==WM_TIMER && (uint64_t)m.lParam>0xffffffffull) {
            /* Host-owned timer: lParam is a TIMERPROC in a loaded host module. Native
             * DispatchMessage calls it directly; the guest copy carries an opaque 0 and
             * Translate/Dispatch forward the retained exact host MSG. */
            HMODULE owner=NULL;
            if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCWSTR)m.lParam,&owner)||!owner)
                xrt_fatal(c,76,"PeekMessage: WM_TIMER procedure %llx outside host modules",(unsigned long long)m.lParam);
            words[3]=0;
        } else words[3]=pump_scalar(c,(uint64_t)m.lParam,m.message,"lParam");
        words[4]=m.time;words[5]=(uint32_t)m.pt.x;words[6]=(uint32_t)m.pt.y;
        memcpy(G2H(out),words,28);
        pump_last=m;pump_guest=out;memcpy(pump_words,words,28);pump_valid=1;
        if(pump_events++<4096)
            xrt_event("gui_peek_message","\"wide\":%d,\"hwnd\":%u,\"message\":%u,\"wparam\":%u,\"lparam\":%u,\"remove\":%u",
                      wide,words[0],words[1],words[2],words[3],flags&PM_REMOVE);
    }
    RET_STD(5,r);
}
static void pump_host_message(CPU*c,uint32_t p,MSG*m) {
    uint32_t words[7];
    gui_transition_memory(c,p,28,0);memcpy(words,G2H(p),28);
    if(pump_valid && p==pump_guest && !memcmp(words,pump_words,28)){*m=pump_last;return;}
    memset(m,0,sizeof *m);
    m->hwnd=words[0]?xrt_gui_device_window(c,words[0]):NULL;m->message=words[1];
    m->wParam=(WPARAM)words[2];m->lParam=(LPARAM)(int32_t)words[3];
    m->time=words[4];m->pt.x=(LONG)words[5];m->pt.y=(LONG)words[6];
}
static void translate_message(CPU*c) {
    MSG m;BOOL r;CPU*prev;XmRequest q={0};
    gui_transition_memory(c,c->r[ESP],8,0);pump_host_message(c,ARG(0),&m);
    prev=xrt_gui_callback_enter(c);begin(c);
    pump_probe(&q,XM_BEGIN,"WIN.TranslateMessage",(uint64_t)(uintptr_t)m.hwnd,m.message,0);
    r=TranslateMessage(&m);
    pump_probe(&q,XM_END,q.name,(uint64_t)(uintptr_t)m.hwnd,m.message,(uint64_t)r);
    end(c);xrt_gui_callback_leave(prev);
    RET_STD(1,r);
}
static void dispatch_message(CPU*c,int wide) {
    MSG m;LRESULT r;CPU*prev;XmRequest q={0};
    gui_transition_memory(c,c->r[ESP],8,0);pump_host_message(c,ARG(0),&m);
    prev=xrt_gui_callback_enter(c);begin(c);
    pump_probe(&q,XM_BEGIN,wide?"WIN.DispatchMessageW":"WIN.DispatchMessageA",(uint64_t)(uintptr_t)m.hwnd,m.message,0);
    r=wide?DispatchMessageW(&m):DispatchMessageA(&m);
    pump_probe(&q,XM_END,q.name,(uint64_t)(uintptr_t)m.hwnd,m.message,(uint64_t)r);
    end(c);xrt_gui_callback_leave(prev);
    RET_STD(1,(uint32_t)r);
}
/* Core appRequestExit(0): PostQuitMessage, then GIsRequestingExit. Native WM_QUIT goes
 * to the calling host thread's queue, which is the guest thread's own queue (one host
 * thread per guest thread), so the guest main loop's PeekMessage sees it and the game
 * runs its normal shutdown (appPreExit, engine/viewport/device/audio teardown, CRT exit,
 * ExitProcess). Nothing is terminated here. */
static void hle_PostQuitMessage(CPU*c) {
    XmRequest q={0};uint32_t code;CPU*prev;
    gui_transition_memory(c,c->r[ESP],8,0);code=ARG(0);
    if(!c->thread || c->thread->state!=1 || c->thread->host_tid!=xm_win_GetCurrentThreadId())
        xrt_fatal(c,76,"PostQuitMessage: caller is not a living guest thread on its own host thread");
    xrt_event("gui_post_quit_message","\"code\":%u,\"guest_tid\":%u",code,c->thread->guest_tid);
    xrt_log("PostQuitMessage(%d) on thread %d: WM_QUIT queued for the guest main loop",(int)code,c->thread->index);
    prev=xrt_gui_callback_enter(c);begin(c);
    pump_probe(&q,XM_BEGIN,"WIN.PostQuitMessage",code,0,0);
    PostQuitMessage((int)code);
    pump_probe(&q,XM_END,q.name,code,0,0);
    end(c);xrt_gui_callback_leave(prev);
    RET_STD(1,0);
}
static void hle_PeekMessageW(CPU*c){peek_message(c,1);}
static void hle_PeekMessageA(CPU*c){peek_message(c,0);}
static void hle_TranslateMessage(CPU*c){translate_message(c);}
static void hle_DispatchMessageW(CPU*c){dispatch_message(c,1);}
static void hle_DispatchMessageA(CPU*c){dispatch_message(c,0);}
/* WinDrv viewport input on the main-loop path. POINT is two guest LONGs. */
static void cursor_point(CPU*c,int op) {
    uint32_t w=op?ARG(0):0,p=op?ARG(1):ARG(0);HWND h=NULL;POINT pt;BOOL ok;CPU*prev;
    gui_transition_memory(c,c->r[ESP],op?12:8,0);gui_transition_memory(c,p,8,1);
    if(op)h=xrt_gui_device_window(c,w);
    pt.x=(LONG)rd32(p);pt.y=(LONG)rd32(p+4);
    if(op==0 && xrt_dev_input_blocked(NULL)) { /* developer isolation: virtual cursor */
        long x,y;xrt_dev_cursor(0,&x,&y,NULL);wr32(p,(uint32_t)x);wr32(p+4,(uint32_t)y);RET_STD(1,1);return;
    }
    prev=xrt_gui_callback_enter(c);begin(c);
    ok=op==0?GetCursorPos(&pt):op==1?ClientToScreen(h,&pt):ScreenToClient(h,&pt);
    end(c);xrt_gui_callback_leave(prev);
    if(ok){wr32(p,(uint32_t)pt.x);wr32(p+4,(uint32_t)pt.y);}
    RET_STD(op?2:1,ok);
}
static void hle_GetCursorPos(CPU*c){cursor_point(c,0);}
static void hle_ClientToScreen(CPU*c){cursor_point(c,1);}
static void hle_ScreenToClient(CPU*c){cursor_point(c,2);}
static void hle_SetCursorPos(CPU*c) {
    BOOL ok;gui_transition_memory(c,c->r[ESP],12,0);
    if(xrt_dev_input_blocked(NULL)){long x=(long)(int32_t)ARG(0),y=(long)(int32_t)ARG(1);xrt_dev_cursor(1,&x,&y,NULL);RET_STD(2,1);return;}
    begin(c);ok=SetCursorPos((int)ARG(0),(int)ARG(1));end(c);RET_STD(2,ok);
}
static void hle_ShowCursor(CPU*c) {
    int n;gui_transition_memory(c,c->r[ESP],8,0);begin(c);n=ShowCursor((BOOL)ARG(0));end(c);RET_STD(1,(uint32_t)n);
}
static void hle_ValidateRect(CPU*c) {
    HWND h=NULL;RECT r,*pr=NULL;BOOL ok;CPU*prev;
    gui_transition_memory(c,c->r[ESP],12,0);
    if(ARG(0))h=xrt_gui_device_window(c,ARG(0));
    if(ARG(1)){gui_transition_memory(c,ARG(1),16,0);r.left=(LONG)rd32(ARG(1));r.top=(LONG)rd32(ARG(1)+4);r.right=(LONG)rd32(ARG(1)+8);r.bottom=(LONG)rd32(ARG(1)+12);pr=&r;}
    prev=xrt_gui_callback_enter(c);begin(c);ok=ValidateRect(h,pr);end(c);xrt_gui_callback_leave(prev);RET_STD(2,ok);
}
static void hle_GetMessageTime(CPU*c){RET_STD(0,(uint32_t)GetMessageTime());}
static void hle_GetParent(CPU*c) {
    HWND p;gui_transition_memory(c,c->r[ESP],8,0);begin(c);p=GetParent(xrt_gui_device_window(c,ARG(0)));end(c);RET_STD(1,window_token(p));
}

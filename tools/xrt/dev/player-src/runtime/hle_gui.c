/* Real USER32/GDI objects behind guest tokens; host pointers never escape. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <imm.h>
#pragma comment(lib,"imm32.lib")
#include <stdlib.h>
#include "xrt_internal.h"
#include "monitor_windows.inc"
typedef struct GuiDC
{
    HDC host;
    HWND window;
    DWORD thread;
    int acquired;
} GuiDC;
static BOOL delete_class_object(uint32_t token, int* handled);
static HINSTANCE class_module(CPU* c,uint32_t guest);
static uint32_t class_owner(CPU* c,HINSTANCE host);
static uint32_t copy_class_string(const void* p,int wide);
static uint32_t known_font_token(HFONT host);
static uint32_t borrowed_icon_token(CPU* c,HICON host);
static HICON guest_icon(CPU* c,uint32_t token);
static void forget_window_properties(HWND host);
static HWND window_host(uint32_t h);
static int registered_getobject_proc(HWND h, uint32_t proc);
static void begin(CPU *c)
{
    SetLastError(xrt_get_last_error(c));
}
static void end(CPU *c)
{
    xrt_set_last_error(c, GetLastError());
}
/* RECT is four guest signed 32-bit fields. Validate every page for both input
 * and output before touching it; committed alone does not imply writable. */
static int writable_guest_rect(uint32_t p)
{
    uint64_t at=p,limit=(uint64_t)p+16;
    if(!p || limit>0x100000000ull)return 0;
    while(at<limit) {
        MEMORY_BASIC_INFORMATION mbi;DWORD access;uint64_t next;
        if(!VirtualQuery(xrt_g+at,&mbi,sizeof mbi) || mbi.State!=MEM_COMMIT ||
            (mbi.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return 0;
        access=mbi.Protect&0xffu;
        if(access!=PAGE_READWRITE && access!=PAGE_WRITECOPY &&
            access!=PAGE_EXECUTE_READWRITE && access!=PAGE_EXECUTE_WRITECOPY)return 0;
        next=(uint64_t)((uint8_t*)mbi.BaseAddress-xrt_g)+mbi.RegionSize;
        if(next<=at)return 0;
        at=next;
    }
    return 1;
}
static void hle_AdjustWindowRect(CPU* c)
{
    uint32_t p=ARG(0),style=ARG(1),menu=ARG(2),esp=c->r[ESP],caller=rd32(esp);
    RECT rect;BOOL result;
    xrt_event("gui_adjust_window_rect_call","\"rect\":%u,\"style\":%u,\"menu\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",
        p,style,menu,esp,caller,xrt_get_last_error(c));
    if(!writable_guest_rect(p))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"AdjustWindowRect: invalid read/write guest RECT %08x (16 bytes); guest pointer faults unsupported",p);
    rect.left=(LONG)(int32_t)rd32(p);rect.top=(LONG)(int32_t)rd32(p+4);
    rect.right=(LONG)(int32_t)rd32(p+8);rect.bottom=(LONG)(int32_t)rd32(p+12);
    xrt_event("gui_adjust_window_rect_input","\"rect\":%u,\"left\":%ld,\"top\":%ld,\"right\":%ld,\"bottom\":%ld",p,rect.left,rect.top,rect.right,rect.bottom);
    begin(c);result=xm_win_AdjustWindowRect(&rect,style,(BOOL)menu);end(c);
    wr32(p,(uint32_t)rect.left);wr32(p+4,(uint32_t)rect.top);
    wr32(p+8,(uint32_t)rect.right);wr32(p+12,(uint32_t)rect.bottom);
    RET_STD(3,result);
    xrt_event("gui_adjust_window_rect_return","\"rect\":%u,\"left\":%ld,\"top\":%ld,\"right\":%ld,\"bottom\":%ld,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        p,rect.left,rect.top,rect.right,rect.bottom,(unsigned)result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* Measured by the same x86 fixture natively and lifted, across all byte virtual
 * keys with per-thread keyboard state. Preserve the signed SHORT and last-error. */
static void hle_GetKeyState(CPU*c) {
    uint32_t key=ARG(0);SHORT result;
    if(key>255)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetKeyState(%u): unmeasured virtual key",key);
    begin(c);result=xm_win_GetKeyState((int)key);end(c);
    if((result&0x8000)&&xrt_dev_input_blocked("GetKeyState down state"))result&=1; /* developer input isolation */
    if(xrt_dev_input_blocked(NULL)&&xrt_dev_key_held(key))result=(SHORT)(0xff80|(result&1)); /* scripted key down */
    RET_STD(1,(uint32_t)(int32_t)result);
}
static void hle_SetKeyboardState(CPU*c) {
    uint32_t p=ARG(0);BOOL result;
    if(p && !xrt_is_committed(p,256))
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetKeyboardState: unreadable 256-byte guest buffer %08x",p);
    begin(c);result=xm_win_SetKeyboardState(p?(BYTE*)G2H(p):NULL);end(c);
    xrt_event("gui_set_keyboard_state","\"buffer\":%u,\"result\":%u,\"last_error\":%u",p,(unsigned)result,xrt_get_last_error(c));
    RET_STD(1,result);
}
static void hle_GetDC(CPU *c)
{
    HDC dc;
    GuiDC *g;
    uint32_t result = 0;
    HWND window=window_host(ARG(0));
    if(ARG(0) && !window) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetDC: unknown guest window %08x",ARG(0));
    begin(c);
    dc = xm_win_GetDC(window);
    end(c);
    if (dc)
    {
        g = (GuiDC *)calloc(1, sizeof *g);
        if (!g)
        {
            xm_win_ReleaseDC(window, dc);
            xrt_fatal(c, XRT_EXIT_SETUP, "GetDC allocation");
        }
        g->host = dc;
        g->window=window;
        g->acquired=1;
        g->thread = xm_win_GetCurrentThreadId();
        result = xrt_handle_new(XH_DC, g);
    }
    xrt_event("gui_get_dc", "\"handle\": %u", result);
    RET_STD(1, result);
}
static void hle_ReleaseDC(CPU *c)
{
    uint32_t token = ARG(1);
    GuiDC *g = (GuiDC *)xrt_handle_get(token, XH_DC);
    int ok = 0;
    HWND window=window_host(ARG(0));
    if(ARG(0) && !window) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ReleaseDC: unknown guest window %08x",ARG(0));
    begin(c);
    if (g && g->acquired && g->window == window && g->thread == xm_win_GetCurrentThreadId())
        ok = xm_win_ReleaseDC(window, g->host);
    end(c);
    if (ok)
    {
        free(g);
        xrt_handle_free(token);
    }
    xrt_event("gui_release_dc", "\"handle\": %u, \"result\": %d", token, ok);
    RET_STD(2, ok);
}
static void hle_GetDeviceCaps(CPU*c) {
    GuiDC*g=(GuiDC*)xrt_handle_get(ARG(0),XH_DC);
    int result;
    if(!g || ARG(1)!=BITSPIXEL)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetDeviceCaps: unmeasured DC/index %08x/%u",ARG(0),ARG(1));
    begin(c); result=xm_win_GetDeviceCaps(g->host,BITSPIXEL); end(c);
    xrt_event("gui_device_caps","\"index\": %u, \"result\": %d",BITSPIXEL,result);
    RET_STD(2,result);
}
static void hle_CreateDIBitmap(CPU *c)
{
    GuiDC *dc = (GuiDC *)xrt_handle_get(ARG(0), XH_DC);
    HBITMAP bitmap;
    uint32_t result = 0;
    if (ARG(0) && !dc)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "CreateDIBitmap: invalid guest DC");
    /* BITMAPINFOHEADER/RGBQUAD contain no pointer fields. */
    begin(c);
    bitmap = xm_win_CreateDIBitmap(dc ? dc->host : NULL, ARG(1) ? (BITMAPINFOHEADER *)G2H(ARG(1)) : NULL, ARG(2),
                            ARG(3) ? G2H(ARG(3)) : NULL, ARG(4) ? (BITMAPINFO *)G2H(ARG(4)) : NULL, ARG(5));
    end(c);
    if (bitmap)
        result = xrt_handle_new(XH_BITMAP, bitmap);
    xrt_event("gui_create_dibitmap", "\"handle\": %u", result);
    RET_STD(6, result);
}
static void hle_CreateBitmap(CPU* c)
{
    HBITMAP bitmap; uint32_t token=0;
    begin(c);
    bitmap=xm_win_CreateBitmap((int)ARG(0),(int)ARG(1),ARG(2),ARG(3),ARG(4)?G2H(ARG(4)):NULL);
    end(c);
    if(bitmap) token=xrt_handle_new(XH_BITMAP,bitmap);
    xrt_event("gui_create_bitmap","\"width\": %d, \"height\": %d, \"handle\": %u",(int)ARG(0),(int)ARG(1),token);
    RET_STD(5,token);
}
static void hle_DeleteObject(CPU *c)
{
    uint32_t token = ARG(0);
    HGDIOBJ obj = (HGDIOBJ)xrt_handle_get(token, XH_BITMAP);
    BOOL ok;
    int handled=0;
    begin(c);
    ok=delete_class_object(token,&handled);
    if(!handled) ok=xm_win_DeleteObject(obj);
    end(c);
    if (ok && handled!=2)
        xrt_handle_free(token);
    xrt_event("gui_delete_object", "\"handle\": %u, \"result\": %d", token, ok);
    RET_STD(1, ok);
}
static void hle_GetDIBits(CPU *c)
{
    GuiDC *dc = (GuiDC *)xrt_handle_get(ARG(0), XH_DC);
    HBITMAP bitmap = (HBITMAP)xrt_handle_get(ARG(1), XH_BITMAP);
    int result;
    if (ARG(0) && !dc)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "GetDIBits: invalid guest DC");
    begin(c);
    result = xm_win_GetDIBits(dc ? dc->host : NULL, bitmap, ARG(2), ARG(3), ARG(4) ? G2H(ARG(4)) : NULL,
                       ARG(5) ? (BITMAPINFO *)G2H(ARG(5)) : NULL, ARG(6));
    end(c);
    RET_STD(7, result);
}
/* Dialog resource and callback bridge. The x86 image is mapped ONLY as resources,
 * never executed by the 64-bit host loader. Host->guest callbacks preserve the suspended CPU. */
typedef struct GuiWindow
{
    HWND host;
    uint32_t token, proc, font;
    int font_local;
    HFONT host_font;
    DWORD thread;
} GuiWindow;
/* D3D8 pins are separate from guest ownership of the HWND itself. */
static unsigned device_window_pins[1024];
static struct { uint32_t token; unsigned count; } destroyed_pins[16];   /* pins of windows destroyed before their device */
static GuiWindow windows[1024];
static __declspec(thread) CPU *callback_cpu;
CPU* xrt_gui_callback_enter(CPU* c) { CPU* previous=callback_cpu;callback_cpu=c;return previous; }
void xrt_gui_callback_leave(CPU* previous) { callback_cpu=previous; }
/* Borrowed IMM32 contexts belong to a thread, not to an individual window.
 * No guest ImmCreate/Destroy/GetContext API is provided. Only returned contexts
 * can be reassociated on their living guest/host thread. Keep tokens after
 * window destruction: the shared default context survives. XrtThread records
 * are never reused, so OS TID reuse cannot revive an expired context. Windows
 * owns context destruction; the bridge never destroys a borrowed HIMC. */
typedef struct GuiIMC {
    HIMC host;
    XrtThread* owner;
    DWORD thread;
    uint32_t token;
} GuiIMC;
static GuiIMC input_contexts[128];
static uint32_t input_context_token(CPU* c,HIMC h) {
    unsigned i;
    if(!h)return 0;
    for(i=0;i<128;i++)if(input_contexts[i].host==h && input_contexts[i].owner==c->thread)
        return input_contexts[i].token;
    for(i=0;i<128;i++)if(!input_contexts[i].host) {
        GuiIMC* p=&input_contexts[i];p->host=h;p->owner=c->thread;p->thread=xm_win_GetCurrentThreadId();
        p->token=xrt_handle_new(XH_IMC,p);return p->token;
    }
    xrt_fatal(c,XRT_EXIT_SETUP,"ImmAssociateContext: borrowed context table full");
}
static void hle_ImmAssociateContext(CPU* c) {
    uint32_t w=ARG(0),ctx=ARG(1),esp=c->r[ESP],caller=rd32(esp),result;
    HWND hwnd=window_host(w);HIMC previous,h=NULL;GuiIMC* p;
    CPU* suspended=callback_cpu;
    DWORD owner=hwnd?xm_win_GetWindowThreadProcessId(hwnd,NULL):0;
    xrt_event("gui_imm_associate_context_call","\"hwnd\":%u,\"context\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",w,ctx,esp,caller,xrt_get_last_error(c));
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ImmAssociateContext: wrong HWND token type %08x",w);
    if(owner && owner!=xm_win_GetCurrentThreadId())
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ImmAssociateContext: cross-thread window unsupported");
    if(ctx) {
        p=(GuiIMC*)xrt_handle_get(ctx,XH_IMC);
        if(!p)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ImmAssociateContext: unknown or wrong-type HIMC token %08x",ctx);
        if(p->owner!=c->thread || p->owner->state!=1 || p->thread!=xm_win_GetCurrentThreadId())
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ImmAssociateContext: foreign or expired thread context unsupported");
        h=p->host;
    }
    /* NULL HWND preserves last-error. Nonzero invalid/destroyed HWNDs instead
     * fail with ERROR_INVALID_WINDOW_HANDLE. Use the measured invalid -1 host
     * sentinel so IMM32 supplies the outcome; never cast guest bits to HWND. */
    if(w && !owner) {
        hwnd=(HWND)(INT_PTR)-1;
        if(xm_win_IsWindow(hwnd))xrt_fatal(c,XRT_EXIT_SETUP,"ImmAssociateContext: invalid HWND sentinel became live");
    }
    begin(c);callback_cpu=c;previous=xm_win_ImmAssociateContext(hwnd,h);end(c);callback_cpu=suspended;
    if(previous && !owner)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ImmAssociateContext: unexpected context from invalid HWND");
    result=input_context_token(c,previous);
    RET_STD(2,result);
    xrt_event("gui_imm_associate_context_return","\"hwnd\":%u,\"context\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",w,ctx,result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
static __declspec(thread) uint32_t creating_proc;
typedef struct GuiCallbackFrame {
    struct GuiCallbackFrame* previous;
    HWND window; UINT message; WPARAM host_wp; LPARAM host_lp;
    uint32_t guest_wp,guest_lp;
    const uint32_t* create_words;
} GuiCallbackFrame;
static __declspec(thread) GuiCallbackFrame* callback_frame;
static HWND window_host(uint32_t h)
{
    return (HWND)xrt_handle_get(h, XH_WINDOW);
}
static uint32_t window_token(HWND h)
{
    unsigned i;
    if (!h)
        return 0;
    for (i = 0; i < 1024; i++)
        if (windows[i].host == h)
            return windows[i].token;
    for (i = 0; i < 1024; i++)
        if (!windows[i].host)
        {
            windows[i].host = h;
            windows[i].thread = xm_win_GetCurrentThreadId();
            windows[i].token = xrt_handle_new(XH_WINDOW, h);
            return windows[i].token;
        }
    xrt_fatal(callback_cpu, XRT_EXIT_SETUP, "GUI window table full");
}
static void forget_dead_windows(void)
{
    unsigned i;
    for (i = 0; i < 1024; i++)
        if (windows[i].host && !xm_win_IsWindow(windows[i].host))
        {
            forget_window_properties(windows[i].host);
            if (windows[i].font && windows[i].font_local)
                xrt_handle_free(windows[i].font);
            xrt_handle_free(windows[i].token);
            memset(&windows[i], 0, sizeof windows[i]);
        }
}
void* xrt_gui_device_window(CPU* c,uint32_t token) {
    HWND h;DWORD pid=0,tid;unsigned i;
    if(!token)return NULL;
    h=window_host(token);
    if(!h || xrt_handle_type(token)!=XH_WINDOW)
        xrt_fatal(c,76,"D3D8: stale, unknown or wrong-type HWND token %08x",token);
    tid=xm_win_GetWindowThreadProcessId(h,&pid);
    if(!xm_win_IsWindow(h) || pid!=xm_win_GetCurrentProcessId() || tid!=xm_win_GetCurrentThreadId() || !c->thread || c->thread->host_tid!=tid)
        xrt_fatal(c,76,"D3D8: foreign, dead or cross-thread HWND token %08x",token);
    for(i=0;i<1024;i++)if(windows[i].host==h && windows[i].token==token && windows[i].thread==tid)return h;
    xrt_fatal(c,76,"D3D8: HWND token lacks GUI registry identity %08x",token);
}
uint32_t xrt_gui_window_identity(CPU* c,void* host) {
    unsigned i;if(!host)return 0;
    for(i=0;i<1024;i++)if(windows[i].host==host && window_host(windows[i].token)==host) {
        xrt_gui_device_window(c,windows[i].token);return windows[i].token;
    }
    xrt_fatal(c,76,"D3D8: unregistered native HWND result (no pointer narrowing)");
}
void xrt_gui_window_pin(CPU* c,uint32_t token) {
    unsigned i;if(!token)return;xrt_gui_device_window(c,token);
    for(i=0;i<1024;i++)if(windows[i].token==token && windows[i].host) {device_window_pins[i]++;return;}
}
int xrt_gui_window_destroyed(uint32_t token) {
    unsigned i;
    for(i=0;token && i<16;i++)if(destroyed_pins[i].token==token)return 1;
    return 0;
}
void xrt_gui_window_unpin(uint32_t token) {
    unsigned i;if(!token)return;
    for(i=0;i<1024;i++)if(windows[i].token==token && windows[i].host && device_window_pins[i]) {device_window_pins[i]--;return;}
    for(i=0;i<16;i++)if(destroyed_pins[i].token==token && destroyed_pins[i].count) {   /* window destroyed first (hle_DestroyWindow) */
        if(!--destroyed_pins[i].count)destroyed_pins[i].token=0;
        return;
    }
    xrt_fatal(NULL,77,"D3D8: window pin accounting mismatch %08x",token);
}
/* USER32 queries this calling thread's actual input queue. Never substitute the
 * active/foreground window or cache focus. Existing GUI tokens also represent
 * a live focused HWND first encountered here (e.g. a native stock control). */
/* Only the observed self-thread boundary is characterized. The real USER32
 * call supplies BOOL and last-error, including its failure on self attachment.
 * Cross-thread queue sharing remains guarded; no guest scalar becomes a pointer. */
static void hle_AttachThreadInput(CPU* c) {
    uint32_t from=ARG(0),to=ARG(1),attach=ARG(2),esp=c->r[ESP],caller=rd32(esp);
    DWORD tid=xm_win_GetCurrentThreadId();BOOL result;
    xrt_event("gui_attach_thread_input_call","\"from\":%u,\"to\":%u,\"attach\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",
        from,to,attach,esp,caller,xrt_get_last_error(c));
    if(!c->thread || c->thread->state!=1 || c->thread->host_tid!=tid ||
       c->thread->guest_tid!=tid || from!=tid || to!=tid)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"AttachThreadInput: only the living current guest/host self-thread pair is measured (%u,%u)",from,to);
    begin(c);result=xm_win_AttachThreadInput(from,to,(BOOL)attach);end(c);
    RET_STD(3,result);
    xrt_event("gui_attach_thread_input_return","\"from\":%u,\"to\":%u,\"attach\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        from,to,attach,(unsigned)result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}

static HWND dev_background_active,dev_background_focus; /* developer background mode: virtual activation (below) */
static void hle_GetFocus(CPU* c)
{
    HWND h;uint32_t result,esp=c->r[ESP],caller=rd32(esp);
    xrt_event("gui_get_focus_call","\"esp\":%u,\"return\":%u",esp,caller);
    begin(c);h=xm_win_GetFocus();
    if(!h&&xrt_dev_background()&&dev_background_focus&&IsWindow(dev_background_focus))h=dev_background_focus; /* virtual focus */
    end(c);
    result=window_token(h);
    RET_STD(0,result);
    xrt_event("gui_get_focus_return","\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u,\"result\":%u,\"last_error\":%u",
        esp,c->r[ESP],caller,c->rv,result,xrt_get_last_error(c));
}
/* Developer background mode (xrt_dev_background): while another process owns the real foreground, the guest
 * sees its own thread's active window (else its first visible unowned top-level window) as the foreground.
 * WinDrv's capture sequence (GetForegroundWindow, AttachThreadInput to that window's thread,
 * SetForegroundWindow, SetActiveWindow) then stays on its own thread and never takes the owner's focus. */
static BOOL CALLBACK dev_background_top(HWND h,LPARAM p) {
    if(IsWindowVisible(h)&&!GetWindow(h,GW_OWNER)){*(HWND*)p=h;return FALSE;}
    return TRUE;
}
/* Activation stays virtual while another process owns the foreground: with the foreground lock timeout expired
 * (an idle owner) or an inherited foreground right, a real SetActiveWindow/SetFocus of the game's window takes the
 * owner's focus (measured: experiments/xrt/tests/bg_input BG_PROBE=a). The guest's GetFocus/GetForegroundWindow then
 * report the window it last focused/activated; no activation messages are synthesized. */
static int dev_background_foreign(void) {
    DWORD pid=0;HWND fg=GetForegroundWindow();
    if(fg)GetWindowThreadProcessId(fg,&pid);
    return pid!=GetCurrentProcessId();
}
/* Standalone player (xrt_player_mode): once the game has had the foreground and the player then switched to another
 * application, the game's own activation requests stay virtual as in background mode (an idle desktop or an inherited
 * foreground right would otherwise let them pull the game back to the front). Clicking or Alt+Tabbing back activates
 * the window natively; from then on the calls pass again. */
static int player_switched_away(void) {
    static int had_foreground;static unsigned logged;
    if(!xrt_player_mode)return 0;
    if(!dev_background_foreign()){had_foreground=1;return 0;}
    if(had_foreground&&logged++<8)xrt_log("player: the game's activation request stays virtual (another application is in front)");
    return had_foreground;
}
static HWND dev_background_foreground(HWND h) {
    static unsigned logged;DWORD pid=0;HWND own;
    if(h)GetWindowThreadProcessId(h,&pid);
    if(pid==GetCurrentProcessId())return h;
    own=GetActiveWindow();
    if(!own&&dev_background_active&&IsWindow(dev_background_active))own=dev_background_active;
    if(!own)EnumThreadWindows(GetCurrentThreadId(),dev_background_top,(LPARAM)&own);
    if(logged++<8)xrt_log("DEV background: GetForegroundWindow host %p (pid %lu) reported to the guest as own window %p",h,pid,own);
    return own?own:h;
}
/* Developer background mode: activating show commands become their non-activating forms and a shown
 * top-level window goes to the bottom of the z-order (rendering continues; the owner's windows stay on top). */
static int dev_background_show(int cmd) {
    switch(cmd){case SW_SHOWNORMAL:case SW_RESTORE:case SW_SHOWDEFAULT:return SW_SHOWNOACTIVATE;
                case SW_SHOW:return SW_SHOWNA;case SW_SHOWMINIMIZED:case SW_MINIMIZE:return SW_SHOWMINNOACTIVE;default:return cmd;}
}
static void dev_background_bottom(HWND h) {
    if(h&&!(GetWindowLongW(h,GWL_STYLE)&WS_CHILD)&&IsWindowVisible(h))
        SetWindowPos(h,HWND_BOTTOM,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOOWNERZORDER);
}
/* Borrow the actual foreground HWND, which may belong to another process.
 * This query neither acquires ownership nor transfers focus/callback execution. */
static void hle_GetForegroundWindow(CPU* c)
{
    HWND h;uint32_t result,esp=c->r[ESP],caller=rd32(esp);
    xrt_event("gui_foreground_call","\"esp\":%u,\"return\":%u,\"last_error\":%u",esp,caller,xrt_get_last_error(c));
    begin(c);h=xm_win_GetForegroundWindow();if(xrt_dev_background())h=dev_background_foreground(h);end(c);
    result=window_token(h);
    xrt_event("gui_foreground_identity","\"host\":\"%llx\",\"token\":%u,\"roundtrip\":%u",
        (unsigned long long)(uintptr_t)h,result,window_host(result)==h);
    RET_STD(0,result);
    xrt_event("gui_foreground_return","\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* Measured owned-window foreground request. USER32 decides success and may
 * synchronously reenter the existing activation/focus callback bridge. */
static void hle_SetForegroundWindow(CPU* c)
{
    uint32_t w=ARG(0),esp=c->r[ESP],caller=rd32(esp);BOOL result;
    HWND hwnd=window_host(w);CPU* suspended=callback_cpu;
    xrt_event("gui_set_foreground_call","\"hwnd\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",w,esp,caller,xrt_get_last_error(c));
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetForegroundWindow: wrong HWND token type %08x",w);
    if(w && !hwnd)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetForegroundWindow: unknown HWND token %08x",w);
    if(hwnd && xm_win_GetWindowThreadProcessId(hwnd,NULL)!=xm_win_GetCurrentThreadId())
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetForegroundWindow: cross-thread window unmeasured");
    if(xrt_dev_background()||player_switched_away()) { /* developer background mode / player in another application: not passed on */
        static unsigned logged;
        begin(c);result=hwnd&&IsWindow(hwnd)&&xrt_dev_background();end(c);   /* player: refused, as USER32 would */
        if(logged++<8)xrt_log("DEV background: SetForegroundWindow(%p) not passed on (result %d)",hwnd,(int)result);
    } else {
    callback_cpu=c;begin(c);result=xm_win_SetForegroundWindow(hwnd);end(c);callback_cpu=suspended;
    }
    RET_STD(1,result);
    xrt_event("gui_set_foreground_return","\"hwnd\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",w,(unsigned)result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* Return USER32's actual previous active HWND through the shared typed map. */
static void hle_SetActiveWindow(CPU* c)
{
    uint32_t w=ARG(0),esp=c->r[ESP],caller=rd32(esp),result;
    HWND hwnd=window_host(w),previous;CPU* suspended=callback_cpu;
    xrt_event("gui_set_active_call","\"hwnd\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",w,esp,caller,xrt_get_last_error(c));
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetActiveWindow: wrong HWND token type %08x",w);
    if(w && !hwnd)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetActiveWindow: unknown HWND token %08x",w);
    if(hwnd && xm_win_GetWindowThreadProcessId(hwnd,NULL)!=xm_win_GetCurrentThreadId())
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetActiveWindow: cross-thread window unmeasured");
    if((xrt_dev_background()||player_switched_away())&&hwnd&&dev_background_foreign()) { /* developer background mode: virtual activation */
        static unsigned logged;
        begin(c);previous=GetActiveWindow();if(!previous&&dev_background_active&&IsWindow(dev_background_active))previous=dev_background_active;
        dev_background_active=hwnd;end(c);
        if(logged++<8)xrt_log("DEV background: SetActiveWindow(%p) kept virtual (previous %p)",hwnd,previous);
    } else {
    callback_cpu=c;begin(c);previous=xm_win_SetActiveWindow(hwnd);end(c);callback_cpu=suspended;
    }
    result=window_token(previous);RET_STD(1,result);
    xrt_event("gui_set_active_return","\"hwnd\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",w,result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* SetFocus returns USER32's previous HWND, including native reentrant activation
 * behavior. Never derive it from the requested HWND or a cached focus value. */
static void hle_SetFocus(CPU* c)
{
    uint32_t w=ARG(0),esp=c->r[ESP],caller=rd32(esp),result;
    HWND hwnd=window_host(w),previous;CPU* suspended=callback_cpu;
    DWORD owner=hwnd?xm_win_GetWindowThreadProcessId(hwnd,NULL):0;
    xrt_event("gui_set_focus_call","\"hwnd\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",
        w,esp,caller,xrt_get_last_error(c));
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetFocus: wrong HWND token type %08x",w);
    /* Attached input queues and cross-thread callback/baton transfer are outside
     * this boundary. Native unattached attempts return NULL / error 5. */
    if(owner && owner!=xm_win_GetCurrentThreadId())
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetFocus: cross-thread window unsupported");
    if(w && !hwnd) {
        hwnd=(HWND)(intptr_t)-1;
        if(xm_win_IsWindow(hwnd))xrt_fatal(c,XRT_EXIT_SETUP,"SetFocus: invalid HWND sentinel unexpectedly valid");
    }
    if((xrt_dev_background()||player_switched_away())&&w&&hwnd!=(HWND)(intptr_t)-1&&dev_background_foreign()&&GetActiveWindow()!=GetAncestor(hwnd,GA_ROOT)) {
        /* developer background mode: focusing a window outside the thread's (real) active window would activate it */
        static unsigned logged;
        begin(c);previous=GetFocus();if(!previous&&dev_background_focus&&IsWindow(dev_background_focus))previous=dev_background_focus;
        dev_background_focus=hwnd;end(c);
        if(logged++<8)xrt_log("DEV background: SetFocus(%p) kept virtual (previous %p)",hwnd,previous);
    } else {
    if(!w)dev_background_focus=NULL;
    callback_cpu=c;begin(c);previous=xm_win_SetFocus(hwnd);end(c);callback_cpu=suspended;
    }
    result=window_token(previous);
    RET_STD(1,result);
    xrt_event("gui_set_focus_return","\"hwnd\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        w,result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* Measured SetCapture, including NULL and reentrant capture-change callbacks.
 * USER32 owns capture state and supplies the previous HWND; guest memory sees
 * only typed tokens. ReleaseCapture is not substituted for the NULL call. */
static void hle_SetCapture(CPU* c)
{
    uint32_t w=ARG(0),esp=c->r[ESP],caller=rd32(esp),result;
    HWND hwnd=window_host(w),previous;CPU* suspended=callback_cpu;
    DWORD owner=hwnd?xm_win_GetWindowThreadProcessId(hwnd,NULL):0;
    xrt_event("gui_set_capture_call","\"hwnd\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",
        w,esp,caller,xrt_get_last_error(c));
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetCapture: wrong HWND token type %08x",w);
    /* Native unattached foreign-window attempts leave both queues unchanged.
     * Attached queues and cross-thread callback transfer remain unmeasured. */
    if(owner && owner!=xm_win_GetCurrentThreadId())
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SetCapture: cross-thread window unsupported");
    if(w && !hwnd) {
        hwnd=(HWND)(intptr_t)-1;
        if(xm_win_IsWindow(hwnd))xrt_fatal(c,XRT_EXIT_SETUP,"SetCapture: invalid HWND sentinel unexpectedly valid");
    }
    callback_cpu=c;begin(c);previous=xm_win_SetCapture(hwnd);end(c);callback_cpu=suspended;
    result=window_token(previous);
    RET_STD(1,result);
    xrt_event("gui_set_capture_return","\"hwnd\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",
        w,result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* Only the encountered NULL RECT path is measured. USER32 releases the real
 * cursor constraint; no guest RECT or synthetic clip state is introduced. */
static void hle_ClipCursor(CPU* c)
{
    uint32_t p=ARG(0),esp=c->r[ESP],caller=rd32(esp);BOOL result;
    xrt_event("gui_clip_cursor_call","\"rect\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",p,esp,caller,xrt_get_last_error(c));
    if(p) {
        /* WinDrv SetMouseCapture: four guest LONGs, copied; the launcher restores the clip. */
        RECT r;
        if(!writable_guest_rect(p))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ClipCursor: RECT outside writable guest memory");
        r.left=(LONG)rd32(p);r.top=(LONG)rd32(p+4);r.right=(LONG)rd32(p+8);r.bottom=(LONG)rd32(p+12);
        if(xrt_dev_input_blocked(NULL)){xrt_dev_cursor(2,NULL,NULL,&r);result=1;} /* developer isolation: virtual cursor only */
        else{begin(c);result=xm_win_ClipCursor(&r);end(c);}
    } else if(xrt_dev_input_blocked(NULL)) {
        xrt_dev_cursor(2,NULL,NULL,NULL);result=1;
    } else {
        begin(c);result=xm_win_ClipCursor(NULL);end(c);
    }
    RET_STD(1,result);
    xrt_event("gui_clip_cursor_return","\"rect\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",p,(unsigned)result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
/* Optional output is exactly one DWORD, including unaligned/page-edge writes.
 * A failed HWND query never probes or modifies that output, as measured natively. */
static int writable_guest_id(uint32_t p) {
    uint64_t at=p,limit=(uint64_t)p+4;
    if(!p || limit>0x100000000ull)return 0;
    while(at<limit) {
        MEMORY_BASIC_INFORMATION mbi;DWORD access;uint64_t next;
        if(!VirtualQuery(xrt_g+at,&mbi,sizeof mbi) || mbi.State!=MEM_COMMIT || (mbi.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return 0;
        access=mbi.Protect&0xffu;
        if(access!=PAGE_READWRITE && access!=PAGE_WRITECOPY && access!=PAGE_EXECUTE_READWRITE && access!=PAGE_EXECUTE_WRITECOPY)return 0;
        next=(uint64_t)((uint8_t*)mbi.BaseAddress-xrt_g)+mbi.RegionSize;if(next<=at)return 0;at=next;
    }
    return 1;
}
static void hle_GetWindowThreadProcessId(CPU* c) {
    uint32_t w=ARG(0),p=ARG(1),esp=c->r[ESP],caller=rd32(esp);DWORD pid=0,tid;HWND h=window_host(w);
    xrt_event("gui_window_ids_call","\"hwnd\":%u,\"output\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",w,p,esp,caller,xrt_get_last_error(c));
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetWindowThreadProcessId: wrong HWND token type %08x",w);
    if(w && !h) {h=(HWND)(intptr_t)-1;if(xm_win_IsWindow(h))xrt_fatal(c,XRT_EXIT_SETUP,"GetWindowThreadProcessId invalid HWND sentinel unexpectedly valid");}
    begin(c);tid=xm_win_GetWindowThreadProcessId(h,p?&pid:NULL);end(c);
    if(tid && p) {
        if(!writable_guest_id(p))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"GetWindowThreadProcessId: invalid four-byte output %08x; native output pointer fault path unsupported",p);
        wr32(p,pid);
    }
    RET_STD(2,tid);
    xrt_event("gui_window_ids_return","\"hwnd\":%u,\"output\":%u,\"result\":%u,\"pid\":%u,\"written\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",w,p,tid,pid,tid&&p?1:0,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
static HWND map_points_window(CPU* c,uint32_t w) {
    HWND h=window_host(w);
    if(w && xrt_handle_type(w)!=XH_FREE && xrt_handle_type(w)!=XH_WINDOW)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"MapWindowPoints: wrong HWND token type %08x",w);
    if(w && !h) {h=(HWND)(intptr_t)-1;if(xm_win_IsWindow(h))xrt_fatal(c,XRT_EXIT_SETUP,"MapWindowPoints invalid HWND sentinel unexpectedly valid");}
    return h;
}
static void hle_MapWindowPoints(CPU* c) {
    uint32_t a=ARG(0),b=ARG(1),p=ARG(2),n=ARG(3),esp=c->r[ESP],caller=rd32(esp),i;
    POINT points[4];HWND from,to;int result;
    xrt_event("gui_map_points_call","\"from\":%u,\"to\":%u,\"points\":%u,\"count\":%u,\"esp\":%u,\"return\":%u,\"last_error\":%u",a,b,p,n,esp,caller,xrt_get_last_error(c));
    if(n<1 || n>4)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"MapWindowPoints: unmeasured point count %u",n);
    from=map_points_window(c,a);to=map_points_window(c,b);
    if(!p || (uint64_t)p+8*n>0x100000000ull)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"MapWindowPoints: invalid guest point array %08x",p);
    for(i=0;i<2*n;i++)if(!writable_guest_id(p+4*i))xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"MapWindowPoints: invalid guest point array %08x",p);
    memcpy(points,G2H(p),8*n);
    for(i=0;i<n;i++)xrt_event("gui_map_points_input","\"index\":%u,\"x\":%ld,\"y\":%ld",i,points[i].x,points[i].y);
    begin(c);result=xm_win_MapWindowPoints(from,to,points,n);end(c);
    memcpy(G2H(p),points,8*n);
    for(i=0;i<n;i++)xrt_event("gui_map_points_output","\"index\":%u,\"x\":%ld,\"y\":%ld",i,points[i].x,points[i].y);
    RET_STD(4,(uint32_t)result);
    xrt_event("gui_map_points_return","\"from\":%u,\"to\":%u,\"points\":%u,\"count\":%u,\"result\":%u,\"last_error\":%u,\"esp_before\":%u,\"esp_after\":%u,\"return\":%u,\"actual_return\":%u",a,b,p,n,(uint32_t)result,xrt_get_last_error(c),esp,c->r[ESP],caller,c->rv);
}
static void pack_windowpos(uint32_t p, const WINDOWPOS *w)
{
    wr32(p, window_token(w->hwnd));
    wr32(p + 4, (intptr_t)w->hwndInsertAfter >= -2 && (intptr_t)w->hwndInsertAfter <= 1
                    ? (uint32_t)(intptr_t)w->hwndInsertAfter
                    : window_token(w->hwndInsertAfter));
    wr32(p + 8, w->x);
    wr32(p + 12, w->y);
    wr32(p + 16, w->cx);
    wr32(p + 20, w->cy);
    wr32(p + 24, w->flags);
}
static HWND insert_host(uint32_t v)
{
    HWND host;
    if (v >= 0xfffffffeu || v <= 1)
        return (HWND)(intptr_t)(int32_t)v;
    host = window_host(v);
    if (!host)
        xrt_fatal(callback_cpu, XRT_EXIT_UNSUPPORTED, "window insertion handle %08x unknown", v);
    return host;
}
static void unpack_windowpos(WINDOWPOS *w, uint32_t p)
{
    w->hwnd = window_host(rd32(p));
    w->hwndInsertAfter = insert_host(rd32(p + 4));
    w->x = (int)rd32(p + 8);
    w->y = (int)rd32(p + 12);
    w->cx = (int)rd32(p + 16);
    w->cy = (int)rd32(p + 20);
    w->flags = rd32(p + 24);
}
/* Developer benchmarking only (dev.py --windowed-res): XRT_DEV_MAX_TRACK=WxH raises the maximum tracking size the
 * guest's WM_GETMINMAXINFO result reports, so a requested window larger than the desktop is not clamped by the system
 * default (virtual screen + frame). Otherwise the client is clamped while D3DDrv keeps the requested back buffer, the
 * sizes differ and DXVK presents through GDI. The window then extends beyond the display: a larger-than-display render
 * surface, not native-display output. Unset (normal runs): the guest's result is returned unchanged. */
static void dev_max_track(MINMAXINFO *m)
{
    static int w = -1, h = 0;
    if (w < 0)
    {
        char v[32];
        DWORD n = GetEnvironmentVariableA("XRT_DEV_MAX_TRACK", v, sizeof v);
        const char *x = n && n < sizeof v ? strchr(v, 'x') : NULL;
        w = x ? atoi(v) : 0;
        h = x ? atoi(x + 1) : 0;
        if (w > 0 && h > 0)
            xrt_log("DEV window maximum tracking size raised to at least %dx%d (larger-than-display benchmarking)", w, h);
    }
    if (w > 0 && h > 0)
    {
        if (m->ptMaxTrackSize.x < w) m->ptMaxTrackSize.x = w;
        if (m->ptMaxTrackSize.y < h) m->ptMaxTrackSize.y = h;
    }
}
#include "hle_gui_diag.inc"
#include "window_transitions.inc"
#include "message_pump.inc"
static INT_PTR invoke_gui_proc(HWND h, UINT msg, WPARAM wp, LPARAM lp, uint32_t explicit_proc)
{
    /* F1: Windows' help request reached the game's main dialog and stopped the run (owner's runs 20261101-211738,
     * -215600): first the undocumented WM_KEYF1 (0x4D, both arguments 0) that DefDlgProc turns into WM_HELP (0x53,
     * lParam a HELPINFO pointer). The game has no Windows help to offer; both are answered as handled here and never
     * cross to the guest. The F1 key itself still reaches the game as WM_KEYDOWN/DirectInput. */
    if (msg == WM_HELP || msg == 0x4D /* WM_KEYF1 */)
    {
        static unsigned logged;
        if (logged++ < 4) xrt_log("F1 help request (message %x) answered as handled; not passed to the game", msg);
        return TRUE;
    }
    xm_scope(callback_cpu,XM_BEGIN,XM_CALLBACK,"USER32.invoke_gui_proc",msg);
    CPU nested;
    uint32_t args[4], proc = explicit_proc, scratch = 0;
    unsigned i;
    INT_PTR result;
    GuiWindow *window = NULL;
    DWORD error = GetLastError();
    GuiCallbackFrame frame;
    uint32_t create_words[12];
    gui_diagnostic_ingress(h,msg,wp,lp,explicit_proc);
    if (!callback_cpu)
        xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "GUI callback outside an active guest host call");
    args[0] = window_token(h);
    args[1] = msg;
    args[2] = (uint32_t)wp;
    args[3] = (uint32_t)lp;
    for (i = 0; i < 1024; i++)
        if (windows[i].host == h)
        {
            window = &windows[i];
            if (!window->proc && !explicit_proc)
                window->proc = creating_proc;
            if (!explicit_proc) proc = window->proc;
            break;
        }
    if (!proc)
        { INT_PTR xm_ret=(FALSE);xm_scope(callback_cpu,XM_END,XM_CALLBACK,"USER32.invoke_gui_proc",(uint64_t)xm_ret);return xm_ret;}
    nested = *callback_cpu;
    xrt_set_last_error(&nested, error);
    /* Temporary structures use the guest stack below the suspended import frame. */
    scratch = (nested.r[ESP] - 128u) & ~15u;
    nested.r[ESP] = scratch;
    switch (msg)
    {
    case WM_GETOBJECT:
    {
        /* Separate native x86/x64 dialog and registered-window oracles. The
         * registered WNDPROC executes and may delegate through its validated
         * callback frame to real DefWindowProcW. No accessibility cookie is
         * manufactured. Other IDs/arguments and unregistered procs stay guarded. */
        int registered = explicit_proc && registered_getobject_proc(h, explicit_proc);
        int client = wp == (WPARAM)0xffffffffu && (DWORD)lp == (DWORD)OBJID_CLIENT &&
            (lp == (LPARAM)(ULONG_PTR)(DWORD)OBJID_CLIENT || lp == (LPARAM)(LONG)OBJID_CLIENT);
        /* Measured separately on a real registered Unicode WNDPROC: scalar
         * class-name-index query, wParam=0, zero/sign-extended -12. Windows
         * DefWindowProcW supplies the result through the active callback frame.
         * This does not admit the tuple to the unmeasured dialog protocol. */
        int query_class = registered && wp == 0 && (DWORD)lp == (DWORD)-12 &&
            (lp == (LPARAM)(ULONG_PTR)(DWORD)-12 || lp == (LPARAM)(LONG)-12);
        if ((explicit_proc && !registered) || !xm_win_IsWindowUnicode(h) || (!client && !query_class))
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED,
                      "WM_GETOBJECT: unmeasured dialog/arguments (wp=%llx lp=%llx)",
                      (unsigned long long)wp, (unsigned long long)lp);
        break;
    }
    case WM_GETICON:
        if(wp>ICON_SMALL2 || ((uint64_t)(uintptr_t)lp>0xffffffffull && lp!=(LPARAM)(int32_t)(uint32_t)lp))
            xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"WM_GETICON: invalid selector or unrepresentable DPI %llu/%lld",(unsigned long long)wp,(long long)lp);
        break;
    case WM_SETTEXT:
        args[3]=copy_class_string((void*)lp,xm_win_IsWindowUnicode(h));
        break;
    case WM_CREATE:
    case WM_NCCREATE:
        {
            CREATESTRUCTW* s=(CREATESTRUCTW*)lp;
            if((uintptr_t)s->lpCreateParams>0xffffffffu)
                xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"CREATESTRUCT contains a non-guest creation parameter");
            if(s->hMenu && !(s->style&WS_CHILD))
                xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"CREATESTRUCT menu requires typed mapping");
            wr32(scratch,(uint32_t)(uintptr_t)s->lpCreateParams);
            wr32(scratch+4,class_owner(&nested,s->hInstance));
            wr32(scratch+8,(uint32_t)(uintptr_t)s->hMenu);
            wr32(scratch+12,window_token(s->hwndParent));
            wr32(scratch+16,s->cy);wr32(scratch+20,s->cx);wr32(scratch+24,s->y);wr32(scratch+28,s->x);
            wr32(scratch+32,s->style);
            wr32(scratch+36,copy_class_string(s->lpszName,xm_win_IsWindowUnicode(h)));
            wr32(scratch+40,copy_class_string(s->lpszClass,xm_win_IsWindowUnicode(h)));
            wr32(scratch+44,s->dwExStyle);
            args[3]=scratch;
            memcpy(create_words,G2H(scratch),48);
        }
        break;
    case WM_USER + 77: /* Class oracle's explicitly scalar nested callback. */
        if (h || wp > 100 || lp > 100)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "class oracle scalar message outside measured range");
        break;
    case 0xae: /* WM_NCUAHDRAWCAPTION (uxtheme caption redraw): wParam is a scalar set of caption-part flags, lParam 0.
                * Measured (8,0)/(9,0) with real default processing; beta batch run 20261102-202449 got (0x1000,0) from the
                * host theme and was refused. Any 32-bit flag set crosses as is; 0xaf (wParam = HDC) stays refused. */
        if(wp>0xffffffffu || lp)
            xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"window callback 0xae: unmeasured arguments (wp=%llx lp=%llx)",(unsigned long long)wp,(unsigned long long)lp);
        break;
    case 0x90: /* Observed Windows theme destruction notification: both arguments zero. */
        if (wp || lp)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "theme destruction notification has nonzero arguments");
        break;
    case WM_DEVICECHANGE: /* Host broadcast: the scalar DBT_DEVNODES_CHANGED (7,0) form crosses as is. */
        if (wp == 7 && !lp)
            break;
        /* DBT_DEVICEARRIVAL / DBT_DEVICEREMOVECOMPLETE carry a read-only DEV_BROADCAST_* structure of dbch_size
         * bytes (observed 0x8004 when a host device went away during a run). It is copied onto the guest stack below
         * the callback scratch and the guest stack pointer moves below it; DefWindowProc/CallWindowProc get the host
         * structure back through the callback frame (forward_message). Nothing is copied back: no output fields. */
        if ((wp == 0x8000 || wp == 0x8004) && lp)
        {
            DWORD size;
            uint32_t data;
            memcpy(&size, (const void *)lp, 4);
            if (size < 12 || size > 1024)
                xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_DEVICECHANGE %llx: DEV_BROADCAST size %lu outside 12..1024",
                          (unsigned long long)wp, (unsigned long)size);
            data = (scratch - ((size + 15u) & ~15u)) & ~15u;
            gui_transition_memory(&nested, data, size, 1);
            memcpy(G2H(data), (const void *)lp, size);
            nested.r[ESP] = data;
            args[3] = data;
            break;
        }
        xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_DEVICECHANGE event %llx with data %llx requires marshalling",
                  (unsigned long long)wp, (unsigned long long)lp);
        break;
    case WM_GETDLGCODE:
        if (lp)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_GETDLGCODE MSG pointer requires marshalling");
        break;
    case WM_NCPAINT:
        /* wParam 1 = whole frame, else an update-region HRGN. A 32-bit process sees the
         * handle's 32-bit value (GDI handles are 32-bit significant); forward_message
         * restores the host value when the guest passes it on to the default procedure. */
        if (wp != 1 && (WPARAM)(LONG_PTR)(int32_t)(uint32_t)wp != wp)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_NCPAINT region handle is not 32-bit representable");
        { static unsigned ncpaints; if (ncpaints++ < 8) xrt_log("WM_NCPAINT %s wParam %llx", wp == 1 ? "whole frame" : "region", (unsigned long long)wp); }
        break;
    case WM_STYLECHANGING: case WM_STYLECHANGED:
        if(!lp || ((int32_t)wp!=GWL_STYLE && (int32_t)wp!=GWL_EXSTYLE))
            xrt_fatal(&nested,76,"style callback: unsupported field or NULL structure");
        gui_transition_memory(&nested,scratch,8,1);memcpy(G2H(scratch),(void*)lp,8);args[3]=scratch;
        break;
    case WM_WINDOWPOSCHANGING:
    case WM_WINDOWPOSCHANGED:
        pack_windowpos(scratch, (WINDOWPOS *)lp);
        args[3] = scratch;
        break;
    case WM_GETMINMAXINFO:
        memcpy(G2H(scratch), (void *)lp, 40);
        args[3] = scratch;
        break;
    case WM_SIZING:
    case WM_MOVING:
        /* User drag of the window border/caption: wParam is the edge (scalar), lParam an in/out screen RECT the
         * procedure may adjust; copied to the scratch and back after the callback (and around DefWindowProc). */
        memcpy(G2H(scratch), (void *)lp, 16);
        args[3] = scratch;
        break;
    case WM_NCCALCSIZE:
        if (wp)
        {
            NCCALCSIZE_PARAMS *n = (NCCALCSIZE_PARAMS *)lp;
            memcpy(G2H(scratch), n->rgrc, 48);
            wr32(scratch + 48, scratch + 52);
            pack_windowpos(scratch + 52, n->lppos);
        }
        else
            memcpy(G2H(scratch), (void *)lp, 16);
        args[3] = scratch;
        break;
    case WM_SETFONT:
        if (window->host_font != (HFONT)wp)
        {
            if (window->font && window->font_local)
                xrt_handle_free(window->font);
            window->host_font = (HFONT)wp;
            window->font = known_font_token((HFONT)wp);
            window->font_local=wp && !window->font;
            if(window->font_local) window->font=xrt_handle_new(XH_FONT,(void*)wp);
        }
        args[2] = window->font;
        break;
    case WM_ERASEBKGND:
    case WM_CTLCOLORSTATIC:
    case WM_CTLCOLORDLG:
    case WM_CTLCOLOREDIT:
    case WM_CTLCOLORBTN:
        /* Borrowed DC valid only for this callback; no acquired ownership. */
        {
            GuiDC *dc = (GuiDC *)calloc(1, sizeof *dc);
            if (!dc)
                xrt_fatal(&nested, XRT_EXIT_SETUP, "callback DC allocation");
            dc->host = (HDC)wp;
            dc->window = h;
            args[2] = xrt_handle_new(XH_DC, dc);
            if (msg != WM_ERASEBKGND)
                args[3] = window_token((HWND)lp);
        }
        break;
    case WM_INITDIALOG: /* lp is the ORIGINAL guest initialization value supplied to CreateDialogParam. */
        args[2] = window_token((HWND)wp);
        break;
    case WM_ACTIVATE:
    case WM_SETFOCUS:
    case WM_KILLFOCUS:
        if (msg == WM_ACTIVATE)
            args[3] = window_token((HWND)lp);
        else
            args[2] = window_token((HWND)wp);
        break;
    case WM_CAPTURECHANGED:
        if(wp)xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"WM_CAPTURECHANGED nonzero wParam unsupported");
        args[3] = window_token((HWND)lp);
        break;
    case WM_COMMAND:
        args[3] = window_token((HWND)lp);
        break;
    case WM_PARENTNOTIFY:
        if(LOWORD(wp)!=WM_CREATE && LOWORD(wp)!=WM_DESTROY)
            xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"WM_PARENTNOTIFY event %u unsupported",LOWORD(wp));
        args[3]=window_token((HWND)lp);
        break;
    case WM_PALETTECHANGED:
        args[2] = window_token((HWND)wp);
        break;
    case WM_SETCURSOR:
    case WM_MOUSEACTIVATE: /* wParam is a window; lParam packs scalar hit-test/message words. */
    case WM_CONTEXTMENU:   /* DefWindowProc's answer to a right-button release: wParam is the window, lParam the packed
                            * screen point (or -1). The game binds the right button to AltFire (launch 20261101-150848). */
    case WM_APPCOMMAND:    /* Media/volume keys during interactive play: wParam is the window, lParam packs the scalar
                            * command, device and key-state words; DefWindowProc gets the host window back. */
        args[2] = window_token((HWND)wp);
        break;
    case WM_TIMER:
        if (lp)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_TIMER callback procedure requires marshalling");
        break;
    case WM_SETTINGCHANGE:
        /* Broadcast to every top-level window when the desktop's owner changes a system setting (the background mode
         * keeps the desktop in use). wParam is a scalar; lParam NULL or a read-only section/policy name, copied below
         * the callback scratch like WM_DEVICECHANGE data; DefWindowProc gets the host string back (forward_message). */
        if (lp)
        {
            int wide_text = xm_win_IsWindowUnicode(h);
            size_t chars = wide_text ? wcsnlen((const wchar_t *)lp, 512) : strnlen((const char *)lp, 512);
            uint32_t size = (uint32_t)((chars + 1) * (wide_text ? 2 : 1)), data;
            if (chars == 512)
                xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_SETTINGCHANGE string longer than 511 characters");
            data = (scratch - ((size + 15u) & ~15u)) & ~15u;
            gui_transition_memory(&nested, data, size, 1);
            memcpy(G2H(data), (const void *)lp, size);
            nested.r[ESP] = data;
            args[3] = data;
            { static unsigned logged; if (logged++ < 8) xrt_log("WM_SETTINGCHANGE wParam %llx lParam string (%u bytes)", (unsigned long long)wp, size); }
        }
        break;
    case WM_NOTIFY:
    case WM_DRAWITEM:
    case WM_MEASUREITEM:
    case WM_COMPAREITEM:
    case WM_DELETEITEM:
    case WM_GETTEXT:
        xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "dialog callback pointer message 0x%x requires marshalling", msg);
    default:
        /* Exact measured registered notification; preserve error while resolving its session identity. */
        if (msg >= 0xc000u && msg <= 0xffffu && wp <= 0xffffffffu && !lp) {
            WCHAR name[40];
            DWORD lookup_error = GetLastError();
            int length = xm_win_GetClipboardFormatNameW(msg, name, 40);
            int taskbar_created = !wp && length == 20 && xm_win_lstrcmpW(name, L"TaskbarButtonCreated") == 0;
            /* dinput8 posts its registered device notification with a scalar wParam. */
            int dinput_notify = length == 34 && xm_win_lstrcmpW(name, L"DIRECTINPUT_NOTIFICATION_MSGSTRING") == 0;
            SetLastError(lookup_error);
            if (taskbar_created || dinput_notify) break;
            /* Any other registered message with both arguments zero carries no pointer or handle: the desktop's shell
             * broadcasts them while the owner works (0xc250 "ShellFileOpened" when a file was opened, launch
             * 20261101-123706). It crosses as is; the guest's procedure decides (normally DefWindowProc). */
            if (!wp) {
                static unsigned logged;
                if (logged++ < 16) xrt_log("registered message %x \"%ls\" (zero arguments) delivered", msg, length > 0 ? name : L"?");
                break;
            }
        }
        /* Only measured scalar messages may cross unmodified. */
        if (!((msg <= WM_ENABLE && msg != WM_GETTEXT) || msg == WM_PAINT || msg == WM_ERASEBKGND ||
              msg == WM_SHOWWINDOW || msg == WM_NCPAINT || msg == WM_NCACTIVATE || msg == WM_DESTROY ||
              /* The window's close button: WinDrv's viewport passes WM_CLOSE (no arguments) on to the game's main
               * dialog window (runs 20261101-210939/-211024). */
              (msg == WM_CLOSE && !wp && !lp) || (msg == WM_SETREDRAW && !lp) ||
              msg == WM_NCDESTROY || msg == WM_CANCELMODE || msg == WM_GETDLGCODE || msg == WM_GETFONT ||
              msg == WM_CHANGEUISTATE || msg == WM_UPDATEUISTATE || msg == WM_QUERYUISTATE ||
              msg == WM_QUERYNEWPALETTE || msg == WM_PALETTECHANGED || msg == WM_DWMNCRENDERINGCHANGED ||
              msg == WM_ACTIVATEAPP || msg == WM_IME_SETCONTEXT || msg == WM_IME_NOTIFY || msg==WM_GETTEXTLENGTH ||
              /* Main-loop input/notifications: wParam/lParam are packed scalars. */
              (msg >= WM_KEYFIRST && msg <= WM_KEYLAST) || (msg >= WM_MOUSEFIRST && msg <= WM_MOUSELAST) ||
              (msg >= WM_NCMOUSEMOVE && msg <= WM_NCXBUTTONDBLCLK) || msg == WM_NCHITTEST ||
              msg == WM_MOUSEHOVER || msg == WM_MOUSELEAVE || msg == WM_NCMOUSEHOVER || msg == WM_NCMOUSELEAVE ||
              msg == WM_SYSCOMMAND || msg == WM_ENTERSIZEMOVE || msg == WM_EXITSIZEMOVE || msg == WM_CHILDACTIVATE ||
              msg == WM_DISPLAYCHANGE ||
              /* Desktop broadcasts while the owner works (background mode); scalar or zero arguments only. */
              msg == WM_SYSCOLORCHANGE || msg == WM_FONTCHANGE || msg == WM_TIMECHANGE || msg == WM_THEMECHANGED ||
              msg == WM_DWMCOMPOSITIONCHANGED || msg == WM_DWMCOLORIZATIONCOLORCHANGED ||
              (msg == WM_POWERBROADCAST && !lp)))
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "dialog callback message 0x%x unsupported (wp=%llx lp=%llx)",
                      msg, (unsigned long long)wp, (unsigned long long)lp);
    }
    xrt_event("gui_callback", "\"message\": %u, \"proc\": %u", msg, proc);
    frame.previous=callback_frame; frame.window=h; frame.message=msg;
    frame.host_wp=wp; frame.host_lp=lp; frame.guest_wp=args[2];frame.guest_lp=args[3];
    frame.create_words=(msg==WM_CREATE || msg==WM_NCCREATE)?create_words:NULL;
    callback_frame=&frame;
    result = (INT_PTR)(int32_t)xrt_call_guest(&nested, proc, 4, args, 1);
    callback_frame=frame.previous;
    if (msg == WM_GETOBJECT) {
        /* No guest accessibility object/cookie marshaller has been measured.
         * Return the actual guest result; do not replace dispatch with FALSE. */
        if (result)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, explicit_proc ?
                      "WM_GETOBJECT: nonzero registered WNDPROC result requires measured accessibility marshalling" :
                      "WM_GETOBJECT: nonzero guest dialog result requires measured accessibility marshalling");
        xrt_event("gui_get_object_callback_return",
                  "\"hwnd\":%u,\"proc\":%u,\"wparam\":%u,\"object_id\":%u,\"result\":%d,\"last_error\":%u",
                  args[0],proc,args[2],args[3],(int)result,xrt_get_last_error(&nested));
    }
    if(frame.create_words && memcmp(create_words,G2H(scratch),48))
        xrt_fatal(&nested,XRT_EXIT_UNSUPPORTED,"CREATESTRUCT field mutation requires marshalling");
    if (msg == WM_WINDOWPOSCHANGING || msg == WM_WINDOWPOSCHANGED)
        unpack_windowpos((WINDOWPOS *)lp, scratch);
    if(msg==WM_STYLECHANGING || msg==WM_STYLECHANGED)gui_style_sync(&nested,msg,scratch,lp);
    if (msg == WM_GETMINMAXINFO)
    {
        memcpy((void *)lp, G2H(scratch), 40);
        dev_max_track((MINMAXINFO *)lp);
    }
    if (msg == WM_SIZING || msg == WM_MOVING)
        memcpy((void *)lp, G2H(scratch), 16);
    if (msg == WM_NCCALCSIZE)
    {
        if (wp)
        {
            NCCALCSIZE_PARAMS *n = (NCCALCSIZE_PARAMS *)lp;
            memcpy(n->rgrc, G2H(scratch), 48);
            unpack_windowpos(n->lppos, scratch + 52);
        }
        else
            memcpy((void *)lp, G2H(scratch), 16);
    }
    if (msg == WM_GETFONT && result)
    {
        HFONT font = (HFONT)xrt_handle_get((uint32_t)result, XH_FONT);
        if (!font)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_GETFONT returned unknown guest font");
        result = (INT_PTR)font;
    }
    if(msg==WM_GETICON) {
        uint32_t token=(uint32_t)result;
        result=(INT_PTR)guest_icon(&nested,token);
        xrt_event("gui_get_icon_callback_return","\"hwnd\":%u,\"selector\":%u,\"dpi\":%u,\"icon\":%u,\"last_error\":%u",
            args[0],args[2],args[3],token,xrt_get_last_error(&nested));
    }
    if(msg==0xae)
        xrt_event("gui_ae_callback_return","\"hwnd\":%u,\"wparam\":%u,\"lparam\":%u,\"result\":%d,\"last_error\":%u",args[0],args[2],args[3],(int)result,xrt_get_last_error(&nested));
    if (msg == WM_ERASEBKGND || msg == WM_CTLCOLORSTATIC || msg == WM_CTLCOLORDLG || msg == WM_CTLCOLOREDIT ||
        msg == WM_CTLCOLORBTN)
    {
        free(xrt_handle_get(args[2], XH_DC));
        xrt_handle_free(args[2]);
        if (result && msg != WM_ERASEBKGND)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "dialog callback brush result requires handle translation");
    }
    SetLastError(xrt_get_last_error(&nested));
    { INT_PTR xm_ret=(result);xm_scope(callback_cpu,XM_END,XM_CALLBACK,"USER32.invoke_gui_proc",(uint64_t)xm_ret);return xm_ret;}
}
static INT_PTR CALLBACK dialog_bridge(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    return invoke_gui_proc(h, msg, wp, lp, 0);
}
/* Developer background mode (create_dialog): the dialog manager's default focus assignment after a nonzero
 * WM_INITDIALOG activates even a hidden dialog (measured: experiments/xrt/tests/bg_input "dialog"). It gets FALSE;
 * the control it would have focused becomes the guest's virtual focus (hle_GetFocus). Other messages unchanged. */
static INT_PTR CALLBACK dev_background_dialog_bridge(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    INT_PTR result = invoke_gui_proc(h, msg, wp, lp, 0);
    if (msg == WM_INITDIALOG && result)
    {
        dev_background_focus = GetNextDlgTabItem(h, NULL, FALSE);
        if (!dev_background_focus) dev_background_focus = h;
        xrt_log("DEV background: WM_INITDIALOG default focus %p kept virtual", dev_background_focus);
        return FALSE;
    }
    return result;
}
static HMODULE resource_module(CPU *c, uint32_t module)
{
    int i;
    for (i = 0; i < xrt_module_count(); i++)
    {
        XrtModule *m = xrt_module_get(i);
        if (m->base == module)
        {
            WCHAR path[1024];
            HMODULE host;
            if (!xm_win_MultiByteToWideChar(CP_ACP, 0, m->path, -1, path, 1024))
            {
                xrt_set_last_error(c, GetLastError());
                return NULL;
            }
            host = xm_win_LoadLibraryExW(path, NULL, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE);
            if (!host)
                xrt_set_last_error(c, GetLastError());
            return host;
        }
    }
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "dialog resource module %08x unknown", module);
}
static void create_dialog(CPU *c, int wide)
{
    HMODULE resources;
    HWND h, parent = window_host(ARG(2));
    uint32_t result = 0;
    CPU *previous = callback_cpu;
    uint32_t oldproc = creating_proc;
    if (ARG(2) && !parent)
    {
        xrt_set_last_error(c, ERROR_INVALID_WINDOW_HANDLE);
        RET_STD(5, 0);
        return;
    }
    begin(c);
    resources = resource_module(c, ARG(0));
    if (!resources)
    {
        RET_STD(5, 0);
        return;
    }
    callback_cpu = c;
    creating_proc = ARG(3);
    if (xrt_dev_background() && !parent)
    {
        /* Developer background mode: a top-level dialog (the startup splash) activates itself while it is created,
         * visible or not: the dialog manager's default focus after WM_INITDIALOG (WM_ACTIVATEAPP before the first
         * CreateWindowEx, runs 20261101-121336 and -132447 with an idle owner). Every top-level dialog is created from a
         * private copy of its template through dev_background_dialog_bridge; a WS_VISIBLE one is shown afterwards
         * without activation at the bottom. */
        HRSRC found = wide ? FindResourceW(resources, ARG(1) < 0x10000u ? MAKEINTRESOURCEW(ARG(1)) : (LPCWSTR)G2H(ARG(1)), (LPCWSTR)RT_DIALOG)
                           : FindResourceA(resources, ARG(1) < 0x10000u ? MAKEINTRESOURCEA(ARG(1)) : (LPCSTR)G2H(ARG(1)), (LPCSTR)RT_DIALOG);
        DWORD size = found ? SizeofResource(resources, found) : 0;
        const BYTE *bytes = found ? (const BYTE *)LockResource(LoadResource(resources, found)) : NULL;
        BYTE *copy = bytes && size >= 18 ? (BYTE *)HeapAlloc(GetProcessHeap(), 0, size) : NULL;
        if (copy)
        {
            DWORD *style;
            memcpy(copy, bytes, size);
            style = (DWORD *)(copy + (((WORD *)copy)[1] == 0xffffu ? 12 : 0)); /* DLGTEMPLATEEX: signature 0xffff, style at 12 */
            {
                int visible = (*style & WS_VISIBLE) != 0;
                *style &= ~WS_VISIBLE;
                xrt_log("DEV background: top-level dialog (template style %08lx) created without activation", (unsigned long)(*style | (visible ? WS_VISIBLE : 0)));
                h = wide ? CreateDialogIndirectParamW(resources, (LPCDLGTEMPLATEW)copy, parent, dev_background_dialog_bridge, (LPARAM)(int32_t)ARG(4))
                         : CreateDialogIndirectParamA(resources, (LPCDLGTEMPLATEA)copy, parent, dev_background_dialog_bridge, (LPARAM)(int32_t)ARG(4));
                HeapFree(GetProcessHeap(), 0, copy);
                if (h && visible && IsWindow(h))
                {
                    ShowWindow(h, SW_SHOWNOACTIVATE);
                    dev_background_bottom(h);
                }
                goto created;
            }
        }
    }
    if (wide)
        h = xm_win_CreateDialogParamW(resources, ARG(1) < 0x10000u ? MAKEINTRESOURCEW(ARG(1)) : (LPCWSTR)G2H(ARG(1)),
                               parent, dialog_bridge, (LPARAM)(int32_t)ARG(4));
    else
        h = xm_win_CreateDialogParamA(resources, ARG(1) < 0x10000u ? MAKEINTRESOURCEA(ARG(1)) : (LPCSTR)G2H(ARG(1)),
                               parent, dialog_bridge, (LPARAM)(int32_t)ARG(4));
created:
    end(c);
    if (h)
        result = window_token(h);
    callback_cpu = previous;
    creating_proc = oldproc;
    xm_win_FreeLibrary(resources);
    forget_dead_windows();
    xrt_event("gui_create_dialog", "\"handle\": %u", result);
    RET_STD(5, result);
}
static void hle_CreateDialogParamW(CPU *c)
{
    create_dialog(c, 1);
}
static void hle_CreateDialogParamA(CPU *c)
{
    create_dialog(c, 0);
}
static void hle_GetDlgItem(CPU *c)
{
    HWND h;
    uint32_t result;
    begin(c);
    h = xm_win_GetDlgItem(window_host(ARG(0)), (int)ARG(1));
    end(c);
    result = window_token(h);
    RET_STD(2, result);
}
static void hle_GetSystemMetrics(CPU *c)
{
    int result;
    begin(c);
    result = xm_win_GetSystemMetrics((int)ARG(0));
    end(c);
    RET_STD(1, result);
}
static void hle_GetWindowRect(CPU *c)
{
    RECT rect;
    BOOL ok;
    begin(c);
    ok = xm_win_GetWindowRect(window_host(ARG(0)), ARG(1) ? &rect : NULL);
    end(c);
    if (ok)
        memcpy(G2H(ARG(1)), &rect, 16);
    RET_STD(2, ok);
}
static void hle_GetDesktopWindow(CPU* c)
{
    HWND h; begin(c); h=xm_win_GetDesktopWindow(); end(c);
    RET_STD(0,window_token(h));
}
static void hle_GetClientRect(CPU* c)
{
    RECT rect; BOOL ok;
    begin(c); ok=xm_win_GetClientRect(window_host(ARG(0)),ARG(1)?&rect:NULL); end(c);
    if(ok) memcpy(G2H(ARG(1)),&rect,16);
    RET_STD(2,ok);
}
static void hle_IsWindow(CPU* c)
{
    BOOL ok;begin(c);ok=xm_win_IsWindow(window_host(ARG(0)));end(c);RET_STD(1,ok);
}
/* WWindow::OnDestroy saves the window placement (IsZoomed) at shutdown (run 20261101-205936, fatal 75 after Quit).
 * Scalar state queries of a registered window. */
static void hle_IsZoomed(CPU* c)
{
    BOOL ok;HWND h=xrt_gui_device_window(c,ARG(0));begin(c);ok=IsZoomed(h);end(c);RET_STD(1,ok);
}
/* Entering fullscreen, WinDrv registers Alt+Esc, Alt+Tab, Ctrl+Esc and Ctrl+Tab as hot keys of its window (so they do
 * not leave exclusive fullscreen), and unregisters them on leaving. Fullscreen here is borderless and must keep
 * Alt+Tab working: the registration is declined (FALSE, ERROR_NOT_SUPPORTED); nothing was registered to unregister. */
static void hle_RegisterHotKey(CPU* c)
{
    static unsigned logged;
    xrt_gui_device_window(c,ARG(0));
    if(logged++<4)xrt_log("RegisterHotKey(id %u, modifiers %x, key %x) declined: borderless fullscreen keeps system shortcuts",ARG(1),ARG(2),ARG(3));
    xrt_set_last_error(c,ERROR_NOT_SUPPORTED);RET_STD(4,FALSE);
}
static void hle_UnregisterHotKey(CPU* c)
{
    xrt_gui_device_window(c,ARG(0));
    xrt_set_last_error(c,ERROR_HOTKEY_NOT_REGISTERED);RET_STD(2,FALSE);
}
static void hle_IsIconic(CPU* c)
{
    BOOL ok;HWND h=xrt_gui_device_window(c,ARG(0));begin(c);ok=IsIconic(h);end(c);RET_STD(1,ok);
}
static void hle_ShowWindow(CPU* c)
{
    BOOL previous_visible;CPU* previous=callback_cpu;int cmd=(int)ARG(1);
    if(xrt_dev_background()&&dev_background_show(cmd)!=cmd){xrt_log("DEV background: ShowWindow %d -> %d",cmd,dev_background_show(cmd));cmd=dev_background_show(cmd);}
    callback_cpu=c;begin(c);previous_visible=xm_win_ShowWindow(window_host(ARG(0)),cmd);
    if(xrt_dev_background())dev_background_bottom(window_host(ARG(0)));
    end(c);callback_cpu=previous;
    RET_STD(2,previous_visible);
}
/* MoveWindow accepts signed geometry and BOOL repaint. Ownership/thread
 * checks and typed callback marshalling remain in xrt_gui_device_window. */
static void hle_MoveWindow(CPU*c) {
    HWND h;BOOL ok;CPU*previous;DWORD error;
    { DWORD saved_error=GetLastError(),saved_mxcsr=_mm_getcsr();
      __declspec(align(16)) CONTEXT context;LONG id=InterlockedIncrement(&gui_diagnostic_serial);
      RtlCaptureContext(&context);gui_diagnostic_bytes(id,"move_host_context",&context,sizeof context);
      gui_diagnostic_bytes(id,"move_guest_cpu",c,sizeof *c);_mm_setcsr(saved_mxcsr);SetLastError(saved_error); }
    if((uint64_t)c->r[ESP]+28>0x100000000ull || !xrt_is_committed(c->r[ESP],28) ||
       !gui_diagnostic_readable(G2H(c->r[ESP]),28))
        xrt_fatal(c,76,"SAFETY: MoveWindow unreadable argument frame");
    xrt_event("gui_move_window_call","\"hwnd\":%u,\"x\":%u,\"y\":%u,\"width\":%u,\"height\":%u,\"repaint\":%u,\"site\":%u",
        ARG(0),ARG(1),ARG(2),ARG(3),ARG(4),ARG(5),c->pc);
    h=xrt_gui_device_window(c,ARG(0));previous=xrt_gui_callback_enter(c);begin(c);
    ok=xm_win_MoveWindow(h,(int)ARG(1),(int)ARG(2),(int)ARG(3),(int)ARG(4),(BOOL)ARG(5));
    error=GetLastError();xrt_gui_callback_leave(previous);xrt_set_last_error(c,error);RET_STD(6,ok);
    xrt_event("gui_move_window_return","\"result\":%u,\"last_error\":%lu,\"esp\":%u,\"return\":%u",(unsigned)ok,error,c->r[ESP],c->rv);
}
static void hle_SetWindowPos(CPU *c)
{
    BOOL ok;
    CPU *prev = callback_cpu;
    UINT flags = ARG(6);
    if (xrt_dev_background() && insert_host(ARG(1)) != HWND_BOTTOM) {
        /* developer background mode: no activation, no raise (HWND_TOP/TOPMOST included) */
        xrt_log("DEV background: SetWindowPos insert %08x flags %x -> %x", ARG(1), flags, flags | SWP_NOACTIVATE | SWP_NOZORDER);
        flags |= SWP_NOACTIVATE | SWP_NOZORDER;
    }
    callback_cpu = c;
    begin(c);
    ok = xm_win_SetWindowPos(window_host(ARG(0)), insert_host(ARG(1)), (int)ARG(2), (int)ARG(3), (int)ARG(4), (int)ARG(5),
                      flags);
    end(c);
    callback_cpu = prev;
    RET_STD(7, ok);
}
static void send_message(CPU *c, int wide)
{
    LRESULT result;
    UINT msg = ARG(1);
    LPARAM lp;
    WPARAM wp = ARG(2);
    CPU *prev = callback_cpu;
    if(msg==WM_GETICON) {
        uint32_t token;
        if(wp>ICON_SMALL2)
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"WM_GETICON: invalid selector or unrepresentable DPI %u/%u",(unsigned)wp,ARG(3));
        callback_cpu=c;begin(c);
        result=wide?xm_win_SendMessageW(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3)):xm_win_SendMessageA(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3));
        end(c);callback_cpu=prev;token=borrowed_icon_token(c,(HICON)result);
        RET_STD(4,token);return;
    }
    if(msg==WM_NCACTIVATE) {
        /* WWindow::WndProc forwards activation to its owner: wParam BOOL, lParam 0, -1 or an update
         * region whose 32-bit value is the full GDI handle (sign-extended, as for WM_NCPAINT). */
        static unsigned logged;
        if(logged++<8)xrt_log("SendMessage WM_NCACTIVATE wParam %u lParam %08x",(unsigned)wp,ARG(3));
        callback_cpu=c;begin(c);
        result=wide?xm_win_SendMessageW(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3)):xm_win_SendMessageA(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3));
        end(c);callback_cpu=prev;RET_STD(4,(uint32_t)result);return;
    }
    if(msg==WM_SETREDRAW && !ARG(3)) {
        /* UWindowsViewport::ResizeViewport brackets its fullscreen style change with WM_SETREDRAW 0/1 (owner's runs
         * 20261101-214637/-214728): wParam BOOL, lParam 0. */
        callback_cpu=c;begin(c);
        result=wide?xm_win_SendMessageW(window_host(ARG(0)),msg,wp,0):xm_win_SendMessageA(window_host(ARG(0)),msg,wp,0);
        end(c);callback_cpu=prev;RET_STD(4,(uint32_t)result);return;
    }
    if(msg==WM_SETTEXT || msg==WM_GETTEXTLENGTH) {
        if(msg==WM_SETTEXT && ARG(3) && ARG(3)<0x10000)
            xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"WM_SETTEXT invalid guest string");
        lp=msg==WM_SETTEXT && ARG(3) ? (LPARAM)G2H(ARG(3)) : (LPARAM)(int32_t)ARG(3);
        callback_cpu=c;begin(c);
        result=wide?xm_win_SendMessageW(window_host(ARG(0)),msg,wp,lp):xm_win_SendMessageA(window_host(ARG(0)),msg,wp,lp);
        end(c);callback_cpu=prev;RET_STD(4,(uint32_t)result);return;
    }
    if(msg==WM_SETFONT || msg==WM_GETFONT) {
        if(msg==WM_SETFONT) {
            wp=(WPARAM)xrt_handle_get(ARG(2),XH_FONT);
            if(ARG(2) && !wp) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"WM_SETFONT unknown guest font");
        }
        callback_cpu=c;begin(c);
        result=wide?xm_win_SendMessageW(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3)):xm_win_SendMessageA(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3));
        end(c);callback_cpu=prev;
        if(msg==WM_GETFONT && result) {
            uint32_t font=known_font_token((HFONT)result);
            if(!font) xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"WM_GETFONT returned a font without guest ownership");
            RET_STD(4,font);return;
        }
        RET_STD(4,(uint32_t)result);return;
    }
    if (msg != STM_SETIMAGE)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "SendMessage 0x%x requires message marshalling", msg);
    if (wp != IMAGE_BITMAP)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "STM_SETIMAGE type %u unsupported", (unsigned)wp);
    lp = (LPARAM)xrt_handle_get(ARG(3), XH_BITMAP);
    if (ARG(3) && !lp)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "STM_SETIMAGE bitmap handle %08x unknown", ARG(3));
    callback_cpu = c;
    begin(c);
    result =
        wide ? xm_win_SendMessageW(window_host(ARG(0)), msg, wp, lp) : xm_win_SendMessageA(window_host(ARG(0)), msg, wp, lp);
    end(c);
    callback_cpu = prev;
    if (result)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "STM_SETIMAGE previous bitmap requires ownership tracking");
    RET_STD(4, 0);
}
static void hle_SendMessageW(CPU *c)
{
    send_message(c, 1);
}
static void hle_SendMessageA(CPU *c)
{
    send_message(c, 0);
}
static void hle_UpdateWindow(CPU *c)
{
    BOOL ok;
    CPU *prev = callback_cpu;
    callback_cpu = c;
    begin(c);
    ok = xm_win_UpdateWindow(window_host(ARG(0)));
    end(c);
    callback_cpu = prev;
    RET_STD(1, ok);
}
static void hle_DestroyWindow(CPU *c)
{
    BOOL ok;
    unsigned i;
    CPU *prev = callback_cpu;
    /* At shutdown the game destroys its viewport window (UObject::StaticExit -> UViewport::Destroy -> CloseWindow)
     * before its render device releases the D3D8 device (owner's run 20261101-221402) - legal in Windows. The device's
     * pins on the window are dropped here and its later release finds them gone (xrt_gui_window_unpin); presenting to
     * the destroyed window would still stop as a stale HWND token. */
    for(i=0;i<1024;i++)if(windows[i].token==ARG(0) && device_window_pins[i]) {
        unsigned k;
        xrt_log("DestroyWindow %08x while a D3D8 device still holds it (%u pins): allowed, as on Windows",ARG(0),device_window_pins[i]);
        for(k=0;k<16;k++)if(!destroyed_pins[k].token){destroyed_pins[k].token=ARG(0);destroyed_pins[k].count=device_window_pins[i];break;}
        if(k==16)xrt_fatal(c,77,"DestroyWindow: pinned-window record full");
        device_window_pins[i]=0;
    }
    callback_cpu = c;
    begin(c);
    ok = xm_win_DestroyWindow(window_host(ARG(0)));
    end(c);
    callback_cpu = prev;
    forget_dead_windows();
    RET_STD(1, ok);
}
/* Ordinal identity verified against the host export as well as the documented name. */
static void hle_InitCommonControls(CPU *c)
{
    static HMODULE module;
    FARPROC ordinal, named;
    typedef void(WINAPI * Init)(void);
    begin(c);
    if (!module)
        module = xm_win_LoadLibraryExW(L"comctl32.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    ordinal = module ? xm_win_GetProcAddress(module, MAKEINTRESOURCEA(17)) : NULL;
    named = module ? xm_win_GetProcAddress(module, "InitCommonControls") : NULL;
    if (!ordinal || ordinal != named)
        xrt_fatal(c, XRT_EXIT_SETUP, "COMCTL32 ordinal 17 differs from InitCommonControls");
    ((Init)ordinal)();
    end(c);
    /* Keep the host module loaded: it owns the registered common control classes. */
    xrt_event("gui_init_common_controls", NULL);
    c->rv = pop32(c); /* void function: preserve guest EAX */
}
#include "hle_gui_classes.inc"
const XrtHle xrt_hle_gui[] = {{"comctl32.dll", "#17", hle_InitCommonControls},
                              {"imm32.dll", "ImmAssociateContext", hle_ImmAssociateContext},
                              {"user32.dll", "AdjustWindowRect", hle_AdjustWindowRect},
                              {"user32.dll", "GetKeyState", hle_GetKeyState},
                              {"user32.dll", "SetKeyboardState", hle_SetKeyboardState},
                              {"user32.dll", "AttachThreadInput", hle_AttachThreadInput},
                              {"user32.dll", "GetFocus", hle_GetFocus},
                              {"user32.dll", "SetFocus", hle_SetFocus},
                              {"user32.dll", "SetCapture", hle_SetCapture},
                              {"user32.dll", "ClipCursor", hle_ClipCursor},
                              {"user32.dll", "GetForegroundWindow", hle_GetForegroundWindow},
                              {"user32.dll", "SetForegroundWindow", hle_SetForegroundWindow},
                              {"user32.dll", "SetActiveWindow", hle_SetActiveWindow},
                              {"user32.dll", "GetWindowThreadProcessId", hle_GetWindowThreadProcessId},
                              {"user32.dll", "MapWindowPoints", hle_MapWindowPoints},
                              {"user32.dll", "GetClassInfoExW", hle_GetClassInfoExW},
                              {"user32.dll", "GetClassInfoExA", hle_GetClassInfoExA},
                              {"user32.dll", "RegisterClassExW", hle_RegisterClassExW},
                              {"user32.dll", "RegisterClassExA", hle_RegisterClassExA},
                              {"user32.dll", "UnregisterClassW", hle_UnregisterClassW},
                              {"user32.dll", "UnregisterClassA", hle_UnregisterClassA},
                              {"user32.dll", "CallWindowProcW", hle_CallWindowProcW},
                              {"user32.dll", "CallWindowProcA", hle_CallWindowProcA},
                              {"user32.dll", "LoadIconW", hle_LoadIconW},
                              {"user32.dll", "LoadIconA", hle_LoadIconA},
                              {"user32.dll", "LoadCursorW", hle_LoadCursorW},
                              {"user32.dll", "LoadCursorA", hle_LoadCursorA},
                              {"user32.dll", "SetCursor", hle_SetCursor},
                              {"gdi32.dll", "CreateSolidBrush", hle_CreateSolidBrush},
                              {"gdi32.dll", "CreateBitmap", hle_CreateBitmap},
                              {"gdi32.dll", "CreatePatternBrush", hle_CreatePatternBrush},
                              {"gdi32.dll", "GetStockObject", hle_GetStockObject},
                              {"user32.dll", "GetDesktopWindow", hle_GetDesktopWindow},
                              {"user32.dll", "GetClientRect", hle_GetClientRect},
                              {"user32.dll", "CreateWindowExW", hle_CreateWindowExW},
                              {"user32.dll", "CreateWindowExA", hle_CreateWindowExA},
                              {"user32.dll", "DefWindowProcW", hle_DefWindowProcW},
                              {"user32.dll", "DefWindowProcA", hle_DefWindowProcA},
                              {"user32.dll", "GetWindowLongW", hle_GetWindowLongW},
                              {"user32.dll", "SetWindowLongA", hle_SetWindowLongA},
                              {"user32.dll", "SetWindowLongW", hle_SetWindowLongW},
                              {"user32.dll", "SetMenu", hle_SetMenu},
                              {"user32.dll", "GetMenu", hle_GetMenu},
                              {"user32.dll", "PostMessageA", hle_PostMessageA},
                              {"user32.dll", "PostMessageW", hle_PostMessageW},
                              {"user32.dll", "PostQuitMessage", hle_PostQuitMessage},
                              {"user32.dll", "PeekMessageW", hle_PeekMessageW},
                              {"user32.dll", "PeekMessageA", hle_PeekMessageA},
                              {"user32.dll", "TranslateMessage", hle_TranslateMessage},
                              {"user32.dll", "DispatchMessageW", hle_DispatchMessageW},
                              {"user32.dll", "DispatchMessageA", hle_DispatchMessageA},
                              {"user32.dll", "GetCursorPos", hle_GetCursorPos},
                              {"user32.dll", "ClientToScreen", hle_ClientToScreen},
                              {"user32.dll", "ScreenToClient", hle_ScreenToClient},
                              {"user32.dll", "SetCursorPos", hle_SetCursorPos},
                              {"user32.dll", "ShowCursor", hle_ShowCursor},
                              {"user32.dll", "ValidateRect", hle_ValidateRect},
                              {"user32.dll", "GetMessageTime", hle_GetMessageTime},
                              {"user32.dll", "GetParent", hle_GetParent},

                              {"user32.dll", "GetWindowLongA", hle_GetWindowLongA},
                              {"user32.dll", "IsWindow", hle_IsWindow},
                              {"user32.dll", "IsZoomed", hle_IsZoomed},
                              {"user32.dll", "IsIconic", hle_IsIconic},
                              {"user32.dll", "RegisterHotKey", hle_RegisterHotKey},
                              {"user32.dll", "UnregisterHotKey", hle_UnregisterHotKey},
                              {"user32.dll", "ShowWindow", hle_ShowWindow},
                              {"user32.dll", "SetPropW", hle_SetPropW},
                              {"user32.dll", "SetPropA", hle_SetPropA},
                              {"user32.dll", "GetPropW", hle_GetPropW},
                              {"user32.dll", "GetPropA", hle_GetPropA},
                              {"user32.dll", "RemovePropW", hle_RemovePropW},
                              {"user32.dll", "RemovePropA", hle_RemovePropA},
                              {"comctl32.dll", "InitCommonControls", hle_InitCommonControls},
                              {"user32.dll", "GetDC", hle_GetDC},
                              {"user32.dll", "ReleaseDC", hle_ReleaseDC},
                              {"user32.dll", "CreateDialogParamW", hle_CreateDialogParamW},
                              {"user32.dll", "CreateDialogParamA", hle_CreateDialogParamA},
                              {"user32.dll", "GetDlgItem", hle_GetDlgItem},
                              {"user32.dll", "GetSystemMetrics", hle_GetSystemMetrics},
                              {"user32.dll", "GetWindowRect", hle_GetWindowRect},
                              {"gdi32.dll", "GetDIBits", hle_GetDIBits},
                              {"gdi32.dll", "GetDeviceCaps", hle_GetDeviceCaps},
                              {"user32.dll", "SetWindowPos", hle_SetWindowPos},
                              {"user32.dll", "MoveWindow", hle_MoveWindow},
                              {"user32.dll", "SendMessageW", hle_SendMessageW},
                              {"user32.dll", "SendMessageA", hle_SendMessageA},
                              {"user32.dll", "UpdateWindow", hle_UpdateWindow},
                              {"user32.dll", "DestroyWindow", hle_DestroyWindow},
                              {"gdi32.dll", "CreateDIBitmap", hle_CreateDIBitmap},
                              {"gdi32.dll", "DeleteObject", hle_DeleteObject},
                              {0}};

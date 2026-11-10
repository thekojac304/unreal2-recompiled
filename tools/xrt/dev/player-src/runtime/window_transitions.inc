/* Conditional WinDrv transitions. Pointer-valued window fields and menu
 * ownership remain separate domains, never truncated into scalar values. */
static void gui_transition_memory(CPU*c,uint32_t p,unsigned bytes,int write) {
 uint64_t at=p,limit=(uint64_t)p+bytes;
 if(!p||limit>0x100000000ull)xrt_fatal(c,76,"window transition: invalid guest range");
 while(at<limit){MEMORY_BASIC_INFORMATION m;DWORD a;uint64_t next;
  if(!VirtualQuery(xrt_g+at,&m,sizeof m)||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))xrt_fatal(c,76,"window transition: inaccessible guest page");
  a=m.Protect&255;
  if(write?(a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY):(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY))xrt_fatal(c,76,"window transition: guest protection");
  next=(uint64_t)((BYTE*)m.BaseAddress-xrt_g)+m.RegionSize;if(next<=at)xrt_fatal(c,76,"window transition: invalid page extent");at=next;
 }
}
static void gui_style_sync(CPU*c,UINT msg,uint32_t guest,LPARAM host) {
 gui_transition_memory(c,guest,8,0);
 if(msg==WM_STYLECHANGING)memcpy((void*)host,G2H(guest),8);
 else if(memcmp((void*)host,G2H(guest),8))xrt_fatal(c,76,"WM_STYLECHANGED: read-only structure changed");
}
static void gui_set_window_long(CPU*c,int wide) {
 HWND h;LONG value;int index;CPU*prev;
 gui_transition_memory(c,c->r[ESP],16,0);index=(int)ARG(1);
 if(index!=GWL_STYLE&&index!=GWL_EXSTYLE)xrt_fatal(c,76,"SetWindowLong: pointer/extra storage field unsupported");
 h=xrt_gui_device_window(c,ARG(0));prev=xrt_gui_callback_enter(c);begin(c);
 value=wide?xm_win_SetWindowLongW(h,index,(LONG)ARG(2)):xm_win_SetWindowLongA(h,index,(LONG)ARG(2));end(c);xrt_gui_callback_leave(prev);RET_STD(3,(uint32_t)value);
}
static void hle_SetWindowLongW(CPU*c){gui_set_window_long(c,1);}
static void hle_SetWindowLongA(CPU*c){gui_set_window_long(c,0);}
static void hle_SetMenu(CPU*c) {
 HWND h;BOOL ok;CPU*prev;
 gui_transition_memory(c,c->r[ESP],12,0);
 if(ARG(1))xrt_fatal(c,76,"SetMenu: non-NULL menu requires typed ownership");
 h=xrt_gui_device_window(c,ARG(0));prev=xrt_gui_callback_enter(c);begin(c);ok=xm_win_SetMenu(h,NULL);end(c);xrt_gui_callback_leave(prev);RET_STD(2,ok);
}
/* UWindowsViewport::SetTopness asks for the window's menu when it leaves fullscreen (owner's runs 20261101-220238,
 * -220317): the game window has none (the game only ever sets NULL), and NULL means "not topmost". A real menu would
 * need the typed ownership SetMenu refuses as well. */
static void hle_GetMenu(CPU*c) {
 HWND h;HMENU m;
 gui_transition_memory(c,c->r[ESP],8,0);
 h=xrt_gui_device_window(c,ARG(0));begin(c);m=GetMenu(h);end(c);
 if(m)xrt_fatal(c,76,"GetMenu: a window menu requires typed ownership");
 RET_STD(1,0);
}
static void gui_post_message(CPU*c,int wide) {
 HWND h,control=NULL;UINT msg;WPARAM wp;LPARAM lp;BOOL ok;CPU*prev;
 gui_transition_memory(c,c->r[ESP],20,0);msg=ARG(1);wp=ARG(2);lp=(LPARAM)(int32_t)ARG(3);
 if(!ARG(0))xrt_fatal(c,76,"PostMessage: thread/broadcast target unsupported");
 h=xrt_gui_device_window(c,ARG(0));
 if(msg==WM_COMMAND){if(ARG(3))control=xrt_gui_device_window(c,ARG(3));lp=(LPARAM)control;}
 else if((msg!=WM_NULL&&msg!=WM_CLOSE)||wp||lp)xrt_fatal(c,76,"PostMessage: unmodelled asynchronous payload");
 prev=xrt_gui_callback_enter(c);begin(c);ok=wide?xm_win_PostMessageW(h,msg,wp,lp):xm_win_PostMessageA(h,msg,wp,lp);end(c);xrt_gui_callback_leave(prev);RET_STD(4,ok);
}
static void hle_PostMessageW(CPU*c){gui_post_message(c,1);}
static void hle_PostMessageA(CPU*c){gui_post_message(c,0);}

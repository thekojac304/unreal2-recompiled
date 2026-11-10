/* Borderless fullscreen (port setting, owner's choice 2026-11-01). The game asks for exclusive fullscreen through
 * CreateDevice/Reset with Windowed=FALSE at the resolution chosen in its menu (UWindowsViewport::ResizeViewport has
 * already removed the caption and frame and captured the mouse). Instead of a display mode change:
 *   - the device window is placed over its whole monitor (no mode change; Alt+Tab, other monitors and a crash leave
 *     the desktop as it was) and the native device is WINDOWED with a back buffer of the window's size - the only
 *     size DXVK presents on its Vulkan path (a back buffer of another size falls back to GDI, run 20261101-211738);
 *   - the game renders into a render-target texture of the chosen resolution with its own depth surface, which
 *     GetBackBuffer, GetRenderTarget and GetDepthStencilSurface return as its back buffer and depth buffer;
 *   - at Present that texture is drawn once onto the real back buffer, scaled with linear filtering and the aspect
 *     ratio kept (black bars), with all device state saved and restored around it (state block, render target).
 * The guest's presentation parameters are restored after the native call, so the game sees what it asked for.
 * Leaving fullscreen (the game restores its frame and asks for a windowed device) releases all of it. */
typedef struct D8Borderless {
    int active;HWND window;
    LONG style;int framed;RECT rect;            /* the window before the first fullscreen fit (restored if the game does not) */
    unsigned vw,vh,format,depth,depthformat;   /* the game's requested (virtual) back buffer */
    D8Texture*tex;D8Surface*rt,*ds;
    unsigned composites;
} D8Borderless;
static D8Borderless d8_bl;
int xrt_d3d8_borderless_window(void*h){return d8_bl.active && d8_bl.window==(HWND)h;}

/* Native slots outside the typed vtable (IDirect3DDevice8 order): state blocks and the pixel shader. */
typedef HRESULT (WINAPI*D8ApplyStateBlockFn)(D8Device*,DWORD);
typedef HRESULT (WINAPI*D8DeleteStateBlockFn)(D8Device*,DWORD);
typedef HRESULT (WINAPI*D8CreateStateBlockFn)(D8Device*,DWORD,DWORD*);
typedef HRESULT (WINAPI*D8SetPixelShaderFn)(D8Device*,DWORD);
#define D8_SLOT(dev,n) (((void*const*)(dev)->vt)[n])

static void d8_bl_release(void) {
    if(d8_bl.ds){XM_Release(NULL,(D8Unknown*)d8_bl.ds);d8_bl.ds=NULL;}
    if(d8_bl.rt){XM_Release(NULL,(D8Unknown*)d8_bl.rt);d8_bl.rt=NULL;}
    if(d8_bl.tex){XM_Release(NULL,(D8Unknown*)d8_bl.tex);d8_bl.tex=NULL;}
}
/* windowed: the game asked for a windowed device again. Its ResizeViewport normally restores the caption and frame and
 * moves the window back first; if the frame is still missing, the window as it was before fullscreen comes back. */
static void d8_bl_end(const char*why,CPU*c,int windowed) {
    if(d8_bl.active){d8_bl_release();d8_bl.active=0;xrt_log("D3D8 borderless fullscreen ended (%s)",why);}
    if(!windowed || !d8_bl.framed)return;
    if(IsWindow(d8_bl.window) && (GetWindowLongW(d8_bl.window,GWL_STYLE)&WS_CAPTION)!=WS_CAPTION) {
        CPU*prev=xrt_gui_callback_enter(c);
        SetWindowLongW(d8_bl.window,GWL_STYLE,d8_bl.style);
        SetWindowPos(d8_bl.window,NULL,d8_bl.rect.left,d8_bl.rect.top,d8_bl.rect.right-d8_bl.rect.left,d8_bl.rect.bottom-d8_bl.rect.top,
                     SWP_NOZORDER|SWP_FRAMECHANGED);
        xrt_gui_callback_leave(prev);
        xrt_log("D3D8 borderless: window frame restored by the runtime");
    }
    d8_bl.framed=0;
}
/* Places the window, without caption or frame, over its monitor; returns the client size. D3DDrv creates the device
 * BEFORE UWindowsViewport::ResizeViewport removes the frame (owner's runs 20261101-214637/-214728: a 2544x1401 back
 * buffer), so the same style change (style & ~(WS_CAPTION|WS_THICKFRAME), as ResizeViewport does) is made here first. */
static void d8_bl_fit(CPU*c,HWND h,unsigned*w,unsigned*hh) {
    MONITORINFO mi;RECT r;CPU*prev;LONG style=GetWindowLongW(h,GWL_STYLE);
    mi.cbSize=sizeof mi;GetMonitorInfoW(MonitorFromWindow(h,MONITOR_DEFAULTTONEAREST),&mi);
    if((style&WS_CAPTION)==WS_CAPTION && !d8_bl.framed){d8_bl.style=style;GetWindowRect(h,&d8_bl.rect);d8_bl.framed=1;}
    prev=xrt_gui_callback_enter(c);
    if(style&(WS_CAPTION|WS_THICKFRAME))SetWindowLongW(h,GWL_STYLE,style&~(LONG)(WS_CAPTION|WS_THICKFRAME));
    SetWindowPos(h,HWND_TOP,mi.rcMonitor.left,mi.rcMonitor.top,mi.rcMonitor.right-mi.rcMonitor.left,mi.rcMonitor.bottom-mi.rcMonitor.top,
                 SWP_FRAMECHANGED|SWP_SHOWWINDOW);
    xrt_gui_callback_leave(prev);
    GetClientRect(h,&r);*w=(unsigned)r.right;*hh=(unsigned)r.bottom;
}
/* Fullscreen request in the 13-word guest presentation tuple pp: remember it, fit the window, and rewrite pp as the
 * windowed native request. Returns 1 when translated (saved[] holds the guest's words to restore afterwards). */
static int d8_bl_translate(CPU*c,uint32_t pp,uint32_t window_token,uint32_t saved[13]) {
    unsigned i,w,h;HWND win;
    if(rd32(pp+28))return 0;
    for(i=0;i<13;i++)saved[i]=rd32(pp+4*i);
    win=xrt_gui_device_window(c,window_token);
    if(!win)xrt_fatal(c,76,"D3D8 borderless fullscreen: no device window");
    d8_bl_release();
    d8_bl.active=1;d8_bl.window=win;   /* before resizing: the game's fullscreen WM_SIZE handling is held back */
    d8_bl.vw=saved[0];d8_bl.vh=saved[1];d8_bl.format=saved[2]?saved[2]:22;d8_bl.depth=saved[8];d8_bl.depthformat=saved[9];
    d8_bl_fit(c,win,&w,&h);
    wr32(pp,w);wr32(pp+4,h);wr32(pp+8,22);wr32(pp+12,1);wr32(pp+16,0);wr32(pp+20,1);
    wr32(pp+28,1);wr32(pp+32,0);wr32(pp+36,0);wr32(pp+40,saved[10]&1);wr32(pp+44,0);wr32(pp+48,0);
    xrt_log("D3D8 borderless fullscreen: game asked %ux%u format %u depth %u/%u multisample %u; window %ux%u, native back buffer %ux%u",
            saved[0],saved[1],saved[2],saved[8],saved[9],saved[4],w,h,w,h);
    xrt_event("d3d8_borderless","\"virtual_width\":%u,\"virtual_height\":%u,\"window_width\":%u,\"window_height\":%u",saved[0],saved[1],w,h);
    return 1;
}
/* After the native device exists (or was reset): the game's render target and depth surface. */
static void d8_bl_create(CPU*c,D8Device*dev) {
    HRESULT hr;
    hr=XM_CreateTexture(c,dev,d8_bl.vw,d8_bl.vh,1,1/*RENDERTARGET*/,d8_bl.format,0/*DEFAULT*/,&d8_bl.tex);
    if(SUCCEEDED(hr))hr=XM_GetSurfaceLevel(c,d8_bl.tex,0,&d8_bl.rt);
    if(SUCCEEDED(hr)&&d8_bl.depth)hr=XM_CreateDepthStencilSurface(c,dev,d8_bl.vw,d8_bl.vh,d8_bl.depthformat,0,&d8_bl.ds);
    if(SUCCEEDED(hr))hr=XM_SetRenderTarget(c,dev,d8_bl.rt,d8_bl.ds);
    if(FAILED(hr)){d8_native_failed=1;xrt_fatal(c,76,"D3D8 borderless fullscreen: %ux%u render target format %u / depth %u failed hr=%08lx",
                                                  d8_bl.vw,d8_bl.vh,d8_bl.format,d8_bl.depthformat,(unsigned long)hr);}
}
/* The game's frame onto the real back buffer, aspect ratio kept. All device state is restored afterwards. */
static void d8_bl_composite(CPU*c,D8Device*dev) {
    D8Surface*bb=NULL,*saved_rt=NULL,*saved_ds=NULL;void*stream=NULL,*indices=NULL;DWORD stride=0,base=0,block=0;
    D8SurfaceDesc d;float W,H,s,x0,y0,x1,y1;HRESULT hr;
    struct {float x,y,z,rhw,u,v;} q[4];
    static const DWORD rs[][2]={{7,0},{14,0},{15,0},{27,0},{22,1},{137,0},{28,0},{52,0},{8,3},{168,15},{29,0}};
    static const DWORD ts[][3]={{0,1,2},{0,2,2},{0,4,2},{0,5,2},{0,13,3},{0,14,3},{0,16,2},{0,17,2},{0,18,0},{0,11,0},{0,24,0},
                                {1,1,1},{1,4,1}};
    unsigned i;
    if(FAILED(XM_GetBackBuffer(c,dev,0,0,&bb))||FAILED(XM_GetDesc(c,bb,&d))){if(bb)XM_Release(c,(D8Unknown*)bb);return;}
    XM_GetRenderTarget(c,dev,&saved_rt);XM_GetDepthStencilSurface(c,dev,&saved_ds);
    XM_GetStreamSource(c,dev,0,&stream,&stride);XM_GetIndices(c,dev,&indices,&base);
    hr=((D8CreateStateBlockFn)D8_SLOT(dev,57))(dev,1/*D3DSBT_ALL*/,&block);
    if(FAILED(hr))xrt_log("D3D8 borderless: CreateStateBlock failed hr=%08lx",(unsigned long)hr);
    XM_SetRenderTarget(c,dev,bb,NULL);
    XM_BeginScene(c,dev);
    XM_Clear(c,dev,0,NULL,1/*TARGET*/,0xff000000,1.0f,0);
    for(i=0;i<sizeof rs/sizeof rs[0];i++)XM_SetRenderState(c,dev,rs[i][0],rs[i][1]);
    for(i=0;i<sizeof ts/sizeof ts[0];i++)XM_SetTextureStageState(c,dev,ts[i][0],ts[i][1],ts[i][2]);
    ((D8SetPixelShaderFn)D8_SLOT(dev,88))(dev,0);
    XM_SetTexture(c,dev,0,(void*)d8_bl.tex);XM_SetTexture(c,dev,1,NULL);
    XM_SetVertexShader(c,dev,0x104/*XYZRHW|TEX1*/);
    W=(float)d.width;H=(float)d.height;s=W/d8_bl.vw<H/d8_bl.vh?W/d8_bl.vw:H/d8_bl.vh;
    x0=(float)(int)((W-d8_bl.vw*s)/2)-0.5f;y0=(float)(int)((H-d8_bl.vh*s)/2)-0.5f;x1=x0+d8_bl.vw*s;y1=y0+d8_bl.vh*s;
    q[0].x=x0;q[0].y=y0;q[0].u=0;q[0].v=0;q[1].x=x1;q[1].y=y0;q[1].u=1;q[1].v=0;
    q[2].x=x0;q[2].y=y1;q[2].u=0;q[2].v=1;q[3].x=x1;q[3].y=y1;q[3].u=1;q[3].v=1;
    for(i=0;i<4;i++){q[i].z=0;q[i].rhw=1;}
    XM_DrawPrimitiveUP(c,dev,5/*TRIANGLESTRIP*/,2,q,sizeof q[0]);
    XM_EndScene(c,dev);
    XM_SetRenderTarget(c,dev,saved_rt,saved_ds);
    if(block){((D8ApplyStateBlockFn)D8_SLOT(dev,54))(dev,block);((D8DeleteStateBlockFn)D8_SLOT(dev,56))(dev,block);}
    XM_SetStreamSource(c,dev,0,stream,stride);XM_SetIndices(c,dev,indices,base);
    if(stream)XM_Release(c,(D8Unknown*)stream);if(indices)XM_Release(c,(D8Unknown*)indices);
    if(saved_rt)XM_Release(c,(D8Unknown*)saved_rt);if(saved_ds)XM_Release(c,(D8Unknown*)saved_ds);
    XM_Release(c,(D8Unknown*)bb);
    if(!d8_bl.composites++)xrt_log("D3D8 borderless: first frame %ux%u drawn onto %ux%u at %.0f,%.0f size %.0fx%.0f",
                                   d8_bl.vw,d8_bl.vh,d.width,d.height,x0+0.5f,y0+0.5f,d8_bl.vw*s,d8_bl.vh*s);
}

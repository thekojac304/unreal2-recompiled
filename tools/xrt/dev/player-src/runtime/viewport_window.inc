/* Windowed maximize. WinDrv's viewport procedure maps SC_MAXIMIZE (Maximize button, caption double-click, window
 * menu, Win+Up) and Alt+Enter to UWindowsViewport::ToggleFullscreen: TryRenderDevice(..., Fullscreen=1) - exclusive
 * fullscreen, which this port does not implement (CreateDevice fatal 76, runs 20261101-191847/-191912) - followed by
 * "set ini:Engine.Engine.ViewportManager StartupFullscreen true". For the top-level viewport window those two requests
 * are performed here as native WINDOWED maximize/restore and not passed on, so StartupFullscreen is not changed. The
 * guest then receives the ordinary WM_GETMINMAXINFO/WM_WINDOWPOSCHANGED/WM_SIZE sequence (monitor work area, actual
 * client size) and resizes its back buffer as for any other resize. SC_RESTORE, every other message, and explicit
 * fullscreen requests (console TOGGLEFULLSCREEN, video options Fullscreen) still reach the game unchanged. */
static int viewport_top_window(HWND h) {
    WCHAR name[64];
    if(xm_win_GetWindowLongW(h,GWL_STYLE)&WS_CHILD)return 0;
    return GetClassNameW(h,name,64)>0 && wcsstr(name,L"ViewportWindow")!=NULL;
}
static int viewport_windowed_maximize(HWND h,UINT msg,WPARAM wp,LPARAM lp,int wide,LRESULT*result) {
    static unsigned logged;
    if(msg==WM_SYSCOMMAND && (wp&0xfff0)==SC_MAXIMIZE && viewport_top_window(h)) {
        if(logged++<32)xrt_log("viewport SC_MAXIMIZE (%llx): windowed maximize to the monitor work area (not ToggleFullscreen)",(unsigned long long)wp);
        xrt_event("viewport_windowed_maximize","\"source\":\"syscommand\",\"wparam\":%u",(unsigned)wp);
        *result=wide?xm_win_DefWindowProcW(h,msg,wp,lp):xm_win_DefWindowProcA(h,msg,wp,lp);
        return 1;
    }
    /* Alt+Enter is the game's own ToggleFullscreen again: fullscreen is borderless (d3d8_borderless.inc). */
    (void)lp;
    return 0;
}
/* Borderless fullscreen: while the device window has no frame, WinDrv's WM_SIZE handler (fullscreen branch) would move
 * it back to the saved windowed rectangle (viewport+0x194) on every SIZE_RESTORED - undoing the monitor-sized window.
 * The game needs no WM_SIZE in fullscreen (its size comes from SetRes), so it is held back. When the game leaves
 * fullscreen it restores the caption first, and its WM_SIZE flows again. */
static int viewport_fullscreen_size(HWND h,UINT msg) {
    static unsigned logged;
    if(msg!=WM_SIZE || !xrt_d3d8_borderless_window(h) || (xm_win_GetWindowLongW(h,GWL_STYLE)&WS_CAPTION)==WS_CAPTION)return 0;
    if(logged++<8)xrt_log("viewport WM_SIZE held back (borderless fullscreen)");
    return 1;
}
/* The game draws its own menu cursor (moved by DirectInput, not by the system cursor). Over the viewport's client area
 * Windows otherwise shows the window class cursor (a crosshair) on every mouse move whenever the game has not captured
 * the mouse, i.e. in menus - a second cursor that does not follow the game's. While the viewport is the foreground
 * window, WM_SETCURSOR for its client area hides the system cursor; title bar and borders keep the normal cursors, and
 * an inactive window keeps the system cursor. */
static int viewport_set_cursor(HWND h,UINT msg,WPARAM wp,LPARAM lp,LRESULT*result) {
    if(msg!=WM_SETCURSOR || LOWORD(lp)!=HTCLIENT || (HWND)wp!=h || GetForegroundWindow()!=h || !viewport_top_window(h))return 0;
    SetCursor(NULL);
    *result=TRUE;
    return 1;
}
/* WinDrv's WM_SIZE handler treats SIZE_MAXIMIZED as "go fullscreen": it captures the mouse and calls
 * RenDev->SetRes(..., Fullscreen=1) at the maximized size (WinDrv+0x5f28/+0x5ff8; run 20261101-205740 died there right
 * after the windowed maximize above). For the top-level viewport window a maximized size is reported to the game as an
 * ordinary resize (SIZE_RESTORED), so it re-creates a windowed back buffer at the actual client size. */
static WPARAM viewport_size_type(HWND h,UINT msg,WPARAM wp) {
    static unsigned logged;
    if(msg!=WM_SIZE || wp!=SIZE_MAXIMIZED || !viewport_top_window(h))return wp;
    if(logged++<32)xrt_log("viewport WM_SIZE SIZE_MAXIMIZED reported to the game as SIZE_RESTORED (windowed back buffer)");
    return SIZE_RESTORED;
}

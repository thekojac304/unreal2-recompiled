/* Port settings: walking speed, UI scale, field of view (Hor+), subtitle size, frame rate limit, VSync.
 *
 * Persistence is the game's own: the settings helper U2Port.PortSettings (tools/xrt/dev/port/U2Port, registered by
 * the port's UIScripts/U2Menus.ui) keeps them as config(User) variables, i.e. User.ini [U2Port.PortSettings]
 * WalkingSpeed=<percent 75..200> and UIScale=<0 Auto | 100 | 125 | 150 | 200>, FieldOfView=<75..120, default 85 | 0 the game's own>,
 * SubtitleSize=<percent 100 | 112 | 125>, FrameRateLimit=<0 unlimited | 20..1000>, VSync=<True|False>; two keys have no menu
 * entry (A/B and diagnosis only): HorPlus=<1|0> and ScriptTickRate=<0 off | 30..240 Hz>. This file reads that section once
 * from the guest's System\User.ini (before the first use) and then follows changes the helper sends through the
 * console command "PORTSET <Key> <Value>", which UWindowsViewport::Exec would otherwise reject as unknown. Missing or
 * out-of-range values mean the original behaviour (100%, UI unscaled).
 *
 * Walking speed: tools/xrt/dev/native/walk_speed.c wraps APawn::calcVelocity for the call from APawn::physWalking.
 *
 * UI scale S: everything UUIConsole::PostRender draws takes its frame size from the viewport (SizeX +0x74, SizeY +0x78):
 * the root's size and location, the FUIRenderer's orthographic projection and clip rectangle, UScaleContainer's scale,
 * the console's FrameX/FrameY. For that one call the viewport reports W/S x H/S, so the whole UI is laid out in that
 * virtual frame and the renderer's own projection maps it onto the full window: S times larger, aspect, anchors,
 * margins and centring kept, the renderer setting and restoring its transforms as on every frame. The real size is
 * restored right after. (A first attempt pushed an extra renderer scale around the root update: the UI stayed small
 * and the transform leaked into the next frame's 3D view - owner's run of 2026-11-01 21:2x.)
 *
 * Field of view and Hor+: tools/xrt/dev/native/view_fov.c (FCameraSceneNode::UpdateMatrices). Subtitle size: the
 * game's subtitle font in its three sizes, chosen by the UnrealScript side and tools/xrt/dev/port.py (logged here
 * only). Frame rate limit:
 * dev_support.c xrt_dev_frame_limit (the limiter after each Present). VSync: hle_d3d8_device.inc (CreateDevice/Reset
 * swap effect); a change asks for one device reset (xrt_port_vsync_reset_due). Script tick ceiling:
 * native/script_tick.c. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <wchar.h>
#include "xrt_internal.h"

static int loaded, walk_percent = 100, ui_choice = 100;
static volatile float walk_factor = 1.0f;
static unsigned logged;
/* fov 0 = the game's own (User.ini [Engine.PlayerController] DefaultFOV); frame_limit -1 = not set in User.ini */
static int fov_choice = 85, subtitle_percent = 100, frame_limit = -1, vsync, hor_plus = 1, tick_rate = 60;
static volatile LONG vsync_reset_due;

static int valid_walk(int p) { return p >= 75 && p <= 200 && p % 5 == 0; }
static int valid_ui(int p) { return p == 0 || p == 100 || p == 125 || p == 150 || p == 200; }
static void set_walk(int p, const char* source) {
    if (!valid_walk(p)) { xrt_log("port: WalkingSpeed %d ignored (%s; 75..200 in steps of 5)", p, source); return; }
    walk_percent = p; walk_factor = (float)p / 100.0f;
    xrt_log("port: walking speed %d%% (%s)", p, source);
    xrt_event("port_setting", "\"key\":\"WalkingSpeed\",\"value\":%d,\"source\":\"%s\"", p, source);
}
static void set_ui(int p, const char* source) {
    if (!valid_ui(p)) { xrt_log("port: UIScale %d ignored (%s; 0 Auto, 100, 125, 150, 200)", p, source); return; }
    ui_choice = p;
    xrt_log("port: UI scale %s%d (%s)", p ? "" : "Auto/", p, source);
    xrt_event("port_setting", "\"key\":\"UIScale\",\"value\":%d,\"source\":\"%s\"", p, source);
}
static void set_fov(int p, const char* source) {
    if (p && (p < 75 || p > 120)) { xrt_log("port: FieldOfView %d ignored (%s; 0 or 75..120)", p, source); return; }
    fov_choice = p;
    xrt_log("port: field of view %s%d (%s; horizontal degrees at 4:3, widened Hor+ for wider screens)", p ? "" : "the game's own/", p, source);
    xrt_event("port_setting", "\"key\":\"FieldOfView\",\"value\":%d,\"source\":\"%s\"", p, source);
}
static void set_subtitle(int p, const char* source) {
    if (p < 100 || p > 200) { xrt_log("port: SubtitleSize %d ignored (%s; 100..200)", p, source); return; }
    subtitle_percent = p;
    xrt_log("port: subtitle size %d%% (%s)", p, source);
    xrt_event("port_setting", "\"key\":\"SubtitleSize\",\"value\":%d,\"source\":\"%s\"", p, source);
}
static void set_frame_limit(int p, const char* source, int apply) {
    if (p && (p < 20 || p > 1000)) { xrt_log("port: FrameRateLimit %d ignored (%s; 0 unlimited or 20..1000)", p, source); return; }
    frame_limit = p;
    xrt_event("port_setting", "\"key\":\"FrameRateLimit\",\"value\":%d,\"source\":\"%s\"", p, source);
    if (apply) xrt_dev_frame_limit((unsigned)p, source);
}
static void set_vsync(int on, const char* source, int reset) {
    int changed = on != vsync;
    vsync = on;
    xrt_log("port: VSync %s (%s)%s", on ? "on" : "off", source, changed && reset ? "; device reset requested" : "");
    xrt_event("port_setting", "\"key\":\"VSync\",\"value\":%d,\"source\":\"%s\"", on, source);
    if (changed && reset) InterlockedExchange(&vsync_reset_due, 1);
}
static int ini_bool(const char* path, const char* key, int fallback) {
    char v[16];
    GetPrivateProfileStringA("U2Port.PortSettings", key, "", v, sizeof v, path);
    if (!v[0]) return fallback;
    return !_stricmp(v, "true") || atoi(v) != 0;
}
static void load(void) {
    XrtModule* exe;
    char path[600], *slash;
    if (loaded) return;
    loaded = 1;
    exe = xrt_module_by_name("Unreal2.exe");
    if (!exe) return;
    snprintf(path, sizeof path, "%s", exe->path);
    slash = strrchr(path, '\\');
    if (!slash) return;
    snprintf(slash + 1, sizeof path - (size_t)(slash + 1 - path), "User.ini");
    set_walk((int)GetPrivateProfileIntA("U2Port.PortSettings", "WalkingSpeed", 100, path), "User.ini");
    set_ui((int)GetPrivateProfileIntA("U2Port.PortSettings", "UIScale", 100, path), "User.ini");
    set_fov((int)GetPrivateProfileIntA("U2Port.PortSettings", "FieldOfView", 85, path), "User.ini");   /* default: the class default 85 (see view_fov.c) */
    set_subtitle((int)GetPrivateProfileIntA("U2Port.PortSettings", "SubtitleSize", 100, path), "User.ini");
    {
        int n = (int)GetPrivateProfileIntA("U2Port.PortSettings", "FrameRateLimit", -1, path);
        if (n >= 0) set_frame_limit(n, "User.ini", 0);   /* applied by dev_support.c at Init return (xrt_port_frame_limit) */
    }
    set_vsync(ini_bool(path, "VSync", 0), "User.ini", 0);
    hor_plus = ini_bool(path, "HorPlus", 1);
    tick_rate = (int)GetPrivateProfileIntA("U2Port.PortSettings", "ScriptTickRate", 60, path);
    if (tick_rate && (tick_rate < 30 || tick_rate > 240)) tick_rate = 60;
    xrt_log("port: Hor+ %s, script tick ceiling %d Hz (User.ini)", hor_plus ? "on" : "OFF", tick_rate);
}
int xrt_port_field_of_view(void) { if (!loaded) load(); return fov_choice; }
int xrt_port_hor_plus(void) { if (!loaded) load(); return hor_plus; }
int xrt_port_frame_limit(void) { if (!loaded) load(); return frame_limit; }
int xrt_port_vsync(void) { if (!loaded) load(); return vsync; }
int xrt_port_script_tick_rate(void) { if (!loaded) load(); return tick_rate; }
int xrt_port_vsync_reset_due(void) { return InterlockedExchange(&vsync_reset_due, 0) != 0; }
/* Developer input script "pset:KEY:VALUE" (dev_support.c): the same paths as the menu's PORTSET, by number. */
void xrt_port_set(int key, int value, const char* source) {
    if (!loaded) load();
    switch (key) {
    case 1: set_fov(value, source); break;
    case 2: set_subtitle(value, source); break;
    case 3: set_vsync(value != 0, source, 1); break;
    case 4: hor_plus = value != 0; xrt_log("port: Hor+ %s (%s)", hor_plus ? "on" : "OFF", source); break;
    case 5: set_ui(value, source); break;
    case 6: set_walk(value, source); break;
    case 7: set_frame_limit(value, source, 1); break;
    case 8: tick_rate = value; xrt_log("port: script tick ceiling %d Hz (%s)", value, source); break;
    default: xrt_log("port: pset key %d unknown (%s)", key, source);
    }
}

float xrt_port_walking_speed(void) {
    if (!loaded) load();
    return walk_factor;
}

/* Auto: the menus and HUD are laid out for about 1024x768 pixels; keep their height near the original 1024x768
 * proportion (768 of 1024 lines) - the largest offered scale with 768*S <= 0.75*height: 1080 lines -> 100%,
 * 1369/1440 -> 125%, 1600 -> 150%, 2160 -> 200%. The executable is DPI-unaware, so on a high-DPI monitor Windows already
 * presents it in logical pixels; the height here is the actual client (back buffer) height. */
static float ui_scale(uint32_t width, uint32_t height) {
    static const int choices[] = {200, 150, 125};
    int p = ui_choice, i;
    float s, room;
    if (!loaded) load();
    if (!p) {
        p = 100;
        for (i = 0; i < 3; i++) if (768.0 * choices[i] / 100.0 <= 0.75 * height) { p = choices[i]; break; }
    }
    /* The menus are laid out for at least 640x480: the scaled frame never gets smaller than that (720x480 at 150%
     * cut the Video options off at the top and bottom - owner's screenshot), and never larger than the screen. */
    s = (float)p / 100.0f;
    room = width / 640.0f < height / 480.0f ? width / 640.0f : height / 480.0f;
    if (s > room) s = room;
    return s < 1.0f ? 1.0f : s;
}

/* Video > Resolution in a window ("PORTSET WindowSize W H", PortSettings.SetResolution): the game window gets a W x H
 * client area, centred on its monitor's work area (and no larger), leaving the maximized state in the same step. The
 * game sees one ordinary WM_SIZE and re-creates its back buffer at that size, as for a drag-resize. (The game's own
 * SETRES would move a maximized window while it stays maximized.) */
static BOOL CALLBACK find_viewport(HWND h, LPARAM out) {
    WCHAR name[64];
    if ((GetWindowLongW(h, GWL_STYLE) & (WS_CHILD | WS_VISIBLE)) != WS_VISIBLE || GetClassNameW(h, name, 64) <= 0 ||
        !wcsstr(name, L"ViewportWindow")) return TRUE;
    *(HWND*)out = h;
    return FALSE;
}
static void set_window_size(CPU* c, int w, int h) {
    HWND win = NULL; RECT r; MONITORINFO mi; WINDOWPLACEMENT wp; LONG style, ex; int ww, wh, aw, ah; CPU* prev;
    EnumThreadWindows(GetCurrentThreadId(), find_viewport, (LPARAM)&win);
    if (!win || w < 320 || h < 200) { xrt_log("port: window size %dx%d not applied (no game window or too small)", w, h); return; }
    style = GetWindowLongW(win, GWL_STYLE); ex = GetWindowLongW(win, GWL_EXSTYLE);
    mi.cbSize = sizeof mi; GetMonitorInfoW(MonitorFromWindow(win, MONITOR_DEFAULTTONEAREST), &mi);
    aw = mi.rcWork.right - mi.rcWork.left; ah = mi.rcWork.bottom - mi.rcWork.top;
    SetRect(&r, 0, 0, w, h); AdjustWindowRectEx(&r, style, FALSE, ex);
    ww = r.right - r.left; wh = r.bottom - r.top;
    if (ww > aw) ww = aw;
    if (wh > ah) wh = ah;
    wp.length = sizeof wp; GetWindowPlacement(win, &wp);
    wp.showCmd = SW_SHOWNORMAL; wp.flags = 0;
    /* rcNormalPosition is in workspace coordinates: screen coordinates relative to the PRIMARY monitor's work area */
    {
        RECT primary; int x, y;
        SystemParametersInfoW(SPI_GETWORKAREA, 0, &primary, 0);
        x = mi.rcWork.left - primary.left + (aw - ww) / 2; y = mi.rcWork.top - primary.top + (ah - wh) / 2;
        SetRect(&wp.rcNormalPosition, x, y, x + ww, y + wh);
    }
    prev = xrt_gui_callback_enter(c);
    SetWindowPlacement(win, &wp);
    xrt_gui_callback_leave(prev);
    GetClientRect(win, &r);
    xrt_log("port: window client %dx%d requested, now %ldx%ld", w, h, r.right, r.bottom);
}

/* "PORTSET Key Value [Value]" (UTF-16, as UWindowsViewport::Exec receives it). Returns 1 when the command was ours. */
static int port_command(CPU* c, const uint16_t* s) {
    wchar_t text[96], key[32];
    int n, value, second = 0, fields;
    for (n = 0; n < 95 && s[n]; n++) text[n] = (wchar_t)s[n];
    text[n] = 0;
    if (_wcsnicmp(text, L"PORTSET ", 8)) return 0;
    fields = swscanf(text + 8, L"%31ls %d %d", key, &value, &second);
    if (fields < 2) { xrt_log("port: malformed command \"%ls\"", text); return 1; }
    if (!_wcsicmp(key, L"WalkingSpeed")) set_walk(value, "menu");
    else if (!_wcsicmp(key, L"UIScale")) set_ui(value, "menu");
    else if (!_wcsicmp(key, L"WindowSize") && fields == 3) set_window_size(c, value, second);
    else if (!_wcsicmp(key, L"FieldOfView")) set_fov(value, "menu");
    else if (!_wcsicmp(key, L"SubtitleSize")) set_subtitle(value, "menu");
    else if (!_wcsicmp(key, L"FrameRateLimit")) set_frame_limit(value, "menu", 1);
    else if (!_wcsicmp(key, L"VSync")) set_vsync(value != 0, "menu", 1);
    else xrt_log("port: unknown setting \"%ls\"", key);
    return 1;
}

/* kind 1: UWindowsViewport::Exec(const TCHAR*, FOutputDevice&); kind 2: UUIConsole::PostRender(FSceneNode* Frame).
 * Returns 1 when the call was completed here. */
int xrt_port_call(CPU* c, unsigned kind, XrtLiftedFn fn) {
    uint32_t esp = c->r[ESP];
    if (kind == 1) {
        uint32_t s = rd32(esp + 4);
        if (!s || !port_command(c, (const uint16_t*)G2H(s))) return 0;
        c->r[EAX] = 1; c->rv = pop32(c); c->r[ESP] += 8;
        return 1;
    } else {
        uint32_t frame = rd32(esp + 4), viewport = frame ? rd32(frame + 4) : 0, w, h, vw, vh;
        float s;
        if (!viewport) return 0;
        w = rd32(viewport + 0x74); h = rd32(viewport + 0x78);
        s = ui_scale(w, h);
        if (s == 1.0f || !w || !h) return 0;
        vw = (uint32_t)(w / s + 0.5f); vh = (uint32_t)(h / s + 0.5f);
        if (logged++ < 8) xrt_log("port: UI drawn from a %ux%u frame on the %ux%u viewport (x%g)", vw, vh, w, h, s);
        wr32(viewport + 0x74, vw); wr32(viewport + 0x78, vh);
        XRT_CALL_LIFTED(fn, c);
        /* restore the real size unless the game itself changed it meanwhile */
        if (rd32(viewport + 0x74) == vw && rd32(viewport + 0x78) == vh) { wr32(viewport + 0x74, w); wr32(viewport + 0x78, h); }
        return 1;
    }
}

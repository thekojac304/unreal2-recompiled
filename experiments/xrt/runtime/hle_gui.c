/* Real USER32/GDI objects behind guest tokens; host pointers never escape. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"
typedef struct GuiDC
{
    HDC host;
    HWND window;
    DWORD thread;
} GuiDC;
static void begin(CPU *c)
{
    SetLastError(xrt_get_last_error(c));
}
static void end(CPU *c)
{
    xrt_set_last_error(c, GetLastError());
}
static void hle_GetDC(CPU *c)
{
    HDC dc;
    GuiDC *g;
    uint32_t result = 0;
    if (ARG(0))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "GetDC: non-desktop window unsupported");
    begin(c);
    dc = GetDC(NULL);
    end(c);
    if (dc)
    {
        g = (GuiDC *)calloc(1, sizeof *g);
        if (!g)
        {
            ReleaseDC(NULL, dc);
            xrt_fatal(c, XRT_EXIT_SETUP, "GetDC allocation");
        }
        g->host = dc;
        g->thread = GetCurrentThreadId();
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
    if (ARG(0))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "ReleaseDC: non-desktop window unsupported");
    begin(c);
    if (g && g->window == NULL && g->thread == GetCurrentThreadId())
        ok = ReleaseDC(NULL, g->host);
    end(c);
    if (ok)
    {
        free(g);
        xrt_handle_free(token);
    }
    xrt_event("gui_release_dc", "\"handle\": %u, \"result\": %d", token, ok);
    RET_STD(2, ok);
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
    bitmap = CreateDIBitmap(dc ? dc->host : NULL, ARG(1) ? (BITMAPINFOHEADER *)G2H(ARG(1)) : NULL, ARG(2),
                            ARG(3) ? G2H(ARG(3)) : NULL, ARG(4) ? (BITMAPINFO *)G2H(ARG(4)) : NULL, ARG(5));
    end(c);
    if (bitmap)
        result = xrt_handle_new(XH_BITMAP, bitmap);
    xrt_event("gui_create_dibitmap", "\"handle\": %u", result);
    RET_STD(6, result);
}
static void hle_DeleteObject(CPU *c)
{
    uint32_t token = ARG(0);
    HGDIOBJ obj = (HGDIOBJ)xrt_handle_get(token, XH_BITMAP);
    BOOL ok;
    begin(c);
    ok = DeleteObject(obj);
    end(c);
    if (ok)
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
    result = GetDIBits(dc ? dc->host : NULL, bitmap, ARG(2), ARG(3), ARG(4) ? G2H(ARG(4)) : NULL,
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
    HFONT host_font;
    DWORD thread;
} GuiWindow;
static GuiWindow windows[1024];
static __declspec(thread) CPU *callback_cpu;
static __declspec(thread) uint32_t creating_proc;
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
            windows[i].thread = GetCurrentThreadId();
            windows[i].token = xrt_handle_new(XH_WINDOW, h);
            return windows[i].token;
        }
    xrt_fatal(callback_cpu, XRT_EXIT_SETUP, "GUI window table full");
}
static void forget_dead_windows(void)
{
    unsigned i;
    for (i = 0; i < 1024; i++)
        if (windows[i].host && !IsWindow(windows[i].host))
        {
            if (windows[i].font)
                xrt_handle_free(windows[i].font);
            xrt_handle_free(windows[i].token);
            memset(&windows[i], 0, sizeof windows[i]);
        }
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
static INT_PTR CALLBACK dialog_bridge(HWND h, UINT msg, WPARAM wp, LPARAM lp)
{
    CPU nested;
    uint32_t args[4], proc = 0, scratch = 0;
    unsigned i;
    INT_PTR result;
    GuiWindow *window = NULL;
    DWORD error = GetLastError();
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
            if (!window->proc)
                window->proc = creating_proc;
            proc = window->proc;
            break;
        }
    if (!proc)
        return FALSE;
    nested = *callback_cpu;
    xrt_set_last_error(&nested, error);
    /* Temporary structures use the guest stack below the suspended import frame. */
    scratch = (nested.r[ESP] - 128u) & ~15u;
    nested.r[ESP] = scratch;
    switch (msg)
    {
    case 0x90: /* Observed Windows theme destruction notification: both arguments zero. */
        if (wp || lp)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "theme destruction notification has nonzero arguments");
        break;
    case WM_GETDLGCODE:
        if (lp)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_GETDLGCODE MSG pointer requires marshalling");
        break;
    case WM_NCPAINT:
        if (wp != 1)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "WM_NCPAINT region requires handle translation");
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
            if (window->font)
                xrt_handle_free(window->font);
            window->host_font = (HFONT)wp;
            window->font = wp ? xrt_handle_new(XH_FONT, (void *)wp) : 0;
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
    case WM_COMMAND:
        args[3] = window_token((HWND)lp);
        break;
    case WM_PALETTECHANGED:
        args[2] = window_token((HWND)wp);
        break;
    case WM_NOTIFY:
    case WM_DRAWITEM:
    case WM_MEASUREITEM:
    case WM_COMPAREITEM:
    case WM_DELETEITEM:
    case WM_CREATE:
    case WM_NCCREATE:
    case WM_SETTINGCHANGE:
    case WM_GETTEXT:
    case WM_SETTEXT:
        xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "dialog callback pointer message 0x%x requires marshalling", msg);
    default:
        /* Only measured scalar messages may cross unmodified. */
        if (!((msg <= WM_ENABLE && msg != WM_GETTEXT) || msg == WM_PAINT || msg == WM_ERASEBKGND ||
              msg == WM_SHOWWINDOW || msg == WM_NCPAINT || msg == WM_NCACTIVATE || msg == WM_DESTROY ||
              msg == WM_NCDESTROY || msg == WM_CANCELMODE || msg == WM_GETDLGCODE || msg == WM_GETFONT ||
              msg == WM_CHANGEUISTATE || msg == WM_UPDATEUISTATE || msg == WM_QUERYUISTATE ||
              msg == WM_QUERYNEWPALETTE || msg == WM_PALETTECHANGED || msg == WM_DWMNCRENDERINGCHANGED ||
              msg == WM_ACTIVATEAPP || msg == WM_IME_SETCONTEXT || msg == WM_IME_NOTIFY))
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "dialog callback message 0x%x unsupported (wp=%llx lp=%llx)",
                      msg, (unsigned long long)wp, (unsigned long long)lp);
    }
    xrt_event("gui_callback", "\"message\": %u, \"proc\": %u", msg, proc);
    result = (INT_PTR)(int32_t)xrt_call_guest(&nested, proc, 4, args, 1);
    if (msg == WM_WINDOWPOSCHANGING || msg == WM_WINDOWPOSCHANGED)
        unpack_windowpos((WINDOWPOS *)lp, scratch);
    if (msg == WM_GETMINMAXINFO)
        memcpy((void *)lp, G2H(scratch), 40);
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
    if (msg == WM_ERASEBKGND || msg == WM_CTLCOLORSTATIC || msg == WM_CTLCOLORDLG || msg == WM_CTLCOLOREDIT ||
        msg == WM_CTLCOLORBTN)
    {
        free(xrt_handle_get(args[2], XH_DC));
        xrt_handle_free(args[2]);
        if (result && msg != WM_ERASEBKGND)
            xrt_fatal(&nested, XRT_EXIT_UNSUPPORTED, "dialog callback brush result requires handle translation");
    }
    SetLastError(xrt_get_last_error(&nested));
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
            if (!MultiByteToWideChar(CP_ACP, 0, m->path, -1, path, 1024))
            {
                xrt_set_last_error(c, GetLastError());
                return NULL;
            }
            host = LoadLibraryExW(path, NULL, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE);
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
    if (wide)
        h = CreateDialogParamW(resources, ARG(1) < 0x10000u ? MAKEINTRESOURCEW(ARG(1)) : (LPCWSTR)G2H(ARG(1)),
                               parent, dialog_bridge, (LPARAM)(int32_t)ARG(4));
    else
        h = CreateDialogParamA(resources, ARG(1) < 0x10000u ? MAKEINTRESOURCEA(ARG(1)) : (LPCSTR)G2H(ARG(1)),
                               parent, dialog_bridge, (LPARAM)(int32_t)ARG(4));
    end(c);
    if (h)
        result = window_token(h);
    callback_cpu = previous;
    creating_proc = oldproc;
    FreeLibrary(resources);
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
    h = GetDlgItem(window_host(ARG(0)), (int)ARG(1));
    end(c);
    result = window_token(h);
    RET_STD(2, result);
}
static void hle_GetSystemMetrics(CPU *c)
{
    int result;
    begin(c);
    result = GetSystemMetrics((int)ARG(0));
    end(c);
    RET_STD(1, result);
}
static void hle_GetWindowRect(CPU *c)
{
    RECT rect;
    BOOL ok;
    begin(c);
    ok = GetWindowRect(window_host(ARG(0)), ARG(1) ? &rect : NULL);
    end(c);
    if (ok)
        memcpy(G2H(ARG(1)), &rect, 16);
    RET_STD(2, ok);
}
static void hle_SetWindowPos(CPU *c)
{
    BOOL ok;
    CPU *prev = callback_cpu;
    callback_cpu = c;
    begin(c);
    ok = SetWindowPos(window_host(ARG(0)), insert_host(ARG(1)), (int)ARG(2), (int)ARG(3), (int)ARG(4), (int)ARG(5),
                      ARG(6));
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
        wide ? SendMessageW(window_host(ARG(0)), msg, wp, lp) : SendMessageA(window_host(ARG(0)), msg, wp, lp);
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
    ok = UpdateWindow(window_host(ARG(0)));
    end(c);
    callback_cpu = prev;
    RET_STD(1, ok);
}
static void hle_DestroyWindow(CPU *c)
{
    BOOL ok;
    CPU *prev = callback_cpu;
    callback_cpu = c;
    begin(c);
    ok = DestroyWindow(window_host(ARG(0)));
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
        module = LoadLibraryExW(L"comctl32.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    ordinal = module ? GetProcAddress(module, MAKEINTRESOURCEA(17)) : NULL;
    named = module ? GetProcAddress(module, "InitCommonControls") : NULL;
    if (!ordinal || ordinal != named)
        xrt_fatal(c, XRT_EXIT_SETUP, "COMCTL32 ordinal 17 differs from InitCommonControls");
    ((Init)ordinal)();
    end(c);
    /* Keep the host module loaded: it owns the registered common control classes. */
    xrt_event("gui_init_common_controls", NULL);
    c->rv = pop32(c); /* void function: preserve guest EAX */
}
const XrtHle xrt_hle_gui[] = {{"comctl32.dll", "#17", hle_InitCommonControls},
                              {"comctl32.dll", "InitCommonControls", hle_InitCommonControls},
                              {"user32.dll", "GetDC", hle_GetDC},
                              {"user32.dll", "ReleaseDC", hle_ReleaseDC},
                              {"user32.dll", "CreateDialogParamW", hle_CreateDialogParamW},
                              {"user32.dll", "CreateDialogParamA", hle_CreateDialogParamA},
                              {"user32.dll", "GetDlgItem", hle_GetDlgItem},
                              {"user32.dll", "GetSystemMetrics", hle_GetSystemMetrics},
                              {"user32.dll", "GetWindowRect", hle_GetWindowRect},
                              {"gdi32.dll", "GetDIBits", hle_GetDIBits},
                              {"user32.dll", "SetWindowPos", hle_SetWindowPos},
                              {"user32.dll", "SendMessageW", hle_SendMessageW},
                              {"user32.dll", "SendMessageA", hle_SendMessageA},
                              {"user32.dll", "UpdateWindow", hle_UpdateWindow},
                              {"user32.dll", "DestroyWindow", hle_DestroyWindow},
                              {"gdi32.dll", "CreateDIBitmap", hle_CreateDIBitmap},
                              {"gdi32.dll", "DeleteObject", hle_DeleteObject},
                              {0}};

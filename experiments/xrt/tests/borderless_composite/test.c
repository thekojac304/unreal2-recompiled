/* borderless_composite - focused test of the developer runtime's borderless fullscreen compositor
 * (out/dev-init/runtime/d3d8_borderless.inc) on the real pinned DXVK D3D8/D3D9 pair the game uses (x64, the verified
 * third_party/graphics/dxvk-v3.1.1 directory, loaded like hle_d3d8.inc does). No game code is involved.
 *
 * A hidden 1000x500 popup window, a windowed native device with a 1000x500 back buffer (as d8_bl_translate asks for),
 * then d8_bl_create for a 320x240 game back buffer (render-target texture + D24S8 depth), a red "game frame", and
 * d8_bl_composite:
 *   targets   after creation GetRenderTarget / GetDepthStencilSurface are the runtime's surfaces, viewport 320x240
 *   image     the back buffer shows the frame scaled by min(1000/320, 500/240) with the aspect kept: red in the middle
 *             (x 167..833), black bars left and right
 *   restore   render target, depth surface, render states, texture stage state, FVF, viewport, stream 0 and the
 *             texture of stage 0 are exactly as the game left them
 *   repeat    100 composites: no failure, state still intact (no leaked state blocks/references: release counts at the end)
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/borderless_composite/run.cmd */
#include <windows.h>
#include <stdio.h>
#include "xrt_internal.h"
#include "monitor_com.inc"

/* ---- owned stubs for what the compositor and the monitor wrappers use */
uint8_t* xrt_g;
unsigned xm_quiet = 1;
CPU* xm_current_cpu(void) { return NULL; }
#undef xm_probe
void xm_probe(CPU* c, const XmRequest* q) { (void)c; (void)q; }
#define xm_probe xm_probe_gated
void xm_scope(CPU* c, unsigned e, unsigned d, const char* n, uint64_t r) { (void)c; (void)e; (void)d; (void)n; (void)r; }
void xm_span(CPU* c, const char* n, const void* p, unsigned b) { (void)c; (void)n; (void)p; (void)b; }
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
void xrt_log(const char* fmt, ...) { va_list a; va_start(a, fmt); printf("     log: "); vprintf(fmt, a); printf("\n"); va_end(a); }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list a; (void)c; va_start(a, fmt); printf("FAIL fatal %d: ", code); vprintf(fmt, a); printf("\n"); va_end(a); exit(1);
}
static HWND test_window;
void* xrt_gui_device_window(CPU* c, uint32_t token) { (void)c; (void)token; return test_window; }
CPU* xrt_gui_callback_enter(CPU* c) { return c; }
void xrt_gui_callback_leave(CPU* p) { (void)p; }
static int d8_native_failed;
#include "d3d8_borderless.inc"

static int failures;
#define CHECK(cond, ...) do { int ok_ = !!(cond); printf(ok_ ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!ok_) failures++; } while (0)

static DWORD rs(D8Device* d, DWORD s) { DWORD v = 0xdeadbeef; d->vt->GetRenderState(d, s, &v); return v; }
static DWORD pixel(D8Device* d, D8Surface* sys, int x, int y) {
    D8Locked l; DWORD v; (void)d;
    sys->vt->LockRect(sys, &l, NULL, 0x10);
    v = *(DWORD*)((BYTE*)l.bits + y * l.pitch + 4 * x) & 0xffffff;
    sys->vt->UnlockRect(sys);
    return v;
}

int main(void) {
    char dir[MAX_PATH], path[MAX_PATH]; HMODULE d9, d8; D8Interface* (WINAPI* create)(UINT); D8Interface* api;
    D8Present n = {0}; D8Device* dev = NULL; D8Surface *rt = NULL, *ds = NULL, *bb = NULL, *sys = NULL; D8Buffer* vb = NULL;
    D8Viewport vp = {10, 10, 100, 100, 0, 0}, got = {0}; DWORD v, stride = 0; void* stream = NULL; void* tex0 = NULL;
    WNDCLASSW wc = {0}; HRESULT hr; int i, ok;
    if (!GetEnvironmentVariableA("XRT_D3D8_DIR", dir, sizeof dir)) { printf("FAIL XRT_D3D8_DIR not set\n"); return 1; }
    snprintf(path, sizeof path, "%s\\d3d9.dll", dir); d9 = LoadLibraryExA(path, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path, sizeof path, "%s\\d3d8.dll", dir); d8 = LoadLibraryExA(path, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!d9 || !d8) { printf("FAIL cannot load the DXVK pair from %s\n", dir); return 1; }
    create = (D8Interface* (WINAPI*)(UINT))GetProcAddress(d8, "Direct3DCreate8");
    api = create(220);
    wc.lpfnWndProc = DefWindowProcW; wc.hInstance = GetModuleHandleW(NULL); wc.lpszClassName = L"xrt_borderless_test"; RegisterClassW(&wc);
    test_window = CreateWindowExW(0, wc.lpszClassName, L"", WS_POPUP, 0, 0, 1000, 500, NULL, NULL, wc.hInstance, NULL);
    n.width = 1000; n.height = 500; n.format = 22; n.count = 1; n.swap = 1; n.window = test_window; n.windowed = 1;
    hr = XM_CreateDevice(NULL, api, 0, 1, test_window, 0x40 /*HARDWARE_VERTEXPROCESSING*/ | 2 /*FPU_PRESERVE*/, &n, &dev);
    CHECK(SUCCEEDED(hr) && dev, "windowed native device with a 1000x500 back buffer (hr %08lx)", (unsigned long)hr);
    if (!dev) return 1;

    d8_bl.active = 1; d8_bl.window = test_window; d8_bl.vw = 320; d8_bl.vh = 240; d8_bl.format = 22; d8_bl.depth = 1; d8_bl.depthformat = 75;
    d8_bl_create(NULL, dev);
    dev->vt->GetRenderTarget(dev, &rt); dev->vt->GetDepthStencilSurface(dev, &ds); dev->vt->GetViewport(dev, &got);
    CHECK(rt == d8_bl.rt && ds == d8_bl.ds && got.width == 320 && got.height == 240,
          "targets: render target and depth are the runtime's, viewport %lux%lu", got.width, got.height);
    if (rt) XM_Release(NULL, (D8Unknown*)rt); if (ds) XM_Release(NULL, (D8Unknown*)ds);

    /* the game's frame and state */
    dev->vt->Clear(dev, 0, NULL, 1, 0xffff0000, 1.0f, 0);
    dev->vt->SetRenderState(dev, 7, 1); dev->vt->SetRenderState(dev, 22, 3); dev->vt->SetRenderState(dev, 27, 1);
    dev->vt->SetTextureStageState(dev, 0, 1, 4);
    dev->vt->SetVertexShader(dev, 0x42);
    dev->vt->CreateVertexBuffer(dev, 64, 0, 0, 1, &vb);
    dev->vt->SetStreamSource(dev, 0, vb, 16);
    dev->vt->SetTexture(dev, 0, NULL);
    dev->vt->SetViewport(dev, &vp);

    for (i = 0, ok = 1; i < 100; i++) d8_bl_composite(NULL, dev);
    dev->vt->GetRenderTarget(dev, &rt); dev->vt->GetDepthStencilSurface(dev, &ds); dev->vt->GetViewport(dev, &got);
    dev->vt->GetStreamSource(dev, 0, &stream, &stride); dev->vt->GetTexture(dev, 0, &tex0); dev->vt->GetVertexShader(dev, &v);
    CHECK(rt == d8_bl.rt && ds == d8_bl.ds, "restore: render target and depth surface");
    CHECK(rs(dev, 7) == 1 && rs(dev, 22) == 3 && rs(dev, 27) == 1, "restore: render states (z %lu cull %lu blend %lu)", rs(dev, 7), rs(dev, 22), rs(dev, 27));
    { DWORD op = 0; dev->vt->GetTextureStageState(dev, 0, 1, &op); CHECK(op == 4, "restore: stage 0 COLOROP (%lu)", op); }
    CHECK(v == 0x42, "restore: FVF %lx", v);
    CHECK(got.x == 10 && got.y == 10 && got.width == 100 && got.height == 100, "restore: viewport %lu,%lu %lux%lu", got.x, got.y, got.width, got.height);
    CHECK(stream == (void*)vb && stride == 16 && tex0 == NULL, "restore: stream 0 and stage 0 texture");
    if (rt) XM_Release(NULL, (D8Unknown*)rt); if (ds) XM_Release(NULL, (D8Unknown*)ds); if (stream) XM_Release(NULL, (D8Unknown*)stream);

    /* the image */
    dev->vt->GetBackBuffer(dev, 0, 0, &bb);
    dev->vt->CreateImageSurface(dev, 1000, 500, 22, &sys);
    hr = dev->vt->CopyRects(dev, bb, NULL, 0, sys, NULL);
    CHECK(SUCCEEDED(hr), "back buffer read back (hr %08lx)", (unsigned long)hr);
    CHECK(pixel(dev, sys, 500, 250) == 0xff0000 && pixel(dev, sys, 200, 30) == 0xff0000 && pixel(dev, sys, 800, 470) == 0xff0000,
          "image: game frame red inside x 167..833 (%06lx %06lx %06lx)", pixel(dev, sys, 500, 250), pixel(dev, sys, 200, 30), pixel(dev, sys, 800, 470));
    CHECK(pixel(dev, sys, 60, 250) == 0 && pixel(dev, sys, 940, 250) == 0, "image: black bars left and right (%06lx %06lx)",
          pixel(dev, sys, 60, 250), pixel(dev, sys, 940, 250));
    XM_Release(NULL, (D8Unknown*)sys); XM_Release(NULL, (D8Unknown*)bb);
    hr = dev->vt->Present(dev, NULL, NULL, NULL, NULL);
    CHECK(SUCCEEDED(hr), "Present (hr %08lx)", (unsigned long)hr);

    dev->vt->SetStreamSource(dev, 0, NULL, 0); XM_Release(NULL, (D8Unknown*)vb);
    d8_bl_end("test");
    v = dev->vt->Release(dev);
    CHECK(v == 0, "device released to 0 after the runtime's objects (%lu): no leaked references", v);
    printf("%s (%d failure%s)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

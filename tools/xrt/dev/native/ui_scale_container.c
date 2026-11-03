/* ui_scale_container.c - port setting "Subtitle Size" (always linked: dev.py PORT). Wraps the translated UI.dll
 * function f_1917f270, the virtual  void UScaleContainer::Update(FSceneNode* Frame, FUIRenderer* Ren)  (thiscall,
 * ret 8). This is a reconstruction of game code: keep it out of redistribution.
 *
 * The game's own ScaleContainer scales its children by (Frame width / RelativeSize.X, Frame height / RelativeSize.Y)
 * (RelativeSize floats at +0x6c/+0x70, parsed with appAtof; Frame->Viewport +0x4, its SizeX/SizeY +0x74/+0x78, which
 * port_settings.c's UI scale already reports as the virtual UI frame). The port's UIScripts/DialogUI.ui wraps the
 * spoken-dialogue subtitles (DialogSubtitlesContainer, 700x75, bottom centre) in a ScaleContainer whose RelativeSize
 * is the marker 640.25,480.25. For that container only, RelativeSize is set to frame / S for the one call, so the
 * subtitles are drawn S times larger (S = SubtitleSize / 100, on top of the UI scale) with their bottom-centre anchor,
 * line wrapping (the dialogue code wraps in the container's own units) and font kept; the marker is restored right
 * after. S is limited so the 700-unit subtitle box (plus margins) stays inside the frame width and a quarter of its
 * height (never below 1: 100% is exactly the original); the box stays above the bottom edge (its 50-unit offset
 * scales with it). Without this runtime the marker would act as an
 * ordinary 640x480 ScaleContainer (subtitles scaled with the window height), never invisible. */
#include "xrt_internal.h"

XrtLiftedRet f_1917f270_translated(CPU* c);

enum { REL_X = 0x6c, REL_Y = 0x70, FRAME_VIEWPORT = 0x4, VIEWPORT_SIZE_X = 0x74, VIEWPORT_SIZE_Y = 0x78 };
#define MARK_X 640.25f
#define MARK_Y 480.25f

XrtLiftedRet f_1917f270(CPU* c) {
    static unsigned logged;
    static float last_s;
    uint32_t self = c->r[ECX], frame = rd32(c->r[ESP] + 4), viewport;
    float w, h, s, room;
#ifdef XRT_RV_ABI
    uint32_t rv;
#endif
    if (rdf32(self + REL_X) != MARK_X || rdf32(self + REL_Y) != MARK_Y || !frame || !(viewport = rd32(frame + FRAME_VIEWPORT))) {
        XRT_TAIL(f_1917f270_translated(c));
    }
    w = (float)(int32_t)rd32(viewport + VIEWPORT_SIZE_X); h = (float)(int32_t)rd32(viewport + VIEWPORT_SIZE_Y);
    if (w < 64.0f || h < 64.0f) { XRT_TAIL(f_1917f270_translated(c)); }
    s = xrt_port_subtitle_scale();
    room = w * 0.96f / 760.0f;           /* 700-unit box + padding inside 96% of the width */
    if (s > room) s = room;
    if (s > h / 300.0f) s = h / 300.0f;  /* never more than a quarter of the height for the 75-unit box */
    if (s < 1.0f) s = 1.0f;              /* 100% (or no room for more) = exactly the original size */
    if (logged < 12 && s != last_s) {
        logged++; last_s = s;
        xrt_log("port: subtitles drawn at x%.3f (setting x%.2f) in the %.0fx%.0f UI frame", s, xrt_port_subtitle_scale(), w, h);
    }
    wrf32(self + REL_X, w / s); wrf32(self + REL_Y, h / s);
#ifdef XRT_RV_ABI
    rv = f_1917f270_translated(c);
#else
    f_1917f270_translated(c);
#endif
    wrf32(self + REL_X, MARK_X); wrf32(self + REL_Y, MARK_Y);
#ifdef XRT_RV_ABI
    return rv;
#endif
}

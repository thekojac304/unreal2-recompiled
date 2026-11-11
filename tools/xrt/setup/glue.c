/* glue.c - the entry the player uses to find the translated modules in UnrealII-game.dll (built by u2gen on the
 * player's machine). Same list and order as the runtime's static list (xrt_main.c lifted_all). Written for this
 * project; contains no game code. */
#include "xrt.h"

int _fltused = 0x9875;   /* the C runtime's marker that floating point is used; this DLL links no C runtime */

extern const XrtLiftedModule xrt_mod_UCC, xrt_mod_Core, xrt_mod_Engine, xrt_mod_GlmLib, xrt_mod_Editor, xrt_mod_Window,
    xrt_mod_UnrImp, xrt_mod_Fire, xrt_mod_Unreal2, xrt_mod_WinDrv, xrt_mod_D3DDrv, xrt_mod_ParticleSystems, xrt_mod_Legend,
    xrt_mod_UI, xrt_mod_U2, xrt_mod_U2Dialog, xrt_mod_U2AI, xrt_mod_vorbisfile, xrt_mod_ogg, xrt_mod_vorbis, xrt_mod_ALAudio;

static const XrtLiftedModule* const modules[] = {
    &xrt_mod_UCC, &xrt_mod_Core, &xrt_mod_Engine, &xrt_mod_GlmLib, &xrt_mod_Editor, &xrt_mod_Window, &xrt_mod_UnrImp,
    &xrt_mod_Fire, &xrt_mod_Unreal2, &xrt_mod_WinDrv, &xrt_mod_D3DDrv, &xrt_mod_ParticleSystems, &xrt_mod_Legend,
    &xrt_mod_UI, &xrt_mod_U2, &xrt_mod_U2Dialog, &xrt_mod_U2AI, &xrt_mod_vorbisfile, &xrt_mod_ogg, &xrt_mod_vorbis,
    &xrt_mod_ALAudio};

/* the translated SSE2 pow core of msvcr70.dll (gen/msvcr70/pow_sse2.c) and the identity of the DLL it was made from */
extern const char xrt_msvcr70_pow_sse2_sha256[];
__declspec(dllexport) const char* xrt_game_pow_sha256(void) { return xrt_msvcr70_pow_sse2_sha256; }
/* xrt_msvcr70_pow_sse2 itself (defined in pow_sse2.c) is exported by u2gen's link (/EXPORT) */

#define XRT_GAME_INTERFACE 1   /* the player refuses a DLL of another interface version */
__declspec(dllexport) int xrt_game_interface(void) { return XRT_GAME_INTERFACE; }
__declspec(dllexport) const XrtLiftedModule* const* xrt_game_modules(int* count) {
    *count = (int)(sizeof modules / sizeof modules[0]);
    return modules;
}

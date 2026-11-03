/* view_fov.c - port settings "Field of View" and Hor+ widescreen (always linked: dev.py PORT). Wraps the translated
 * Engine.dll function f_103f8a40, the virtual  void FCameraSceneNode::UpdateMatrices()  (thiscall, no arguments),
 * which builds the node's view and projection matrices and from them every derived matrix and frustum the renderer
 * and the visibility code use. This is a reconstruction of game code (like the translated units): keep it out of
 * redistribution.
 *
 * The engine's projection is FPerspectiveMatrix(FOV/2, SizeX, SizeY, ...): FOV (node +0x1e8, degrees) is the
 * HORIZONTAL angle whatever the viewport's shape, so a screen wider than the game's 4:3 shows LESS vertically
 * ("Vert-": at 16:9 the top and bottom of the 4:3 picture are cut away, at 32:9 more than half of it).
 *
 * Hor+: for the player's view (FPlayerSceneNode, the main 3D view) and for Canvas.DrawActor (FActorSceneNode: the
 * first-person weapon), the engine's FOV F is taken as the horizontal angle of a 4:3 view and, on a viewport of
 * aspect A > 4/3, widened to  2*atan(tan(F/2) * A * 3/4)  for this one call, so the vertical angle stays the 4:3
 * one and the extra width shows more of the world at the sides. F is restored right after; the matrices (and the
 * frustum culling built from them in the same call) carry the widened angle. Nothing else changes: the game's own
 * FovAngle (zoom, scripted camera FOV, cinematic USubActionFOV, mouse-sensitivity scaling) keeps its 4:3 meaning,
 * the weapon keeps the vertical framing and size it has at 4:3, orthographic map views (RendMap 13-15) and every
 * other scene node (shadow projectors, light maps, mirrors/sky inherit the parent's matrices) are left alone.
 * Viewports narrower than 4:3 are not changed.
 *
 * Default 85 (the game's class default; enhanced batch): the shipped/GOG User.ini sets DefaultFOV=100, a widescreen
 * compensation for the Vert- projection (100 deg across 16:9 = 67.7 deg vertical, about the original 85 at 4:3). Kept
 * under Hor+ it would show 83.6 deg vertically; 85 under Hor+ gives 101.4 x 69.0 deg at 16:9, the original framing.
 * The game scales mouse turning with the FOV (PlayerInput FOVScale = DesiredFOV/90), so 85 turns ~15% slower than 100.
 * Field of View (User.ini [U2Port.PortSettings] FieldOfView, 75..120, horizontal degrees at 4:3; 0 = the game's own):
 * the player's configured FOV is the game's own PlayerController.DefaultFOV (+0x6e0; DesiredFOV +0x6dc; class default
 * 85, DefUser.ini 90). When the setting is on, every player-view update keeps DefaultFOV at the setting, and moves
 * DesiredFOV with it when the player is not zoomed (DesiredFOV == old DefaultFOV): the game's AdjustView then brings
 * FovAngle there. Re-applied on every frame, so a loaded save or a new level (which restore the saved controller's
 * DefaultFOV) cannot reset it; zoom (DesiredFOV below DefaultFOV) and scripted FovAngle changes keep working. */
#include <math.h>
#include "xrt_internal.h"

XrtLiftedRet f_103f8a40_translated(CPU* c);   /* xrt.h: returns its return address under XRT_RV_ABI */

/* Which node: the derived vtable is installed only AFTER FCameraSceneNode's constructor, and that constructor already
 * calls UpdateMatrices (return address CTOR_RET): there the node still has the base vtable, so the derived constructor
 * is found on the guest stack instead. The base constructor's frame is fixed (push ebp; 3 pushes; sub esp,0x18;
 * 3 register pushes; every callee before this call is ret-N), so its own return address is at entry esp + 0x38:
 * FPlayerSceneNode's constructor returns to PLAYER_CTOR_RET, FActorSceneNode's to ACTOR_CTOR_RET. Other users of a
 * plain FCameraSceneNode are left alone. */
enum { VT_CAMERA_NODE = 0x207668, CTOR_RET = 0xfa498, PLAYER_CTOR_RET = 0xfa52b, ACTOR_CTOR_RET = 0xfa58b };
enum { VT_PLAYER_NODE = 0x2076a0, VT_ACTOR_NODE = 0x2076d8,                     /* Engine.dll RVAs */
       NODE_VIEWPORT = 0x4, NODE_FOV = 0x1e8,
       VIEWPORT_ACTOR = 0x30, VIEWPORT_SIZE_X = 0x74, VIEWPORT_SIZE_Y = 0x78,
       PC_RENDMAP = 0x6cc, PC_DESIRED_FOV = 0x6dc, PC_DEFAULT_FOV = 0x6e0 };

static unsigned logged_widen[2], logged_fov;   /* [0] weapon/actor nodes, [1] the player's view */

static void keep_player_fov(uint32_t pc) {
    int want = xrt_port_field_of_view();
    float def, desired;
    if (!want || !pc) return;
    def = rdf32(pc + PC_DEFAULT_FOV);
    if (fabsf(def - (float)want) < 0.01f) return;
    desired = rdf32(pc + PC_DESIRED_FOV);
    wrf32(pc + PC_DEFAULT_FOV, (float)want);
    if (fabsf(desired - def) < 0.01f) wrf32(pc + PC_DESIRED_FOV, (float)want);
    if (logged_fov++ < 16)
        xrt_log("port: player FOV setting %d applied (DefaultFOV was %.1f, DesiredFOV %.1f%s)", want, def, desired,
                fabsf(desired - def) < 0.01f ? " -> follows" : ", zoomed: kept");
}

XrtLiftedRet f_103f8a40(CPU* c) {
    static XrtModule* engine;
    uint32_t node = c->r[ECX], esp = c->r[ESP], vt, viewport, pc, w, h, rendmap;
    int player;
    float fov, wide;
    double aspect;
#ifdef XRT_RV_ABI
    uint32_t rv;
#endif
    if (!engine) engine = xrt_module_by_name("Engine.dll");
    if (!engine) { XRT_TAIL(f_103f8a40_translated(c)); }
    vt = rd32(node) - engine->base;
    if (vt == VT_CAMERA_NODE && rd32(esp) == engine->base + CTOR_RET) {
        uint32_t derived = rd32(esp + 0x38) - engine->base;
        vt = derived == PLAYER_CTOR_RET ? VT_PLAYER_NODE : derived == ACTOR_CTOR_RET ? VT_ACTOR_NODE : vt;
    }
    if ((vt != VT_PLAYER_NODE && vt != VT_ACTOR_NODE) || !(viewport = rd32(node + NODE_VIEWPORT))) {
        XRT_TAIL(f_103f8a40_translated(c));
    }
    player = vt == VT_PLAYER_NODE;
    pc = rd32(viewport + VIEWPORT_ACTOR);
    if (player) keep_player_fov(pc);
    w = rd32(viewport + VIEWPORT_SIZE_X); h = rd32(viewport + VIEWPORT_SIZE_Y);
    rendmap = pc ? rd32(pc + PC_RENDMAP) : 0;
    fov = rdf32(node + NODE_FOV);
    aspect = h ? (double)w / h : 0.0;
    if (!xrt_port_hor_plus() || !w || !h || aspect <= 4.0 / 3.0 + 1e-4 || (rendmap >= 13 && rendmap <= 15) ||
        !(fov > 0.5f && fov < 170.0f)) {
        XRT_TAIL(f_103f8a40_translated(c));
    }
    /* half angle in radians -> widened half angle -> full angle in degrees (atan * 360/pi = 2 * atan in degrees) */
    wide = (float)(atan(tan(fov * (3.14159265358979 / 360.0)) * aspect * 0.75) * (360.0 / 3.14159265358979));
    if (wide > 170.0f) wide = 170.0f;
    if (logged_widen[player] < 24) {
        static float last_fov[2], last_wide[2];
        if (fov != last_fov[player] || wide != last_wide[player]) {
            logged_widen[player]++; last_fov[player] = fov; last_wide[player] = wide;
            xrt_log("port: Hor+ %s FOV %.2f -> %.2f deg horizontal on %ux%u (aspect %.3f, vertical %.2f deg as at 4:3)",
                    player ? "view" : "weapon", fov, wide, w, h, aspect,
                    atan(tan(fov * (3.14159265358979 / 360.0)) * 0.75) * (360.0 / 3.14159265358979));
        }
    }
    wrf32(node + NODE_FOV, wide);
#ifdef XRT_RV_ABI
    rv = f_103f8a40_translated(c);
#else
    f_103f8a40_translated(c);
#endif
    if (rdf32(node + NODE_FOV) == wide) wrf32(node + NODE_FOV, fov);   /* unless the call itself stored a new FOV */
#ifdef XRT_RV_ABI
    return rv;
#endif
}

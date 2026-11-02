/* walk_speed.c - port setting "Walking Speed" (always linked: dev.py PORT). Wraps the translated Engine.dll function
 * f_103e24d0, the thiscall  void APawn::calcVelocity(FVector AccelDir, float DeltaTime, float MaxSpeed, float Friction,
 * int bFluid, int bBrake, int bBuoyant)  (ret 0x24). This is a reconstruction of game code (like the translated
 * units): keep it out of redistribution.
 *
 * Applied only when all hold: the factor k (runtime port_settings.c, User.ini [U2Port.PortSettings] WalkingSpeed) is
 * not 1; the caller is APawn::physWalking (return address Engine.dll+0xe61da: walking and running on the ground - not
 * falling/jumping, swimming, flying, ladders or spider physics); and the pawn's Controller is a PlayerController
 * (APawn::IsHumanControlled: +0x3a0 Controller, UObject::IsA over +0x24 Class / +0x28 SuperField). NPCs, enemies,
 * scripted (non-player) controllers and every other physics mode are unchanged.
 *
 * calcVelocity is linear in its speed inputs: Velocity' = Velocity - (Velocity - AccelDir*|Velocity|)*Friction*dt
 * + Acceleration*dt*(...), with Acceleration clamped to AccelRate (+0x470, times +0x47c) and |Velocity'| clamped to
 * MaxSpeed (times +0x47c). For the one call, MaxSpeed, AccelRate and the pawn's Acceleration (+0x148) are scaled by
 * k, so the walking velocity (and the time to reach it) scales by exactly k. Afterwards AccelRate is restored and
 * Acceleration returns to the unscaled value (calcVelocity's own clamp result divided by k when it changed it).
 * Nothing is stored in the pawn: a respawned pawn, a loaded save or scripts that set GroundSpeed never compound
 * the factor. The move itself stays the engine's swept, collision-checked physWalking step (no tunnelling: the
 * engine already sub-steps the move and traces it against the world; triggers fire from the same touches). */
#include "xrt_internal.h"

XrtLiftedRet f_103e24d0_translated(CPU* c);   /* xrt.h: returns its return address under XRT_RV_ABI */

enum { PHYS_WALKING_RETURN = 0xe61da, PLAYER_CONTROLLER_CLASS = 0x332148,   /* Engine.dll RVAs */
       PAWN_CONTROLLER = 0x3a0, PAWN_ACCELERATION = 0x148, PAWN_ACCEL_RATE = 0x470,
       OBJECT_CLASS = 0x24, STRUCT_SUPER = 0x28 };

static int human_controlled(uint32_t engine, uint32_t pawn) {
    uint32_t controller = rd32(pawn + PAWN_CONTROLLER), cls, depth;
    if (!controller) return 0;
    for (cls = rd32(controller + OBJECT_CLASS), depth = 0; cls && depth < 64; cls = rd32(cls + STRUCT_SUPER), depth++)
        if (cls == engine + PLAYER_CONTROLLER_CLASS) return 1;
    return 0;
}

XrtLiftedRet f_103e24d0(CPU* c) {
    static XrtModule* engine;
    uint32_t esp = c->r[ESP], pawn = c->r[ECX], acc = pawn + PAWN_ACCELERATION, i;
    float k = xrt_port_walking_speed(), a[3], scaled[3], rate;
#ifdef XRT_RV_ABI
    uint32_t rv;
#endif
    if (!engine) engine = xrt_module_by_name("Engine.dll");
    if (k == 1.0f || !engine || rd32(esp) != engine->base + PHYS_WALKING_RETURN || !human_controlled(engine->base, pawn)) {
        XRT_TAIL(f_103e24d0_translated(c));
    }
    rate = rdf32(pawn + PAWN_ACCEL_RATE);
    for (i = 0; i < 3; i++) { a[i] = rdf32(acc + 4 * i); scaled[i] = a[i] * k; wrf32(acc + 4 * i, scaled[i]); }
    wrf32(esp + 0x14, rdf32(esp + 0x14) * k);      /* MaxSpeed (callee-owned argument slot) */
    wrf32(pawn + PAWN_ACCEL_RATE, rate * k);
#ifdef XRT_RV_ABI
    rv = f_103e24d0_translated(c);
#else
    f_103e24d0_translated(c);
#endif
    wrf32(pawn + PAWN_ACCEL_RATE, rate);
    for (i = 0; i < 3; i++) {
        float now = rdf32(acc + 4 * i);
        wrf32(acc + 4 * i, now == scaled[i] ? a[i] : now / k);
    }
#ifdef XRT_RV_ABI
    return rv;
#endif
}

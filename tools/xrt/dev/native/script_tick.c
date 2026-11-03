/* script_tick.c - high-frame-rate correctness: a tick-rate ceiling for the script Tick events of the few actor classes
 * whose UnrealScript Tick is frame-rate dependent (always linked: dev.py PORT). Wraps the translated Core.dll function
 * f_10125320, the virtual  void UObject::ProcessEvent(UFunction* Function, void* Parms, void* Result)  (thiscall,
 * ret 0xc), through which AActor::Tick delivers the script event Tick(float DeltaTime) (class or state function).
 * This is a reconstruction of game code: keep it out of redistribution.
 *
 * The engine itself is time based (level_tick.c), and so is almost all script code; the audit of every script Tick
 * (out/dev-init/enhanced/grep/tick, ENHANCED_REPORT) found these classes doing per-tick work that does not scale with
 * DeltaTime, so their behaviour drifts with the frame rate:
 *   U2DrakkMedium            limb attacks: Max(int(Rate*DeltaTime), 1) damage per tick -> damage per second grows
 *                            with FPS above ~100 FPS (144 dps from every limb at 144 FPS, 500 at 500)
 *   U2DrakkLight             charge-up: GroundSpeed = Lerp(ChargeLevel, GroundSpeed, 0) each tick -> the drone
 *                            stops dead at high FPS (distance covered while charging 0.24x at 30 FPS, 0.08x at 500)
 *   projectileBlackHole      pain ring: int(DamagePerSecond*DeltaTime) per tick -> 0 damage above 300 FPS
 *   U2KillerSproutController grab/digest damage only when Rate*DeltaTime >= 1 in one tick
 *   RubbleChunk              FRand() < 0.1 per tick spawns a bubble -> bubble rate (and actor spawns) grow with FPS
 *   Fader                    flicker toggles every tick -> invisible at high FPS
 * For actors of these classes (and their subclasses) the Tick event is delivered at most ScriptTickRate times per
 * second of game time (User.ini [U2Port.PortSettings] ScriptTickRate, default 60; 0 = off): a frame's DeltaTime
 * accumulates per actor and the event runs with the accumulated time once at least 1/ScriptTickRate has passed. At
 * or below that frame rate every event is delivered unchanged (the original behaviour); above it these actors behave
 * as at 60 FPS. Native physics, animation and every other event of these actors still run every frame, and no other
 * class is touched. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <wchar.h>
#include "xrt_internal.h"

XrtLiftedRet f_10125320_translated(CPU* c);

enum { OBJ_NAME = 0x20, OBJ_CLASS = 0x24, STRUCT_SUPER = 0x28, NAMES_RVA = 0x175e18, NAME_TEXT = 0xc };
static const wchar_t* const limited[] = { L"U2DrakkMedium", L"U2DrakkLight", L"projectileBlackHole",
                                          L"U2KillerSproutController", L"RubbleChunk", L"Fader" };
/* Developer test only (none of the classes above appears in the test checkpoints): XRT_DEV_TICK_EXTRA=ClassName adds
 * one more class (and its subclasses) to the ceiling, so the mechanism can be exercised and measured in game. */
static wchar_t extra[64];
static int extra_read;
static unsigned long long delivered, deferred, next_report;
static XrtModule* core;
static int32_t tick_name = -1;
static unsigned name_scans;

static const uint16_t* name_text(int32_t index) {
    uint32_t names = core->base + NAMES_RVA, data = rd32(names), count = rd32(names + 4), entry;
    if (index < 0 || (uint32_t)index >= count || !(entry = rd32(data + 4u * (uint32_t)index))) return NULL;
    return (const uint16_t*)G2H(entry + NAME_TEXT);
}
static int name_is(const uint16_t* s, const wchar_t* want) {
    if (!s) return 0;
    while (*want && *s && towlower(*s) == towlower(*want)) { s++; want++; }
    return !*want && !*s;
}
static void find_tick_name(void) {
    uint32_t names = core->base + NAMES_RVA, count = rd32(names + 4), i;
    for (i = 0; i < count; i++) if (name_is(name_text((int32_t)i), L"Tick")) { tick_name = (int32_t)i; break; }
    xrt_log("port: script tick ceiling: FName Tick %s (index %d of %u names)", tick_name >= 0 ? "found" : "NOT found yet", tick_name, count);
}
/* class -> limited? (the class chain's names), cached with the class name so a reused address is re-checked */
static struct { uint32_t cls; int32_t name; int limited; } class_cache[512];
static int class_limited(uint32_t cls) {
    unsigned slot = (cls >> 3) & 511, depth;
    int32_t name = (int32_t)rd32(cls + OBJ_NAME);
    uint32_t k;
    if (class_cache[slot].cls == cls && class_cache[slot].name == name) return class_cache[slot].limited;
    class_cache[slot].cls = cls; class_cache[slot].name = name; class_cache[slot].limited = 0;
    if (!extra_read) {
        const char* v = getenv("XRT_DEV_TICK_EXTRA");
        extra_read = 1;
        if (v && *v) { mbstowcs(extra, v, 63); xrt_log("port: script tick ceiling: developer test class %ls added", extra); }
    }
    for (k = cls, depth = 0; k && depth < 32; k = rd32(k + STRUCT_SUPER), depth++) {
        unsigned i;
        const uint16_t* s = name_text((int32_t)rd32(k + OBJ_NAME));
        for (i = 0; i <= sizeof limited / sizeof *limited; i++)
            if (i < sizeof limited / sizeof *limited ? name_is(s, limited[i]) : extra[0] && name_is(s, extra)) {
                const uint16_t* own = name_text(name);
                class_cache[slot].limited = 1;
                xrt_log("port: script Tick of class %ls (%ls) limited to %d Hz", own ? (const wchar_t*)own : L"?",
                        i < sizeof limited / sizeof *limited ? limited[i] : extra, xrt_port_script_tick_rate());
                return 1;
            }
    }
    return 0;
}
/* per actor: accumulated game time not yet delivered */
static struct { uint32_t obj, cls; float acc; } actors[2048];

XrtLiftedRet f_10125320(CPU* c) {
    uint32_t esp = c->r[ESP], obj = c->r[ECX], fn = rd32(esp + 4), parms = rd32(esp + 8), cls;
    int rate;
    if (!fn || !parms) { XRT_TAIL(f_10125320_translated(c)); }
    if (tick_name < 0) {
        if (!core) core = xrt_module_by_name("Core.dll");
        if (!core || (name_scans++ & 1023)) { XRT_TAIL(f_10125320_translated(c)); }
        find_tick_name();
        if (tick_name < 0) { XRT_TAIL(f_10125320_translated(c)); }
    }
    if ((int32_t)rd32(fn + OBJ_NAME) != tick_name || !(rate = xrt_port_script_tick_rate()) ||
        !(cls = rd32(obj + OBJ_CLASS)) || !class_limited(cls)) {
        XRT_TAIL(f_10125320_translated(c));
    }
    {
        unsigned slot = (obj >> 3) & 2047, i, free_slot = 2048;
        float dt = rdf32(parms), total;
        for (i = 0; i < 8; i++) {
            unsigned s = (slot + i) & 2047;
            if (actors[s].obj == obj) { slot = s; break; }
            if (!actors[s].obj && free_slot == 2048) free_slot = s;
        }
        if (i == 8) {   /* first event of this actor (or table crowded): start its account */
            slot = free_slot < 2048 ? free_slot : slot;
            actors[slot].obj = obj; actors[slot].cls = cls; actors[slot].acc = 0.0f;
        } else if (actors[slot].cls != cls) { actors[slot].cls = cls; actors[slot].acc = 0.0f; }   /* address reused */
        total = actors[slot].acc + dt;
        {
            unsigned long long now = GetTickCount64();
            if (now >= next_report) {
                if (next_report)
                    xrt_log("port: script tick ceiling: %llu Tick events delivered, %llu deferred (accumulated) so far",
                            delivered, deferred);
                next_report = now + 20000;
            }
        }
        if (total < 1.0f / (float)rate - 1e-5f) {
            uint32_t ra;
            deferred++;
            actors[slot].acc = total;           /* not delivered this frame: return as the event would (ret 0xc) */
            ra = pop32(c); c->r[ESP] += 12;
#ifdef XRT_RV_ABI
            return ra;
#else
            c->rv = ra; return;
#endif
        }
        actors[slot].acc = 0.0f;
        delivered++;
        wrf32(parms, total);
    }
    XRT_TAIL(f_10125320_translated(c));
}

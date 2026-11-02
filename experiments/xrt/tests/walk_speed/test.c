/* walk_speed - focused test of tools/xrt/dev/native/walk_speed.c (the Walking Speed wrapper of APawn::calcVelocity).
 * Compiles the wrapper against owned stubs: f_103e24d0_translated is a model of calcVelocity with the same inputs,
 * outputs and calling convention (thiscall, ret 0x24): it clamps Acceleration to AccelRate*Factor and writes it back,
 * adds Acceleration*dt to Velocity and clamps |Velocity| to MaxSpeed*Factor. Guest memory is a small committed block.
 *
 *   identity   k = 1: the translated function runs unchanged (bit-identical velocity, acceleration, stack)
 *   scaled     k = 1.5 / 2.0 / 0.75, physWalking caller, PlayerController pawn: the velocity after 40 steps from rest
 *              (and every intermediate step) is k times the original; AccelRate, Acceleration and the stack are restored
 *   clamp      Acceleration above AccelRate: the wrapper hands back calcVelocity's own clamp result, unscaled
 *   scope      other callers (swimming/flying/ladder return addresses), an NPC controller class chain, no controller:
 *              unchanged at k = 2
 *   compound   1000 calls leave AccelRate exactly as before (nothing accumulates in the pawn)
 * Exit 0 when every check passes. Build/run: experiments/xrt/tests/walk_speed/run.cmd */
#include <windows.h>
#include <math.h>
#include <stdio.h>
#include "xrt_internal.h"

uint8_t* xrt_g;
static float k_setting = 1.0f;
static XrtModule engine_module = {"Engine.dll"};
float xrt_port_walking_speed(void) { return k_setting; }
XrtModule* xrt_module_by_name(const char* name) { return strcmp(name, "Engine.dll") ? NULL : &engine_module; }
static unsigned translated_calls;

enum { VEL = 0x13c, ACC = 0x148, RATE = 0x470, FACTOR = 0x47c };
/* Model of calcVelocity: same argument layout and the same uses of the pawn fields. */
void f_103e24d0_translated(CPU* c) {
    uint32_t esp = c->r[ESP], p = c->r[ECX], i;
    float dt = rdf32(esp + 0x10), max = rdf32(esp + 0x14), f = rdf32(p + FACTOR), rate = rdf32(p + RATE), a[3], v[3], n;
    translated_calls++;
    for (i = 0; i < 3; i++) { a[i] = rdf32(p + ACC + 4 * i); v[i] = rdf32(p + VEL + 4 * i); }
    n = sqrtf(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    if (n > rate * f) for (i = 0; i < 3; i++) { a[i] = a[i] / n * rate * f; wrf32(p + ACC + 4 * i, a[i]); }
    for (i = 0; i < 3; i++) v[i] += a[i] * dt;
    n = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (n > max * f) for (i = 0; i < 3; i++) v[i] = v[i] / n * max * f;
    for (i = 0; i < 3; i++) wrf32(p + VEL + 4 * i, v[i]);
    c->rv = pop32(c); c->r[ESP] += 0x24;
}
#include "../../../../tools/xrt/dev/native/walk_speed.c"

static int failures;
#define CHECK(cond, ...) do { int ok_ = !!(cond); printf(ok_ ? "ok   " : "FAIL "); printf(__VA_ARGS__); printf("\n"); if (!ok_) failures++; } while (0)

enum { BASE = 0x10000, BLOCK = 0x10000, PAWN = 0x11000, CTRL = 0x12000, NPC_CLASS = 0x13000, SUPER = 0x13100,
       STACK = 0x1f000 };
#define ENGINE 0x10300000u
static void pawn_reset(uint32_t controller, uint32_t cls) {
    memset(xrt_g + PAWN, 0, 0x500);
    wrf32(PAWN + ACC, 2048.0f); wrf32(PAWN + RATE, 2048.0f); wrf32(PAWN + FACTOR, 1.0f);
    wr32(PAWN + 0x3a0, controller);
    if (controller) wr32(controller + 0x24, cls);
}
static float call(CPU* c, uint32_t ret, float max) {
    uint32_t esp = STACK;
    c->r[ECX] = PAWN; c->r[ESP] = esp;
    wr32(esp, ret); wrf32(esp + 4, 1); wrf32(esp + 8, 0); wrf32(esp + 12, 0);
    wrf32(esp + 0x10, 1.0f / 60); wrf32(esp + 0x14, max); wrf32(esp + 0x18, 8); wr32(esp + 0x1c, 0); wr32(esp + 0x20, 1); wr32(esp + 0x24, 0);
    f_103e24d0(c);
    return rdf32(PAWN + VEL);
}
static int restored(CPU* c, uint32_t ret) {
    return c->r[ESP] == STACK + 0x28 && c->rv == ret && rdf32(PAWN + RATE) == 2048.0f;
}

int main(void) {
    CPU cpu = {0}; CPU* c = &cpu; float base[40], v; int i, ok, step;
    const uint32_t walk = ENGINE + 0xe61da, swim = ENGINE + 0xe7000;
    const float ks[3] = {1.5f, 2.0f, 0.75f};
    xrt_g = (uint8_t*)VirtualAlloc(NULL, BASE + BLOCK, MEM_RESERVE, PAGE_NOACCESS);
    VirtualAlloc(xrt_g + BASE, BLOCK, MEM_COMMIT, PAGE_READWRITE);
    engine_module.base = ENGINE;
    /* player: controller class chain -> PlayerController */
    wr32(SUPER + 0x28, ENGINE + 0x332148);
    /* identity */
    k_setting = 1.0f; pawn_reset(CTRL, SUPER);
    for (i = 0; i < 40; i++) base[i] = call(c, walk, 440.0f);
    CHECK(base[39] == 440.0f && translated_calls == 40, "identity: original reaches GroundSpeed 440 (%g)", base[39]);
    for (step = 0; step < 3; step++) {
        float k = ks[step];
        k_setting = k; pawn_reset(CTRL, SUPER); ok = 1;
        for (i = 0; i < 40; i++) {
            v = call(c, walk, 440.0f);
            if (fabsf(v - base[i] * k) > 1e-3f * k * 440.0f || !restored(c, walk) || rdf32(PAWN + ACC) != 2048.0f) ok = 0;
        }
        CHECK(ok, "scaled %g%%: velocity %g = %g x original at every step, AccelRate/Acceleration/stack restored", k * 100, v, k);
    }
    /* clamp: acceleration above AccelRate is clamped by calcVelocity itself; the unscaled clamp result comes back */
    k_setting = 1.5f; pawn_reset(CTRL, SUPER); wrf32(PAWN + ACC, 4096.0f);
    call(c, walk, 440.0f);
    CHECK(fabsf(rdf32(PAWN + ACC) - 2048.0f) <= 2048.0f * 1e-6f, "clamp: Acceleration back as the unscaled clamp result (%g)", rdf32(PAWN + ACC));
    /* scope */
    k_setting = 2.0f; pawn_reset(CTRL, SUPER);
    for (i = 0; i < 40; i++) v = call(c, swim, 440.0f);
    CHECK(v == base[39] && restored(c, swim), "scope: other physics caller unchanged at 200%% (%g)", v);
    wr32(NPC_CLASS + 0x28, 0); pawn_reset(CTRL, NPC_CLASS);
    for (i = 0; i < 40; i++) v = call(c, walk, 440.0f);
    CHECK(v == base[39], "scope: NPC controller unchanged at 200%% (%g)", v);
    pawn_reset(0, 0);
    for (i = 0; i < 40; i++) v = call(c, walk, 440.0f);
    CHECK(v == base[39], "scope: no controller unchanged at 200%% (%g)", v);
    /* compounding */
    pawn_reset(CTRL, SUPER);
    for (i = 0; i < 1000; i++) call(c, walk, 440.0f);
    CHECK(rdf32(PAWN + RATE) == 2048.0f && rdf32(PAWN + VEL) == 880.0f, "compound: 1000 calls, AccelRate exact, speed 880 = 2 x 440 (%g)",
          rdf32(PAWN + VEL));
    printf("%s (%d failure%s)\n", failures ? "FAIL" : "PASS", failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}

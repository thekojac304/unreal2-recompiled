/* level_tick.c - frame timing probe for the high-frame-rate measurements (always linked: dev.py PORT; read-only).
 * Wraps the translated Engine.dll function f_103b5be0, the virtual  void ULevel::Tick(ELevelTick TickType, FLOAT
 * DeltaSeconds)  (thiscall, ret 8). This is a reconstruction of game code: keep it out of redistribution.
 *
 * What the engine does with the frame time (disassembly of this function): DeltaSeconds (the main loop's wall-clock
 * frame time) is multiplied by LevelInfo.TimeDilation; unless the level is paused the double at ULevel +0xd0 (the
 * level's TimeSeconds, copied to LevelInfo.TimeSeconds) advances by that amount; then the DeltaTime every actor ticks
 * with is clamped to [0.001 * TimeDilation, 0.4] s. So game time follows the wall clock between 2.5 and 1000 frames
 * per second; above 1000 FPS actors would be simulated faster than real time (the frame limiter keeps a 1 ms floor,
 * dev_support.c), below 2.5 FPS slower.
 *
 * Recorded per call (the last call of a frame wins; dev_support.c writes them into frames.csv): the incoming frame
 * time, the level's time after the tick and the level pointer. Nothing in the game is changed. */
#include "xrt_internal.h"

XrtLiftedRet f_103b5be0_translated(CPU* c);

volatile double xrt_probe_level_time;
volatile float xrt_probe_frame_dt;
volatile uint32_t xrt_probe_level, xrt_probe_level_ticks;

XrtLiftedRet f_103b5be0(CPU* c) {
    uint32_t level = c->r[ECX];
    float dt = rdf32(c->r[ESP] + 8);
#ifdef XRT_RV_ABI
    uint32_t rv = f_103b5be0_translated(c);
#else
    f_103b5be0_translated(c);
#endif
    xrt_probe_frame_dt = dt;
    xrt_probe_level_time = rdf64(level + 0xd0);
    xrt_probe_level = level;
    xrt_probe_level_ticks++;
#ifdef XRT_RV_ABI
    return rv;
#endif
}

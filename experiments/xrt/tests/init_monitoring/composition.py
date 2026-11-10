"""Fail-closed staged composition. No launch/authorization/policy mutation API.

This preserves the retained semantic observer's detailed operation handlers.
It is NOT a complete genuine-Init observer: coverage.py records missing domains,
and genuine construction cannot continue past CREATE_PROCESS until they qualify.
"""
import ast
import ctypes as C
import struct
from types import MethodType
from common import *
from supervisor.windows import Context

semantic = load('init_monitoring_semantic', H.parent / 'semantic_compat/observer.py')
# Reuse the exact paired Init checks, without importing the endpoint-only
# install() or its breakpoint replacement. Preserve the source identity.
pair_source = H.parent / 'integrated_candidate/continuation.py'
pair_node = next(n for n in ast.parse(pair_source.read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name == 'verify_pair')
exec(compile(ast.Module(body=[pair_node], type_ignores=[]), str(pair_source), 'exec'))

def schedule(capture, plan):
    points = dict(capture.breakpoints)
    hard = capture.base + plan['stop_rva']
    if callable(getattr(capture,'log',None)):
        capture.log('monitor_schedule_proposal',points={hex(a):t for a,t in points.items()},endpoint=hard)
    core.require(hard not in points or points[hard] == 'init_return', 'endpoint collision')
    points[hard] = 'init_return'
    core.require(points.get(capture.sym('xrt_fatal')) == 'fatal_entry', 'fatal monitoring absent')
    core.require(len(points) <= 4, 'monitoring requires more than four hardware slots')
    return points

def arm_all(capture, ctx, plan, resume=False):
    """Debug events suspend all threads. Publish one schedule to EVERY live thread.

    RF is set only for the triggering thread. No code/data patch or software BP.
    A failed readback prevents ContinueDebugEvent through retained BoundedLoop.
    """
    points = schedule(capture, plan)
    capture.breakpoints = points
    capture.monitor_generation += 1
    addresses = list(points)
    capture.log('monitor_schedule', generation=capture.monitor_generation,
                points={hex(a): t for a, t in points.items()},
                threads=list(capture.threads), endpoint=hex(capture.base + plan['stop_rva']))
    for tid, (handle, _) in capture.threads.items():
        current = ctx if int(handle) == int(ctx.thread) else Context(handle)
        try:
            current.arm(addresses, resume and int(handle) == int(ctx.thread))
        except BaseException as error:
            # Context.arm has its own mandatory readback assertion. Preserve
            # the actual stopped context on that failure before propagating it.
            capture.log('monitor_arm_failure',tid=tid,expected=addresses,error=str(error))
            actual=Context(handle)
            capture.log('monitor_arm_failure_raw',tid=tid,host=actual.snapshot(),
                dr=[C.c_uint64.from_address(actual.ptr+72+8*i).value for i in range(4)],
                dr7=C.c_uint64.from_address(actual.ptr+112).value)
            raise
        actual = Context(handle)
        dr = [C.c_uint64.from_address(actual.ptr + 72 + 8*i).value for i in range(4)]
        dr7 = C.c_uint64.from_address(actual.ptr + 112).value
        capture.log('monitor_readback', generation=capture.monitor_generation, tid=tid,
                    thread_handle=int(handle), dr=dr, dr7=dr7, expected=addresses,
                    host=actual.snapshot())
        core.require(dr == addresses + [0]*(4-len(addresses)) and
                     dr7 & 0xffff00ff == sum(1 << (2*i) for i in range(len(addresses))),
                     'all-thread hardware readback')

def install(capture, plan, check_environment, *, owned_fixture=False):
    core.require(capture.base == 0 and not capture.breakpoints, 'unexecuted observer required')
    detailed_hit = capture.hit
    retained_log = capture.log
    def strict_log(self, kind, **fields):
        retained_log(kind, **fields)
        # This preparation does not grant a functional-development exception.
        # Preserve the complete difference before refusing to resume; do not
        # inherit the older observer's broad record-and-continue status policy.
        if kind == 'strict_differential':
            raise core.Rejected('strict state discrepancy; no scoped execution policy authorized')
    capture.log = MethodType(strict_log, capture)
    capture.init_entry = None
    # Retained idle() uses this as a schedule flag. We never dispatch its SetRes
    # entry/endpoint handlers and do not claim a SetRes observation or return.
    capture.setres_entry = dict(schedule_only=True, setres_observed=False)
    capture.monitor_generation = 0
    capture.monitor_counts = {}
    capture.monitor_owner = None
    capture.out = Path(capture.out)

    def idle(self):
        self.breakpoints = {self.sym('xrt_fatal'): 'fatal_entry',
                            self.sym('d8_semantic_checkpoint'): 'semantic_checkpoint',
                            self.sym('invoke_gui_proc'): 'semantic_callback'}

    def on_create(self, ev):
        self.log('monitor_coverage_gate', owned_fixture=owned_fixture,
                 genuine_interval_qualified=False, missing=read(O/'coverage.json')['blocking_requirements'])
        # No future caller can mistake successful construction for launch readiness.
        core.require(owned_fixture, 'genuine monitoring coverage incomplete; preparation only')
        for name in ('entry', 'stop'):
            actual = self.mem(self.base + plan[name+'_rva'], len(bytes.fromhex(plan[name+'_bytes'])))
            self.log('monitor_code_identity', boundary=name, actual=actual.hex(), expected=plan[name+'_bytes'])
            core.require(actual.hex() == plan[name+'_bytes'], 'Init boundary code identity')
        self.breakpoints = {self.sym('xrt_fatal'): 'fatal_entry',
                            self.sym('d8_semantic_checkpoint'): 'semantic_checkpoint',
                            self.base + plan['entry_rva']: 'init_entry'}
        check_environment('target-created-before-first-resume')

    def evidence(self, tag, ctx, tid):
        # Host observation is durable even if a subsequent target memory read fails.
        self.log('monitor_raw_host', tag=tag, tid=tid, host=ctx.snapshot(), generation=self.monitor_generation)
        self.log('monitor_raw_stack', tag=tag, raw=self.mem(ctx.get('rsp'), 96).hex())
        pointer = ctx.get('rcx') if tag in ('init_entry', 'semantic_checkpoint') else self.cpu
        if tag == 'init_return': pointer = ctx.get(plan['stop_registers']['cpu'])
        if pointer:
            raw = self.mem(pointer, 416)
            self.log('monitor_raw_cpu', tag=tag, address=pointer, raw=raw.hex())
            if self.guest_base:
                esp = struct.unpack_from('<I', raw, 16)[0]
                if esp <= 0xffffff80:
                    self.log('monitor_raw_guest_stack', tag=tag, esp=esp,
                             raw=self.mem(self.guest_base+esp, 128).hex())
            self.log('monitor_raw_objects', tag=tag, objects=self.object_state(), hwnds=self.hwnds())
        return pointer

    def hit(self, tag, ctx, tid):
        try:
            pointer = evidence(self, tag, ctx, tid)
            self.monitor_counts[tag] = self.monitor_counts.get(tag, 0) + 1
            if tag == 'init_entry':
                raw = self.mem(pointer, 416)
                self.log('integrated_init_entry_raw', tid=tid, cpu=pointer, raw=raw.hex(), host=ctx.snapshot())
                core.require(self.init_entry is None, 'duplicate Init entry')
                self.guest_base = self.u64(self.sym('xrt_g'))
                self.cpu = pointer
                esp = struct.unpack_from('<I', raw, 16)[0]
                caller = self.mem(self.guest_base+esp, 4)
                self.log('monitor_init_caller', raw=caller.hex())
                core.require(caller == struct.pack('<I', GUEST), 'Init caller')
                self.init_entry = dict(tid=tid, cpu=pointer, raw=raw.hex())
                idle(self)
                return
            if tag == 'init_return':
                raw = self.mem(pointer, 416)
                code = self.mem(ctx.get('rip'), len(bytes.fromhex(plan['stop_bytes'])))
                self.log('resource_init_endpoint_raw', raw_cpu=raw.hex(), host=ctx.snapshot(),
                         actual_code=code.hex(), instruction_executed=False)
                core.require(ctx.get('rip') == self.base+plan['stop_rva'] and code.hex() == plan['stop_bytes'], 'Init stop instruction')
                core.require(ctx.get('rbx') & 0xffffffff == GUEST, 'Init boundary register')
                core.require(not self.entries and self.native_active is None and not self.callback_frames,
                             'outstanding native/callback operation at Init return')
                self.snapshot_events()
                data = read(self.out/'runtime-events.json')
                core.require(data['events_dropped'] == 0, 'dropped runtime evidence')
                result = verify_pair(self.init_entry, raw, data['events'], tid, pointer)
                self.log('integrated_init_verified', **result, monitoring_counts=self.monitor_counts,
                         genuine_coverage_qualified=False, owned_fixture=owned_fixture)
                self.stop_requested = True
                return
            if tag == 'semantic_checkpoint':
                phase, slot = ctx.get('rdx') & 0xffffffff, ctx.get('r8') & 0xffffffff
                self.log('monitor_checkpoint_dispatch', phase=phase, slot=slot)
                # The retained handler silently skipped unsupported phase-zero
                # signatures. Never permit their native execution in this proposal.
                core.require(slot in semantic.NARGS, 'unqualified native signature: '+str(slot))
                core.require(phase in (0, 1, 2, 3), 'unknown native phase')
                if phase == 0:
                    core.require(self.monitor_owner is None, 'overlapping operation or callback reentry')
                    self.monitor_owner = tid
                core.require(self.monitor_owner == tid, 'cross-thread native operation')
                if phase == 1 and slot == 100: check_environment('before-CreateDevice')
            if tag == 'semantic_callback':
                self.log('monitor_callback_entry', depth=len(self.callback_frames)+1, host=ctx.snapshot())
            if tag == 'semantic_callback_return':
                self.log('monitor_callback_return', depth=len(self.callback_frames), host=ctx.snapshot())
            if tag.startswith('semantic_native') or tag.startswith('semantic_callback'):
                core.require(self.monitor_owner == tid, 'cross-thread native/callback boundary')
            detailed_hit(tag, ctx, tid)
            if tag == 'semantic_checkpoint' and phase == 3:
                self.monitor_owner = None
                idle(self)
            # The detailed handler releases its phase checkpoint while a native
            # method/callback is active. Keep its exact entry/return/stack logic.
            if tag == 'semantic_native_return':
                self.breakpoints[self.sym('invoke_gui_proc')] = 'semantic_callback'
            if tag == 'fatal_entry':
                raise core.Rejected('fatal before Init return; no retry')
        except BaseException:
            self.snapshot_events()
            raise

    capture.on_create = MethodType(on_create, capture)
    capture.hit = MethodType(hit, capture)
    capture.update = MethodType(lambda self, ctx, resume=False: arm_all(self, ctx, plan, resume), capture)
    return capture

def construct(out, plan, check_environment, dependencies):
    capture, _ = semantic.construct(out, plan, check_environment, dependencies)
    capture.out = out
    return install(capture, plan, check_environment)

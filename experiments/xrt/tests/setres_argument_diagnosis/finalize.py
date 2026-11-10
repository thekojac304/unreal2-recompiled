"""Seal offline preparation and its explicit evidence/readiness limits."""
import copy
import json
import pathlib
import shutil
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
from attach_audit import audit


def run():
    core.require(read(O/'fixture-validation.json')['passed'] and read(O/'native-x86-abi-validation.json')['passed'],'fixture qualification incomplete')
    data=read(ATTEMPT/'runtime-events.json')['events']
    actual=[e for e in data if e['kind'].startswith('gui_attach_thread_input_')]
    tests=[]
    for name,events,accept in [('actual-original-branch',actual,True),('omitted-original-branch',[],True),
            ('missing-detach',actual[:2],False),('wrong-detach-flag',copy.deepcopy(actual),False),
            ('wrong-result',copy.deepcopy(actual),False)]:
        if name=='wrong-detach-flag':events[-1]['attach']=1
        if name=='wrong-result':events[-1]['result']=1
        passed=False
        try:audit(events);passed=True
        except core.Rejected:pass
        core.require(passed==accept,'attach/detach audit case failed: '+name)
        tests.append(dict(case=name,accepted=passed,passed=True))
    save(O/'attach-audit-validation.json',dict(passed=True,cases=tests,genuine_launches=0))
    strict_files=read(OLD/'preservation.json')['strict_failure_files']
    strict=O/'strict-failures';strict.mkdir()
    for name,digest in strict_files.items():
        core.require(core.sha(name)==digest,'retained strict evidence changed')
        shutil.copy2(name,strict/pathlib.Path(name).name)
    gamma=W/'out/recovery/renderer-gamma-integration-20261029-01/physical-gamma-abi-audit.json'
    shutil.copy2(gamma,strict/gamma.name)
    save(strict/'status.json',dict(strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained',
         evidence={**strict_files,str(gamma):core.sha(gamma)},
         native_x86_fixture_scope='The new owned ABI probe passes; it does not pass the strict native-x86 renderer compatibility gate.'))
    failures=[]
    for root in O.glob('native-x86-abi-*'):
        path=root/'0/debug-events.jsonl'
        if not path.exists():continue
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        if any(r['kind']=='exception' and r.get('first_chance')==0 for r in rows):
            cleanup=next(r for r in reversed(rows) if r['kind']=='process_tree_cleanup')
            core.require(cleanup['passed'],'failed fixture cleanup unverified')
            failures.append(dict(evidence=str(root),classification='non-game fixture harness limitation',
                reason='x64 debugger loop did not recognize STATUS_WX86_BREAKPOINT 0x4000001f',cleanup=cleanup,
                repair='An isolated local function copy accepts the WOW64 breakpoint for owned x86 tests; production supervisor is untouched.'))
    save(O/'development-repairs.json',dict(failed_fixture_runs=failures,genuine_failures_reclassified=0))
    report='''Unreal II SetRes argument mismatch investigation — preparation only

Conclusion
The observer conflates two genuine SetRes callers. Initial viewport setup in
WinDrv calls virtual slot +78 at 11104BF5 and returns to 11104BF8. The failed
observer requires 0696D2CD, which is the continuation of a different call in
D3DDrv::Lock (0696D2CA). The original x86 ABI and six-word layout are correct.
No game/renderer compatibility or configuration defect is established here.

Critical evidence limit
The exact SetRes frame CANNOT be recovered from this consumed attempt. The
assertion executes before self.log(setres_entry). The guarded exception handler
copies only the runtime event array. All 387 raw debugger observations were
examined: none stores CPU/CONTEXT/guest-stack bytes at the failing exception.
DEBUG_EVENT's EXCEPTION_RECORD contains the hardware address, not guest memory.
The complete copied runtime array/stream has 74,493 equal, untruncated records,
with no SetRes frame event. There is no process dump in the attempt. Do not
label the following reconstruction as an exact observed frame.

Frame word   Role           Reconstruction / evidence
0            return        0x11104BF8, inferred from original initial call flow;
                           observer requires 0x0696D2CD.
1            viewport      0x142D8800, recorded TryRenderDevice receiver; original
                           PUSH ESI forwards it. SetRes word was not captured.
2            width         1540 (0x604), recorded window geometry and unchanged INI;
                           SetRes word was not captured.
3            height        945 (0x3B1), recorded window geometry and unchanged INI;
                           SetRes word was not captured.
4            fullscreen    UNKNOWN live word. Config predicts 0; original combines
                           renderer[+70] with the qualified fullscreen request.
5            color bits    32 (0x20), original initial caller's immediate PUSH 20;
                           SetRes word was not captured.
Renderer this is in guest ECX, not the stack. Its live value was not captured.
The necessary mismatching component under the original call flow is frame[0].
The saved assertion alone cannot prove every other live component matched.

Independent original x86 decode
Export: ?SetRes@UD3DRenderDevice@@UAEHPAVUViewport@@HHHH@Z, RVA E890,
translated VA 0696E890 (original preferred image base 10000000).
Both callers push color, fullscreen, height, width, viewport, then CALL. Thus
at entry ESP points to [return,viewport,width,height,fullscreen,color_bits].
The callee establishes EBP, consumes [EBP+8..18], and returns with C2 14 00
(RET 20), producing a total guest ESP delta of 24 including return address.
original-x86-decode.json retains exact original bytes, exports and instructions.

Genuine configuration sources
System/Unreal2.ini hash before, after and now is
bcb0c403fa71e7f82a64a8ee06ea3b5ff1f1ec2435b3e4d14756c5b5aaeccac4.
WindowedViewportX=1540, WindowedViewportY=945, StartupFullscreen=false,
Use16bit=False; the genuine command contains -windowed. The recorded input
rectangle [100,100,1640,1045] confirms 1540x945. Default.ini's 800x600 defaults
are not the active values. No settings or argument values were changed.
config-sources.json traces the exact fields, branches and source limitations.
Requested depth 32 is not proof of any created native presentation format.

Last verified milestone and native work
Raw exception index 373 is a hardware stop at the exact translated SetRes
function entry (symbol RVA from the saved debugger plan). It precedes that
function's guest prologue. No CreateDevice, Clear, Present, device state,
configured batch, material or gamma call/return exists in this attempt.
Earlier Direct3DCreate8, adapter enumeration/identification and GetDeviceCaps
completed successfully, so saying no native graphics work occurred is wrong.
Termination before continue and Job cleanup passed (remaining processes 0).
SetRes completion, OpenWindow return, engine Init return and world ticking
are not established by this stop. Earlier historical renderer milestones are
not attributed to this attempt.

Additional observer defects relevant before completion
The permanent 0696D2CD endpoint belongs to Lock's device-null recovery branch.
Successful initial SetRes creates renderer[+4698]; Lock then skips that call.
It is not a sound endpoint for initial SetRes completion. Its exact mapping
and permanent limits remain unchanged; no expansion was made.
The genuine stream also contains TWO self-thread USER32 pairs: attach=1 at
return 11104A4E and detach=0 at return 11104ACE, both FALSE/87 and ESP+16.
The old owner's at-most-one attach=1 audit would reject this original branch
later. A separate offline audit now checks the exact optional pair, with five
positive/negative cases. It does not qualify cross-thread queue attachment.

Fresh isolated correction and validation
experiments/xrt/tests/setres_argument_diagnosis/observer.py classifies initial
and Lock callers separately, saves raw host/CPU/frame bytes BEFORE assertions,
reports each failed component, reads renderer/viewport source fields, and stops
at first entry before any device operation. Ten live x64 debugger fixture cases
pass, including each argument rejection, receiver mismatch and evidence-write
failure. Four independent native x86 debugger cases use real CALL/RET 20 and
ECX thiscall, verify all six words, ESP+24, and both fullscreen OR sources.
An initial owned x86 fixture harness failure is retained separately with its
cleanup evidence and local WOW64 repair. No production debugger edits occurred.

Preservation and readiness
The complete original sandbox, consumed build and attempt, runtime/generated
sources, production supervisor/global ledger and prior failure packages are
preserved in place with full before/after content inventories. The complete raw
attempt, candidate EXE/PDB, global ledger and original failure/consumption marker
also have independently verified copies here. No consumed marker, hold or
authorization was reset. Strict x87, WNDPROC and native-x86 failures are retained
separately under strict-failures/; the owned ABI tests do not change those gates.

The diagnostic capture routine is qualified. A genuine completion continuation
is NOT launch-ready: the exact historical frame is unavailable, the candidate
is consumed, and initial completion needs a correctly mapped bounded return
observer. This preparation intentionally has no owner launcher; its factory's
creation hook rejects the consumed identity. A future separately prepared fresh
candidate/identity and initial-return mapping must be qualified before a later
bounded continuation. Do not manufacture an identity-only rebuild to bypass the
consumption rule. No genuine game launch, candidate retry, configuration change,
renderer-profile expansion, original-install/save edit, push or release occurred.
'''
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    from investigate import verify
    verify()
    files={str(H/p):digest for p,digest in core.tree(H).items()}
    files.update({str(O/p):digest for p,digest in core.tree(O).items()})
    save(O/'preparation-seal.json',dict(passed=True,files=files,implementation=core.tree(H),
         diagnostic_capture_qualified=True,genuine_completion_ready=False,genuine_authorized=False,
         genuine_launches=0,consumed_candidate_retry=False,permanent_breakpoint_expansion=False,
         reason='Historical frame missing; consumed candidate forbidden; initial completion endpoint requires separate preparation.',
         strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained'))
    print('PREPARATION SEALED. 19 focused cases pass. Zero genuine launches. Completion readiness remains blocked by documented evidence/identity/endpoint limits.',flush=True)


if __name__=='__main__':run()

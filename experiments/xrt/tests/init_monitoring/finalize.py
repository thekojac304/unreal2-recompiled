"""Seal the concrete preparation result. Never converts partial coverage to READY."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    identity_record=read(O/'candidate-identity.json');plan=read(O/'composed-mapping.json')
    coverage=read(O/'coverage.json');live=read(O/'live-validation.json')
    checks=read(O/'regression-validation.json');hardware=read(O/'debugger-validation.json')
    contained=read(O/'containment-validation.json');preservation=read(O/'preservation-after.json')
    for receipt in (identity_record,live,checks,hardware,contained,preservation):
        core.require(receipt['passed'],'failed preparation receipt')
    for name in ('composition.py','common.py','protocol.c','live.py'):
        core.require(core.sha(H/name)==live['source'][name],'live-tested observer/fixture source changed: '+name)
    core.require(not coverage['complete'],'coverage changed; report requires fresh review')
    core.require(core.sha(identity()[0])==identity()[1] and core.sha(identity()[0].with_suffix('.pdb'))==identity()[2],'candidate changed')
    physical=read(W/'out/recovery/resource-functional-assessment-20261030-01/physical-audit.json')
    core.require(physical['strict_native_x86']=='FAILED','historical strict verdict')
    risks=dict(strict_native_x86_compatibility='FAILED',
        source=str(W/'out/recovery/resource-functional-assessment-20261030-01/physical-audit.json'),
        source_sha256=core.sha(W/'out/recovery/resource-functional-assessment-20261030-01/physical-audit.json'),
        last_error=physical['differences'],
        fpu=[dict(parameters=r['parameters'],strict_failures=r['strict_failures']) for r in physical['reports']],
        experimental_exception_granted=False,normalization=False,
        prior_directinput_Acquire_difference='Independent invocations: last-error 0 versus 5; actual inner-native transfer separately passed.',
        prior_x87_WNDPROC='Historical strict x87 and complete WNDPROC equality remain FAILED.',
        runtime_dependency_proof=False,
        scope='Only the saved 114-operation-per-variant fixtures, their exact backend/configurations and measured precision-status bits. No blanket FPU or last-error exception.')
    save(O/'retained-risks.json',risks)
    result=dict(status='NOT_READY_MONITORING_INCOMPLETE',complete_monitoring=False,
        genuine_execution_ready=False,execution_authorized=False,observer_installed=False,
        candidate=identity_record,guest_stop='0x1090ED5C',stop_rva=hex(plan['stop_rva']),stop_bytes=plan['stop_bytes'],
        bounded_future_scope=dict(maximum_launches=1,seconds=60,retry=False,main_loop_ticks=False),
        strict_native_x86_compatibility='FAILED',blocking_requirements=coverage['blocking_requirements'],
        live_cases=len(live['results']),live_passes=sum(r['passed'] for r in live['results']),regression_tests=checks['tests'],
        hardware_qualification_scope=hardware['scope'],genuine_launches=0,physical_launches=0,
        authorization_procedure=None,
        authorization_reason='No owner launch/activation procedure is issued until complete monitoring gates pass. Existing production stop/authorization remains unchanged.')
    save(O/'readiness.json',result)
    report=f'''Init monitoring preparation — NOT READY

The requested full monitoring integration is NOT complete. Do not launch or
activate this staged observer. All artifacts are separate from historical
handoffs. No genuine game or physical GPU fixture was launched.

Implemented and validated
- Composed the retained detailed semantic native-entry/return and nested callback
  handlers with paired UGameEngine::Init entry/return checks on owned non-game code.
- Preserved raw host registers/FXSAVE, full 416-byte guest CPUs, native HRESULT and
  TEB last-error, guest stack/inputs, COM/device identity and callback nesting.
  Raw evidence precedes assertions, including malformed/duplicate Init boundaries.
- Every breakpoint schedule is now written/read back on EVERY live thread in the
  staged instance. Fatal and endpoint remain armed during native/callback nesting.
  Four-slot overflow/collision is a rejection, never silent monitor removal.
- Unknown renderer signatures stop at phase zero, before native dispatch. The
  older observer silently treated these as auxiliary entries. No broad FPU waiver
  is inherited: an observed strict difference is saved, then execution is stopped.
- {sum(r['passed'] for r in live['results'])} live composition cases passed, including native failure (actual E_FAIL,
  last-error 87), two native operations across the owned Init interval, depth-two
  callback pairs, fatal during callback, guest corruption, unqualified texture,
  failed evidence/readback and watchdog. Each live thread received every schedule;
  the successful interval exercised three simultaneous threads.
- An additional adversarial callback case FAILED full monitoring qualification:
  a phase-zero checkpoint inside an active callback was not trapped. The owned
  marker and raw trace are retained. No actual resource API executed in that test.
  Four slots already held fatal, endpoint, callback entry and callback return.
  Fatal/endpoint remained armed, but the operation checkpoint was absent. This
  failed coverage verdict is retained; the protocol reaching Init is not a pass.
- {checks['tests']} isolated regression tests passed. Retained production observer fatal,
  module-denial and stream/snapshot tests passed. Separate watchdog, descendant
  Job cleanup and cancellation tests passed. All reported remaining Job counts=0.

Candidate retained unchanged and unconsumed
EXE: {identity()[0]}
SHA256: {identity()[1]}
PDB SHA256: {identity()[2]}
PE/PDB GUID: {identity_record['pe_pdb']['guid']}, age {identity_record['pe_pdb']['age']}
All 279 object source/header/toolchain lineages independently reverified; exact
link inputs comprise 265 generated + 12 reused runtime + 2 compiled runtime objects.
All 60 selected linked adapter identities reverified. No relink or candidate retry.

Hardware stop
Guest 0x1090ED5C; host RVA {hex(plan['stop_rva'])}; bytes {plan['stop_bytes']}:
mov dword ptr [rdi+0x44], ebx. Original indirect Init call/checked return mapped.
Candidate was mapped SEC_IMAGE_NO_EXECUTE only. Owned identical instruction was
stopped before execution, with live DR readbacks, including new threads. No claim
that the genuine candidate reached this endpoint. Job termination precedes resume.

Exact retained risks
Strict native-x86 compatibility remains FAILED. Physical functional qualification
within its measured scope is retained; no GPU matrix rerun or renderer edit.
CreateTexture: operation 14 (zero-based 13), slot 20, native x86 last-error=0;
native x64/translated x64=0x13572468. HRESULT/resource output agree. Never normalize.
Seven outer FPU failures per variant: resource Clear x3, DrawPrimitive, first
Present, transfer CreateDepthStencilSurface and transfer Clear. MXCSR changes
0x3F80 -> 0x3FA0, except native-x86 depth creation changes x87 status 0x3000 ->
0x3020. These are outer-wrapper fixture measurements, not complete inner-native
observations of genuine Init. Exact indexed pre/post records are retained-risks.json.
Historical x87/WNDPROC and independent DirectInput Acquire last-error differences
remain failures. No experimental policy has been granted. Guest consumers still
need actual-path observation or scoped nondependence proof.

Remaining gates (substantial implementation/qualification work, not permission to launch)
'''+''.join(f'{i+1}. {b}\n' for i,b in enumerate(coverage['blocking_requirements']))+'''
The retained renderer observer has only 12 known signatures; the scan finds 99
additional literal slot identifiers, including explicitly unsupported stubs.
That count is a conservative source inventory, not 99 required supported methods.
Passing the owned protocol tests does not establish complete genuine-interval
coverage, real GUI/DirectInput composition, or renderer resource-lifetime capture.

Owner authorization
No launch command or authorization token is issued: monitoring gates did not pass.
The one-launch/60-second scope is retained as a future review constraint only.
Do not reuse the old endpoint-only handoff. Production supervisor/stop/ledgers,
original installation/saves, consumed identities and strict failures are unchanged.
No remote push or release. Preparation stops with readiness=false.

Preservation qualification
Historical evidence CONTENT hashes, strict verdicts, ledgers, candidate and
original assets/saves match the baseline. Exact metadata preservation is false:
the retained functional-assessment verify.py main program rewrote three JSON
receipts byte-identically (assessment-tests.json, monitor-coverage.json,
reader-crosscheck.json), changing their mtimes. The runner was corrected to import
only its unittest cases. No timestamps were backdated and no content was lost.
The already-running disposable fixture service also updated status.json; its
other files and ledgers match. The open supervisor.lock was explicitly excluded
from hashing and never modified. See preservation-after.json for exact exceptions.
'''
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    receipts=['candidate-identity.json','stop-mapping.json','composed-mapping.json','linked-adapters.json',
              'coverage.json','live-validation.json','regression-validation.json','debugger-validation.json',
              'containment-validation.json','preservation-before.json','preservation-after.json',
              'historical-inventory.json','retained-risks.json','readiness.json','REPORT.txt']
    save(O/'seal.json',dict(source=core.tree(H),receipts={name:core.sha(O/name) for name in receipts},
                          complete_monitoring=False,genuine_execution_ready=False))
    print(result['status'],str(O/'REPORT.txt'),flush=True)

if __name__=='__main__':main()
